"""Acceptance test: the reference fixture reproduces the golden record.

The expected values below are the golden record (the adjudicated reference
case). The renderer and store must compute their numbers from the fixture;
this test asserts the computed numbers equal the golden record exactly.
"""

import tempfile
import unittest
from pathlib import Path

from fencewalk.fixture import load_fixture
from fencewalk.report import render_report
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"
PACK_ID = "flash-20261113-001"

EXPECTED_TALLIES = {
    "Covered": 3,
    "Partial": 8,
    "Unknown": 5,
    "Not applicable": 2,
    "Gap": 2,
}
EXPECTED_COVERED = {"R-3.1", "R-3.3", "R-4.3"}
EXPECTED_NA = {"R-1.4", "R-2.6"}
EXPECTED_GAP = {"R-1.2", "R-1.5"}
EXPECTED_CHAINS = 3
EXPECTED_FIXES = 16
EXPECTED_VERIFY_NEXT = 10


class AcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.tmp.name) / "reference.db"
        load_fixture(FIXTURE_DIR, cls.db_path)
        cls.store = Store(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        cls.tmp.cleanup()

    def test_coverage_tallies_match_golden_record(self):
        tallies = self.store.coverage_tallies(PACK_ID)
        computed = {s: tallies.get(s, 0) for s in EXPECTED_TALLIES}
        self.assertEqual(computed, EXPECTED_TALLIES)
        self.assertEqual(sum(tallies.values()), 20)

    def test_covered_and_na_rows_are_the_golden_ones(self):
        coverage = self.store.list_coverage(PACK_ID)
        covered = {r["item_id"] for r in coverage if r["status"] == "Covered"}
        na = {r["item_id"] for r in coverage if r["status"] == "Not applicable"}
        gap = {r["item_id"] for r in coverage if r["status"] == "Gap"}
        self.assertEqual(covered, EXPECTED_COVERED)
        self.assertEqual(na, EXPECTED_NA)
        self.assertEqual(gap, EXPECTED_GAP)
        for row in coverage:
            if row["status"] == "Not applicable":
                self.assertEqual(row["cited_entry_ids"], [])
                self.assertTrue(row["na_reason"].strip())
            elif row["status"] != "Unknown":
                self.assertTrue(row["cited_entry_ids"], row["item_id"])

    def test_chains_fixes_verify_next_counts(self):
        self.assertEqual(len(self.store.list_chains()), EXPECTED_CHAINS)
        self.assertEqual(len(self.store.list_fixes()), EXPECTED_FIXES)
        self.assertEqual(len(self.store.list_verify_next()), EXPECTED_VERIFY_NEXT)

    def test_fix_record_shape(self):
        fixes = self.store.list_fixes()
        self.assertEqual(
            [f["fix_id"] for f in fixes], [f"F-{n}" for n in range(1, 17)]
        )
        by_id = {f["fix_id"]: f for f in fixes}
        # F-4 and F-8 carry no rubric citation in the golden record;
        # every other fix cites at least one item.
        unmapped = {i for i, f in by_id.items() if not f["rubric_item_ids"]}
        self.assertEqual(unmapped, {"F-4", "F-8"})
        # F-1 is done, F-2 approved, F-16 deferred; the rest are proposed.
        special = {"F-1": "done", "F-2": "approved", "F-16": "deferred"}
        for fix_id, fix in by_id.items():
            self.assertEqual(fix["status"], special.get(fix_id, "proposed"), fix_id)
        statuses = {
            c["chain_key"]: (c["control_rubric"], c["control_status"])
            for c in self.store.list_chains()
        }
        self.assertEqual(statuses, {
            "A": ("R-1.2", "Gap"), "B": ("R-1.3", "Partial"), "C": (None, "Gap"),
        })
        for chain in self.store.list_chains():
            self.assertEqual(len(chain["steps"]), 4)

    def test_rendered_report_carries_the_computed_numbers(self):
        report = render_report(self.db_path)
        self.assertIn(
            "Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows",
            report,
        )
        self.assertIn("- Attack chains: 3", report)
        self.assertIn("- Fixes: 16 (proposed 13, approved 1, done 1, deferred 1)", report)
        self.assertIn("- Verify-next items: 10", report)
        for fix_id in (f"F-{n}" for n in range(1, 17)):
            self.assertIn(f"| {fix_id} |", report)


if __name__ == "__main__":
    unittest.main()
