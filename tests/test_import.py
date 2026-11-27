"""Slice 1 import tests: the bundle-Markdown import rules, exactly."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.intake import import_inventory
from fencewalk.store import InvariantError, Store

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-inventory.md"
MULTILABEL_LINE = 13  # the security-defaults bullet in the sample fixture


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "eng.db")
        self.store.init_schema()
        self.eng = self.store.create_engagement(
            "Import test", "Sample firm", "2026-11-18", "verify-first"
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _import(self):
        return import_inventory(
            self.store, self.eng, FIXTURE, date="2026-11-18", actor="test"
        )

    def test_report_counts_exact(self):
        report = self._import()
        self.assertEqual(report["file_name"], "sample-inventory.md")
        self.assertEqual(report["per_section"], {"A": 6, "B": 2, "H": 2})
        self.assertEqual(
            report["label_tallies"],
            {"VERIFIED": 4, "ON RECORD": 2, "UNKNOWN": 4},
        )
        self.assertEqual(report["unlabeled"], 3)
        self.assertEqual(report["verified_date_not_parsed"], 1)
        self.assertEqual(report["preamble_lines"], 2)
        self.assertEqual(report["total_imported"], 10)
        self.assertEqual(
            report["skipped_multi_label"],
            [{"section": "A", "line_no": MULTILABEL_LINE,
              "markers": ["ON RECORD", "VERIFIED", "UNKNOWN"]}],
        )

    def test_imported_entries_exact(self):
        self._import()
        entries = {e["entry_id"]: e for e in self.store.list_inventory()}
        self.assertEqual(
            sorted(entries),
            ["A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2", "H1", "H2"],
        )
        self.assertEqual(entries["A1"]["label"], "VERIFIED")
        self.assertEqual(entries["A1"]["checked_date"], "2026-11-04")
        self.assertEqual(entries["A2"]["label"], "ON RECORD")
        self.assertEqual(entries["A3"]["label"], "UNKNOWN")
        self.assertEqual(entries["A4"]["label"], "VERIFIED")
        self.assertEqual(entries["A4"]["checked_date"], "2026-11-04")
        self.assertEqual(entries["A5"]["label"], "VERIFIED")
        self.assertIsNone(entries["A5"]["checked_date"])
        self.assertEqual(entries["B1"]["label"], "VERIFIED")
        self.assertEqual(entries["B1"]["checked_date"], "2026-11-03")
        self.assertEqual(entries["B2"]["label"], "ON RECORD")
        # Unlabeled entries import as UNKNOWN with the stated source.
        for entry_id in ("A6", "H1", "H2"):
            self.assertEqual(entries[entry_id]["label"], "UNKNOWN")
            self.assertEqual(
                entries[entry_id]["source"],
                "imported from sample-inventory.md; label not stated in source",
            )
        self.assertEqual(
            entries["A1"]["source"], "imported from sample-inventory.md"
        )
        # Bold markers are stripped from stored bodies.
        self.assertNotIn("**", entries["A3"]["body"])
        # The skipped multi-label bullet is nowhere in the store.
        self.assertFalse(
            any("Security defaults" in e["body"] for e in entries.values())
        )

    def test_import_into_nonempty_inventory_refused(self):
        self._import()
        with self.assertRaises(InvariantError):
            self._import()

    def test_import_cli_refusal_is_clean(self):
        db = str(Path(self.tmp.name) / "cli.db")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([
                "new", db, "--name", "T", "--subject", "S",
                "--method-order", "verify-first", "--date", "2026-11-18",
            ])
        self.assertEqual(code, 0)
        with redirect_stdout(out), redirect_stderr(err):
            code = main([
                "import-inventory", db, str(FIXTURE), "--date", "2026-11-18",
            ])
        self.assertEqual(code, 0)
        self.assertIn("Total imported: 10", out.getvalue())
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([
                "import-inventory", db, str(FIXTURE), "--date", "2026-11-18",
            ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
