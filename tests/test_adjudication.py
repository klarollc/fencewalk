"""Slice 5 tests: adjudication decision events (append-only, correct
requires its note), the record-entry commands (add-chain, add-fix,
set-fix-status, list-fixes, add-verify-next) with the duplicate and
citation validation the schema leaves to the CLI, the report's
Adjudication section (present only when events exist), pre-slice-5
databases, and the full v1 loop end to end."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"
SAMPLE_PACK = REPO_ROOT / "tests" / "fixtures" / "sample-pack.json"
SAMPLE_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "sample-model-output.md"
PACK_ID = "sample-wharf-2026"
DATE = "2026-11-18"
CORRECTION = (
    "Coverage corrected before applying: W-1.2 is scored from the "
    "checklist, not taken from the run."
)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def printed_value(stdout, label):
    for line in stdout.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    raise AssertionError(f"no '{label}' line in output: {stdout!r}")


class ScratchTestCase(unittest.TestCase):
    """Base: a fresh engagement with the sample pack loaded."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "Slice 5 scratch",
            "--subject", "Scratch subject", "--method-order", "model-first",
            "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        code, _, err = run_cli(["load-pack", self.db, str(SAMPLE_PACK)])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def make_run(self):
        out_path = str(Path(self.tmp.name) / "packet.md")
        code, out, err = run_cli([
            "packet", self.db, "--out", out_path, "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        self.packet_hash = printed_value(out, "sha256:")
        code, out, err = run_cli([
            "ingest", self.db, str(SAMPLE_OUTPUT),
            "--packet-hash", self.packet_hash,
            "--model", "Example Model 1", "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        return 1

    def adjudicate(self, section, decision, *extra):
        return run_cli([
            "adjudicate", self.db, "--run", "1", "--section", section,
            "--decision", decision, "--date", DATE, *extra,
        ])

    def report(self):
        code, out, err = run_cli(["report", self.db])
        self.assertEqual(code, 0, err)
        return out


class AdjudicationTest(ScratchTestCase):
    def setUp(self):
        super().setUp()
        self.make_run()

    def test_event_records_and_lists(self):
        code, out, err = self.adjudicate("coverage", "accept")
        self.assertEqual(code, 0, err)
        self.assertIn("coverage", out)
        self.assertIn("accept", out)
        code, out, err = run_cli(["adjudications", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn("coverage: accept", out)
        self.assertIn("coverage: accept", out.split("Current standings:")[1])
        for section in ("chains", "fixes", "verify-next"):
            self.assertIn(f"{section}: no decision recorded", out)

    def test_correct_without_note_refused_and_records_nothing(self):
        code, _, err = self.adjudicate("coverage", "correct")
        self.assertEqual(code, 1)
        self.assertIn("requires --note", err)
        store = Store(self.db)
        try:
            self.assertEqual(store.list_adjudications(1), [])
        finally:
            store.close()

    def test_correct_with_note_records_the_correction(self):
        code, _, err = self.adjudicate(
            "fixes", "correct", "--note", CORRECTION
        )
        self.assertEqual(code, 0, err)
        code, out, err = run_cli(["adjudications", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn("fixes: correct", out)
        self.assertIn(CORRECTION, out)

    def test_nonexistent_run_refused_cleanly(self):
        code, _, err = run_cli([
            "adjudicate", self.db, "--run", "99", "--section", "coverage",
            "--decision", "accept",
        ])
        self.assertEqual(code, 1)
        self.assertIn("no such run: 99", err)
        code, _, err = run_cli(["adjudications", self.db, "--run", "99"])
        self.assertEqual(code, 1)
        self.assertIn("no such run: 99", err)

    def test_readjudication_appends_and_standing_is_the_latest(self):
        self.assertEqual(self.adjudicate("chains", "accept")[0], 0)
        self.assertEqual(self.adjudicate("chains", "reject")[0], 0)
        code, out, err = run_cli(["adjudications", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        events_part, standings = out.split("Current standings:")
        self.assertIn("chains: accept", events_part)
        self.assertIn("chains: reject", events_part)
        self.assertIn("chains: reject", standings)
        self.assertNotIn("chains: accept", standings)
        store = Store(self.db)
        try:
            self.assertEqual(len(store.list_adjudications(1)), 2)
        finally:
            store.close()


class ChainTest(ScratchTestCase):
    def add_chain(self, *extra):
        argv = [
            "add-chain", self.db, "--key", "A",
            "--name", "a borrowed ladder reaches the office window",
            "--control", "a lock on the window latch",
            "--control-status", "unknown",
            "--step", "Reconnaissance: the ladder is stored in the open yard",
            "--step", "Initial access: the window is climbed at night",
            *extra,
        ]
        return run_cli(argv)

    def test_add_chain_lands_and_renders_in_report(self):
        code, out, err = self.add_chain("--control-rubric", "W-1.1")
        self.assertEqual(code, 0, err)
        self.assertIn("added chain A (2 steps)", out)
        report = self.report()
        self.assertIn(
            "### Chain A: a borrowed ladder reaches the office window",
            report,
        )
        self.assertIn(
            "1. **Reconnaissance.** the ladder is stored in the open yard",
            report,
        )
        self.assertIn(
            "Earliest breaking control: a lock on the window latch"
            " (W-1.1) Status: unknown.",
            report,
        )

    def test_duplicate_key_refused(self):
        self.assertEqual(self.add_chain()[0], 0)
        code, _, err = self.add_chain()
        self.assertEqual(code, 1)
        self.assertIn("duplicate chain key: A", err)

    def test_step_without_colon_refused(self):
        code, _, err = run_cli([
            "add-chain", self.db, "--key", "A", "--name", "x",
            "--control", "y", "--control-status", "unknown",
            "--step", "a step with no phase separator",
        ])
        self.assertEqual(code, 1)
        self.assertIn("step must be '<phase>: <text>'", err)

    def test_no_step_refused(self):
        code, _, err = run_cli([
            "add-chain", self.db, "--key", "A", "--name", "x",
            "--control", "y", "--control-status", "unknown",
        ])
        self.assertEqual(code, 1)
        self.assertIn("at least one --step is required", err)

    def test_unknown_control_rubric_refused(self):
        code, _, err = self.add_chain("--control-rubric", "W-9.9")
        self.assertEqual(code, 1)
        self.assertIn(f"no such item in pack {PACK_ID}: W-9.9", err)


class FixTest(ScratchTestCase):
    def add_fix(self, fix_id="F-1", *extra):
        return run_cli([
            "add-fix", self.db, "--id", fix_id,
            "--action", "Fit a lock to the office window latch",
            "--effort", "An hour", "--breaks", "A", *extra,
        ])

    def test_add_fix_lands_proposed_with_citations(self):
        code, out, err = self.add_fix("F-1", "--rubric", "W-2.1")
        self.assertEqual(code, 0, err)
        self.assertIn("added fix F-1 (proposed)", out)
        code, out, err = run_cli(["list-fixes", self.db])
        self.assertEqual(code, 0, err)
        self.assertIn("F-1 [proposed]", out)
        self.assertIn("rubric W-2.1", out)
        self.assertIn(
            "Tallies: proposed 1 · approved 0 · done 0 · deferred 0", out
        )

    def test_duplicate_id_refused(self):
        self.assertEqual(self.add_fix()[0], 0)
        code, _, err = self.add_fix()
        self.assertEqual(code, 1)
        self.assertIn("duplicate fix id: F-1", err)

    def test_unknown_rubric_item_refused(self):
        code, _, err = self.add_fix("F-1", "--rubric", "W-9.9")
        self.assertEqual(code, 1)
        self.assertIn(f"no such item in pack {PACK_ID}: W-9.9", err)

    def test_set_fix_status_moves_and_shows(self):
        self.assertEqual(self.add_fix()[0], 0)
        code, out, err = run_cli([
            "set-fix-status", self.db, "F-1", "approved",
            "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("F-1 status set to approved", out)
        code, out, err = run_cli(["list-fixes", self.db])
        self.assertEqual(code, 0, err)
        self.assertIn("F-1 [approved]", out)
        self.assertIn(
            "Tallies: proposed 0 · approved 1 · done 0 · deferred 0", out
        )
        report = self.report()
        self.assertIn(
            "Fixes: 1 (proposed 0, approved 1, done 0, deferred 0)", report
        )
        self.assertIn("| F-1 |", report)
        self.assertIn("approved", report.split("| F-1 |")[1].splitlines()[0])

    def test_same_status_refused_cleanly(self):
        self.assertEqual(self.add_fix()[0], 0)
        code, _, err = run_cli([
            "set-fix-status", self.db, "F-1", "proposed", "--date", DATE,
        ])
        self.assertEqual(code, 1)
        self.assertIn("fix F-1 is already proposed", err)

    def test_unknown_fix_refused_cleanly(self):
        code, _, err = run_cli([
            "set-fix-status", self.db, "F-99", "approved", "--date", DATE,
        ])
        self.assertEqual(code, 1)
        self.assertIn("no such fix: F-99", err)


class VerifyNextTest(ScratchTestCase):
    def test_two_adds_take_sequences_1_and_2_and_render_in_order(self):
        code, out, err = run_cli([
            "add-verify-next", self.db,
            "--unknown", "whether the yard gate is locked at night",
            "--why", "chain A stands or falls on it",
            "--check", "the harbour log's gate page",
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("added verify-next item 1", out)
        code, out, err = run_cli([
            "add-verify-next", self.db,
            "--unknown", "who holds the spare office key",
            "--why", "a second keyholder changes the access picture",
            "--check", "the key register in the office drawer",
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("added verify-next item 2", out)
        report = self.report()
        first = report.index(
            "1. **Unknown:** whether the yard gate is locked at night"
        )
        second = report.index("2. **Unknown:** who holds the spare office key")
        self.assertLess(first, second)


class ReportAdjudicationSectionTest(ScratchTestCase):
    def setUp(self):
        super().setUp()
        self.make_run()

    def test_no_section_when_no_events(self):
        self.assertNotIn("## Adjudication", self.report())

    def test_fresh_engagement_report_has_no_adjudication_heading(self):
        # A run exists but nothing was adjudicated: still no section.
        code, out, err = run_cli(["adjudications", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn("coverage: no decision recorded", out)
        self.assertNotIn("## Adjudication", self.report())

    def test_section_shows_current_decisions_and_notes(self):
        self.assertEqual(
            self.adjudicate("coverage", "correct", "--note", CORRECTION)[0], 0
        )
        self.assertEqual(self.adjudicate("chains", "accept")[0], 0)
        report = self.report()
        self.assertIn("## Adjudication", report)
        self.assertIn("### Run 1 — Example Model 1 (2026-11-18)", report)
        self.assertIn(f"- Packet hash: {self.packet_hash}", report)
        self.assertIn("- Coverage: correct (2026-11-18, operator)", report)
        self.assertIn(CORRECTION, report)
        self.assertIn("- Chains: accept (2026-11-18, operator)", report)
        self.assertIn("- Fixes: no decision recorded", report)
        self.assertIn("- Verify-next: no decision recorded", report)

    def test_superseded_event_is_not_the_standing(self):
        self.assertEqual(
            self.adjudicate(
                "coverage", "accept", "--note", "the first note"
            )[0],
            0,
        )
        self.assertEqual(
            self.adjudicate(
                "coverage", "reject", "--note", "the second note"
            )[0],
            0,
        )
        report = self.report()
        self.assertIn("- Coverage: reject", report)
        self.assertIn("the second note", report)
        self.assertNotIn("the first note", report)


class PreSlice5DatabaseTest(unittest.TestCase):
    """A database whose adjudication table was dropped (as a pre-slice-5
    database would lack it) still adjudicates and reports."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "ref.db")
        code, _, err = run_cli(["load-fixture", str(FIXTURE_DIR), self.db])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def test_adjudicate_and_report_work_after_table_dropped(self):
        out_path = str(Path(self.tmp.name) / "packet.md")
        code, out, err = run_cli([
            "packet", self.db, "--out", out_path, "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        packet_hash = printed_value(out, "sha256:")
        code, _, err = run_cli([
            "ingest", self.db, str(SAMPLE_OUTPUT),
            "--packet-hash", packet_hash, "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE adjudication")
        conn.commit()
        conn.close()
        code, _, err = run_cli([
            "adjudicate", self.db, "--run", "1", "--section", "coverage",
            "--decision", "accept", "--date", DATE,
        ])
        self.assertEqual(code, 0, err)
        code, out, err = run_cli(["report", self.db])
        self.assertEqual(code, 0, err)
        self.assertIn("## Adjudication", out)
        self.assertIn("- Coverage: accept", out)


class EndToEndTest(unittest.TestCase):
    """The full v1 loop, per the slice-5 brief §1.5: intake, pack,
    packet, ingest, draft, adjudicate, apply by hand, track one fix,
    and read the final report."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "loop.db")

    def tearDown(self):
        self.tmp.cleanup()

    def step(self, argv):
        code, out, err = run_cli(argv)
        self.assertEqual(code, 0, f"{argv[0]}: {err}")
        return out

    def test_full_v1_loop(self):
        db = self.db
        self.step([
            "new", db, "--name", "Full loop engagement",
            "--subject", "Full loop subject",
            "--method-order", "model-first", "--date", DATE,
        ])
        self.step([
            "add-entry", db, "--section", "A",
            "--body", "The office window latch is fitted and checked.",
            "--label", "VERIFIED", "--source", "site visit",
            "--checked-date", DATE, "--date", DATE,
        ])
        self.step([
            "add-entry", db, "--section", "B",
            "--body", "The harbour log is kept in the office drawer.",
            "--label", "ON RECORD", "--source", "operator records",
            "--date", DATE,
        ])
        self.step([
            "add-entry", db, "--section", "C",
            "--body", "Whether the yard gate is locked at night.",
            "--label", "UNKNOWN", "--source", "not yet checked",
            "--date", DATE,
        ])
        self.step(["load-pack", db, str(SAMPLE_PACK)])

        out_path = str(Path(self.tmp.name) / "packet.md")
        out = self.step([
            "packet", db, "--out", out_path, "--date", DATE,
        ])
        packet_hash = printed_value(out, "sha256:")
        self.step([
            "ingest", db, str(SAMPLE_OUTPUT),
            "--packet-hash", packet_hash, "--model", "Example Model 1",
            "--date", DATE,
        ])
        draft = self.step(["draft", db, "--run", "1"])
        self.assertIn("Decision: (accept / correct / reject)", draft)

        self.step([
            "adjudicate", db, "--run", "1", "--section", "coverage",
            "--decision", "correct", "--note", CORRECTION,
            "--date", DATE,
        ])
        for section in ("chains", "fixes", "verify-next"):
            self.step([
                "adjudicate", db, "--run", "1", "--section", section,
                "--decision", "accept", "--date", DATE,
            ])

        # Applying the adjudicated deliverables is explicit, by hand.
        self.step([
            "score", db, "--pack", PACK_ID, "--item", "W-1.1",
            "--status", "Covered",
            "--reasoning", "The latch is fitted and was checked on site.",
            "--cite", "A1",
        ])
        self.step([
            "score", db, "--pack", PACK_ID, "--item", "W-2.1",
            "--status", "Unknown",
            "--reasoning", "The log's completeness has never been sampled.",
        ])
        self.step([
            "add-chain", db, "--key", "A",
            "--name", "a borrowed ladder reaches the office window",
            "--control", "a lock on the window latch",
            "--control-status", "unknown", "--control-rubric", "W-1.1",
            "--step", "Reconnaissance: the ladder is stored in the open yard",
            "--step", "Initial access: the window is climbed at night",
        ])
        self.step([
            "add-fix", db, "--id", "F-1",
            "--action", "Fit a lock to the office window latch",
            "--effort", "An hour", "--breaks", "A",
            "--rubric", "W-1.1", "--date", DATE,
        ])
        self.step([
            "add-fix", db, "--id", "F-2",
            "--action", "Sample the harbour log against the gate record",
            "--effort", "A project", "--breaks", "A",
            "--rubric", "W-2.1", "--date", DATE,
        ])
        self.step([
            "add-verify-next", db,
            "--unknown", "whether the yard gate is locked at night",
            "--why", "chain A stands or falls on it",
            "--check", "the harbour log's gate page",
        ])
        self.step([
            "set-fix-status", db, "F-1", "approved", "--date", DATE,
        ])

        report = self.step(["report", db])
        # The chain, with its earliest-breaking control line.
        self.assertIn(
            "### Chain A: a borrowed ladder reaches the office window",
            report,
        )
        self.assertIn(
            "Earliest breaking control: a lock on the window latch"
            " (W-1.1) Status: unknown.",
            report,
        )
        # Both fixes, with their statuses.
        self.assertIn("| F-1 |", report)
        self.assertIn(
            "approved", report.split("| F-1 |")[1].splitlines()[0]
        )
        self.assertIn("| F-2 |", report)
        self.assertIn(
            "proposed", report.split("| F-2 |")[1].splitlines()[0]
        )
        # The verify-next item.
        self.assertIn(
            "1. **Unknown:** whether the yard gate is locked at night",
            report,
        )
        # Coverage tallies match the two scores entered.
        self.assertIn(
            "Covered 1 · Partial 0 · Unknown 1 · Not applicable 0"
            " · Gap 0 — 2 rows",
            report,
        )
        # The Adjudication section, with the correction preserved.
        self.assertIn("## Adjudication", report)
        self.assertIn("- Coverage: correct (2026-11-18, operator)", report)
        self.assertIn(CORRECTION, report)
        self.assertIn("- Chains: accept", report)
        self.assertIn("- Fixes: accept", report)
        self.assertIn("- Verify-next: accept", report)


if __name__ == "__main__":
    unittest.main()
