"""Deeper Slice 2 tests: the calibration report.

`fencewalk calibration` compares each coverage-adjudicated run's
proposed statuses (read through the draft's section machinery) with
today's standing scores, and tallies agree / model optimistic / model
pessimistic / n/a-involved / standing unscored by group, posture, run
and overall. It is read-only: the database's bytes never change.

The hand-built engagement below is the reference-case fixture with
real runs recorded through the CLI. Expected tallies are hand-counted
from the fixture's standing statuses (R-1.1 Partial, R-1.2 Gap,
R-1.3 Partial, R-1.4 Not applicable, R-1.5 Gap, R-2.1 Unknown, R-2.3
Unknown, R-2.6 Not applicable, R-3.2 Partial, R-3.3 Covered, R-4.3
Covered)."""

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.calibration import bucket, read_proposals

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "src" / "fencewalk" / "fixtures"
PACKS = REPO_ROOT / "src" / "fencewalk" / "packs"
FLASH_IDS = {
    i["item_id"] for i in json.loads(
        (PACKS / "flash-20261113-001.json").read_text(encoding="utf-8")
    )["items"]
}

# Run 1, standard posture, Status in the third column. Hand count:
# agree R-1.1, R-1.4, R-2.6 (R-1.4 and R-2.6 with two N/A sides);
# optimistic R-1.5 (Partial over Gap); pessimistic R-2.1 (Gap under
# Unknown), R-3.3 (Partial under Covered); n/a-involved R-3.2, R-4.3.
# Not readable: R-4.1 (no exact status cell), R-4.2 (two status cells).
STANDARD_OUTPUT = """Synthetic standard run output.

## 1. Coverage map

| Rubric ID | Entries | Status | Reasoning |
|---|---|---|---|
| R-1.1 | C1, E1 | Partial | The main services are known; the NAS and camera were not listed. |
| R-1.4 | — | **Not applicable** | No deployed application of its own. |
| R-1.5 | E2 | Partial | The forward was a one-off. |
| R-2.1 | A8 | Gap | No grant inventory exists at all. |
| R-2.6 | — | Not applicable | No CA or on-premises directory. |
| R-3.2 | D5 | Not applicable | There is no client portal. |
| R-3.3 | C8 | Partial | The probe is one point in time. |
| R-4.3 | — | Not applicable | No incident has been confirmed. |
| R-4.1 | F4 | Partial or Gap | Retention is unchecked. |
| R-4.2 | A9 | Unknown | Gap |

## 2. Attack chains

1. Reconnaissance: public pages name the providers.
"""

# Run 2, adversarial posture, the amended four-column table. Hand
# count: agree R-3.3 (holds); optimistic R-1.2 (Partial over Gap);
# pessimistic R-1.3 (Gap under Partial), R-2.3 (Gap under Unknown).
ADVERSARIAL_OUTPUT = """Synthetic adversarial run output.

## Coverage challenges

| ID | Proposed status | Holds/Challenged | Reasoning |
|---|---|---|---|
| R-1.2 | Partial | Challenged | E4 shows a password stands in front of the NAS page. |
| R-1.3 | Gap | Challenged | Overclaiming reasoning: C2 and C3 leave every publishing path shared. |
| R-2.3 | Gap | Challenged | A9 says nothing was written down, and nothing was asked. |
| R-3.3 | Covered | Holds | C8 is VERIFIED and covers the error-page probe. |

Most material: R-1.3.
"""

# Run 3, standard posture: adjudicated for chains only, so excluded.
UNADJUDICATED_OUTPUT = """## Coverage map

| Item | Status | Reasoning |
|---|---|---|
| R-1.1 | Gap | Excluded run. |
"""

REPORT_HEAD = (
    "# Calibration report — Reference case — Marigold Community Food"
    " Bank perimeter audit\n"
    "\n"
    "- Subject: Marigold Community Food Bank (fictional reference firm)\n"
    "- Engagement: Reference case — Marigold Community Food Bank"
    " perimeter audit\n"
    "- Compared pack: `flash-20261113-001` — ARTEX mitigations rubric\n"
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def table_row(report, first_cell):
    """The cells of the report table row whose first cell is first_cell."""
    for line in report.splitlines():
        if line.startswith(f"| {first_cell} |"):
            return [c.strip() for c in line.strip().strip("|").split("|")][1:]
    raise AssertionError(f"no row {first_cell!r} in report")


class _Engagement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = str(self.dir / "ref.db")
        self.ok(["load-fixture", str(FIXTURES / "reference-case"), self.db])

    def tearDown(self):
        self.tmp.cleanup()

    def ok(self, argv):
        code, stdout, err = run_cli(argv)
        self.assertEqual(code, 0, err)
        return stdout

    def record_run(self, output, posture="standard", name="run",
                   pack=None, date="2026-11-25", model="synthetic/model"):
        argv = ["packet", self.db, "--date", "2026-11-22", "--posture",
                posture, "--out", str(self.dir / f"{name}-packet.md")]
        if pack:
            argv += ["--pack", pack]
        packet_hash = printed_value(self.ok(argv), "sha256:")
        out_file = self.dir / f"{name}-output.md"
        out_file.write_text(output, encoding="utf-8")
        stdout = self.ok(["ingest", self.db, str(out_file), "--packet-hash",
                          packet_hash, "--model", model, "--date", date])
        return int(printed_value(stdout, "ingested model run"))

    def adjudicate(self, run_id, section="coverage", decision="accept"):
        self.ok(["adjudicate", self.db, "--run", str(run_id), "--section",
                 section, "--decision", decision, "--date", "2026-11-25"])

    def calibration(self, *extra):
        return self.ok(["calibration", self.db, *extra])


class HandBuiltRunsTests(_Engagement):
    def setUp(self):
        super().setUp()
        self.run1 = self.record_run(STANDARD_OUTPUT, name="std",
                                    model="synthetic/standard")
        self.adjudicate(self.run1)
        self.run2 = self.record_run(ADVERSARIAL_OUTPUT, posture="adversarial",
                                    name="adv", model="synthetic/adversarial")
        self.adjudicate(self.run2, decision="reject")
        self.run3 = self.record_run(UNADJUDICATED_OUTPUT, name="unadj")
        self.adjudicate(self.run3, section="chains")

    def test_header_counts_population_and_exclusions(self):
        report = self.calibration()
        self.assertTrue(report.startswith(REPORT_HEAD))
        self.assertIn("- Runs qualifying: 2\n", report)
        self.assertIn("- 1 runs not adjudicated for coverage — excluded\n",
                      report)
        self.assertIn("- 2 rows not readable — excluded\n", report)

    def test_tallies_match_the_hand_count(self):
        report = self.calibration()
        # Compared, agree, optimistic, pessimistic, n/a, unscored, share.
        self.assertEqual(
            table_row(report, "Group 1 — Reduce external attack surface"),
            ["5", "2", "2", "1", "0", "0", "40.0%"])
        self.assertEqual(
            table_row(report, "Group 2 — Harden identity and access"),
            ["3", "1", "0", "2", "0", "0", "33.3%"])
        self.assertEqual(
            table_row(report, "Group 3 — Strengthen application protections"),
            ["3", "1", "0", "1", "1", "0", "33.3%"])
        self.assertEqual(
            table_row(report, "Group 4 — Preserve evidence and respond"),
            ["1", "0", "0", "0", "1", "0", "0.0%"])
        self.assertEqual(table_row(report, "standard"),
                         ["8", "3", "1", "2", "2", "0", "37.5%"])
        self.assertEqual(table_row(report, "adversarial"),
                         ["4", "1", "1", "2", "0", "0", "25.0%"])
        overall = report[report.index("## Overall"):]
        self.assertIn("| 12 | 4 | 2 | 4 | 2 | 0 | 33.3% |", overall)

    def test_by_run_rows(self):
        report = self.calibration()
        self.assertEqual(
            table_row(report, str(self.run1)),
            ["synthetic/standard", "2026-11-25", "standard", "8", "37.5%"])
        self.assertEqual(
            table_row(report, str(self.run2)),
            ["synthetic/adversarial", "2026-11-25", "adversarial", "4",
             "25.0%"])
        by_run = report[report.index("## By run"):report.index("## Overall")]
        self.assertNotIn(f"| {self.run3} |", by_run)

    def test_hand_rescore_moves_one_item_from_agree_to_optimistic(self):
        before = self.calibration()
        self.ok(["rescore", self.db, "--pack", "flash-20261113-001",
                 "--item", "R-1.1", "--status", "Gap",
                 "--reasoning", "Hand rescore after adjudication.",
                 "--cite", "A4"])
        after = self.calibration()
        group = "Group 1 — Reduce external attack surface"
        self.assertEqual(table_row(before, group),
                         ["5", "2", "2", "1", "0", "0", "40.0%"])
        self.assertEqual(table_row(after, group),
                         ["5", "1", "3", "1", "0", "0", "20.0%"])
        self.assertEqual(table_row(after, "standard"),
                         ["8", "2", "2", "2", "2", "0", "25.0%"])
        self.assertEqual(table_row(after, "adversarial"),
                         ["4", "1", "1", "2", "0", "0", "25.0%"])

    def test_reading_this_states_the_limitation(self):
        report = self.calibration()
        self.assertIn("## Reading this", report)
        self.assertIn(
            "Standing scores are as of today. A score changed since"
            " adjudication for any reason counts exactly as an overturn"
            " does, and agreement is measured against the record, not"
            " against the adjudicator's intent.", report)

    def test_render_is_read_only_and_deterministic(self):
        before = sha(self.db)
        first = self.calibration()
        second = self.calibration()
        out = self.dir / "calibration.md"
        self.ok(["calibration", self.db, "--out", str(out)])
        self.assertEqual(sha(self.db), before)
        self.assertEqual(first, second)
        self.assertEqual(out.read_text(encoding="utf-8"), first)

    def test_section_order(self):
        report = self.calibration()
        positions = [report.index(h) for h in (
            "## By group", "## By posture", "## By run", "## Overall",
            "## Reading this")]
        self.assertEqual(positions, sorted(positions))


class PopulationTests(_Engagement):
    def test_no_runs_renders_the_plain_message(self):
        before = sha(self.db)
        report = self.calibration()
        self.assertTrue(report.startswith(REPORT_HEAD))
        self.assertIn("- Runs qualifying: 0\n", report)
        self.assertIn(
            "No run qualifies for calibration: no model run recorded"
            " against a `flash-20261113-001` packet has an adjudication"
            " event in the coverage section.", report)
        self.assertNotIn("## By group", report)
        self.assertEqual(sha(self.db), before)

    def test_unadjudicated_runs_are_excluded_and_counted(self):
        run = self.record_run(STANDARD_OUTPUT)
        self.adjudicate(run, section="fixes")
        report = self.calibration()
        self.assertIn("- Runs qualifying: 0\n", report)
        self.assertIn("- 1 runs not adjudicated for coverage — excluded\n",
                      report)
        self.assertIn("No run qualifies for calibration", report)

    def test_runs_for_another_pack_are_not_in_the_population(self):
        pack_file = PACKS / "ncsc-cyber-essentials-3.3.json"
        self.ok(["load-pack", self.db, str(pack_file)])
        run = self.record_run(STANDARD_OUTPUT, pack="ncsc-cyber-essentials-3.3")
        self.adjudicate(run)
        report = self.calibration()
        self.assertIn("- Runs qualifying: 0\n", report)
        self.assertIn("- 0 runs not adjudicated for coverage — excluded\n",
                      report)

    def test_standing_unscored_is_counted_not_directed(self):
        pack_file = PACKS / "ncsc-cyber-essentials-3.3.json"
        pack = json.loads(pack_file.read_text(encoding="utf-8"))
        first, second = (i["item_id"] for i in pack["items"][:2])
        group = pack["items"][0]["group"]
        self.ok(["load-pack", self.db, str(pack_file)])
        self.ok(["score", self.db, "--pack", pack["pack_id"], "--item", first,
                 "--status", "Partial", "--reasoning", "On record only.",
                 "--cite", "E2"])
        output = ("## Coverage map\n\n| Item | Status |\n|---|---|\n"
                  f"| {first} | Partial |\n| {second} | Covered |\n")
        run = self.record_run(output, pack=pack["pack_id"])
        self.adjudicate(run)
        report = self.calibration("--pack", pack["pack_id"])
        self.assertIn("- Runs qualifying: 1\n", report)
        overall = report[report.index("## Overall"):]
        self.assertIn("| 2 | 1 | 0 | 0 | 0 | 1 | 50.0% |", overall)
        # Both items sit in the pack's first group (Firewalls).
        self.assertEqual(pack["items"][1]["group"], group)
        self.assertEqual(table_row(report, group),
                         ["2", "1", "0", "0", "0", "1", "50.0%"])

    def test_unknown_pack_is_refused(self):
        code, _, err = run_cli(["calibration", self.db, "--pack", "no-such"])
        self.assertEqual(code, 1)
        self.assertIn("pack no-such is not loaded", err)

    def test_out_onto_the_database_is_refused(self):
        before = sha(self.db)
        code, _, err = run_cli(["calibration", self.db, "--out", self.db])
        self.assertEqual(code, 1)
        self.assertEqual(sha(self.db), before)


class OlderDatabaseTests(_Engagement):
    def test_pre_slice1_database_is_unchanged_and_reads_standard(self):
        run = self.record_run(STANDARD_OUTPUT)
        self.adjudicate(run)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("ALTER TABLE packet_record DROP COLUMN posture")
            conn.commit()
        before = sha(self.db)
        report = self.calibration()
        self.assertEqual(sha(self.db), before)
        self.assertEqual(table_row(report, "standard"),
                         ["8", "3", "1", "2", "2", "0", "37.5%"])
        with closing(sqlite3.connect(self.db)) as conn:
            cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(packet_record)")]
        self.assertNotIn("posture", cols)

    def test_no_model_pass_tables_renders_no_qualifying_runs(self):
        # Amendment 1, addition 2: the read-only open raises rather than
        # creating the tables; calibration catches it, exit 0, bytes
        # unchanged.
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE adjudication")
            conn.execute("DROP TABLE model_run")
            conn.execute("DROP TABLE packet_record")
            conn.commit()
        before = sha(self.db)
        code, report, err = run_cli(["calibration", self.db])
        self.assertEqual(code, 0, err)
        self.assertIn("- Runs qualifying: 0\n", report)
        self.assertIn("No run qualifies for calibration", report)
        self.assertEqual(sha(self.db), before)
        with closing(sqlite3.connect(self.db)) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertNotIn("model_run", tables)

    def test_model_runs_without_the_adjudication_table(self):
        run = self.record_run(STANDARD_OUTPUT)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE adjudication")
            conn.commit()
        before = sha(self.db)
        report = self.calibration()
        self.assertEqual(sha(self.db), before)
        self.assertIn("- Runs qualifying: 0\n", report)
        self.assertIn("- 1 runs not adjudicated for coverage — excluded\n",
                      report)
        self.assertTrue(run)


class ExtractionTests(unittest.TestCase):
    """The row rule, through draft.split_sections: one item-ID cell and
    one status cell, in any column order; anything else is counted."""

    def test_both_shipped_samples_read_whatever_the_column_order(self):
        docs = (REPO_ROOT / "docs" / "sample-model-output.md").read_text(
            encoding="utf-8")
        tests = (REPO_ROOT / "tests" / "fixtures"
                 / "sample-model-output.md").read_text(encoding="utf-8")
        self.assertEqual(read_proposals(docs, FLASH_IDS), ({
            "R-1.1": "Partial", "R-2.1": "Unknown",
            "R-3.2": "Not applicable"}, 0))
        self.assertEqual(read_proposals(tests, FLASH_IDS), ({
            "R-1.2": "Gap", "R-2.6": "Not applicable",
            "R-3.3": "Covered", "R-4.1": "Unknown"}, 0))

    def test_adversarial_table_reads_the_proposal(self):
        proposals, unreadable = read_proposals(ADVERSARIAL_OUTPUT, FLASH_IDS)
        self.assertEqual(proposals, {"R-1.2": "Partial", "R-1.3": "Gap",
                                     "R-2.3": "Gap", "R-3.3": "Covered"})
        self.assertEqual(unreadable, 0)

    def test_unreadable_rows_are_counted_never_guessed(self):
        output = (
            "## Coverage map\n\n| ID | Status | Note |\n|---|---|---|\n"
            "| R-1.1 | Partial | ok |\n"
            "| R-1.2 | partial | lower case is not a status |\n"
            "| R-1.3 | Covered | Gap |\n"
            "| R-1.5 | R-1.6 | Partial |\n"
            "| R-2.1 | Unknown | first of two |\n"
            "| R-2.1 | Gap | second of two |\n"
            "| Z-9 | Covered | not a pack item |\n"
        )
        proposals, unreadable = read_proposals(output, FLASH_IDS)
        self.assertEqual(proposals, {"R-1.1": "Partial"})
        self.assertEqual(unreadable, 5)

    def test_rows_outside_the_coverage_section_are_not_read(self):
        output = (
            "| R-1.1 | Covered |\n\n"
            "## Fix list\n\n| R-1.1 | Gap |\n"
        )
        self.assertEqual(read_proposals(output, FLASH_IDS), ({}, 0))

    def test_buckets(self):
        self.assertEqual(bucket("Partial", "Partial"), "agree")
        self.assertEqual(bucket("Covered", "Partial"), "model optimistic")
        self.assertEqual(bucket("Unknown", "Gap"), "model optimistic")
        self.assertEqual(bucket("Gap", "Unknown"), "model pessimistic")
        self.assertEqual(bucket("Not applicable", "Not applicable"), "agree")
        self.assertEqual(bucket("Not applicable", "Gap"), "n/a-involved")
        self.assertEqual(bucket("Covered", "Not applicable"), "n/a-involved")
        self.assertEqual(bucket("Covered", None), "standing unscored")


if __name__ == "__main__":
    unittest.main()
