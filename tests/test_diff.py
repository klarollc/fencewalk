"""Drift report (`fencewalk diff`): re-audit diffing between two copies
of one engagement database.

Every pair here is built from a real bundled fixture: the fixture is
loaded, the database is copied (the "before re-audit" copy), and the
newer side is then changed only through the CLI's own commands, which
write through the Store. The report must name exactly those changes,
and neither database may change by a byte.
"""

import hashlib
import io
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.diff import render_diff
from fencewalk.fixture import load_fixture

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "src/fencewalk/fixtures"
SAMPLE_PACK = ROOT / "tests/fixtures/sample-pack.json"
REF_PACK = "flash-20261113-001"
ALL_FIXTURES = (
    "reference-case", "demo-scuba", "dns-registrar", "github-org",
    "google-workspace",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


def section(report, title):
    """The lines of one '## title' section, up to the next heading."""
    lines = report.split("\n")
    start = lines.index(f"## {title}") + 1
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def table_rows(report, title):
    """The data rows of a section's table, as tuples of cell text."""
    rows = []
    for line in section(report, title):
        if line.startswith("| ") and not line.startswith("|---"):
            rows.append(tuple(c.strip() for c in line.strip("|").split(" | ")))
    return rows[1:]  # drop the header row


class DiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def pair(self, fixture="reference-case", prepare=None):
        """Load a fixture as the newer database, optionally run prepare
        on it, then copy it as the older one. Returns (older, newer)."""
        newer = self.root / f"{fixture}.db"
        load_fixture(FIXTURES / fixture, newer)
        if prepare:
            prepare(newer)
        older = self.root / f"{fixture}-before.db"
        shutil.copyfile(newer, older)
        return older, newer

    def run_ok(self, *args):
        code, out, err = cli(*args)
        self.assertEqual(code, 0, err)
        return out

    def diff(self, older, newer, *extra):
        return self.run_ok("diff", older, newer, *extra)

    def refuse(self, *args):
        code, out, err = cli("diff", *args)
        self.assertEqual(code, 1, out)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "), err)
        self.assertNotIn("Traceback", err)
        return err

    def mutate_reference(self, newer):
        """One change of each kind, through the CLI's own commands."""
        self.run_ok("rescore", newer, "--pack", REF_PACK, "--item", "R-2.1",
                    "--status", "Partial", "--reasoning", "App inventory taken.",
                    "--cite", "A8")
        self.run_ok("set-label", newer, "A4", "VERIFIED",
                    "--date", "2026-12-01", "--actor", "operator")
        self.run_ok("set-fix-status", newer, "F-3", "approved",
                    "--date", "2026-12-02", "--actor", "operator")
        self.run_ok("add-entry", newer, "--section", "G",
                    "--body", "A second responder is named on the incident sheet.",
                    "--label", "VERIFIED", "--source", "Board minutes",
                    "--date", "2026-12-03")

    # -- the mutated pair ---------------------------------------------------

    def test_mutated_pair_names_exactly_the_changes_made(self):
        older, newer = self.pair()
        self.mutate_reference(newer)
        report = self.diff(older, newer)
        self.assertEqual(table_rows(report, "Coverage changes"),
                         [("`R-2.1`", "Unknown", "Partial")])
        self.assertIn("19 items unchanged.", section(report, "Coverage changes"))
        self.assertEqual(table_rows(report, "Inventory changes"), [
            ("`A4`", "changed", "UNKNOWN", "VERIFIED"),
            ("`G5`", "added", "—", "VERIFIED"),
        ])
        self.assertIn("51 entries unchanged.", section(report, "Inventory changes"))
        self.assertEqual(table_rows(report, "Fix changes"),
                         [("`F-3`", "changed", "proposed", "approved", "2026-12-02")])
        self.assertIn("15 fixes unchanged.", section(report, "Fix changes"))
        self.assertIn(
            "Coverage changes 1 · inventory changes 2 · fix changes 1", report
        )

    def test_header_carries_subject_paths_pack_and_both_postures(self):
        older, newer = self.pair()
        self.mutate_reference(newer)
        report = self.diff(older, newer)
        head = report.split("\n## ")[0]
        self.assertTrue(head.startswith(
            "# Drift report — Reference case — Marigold Community Food Bank"
            " perimeter audit\n"
        ))
        for line in (
            "- Subject: Marigold Community Food Bank (fictional reference firm)",
            "- Engagement: Reference case — Marigold Community Food Bank"
            " perimeter audit",
            f"- Older: `{older}`",
            f"- Newer: `{newer}`",
            f"- Compared pack: `{REF_PACK}` — ARTEX mitigations rubric",
            "- Older posture: Covered 3 · Partial 8 · Unknown 5 ·"
            " Not applicable 2 · Gap 2 — 20 rows",
            "- Newer posture: Covered 3 · Partial 9 · Unknown 4 ·"
            " Not applicable 2 · Gap 2 — 20 rows",
        ):
            self.assertIn(line + "\n", head)

    def test_reversed_pair_reads_added_as_removed(self):
        older, newer = self.pair()
        self.mutate_reference(newer)
        report = self.diff(newer, older)
        self.assertEqual(table_rows(report, "Coverage changes"),
                         [("`R-2.1`", "Partial", "Unknown")])
        self.assertEqual(table_rows(report, "Inventory changes"), [
            ("`A4`", "changed", "VERIFIED", "UNKNOWN"),
            ("`G5`", "removed", "VERIFIED", "—"),
        ])
        # The status date is always the newer side's.
        (row,) = table_rows(report, "Fix changes")
        self.assertEqual(row[:4], ("`F-3`", "changed", "approved", "proposed"))
        with closing(sqlite3.connect(older)) as conn, conn:
            (date,) = conn.execute(
                "SELECT status_date FROM fix WHERE fix_id = 'F-3'"
            ).fetchone()
        self.assertEqual(row[4], date)

    def test_item_scored_on_one_side_reads_not_scored(self):
        older, newer = self.pair(
            prepare=lambda db: self.run_ok("load-pack", db, SAMPLE_PACK)
        )
        self.run_ok("score", newer, "--pack", "sample-wharf-2026",
                    "--item", "W-1.1", "--status", "Unknown",
                    "--reasoning", "Not yet checked.")
        report = self.diff(older, newer, "--pack", "sample-wharf-2026")
        self.assertIn("- Compared pack: `sample-wharf-2026`", report)
        self.assertEqual(table_rows(report, "Coverage changes"),
                         [("`W-1.1`", "not scored", "Unknown")])
        # Items scored on neither side are neither listed nor counted.
        self.assertIn("0 items unchanged.", section(report, "Coverage changes"))
        self.assertIn("No changes.", section(report, "Inventory changes"))
        reverse = self.diff(newer, older, "--pack", "sample-wharf-2026")
        self.assertEqual(table_rows(reverse, "Coverage changes"),
                         [("`W-1.1`", "Unknown", "not scored")])

    def test_added_fix_carries_newer_status_date(self):
        older, newer = self.pair()
        self.run_ok("add-fix", newer, "--id", "F-99", "--action", "Add a second admin.",
                    "--effort", "Minutes", "--breaks", "B", "--date", "2026-12-04")
        report = self.diff(older, newer)
        self.assertEqual(table_rows(report, "Fix changes"),
                         [("`F-99`", "added", "—", "proposed", "2026-12-04")])
        self.assertIn("16 fixes unchanged.", section(report, "Fix changes"))
        self.assertIn(
            "Coverage changes 0 · inventory changes 0 · fix changes 1", report
        )

    def test_reasoning_change_without_status_change_is_unchanged(self):
        older, newer = self.pair()
        self.run_ok("rescore", newer, "--pack", REF_PACK, "--item", "R-2.1",
                    "--status", "Unknown", "--reasoning", "Reworded reasoning.",
                    "--cite", "A8")
        report = self.diff(older, newer)
        self.assertEqual(section(report, "Coverage changes")[1], "No changes.")
        self.assertIn("20 items unchanged.", section(report, "Coverage changes"))

    def test_status_round_trip_reads_unchanged(self):
        """Current state only: a fix moved and moved back is unchanged,
        although its history table grew."""
        older, newer = self.pair()
        self.run_ok("set-fix-status", newer, "F-3", "approved", "--date", "2026-12-02")
        self.run_ok("set-fix-status", newer, "F-3", "proposed", "--date", "2026-12-03")
        report = self.diff(older, newer)
        self.assertEqual(section(report, "Fix changes")[1], "No changes.")

    # -- identical pairs and determinism -----------------------------------

    def assert_no_changes(self, report):
        for title in ("Coverage changes", "Inventory changes", "Fix changes"):
            self.assertEqual(section(report, title)[1], "No changes.", title)
            self.assertEqual(table_rows(report, title), [], title)
        self.assertIn(
            "Coverage changes 0 · inventory changes 0 · fix changes 0", report
        )

    def test_identical_pair_reads_no_changes_for_every_fixture(self):
        for fixture in ALL_FIXTURES:
            with self.subTest(fixture=fixture):
                older, newer = self.pair(fixture)
                self.assert_no_changes(self.diff(older, newer))

    def test_same_file_twice_reads_no_changes(self):
        _older, newer = self.pair()
        self.assert_no_changes(self.diff(newer, newer))

    def test_repeated_runs_are_byte_identical(self):
        older, newer = self.pair()
        self.mutate_reference(newer)
        first = self.diff(older, newer)
        self.assertEqual(self.diff(older, newer), first)
        self.assertEqual(render_diff(older, newer), first)

    def test_out_writes_the_same_report_to_a_file(self):
        older, newer = self.pair()
        self.mutate_reference(newer)
        out = self.root / "drift.md"
        printed = self.diff(older, newer, "--out", out)
        self.assertEqual(printed, f"drift report written to {out}\n")
        self.assertEqual(out.read_text(encoding="utf-8"), self.diff(older, newer))

    # -- immutability --------------------------------------------------------

    def assert_diff_leaves_bytes(self, older, newer, *extra):
        before = (digest(older), digest(newer))
        self.diff(older, newer, *extra)
        self.assertEqual((digest(older), digest(newer)), before)

    def test_diff_never_changes_either_database(self):
        older, newer = self.pair()
        self.mutate_reference(newer)
        self.assert_diff_leaves_bytes(older, newer)
        self.assert_diff_leaves_bytes(newer, older)

    def test_pre_slice_1_database_on_either_side_stays_byte_identical(self):
        """A database whose engagement table predates primary_pack is
        read without migration, as older or newer side."""
        def drop_primary_column(db):
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute("ALTER TABLE engagement DROP COLUMN primary_pack")

        older, newer = self.pair(prepare=drop_primary_column)
        self.mutate_reference(older)  # the first write migrates this one
        with closing(sqlite3.connect(newer)) as conn, conn:
            columns = [r[1] for r in conn.execute("PRAGMA table_info(engagement)")]
        self.assertNotIn("primary_pack", columns)
        self.assert_diff_leaves_bytes(older, newer)
        self.assert_diff_leaves_bytes(newer, older)
        report = self.diff(older, newer)
        self.assertIn(f"- Compared pack: `{REF_PACK}`", report)
        self.assertEqual(table_rows(report, "Coverage changes"),
                         [("`R-2.1`", "Partial", "Unknown")])

    def test_refusals_leave_both_databases_unchanged(self):
        older, _ = self.pair()
        other, _ = self.pair("dns-registrar")
        before = (digest(older), digest(other))
        self.refuse(older, other)
        self.refuse(older, older, "--pack", "no-such-pack")
        self.assertEqual((digest(older), digest(other)), before)

    # -- refusals ------------------------------------------------------------

    def test_different_engagements_are_refused(self):
        older, _ = self.pair()
        other, _ = self.pair("dns-registrar")
        err = self.refuse(older, other)
        self.assertIn("different engagements", err)
        self.assertIn("subject_label", err)

    def test_same_subject_different_created_date_is_refused(self):
        older, newer = self.pair()
        with closing(sqlite3.connect(newer)) as conn, conn:
            conn.execute("UPDATE engagement SET created_date = '2027-01-01'")
        err = self.refuse(older, newer)
        self.assertIn("created_date", err)

    def test_pack_missing_from_older_is_refused(self):
        older, newer = self.pair()
        self.run_ok("load-pack", newer, SAMPLE_PACK)
        err = self.refuse(older, newer, "--pack", "sample-wharf-2026")
        self.assertIn("sample-wharf-2026 is not loaded in", err)
        self.assertIn(str(older), err)

    def test_default_pack_missing_from_older_is_refused(self):
        older, newer = self.pair()
        self.run_ok("load-pack", newer, SAMPLE_PACK)
        self.run_ok("set-primary-pack", newer, "sample-wharf-2026")
        err = self.refuse(older, newer)
        self.assertIn("sample-wharf-2026 is not loaded in", err)

    def test_pack_missing_from_newer_is_refused(self):
        older, newer = self.pair()
        err = self.refuse(older, newer, "--pack", "no-such-pack")
        self.assertIn(f"no-such-pack is not loaded in {newer}", err)

    def test_missing_database_is_refused_and_not_created(self):
        older, _ = self.pair()
        ghost = self.root / "ghost.db"
        self.assertIn("no such database", self.refuse(older, ghost))
        self.assertIn("no such database", self.refuse(ghost, older))
        self.assertFalse(ghost.exists())

    def test_database_with_two_engagement_rows_is_refused(self):
        older, newer = self.pair()
        with closing(sqlite3.connect(newer)) as conn, conn:
            conn.execute(
                "INSERT INTO engagement (name, subject_label, created_date, method_order)"
                " SELECT name, subject_label, created_date, method_order FROM engagement"
            )
        err = self.refuse(older, newer)
        self.assertIn("2 engagement rows; diff needs exactly one", err)

    def test_out_onto_either_database_is_refused(self):
        older, newer = self.pair()
        before = (digest(older), digest(newer))
        for target in (older, newer):
            err = self.refuse(older, newer, "--out", target)
            self.assertIn("--out must not be the database path", err)
        self.assertEqual((digest(older), digest(newer)), before)


if __name__ == "__main__":
    unittest.main()
