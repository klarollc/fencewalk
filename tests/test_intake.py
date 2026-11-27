"""Slice 1 intake tests: entry detail edits and the intake CLI."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import load_pack, validate_pack
from fencewalk.report import render_report
from fencewalk.store import InvariantError, Store

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "flash-20261113-001.json"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class UpdateEntryDetailsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "eng.db")
        self.store.init_schema()
        self.eng = self.store.create_engagement(
            "Test engagement", "Test subject", "2026-11-18", "verify-first"
        )
        self.store.add_inventory_entry(
            self.eng, "A1", "A", "Original body.", "VERIFIED", "first source",
            "2026-11-10", "2027-01-01", date="2026-11-18", actor="test",
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _entry(self):
        return self.store.list_inventory()[0]

    def _history(self):
        rows = self.store.conn.execute(
            "SELECT label, date, actor FROM entry_label_history ORDER BY id"
        ).fetchall()
        return [(r["label"], r["date"], r["actor"]) for r in rows]

    def test_update_changes_body_source_and_dates(self):
        self.store.update_entry_details(
            "A1", body="Corrected body.", source="second source",
            checked_date="2026-11-12", decay_date="2027-02-01",
        )
        e = self._entry()
        self.assertEqual(e["body"], "Corrected body.")
        self.assertEqual(e["source"], "second source")
        self.assertEqual(e["checked_date"], "2026-11-12")
        self.assertEqual(e["decay_date"], "2027-02-01")

    def test_update_leaves_unset_dates_alone(self):
        self.store.update_entry_details("A1", body="Corrected body.")
        e = self._entry()
        self.assertEqual(e["checked_date"], "2026-11-10")
        self.assertEqual(e["decay_date"], "2027-01-01")

    def test_update_clears_dates_with_none(self):
        self.store.update_entry_details(
            "A1", checked_date=None, decay_date=None
        )
        e = self._entry()
        self.assertIsNone(e["checked_date"])
        self.assertIsNone(e["decay_date"])

    def test_update_never_touches_label_or_history(self):
        before = self._history()
        self.store.update_entry_details(
            "A1", body="Corrected body.", source="second source",
            checked_date=None, decay_date="2027-03-01",
        )
        self.assertEqual(self._entry()["label"], "VERIFIED")
        self.assertEqual(self._history(), before)

    def test_update_unknown_entry_is_a_clean_error(self):
        with self.assertRaises(InvariantError):
            self.store.update_entry_details("Z9", body="Nope.")


class IntakeCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")

    def tearDown(self):
        self.tmp.cleanup()

    def _new(self):
        return run_cli([
            "new", self.db, "--name", "Intake test", "--subject", "Test firm",
            "--method-order", "verify-first", "--date", "2026-11-18",
        ])

    def test_end_to_end(self):
        code, _, _ = self._new()
        self.assertEqual(code, 0)
        # The renderer reads a rubric pack from the store; seed the FLASH
        # pack through the store API (pack loading is slice 0 machinery —
        # there is deliberately no pack CLI in slice 1).
        store = Store(self.db)
        store.add_pack(validate_pack(load_pack(PACK_PATH)))
        store.close()

        code, out, _ = run_cli([
            "add-entry", self.db, "--section", "A", "--id", "A1",
            "--body", "First entry.", "--label", "VERIFIED",
            "--source", "console read", "--checked-date", "2026-11-18",
            "--date", "2026-11-18",
        ])
        self.assertEqual(code, 0)
        self.assertIn("added A1", out)

        code, out, _ = run_cli([
            "add-entry", self.db, "--section", "A",
            "--body", "Second entry.", "--label", "UNKNOWN",
            "--source", "not on record", "--date", "2026-11-18",
        ])
        self.assertEqual(code, 0)
        self.assertIn("added A2", out)  # auto-assigned ID

        code, out, _ = run_cli(["list-entries", self.db])
        self.assertEqual(code, 0)
        self.assertIn("A1", out)
        self.assertIn("A2", out)

        code, _, _ = run_cli([
            "set-label", self.db, "A2", "ON RECORD",
            "--date", "2026-11-19", "--actor", "operator",
        ])
        self.assertEqual(code, 0)
        store = Store(self.db)
        history = store.conn.execute(
            "SELECT label, date, actor FROM entry_label_history"
            " WHERE entry_id = 'A2' ORDER BY id"
        ).fetchall()
        self.assertEqual(
            [(h["label"], h["date"], h["actor"]) for h in history],
            [("UNKNOWN", "2026-11-18", "operator"),
             ("ON RECORD", "2026-11-19", "operator")],
        )

        code, _, _ = run_cli([
            "edit-entry", self.db, "A1", "--body", "First entry, corrected.",
        ])
        self.assertEqual(code, 0)
        entries = {e["entry_id"]: e for e in store.list_inventory()}
        store.close()
        self.assertEqual(entries["A1"]["body"], "First entry, corrected.")
        self.assertEqual(entries["A1"]["label"], "VERIFIED")

        report = render_report(self.db)
        self.assertIn(
            "- Inventory: 2 entries (VERIFIED 1, ON RECORD 1, UNKNOWN 0)",
            report,
        )

    def test_new_refuses_existing_file(self):
        code, _, _ = self._new()
        self.assertEqual(code, 0)
        code, _, err = self._new()
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)

    def test_duplicate_entry_id_is_a_clean_error(self):
        code, _, _ = self._new()
        self.assertEqual(code, 0)
        argv = [
            "add-entry", self.db, "--section", "B", "--id", "B1",
            "--body", "An entry.", "--label", "UNKNOWN",
            "--source", "not on record", "--date", "2026-11-18",
        ]
        code, _, _ = run_cli(argv)
        self.assertEqual(code, 0)
        code, _, err = run_cli(argv)
        self.assertEqual(code, 1)
        self.assertIn("duplicate entry id", err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
