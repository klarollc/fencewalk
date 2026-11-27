"""Deeper Slice 4b tests: the computed attack-path graph.

Each chain's exposure is derived at render time from the standing
scores its annotated steps name: interrupted at the earliest Covered
step; contested at the earliest Partial/Unknown step when none is
Covered; open when every annotated step is Gap, Not applicable or
unscored. A chain whose steps name no items is not computed, and says
so. Related fixes join through fix-to-item mappings.

The hand-built engagement is reference-case, annotated by hand, with
this hand derivation (standing statuses from the fixture):

  A: 1 R-2.1 Unknown · 2 R-4.3 Covered · 3 R-3.3 Covered · 4 R-1.3 Partial
     -> interrupted at step 2 (a later Covered step, 3, also present);
        fixes on R-2.1 / R-4.3 / R-1.3: F-1 (done), F-5, F-6, F-9
  B: 2 R-2.2 Partial · 3 R-2.3 Unknown (steps 1, 4 unannotated)
     -> contested at step 2, from 2 of 4 steps;
        fixes on R-2.2 / R-2.3: F-10, F-14
  C: 1 R-2.6 Not applicable · 2 NCSC-CE-FW-01 unscored · 4 R-1.4 N/A
     -> open, from 3 of 4 steps; fix F-21 (mapped to NCSC-CE-FW-01)
  D: no step names an item -> not computed
  Rescore R-4.3 Covered -> Gap: A -> interrupted at step 3 (R-3.3).
"""

import difflib
import hashlib
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.chains import derive, related_fixes, report_exposures

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "src" / "fencewalk" / "fixtures"
PACKS = REPO_ROOT / "src" / "fencewalk" / "packs"
PACK = "flash-20261113-001"
NCSC = "ncsc-cyber-essentials-3.3"

ANNOTATIONS = (
    ("A", 1, "R-2.1", PACK), ("A", 2, "R-4.3", PACK), ("A", 3, "R-3.3", PACK),
    ("A", 4, "R-1.3", PACK), ("B", 2, "R-2.2", PACK), ("B", 3, "R-2.3", PACK),
    ("C", 1, "R-2.6", PACK), ("C", 2, "NCSC-CE-FW-01", NCSC),
    ("C", 4, "R-1.4", PACK),
)

EXPOSURE_A = ("  Exposure: interrupted at step 2, where R-4.3"
              " (flash-20261113-001) is Covered. Derived from all 4 steps.")
EXPOSURE_B = ("  Exposure: contested at step 2, where R-2.2"
              " (flash-20261113-001) is Partial; no annotated step is Covered."
              " Derived from 2 of 4 steps (those that name an item); the other"
              " steps are not judged.")
EXPOSURE_C = ("  Exposure: open: every annotated step is Gap, Not applicable, or"
              " unscored, so nothing annotated holds. Derived from 3 of 4"
              " steps (those that name an item); the other steps are not judged.")
EXPOSURE_D = ("  Exposure: not computed: no step of this chain names the rubric"
              " item it exercises.")

REPORT_LINES = [
    "Computed exposure: interrupted at step 2, where R-4.3 is Covered."
    " Derived from all 4 steps.",
    "Computed exposure: contested at step 2, where R-2.2 is Partial; no"
    " annotated step is Covered. Derived from 2 of 4 steps (those that name"
    " an item); the other steps are not judged.",
    "Computed exposure: open: every annotated step is Gap, Not applicable, or"
    " unscored, so nothing annotated holds. Derived from 3 of 4 steps (those"
    " that name an item); the other steps are not judged.",
]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chain_block(listing, key):
    """The lines of one chain's block in the chains listing."""
    blocks = listing.split("\n\n")
    for block in blocks:
        if block.startswith(f"Chain {key}:"):
            return block.splitlines()
    raise AssertionError(f"no chain {key} in listing")


class _Engagement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.plain = self.build("plain")
        self.db = self.build("annotated")
        for key, step, item, pack in ANNOTATIONS:
            self.ok(["set-step-item", self.db, "--chain", key, "--step",
                     str(step), "--item", item, "--pack", pack])

    def tearDown(self):
        self.tmp.cleanup()

    def ok(self, argv):
        code, stdout, err = run_cli(argv)
        self.assertEqual(code, 0, err)
        return stdout

    def build(self, name):
        db = str(self.dir / f"{name}.db")
        self.ok(["load-fixture", str(FIXTURES / "reference-case"), db])
        self.ok(["load-pack", db, str(PACKS / f"{NCSC}.json")])
        self.ok(["add-chain", db, "--key", "D",
                 "--name", "Donor list exported through a staff login",
                 "--control", "two-step sign-in on the donor-management"
                 " service",
                 "--control-status", "unknown",
                 "--step", "Reconnaissance: Staff names are on appeal letters.",
                 "--step", "Initial access: A phished staff password is"
                 " tried."])
        self.ok(["add-fix", db, "--id", "F-21",
                 "--action", "Put a boundary firewall rule set on record.",
                 "--effort", "An hour", "--breaks", "C",
                 "--rubric", "NCSC-CE-FW-01", "--pack", NCSC,
                 "--date", "2026-11-25"])
        return db

    def chains(self, db=None):
        return self.ok(["chains", db or self.db])

    def report(self, db):
        out = self.dir / f"{Path(db).stem}-{len(list(self.dir.iterdir()))}.md"
        self.ok(["report", db, "--out", str(out)])
        return out.read_text(encoding="utf-8")


class DerivationTests(_Engagement):
    def test_interrupted_names_the_earliest_covered_step(self):
        block = chain_block(self.chains(), "A")
        self.assertIn(EXPOSURE_A, block)
        self.assertIn("     item R-4.3 (flash-20261113-001) — Covered", block)
        self.assertIn("     item R-3.3 (flash-20261113-001) — Covered", block)

    def test_contested_and_partly_annotated_says_so(self):
        block = chain_block(self.chains(), "B")
        self.assertIn(EXPOSURE_B, block)
        # Unannotated steps are shown unmarked: no item line follows them.
        step1 = next(i for i, line in enumerate(block)
                     if line.startswith("  1. "))
        self.assertTrue(block[step1 + 1].startswith("  2. "))
        step4 = next(i for i, line in enumerate(block)
                     if line.startswith("  4. "))
        self.assertTrue(block[step4 + 1].startswith("  Exposure: "))

    def test_unscored_item_marks_unscored_and_leaves_the_path_open(self):
        block = chain_block(self.chains(), "C")
        self.assertIn(
            "     item NCSC-CE-FW-01 (ncsc-cyber-essentials-3.3) — unscored",
            block)
        self.assertIn(
            "     item R-2.6 (flash-20261113-001) — Not applicable", block)
        self.assertIn(EXPOSURE_C, block)

    def test_a_chain_naming_no_items_is_not_computed(self):
        block = chain_block(self.chains(), "D")
        self.assertIn(EXPOSURE_D, block)
        self.assertIn("  Related fixes: none (no step names an item)", block)
        for word in ("interrupted", "contested", "open:"):
            self.assertNotIn(word, "\n".join(block))

    def test_related_fixes_join_exactly(self):
        listing = self.chains()
        self.assertIn("  Related fixes: F-1 (done), F-5 (proposed),"
                      " F-6 (proposed), F-9 (proposed)",
                      chain_block(listing, "A"))
        self.assertIn("  Related fixes: F-10 (proposed), F-14 (proposed)",
                      chain_block(listing, "B"))
        self.assertIn("  Related fixes: F-21 (proposed)",
                      chain_block(listing, "C"))

    def test_closing_tally(self):
        self.assertTrue(self.chains().endswith(
            "\nExposure: interrupted 1 · contested 1 · open 1 · not computed 1\n"))

    def test_rescore_rederives_on_the_next_render(self):
        before_tables = self.tables()
        self.ok(["rescore", self.db, "--pack", PACK, "--item", "R-4.3",
                 "--status", "Gap", "--reasoning", "Hand rescore.",
                 "--cite", "C1"])
        self.assertIn(
            "  Exposure: interrupted at step 3, where R-3.3"
            " (flash-20261113-001) is Covered. Derived from all 4 steps.",
            chain_block(self.chains(), "A"))
        self.assertIn(
            "Computed exposure: interrupted at step 3, where R-3.3 is Covered."
            " Derived from all 4 steps.", self.report(self.db))
        # Nothing stored: no table was added, none holds an exposure.
        self.assertEqual(self.tables(), before_tables)

    def test_a_proposed_fix_interrupts_nothing(self):
        # Marking a related fix done changes no derivation.
        self.ok(["set-fix-status", self.db, "F-21", "done",
                 "--date", "2026-11-25"])
        block = chain_block(self.chains(), "C")
        self.assertIn(EXPOSURE_C, block)
        self.assertIn("  Related fixes: F-21 (done)", block)

    def tables(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return sorted(r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"))


class SurfaceTests(_Engagement):
    def test_chains_is_read_only_and_deterministic(self):
        before = sha(self.db)
        first = self.chains()
        second = self.chains()
        self.assertEqual(first, second)
        self.assertEqual(sha(self.db), before)

    def test_chains_are_ordered_by_key_with_the_control_line(self):
        listing = self.chains()
        heads = [line for line in listing.splitlines()
                 if line.startswith("Chain ")]
        self.assertEqual([h.split(":")[0] for h in heads],
                         ["Chain A", "Chain B", "Chain C", "Chain D"])
        self.assertIn("(R-1.2, flash-20261113-001) Status: Gap.",
                      chain_block(listing, "A")[1])
        self.assertEqual(chain_block(listing, "D")[1],
                         "  Earliest breaking control: two-step sign-in on"
                         " the donor-management service Status: unknown.")

    def test_report_differs_only_by_the_exposure_lines(self):
        plain = self.report(self.plain)
        annotated = self.report(self.db)
        diff = [line for line in difflib.ndiff(
            plain.splitlines(), annotated.splitlines())
            if line[:2] in ("+ ", "- ")]
        self.assertEqual(diff, ["+ " + line for line in REPORT_LINES])
        # Each line sits directly under its chain's control line.
        lines = annotated.splitlines()
        for exposure in REPORT_LINES:
            at = lines.index(exposure)
            self.assertTrue(lines[at - 1].startswith("Earliest breaking control:"))

    def test_report_cites_a_cross_pack_deciding_item_with_its_pack(self):
        self.ok(["score", self.db, "--pack", NCSC, "--item", "NCSC-CE-FW-01",
                 "--status", "Partial", "--reasoning", "On record only.",
                 "--cite", "E2"])
        report = self.report(self.db)
        self.assertIn(
            "Computed exposure: contested at step 2, where NCSC-CE-FW-01"
            " (ncsc-cyber-essentials-3.3) is Partial; no annotated step is"
            " Covered.", report)

    def test_unannotated_engagement_renders_exactly_as_before(self):
        # No exposure line anywhere, and report_exposures reads nothing:
        # with no annotated chain it does not even open the database.
        self.assertNotIn("Computed exposure", self.report(self.plain))
        from fencewalk.store import Store
        with closing(Store(self.plain)) as store:
            chains = store.list_chains()
        self.assertEqual(
            report_exposures(str(self.dir / "does-not-exist.db"), chains), {})

    def test_no_chains_and_pre_slice4a_databases(self):
        empty = str(self.dir / "empty.db")
        self.ok(["new", empty, "--name", "E", "--subject", "S",
                 "--method-order", "verify-first", "--date", "2026-11-25"])
        self.assertEqual(self.chains(empty), "No chains recorded.\n")
        with closing(sqlite3.connect(self.plain)) as conn:
            conn.execute("ALTER TABLE chain_step DROP COLUMN item_id")
            conn.execute("ALTER TABLE chain_step DROP COLUMN item_pack")
            conn.commit()
        before = sha(self.plain)
        listing = self.chains(self.plain)
        self.assertEqual(listing.count(EXPOSURE_D), 4)
        self.assertNotIn("Computed exposure", self.report(self.plain))
        self.assertEqual(sha(self.plain), before)


class UnitTests(unittest.TestCase):
    def chain(self, *steps):
        return {"steps": [
            {"step_no": i, "item_id": item, "item_pack": "p" if item else None}
            for i, item in enumerate(steps, start=1)
        ]}

    def test_buckets_and_earliest_steps(self):
        statuses = {("p", "c"): "Covered", ("p", "c2"): "Covered",
                    ("p", "pa"): "Partial", ("p", "u"): "Unknown",
                    ("p", "g"): "Gap", ("p", "na"): "Not applicable"}
        d = derive(self.chain("pa", "c", None, "c2"), statuses)
        self.assertEqual((d["kind"], d["step"]["step_no"]), ("interrupted", 2))
        d = derive(self.chain("g", "u", "pa"), statuses)
        self.assertEqual((d["kind"], d["step"]["step_no"], d["mark"]),
                         ("contested", 2, "Unknown"))
        d = derive(self.chain("g", "na", "missing"), statuses)
        self.assertEqual((d["kind"], d["step"]), ("open", None))
        self.assertIsNone(derive(self.chain(None, None), statuses))
        self.assertEqual((d["annotated"], d["steps"]), (3, 3))

    def test_related_fixes_match_on_pack_and_item(self):
        chain = {"steps": [{"step_no": 1, "item_id": "X-1", "item_pack": "p"}]}
        fixes = [
            {"fix_id": "same", "rubric_item_ids": ["X-1"],
             "rubric_item_packs": {"X-1": "p"}},
            {"fix_id": "other-pack", "rubric_item_ids": ["X-1"],
             "rubric_item_packs": {"X-1": "q"}},
            {"fix_id": "legacy", "rubric_item_ids": ["X-1"],
             "rubric_item_packs": {"X-1": None}},
            {"fix_id": "unrelated", "rubric_item_ids": ["X-2"],
             "rubric_item_packs": {"X-2": "p"}},
        ]
        self.assertEqual([f["fix_id"] for f in related_fixes(chain, fixes)],
                         ["same", "legacy"])


if __name__ == "__main__":
    unittest.main()
