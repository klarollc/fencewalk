"""Demo-scuba fixture tests: the ScubaGear v2.0.0 sample run as a second
bundled fixture (the fictional Tidewater Advisory engagement).

Coverage is one score per SCuBA pack item, derived from the sample
ScubaResults.csv (see the fixture README). These tests load the fixture
by name and assert its shape from the loaded store and the pack: every
pack item scored once at the golden tallies, one proposed fix per Gap,
one verify-next item per product carrying Partial rows, chains whose
control rubric is a pack item. They also assert the fixture's
machine-checked scrub (no GUID, no e-mail address outside the
fictional .example domain, no IPv4 address, no phone number but the
fictional one, in any file of the fixture directory, comments
included), that EXPECTED-REPORT.md is byte-identical to a fresh
render, and that the packet and PDF are deterministic across two
fresh databases.
"""

import hashlib
import io
import json
import re
import tempfile
import unittest
from collections import Counter, defaultdict
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import bundled_fixture_dir, bundled_fixture_names, load_fixture
from fencewalk.report import render_report
from fencewalk.report_pdf import render_pdf
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "demo-scuba"
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "scuba-m365-v2.0.0.json"
PACK_ID = "scuba-m365-v2.0.0"
PACKET_DATE = "2026-10-15"

# The pristine demo packet, pinned the same way tests/test_model_api.py
# pins the reference packet: byte count and sha256 at PACKET_DATE.
PRISTINE_PACKET_BYTES = 30166
PRISTINE_PACKET_SHA256 = (
    "270dbc5243d4a459edb9c367be082af099762efbf5877adeacd734f53b2cda3d"
)

# Golden numbers: the ScubaGear v2.0.0 sample ScubaResults.csv, counted
# from the pinned tag (Pass/Fail/Warning/N/A per product). The loaded
# fixture must reproduce them; the tests compute every count from the
# store.
EXPECTED_TALLIES = {
    "Covered": 72, "Gap": 15, "Partial": 14, "Not applicable": 8, "Unknown": 0,
}
EXPECTED_PRODUCT_TALLIES = {
    "AAD": {"Covered": 14, "Gap": 12, "Partial": 5, "Not applicable": 3},
    "EXO": {"Covered": 11, "Partial": 1},
    "POWERBI": {"Covered": 5, "Partial": 3},
    "POWERPLATFORM": {"Covered": 5, "Gap": 1, "Partial": 1, "Not applicable": 2},
    "SECURITYSUITE": {"Covered": 17, "Partial": 4, "Not applicable": 3},
    "SHAREPOINT": {"Covered": 6, "Gap": 2},
    "TEAMS": {"Covered": 14},
}

GUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
PHONE = re.compile(r"\(?\b\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")
ALLOWED_PHONE = "(555) 010-0177"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def product(item_id):
    return item_id.split(".")[1]


def scrub_hits(text):
    """Every identifier-shaped string in text that the scrub forbids."""
    hits = []
    hits += [("guid", m) for m in GUID.findall(text)]
    hits += [("email", m) for m in EMAIL.findall(text)
             if not m.lower().endswith(".example")]
    hits += [("ipv4", m) for m in IPV4.findall(text)]
    hits += [("phone", m) for m in PHONE.findall(text)
             if m.lstrip("(") != ALLOWED_PHONE.lstrip("(")]
    if "onmicrosoft" in text.lower():
        hits.append(("tenant-domain", "onmicrosoft"))
    return hits


class DemoFixtureLoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp.name) / "demo.db")
        load_fixture(bundled_fixture_dir("demo-scuba"), cls.db_path)
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)
        cls.pack_items = [i["item_id"] for i in cls.pack["items"]]
        store = Store(cls.db_path)
        try:
            cls.engagement = store.get_engagement()
            cls.scores = [store.get_coverage(PACK_ID, i) for i in cls.pack_items]
            cls.all_scores = store.conn.execute(
                "SELECT pack_id, item_id, status FROM coverage_score"
            ).fetchall()
            cls.fixes = store.list_fixes()
            cls.chains = store.list_chains()
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
        self.assertIn("demo-scuba", bundled_fixture_names())
        self.assertIn("reference-case", bundled_fixture_names())
        self.assertEqual(bundled_fixture_dir("demo-scuba"), FIXTURE_DIR)

    def test_engagement_record(self):
        self.assertEqual(self.engagement["name"],
                         "Demo case — Tidewater Advisory perimeter audit")
        self.assertEqual(self.engagement["subject_label"],
                         "Tidewater Advisory LLC (fictional demo firm)")
        self.assertEqual(self.engagement["created_date"], PACKET_DATE)
        self.assertEqual(self.engagement["method_order"], "verify-first")

    def test_every_pack_item_scored_exactly_once(self):
        self.assertTrue(all(s is not None for s in self.scores))
        scored = [r["item_id"] for r in self.all_scores]
        self.assertEqual(len(scored), len(set(scored)))
        self.assertEqual(sorted(scored), sorted(self.pack_items))
        self.assertEqual({r["pack_id"] for r in self.all_scores}, {PACK_ID})
        self.assertEqual(len(scored), len(self.pack["items"]))

    def test_coverage_tallies(self):
        counts = Counter(self.status.values())
        self.assertEqual(
            {k: counts.get(k, 0) for k in EXPECTED_TALLIES}, EXPECTED_TALLIES
        )
        self.assertEqual(sum(counts.values()), len(self.pack_items))

    def test_per_product_tallies(self):
        by_product = defaultdict(Counter)
        for item, status in self.status.items():
            by_product[product(item)][status] += 1
        self.assertEqual(
            {p: dict(c) for p, c in by_product.items()}, EXPECTED_PRODUCT_TALLIES
        )

    def test_reasoning_free_of_html_and_identifiers(self):
        for s in self.scores:
            for field in ("reasoning", "na_reason"):
                text = s[field] or ""
                self.assertNotRegex(text, r"<[^>]+>", s["item_id"])
                self.assertNotRegex(text, r"&[a-z]+;|&#\d+;", s["item_id"])
                self.assertEqual(text, " ".join(text.split()), s["item_id"])
                self.assertEqual(scrub_hits(text), [], s["item_id"])
            self.assertTrue(s["reasoning"].strip(), s["item_id"])

    def test_na_reason_only_on_na_rows(self):
        for s in self.scores:
            if s["status"] == "Not applicable":
                self.assertEqual(s["na_reason"], s["reasoning"], s["item_id"])
            else:
                self.assertIsNone(s["na_reason"], s["item_id"])

    def test_every_score_cites_existing_entries(self):
        for s in self.scores:
            self.assertTrue(s["cited_entry_ids"], s["item_id"])
            for eid in s["cited_entry_ids"]:
                self.assertIn(eid, self.entries, s["item_id"])

    def test_inventory_labels_and_dates(self):
        self.assertTrue(self.entries)
        for e in self.entries.values():
            self.assertIn(e["section"], "ABCDEFGH")
            self.assertTrue(e["entry_id"].startswith(e["section"]))
            self.assertTrue(e["source"].strip())
            if e["label"] == "VERIFIED":
                self.assertEqual(e["checked_date"], PACKET_DATE, e["entry_id"])
            else:
                self.assertIsNone(e["checked_date"], e["entry_id"])

    def test_one_proposed_fix_per_gap(self):
        gaps = [i for i in self.pack_items if self.status[i] == "Gap"]
        self.assertEqual(len(self.fixes), len(gaps))
        self.assertEqual(
            [f["fix_id"] for f in self.fixes],
            [f"F-{n}" for n in range(1, len(gaps) + 1)],
        )
        cited = []
        for fix in self.fixes:
            self.assertEqual(fix["status"], "proposed", fix["fix_id"])
            self.assertEqual(len(fix["rubric_item_ids"]), 1, fix["fix_id"])
            item = fix["rubric_item_ids"][0]
            self.assertEqual(self.status[item], "Gap", fix["fix_id"])
            self.assertEqual(fix["rubric_item_packs"], {item: PACK_ID})
            cited.append(item)
        self.assertEqual(cited, gaps)

    def test_one_verify_next_item_per_warning_product(self):
        partial = defaultdict(list)
        for item in self.pack_items:
            if self.status[item] == "Partial":
                partial[product(item)].append(item)
        self.assertEqual(len(self.verify), len(partial))
        named_products = []
        for item in self.verify:
            ids = re.findall(r"MS\.[A-Z]+\.\d+\.\d+v\d+", item["unknown_text"])
            self.assertTrue(ids, item["seq"])
            prods = {product(i) for i in ids}
            self.assertEqual(len(prods), 1, item["seq"])
            prod = prods.pop()
            self.assertEqual(sorted(set(ids)), sorted(partial[prod]), item["seq"])
            for field in ("why", "cheapest_check"):
                self.assertTrue(item[field].strip())
            named_products.append(prod)
        self.assertEqual(sorted(named_products), sorted(partial))

    def test_chains_rest_on_pack_items(self):
        self.assertGreaterEqual(len(self.chains), 2)
        fix_chains = set()
        for fix in self.fixes:
            fix_chains.update(c.strip() for c in fix["chains_broken"].split(","))
        for chain in self.chains:
            self.assertIn(chain["control_rubric"], self.pack_items, chain["chain_key"])
            self.assertEqual(chain["control_pack"], PACK_ID, chain["chain_key"])
            self.assertIn(chain["chain_key"], fix_chains)
            self.assertTrue(chain["steps"])


class DemoFixtureCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _load(self, name):
        db = str(Path(self.tmp.name) / name)
        code, out, err = run_cli(["load-fixture", "demo-scuba", db])
        self.assertEqual(code, 0, err)
        self.assertIn("demo-scuba", out)
        return db

    def test_load_fixture_by_name_through_cli(self):
        db = self._load("cli.db")
        store = Store(db)
        try:
            self.assertEqual(
                store.get_engagement()["subject_label"],
                "Tidewater Advisory LLC (fictional demo firm)",
            )
        finally:
            store.close()

    def test_expected_report_is_byte_identical_to_a_fresh_render(self):
        db = self._load("report.db")
        expected = (FIXTURE_DIR / "EXPECTED-REPORT.md").read_bytes()
        self.assertEqual(render_report(db).encode("utf-8"), expected)
        out = Path(self.tmp.name) / "report.md"
        code, _, err = run_cli(["report", db, "--out", str(out)])
        self.assertEqual(code, 0, err)
        self.assertEqual(out.read_bytes(), expected)

    def test_packet_and_pdf_deterministic_across_fresh_databases(self):
        packets, pdfs = [], []
        for n in (1, 2):
            db = self._load(f"det{n}.db")
            out = Path(self.tmp.name) / f"packet{n}.md"
            code, _, err = run_cli(
                ["packet", db, "--date", PACKET_DATE, "--out", str(out)]
            )
            self.assertEqual(code, 0, err)
            packets.append(out.read_bytes())
            pdfs.append(render_pdf(db))
        self.assertEqual(packets[0], packets[1])
        self.assertEqual(hashlib.sha256(packets[0]).hexdigest(),
                         hashlib.sha256(packets[1]).hexdigest())
        self.assertEqual(len(packets[0]), PRISTINE_PACKET_BYTES)
        self.assertEqual(hashlib.sha256(packets[0]).hexdigest(),
                         PRISTINE_PACKET_SHA256)
        self.assertEqual(pdfs[0], pdfs[1])
        self.assertTrue(pdfs[0].startswith(b"%PDF-"))


class DemoFixtureScrubTest(unittest.TestCase):
    def test_fixture_files_carry_no_identifiers(self):
        files = sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file())
        self.assertEqual(len(files), 9)
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertEqual(scrub_hits(text), [], path.name)

    def test_scrub_check_catches_what_it_forbids(self):
        planted = (
            "<!-- tenant 0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0 -->"
            " ops@contoso.com 10.20.30.40 (212) 555-0199 x.onmicrosoft.com"
        )
        kinds = sorted(k for k, _ in scrub_hits(planted))
        self.assertEqual(
            kinds, ["email", "guid", "ipv4", "phone", "tenant-domain"]
        )
        allowed = "admin@tidewateradvisory.example (555) 010-0177 v2.0.0"
        self.assertEqual(scrub_hits(allowed), [])


if __name__ == "__main__":
    unittest.main()
