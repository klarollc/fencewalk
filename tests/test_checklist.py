"""Slice 3 tests: the verification checklist as a derived view — fixture
golden unknowns, the set-label resolution loop, decay rules, determinism,
and the empty case."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"

GOLDEN_UNKNOWN_IDS = [
    "A4", "A8", "B4", "C4", "D2", "E3", "E5", "E8", "F3", "G4",
    "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8",
]

AS_OF = "2026-11-18"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def section_lines(text, header):
    """The lines of one '## <header>' section of the checklist."""
    lines = text.splitlines()
    start = lines.index(f"## {header}") + 1
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def check_ids(text, header):
    """Entry IDs of the checkbox lines in one section, in order."""
    ids = []
    for line in section_lines(text, header):
        if line.startswith("- [ ] **"):
            ids.append(line.split("**")[1])
    return ids


def counts_line(text):
    for line in text.splitlines():
        if line.startswith("- Checks:"):
            return line
    raise AssertionError("no counts line in checklist output")


class FixtureDbTestCase(unittest.TestCase):
    """Base: the reference fixture loaded into a temp database."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "ref.db")
        code, _, err = run_cli(["load-fixture", str(FIXTURE_DIR), self.db])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def checklist(self, as_of=AS_OF):
        code, out, err = run_cli(["checklist", self.db, "--date", as_of])
        self.assertEqual(code, 0, err)
        return out


class FixtureGoldenTest(FixtureDbTestCase):
    def test_golden_unknown_ids_in_order(self):
        text = self.checklist()
        self.assertEqual(check_ids(text, "Unknown entries"), GOLDEN_UNKNOWN_IDS)

    def test_counts_line(self):
        text = self.checklist()
        self.assertEqual(
            counts_line(text),
            "- Checks: 18 unknown · 0 decayed evidence · 18 total",
        )

    def test_no_decayed_section_entries(self):
        text = self.checklist()
        self.assertEqual(check_ids(text, "Decayed evidence"), [])
        self.assertIn("None.", section_lines(text, "Decayed evidence"))

    def test_settled_entry_never_appears(self):
        # G1 is a settled entry (the board-approved incident sheet,
        # VERIFIED Nov 5); it is not unknown and carries no decay date,
        # so no section may list it.
        text = self.checklist()
        self.assertNotIn("**G1**", text)

    def test_golden_holds_at_any_as_of_date(self):
        text = self.checklist(as_of="2030-01-01")
        self.assertEqual(check_ids(text, "Unknown entries"), GOLDEN_UNKNOWN_IDS)
        self.assertEqual(
            counts_line(text),
            "- Checks: 18 unknown · 0 decayed evidence · 18 total",
        )


class ResolutionLoopTest(FixtureDbTestCase):
    def test_set_label_resolution_leaves_the_next_checklist(self):
        code, _, err = run_cli([
            "set-label", self.db, "A4", "VERIFIED",
            "--date", "2026-11-05", "--actor", "tester",
        ])
        self.assertEqual(code, 0, err)
        text = self.checklist()
        ids = check_ids(text, "Unknown entries")
        self.assertNotIn("A4", ids)
        self.assertEqual(len(ids), 17)
        self.assertEqual(
            counts_line(text),
            "- Checks: 17 unknown · 0 decayed evidence · 17 total",
        )


class DeterminismTest(FixtureDbTestCase):
    def test_two_renders_are_byte_identical(self):
        self.assertEqual(self.checklist(), self.checklist())

    def test_out_file_matches_stdout(self):
        out_path = str(Path(self.tmp.name) / "checklist.md")
        code, out, err = run_cli(
            ["checklist", self.db, "--date", AS_OF, "--out", out_path]
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(out, f"checklist written to {out_path}\n")
        written = Path(out_path).read_text(encoding="utf-8")
        self.assertEqual(written, self.checklist())


class ScratchDbTestCase(unittest.TestCase):
    """Base: a fresh empty engagement in a temp directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "Checklist test",
            "--subject", "Test firm", "--method-order", "verify-first",
            "--date", "2026-11-18",
        ])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, entry_id, section, label, body="Body text.",
            checked=None, decay=None):
        argv = [
            "add-entry", self.db, "--section", section, "--id", entry_id,
            "--body", body, "--label", label, "--source", "test source",
            "--date", "2026-11-18", "--actor", "tester",
        ]
        if checked is not None:
            argv += ["--checked-date", checked]
        if decay is not None:
            argv += ["--decay-date", decay]
        code, _, err = run_cli(argv)
        self.assertEqual(code, 0, err)

    def checklist(self, as_of=AS_OF):
        code, out, err = run_cli(["checklist", self.db, "--date", as_of])
        self.assertEqual(code, 0, err)
        return out


class DecayRulesTest(ScratchDbTestCase):
    def setUp(self):
        super().setUp()
        self.add("A1", "A", "VERIFIED", checked="2026-10-15", decay="2026-11-01")
        self.add("A2", "A", "VERIFIED", checked="2026-11-18", decay="2026-11-18")
        self.add("A3", "A", "VERIFIED", checked="2026-11-18", decay="2026-12-01")
        self.add("A4", "A", "ON RECORD", checked="2026-09-30", decay="2026-11-01")
        self.add("A5", "A", "UNKNOWN", decay="2026-11-01")
        self.add("A6", "A", "VERIFIED", checked="2026-11-18")
        self.text = self.checklist()

    def test_decayed_verified_before_as_of_is_listed(self):
        self.assertIn("A1", check_ids(self.text, "Decayed evidence"))

    def test_decay_on_as_of_date_is_listed(self):
        self.assertIn("A2", check_ids(self.text, "Decayed evidence"))

    def test_decay_after_as_of_is_not_listed(self):
        self.assertNotIn("**A3**", self.text)

    def test_decayed_on_record_is_listed(self):
        self.assertIn("A4", check_ids(self.text, "Decayed evidence"))

    def test_unknown_with_past_decay_appears_only_as_unknown(self):
        self.assertIn("A5", check_ids(self.text, "Unknown entries"))
        self.assertNotIn("A5", check_ids(self.text, "Decayed evidence"))

    def test_verified_without_decay_date_is_never_listed(self):
        self.assertNotIn("**A6**", self.text)

    def test_decayed_section_contents_and_counts(self):
        self.assertEqual(
            check_ids(self.text, "Decayed evidence"), ["A1", "A2", "A4"]
        )
        self.assertEqual(
            counts_line(self.text),
            "- Checks: 1 unknown · 3 decayed evidence · 4 total",
        )

    def test_decayed_line_shows_checked_and_decay_dates(self):
        lines = [
            ln for ln in section_lines(self.text, "Decayed evidence")
            if ln.startswith("- [ ] **A1**")
        ]
        self.assertEqual(len(lines), 1)
        self.assertIn("VERIFIED", lines[0])
        self.assertIn("checked 2026-10-15", lines[0])
        self.assertIn("decay 2026-11-01", lines[0])

    def test_decayed_line_without_checked_date_says_not_recorded(self):
        self.add("B1", "B", "ON RECORD", decay="2026-11-01")
        text = self.checklist()
        lines = [
            ln for ln in section_lines(text, "Decayed evidence")
            if ln.startswith("- [ ] **B1**")
        ]
        self.assertEqual(len(lines), 1)
        self.assertIn("checked not recorded", lines[0])


class EmptyCaseTest(ScratchDbTestCase):
    def test_no_unknowns_no_decay_renders_none_sections(self):
        self.add("A1", "A", "VERIFIED", checked="2026-11-18")
        text = self.checklist()
        self.assertIn("None.", section_lines(text, "Unknown entries"))
        self.assertIn("None.", section_lines(text, "Decayed evidence"))
        self.assertEqual(
            counts_line(text),
            "- Checks: 0 unknown · 0 decayed evidence · 0 total",
        )


if __name__ == "__main__":
    unittest.main()
