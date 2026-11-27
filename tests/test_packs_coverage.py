"""Slice 2 tests: pack loading/validation, coverage scoring discipline,
coverage listing, and the pack-less report ruling."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FLASH_PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "flash-20261113-001.json"
SAMPLE_PACK_PATH = REPO_ROOT / "tests" / "fixtures" / "sample-pack.json"
FLASH_ID = "flash-20261113-001"
SAMPLE_ID = "sample-wharf-2026"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def valid_pack():
    return {
        "pack_id": "test-pack-1",
        "title": "Test Pack",
        "source_citation": "Invented test citation (2026).",
        "version": "1.0",
        "items": [
            {"item_id": "T-1.1", "group": "Group 1 — Tests",
             "text": "A first test item."},
            {"item_id": "T-1.2", "group": "Group 1 — Tests",
             "text": "A second test item."},
        ],
    }


class CliDbTestCase(unittest.TestCase):
    """Base: a fresh engagement database in a temp directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "Slice 2 test", "--subject", "Test firm",
            "--method-order", "verify-first", "--date", "2026-11-18",
        ])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def write_pack(self, pack, name="pack.json"):
        path = Path(self.tmp.name) / name
        path.write_text(json.dumps(pack), encoding="utf-8")
        return str(path)

    def load_pack(self, pack_path):
        return run_cli(["load-pack", self.db, str(pack_path)])

    def add_entry(self, entry_id, section="A", label="VERIFIED"):
        code, _, err = run_cli([
            "add-entry", self.db, "--section", section, "--id", entry_id,
            "--body", f"Body of {entry_id}.", "--label", label,
            "--source", "console read", "--checked-date", "2026-11-18",
            "--date", "2026-11-18",
        ])
        self.assertEqual(code, 0, err)

    def score(self, pack, item, status, *extra):
        return run_cli([
            "score", self.db, "--pack", pack, "--item", item,
            "--status", status, "--reasoning", f"Reasoning for {item}.",
            *extra,
        ])

    def pack_row_count(self):
        store = Store(self.db)
        try:
            return store.conn.execute(
                "SELECT COUNT(*) AS n FROM rubric_pack"
            ).fetchone()["n"]
        finally:
            store.close()

    def get_score(self, pack, item):
        store = Store(self.db)
        try:
            return store.get_coverage(pack, item)
        finally:
            store.close()


class PackValidationTest(CliDbTestCase):
    def assert_refused(self, pack):
        code, _, err = self.load_pack(self.write_pack(pack))
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(self.pack_row_count(), 0)

    def test_missing_pack_id_refused(self):
        pack = valid_pack()
        del pack["pack_id"]
        self.assert_refused(pack)

    def test_empty_title_refused(self):
        pack = valid_pack()
        pack["title"] = ""
        self.assert_refused(pack)

    def test_missing_version_refused(self):
        pack = valid_pack()
        del pack["version"]
        self.assert_refused(pack)

    def test_missing_citation_refused(self):
        pack = valid_pack()
        pack["source_citation"] = ""
        self.assert_refused(pack)

    def test_missing_items_refused(self):
        pack = valid_pack()
        del pack["items"]
        self.assert_refused(pack)

    def test_empty_items_refused(self):
        pack = valid_pack()
        pack["items"] = []
        self.assert_refused(pack)

    def test_duplicate_item_ids_refused(self):
        pack = valid_pack()
        pack["items"][1]["item_id"] = pack["items"][0]["item_id"]
        self.assert_refused(pack)

    def test_item_missing_group_refused(self):
        pack = valid_pack()
        pack["items"][0]["group"] = ""
        self.assert_refused(pack)

    def test_item_missing_text_refused(self):
        pack = valid_pack()
        del pack["items"][0]["text"]
        self.assert_refused(pack)


class LoadPackTest(CliDbTestCase):
    def test_flash_pack_loads_with_counts(self):
        code, out, err = self.load_pack(FLASH_PACK_PATH)
        self.assertEqual(code, 0, err)
        self.assertIn(FLASH_ID, out)
        self.assertIn("20 items, 4 groups", out)
        self.assertEqual(self.pack_row_count(), 1)

    def test_sample_pack_loads_with_counts(self):
        code, out, err = self.load_pack(SAMPLE_PACK_PATH)
        self.assertEqual(code, 0, err)
        self.assertIn("3 items, 2 groups", out)

    def test_duplicate_pack_refused(self):
        code, _, err = self.load_pack(FLASH_PACK_PATH)
        self.assertEqual(code, 0, err)
        code, _, err = self.load_pack(FLASH_PACK_PATH)
        self.assertEqual(code, 1)
        self.assertIn("already loaded", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(self.pack_row_count(), 1)
        store = Store(self.db)
        try:
            self.assertEqual(len(store.list_items(FLASH_ID)), 20)
        finally:
            store.close()

    def test_missing_pack_file_is_a_clean_error(self):
        code, _, err = self.load_pack(Path(self.tmp.name) / "nope.json")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)


class ScoringTest(CliDbTestCase):
    def setUp(self):
        super().setUp()
        code, _, err = self.load_pack(FLASH_PACK_PATH)
        self.assertEqual(code, 0, err)
        self.add_entry("A1")
        self.add_entry("A2", label="UNKNOWN")

    def test_one_happy_path_per_status(self):
        cases = [
            ("R-1.1", "Covered", ["--cite", "A1"]),
            ("R-1.2", "Partial", ["--cite", "A1", "--cite", "A2"]),
            ("R-2.1", "Unknown", []),
            ("R-2.6", "Not applicable",
             ["--na-reason", "No such system exists in this environment."]),
            ("R-3.1", "Gap", ["--cite", "A2"]),
        ]
        for item, status, extra in cases:
            code, _, err = self.score(FLASH_ID, item, status, *extra)
            self.assertEqual(code, 0, f"{item}: {err}")
            saved = self.get_score(FLASH_ID, item)
            self.assertEqual(saved["status"], status)
        self.assertEqual(
            self.get_score(FLASH_ID, "R-1.2")["cited_entry_ids"], ["A1", "A2"]
        )
        self.assertEqual(
            self.get_score(FLASH_ID, "R-2.6")["na_reason"],
            "No such system exists in this environment.",
        )

    def test_citationless_covered_refused(self):
        code, _, err = self.score(FLASH_ID, "R-1.3", "Covered")
        self.assertEqual(code, 1)
        self.assertIn("may only be", err)
        self.assertNotIn("Traceback", err)
        self.assertIsNone(self.get_score(FLASH_ID, "R-1.3"))

    def test_na_without_reason_refused(self):
        code, _, err = self.score(FLASH_ID, "R-3.2", "Not applicable")
        self.assertEqual(code, 1)
        self.assertIn("N/A reason", err)
        self.assertIsNone(self.get_score(FLASH_ID, "R-3.2"))

    def test_citing_nonexistent_entry_refused_cleanly(self):
        code, _, err = self.score(
            FLASH_ID, "R-1.3", "Partial", "--cite", "Z9"
        )
        self.assertEqual(code, 1)
        self.assertIn("no such entry: Z9", err)
        self.assertNotIn("Traceback", err)
        self.assertIsNone(self.get_score(FLASH_ID, "R-1.3"))

    def test_scoring_nonexistent_item_refused_cleanly(self):
        code, _, err = self.score(
            FLASH_ID, "R-9.9", "Partial", "--cite", "A1"
        )
        self.assertEqual(code, 1)
        self.assertIn("no such item", err)
        self.assertNotIn("Traceback", err)

    def test_scoring_with_nonexistent_pack_refused_cleanly(self):
        code, _, err = self.score("no-such-pack", "R-1.1", "Unknown")
        self.assertEqual(code, 1)
        self.assertIn("no such pack", err)
        self.assertNotIn("Traceback", err)


class DuplicateDisciplineTest(CliDbTestCase):
    def setUp(self):
        super().setUp()
        code, _, err = self.load_pack(SAMPLE_PACK_PATH)
        self.assertEqual(code, 0, err)
        self.add_entry("A1")
        self.add_entry("A2", label="UNKNOWN")

    def test_second_score_refused_and_original_unchanged(self):
        code, _, err = self.score(SAMPLE_ID, "W-1.1", "Covered", "--cite", "A1")
        self.assertEqual(code, 0, err)
        code, _, err = self.score(SAMPLE_ID, "W-1.1", "Partial", "--cite", "A1")
        self.assertEqual(code, 1)
        self.assertIn("already scored as Covered", err)
        self.assertIn("rescore", err)
        saved = self.get_score(SAMPLE_ID, "W-1.1")
        self.assertEqual(saved["status"], "Covered")
        self.assertEqual(saved["reasoning"], "Reasoning for W-1.1.")

    def test_rescore_replaces_status_reasoning_and_citations(self):
        code, _, err = self.score(SAMPLE_ID, "W-1.1", "Covered", "--cite", "A1")
        self.assertEqual(code, 0, err)
        code, out, err = run_cli([
            "rescore", self.db, "--pack", SAMPLE_ID, "--item", "W-1.1",
            "--status", "Partial", "--reasoning", "Revised reasoning.",
            "--cite", "A2",
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("was: Covered", out)
        self.assertIn("now: Partial", out)
        saved = self.get_score(SAMPLE_ID, "W-1.1")
        self.assertEqual(saved["status"], "Partial")
        self.assertEqual(saved["reasoning"], "Revised reasoning.")
        self.assertEqual(saved["cited_entry_ids"], ["A2"])

    def test_rescore_violating_invariant_leaves_previous_intact(self):
        code, _, err = self.score(SAMPLE_ID, "W-1.2", "Covered", "--cite", "A1")
        self.assertEqual(code, 0, err)
        code, _, err = run_cli([
            "rescore", self.db, "--pack", SAMPLE_ID, "--item", "W-1.2",
            "--status", "Covered", "--reasoning", "No citations this time.",
        ])
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", err)
        saved = self.get_score(SAMPLE_ID, "W-1.2")
        self.assertEqual(saved["status"], "Covered")
        self.assertEqual(saved["reasoning"], "Reasoning for W-1.2.")
        self.assertEqual(saved["cited_entry_ids"], ["A1"])

    def test_rescore_on_unscored_item_refused(self):
        code, _, err = run_cli([
            "rescore", self.db, "--pack", SAMPLE_ID, "--item", "W-2.1",
            "--status", "Unknown", "--reasoning", "Nothing yet.",
        ])
        self.assertEqual(code, 1)
        self.assertIn("use score", err)
        self.assertIsNone(self.get_score(SAMPLE_ID, "W-2.1"))


class ListCoverageTest(CliDbTestCase):
    def setUp(self):
        super().setUp()
        code, _, err = self.load_pack(SAMPLE_PACK_PATH)
        self.assertEqual(code, 0, err)

    def test_scored_and_unscored_stay_distinct(self):
        code, _, err = self.score(SAMPLE_ID, "W-1.1", "Unknown")
        self.assertEqual(code, 0, err)
        code, out, err = run_cli(
            ["list-coverage", self.db, "--pack", SAMPLE_ID]
        )
        self.assertEqual(code, 0, err)
        lines = {ln.split(" ")[0]: ln for ln in out.splitlines()}
        self.assertIn("Unknown", lines["W-1.1"])
        self.assertNotIn("not scored", lines["W-1.1"])
        self.assertIn("not scored", lines["W-1.2"])
        self.assertNotIn("Unknown", lines["W-1.2"])
        self.assertIn("not scored", lines["W-2.1"])
        tallies = [ln for ln in out.splitlines() if ln.startswith("Tallies:")]
        self.assertEqual(len(tallies), 1)
        self.assertIn("Unknown 1", tallies[0])
        self.assertIn("not scored 2", tallies[0])


class PacklessReportTest(CliDbTestCase):
    def test_report_without_pack_is_a_clean_error(self):
        code, out, err = run_cli(["report", self.db])
        self.assertEqual(code, 1)
        self.assertIn("no rubric pack", err)
        self.assertIn("load-pack", err)
        self.assertNotIn("Traceback", err)
        self.assertNotIn("Engagement report", out)


class EndToEndTest(CliDbTestCase):
    def test_new_load_score_list_report(self):
        code, _, err = self.load_pack(SAMPLE_PACK_PATH)
        self.assertEqual(code, 0, err)
        self.add_entry("A1")
        self.add_entry("A2", label="UNKNOWN")
        code, _, err = self.score(SAMPLE_ID, "W-1.1", "Covered", "--cite", "A1")
        self.assertEqual(code, 0, err)
        code, _, err = self.score(SAMPLE_ID, "W-2.1", "Unknown")
        self.assertEqual(code, 0, err)

        code, out, err = run_cli(
            ["list-coverage", self.db, "--pack", SAMPLE_ID]
        )
        self.assertEqual(code, 0, err)
        self.assertIn("Covered 1", out)
        self.assertIn("Unknown 1", out)
        self.assertIn("not scored 1", out)

        code, out, err = run_cli(["report", self.db])
        self.assertEqual(code, 0, err)
        self.assertIn(
            "Covered 1 · Partial 0 · Unknown 1 · Not applicable 0 · Gap 0"
            " — 2 rows",
            out,
        )
        self.assertIn("| W-1.1 |", out)
        self.assertIn("| W-2.1 |", out)


if __name__ == "__main__":
    unittest.main()
