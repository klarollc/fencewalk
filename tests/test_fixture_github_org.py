"""GitHub-org fixture tests: the fictional Alder Creek Advisory GitHub
organization, scored against github-org-security-1.0, as the third
bundled fixture.

The fixture carries the first cross-pack chain: chain A's control and
fix F-9's citation are items of the SCuBA pack, loaded beside the
GitHub pack through engagement.json's extra_pack_files. These tests
load the fixture by name from an arbitrary working directory and
assert its shape from the loaded store; that EXPECTED-REPORT.md is
byte-identical to a fresh render from two fresh databases; that the
packet at PACKET_DATE is pinned by byte count and sha256 (the
reference/demo treatment); that the PDF renders deterministically
at a pinned page count; that the cross-pack annotations appear in
the report and the PDF; and the fixture's machine-checked scrub.
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
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "github-org"
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "github-org-security-1.0.json"
PACK_ID = "github-org-security-1.0"
SCUBA_ID = "scuba-m365-v2.0.0"
PACKET_DATE = "2026-11-21"

# The pristine github-org packet at PACKET_DATE, pinned as the
# reference and demo packets are: byte count and sha256.
PRISTINE_PACKET_BYTES = 17262
PRISTINE_PACKET_SHA256 = (
    "7749f3eb0b76cf1e8c7d8e241e51853eca6418a36faeffa54ce88a70d64704a5"
)
PDF_PAGES = 5

EXPECTED_TALLIES = {
    "Covered": 5, "Partial": 3, "Unknown": 2, "Not applicable": 3, "Gap": 21,
}
EXPECTED_LABELS = {"VERIFIED": 17, "ON RECORD": 3, "UNKNOWN": 4}
PLAN_NA = {
    "GH-ID-03": "SAML single sign-on requires GitHub Enterprise Cloud;"
                " the organization is on the Team plan.",
    "GH-ID-04": "IP allow lists require GitHub Enterprise Cloud;"
                " the organization is on the Team plan.",
    "GH-ID-05": "Restricted email notifications require GitHub Enterprise"
                " Cloud; the organization is on the Team plan.",
}

GUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
PHONE = re.compile(r"\(?\b\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")
TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")
HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|dev|app|cloud)\b")


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
    hits += [("phone", m) for m in PHONE.findall(text)]
    hits += [("token", m) for m in TOKEN.findall(text)]
    hits += [("host", m) for m in HOST.findall(text)
             if m not in ("creativecommons.org",)]
    return hits


class GitHubOrgFixtureLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp.name) / "gh.db")
        load_fixture(bundled_fixture_dir("github-org"), cls.db_path)
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
            cls.scuba_items = {i["item_id"] for i in store.list_pack_items(SCUBA_ID)}
        finally:
            store.close()
        cls.status = {s["item_id"]: s["status"] for s in cls.scores}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bundled_by_name(self):
        self.assertIn("github-org", bundled_fixture_names())
        self.assertEqual(bundled_fixture_dir("github-org"), FIXTURE_DIR)

    def test_engagement_record(self):
        self.assertEqual(
            self.engagement["name"],
            "GitHub organization case — Alder Creek Advisory perimeter audit",
        )
        self.assertEqual(self.engagement["subject_label"],
                         "Alder Creek Advisory LLC (fictional demo firm)")
        self.assertEqual(self.engagement["created_date"], PACKET_DATE)
        self.assertEqual(self.engagement["method_order"], "verify-first")
        raw = json.loads((FIXTURE_DIR / "engagement.json").read_text(encoding="utf-8"))
        self.assertEqual(raw["pack_file"], "../../packs/github-org-security-1.0.json")
        self.assertEqual(raw["extra_pack_files"], ["../../packs/scuba-m365-v2.0.0.json"])

    def test_both_packs_loaded_primary_first(self):
        self.assertEqual(self.packs, [PACK_ID, SCUBA_ID])

    def test_every_pack_item_scored_once_under_the_primary_pack(self):
        self.assertTrue(all(s is not None for s in self.scores))
        scored = [r["item_id"] for r in self.all_scores]
        self.assertEqual(sorted(scored), sorted(self.pack_items))
        self.assertEqual({r["pack_id"] for r in self.all_scores}, {PACK_ID})

    def test_coverage_tallies_and_shape(self):
        counts = Counter(self.status.values())
        self.assertEqual({k: counts.get(k, 0) for k in EXPECTED_TALLIES},
                         EXPECTED_TALLIES)
        # The brief's shape (§5.3 with Amendments 1-2).
        self.assertEqual(self.status["GH-ID-01"], "Gap")
        self.assertEqual(self.status["GH-ID-02"], "Gap")
        self.assertLessEqual(counts["Covered"], 14)
        self.assertGreaterEqual(counts["Gap"], 8)
        self.assertGreaterEqual(counts["Unknown"], 2)

    def test_plan_not_applicable_rows(self):
        for s in self.scores:
            if s["status"] == "Not applicable":
                self.assertEqual(s["na_reason"], PLAN_NA[s["item_id"]])
                self.assertEqual(s["reasoning"], s["na_reason"])
            else:
                self.assertIsNone(s["na_reason"], s["item_id"])
        self.assertEqual(
            sorted(i for i, st in self.status.items() if st == "Not applicable"),
            sorted(PLAN_NA),
        )

    def test_every_score_cites_existing_entries(self):
        for s in self.scores:
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
        self.assertEqual(self.entries["H1"]["label"], "ON RECORD")
        self.assertIn("MS.AAD.3.6v1", self.entries["H1"]["body"])
        self.assertIn("not available on the current plan",
                      self.entries["A6"]["body"])

    def test_chain_a_is_cross_pack(self):
        a = self.chains["A"]
        self.assertEqual(a["control_rubric"], "MS.AAD.3.6v1")
        self.assertEqual(a["control_pack"], SCUBA_ID)
        self.assertIn("MS.AAD.3.6v1", self.scuba_items)
        self.assertEqual(a["control_status"], "Gap")
        steps = " ".join(s["text"] for s in a["steps"])
        for cited in ("MS.AAD.3.1v1", "GH-ID-02", "GH-TOK-01", "GH-TOK-03"):
            self.assertIn(cited, steps)

    def test_chains_b_and_c_rest_on_the_github_pack(self):
        self.assertEqual(sorted(self.chains), ["A", "B", "C"])
        for key, control in (("B", "GH-ACT-02"), ("C", "GH-MEM-03")):
            chain = self.chains[key]
            self.assertEqual(chain["control_rubric"], control)
            self.assertEqual(chain["control_pack"], PACK_ID)
            self.assertEqual(chain["control_status"], "Gap")
            self.assertEqual(self.status[control], "Gap")

    def test_fixes(self):
        self.assertEqual(list(self.fixes), [f"F-{n}" for n in range(1, 10)])
        cited = {}
        for fix in self.fixes.values():
            self.assertEqual(fix["status"], "proposed", fix["fix_id"])
            self.assertEqual(fix["status_actor"], "operator", fix["fix_id"])
            self.assertEqual(fix["status_date"], PACKET_DATE, fix["fix_id"])
            self.assertEqual(len(fix["rubric_item_ids"]), 1, fix["fix_id"])
            cited[fix["fix_id"]] = fix["rubric_item_packs"]
        self.assertEqual(cited["F-9"], {"MS.AAD.3.6v1": SCUBA_ID})
        for n in range(1, 9):
            ((item, pack),) = cited[f"F-{n}"].items()
            self.assertEqual(pack, PACK_ID)
            self.assertEqual(self.status[item], "Gap", f"F-{n}")
        self.assertIn("A", self.fixes["F-9"]["chains_broken"])

    def test_verify_next_matches_unknowns(self):
        self.assertEqual([v["seq"] for v in self.verify], [1, 2, 3, 4, 5])
        self.assertEqual(
            self.verify[0]["unknown_text"],
            "Whether the firm's exposure justifies moving to GitHub Enterprise"
            " Cloud, which SAML single sign-on and IP allow lists require.",
        )
        self.assertEqual(
            self.verify[0]["cheapest_check"],
            "The plan comparison against the two Not-applicable items"
            " (GH-ID-03, GH-ID-04), read against the firm's client commitments.",
        )
        unknown_entries = sorted(
            e for e, d in self.entries.items() if d["label"] == "UNKNOWN")
        named = sorted(
            m for v in self.verify[1:]
            for m in re.findall(r"\(([A-H]\d+)\)", v["unknown_text"]))
        self.assertEqual(named, unknown_entries)
        # Each Unknown score's open question is on the verify-next list.
        for item in (i for i, st in self.status.items() if st == "Unknown"):
            self.assertTrue(any(item in v["why"] for v in self.verify), item)


class GitHubOrgFixtureCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        # An arbitrary working directory: the fixture resolves by name.
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def _load(self, name):
        db = str(Path(self.tmp.name) / name)
        code, out, err = run_cli(["load-fixture", "github-org", db])
        self.assertEqual(code, 0, err)
        self.assertIn("github-org", out)
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

    def test_report_annotates_the_cross_pack_citations(self):
        text = render_report(self._load("annot.db"))
        self.assertIn(
            "Earliest breaking control: phishing-resistant MFA required for the"
            " highly privileged roles (in the tenant)"
            " (MS.AAD.3.6v1 (scuba-m365-v2.0.0)) Status: Gap.", text)
        self.assertRegex(
            text, r"\| F-9 \| [^|]+ \| MS\.AAD\.3\.6v1 \(scuba-m365-v2\.0\.0\) \|")
        # Citations of the rendered pack stay bare.
        self.assertIn("(GH-ACT-02) Status: Gap.", text)
        self.assertEqual(text.count("(scuba-m365-v2.0.0)"), 2)

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
        text = extract_text(pdfs[0])
        # Chain A's control line renders whole; the F-9 rubric cell
        # wraps inside the pack id, so count with whitespace removed.
        self.assertIn("(MS.AAD.3.6v1 (scuba-m365-v2.0.0)) Status: Gap.", text)
        self.assertEqual("".join(text.split()).count("(scuba-m365-v2.0.0)"), 2)


class GitHubOrgFixtureScrubTest(unittest.TestCase):
    def test_fixture_files_carry_no_identifiers(self):
        files = sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file())
        self.assertEqual(len(files), 9)
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertEqual(scrub_hits(text), [], path.name)

    def test_scrub_check_catches_what_it_forbids(self):
        planted = (
            "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0 ops@contoso.com"
            " 10.20.30.40 (212) 555-0199 ghp_" + "a" * 36 + " ci.example.com"
        )
        kinds = sorted({k for k, _ in scrub_hits(planted)})
        self.assertEqual(
            kinds, ["email", "guid", "host", "ipv4", "phone", "token"])
        allowed = ("it@aldercreek.example ci-old.aldercreek.example"
                   " MS.AAD.3.6v1 github-org-security-1.0")
        self.assertEqual(scrub_hits(allowed), [])


if __name__ == "__main__":
    unittest.main()
