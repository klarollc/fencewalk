"""Deeper Slice 4a tests: chain steps name the rubric items they exercise.

chain_step gains item_id and item_pack, both NULL or both set (the
chain head's control_rubric / control_pack pattern), in SCHEMA and via
the ADDED_COLUMNS lazy migration. `add-chain --step-item N=ITEM` names
items at creation and `set-step-item` annotates or clears a step after
the fact, both validated against the pack resolved as --control-rubric
resolves it. Refusals write nothing. Nothing renders differently:
list_chains carries the two fields, and reports and PDFs are unchanged.
"""

import hashlib
import io
import json
import shutil
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
NCSC = "ncsc-cyber-essentials-3.3"

CHAIN_D = [
    "--key", "D", "--name", "Donor list exported through a staff login",
    "--control", "two-step sign-in on every donor-management account",
    "--control-status", "unknown", "--control-rubric", "R-3.4",
    "--step", "Reconnaissance: Staff names are on appeal letters (D1).",
    "--step", "Initial access: A phished staff password is tried.",
    "--step", "Privilege escalation: None needed.",
    "--step", "Collection-exfiltration: The donor list leaves in one export.",
]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def step_columns(db):
    with closing(sqlite3.connect(db)) as conn:
        return [r[1] for r in conn.execute("PRAGMA table_info(chain_step)")]


class _Engagement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.load("ref")

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, name, fixture=FIXTURES / "reference-case"):
        db = str(self.dir / f"{name}.db")
        self.ok(["load-fixture", str(fixture), db])
        return db

    def ok(self, argv):
        code, stdout, err = run_cli(argv)
        self.assertEqual(code, 0, err)
        return stdout

    def refused(self, argv, message, db=None):
        db = db or self.db
        before = sha(db)
        code, _, err = run_cli(argv)
        self.assertEqual(code, 1, err)
        self.assertIn(message, err)
        self.assertEqual(sha(db), before)

    def steps(self, key, db=None):
        with closing(Store(db or self.db)) as store:
            chain = next(c for c in store.list_chains() if c["chain_key"] == key)
        return [(s["step_no"], s["item_id"], s["item_pack"])
                for s in chain["steps"]]


class CreationTests(_Engagement):
    def test_step_items_are_recorded_with_their_pack(self):
        out = self.ok(["add-chain", self.db, *CHAIN_D,
                       "--step-item", "1=R-3.4", "--step-item", "4=R-3.1"])
        self.assertEqual(
            out, "added chain D (4 steps, 2 naming rubric items)\n")
        self.assertEqual(self.steps("D"), [
            (1, "R-3.4", PACK), (2, None, None), (3, None, None),
            (4, "R-3.1", PACK),
        ])

    def test_a_chain_without_step_items_records_nulls(self):
        out = self.ok(["add-chain", self.db, *CHAIN_D])
        self.assertEqual(out, "added chain D (4 steps)\n")
        self.assertEqual(self.steps("D"), [
            (1, None, None), (2, None, None), (3, None, None),
            (4, None, None),
        ])
        # The fixture's own chains are unannotated.
        for key in ("A", "B", "C"):
            self.assertTrue(all(i is None and p is None
                                for _, i, p in self.steps(key)), key)

    def test_pack_option_and_primary_default(self):
        self.ok(["load-pack", self.db, str(PACKS / f"{NCSC}.json")])
        self.ok(["add-chain", self.db, "--key", "D", "--name", "n",
                 "--control", "c", "--control-status", "absent",
                 "--step", "A: x", "--step", "B: y", "--pack", NCSC,
                 "--step-item", "2=NCSC-CE-FW-01"])
        self.assertEqual(self.steps("D"), [
            (1, None, None), (2, "NCSC-CE-FW-01", NCSC)])
        # Without --pack: the engagement's primary pack (the fixture's).
        self.ok(["add-chain", self.db, "--key", "E", "--name", "n",
                 "--control", "c", "--control-status", "absent",
                 "--step", "A: x", "--step-item", "1=R-1.1"])
        self.assertEqual(self.steps("E"), [(1, "R-1.1", PACK)])

    def test_creation_refusals_write_nothing(self):
        base = ["add-chain", self.db, *CHAIN_D]
        self.refused(base + ["--step-item", "1=R-9.9"],
                     "no such item in pack flash-20261113-001: R-9.9")
        self.refused(base + ["--step-item", "5=R-1.1"],
                     "--step-item names step 5, but the chain has 4 steps")
        self.refused(base + ["--step-item", "0=R-1.1"],
                     "--step-item names step 0")
        self.refused(base + ["--step-item", "one=R-1.1"],
                     "step item must be '<step_no>=<item_id>'")
        self.refused(base + ["--step-item", "1="],
                     "step item must be '<step_no>=<item_id>'")
        self.refused(base + ["--step-item", "R-1.1"],
                     "step item must be '<step_no>=<item_id>'")
        self.refused(base + ["--step-item", "1=R-1.1", "--step-item", "1=R-1.2"],
                     "--step-item names step 1 twice")
        self.refused(base + ["--step-item", "1=R-1.1", "--pack", "no-such"],
                     "no such pack: no-such")
        # An item that exists, but in another loaded pack.
        self.ok(["load-pack", self.db, str(PACKS / f"{NCSC}.json")])
        self.refused(base + ["--step-item", "1=NCSC-CE-FW-01"],
                     "no such item in pack flash-20261113-001: NCSC-CE-FW-01")

    def test_store_pairing_refusals_write_nothing(self):
        before = sha(self.db)
        with closing(Store(self.db)) as store:
            eng = store.get_engagement()["id"]
            for step in ({"phase": "A", "text": "t", "item_id": "R-1.1"},
                         {"phase": "A", "text": "t", "item_pack": PACK}):
                with self.assertRaises(InvariantError):
                    store.add_chain(eng, "Z", "n",
                                    [{"phase": "A", "text": "ok"}, step],
                                    "c", "absent")
        self.assertEqual(sha(self.db), before)

    def test_loader_passes_step_item_keys_through(self):
        # The engagement file names its pack by a relative path
        # (../../packs/...), so the copy keeps the same depth.
        fixture = self.dir / "src" / "fixtures" / "annotated"
        shutil.copytree(FIXTURES / "reference-case", fixture)
        (self.dir / "src" / "packs").mkdir()
        shutil.copy(PACKS / f"{PACK}.json", self.dir / "src" / "packs")
        chains_file = fixture / "chains.json"
        chains = json.loads(chains_file.read_text(encoding="utf-8"))
        chains["chains"][0]["steps"][0]["item_id"] = "R-2.1"
        chains["chains"][0]["steps"][0]["item_pack"] = PACK
        chains_file.write_text(json.dumps(chains), encoding="utf-8")
        db = self.load("annotated", fixture)
        key = chains["chains"][0]["chain_key"]
        self.assertEqual(self.steps(key, db)[0], (1, "R-2.1", PACK))
        self.assertTrue(all(i is None for _, i, _p in self.steps(key, db)[1:]))


class AnnotationTests(_Engagement):
    def setUp(self):
        super().setUp()
        self.ok(["add-chain", self.db, *CHAIN_D, "--step-item", "1=R-3.4"])

    def test_set_step_item_annotates_and_clears(self):
        out = self.ok(["set-step-item", self.db, "--chain", "D", "--step", "4",
                       "--item", "R-3.1"])
        self.assertEqual(out, "chain D step 4: item R-3.1"
                              " (flash-20261113-001) (was none)\n")
        out = self.ok(["set-step-item", self.db, "--chain", "D", "--step", "1",
                       "--item", "R-3.2"])
        self.assertEqual(out, "chain D step 1: item R-3.2 (flash-20261113-001)"
                              " (was R-3.4 (flash-20261113-001))\n")
        out = self.ok(["set-step-item", self.db, "--chain", "D", "--step", "1",
                       "--clear"])
        self.assertEqual(out, "chain D step 1: item none"
                              " (was R-3.2 (flash-20261113-001))\n")
        self.assertEqual(self.steps("D"), [
            (1, None, None), (2, None, None), (3, None, None),
            (4, "R-3.1", PACK),
        ])

    def test_set_step_item_on_a_fixture_chain_and_another_pack(self):
        self.ok(["load-pack", self.db, str(PACKS / f"{NCSC}.json")])
        self.ok(["set-step-item", self.db, "--chain", "A", "--step", "2",
                 "--item", "NCSC-CE-FW-01", "--pack", NCSC])
        self.assertEqual(self.steps("A")[1], (2, "NCSC-CE-FW-01", NCSC))

    def test_annotation_refusals_write_nothing(self):
        base = ["set-step-item", self.db]
        self.refused(base + ["--chain", "Z", "--step", "1", "--item", "R-1.1"],
                     "no such chain: Z")
        self.refused(base + ["--chain", "D", "--step", "5", "--item", "R-1.1"],
                     "chain D has no step 5")
        self.refused(base + ["--chain", "D", "--step", "0", "--clear"],
                     "chain D has no step 0")
        self.refused(base + ["--chain", "D", "--step", "1", "--item", "R-9.9"],
                     "no such item in pack flash-20261113-001: R-9.9")
        self.refused(base + ["--chain", "D", "--step", "1", "--item", "R-1.1",
                             "--pack", "no-such"], "no such pack: no-such")
        before = sha(self.db)
        for argv in (base + ["--chain", "D", "--step", "1"],
                     base + ["--chain", "D", "--step", "1", "--item", "R-1.1",
                             "--clear"]):
            with self.assertRaises(SystemExit):
                run_cli(argv)
        self.assertEqual(sha(self.db), before)

    def test_store_refusals_write_nothing(self):
        before = sha(self.db)
        with closing(Store(self.db)) as store:
            for args in (("D", 1, "R-1.1", None), ("D", 1, None, PACK),
                         ("Z", 1, "R-1.1", PACK), ("D", 9, "R-1.1", PACK),
                         ("D", 1, "R-9.9", PACK), ("D", 1, "R-1.1", "no-such")):
                with self.assertRaises(InvariantError, msg=str(args)):
                    store.set_chain_step_item(*args)
        self.assertEqual(sha(self.db), before)


class NoRenderingChangeTests(_Engagement):
    def test_step_items_add_only_exposure_lines_and_leave_the_pdf(self):
        plain = self.load("plain")
        self.ok(["add-chain", plain, *CHAIN_D])
        self.ok(["add-chain", self.db, *CHAIN_D,
                 "--step-item", "1=R-3.4", "--step-item", "2=R-3.1"])
        self.ok(["set-step-item", self.db, "--chain", "A", "--step", "1",
                 "--item", "R-2.1"])
        outputs = {}
        for name, db in (("plain", plain), ("annotated", self.db)):
            self.ok(["report", db, "--out", str(self.dir / f"{name}.md")])
            self.ok(["pdf", db, "--out", str(self.dir / f"{name}.pdf")])
            outputs[name] = ((self.dir / f"{name}.md").read_bytes(),
                             (self.dir / f"{name}.pdf").read_bytes())
        # Deeper Slice 4b: the Markdown report gains one computed-exposure
        # line per chain whose steps name items (here A and D), and
        # nothing else; the PDF stays byte-identical.
        plain_md = outputs["plain"][0].decode("utf-8").splitlines()
        annotated_md = outputs["annotated"][0].decode("utf-8").splitlines()
        exposure = [line for line in annotated_md
                    if line.startswith("Computed exposure: ")]
        self.assertEqual(len(exposure), 2)
        self.assertEqual(
            [line for line in annotated_md if line not in exposure], plain_md)
        self.assertEqual(outputs["plain"][1], outputs["annotated"][1])


class MigrationTests(_Engagement):
    """A database whose chain_step predates the columns (as base code
    builds it): reads render as before and write nothing; the first
    add-chain or set-step-item adds both columns and records."""

    def base_shape(self, pre_slice1=False):
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("ALTER TABLE chain_step DROP COLUMN item_id")
            conn.execute("ALTER TABLE chain_step DROP COLUMN item_pack")
            if pre_slice1:
                conn.execute("ALTER TABLE packet_record DROP COLUMN posture")
            conn.commit()
        self.assertEqual(step_columns(self.db),
                         ["chain_id", "step_no", "phase", "text"])

    def check_reads_write_nothing(self):
        before = sha(self.db)
        with closing(Store(self.db)) as store:
            chains = store.list_chains()
        self.assertNotIn("item_id", chains[0]["steps"][0])
        self.ok(["report", self.db, "--out", str(self.dir / "r.md")])
        self.assertEqual(sha(self.db), before)
        self.assertNotIn("item_id", step_columns(self.db))
        return (self.dir / "r.md").read_bytes()

    def test_first_add_chain_migrates_and_records(self):
        self.base_shape()
        report_before = self.check_reads_write_nothing()
        # A refused add-chain neither writes nor migrates.
        self.refused(["add-chain", self.db, *CHAIN_D, "--step-item", "1=R-9.9"],
                     "no such item")
        self.assertNotIn("item_id", step_columns(self.db))
        self.ok(["add-chain", self.db, *CHAIN_D, "--step-item", "2=R-3.1"])
        self.assertEqual(step_columns(self.db)[-2:], ["item_id", "item_pack"])
        self.assertEqual(self.steps("D")[1], (2, "R-3.1", PACK))
        self.assertEqual(self.steps("A")[0], (1, None, None))
        self.assertTrue(report_before)

    def test_first_set_step_item_migrates_and_records(self):
        self.base_shape()
        self.check_reads_write_nothing()
        self.refused(["set-step-item", self.db, "--chain", "A", "--step", "9",
                      "--item", "R-1.1"], "chain A has no step 9")
        self.assertNotIn("item_id", step_columns(self.db))
        self.ok(["set-step-item", self.db, "--chain", "A", "--step", "1",
                 "--item", "R-2.1"])
        self.assertEqual(step_columns(self.db)[-2:], ["item_id", "item_pack"])
        self.assertEqual(self.steps("A")[0], (1, "R-2.1", PACK))

    def test_pre_slice1_database(self):
        self.base_shape(pre_slice1=True)
        self.check_reads_write_nothing()
        self.ok(["set-step-item", self.db, "--chain", "A", "--step", "1",
                 "--item", "R-2.1"])
        self.assertEqual(self.steps("A")[0], (1, "R-2.1", PACK))

    def test_report_after_migration_differs_only_by_the_exposure_line(self):
        self.base_shape()
        report_before = self.check_reads_write_nothing()
        self.ok(["set-step-item", self.db, "--chain", "A", "--step", "1",
                 "--item", "R-2.1"])
        self.ok(["report", self.db, "--out", str(self.dir / "r2.md")])
        # Deeper Slice 4b: chain A now carries its computed exposure, and
        # nothing else in the report moves.
        after = (self.dir / "r2.md").read_text(encoding="utf-8").splitlines()
        exposure = [line for line in after
                    if line.startswith("Computed exposure: ")]
        self.assertEqual(exposure, [
            "Computed exposure: contested at step 1, where R-2.1 is Unknown;"
            " no annotated step is Covered. Derived from 1 of 4 steps (the one"
            " that names an item); the other steps are not judged."])
        self.assertEqual([line for line in after if line not in exposure],
                         report_before.decode("utf-8").splitlines())

    def test_new_databases_carry_the_columns(self):
        self.assertEqual(step_columns(self.db),
                         ["chain_id", "step_no", "phase", "text",
                          "item_id", "item_pack"])


if __name__ == "__main__":
    unittest.main()
