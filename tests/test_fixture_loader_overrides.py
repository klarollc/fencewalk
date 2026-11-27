"""Fixture loader cross-pack overrides (extra_pack_files, a chain's
control_pack, a fix's rubric_pack_id).

Each test builds a small fixture in a scratch directory from two tiny
packs and loads it. Absent keys keep today's behaviour (every citation
under the primary pack); each override is honoured; an override naming
a pack the fixture does not load is refused with a ValueError naming
the pack, before any database is written; a control_pack without a
control_rubric is refused.
"""

import json
import tempfile
import unittest
from pathlib import Path

from fencewalk.fixture import load_fixture
from fencewalk.store import Store

PRIMARY = {
    "pack_id": "test-primary-1.0", "title": "Primary", "version": "1.0",
    "source_citation": "Test pack.",
    "items": [{"group": "G", "item_id": "P-1", "text": "Primary item."}],
}
EXTRA = {
    "pack_id": "test-extra-1.0", "title": "Extra", "version": "1.0",
    "source_citation": "Test pack.",
    "items": [{"group": "G", "item_id": "X-1", "text": "Extra item."}],
}


def chain(key, rubric=None, **extra):
    c = {"chain_key": key, "name": f"Chain {key}", "earliest_control": "c",
         "control_status": "Gap",
         "steps": [{"phase": "Initial access", "text": "step"}]}
    if rubric is not None:
        c["control_rubric"] = rubric
    c.update(extra)
    return c


def fix(fix_id, items, **extra):
    f = {"fix_id": fix_id, "action": "do it", "effort": "Minutes",
         "chains_broken": "A", "rubric_item_ids": items, "status": "proposed",
         "status_date": "2026-11-21", "status_actor": "operator"}
    f.update(extra)
    return f


class LoaderOverrideTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "packs").mkdir()
        for pack in (PRIMARY, EXTRA):
            (self.root / "packs" / f"{pack['pack_id']}.json").write_text(
                json.dumps(pack), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, chains, fixes, extra_packs=True):
        fx = self.root / "fx"
        fx.mkdir(exist_ok=True)
        engagement = {
            "name": "Override test", "subject_label": "Test firm",
            "created_date": "2026-11-21", "method_order": "verify-first",
            "pack_file": "../packs/test-primary-1.0.json",
        }
        if extra_packs:
            engagement["extra_pack_files"] = ["../packs/test-extra-1.0.json"]
        data = {
            "engagement.json": engagement,
            "inventory.json": {"entries": [{
                "entry_id": "A1", "section": "A", "body": "b",
                "label": "ON RECORD", "source": "s"}]},
            "coverage.json": {"scores": [{
                "item_id": "P-1", "status": "Gap", "reasoning": "r",
                "cited_entry_ids": ["A1"]}]},
            "chains.json": {"chains": chains},
            "fixes.json": {"fixes": fixes},
            "verify_next.json": {"items": []},
        }
        for name, body in data.items():
            (fx / name).write_text(json.dumps(body), encoding="utf-8")
        return fx

    def load(self, fx):
        db = self.root / "eng.db"
        load_fixture(fx, db)
        store = Store(db)
        try:
            packs = [p["pack_id"] for p in store.list_packs()]
            chains = {c["chain_key"]: c for c in store.list_chains()}
            fixes = {f["fix_id"]: f for f in store.list_fixes()}
            coverage_packs = {r["pack_id"] for r in store.conn.execute(
                "SELECT pack_id FROM coverage_score").fetchall()}
        finally:
            store.close()
        return packs, chains, fixes, coverage_packs

    def test_defaults_unchanged_without_overrides(self):
        fx = self.build([chain("A", "P-1"), chain("B")],
                        [fix("F-1", ["P-1"])], extra_packs=False)
        packs, chains, fixes, coverage_packs = self.load(fx)
        self.assertEqual(packs, ["test-primary-1.0"])
        self.assertEqual(chains["A"]["control_pack"], "test-primary-1.0")
        self.assertIsNone(chains["B"]["control_pack"])
        self.assertEqual(fixes["F-1"]["rubric_item_packs"],
                         {"P-1": "test-primary-1.0"})
        self.assertEqual(coverage_packs, {"test-primary-1.0"})

    def test_extra_pack_loaded_after_primary(self):
        fx = self.build([chain("A", "P-1")], [fix("F-1", ["P-1"])])
        packs, chains, fixes, coverage_packs = self.load(fx)
        self.assertEqual(packs, ["test-primary-1.0", "test-extra-1.0"])
        # Loading an extra pack moves no citation off the primary pack.
        self.assertEqual(chains["A"]["control_pack"], "test-primary-1.0")
        self.assertEqual(fixes["F-1"]["rubric_item_packs"],
                         {"P-1": "test-primary-1.0"})
        self.assertEqual(coverage_packs, {"test-primary-1.0"})

    def test_chain_control_pack_honoured(self):
        fx = self.build(
            [chain("A", "X-1", control_pack="test-extra-1.0"), chain("B", "P-1")],
            [fix("F-1", ["P-1"])])
        _, chains, _, _ = self.load(fx)
        self.assertEqual(chains["A"]["control_rubric"], "X-1")
        self.assertEqual(chains["A"]["control_pack"], "test-extra-1.0")
        self.assertEqual(chains["B"]["control_pack"], "test-primary-1.0")

    def test_fix_rubric_pack_id_honoured(self):
        fx = self.build(
            [chain("A", "P-1")],
            [fix("F-1", ["P-1"]),
             fix("F-2", ["X-1"], rubric_pack_id="test-extra-1.0")])
        _, _, fixes, _ = self.load(fx)
        self.assertEqual(fixes["F-1"]["rubric_item_packs"],
                         {"P-1": "test-primary-1.0"})
        self.assertEqual(fixes["F-2"]["rubric_item_packs"],
                         {"X-1": "test-extra-1.0"})

    def test_unknown_control_pack_refused(self):
        fx = self.build([chain("A", "X-1", control_pack="no-such-pack")],
                        [fix("F-1", ["P-1"])])
        with self.assertRaisesRegex(ValueError, "no-such-pack"):
            load_fixture(fx, self.root / "eng.db")
        self.assertFalse((self.root / "eng.db").exists())

    def test_extra_pack_not_listed_is_unknown(self):
        fx = self.build([chain("A", "X-1", control_pack="test-extra-1.0")],
                        [fix("F-1", ["P-1"])], extra_packs=False)
        with self.assertRaisesRegex(ValueError, "test-extra-1.0"):
            load_fixture(fx, self.root / "eng.db")
        self.assertFalse((self.root / "eng.db").exists())

    def test_unknown_rubric_pack_id_refused(self):
        fx = self.build([chain("A", "P-1")],
                        [fix("F-1", ["X-1"], rubric_pack_id="no-such-pack")])
        with self.assertRaisesRegex(ValueError, "no-such-pack"):
            load_fixture(fx, self.root / "eng.db")
        self.assertFalse((self.root / "eng.db").exists())

    def test_control_pack_without_control_rubric_refused(self):
        fx = self.build([chain("A", control_pack="test-extra-1.0")],
                        [fix("F-1", ["P-1"])])
        with self.assertRaisesRegex(ValueError, "control_pack without control_rubric"):
            load_fixture(fx, self.root / "eng.db")
        self.assertFalse((self.root / "eng.db").exists())


if __name__ == "__main__":
    unittest.main()
