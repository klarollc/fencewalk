"""Invariant tests: the store enforces the method's discipline in code."""

import inspect
import os
import re
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from fencewalk.store import InvariantError, Store

PACK = {
    "pack_id": "test-pack",
    "title": "Test pack",
    "source_citation": "Test source",
    "version": "1.0",
    "items": [
        {"item_id": "R-1.1", "group": "Group 1", "text": "First item."},
        {"item_id": "R-1.2", "group": "Group 1", "text": "Second item."},
    ],
}


class InvariantTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "eng.db")
        self.store.init_schema()
        self.eng = self.store.create_engagement(
            "Test engagement", "Test subject", "2026-11-18", "verify-first"
        )
        self.store.add_pack(PACK)
        self.store.add_inventory_entry(
            self.eng, "A1", "A", "An entry.", "VERIFIED", "test source",
            "2026-11-18", date="2026-11-18", actor="test",
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_citationless_covered_rejected(self):
        with self.assertRaises(InvariantError):
            self.store.save_coverage(
                self.eng, "test-pack", "R-1.1", "Covered", "No evidence cited."
            )

    def test_citationless_partial_rejected(self):
        with self.assertRaises(InvariantError):
            self.store.save_coverage(
                self.eng, "test-pack", "R-1.1", "Partial", "No evidence cited."
            )

    def test_citationless_gap_rejected(self):
        with self.assertRaises(InvariantError):
            self.store.save_coverage(
                self.eng, "test-pack", "R-1.1", "Gap", "No evidence cited."
            )

    def test_citationless_unknown_accepted(self):
        self.store.save_coverage(
            self.eng, "test-pack", "R-1.1", "Unknown", "Nothing on record."
        )

    def test_na_without_reason_rejected(self):
        with self.assertRaises(InvariantError):
            self.store.save_coverage(
                self.eng, "test-pack", "R-1.1", "Not applicable", "No reason given."
            )
        with self.assertRaises(InvariantError):
            self.store.save_coverage(
                self.eng, "test-pack", "R-1.1", "Not applicable",
                "Blank reason.", na_reason="   ",
            )

    def test_na_with_reason_accepted(self):
        self.store.save_coverage(
            self.eng, "test-pack", "R-1.1", "Not applicable",
            "Does not arise here.", na_reason="No such system exists in the inventory.",
        )

    def test_na_with_citations_still_needs_reason(self):
        with self.assertRaises(InvariantError):
            self.store.save_coverage(
                self.eng, "test-pack", "R-1.1", "Not applicable",
                "Cited but unexplained.", cited_entry_ids=["A1"],
            )

    def test_cited_covered_accepted(self):
        self.store.save_coverage(
            self.eng, "test-pack", "R-1.1", "Covered", "Rests on A1.",
            cited_entry_ids=["A1"],
        )

    def test_label_changes_only_via_explicit_call_with_history(self):
        self.store.add_inventory_entry(
            self.eng, "A2", "A", "An unknown.", "UNKNOWN", "not on record",
            date="2026-11-18", actor="test",
        )
        self.store.set_entry_label("A2", "VERIFIED", date="2026-11-19", actor="operator")
        entries = {e["entry_id"]: e for e in self.store.list_inventory()}
        self.assertEqual(entries["A2"]["label"], "VERIFIED")
        history = self.store.conn.execute(
            "SELECT label, date, actor FROM entry_label_history"
            " WHERE entry_id = 'A2' ORDER BY id"
        ).fetchall()
        self.assertEqual(
            [(h["label"], h["date"], h["actor"]) for h in history],
            [("UNKNOWN", "2026-11-18", "test"), ("VERIFIED", "2026-11-19", "operator")],
        )

    def test_no_other_label_mutation_path(self):
        # The store exposes exactly one label-changing method; nothing in the
        # coverage or fix paths touches inventory labels.
        mutators = [
            name for name in dir(self.store)
            if "label" in name and not name.startswith("_")
        ]
        self.assertEqual(mutators, ["inventory_label_counts", "set_entry_label"])

    def test_fix_status_changes_record_history(self):
        self.store.add_fix(
            self.eng, "F-1", "Do the thing.", "Minutes", "None",
            status="proposed", status_date="2026-11-18", status_actor="adjudication",
        )
        self.store.set_fix_status("F-1", "done", date="2026-11-19", actor="operator")
        fix = self.store.list_fixes()[0]
        self.assertEqual(fix["status"], "done")
        self.assertEqual(fix["status_date"], "2026-11-19")
        self.assertEqual(fix["status_actor"], "operator")

    def test_fix_rubric_items_require_a_pack(self):
        with self.assertRaises(InvariantError) as ctx:
            self.store.add_fix(
                self.eng, "F-1", "Do the thing.", "Minutes", "None",
                ["R-1.1"], status="proposed", status_date="2026-11-18",
                status_actor="adjudication",
            )
        self.assertEqual(
            str(ctx.exception), "rubric items require rubric_pack_id"
        )

    def test_fix_records_the_pack_with_each_citation(self):
        self.store.add_fix(
            self.eng, "F-1", "Do the thing.", "Minutes", "None",
            ["R-1.1", "R-1.2"], status="proposed",
            status_date="2026-11-18", status_actor="adjudication",
            rubric_pack_id="test-pack",
        )
        fix = self.store.list_fixes()[0]
        self.assertEqual(fix["rubric_item_ids"], ["R-1.1", "R-1.2"])
        self.assertEqual(
            fix["rubric_item_packs"],
            {"R-1.1": "test-pack", "R-1.2": "test-pack"},
        )

    def test_fix_without_rubric_items_needs_no_pack(self):
        self.store.add_fix(
            self.eng, "F-1", "Do the thing.", "Minutes", "None",
            status="proposed", status_date="2026-11-18",
            status_actor="adjudication",
        )
        self.assertEqual(self.store.list_fixes()[0]["rubric_item_packs"], {})

    def test_chain_control_rubric_requires_a_pack(self):
        steps = [{"phase": "Access", "text": "A step."}]
        with self.assertRaises(InvariantError) as ctx:
            self.store.add_chain(
                self.eng, "A", "A chain", steps, "A control.", "absent",
                "R-1.1",
            )
        self.assertEqual(
            str(ctx.exception), "control_rubric requires control_pack"
        )
        self.assertEqual(self.store.list_chains(), [])

    def test_chain_records_the_control_pack(self):
        steps = [{"phase": "Access", "text": "A step."}]
        self.store.add_chain(
            self.eng, "A", "A chain", steps, "A control.", "absent",
            "R-1.1", control_pack="test-pack",
        )
        self.store.add_chain(
            self.eng, "B", "No rubric", steps, "A control.", "absent",
        )
        chains = {c["chain_key"]: c for c in self.store.list_chains()}
        self.assertEqual(chains["A"]["control_pack"], "test-pack")
        self.assertIsNone(chains["B"]["control_pack"])


# -- 0.3.5: lazy migration (opening never writes) and the backfill -------

PACK_A = {
    "pack_id": "pack-a",
    "title": "Pack A",
    "source_citation": "Test source",
    "version": "1.0",
    "items": [
        {"item_id": "R-1.1", "group": "G", "text": "Shared with B."},
        {"item_id": "R-1.2", "group": "G", "text": "Only in A."},
    ],
}
PACK_B = {
    "pack_id": "pack-b",
    "title": "Pack B",
    "source_citation": "Test source",
    "version": "1.0",
    "items": [
        {"item_id": "R-1.1", "group": "G", "text": "Shared with A."},
        {"item_id": "B-2.1", "group": "G", "text": "Only in B."},
    ],
}
PACK_C = {
    "pack_id": "pack-c",
    "title": "Pack C",
    "source_citation": "Test source",
    "version": "1.0",
    "items": [{"item_id": "C-3.1", "group": "G", "text": "Only in C."}],
}
D = "2026-11-22"
HASH = "0" * 64


def build_pre_034_db(path):
    """A database with the shape the 0.3.5 probes pin, downgraded to
    the pre-0.3.4 schema with DROP COLUMN (so its citations carry no
    pack): fix F-1 cites R-1.2 (in pack-a only), F-2 cites R-1.1 (in
    pack-a and pack-b), F-3 cites Z-0.0 (in no loaded pack); chain
    C1's control rubric B-2.1 is in pack-b only, C2's is R-1.1 (in
    both), C3 has none. Also one entry, one score, one packet, one
    run, so every write method has something to act on."""
    store = Store(path)
    store.init_schema()
    eng = store.create_engagement("E", "S", D, "verify-first")
    store.add_pack(PACK_A)
    store.add_pack(PACK_B)
    store.add_inventory_entry(
        eng, "A1", "A", "An entry.", "UNKNOWN", "src",
        date=D, actor="test",
    )
    store.save_coverage(eng, "pack-a", "R-1.2", "Unknown", "Not known.")
    steps = [{"phase": "Access", "text": "A step."}]
    store.add_chain(eng, "C1", "One", steps, "ctl", "absent",
                    "B-2.1", control_pack="pack-b")
    store.add_chain(eng, "C2", "Two", steps, "ctl", "absent",
                    "R-1.1", control_pack="pack-a")
    store.add_chain(eng, "C3", "Three", steps, "ctl", "absent")
    for fix_id, item in (("F-1", "R-1.2"), ("F-2", "R-1.1")):
        store.add_fix(eng, fix_id, "act", "low", "C1", [item],
                      status="proposed", status_date=D,
                      status_actor="test", rubric_pack_id="pack-a")
    store.add_fix(eng, "F-3", "act", "low", "C1",
                  status="proposed", status_date=D, status_actor="test")
    store.record_packet(eng, "pack-a", D, 2500, 10, HASH)
    store.record_run(eng, HASH, "m", D, "output")
    store.close()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT INTO fix_rubric (fix_pk, item_id, pack_id)"
            " SELECT id, 'Z-0.0', NULL FROM fix WHERE fix_id = 'F-3'"
        )
        conn.execute("ALTER TABLE fix_rubric DROP COLUMN pack_id")
        conn.execute("ALTER TABLE chain DROP COLUMN control_pack")
        conn.commit()
    finally:
        conn.close()
    return eng


def columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def all_rows(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )]
        return {
            t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
            for t in tables
        }
    finally:
        conn.close()


def fingerprint(path):
    st = os.stat(path)
    return Path(path).read_bytes(), st.st_mtime_ns


# Every Store method that writes, mapped to a call that exercises it
# on the downgraded database. Kept in step with the source by
# test_every_writing_method_is_covered below.
WRITE_CALLS = {
    "create_engagement": lambda s, e: s.create_engagement("E2", "S2", D, "verify-first"),
    "add_inventory_entry": lambda s, e: s.add_inventory_entry(
        e, "A2", "A", "Another.", "UNKNOWN", "src", date=D, actor="t"),
    "set_entry_label": lambda s, e: s.set_entry_label("A1", "VERIFIED", date=D, actor="t"),
    "update_entry_details": lambda s, e: s.update_entry_details("A1", body="Edited."),
    "add_pack": lambda s, e: s.add_pack(PACK_C),
    "save_coverage": lambda s, e: s.save_coverage(e, "pack-a", "R-1.1", "Unknown", "r"),
    "replace_coverage": lambda s, e: s.replace_coverage(e, "pack-a", "R-1.2", "Unknown", "r2"),
    "add_chain": lambda s, e: s.add_chain(
        e, "C4", "Four", [{"phase": "Access", "text": "t"}], "ctl", "absent"),
    "add_fix": lambda s, e: s.add_fix(
        e, "F-4", "act", "low", "C4", status="proposed", status_date=D, status_actor="t"),
    "set_fix_status": lambda s, e: s.set_fix_status("F-1", "done", date=D, actor="t"),
    "add_verify_next": lambda s, e: s.add_verify_next(e, 1, "u", "w", "c"),
    "record_packet": lambda s, e: s.record_packet(e, "pack-a", D, 2500, 11, "1" * 64),
    "record_run": lambda s, e: s.record_run(e, HASH, "m", D, "output 2"),
    "record_adjudication": lambda s, e: s.record_adjudication(
        1, "coverage", "accept", None, D, "t"),
    "set_primary_pack": lambda s, e: s.set_primary_pack("pack-b"),
    "record_probe": lambda s, e: s.record_probe(
        e, "pack-a", "R-1.1", "m", "confirmed", D, "t"),
    "set_chain_step_item": lambda s, e: s.set_chain_step_item(
        "C2", 1, "R-1.2", "pack-a"),
}
# Writers that need no guard: the migration itself; init_schema,
# which creates a fresh schema that already carries the columns; the
# private coverage insert, whose only callers are guarded; and the
# lazy CREATE TABLE IF NOT EXISTS helpers for the slice-4/5 tables,
# which never touch fix_rubric or chain.
UNGUARDED_WRITERS = {
    "migrate", "_backfill", "init_schema", "_insert_coverage",
    "_ensure_model_pass_tables", "_ensure_adjudication_table",
}
WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|REPLACE)\b|\.commit\(|executescript\("
)


class LazyMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "old.db")
        self.eng = build_pre_034_db(self.db)

    def tearDown(self):
        db = Path(self.db)
        if db.exists():
            db.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self.tmp.cleanup()

    def _read_everything(self, store):
        store.get_engagement()
        store.list_inventory()
        store.inventory_label_counts()
        store.list_packs()
        store.default_pack_id()
        store.list_items("pack-a")
        store.list_coverage("pack-a")
        store.coverage_tallies("pack-a")
        store.list_chains()
        fixes = store.list_fixes()
        store.fix_status_counts()
        store.list_verify_next()
        store.list_packets()
        store.get_packet_by_hash(HASH)
        store.list_runs()
        store.get_run(1)
        store.list_adjudications(1)
        return fixes

    def test_opening_and_reading_never_write(self):
        before = fingerprint(self.db)
        with Store(self.db) as store:
            fixes = self._read_everything(store)
        self.assertEqual(fingerprint(self.db), before)
        self.assertNotIn("pack_id", columns(self.db, "fix_rubric"))
        self.assertNotIn("control_pack", columns(self.db, "chain"))
        # list_fixes reads a NULL pack per citation on the old schema.
        packs = {f["fix_id"]: f["rubric_item_packs"] for f in fixes}
        self.assertEqual(packs, {
            "F-1": {"R-1.2": None}, "F-2": {"R-1.1": None},
            "F-3": {"Z-0.0": None},
        })

    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "root ignores file permissions",
    )
    def test_read_only_file_opens_and_reads(self):
        Path(self.db).chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        before = fingerprint(self.db)
        with Store(self.db) as store:
            self._read_everything(store)
        self.assertEqual(fingerprint(self.db), before)

    def test_every_writing_method_is_covered(self):
        writers = set()
        for name, fn in inspect.getmembers(Store, inspect.isfunction):
            if WRITE_PATTERN.search(inspect.getsource(fn)):
                writers.add(name)
        self.assertEqual(writers - UNGUARDED_WRITERS, set(WRITE_CALLS))
        for name in WRITE_CALLS:
            self.assertIn(
                "self._ensure_migrated()",
                inspect.getsource(getattr(Store, name)), name,
            )

    def test_every_write_method_migrates_before_writing(self):
        for name, call in WRITE_CALLS.items():
            with self.subTest(method=name):
                db = str(Path(self.tmp.name) / f"{name}.db")
                eng = build_pre_034_db(db)
                with Store(db) as store:
                    call(store, eng)
                self.assertIn("pack_id", columns(db, "fix_rubric"))
                self.assertIn("control_pack", columns(db, "chain"))
                rows = all_rows(db)
                f1 = [r for r in rows["fix_rubric"] if r["item_id"] == "R-1.2"]
                self.assertEqual([r["pack_id"] for r in f1], ["pack-a"])

    def test_a_refused_write_does_not_migrate(self):
        # Invariant checks run before the guard: a write refused by
        # the method's own discipline leaves the file untouched.
        before = fingerprint(self.db)
        with Store(self.db) as store:
            with self.assertRaises(InvariantError):
                store.set_fix_status("F-1", "proposed", date=D, actor="t")
            with self.assertRaises(InvariantError):
                store.add_fix(self.eng, "F-9", "a", "low", "C1", ["R-1.2"],
                              status="proposed", status_date=D,
                              status_actor="t")
        self.assertEqual(fingerprint(self.db), before)

    def test_first_write_migrates_then_later_opens_write_nothing(self):
        with Store(self.db) as store:
            store.set_entry_label("A1", "VERIFIED", date=D, actor="t")
        self.assertIn("pack_id", columns(self.db, "fix_rubric"))
        self.assertIn("control_pack", columns(self.db, "chain"))
        after_write = fingerprint(self.db)
        with Store(self.db) as store:
            self._read_everything(store)
        self.assertEqual(fingerprint(self.db), after_write)


class BackfillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "old.db")
        build_pre_034_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def _packs(self):
        rows = all_rows(self.db)
        fix_keys = {r["id"]: r["fix_id"] for r in rows["fix"]}
        fixes = {
            (fix_keys[r["fix_pk"]], r["item_id"]): r["pack_id"]
            for r in rows["fix_rubric"]
        }
        chains = {r["chain_key"]: r["control_pack"] for r in rows["chain"]}
        return fixes, chains

    def test_backfill_fills_only_determined_packs(self):
        before = all_rows(self.db)
        with Store(self.db) as store:
            store.set_entry_label("A1", "VERIFIED", date=D, actor="t")
        fixes, chains = self._packs()
        self.assertEqual(fixes, {
            ("F-1", "R-1.2"): "pack-a",   # in exactly one pack: filled
            ("F-2", "R-1.1"): None,       # in two packs: stays NULL
            ("F-3", "Z-0.0"): None,       # in no loaded pack: stays NULL
        })
        self.assertEqual(chains, {
            "C1": "pack-b",               # B-2.1 in exactly one pack
            "C2": None,                   # R-1.1 in two packs
            "C3": None,                   # no control rubric
        })
        # No other row or column changed (the set-label write aside).
        after = all_rows(self.db)
        for row in after["fix_rubric"]:
            del row["pack_id"]
        for row in after["chain"]:
            del row["control_pack"]
        for table in ("inventory_entry", "entry_label_history"):
            del after[table]
            del before[table]
        self.assertEqual(after, before)

    def test_second_migrate_changes_zero_rows_and_writes_nothing(self):
        with Store(self.db) as store:
            first = store.migrate()
        self.assertEqual(first, {
            "columns_added": 2,
            "fix_rubric_backfilled": 1,
            "chain_backfilled": 1,
        })
        settled = fingerprint(self.db)
        with Store(self.db) as store:
            second = store.migrate()
        self.assertEqual(second, {
            "columns_added": 0,
            "fix_rubric_backfilled": 0,
            "chain_backfilled": 0,
        })
        # The second migrate wrote nothing at all: bytes and mtime.
        self.assertEqual(fingerprint(self.db), settled)
        # And a later write (which runs migrate via the guard first)
        # changes no pack.
        with Store(self.db) as store:
            store.set_entry_label("A1", "VERIFIED", date=D, actor="t")
        self.assertEqual(self._packs(), (
            {("F-1", "R-1.2"): "pack-a", ("F-2", "R-1.1"): None,
             ("F-3", "Z-0.0"): None},
            {"C1": "pack-b", "C2": None, "C3": None},
        ))

    def test_backfill_runs_before_a_new_pack_loads(self):
        # add_pack migrates before inserting: C-3.1 is not yet loaded
        # when the backfill runs, and loading a pack that shares an
        # id afterwards does not undo a pack already determined.
        with Store(self.db) as store:
            store.add_pack({
                "pack_id": "pack-z",
                "title": "Pack Z",
                "source_citation": "Test source",
                "version": "1.0",
                "items": [{"item_id": "R-1.2", "group": "G", "text": "Dup."}],
            })
        fixes, _ = self._packs()
        self.assertEqual(fixes[("F-1", "R-1.2")], "pack-a")
        with Store(self.db) as store:
            self.assertEqual(store.migrate()["fix_rubric_backfilled"], 0)


if __name__ == "__main__":
    unittest.main()
