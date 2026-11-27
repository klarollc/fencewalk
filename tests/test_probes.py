"""Deeper Slice 3 tests: behavioral verification probes (mechanism).

`record-probe` appends one probe (item, method, outcome confirmed /
failed / inconclusive, date, actor) to probe_result, created lazily on
the write path; refusals write nothing. `probes` lists each probed
item's latest probe, and `--unprobed` the Covered/Partial items with no
probe on record. Both listings are read-only and never create the table.
Probes never change scores.

The reference-case fixture's Covered/Partial items: Covered R-3.1,
R-3.3, R-4.3; Partial R-1.1, R-1.3, R-1.6, R-2.2, R-2.5, R-3.2, R-3.4,
R-4.1 (11 in all)."""

import hashlib
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.store import InvariantError, Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "src" / "fencewalk" / "fixtures"
PACKS = REPO_ROOT / "src" / "fencewalk" / "packs"
PACK = "flash-20261113-001"

DOCUMENTARY = [
    "R-1.1", "R-1.3", "R-1.6", "R-2.2", "R-2.5", "R-3.1",
    "R-3.2", "R-3.3", "R-3.4", "R-4.1", "R-4.3",
]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tables(db):
    with closing(sqlite3.connect(db)) as conn:
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}


def item_lines(listing):
    """The item lines of a listing (not the pack line, method lines or
    the closing tally)."""
    return [
        line for line in listing.splitlines()
        if line.startswith("R-")
    ]


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

    def probe(self, item, outcome, date="2026-11-25", method=None,
              actor="operator", pack=PACK):
        return self.ok([
            "record-probe", self.db, "--pack", pack, "--item", item,
            "--method", method or f"Exercised {item}.", "--outcome", outcome,
            "--date", date, "--actor", actor,
        ])

    def listing(self, *extra):
        return self.ok(["probes", self.db, *extra])


class WorkflowTests(_Engagement):
    def test_each_outcome_records_and_the_list_shows_latest_per_item(self):
        out = self.probe("R-3.3", "confirmed",
                         method="Ran the scanner against the live site.")
        self.assertEqual(out, "recorded probe 1 (R-3.3, confirmed);"
                              " scores are unchanged\n")
        self.probe("R-1.4", "failed", date="2026-11-24",
                   method="Edited a page in place on the host.")
        self.probe("R-2.1", "inconclusive", actor="second admin",
                   method="Asked for the grant list; none came back.")
        listing = self.listing()
        self.assertEqual(listing, (
            "Pack: flash-20261113-001 (ARTEX mitigations rubric)\n"
            "R-1.4 (Group 1 — Reduce external attack surface) failed"
            " — 2026-11-24 · operator · 1 probe on record\n"
            "  method: Edited a page in place on the host.\n"
            "R-2.1 (Group 2 — Harden identity and access) inconclusive"
            " — 2026-11-25 · second admin · 1 probe on record\n"
            "  method: Asked for the grant list; none came back.\n"
            "R-3.3 (Group 3 — Strengthen application protections) confirmed"
            " — 2026-11-25 · operator · 1 probe on record\n"
            "  method: Ran the scanner against the live site.\n"
            "Latest outcomes: confirmed 1 · failed 1 · inconclusive 1"
            " · probes on record 3\n"
        ))

    def test_latest_is_by_date_then_record_order(self):
        self.probe("R-1.4", "failed", date="2026-11-20", method="first")
        self.probe("R-1.4", "confirmed", date="2026-11-25", method="third")
        # Recorded last but dated earlier: not the latest.
        self.probe("R-1.4", "inconclusive", date="2026-11-22", method="second")
        listing = self.listing()
        self.assertEqual(item_lines(listing), [
            "R-1.4 (Group 1 — Reduce external attack surface) confirmed"
            " — 2026-11-25 · operator · 3 probes on record",
        ])
        self.assertIn("  method: third\n", listing)
        # Same date: record order decides.
        self.probe("R-1.4", "failed", date="2026-11-25", method="fourth")
        listing = self.listing()
        self.assertIn(" failed — 2026-11-25 · operator · 4 probes", listing)
        self.assertIn("  method: fourth\n", listing)

    def test_list_is_ordered_by_item(self):
        for item in ("R-4.3", "R-1.1", "R-2.4", "R-1.6"):
            self.probe(item, "confirmed")
        self.assertEqual(
            [line.split(" ")[0] for line in item_lines(self.listing())],
            ["R-1.1", "R-1.6", "R-2.4", "R-4.3"],
        )

    def test_unprobed_lists_exactly_the_documentary_claims_and_shrinks(self):
        listing = self.listing("--unprobed")
        self.assertEqual(
            [line.split(" ")[0] for line in item_lines(listing)], DOCUMENTARY)
        self.assertIn(
            "R-3.1 (Group 3 — Strengthen application protections) Covered"
            " — no probe on record\n", listing)
        self.assertTrue(listing.endswith(
            "Unprobed: 11 of 11 Covered or Partial items\n"))
        # A failed probe is still a probe on record.
        self.probe("R-3.1", "failed")
        self.probe("R-4.1", "inconclusive")
        listing = self.listing("--unprobed")
        remaining = [i for i in DOCUMENTARY if i not in ("R-3.1", "R-4.1")]
        self.assertEqual(
            [line.split(" ")[0] for line in item_lines(listing)], remaining)
        self.assertTrue(listing.endswith(
            "Unprobed: 9 of 11 Covered or Partial items\n"))
        # Probing a Gap/Unknown/N-A item does not touch the list.
        self.probe("R-2.1", "confirmed")
        self.assertEqual(self.listing("--unprobed"), listing)

    def test_unprobed_when_every_claim_is_probed(self):
        for item in DOCUMENTARY:
            self.probe(item, "confirmed")
        self.assertEqual(self.listing("--unprobed"), (
            "Pack: flash-20261113-001 (ARTEX mitigations rubric)\n"
            "Every Covered or Partial item has a probe on record.\n"
            "Unprobed: 0 of 11 Covered or Partial items\n"
        ))

    def test_no_probes_renders_the_plain_line(self):
        self.assertEqual(self.listing(), (
            "Pack: flash-20261113-001 (ARTEX mitigations rubric)\n"
            "No probes recorded.\n"
        ))

    def test_pack_option_scopes_the_listing(self):
        self.ok(["load-pack", self.db,
                 str(PACKS / "ncsc-cyber-essentials-3.3.json")])
        self.probe("NCSC-CE-FW-01", "failed", pack="ncsc-cyber-essentials-3.3")
        self.probe("R-1.4", "confirmed")
        default = self.listing()
        self.assertIn("R-1.4 ", default)
        self.assertNotIn("NCSC-CE-FW-01", default)
        ncsc = self.listing("--pack", "ncsc-cyber-essentials-3.3")
        self.assertIn("NCSC-CE-FW-01 (Firewalls) failed", ncsc)
        self.assertNotIn("R-1.4", ncsc)
        self.assertIn("Unprobed: 0 of 0", self.listing(
            "--pack", "ncsc-cyber-essentials-3.3", "--unprobed"))

    def test_listings_are_read_only(self):
        self.probe("R-1.4", "confirmed")
        before = sha(self.db)
        self.listing()
        self.listing("--unprobed")
        self.assertEqual(sha(self.db), before)


class ProbesChangeNoScoreTests(_Engagement):
    def test_a_failed_probe_moves_no_score_and_no_other_record(self):
        report = self.dir / "before.md"
        self.ok(["report", self.db, "--out", str(report)])
        coverage = self.ok(["list-coverage", self.db, "--pack", PACK])
        with closing(sqlite3.connect(self.db)) as conn:
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("coverage_score", "coverage_citation",
                                "adjudication", "model_run", "fix",
                                "fix_status_history", "entry_label_history",
                                "chain", "verify_next")}
        self.probe("R-1.4", "failed",
                   method="Edited a page in place on the host; it stuck.")
        after = self.dir / "after.md"
        self.ok(["report", self.db, "--out", str(after)])
        self.assertEqual(after.read_bytes(), report.read_bytes())
        self.assertEqual(
            self.ok(["list-coverage", self.db, "--pack", PACK]), coverage)
        with closing(sqlite3.connect(self.db)) as conn:
            for table, n in counts.items():
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    n, table)


class RefusalTests(_Engagement):
    def refused(self, argv, message):
        before = sha(self.db)
        code, _, err = run_cli(argv)
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertEqual(sha(self.db), before)

    def argv(self, pack=PACK, item="R-1.4", method="Did the thing.",
             outcome="confirmed"):
        return ["record-probe", self.db, "--pack", pack, "--item", item,
                "--method", method, "--outcome", outcome,
                "--date", "2026-11-25"]

    def test_unknown_pack_writes_nothing(self):
        self.refused(self.argv(pack="no-such-pack"), "no such pack: no-such-pack")

    def test_item_outside_the_pack_writes_nothing(self):
        self.refused(self.argv(item="R-9.9"),
                     "no such item in pack flash-20261113-001: R-9.9")
        # An item that exists, but in a different pack.
        self.ok(["load-pack", self.db,
                 str(PACKS / "ncsc-cyber-essentials-3.3.json")])
        self.refused(self.argv(item="NCSC-CE-FW-01"),
                     "no such item in pack flash-20261113-001: NCSC-CE-FW-01")

    def test_blank_method_writes_nothing(self):
        self.refused(self.argv(method="   "), "a probe needs a method")

    def test_outcome_outside_the_set_is_a_cli_choice_error(self):
        before = sha(self.db)
        with self.assertRaises(SystemExit):
            run_cli(self.argv(outcome="passed"))
        self.assertEqual(sha(self.db), before)

    def test_store_refuses_before_any_write(self):
        before = sha(self.db)
        with closing(Store(self.db)) as store:
            eng = store.get_engagement()["id"]
            for args in (
                (PACK, "R-1.4", "m", "passed"),
                ("no-such", "R-1.4", "m", "confirmed"),
                (PACK, "R-9.9", "m", "confirmed"),
                (PACK, "R-1.4", "", "confirmed"),
            ):
                with self.assertRaises(InvariantError):
                    store.record_probe(eng, *args, "2026-11-25", "operator")
        self.assertEqual(sha(self.db), before)

    def test_schema_check_holds_the_outcome_set(self):
        with closing(sqlite3.connect(self.db)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO probe_result (engagement_id, pack_id,"
                    " item_id, method, outcome, date, actor)"
                    " VALUES (1, ?, 'R-1.4', 'm', 'passed', 'd', 'a')",
                    (PACK,),
                )


class MigrationTests(_Engagement):
    """A database from before the probe_result table: listings render
    the empty forms and leave the file byte-identical; the first
    record-probe creates the table and records."""

    def drop_probe_table(self, pre_slice1=False):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE probe_result")
            if pre_slice1:
                conn.execute("ALTER TABLE packet_record DROP COLUMN posture")
            conn.commit()
        self.assertNotIn("probe_result", tables(self.db))

    def check_older_database(self):
        before = sha(self.db)
        self.assertEqual(self.listing(), (
            "Pack: flash-20261113-001 (ARTEX mitigations rubric)\n"
            "No probes recorded.\n"
        ))
        self.assertTrue(self.listing("--unprobed").endswith(
            "Unprobed: 11 of 11 Covered or Partial items\n"))
        with closing(Store(self.db)) as store:
            self.assertEqual(store.list_probes(PACK), [])
        self.assertEqual(sha(self.db), before)
        self.assertNotIn("probe_result", tables(self.db))
        # A refused record-probe neither creates the table nor migrates.
        code, _, _ = run_cli(["record-probe", self.db, "--pack", PACK,
                              "--item", "R-9.9", "--method", "m",
                              "--outcome", "failed"])
        self.assertEqual(code, 1)
        self.assertEqual(sha(self.db), before)
        self.probe("R-1.4", "failed")
        self.assertIn("probe_result", tables(self.db))
        self.assertIn(" failed — 2026-11-25 · operator · 1 probe on record",
                      self.listing())

    def test_database_without_the_probe_table(self):
        self.drop_probe_table()
        self.check_older_database()

    def test_pre_slice1_database(self):
        self.drop_probe_table(pre_slice1=True)
        self.check_older_database()

    def test_new_databases_carry_the_table(self):
        self.assertIn("probe_result", tables(self.db))


if __name__ == "__main__":
    unittest.main()
