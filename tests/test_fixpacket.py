"""Single-fix packets (`fencewalk fix-packet`) and the read they need,
Store.list_fix_status_history.

Every database here is a real bundled fixture, changed only through
the CLI's own commands or the Store's write methods. A fix packet is a
view: rendering one must leave the database's bytes unchanged and
record nothing.
"""

import hashlib
import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixpacket import render_fix_packet
from fencewalk.fixture import load_fixture
from fencewalk.store import Store

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


def query(db, sql, params=()):
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute(sql, params).fetchall()


def section(packet, title):
    """The lines of one '## title' section, up to the next '## '."""
    lines = packet.split("\n")
    start = lines.index(f"## {title}") + 1
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


class FixPacketTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def load(self, fixture="reference-case"):
        db = self.root / f"{fixture}.db"
        load_fixture(FIXTURES / fixture, db)
        return db

    def run_ok(self, *args):
        code, out, err = cli(*args)
        self.assertEqual(code, 0, err)
        return out

    def packet(self, db, fix_id, *extra):
        return self.run_ok("fix-packet", db, fix_id, *extra)

    def refuse(self, *args):
        code, out, err = cli("fix-packet", *args)
        self.assertEqual(code, 1, out)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("error: "), err)
        self.assertNotIn("Traceback", err)
        return err

    # -- Store.list_fix_status_history --------------------------------------

    def test_history_is_oldest_first_across_status_changes(self):
        db = self.load()
        self.run_ok("set-fix-status", db, "F-10", "approved",
                    "--date", "2026-12-01", "--actor", "operator")
        self.run_ok("set-fix-status", db, "F-10", "done",
                    "--date", "2026-12-05", "--actor", "principal")
        with Store(db) as store:
            self.assertEqual(store.list_fix_status_history("F-10"), [
                {"status": "proposed", "date": "2026-11-05", "actor": "operator"},
                {"status": "approved", "date": "2026-12-01", "actor": "operator"},
                {"status": "done", "date": "2026-12-05", "actor": "principal"},
            ])
            # Another fix's history is its own.
            self.assertEqual(
                [h["status"] for h in store.list_fix_status_history("F-3")],
                ["proposed"],
            )

    def test_history_of_unknown_fix_is_empty(self):
        db = self.load()
        with Store(db) as store:
            self.assertEqual(store.list_fix_status_history("F-99"), [])

    def test_history_read_writes_nothing(self):
        db = self.load()
        before = digest(db)
        with Store(db) as store:
            store.list_fix_status_history("F-10")
            store.list_fix_status_history("F-99")
        self.assertEqual(digest(db), before)

    # -- the packet ------------------------------------------------------------

    def test_fixture_packet_header_items_and_verify_list(self):
        db = self.load()
        packet = self.packet(db, "F-10")
        (action,) = query(db, "SELECT action FROM fix WHERE fix_id = 'F-10'")[0]
        self.assertTrue(packet.startswith(f"# F-10 — {action}\n"))
        self.assertIn(
            "- Subject: Marigold Community Food Bank (fictional reference firm)\n",
            packet,
        )
        self.assertIn(
            "- Engagement: Reference case — Marigold Community Food Bank"
            " perimeter audit\n",
            packet,
        )
        self.assertIn(
            "- Status: proposed (2026-11-05, operator) · effort Minutes, then a"
            " wait · breaks None (evidence)\n", packet,
        )
        items = section(packet, "Mapped rubric items")
        self.assertEqual([l for l in items if l.startswith("### ")],
                         ["### `R-2.3`", "### `R-4.4`"])
        for item_id in ("R-2.3", "R-4.4"):
            (text,) = query(
                db, "SELECT text FROM rubric_item WHERE pack_id = ? AND item_id = ?",
                (REF_PACK, item_id),
            )[0]
            self.assertIn(f"- Rubric text: {text}\n", packet)
        self.assertIn(f"- Pack: `{REF_PACK}` — ARTEX mitigations rubric", items)
        self.assertIn(
            "- Coverage: Unknown — The managed IT provider that ran the tenant"
            " until June 2025 never wrote down what it connected (A9), so whether"
            " any of the advisory's affected applications were ever authorized"
            " here cannot be said from the record.", items,
        )
        self.assertIn(
            "- Coverage: Unknown — Whether any affected application connection"
            " exists turns on the former provider's answer (A9), which has not"
            " yet been asked for.", items,
        )
        self.assertEqual(items.count("- Cited entries: `A9` (ON RECORD)"), 2)
        self.assertEqual(
            [l for l in section(packet, "Verify by rescore") if l.startswith("- ")],
            ["- `R-2.3` · Unknown", "- `R-4.4` · Unknown"],
        )

    def test_packet_carries_full_history_after_status_change(self):
        db = self.load()
        self.run_ok("set-fix-status", db, "F-10", "approved",
                    "--date", "2026-12-01", "--actor", "operator")
        packet = self.packet(db, "F-10")
        rows = [l for l in section(packet, "Status history") if l.startswith("| ")]
        self.assertEqual(rows, [
            "| Status | Date | Actor |",
            "| proposed | 2026-11-05 | operator |",
            "| approved | 2026-12-01 | operator |",
        ])
        self.assertIn("- Status: approved (2026-12-01, operator)", packet)

    def test_packet_follows_current_coverage_and_labels(self):
        db = self.load()
        self.run_ok("set-label", db, "A9", "VERIFIED", "--date", "2026-12-01")
        for item in ("R-2.3", "R-4.4"):
            self.run_ok("rescore", db, "--pack", REF_PACK, "--item", item,
                        "--status", "Covered", "--reasoning", "Fixed and checked.",
                        "--cite", "A9")
        packet = self.packet(db, "F-10")
        self.assertIn("- Coverage: Covered — Fixed and checked.", packet)
        self.assertIn("- Cited entries: `A9` (VERIFIED)", packet)
        self.assertEqual(section(packet, "Verify by rescore")[1],
                         "All mapped items are Covered.")

    def test_mapped_item_not_scored(self):
        db = self.load()
        self.run_ok("load-pack", db, SAMPLE_PACK)
        self.run_ok("add-fix", db, "--id", "F-90", "--action", "Mount life rings.",
                    "--effort", "Minutes", "--breaks", "None",
                    "--rubric", "W-1.2", "--rubric", "W-1.1",
                    "--pack", "sample-wharf-2026", "--date", "2026-12-01")
        packet = self.packet(db, "F-90")
        items = section(packet, "Mapped rubric items")
        self.assertEqual([l for l in items if l.startswith("### ")],
                         ["### `W-1.1`", "### `W-1.2`"])
        self.assertEqual(items.count("- Coverage: not scored"), 2)
        self.assertIn(
            "- Rubric text: Life rings are mounted at every ladder and"
            " inspected monthly.", items,
        )
        self.assertEqual(
            [l for l in section(packet, "Verify by rescore") if l.startswith("- ")],
            ["- `W-1.1` · not scored", "- `W-1.2` · not scored"],
        )

    def test_fix_with_no_mappings_renders_its_explicit_line(self):
        db = self.load()
        with Store(db) as store:
            store.add_fix(store.get_engagement()["id"], "F-91", "Write it down.",
                          "Minutes", "None", status="proposed",
                          status_date="2026-12-02", status_actor="operator")
        for fix_id in ("F-91", "F-4"):  # Store-added, and the fixture's own
            with self.subTest(fix=fix_id):
                packet = self.packet(db, fix_id)
                self.assertEqual(section(packet, "Mapped rubric items")[1],
                                 "No mapped rubric items.")
                self.assertNotIn("### ", packet)
                self.assertEqual(section(packet, "Verify by rescore")[1],
                                 "No mapped rubric items to rescore.")

    def test_every_fixture_fix_renders_rubric_text_verbatim(self):
        for fixture in ALL_FIXTURES:
            db = self.load(fixture)
            before = digest(db)
            mappings = query(
                db, "SELECT f.fix_id, ri.text FROM fix f"
                " JOIN fix_rubric fr ON fr.fix_pk = f.id"
                " JOIN rubric_item ri ON ri.pack_id = fr.pack_id"
                " AND ri.item_id = fr.item_id",
            )
            self.assertTrue(mappings, fixture)
            rendered = {}
            for fix_id, text in mappings:
                with self.subTest(fixture=fixture, fix=fix_id):
                    if fix_id not in rendered:
                        rendered[fix_id] = render_fix_packet(db, fix_id)
                    self.assertIn(f"- Rubric text: {text}\n", rendered[fix_id])
            self.assertEqual(digest(db), before, fixture)

    # -- determinism and --out --------------------------------------------

    def test_repeated_renders_are_byte_identical(self):
        db = self.load()
        first = self.packet(db, "F-10")
        self.assertEqual(self.packet(db, "F-10"), first)
        self.assertEqual(render_fix_packet(db, "F-10"), first)

    def test_out_writes_the_same_packet(self):
        db = self.load()
        out = self.root / "F-10.md"
        self.assertEqual(self.packet(db, "F-10", "--out", out),
                         f"fix packet written to {out}\n")
        self.assertEqual(out.read_text(encoding="utf-8"), self.packet(db, "F-10"))

    # -- immutability -----------------------------------------------------

    def test_render_leaves_database_bytes_and_records_no_run(self):
        db = self.load()
        before = digest(db)
        self.packet(db, "F-10")
        self.packet(db, "F-4")
        self.refuse(db, "F-99")
        self.assertEqual(digest(db), before)
        self.assertEqual(query(db, "SELECT COUNT(*) FROM packet_record")[0][0], 0)

    def test_pre_slice_1_database_stays_byte_identical(self):
        db = self.load()
        query(db, "ALTER TABLE engagement DROP COLUMN primary_pack")
        before = digest(db)
        packet = self.packet(db, "F-10")
        self.assertIn("### `R-2.3`", packet)
        self.assertEqual(digest(db), before)
        columns = [r[1] for r in query(db, "PRAGMA table_info(engagement)")]
        self.assertNotIn("primary_pack", columns)

    # -- refusals ---------------------------------------------------------

    def test_unknown_fix_is_refused_by_name(self):
        db = self.load()
        self.assertIn("no such fix: F-99", self.refuse(db, "F-99"))

    def test_missing_database_is_refused_and_not_created(self):
        ghost = self.root / "ghost.db"
        self.assertIn("no such database", self.refuse(ghost, "F-1"))
        self.assertFalse(ghost.exists())

    def test_out_onto_the_database_is_refused(self):
        db = self.load()
        before = digest(db)
        self.assertIn("--out must not be the database path",
                      self.refuse(db, "F-10", "--out", db))
        self.assertEqual(digest(db), before)


if __name__ == "__main__":
    unittest.main()
