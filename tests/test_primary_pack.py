"""Stored primary pack tests.

Fixture loading records the fixture's own pack (engagement.json
pack_file) as the engagement's primary pack; `set-primary-pack`
records one for an existing engagement and refuses a pack that is not
loaded; Store.default_pack_id() returns the recorded primary and
otherwise exactly the alphabetically-first loaded pack. An explicit
--pack still wins. A database with no recorded primary, including one
whose engagement table predates the column, renders as it always did,
and opening or reading it never writes.
"""

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import load_fixture, load_pack
from fencewalk.packet import assemble_packet
from fencewalk.report import render_report
from fencewalk.store import InvariantError, Store
from fencewalk.web import _default_pack_id, _pack_select

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "src" / "fencewalk" / "fixtures"
FIXTURE_NAMES = (
    "demo-scuba", "dns-registrar", "github-org", "google-workspace",
    "reference-case",
)
GWS_ID = "scuba-gws-v1.1.0"
DNS_ID = "dns-registrar-security-1.0"
FLASH_ID = "flash-20261113-001"
SCUBA_ID = "scuba-m365-v2.0.0"
D = "2026-11-24"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def fixture_pack_id(name):
    """The pack_id of the pack a fixture's engagement.json names as
    pack_file."""
    fixture_dir = FIXTURES / name
    engagement = json.loads(
        (fixture_dir / "engagement.json").read_text(encoding="utf-8")
    )
    return load_pack(fixture_dir / engagement["pack_file"])["pack_id"]


def engagement_columns(db):
    conn = sqlite3.connect(str(db))
    try:
        return [r[1] for r in conn.execute("PRAGMA table_info(engagement)")]
    finally:
        conn.close()


def drop_primary_column(db):
    """Give the database the engagement table every database had
    before the primary pack: no primary_pack column at all."""
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("ALTER TABLE engagement DROP COLUMN primary_pack")
        conn.commit()
    finally:
        conn.close()


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return str(Path(self.tmp.name) / name)

    def load(self, fixture, name):
        db = self.path(name)
        load_fixture(FIXTURES / fixture, db)
        return db


class FixtureLoadRecordsPrimaryTest(Case):
    def test_every_fixture_records_its_pack_file_pack(self):
        for name in FIXTURE_NAMES:
            with self.subTest(fixture=name):
                db = self.load(name, f"{name}.db")
                with Store(db) as store:
                    self.assertEqual(store.primary_pack(), fixture_pack_id(name))
                    self.assertEqual(store.get_engagement()["primary_pack"],
                                     fixture_pack_id(name))

    def test_every_fixture_default_render_is_its_golden(self):
        # The headline: no --pack anywhere.
        for name in FIXTURE_NAMES:
            with self.subTest(fixture=name):
                db = self.load(name, f"{name}-render.db")
                expected = (FIXTURES / name / "EXPECTED-REPORT.md").read_text(
                    encoding="utf-8")
                self.assertEqual(render_report(db), expected)

    def test_google_workspace_primary_is_not_the_alphabetical_first(self):
        db = self.load("google-workspace", "gws.db")
        with Store(db) as store:
            alphabetical = store.conn.execute(
                "SELECT pack_id FROM rubric_pack ORDER BY pack_id LIMIT 1"
            ).fetchone()[0]
            self.assertEqual(alphabetical, DNS_ID)
            self.assertEqual(store.default_pack_id(), GWS_ID)

    def test_google_workspace_default_packet_is_the_pack_packet(self):
        db = self.load("google-workspace", "gws-packet.db")
        default, pack = assemble_packet(db, assembled_date="2026-11-18")
        self.assertEqual(pack["pack_id"], GWS_ID)
        named, _ = assemble_packet(db, GWS_ID, assembled_date="2026-11-18")
        self.assertEqual(default, named)

    def test_explicit_pack_keeps_precedence(self):
        db = self.load("google-workspace", "gws-flag.db")
        text = render_report(db, DNS_ID)
        self.assertIn("not scored 28 (of 28)", text)
        _, pack = assemble_packet(db, DNS_ID, assembled_date="2026-11-18")
        self.assertEqual(pack["pack_id"], DNS_ID)


class DefaultPackIdTest(Case):
    def new_db(self, name, *packs):
        db = self.path(name)
        code, _, err = run_cli([
            "new", db, "--name", "Primary", "--subject", "Test firm",
            "--method-order", "verify-first", "--date", D,
        ])
        self.assertEqual(code, 0, err)
        for pack in packs:
            code, _, err = run_cli(["load-pack", db, pack])
            self.assertEqual(code, 0, err)
        return db

    def test_no_primary_is_the_alphabetical_rule(self):
        db = self.new_db("alpha.db", SCUBA_ID, FLASH_ID)
        with Store(db) as store:
            self.assertIsNone(store.primary_pack())
            self.assertEqual(store.default_pack_id(), FLASH_ID)

    def test_recorded_primary_wins_over_the_alphabetical_rule(self):
        db = self.new_db("primary.db", FLASH_ID, SCUBA_ID)
        with Store(db) as store:
            store.set_primary_pack(SCUBA_ID)
            self.assertEqual(store.default_pack_id(), SCUBA_ID)
            # The web layer picks up the same default.
            self.assertEqual(_default_pack_id(store), SCUBA_ID)
            self.assertIn(f'<option value="{SCUBA_ID}" selected>',
                          _pack_select(store))

    def test_new_records_no_primary_and_no_pack_is_none(self):
        db = self.new_db("empty.db")
        with Store(db) as store:
            self.assertIsNone(store.primary_pack())
            self.assertIsNone(store.default_pack_id())

    def test_store_refuses_an_unloaded_pack_and_writes_nothing(self):
        db = self.new_db("refuse.db", FLASH_ID)
        before = Path(db).read_bytes()
        with Store(db) as store:
            with self.assertRaises(InvariantError):
                store.set_primary_pack(SCUBA_ID)
        self.assertEqual(Path(db).read_bytes(), before)

    def test_a_primary_naming_no_loaded_pack_falls_back(self):
        db = self.new_db("dangling.db", SCUBA_ID, FLASH_ID)
        conn = sqlite3.connect(db)
        try:
            conn.execute("UPDATE engagement SET primary_pack = 'gone-pack'")
            conn.commit()
        finally:
            conn.close()
        with Store(db) as store:
            self.assertIsNone(store.primary_pack())
            self.assertEqual(store.default_pack_id(), FLASH_ID)


class SetPrimaryPackCliTest(Case):
    def test_accepts_a_loaded_pack(self):
        db = self.load("reference-case", "ref.db")
        code, _, err = run_cli(["load-pack", db, SCUBA_ID])
        self.assertEqual(code, 0, err)
        code, out, err = run_cli(["set-primary-pack", db, SCUBA_ID])
        self.assertEqual(code, 0, err)
        self.assertIn(f"primary pack set to {SCUBA_ID}", out)
        with Store(db) as store:
            self.assertEqual(store.default_pack_id(), SCUBA_ID)
        self.assertIn("- Rubric pack: CISA SCuBA M365", render_report(db))
        # And back: the fixture's own pack renders the golden again.
        code, _, err = run_cli(["set-primary-pack", db, FLASH_ID])
        self.assertEqual(code, 0, err)
        expected = (FIXTURES / "reference-case" / "EXPECTED-REPORT.md"
                    ).read_text(encoding="utf-8")
        self.assertEqual(render_report(db), expected)

    def test_refuses_a_pack_not_loaded(self):
        db = self.load("reference-case", "ref-refuse.db")
        before = Path(db).read_bytes()
        code, out, err = run_cli(["set-primary-pack", db, SCUBA_ID])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn(f"no such pack: {SCUBA_ID}", err)
        self.assertEqual(Path(db).read_bytes(), before)

    def test_refuses_a_missing_database(self):
        db = self.path("absent.db")
        code, _, err = run_cli(["set-primary-pack", db, FLASH_ID])
        self.assertEqual(code, 1)
        self.assertIn("no such database", err)
        self.assertFalse(Path(db).exists())


class PreSliceDatabaseTest(Case):
    """A database whose engagement table has no primary_pack column,
    as every database before this slice: it renders exactly as the
    alphabetical default did, opening and reading never write, and
    the first write adds the column through the lazy migration."""

    def setUp(self):
        super().setUp()
        self.db = self.load("google-workspace", "old.db")
        drop_primary_column(self.db)

    def test_renders_the_alphabetical_default(self):
        self.assertNotIn("primary_pack", engagement_columns(self.db))
        before = Path(self.db).read_bytes()
        with Store(self.db) as store:
            self.assertIsNone(store.primary_pack())
            self.assertEqual(store.default_pack_id(), DNS_ID)
            self.assertIsNone(store.get_engagement().get("primary_pack"))
        text = render_report(self.db)
        self.assertIn("not scored 28 (of 28)", text)
        self.assertEqual(text, render_report(self.db, DNS_ID))
        self.assertEqual(Path(self.db).read_bytes(), before)
        self.assertNotIn("primary_pack", engagement_columns(self.db))

    def test_an_unrelated_write_migrates_without_recording_a_primary(self):
        with Store(self.db) as store:
            store.set_entry_label("A4", "VERIFIED", date=D, actor="t")
        self.assertIn("primary_pack", engagement_columns(self.db))
        with Store(self.db) as store:
            self.assertIsNone(store.primary_pack())
            self.assertEqual(store.default_pack_id(), DNS_ID)

    def test_set_primary_pack_migrates_then_records(self):
        code, _, err = run_cli(["set-primary-pack", self.db, GWS_ID])
        self.assertEqual(code, 0, err)
        self.assertIn("primary_pack", engagement_columns(self.db))
        expected = (FIXTURES / "google-workspace" / "EXPECTED-REPORT.md"
                    ).read_text(encoding="utf-8")
        self.assertEqual(render_report(self.db), expected)


if __name__ == "__main__":
    unittest.main()
