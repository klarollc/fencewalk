"""DNS-registrar fixture tests: the fictional Wrenfield Advisory domains,
DNS and mail authentication, scored against dns-registrar-security-1.0,
as the fourth bundled fixture.

The fixture is single-pack: engagement.json names no extra packs, and
every citation is to the DNS pack. These tests load the fixture by name
from an arbitrary working directory and assert its shape from the loaded
store (every per-item status from the brief's §5.1, the chain controls
from §5.3); that EXPECTED-REPORT.md is byte-identical to a fresh render
from two fresh databases; that the packet at PACKET_DATE is pinned by
byte count and sha256; that the PDF renders deterministically at a pinned
page count; and the fixture's machine-checked scrub.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "dns-registrar"
PACK_PATH = (REPO_ROOT / "src" / "fencewalk" / "packs"
             / "dns-registrar-security-1.0.json")
PACK_ID = "dns-registrar-security-1.0"
PACKET_DATE = "2026-11-20"

PRISTINE_PACKET_BYTES = 15758
PRISTINE_PACKET_SHA256 = (
    "3a65cbcabb189943f83a0dfa08cca321bf260a68c6ac9daac485fe5048cb45de"
)
PDF_PAGES = 4

# The brief's §5.1 per-item statuses (DNS-EM-04 reworded by Amendment 1
# R1, status unchanged).
EXPECTED_STATUS = {
    "DNS-REG-01": "Partial", "DNS-REG-02": "Covered", "DNS-REG-03": "Gap",
    "DNS-REG-04": "Gap", "DNS-REG-05": "Partial",
    "DNS-ZONE-01": "Covered", "DNS-ZONE-02": "Gap", "DNS-ZONE-03": "Gap",
    "DNS-ZONE-04": "Covered",
    "DNS-NS-01": "Gap", "DNS-NS-02": "Unknown", "DNS-NS-03": "Gap",
    "DNS-EM-01": "Partial", "DNS-EM-02": "Gap", "DNS-EM-03": "Partial",
    "DNS-EM-04": "Gap", "DNS-EM-05": "Gap", "DNS-EM-06": "Gap",
    "DNS-EM-07": "Gap", "DNS-EM-08": "Gap",
    "DNS-TLS-01": "Gap", "DNS-TLS-02": "Gap", "DNS-TLS-03": "Gap",
    "DNS-TLS-04": "Unknown",
    "DNS-SUB-01": "Gap", "DNS-SUB-02": "Gap", "DNS-SUB-03": "Gap",
    "DNS-SUB-04": "Partial",
}
EXPECTED_TALLIES = {
    "Covered": 3, "Partial": 5, "Unknown": 2, "Not applicable": 0, "Gap": 18,
}
EXPECTED_LABELS = {"VERIFIED": 15, "ON RECORD": 5, "UNKNOWN": 5}
CHAIN_CONTROLS = {"A": "DNS-EM-04", "B": "DNS-SUB-02", "C": "DNS-REG-03"}

GUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
IPV6 = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
PHONE = re.compile(r"\(?\b\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")
HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|dev|app|cloud|co|uk)\b")


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def scrub_hits(text):
    """Every identifier-shaped string in text that the scrub forbids."""
    hits = []
    hits += [("guid", m) for m in GUID.findall(text)]
    hits += [("email", m) for m in EMAIL.findall(text)
             if not m.lower().endswith(".example")]
    hits += [("ipv4", m) for m in IPV4.findall(text)]
    hits += [("ipv6", m) for m in IPV6.findall(text)]
    hits += [("phone", m) for m in PHONE.findall(text)]
    hits += [("host", m) for m in HOST.findall(text)]
    return hits


class DnsFixtureLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp.name) / "dns.db")
        load_fixture(bundled_fixture_dir("dns-registrar"), cls.db_path)
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)
        cls.pack_items = [i["item_id"] for i in cls.pack["items"]]
        store = Store(cls.db_path)
        try:
            cls.engagement = store.get_engagement()
            cls.packs = [p["pack_id"] for p in store.list_packs()]
            cls.scores = [store.get_coverage(PACK_ID, i) for i in cls.pack_items]
            cls.all_scores = store.conn.execute(
                "SELECT pack_id, item_id, status FROM coverage_score"
            ).fetchall()
            cls.fixes = {f["fix_id"]: f for f in store.list_fixes()}
            cls.chains = {c["chain_key"]: c for c in store.list_chains()}
            cls.verify = [dict(r) for r in store.list_verify_next()]
            cls.entries = {r["entry_id"]: dict(r) for r in store.conn.execute(
                "SELECT * FROM inventory_entry").fetchall()}
        finally:
            store.close()
        cls.status = {s["item_id"]: s["status"] for s in cls.scores}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bundled_by_name(self):
        self.assertIn("dns-registrar", bundled_fixture_names())
        self.assertEqual(bundled_fixture_dir("dns-registrar"), FIXTURE_DIR)

    def test_engagement_record_single_pack(self):
        self.assertEqual(
            self.engagement["name"],
            "DNS and registrar case — Wrenfield Advisory perimeter audit")
        self.assertEqual(self.engagement["subject_label"],
                         "Wrenfield Advisory LLC (fictional demo firm)")
        self.assertEqual(self.engagement["created_date"], PACKET_DATE)
        self.assertEqual(self.engagement["method_order"], "verify-first")
        raw = json.loads((FIXTURE_DIR / "engagement.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["pack_file"],
                         "../../packs/dns-registrar-security-1.0.json")
        self.assertNotIn("extra_pack_files", raw)
        self.assertEqual(self.packs, [PACK_ID])

    def test_every_pack_item_scored_once(self):
        self.assertTrue(all(s is not None for s in self.scores))
        scored = [r["item_id"] for r in self.all_scores]
        self.assertEqual(sorted(scored), sorted(self.pack_items))
        self.assertEqual({r["pack_id"] for r in self.all_scores}, {PACK_ID})

    def test_per_item_statuses_and_tallies(self):
        self.assertEqual(self.status, EXPECTED_STATUS)
        counts = Counter(self.status.values())
        self.assertEqual({k: counts.get(k, 0) for k in EXPECTED_TALLIES},
                         EXPECTED_TALLIES)

    def test_every_score_cites_existing_entries(self):
        for s in self.scores:
            self.assertIsNone(s["na_reason"], s["item_id"])
            self.assertTrue(s["cited_entry_ids"], s["item_id"])
            for eid in s["cited_entry_ids"]:
                self.assertIn(eid, self.entries, s["item_id"])
            text = s["reasoning"]
            self.assertEqual(text, " ".join(text.split()), s["item_id"])
            self.assertNotIn("|", text, s["item_id"])

    def test_inventory_labels_and_dates(self):
        counts = Counter(e["label"] for e in self.entries.values())
        self.assertEqual(dict(counts), EXPECTED_LABELS)
        for e in self.entries.values():
            self.assertIn(e["section"], "ABCDEFGH")
            self.assertTrue(e["entry_id"].startswith(e["section"]))
            self.assertTrue(e["source"].strip())
            if e["label"] == "VERIFIED":
                self.assertEqual(e["checked_date"], PACKET_DATE, e["entry_id"])
            else:
                self.assertIsNone(e["checked_date"], e["entry_id"])

    def test_chains_rest_on_the_pack(self):
        self.assertEqual(sorted(self.chains), ["A", "B", "C"])
        for key, control in CHAIN_CONTROLS.items():
            chain = self.chains[key]
            self.assertEqual(chain["control_rubric"], control)
            self.assertEqual(chain["control_pack"], PACK_ID)
            self.assertEqual(chain["control_status"], "Gap")
            self.assertEqual(self.status[control], "Gap")
        steps_c = " ".join(s["text"] for s in self.chains["C"]["steps"])
        self.assertNotIn("out-of-band", steps_c)

    def test_fixes(self):
        self.assertEqual(list(self.fixes), [f"F-{n}" for n in range(1, 11)])
        for fix in self.fixes.values():
            self.assertEqual(fix["status"], "proposed", fix["fix_id"])
            self.assertEqual(fix["status_actor"], "operator", fix["fix_id"])
            self.assertEqual(fix["status_date"], PACKET_DATE, fix["fix_id"])
            self.assertTrue(fix["rubric_item_ids"], fix["fix_id"])
            for item, pack in fix["rubric_item_packs"].items():
                self.assertEqual(pack, PACK_ID, fix["fix_id"])
                self.assertIn(item, EXPECTED_STATUS, fix["fix_id"])
        f1 = self.fixes["F-1"]
        self.assertEqual(f1["rubric_item_ids"], ["DNS-EM-04", "DNS-EM-05"])
        self.assertIn("p=quarantine", f1["action"])
        self.assertIn("at least a month", f1["action"])
        self.assertEqual(f1["chains_broken"], "A")

    def test_verify_next_matches_unknowns(self):
        self.assertEqual([v["seq"] for v in self.verify], [1, 2, 3, 4, 5])
        unknown_entries = sorted(
            e for e, d in self.entries.items() if d["label"] == "UNKNOWN")
        named = sorted(
            m for v in self.verify
            for m in re.findall(r"\(([A-H]\d+)\)", v["unknown_text"]))
        self.assertEqual(named, unknown_entries)
        for item in (i for i, st in self.status.items() if st == "Unknown"):
            self.assertTrue(any(item in v["why"] for v in self.verify), item)


class DnsFixtureCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def _load(self, name):
        db = str(Path(self.tmp.name) / name)
        code, out, err = run_cli(["load-fixture", "dns-registrar", db])
        self.assertEqual(code, 0, err)
        self.assertIn("dns-registrar", out)
        return db

    def test_expected_report_from_two_fresh_databases(self):
        expected = (FIXTURE_DIR / "EXPECTED-REPORT.md").read_bytes()
        for n in (1, 2):
            db = self._load(f"report{n}.db")
            self.assertEqual(render_report(db).encode("utf-8"), expected)
            out = Path(self.tmp.name) / f"report{n}.md"
            code, _, err = run_cli(["report", db, "--out", str(out)])
            self.assertEqual(code, 0, err)
            self.assertEqual(out.read_bytes(), expected)

    def test_report_renders_chain_controls_bare(self):
        text = render_report(self._load("annot.db"))
        for control in CHAIN_CONTROLS.values():
            self.assertIn(f"({control}) Status: Gap.", text)
        # Single-pack: no citation is annotated with a pack id.
        self.assertNotIn(f"({PACK_ID})", text)

    def test_packet_and_pdf_pinned_across_fresh_databases(self):
        packets, pdfs = [], []
        for n in (1, 2):
            db = self._load(f"det{n}.db")
            out = Path(self.tmp.name) / f"packet{n}.md"
            code, _, err = run_cli(
                ["packet", db, "--date", PACKET_DATE, "--out", str(out)])
            self.assertEqual(code, 0, err)
            packets.append(out.read_bytes())
            pdfs.append(render_pdf(db))
        self.assertEqual(packets[0], packets[1])
        self.assertEqual(len(packets[0]), PRISTINE_PACKET_BYTES)
        self.assertEqual(hashlib.sha256(packets[0]).hexdigest(),
                         PRISTINE_PACKET_SHA256)
        self.assertEqual(pdfs[0], pdfs[1])
        self.assertTrue(pdfs[0].startswith(b"%PDF-"))
        self.assertEqual(
            len(re.findall(rb"/Type /Page(?!s)", pdfs[0])), PDF_PAGES)
        self.assertIn(f"/Count {PDF_PAGES}".encode(), pdfs[0])


class DnsFixtureScrubTest(unittest.TestCase):
    def test_fixture_files_carry_no_identifiers(self):
        files = sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file())
        self.assertEqual(len(files), 9)
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertEqual(scrub_hits(text), [], path.name)

    def test_scrub_check_catches_what_it_forbids(self):
        planted = (
            "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0 ops@contoso.com"
            " 10.20.30.40 2001:db8:0:1::53 (212) 555-0199 ns1.provider.net"
        )
        kinds = sorted({k for k, _ in scrub_hits(planted)})
        self.assertEqual(
            kinds, ["email", "guid", "host", "ipv4", "ipv6", "phone"])
        allowed = ("dmarc@wrenfield.example help.wrenfield.example"
                   " wrenfieldgroup.example DNS-EM-04 RFC 9989 2027-03-18")
        self.assertEqual(scrub_hits(allowed), [])


if __name__ == "__main__":
    unittest.main()
