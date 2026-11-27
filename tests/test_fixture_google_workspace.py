"""Google-workspace fixture tests: the fictional Larkspur Advisory tenant
on Business Standard, scored against scuba-gws-v1.1.0, with the DNS and
registrar pack loaded beside it for chain B and fix F-2.

Two packs are loaded. Loading records the GWS pack as the primary pack,
so the default render is the golden; the renders here still name the GWS
pack with --pack, and one pins the default render. These tests load the
fixture by
name from an arbitrary working directory and assert its shape from the
store (the coverage guardrails, the Not-applicable classes, the chain
controls); that EXPECTED-REPORT.md is byte-identical to a fresh render
from two fresh databases; the pinned packet and PDF page count; the
cross-pack annotations on chain B and F-2; and the machine-checked scrub.
"""

import hashlib
import io
import json
import os
import re
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import bundled_fixture_dir, bundled_fixture_names, load_fixture
from fencewalk.report import render_report
from fencewalk.report_pdf import render_pdf
from fencewalk.store import Store
from test_report_pack import extract_text

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "google-workspace"
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "scuba-gws-v1.1.0.json"
PACK_ID = "scuba-gws-v1.1.0"
DNS_ID = "dns-registrar-security-1.0"
PACKET_DATE = "2026-11-18"

PRISTINE_PACKET_BYTES = 26727
PRISTINE_PACKET_SHA256 = (
    "9f870c739b11bbb3982785b38e1d8eda0b33e44711e29a6383d7a99657a66081"
)
PDF_PAGES = 10

EXPECTED_TALLIES = {
    "Covered": 45, "Partial": 4, "Unknown": 4, "Not applicable": 11, "Gap": 60,
}
EXPECTED_LABELS = {"VERIFIED": 6, "ON RECORD": 10, "UNKNOWN": 4}
NA_EDITION = {
    "GWS.COMMONCONTROLS.2.1v1", "GWS.COMMONCONTROLS.15.2v1",
    "GWS.COMMONCONTROLS.17.1v1", "GWS.COMMONCONTROLS.18.1v1",
    "GWS.COMMONCONTROLS.18.2v1",
}
NA_FEDERAL = {"GWS.GMAIL.4.3v1"}
CONDITION_UNMET = {
    "GWS.COMMONCONTROLS.3.1v1", "GWS.COMMONCONTROLS.3.2v1",
    "GWS.DRIVEDOCS.1.10v1", "GWS.DRIVEDOCS.1.11v1", "GWS.CALENDAR.3.2v1",
}

GUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
PHONE = re.compile(r"\(?\b\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")
CLIENT_ID = re.compile(r"\b\d{12,}\b|\.apps\.googleusercontent\.com")
HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|dev|app|cloud|co|uk|gov)\b")


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def scrub_hits(text):
    hits = []
    hits += [("guid", m) for m in GUID.findall(text)]
    hits += [("email", m) for m in EMAIL.findall(text)
             if not m.lower().endswith(".example")]
    hits += [("ipv4", m) for m in IPV4.findall(text)]
    hits += [("phone", m) for m in PHONE.findall(text)]
    hits += [("client-id", m) for m in CLIENT_ID.findall(text)]
    # The pack citation's release URL (the source, not an identifier)
    # reaches the rendered report.
    hits += [("host", m) for m in HOST.findall(text) if m != "github.com"]
    return hits


class GwsFixtureLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp.name) / "gws.db")
        load_fixture(bundled_fixture_dir("google-workspace"), cls.db_path)
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)
        cls.pack_items = [i["item_id"] for i in cls.pack["items"]]
        store = Store(cls.db_path)
        try:
            cls.engagement = store.get_engagement()
            cls.packs = [p["pack_id"] for p in store.list_packs()]
            cls.scores = {i: store.get_coverage(PACK_ID, i) for i in cls.pack_items}
            cls.all_scores = store.conn.execute(
                "SELECT pack_id, item_id FROM coverage_score").fetchall()
            cls.fixes = {f["fix_id"]: f for f in store.list_fixes()}
            cls.chains = {c["chain_key"]: c for c in store.list_chains()}
            cls.verify = [dict(r) for r in store.list_verify_next()]
            cls.entries = {r["entry_id"]: dict(r) for r in store.conn.execute(
                "SELECT * FROM inventory_entry").fetchall()}
            cls.dns_items = {i["item_id"] for i in store.list_pack_items(DNS_ID)}
        finally:
            store.close()
        cls.status = {i: s["status"] for i, s in cls.scores.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bundled_by_name(self):
        self.assertIn("google-workspace", bundled_fixture_names())
        self.assertEqual(bundled_fixture_dir("google-workspace"), FIXTURE_DIR)

    def test_engagement_record_and_packs(self):
        self.assertEqual(
            self.engagement["name"],
            "Google Workspace case — Larkspur Advisory perimeter audit")
        self.assertEqual(self.engagement["subject_label"],
                         "Larkspur Advisory LLC (fictional demo firm)")
        self.assertEqual(self.engagement["created_date"], PACKET_DATE)
        self.assertEqual(self.engagement["method_order"], "verify-first")
        raw = json.loads((FIXTURE_DIR / "engagement.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["pack_file"], "../../packs/scuba-gws-v1.1.0.json")
        self.assertEqual(raw["extra_pack_files"],
                         ["../../packs/dns-registrar-security-1.0.json"])
        self.assertEqual(self.packs, [PACK_ID, DNS_ID])

    def test_every_item_scored_once_under_the_gws_pack(self):
        self.assertTrue(all(s is not None for s in self.scores.values()))
        self.assertEqual(sorted(r["item_id"] for r in self.all_scores),
                         sorted(self.pack_items))
        self.assertEqual({r["pack_id"] for r in self.all_scores}, {PACK_ID})

    def test_tallies_within_guardrails(self):
        counts = Counter(self.status.values())
        self.assertEqual({k: counts.get(k, 0) for k in EXPECTED_TALLIES},
                         EXPECTED_TALLIES)
        self.assertGreaterEqual(counts["Gap"], 25)
        self.assertLessEqual(counts["Covered"], 60)
        self.assertGreaterEqual(counts["Unknown"], 3)

    def test_not_applicable_classes(self):
        na = {i for i, st in self.status.items() if st == "Not applicable"}
        self.assertEqual(na, NA_EDITION | NA_FEDERAL | CONDITION_UNMET)
        for item in NA_EDITION:
            reason = self.scores[item]["na_reason"]
            self.assertIn("Business Standard", reason, item)
            self.assertIn("edition documentation", reason, item)
        self.assertIn("federal", self.scores["GWS.GMAIL.4.3v1"]["na_reason"])
        for item, s in self.scores.items():
            if s["status"] == "Not applicable":
                self.assertEqual(s["reasoning"], s["na_reason"], item)
            else:
                self.assertIsNone(s["na_reason"], item)

    def test_condition_unmet_rows_are_not_applicable(self):
        # Amendment 2, R2: the third Not-applicable class.
        for item in CONDITION_UNMET:
            self.assertEqual(self.status[item], "Not applicable", item)
            self.assertIn("condition is unmet", self.scores[item]["na_reason"], item)

    def test_identity_posture(self):
        for item in ("GWS.COMMONCONTROLS.1.1v1", "GWS.COMMONCONTROLS.1.3v1",
                     "GWS.DRIVEDOCS.1.1v1", "GWS.DRIVEDOCS.1.5v1",
                     "GWS.GMAIL.4.2v1"):
            self.assertEqual(self.status[item], "Gap", item)
        self.assertEqual(self.status["GWS.GMAIL.2.1v1"], "Covered")
        self.assertEqual(self.status["GWS.GMAIL.11.1v1"], "Covered")

    def test_every_score_cites_existing_entries(self):
        for item, s in self.scores.items():
            self.assertTrue(s["cited_entry_ids"], item)
            for eid in s["cited_entry_ids"]:
                self.assertIn(eid, self.entries, item)
            self.assertEqual(s["reasoning"], " ".join(s["reasoning"].split()), item)
            self.assertNotIn("|", s["reasoning"], item)

    def test_inventory_labels_and_dates(self):
        counts = Counter(e["label"] for e in self.entries.values())
        self.assertEqual(dict(counts), EXPECTED_LABELS)
        for e in self.entries.values():
            self.assertIn(e["section"], "ABCDEFGH")
            self.assertTrue(e["entry_id"].startswith(e["section"]))
            if e["label"] == "VERIFIED":
                self.assertEqual(e["checked_date"], PACKET_DATE, e["entry_id"])
            else:
                self.assertIsNone(e["checked_date"], e["entry_id"])

    def test_chains(self):
        self.assertEqual(sorted(self.chains), ["A", "B", "C"])
        expected = {"A": ("GWS.COMMONCONTROLS.1.1v1", PACK_ID),
                    "B": ("DNS-EM-04", DNS_ID),
                    "C": ("GWS.DRIVEDOCS.1.5v1", PACK_ID)}
        for key, (control, pack) in expected.items():
            chain = self.chains[key]
            self.assertEqual(chain["control_rubric"], control)
            self.assertEqual(chain["control_pack"], pack)
            self.assertEqual(chain["control_status"], "Gap")
        self.assertIn("DNS-EM-04", self.dns_items)

    def test_fixes(self):
        self.assertEqual(list(self.fixes), [f"F-{n}" for n in range(1, 13)])
        for fix in self.fixes.values():
            self.assertEqual(fix["status"], "proposed", fix["fix_id"])
            self.assertEqual(fix["status_actor"], "operator", fix["fix_id"])
            self.assertEqual(fix["status_date"], PACKET_DATE, fix["fix_id"])
        f2 = self.fixes["F-2"]
        self.assertEqual(f2["rubric_item_packs"],
                         {"DNS-EM-04": DNS_ID, "DNS-EM-05": DNS_ID})
        self.assertIn("p=quarantine", f2["action"])
        self.assertIn("GWS.GMAIL.4.2v1", f2["action"])
        for key, fix in self.fixes.items():
            if key != "F-2":
                self.assertEqual(set(fix["rubric_item_packs"].values()), {PACK_ID})

    def test_verify_next_matches_unknowns(self):
        self.assertEqual([v["seq"] for v in self.verify], [1, 2, 3, 4, 5])
        unknown_entries = sorted(
            e for e, d in self.entries.items() if d["label"] == "UNKNOWN")
        named = sorted(
            m for v in self.verify[1:]
            for m in re.findall(r"\(([A-H]\d+)\)", v["unknown_text"]))
        self.assertEqual(named, unknown_entries)
        self.assertIn("GWS.COMMONCONTROLS.14.1v1", self.verify[0]["unknown_text"])
        for item in (i for i, st in self.status.items() if st == "Unknown"):
            self.assertTrue(any(item in v["why"] for v in self.verify), item)


class GwsFixtureCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def _load(self, name):
        db = str(Path(self.tmp.name) / name)
        code, out, err = run_cli(["load-fixture", "google-workspace", db])
        self.assertEqual(code, 0, err)
        return db

    def test_expected_report_from_two_fresh_databases(self):
        expected = (FIXTURE_DIR / "EXPECTED-REPORT.md").read_bytes()
        for n in (1, 2):
            db = self._load(f"report{n}.db")
            self.assertEqual(render_report(db, PACK_ID).encode("utf-8"), expected)
            out = Path(self.tmp.name) / f"report{n}.md"
            code, _, err = run_cli(
                ["report", db, "--pack", PACK_ID, "--out", str(out)])
            self.assertEqual(code, 0, err)
            self.assertEqual(out.read_bytes(), expected)

    def test_default_render_is_the_expected_report(self):
        # Loading records the GWS pack (pack_file) as the primary pack,
        # so the default render, with no --pack, is the golden.
        expected = (FIXTURE_DIR / "EXPECTED-REPORT.md").read_text(encoding="utf-8")
        self.assertEqual(render_report(self._load("default.db")), expected)

    def test_report_annotates_the_cross_pack_citations(self):
        text = render_report(self._load("annot.db"), PACK_ID)
        self.assertIn(
            "Earliest breaking control: a DMARC enforcement policy in force for"
            " the domain (DNS-EM-04 (dns-registrar-security-1.0)) Status: Gap.",
            text)
        self.assertRegex(
            text, r"\| F-2 \| [^|]+ \| DNS-EM-04 \(dns-registrar-security-1\.0\),"
                  r" DNS-EM-05 \(dns-registrar-security-1\.0\) \|")
        self.assertIn("(GWS.COMMONCONTROLS.1.1v1) Status: Gap.", text)
        self.assertIn("(GWS.DRIVEDOCS.1.5v1) Status: Gap.", text)
        self.assertEqual(text.count("(dns-registrar-security-1.0)"), 3)

    def test_packet_and_pdf_pinned_across_fresh_databases(self):
        packets, pdfs = [], []
        for n in (1, 2):
            db = self._load(f"det{n}.db")
            out = Path(self.tmp.name) / f"packet{n}.md"
            code, _, err = run_cli(["packet", db, "--pack", PACK_ID,
                                    "--date", PACKET_DATE, "--out", str(out)])
            self.assertEqual(code, 0, err)
            packets.append(out.read_bytes())
            pdfs.append(render_pdf(db, PACK_ID))
        self.assertEqual(packets[0], packets[1])
        self.assertEqual(len(packets[0]), PRISTINE_PACKET_BYTES)
        self.assertEqual(hashlib.sha256(packets[0]).hexdigest(),
                         PRISTINE_PACKET_SHA256)
        self.assertEqual(pdfs[0], pdfs[1])
        self.assertEqual(
            len(re.findall(rb"/Type /Page(?!s)", pdfs[0])), PDF_PAGES)
        flat = "".join(extract_text(pdfs[0]).split())
        self.assertEqual(flat.count("(dns-registrar-security-1.0)"), 3)


class GwsFixtureScrubTest(unittest.TestCase):
    def test_fixture_files_carry_no_identifiers(self):
        files = sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file())
        self.assertEqual(len(files), 9)
        for path in files:
            self.assertEqual(scrub_hits(path.read_text(encoding="utf-8")), [],
                             path.name)

    def test_scrub_check_catches_what_it_forbids(self):
        planted = ("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0 ops@contoso.com"
                   " 10.20.30.40 (212) 555-0199 123456789012"
                   " x.apps.googleusercontent.com reports@dmarc.cyber.dhs.gov")
        kinds = sorted({k for k, _ in scrub_hits(planted)})
        self.assertEqual(kinds, ["client-id", "email", "guid", "host", "ipv4",
                                 "phone"])
        self.assertEqual(scrub_hits("it@larkspur.example GWS.GMAIL.4.2v1"
                                    " 2026-11-18"), [])


if __name__ == "__main__":
    unittest.main()
