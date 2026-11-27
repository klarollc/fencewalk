"""Registry CLI contracts, atomic writes and database byte preservation."""

import datetime
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from fencewalk.__main__ import main
from fencewalk.fixture import load_fixture
from fencewalk.registry import _ReadOnlyStore
from fencewalk.store import Store

FIXTURES = Path(__file__).resolve().parents[1] / "src/fencewalk/fixtures"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = self.root / "registry.json"
        self.db = self.root / "engagement.db"
        self.env = patch.dict(os.environ, {"HOME": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("FENCEWALK_REGISTRY", None)

    def cli(self, command, *args, registry=True):
        argv = [command, *map(str, args)]
        if registry:
            argv += ["--registry", str(self.registry)]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def load(self, fixture="google-workspace", db=None):
        db = db or self.db
        load_fixture(FIXTURES / fixture, db)
        return db

    def register(self, db=None):
        code, out, err = self.cli("register", db or self.db)
        self.assertEqual(code, 0, err)
        return out

    def test_register_stores_only_canonical_path_and_registration_date(self):
        self.load()
        with Store(self.db) as store:
            subject = store.get_engagement()["subject_label"]
        self.assertIn(subject, self.register())
        self.assertEqual(json.loads(self.registry.read_text()), [{
            "path": str(self.db.resolve()),
            "registered_date": datetime.date.today().isoformat(),
        }])

    def test_absent_registry_lists_plain_empty_without_creating_anything(self):
        self.registry = self.root / "absent" / "registry.json"
        self.assertEqual(self.cli("engagements"), (0, "no engagements registered\n", ""))
        self.assertFalse(self.registry.parent.exists())

    def test_empty_registry_lists_plain_empty_and_is_unchanged(self):
        self.registry.write_text("[]\n")
        before = self.registry.read_bytes()
        self.assertEqual(self.cli("engagements"), (0, "no engagements registered\n", ""))
        self.assertEqual(self.registry.read_bytes(), before)

    def test_missing_file_registration_creates_neither_file(self):
        code, _, err = self.cli("register", self.db)
        self.assertEqual(code, 1)
        self.assertIn("no such database file", err)
        self.assertFalse(self.db.exists())
        self.assertFalse(self.registry.exists())

    def test_directory_is_not_a_database_file(self):
        code, _, err = self.cli("register", self.root)
        self.assertEqual(code, 1)
        self.assertIn("no such database file", err)
        self.assertFalse(self.registry.exists())

    def test_database_with_no_engagement_is_refused_without_registry_change(self):
        self.load()
        self.register()
        empty = self.root / "empty.db"
        with Store(empty) as store:
            store.init_schema()
        before, db_before = self.registry.read_bytes(), digest(empty)
        code, _, err = self.cli("register", empty)
        self.assertEqual(code, 1)
        self.assertIn("no engagement", err)
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertEqual(digest(empty), db_before)

    def test_non_database_file_and_unrelated_database_are_refused(self):
        self.db.write_text("not a database")
        other = self.root / "other.db"
        with sqlite3.connect(other) as conn:
            conn.execute("CREATE TABLE unrelated (id INTEGER)")
        for db in (self.db, other):
            with self.subTest(db=db):
                before = digest(db)
                code, _, err = self.cli("register", db)
                self.assertEqual(code, 1)
                self.assertIn(str(db), err)
                self.assertFalse(self.registry.exists())
                self.assertEqual(digest(db), before)

    def test_duplicate_registration_collapses_relative_paths_and_symlinks(self):
        self.load()
        self.register()
        alias = self.root / "alias.db"
        alias.symlink_to(self.db)
        before = self.registry.read_bytes()
        for db in (self.db, alias, self.root / ".." / self.root.name / self.db.name,
                   Path(os.path.relpath(self.db))):
            with self.subTest(db=db):
                code, _, err = self.cli("register", db)
                self.assertEqual(code, 1)
                self.assertIn("already registered", err)
                self.assertEqual(self.registry.read_bytes(), before)

    def test_unregister_unregistered_path_preserves_registry(self):
        for exists in (False, True):
            with self.subTest(exists=exists):
                if exists:
                    self.registry.write_text("[]\n")
                code, _, err = self.cli("unregister", self.db)
                self.assertEqual(code, 1)
                self.assertIn("not registered", err)
                self.assertEqual(self.registry.exists(), exists)
                if exists:
                    self.assertEqual(self.registry.read_text(), "[]\n")
                self.assertFalse(self.db.exists())

    def test_unregister_uses_canonical_path_and_keeps_other_entries(self):
        self.load()
        self.register()
        other = self.load("reference-case", self.root / "other.db")
        self.register(other)
        alias = self.root / "alias.db"
        alias.symlink_to(self.db)
        code, _, err = self.cli("unregister", alias)
        self.assertEqual(code, 0, err)
        self.assertEqual([e["path"] for e in json.loads(self.registry.read_text())], [str(other)])

    def test_unregister_never_opens_database_even_if_corrupt_or_missing(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if self.db.exists():
                    self.db.unlink()
                self.load()
                self.register()
                if missing:
                    self.db.unlink()
                else:
                    self.db.write_bytes(b"unreadable as SQLite")
                with patch("fencewalk.registry.sqlite3.connect", side_effect=AssertionError("database opened")):
                    code, _, err = self.cli("unregister", self.db)
                self.assertEqual(code, 0, err)
                self.assertEqual(json.loads(self.registry.read_text()), [])
                self.assertEqual(self.db.exists(), not missing)
                if not missing:
                    self.assertEqual(self.db.read_bytes(), b"unreadable as SQLite")

    def test_missing_listing_shows_path_no_counts_and_does_not_create_database(self):
        self.load()
        self.register()
        before = self.registry.read_bytes()
        self.db.unlink()
        code, out, err = self.cli("engagements")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines()[1:], [f"MISSING · {self.db}"])
        self.assertFalse(self.db.exists())
        self.assertEqual(self.registry.read_bytes(), before)

    def test_malformed_registry_is_hard_error_for_every_command(self):
        self.load()
        for content in (b"{broken", b"\xff", b"{}", b"null", b"[{}]",
                        b'[{"path":"relative","registered_date":"2026-11-24"}]'):
            for command in ("register", "engagements", "unregister"):
                with self.subTest(content=content, command=command):
                    self.registry.write_bytes(content)
                    code, out, err = self.cli(command, *([] if command == "engagements" else [self.db]))
                    self.assertEqual(code, 1)
                    self.assertEqual(out, "")
                    self.assertIn(str(self.registry), err)
                    self.assertEqual(self.registry.read_bytes(), content)

    def test_flag_beats_environment_for_every_command(self):
        self.load()
        env_path = self.root / "env.json"
        env_path.write_bytes(b"{bad JSON")
        os.environ["FENCEWALK_REGISTRY"] = str(env_path)
        self.register()
        self.assertEqual(self.cli("engagements")[0], 0)
        self.assertEqual(self.cli("unregister", self.db)[0], 0)
        self.assertEqual(env_path.read_bytes(), b"{bad JSON")
        self.assertFalse((self.root / ".fencewalk").exists())

    def test_environment_overrides_default_for_every_command(self):
        self.load()
        os.environ["FENCEWALK_REGISTRY"] = str(self.registry)
        self.assertEqual(self.cli("register", self.db, registry=False)[0], 0)
        self.assertTrue(self.registry.exists())
        self.assertEqual(self.cli("engagements", registry=False)[0], 0)
        self.assertEqual(self.cli("unregister", self.db, registry=False)[0], 0)
        self.assertEqual(json.loads(self.registry.read_text()), [])
        self.assertFalse((self.root / ".fencewalk").exists())

    def test_default_is_created_only_on_first_register(self):
        self.load()
        default = self.root / ".fencewalk/registry.json"
        self.assertEqual(self.cli("engagements", registry=False), (0, "no engagements registered\n", ""))
        self.assertFalse(default.parent.exists())
        self.assertEqual(self.cli("register", self.db, registry=False)[0], 0)
        self.assertEqual(json.loads(default.read_text())[0]["path"], str(self.db))
        self.assertEqual(self.cli("unregister", self.db, registry=False)[0], 0)
        self.assertEqual(json.loads(default.read_text()), [])

    def test_listing_uses_live_metadata_counts_and_default_pack(self):
        self.load()
        self.register()
        registry_before = self.registry.read_bytes()
        with Store(self.db) as store:
            store.conn.execute("UPDATE engagement SET name = 'Updated name', subject_label = 'Updated subject', created_date = '2026-01-02'")
            store.conn.commit()
            eng = store.get_engagement()
            packs = len(store.list_packs())
            entries = len(store.list_inventory())
            pack = store.default_pack_id()
            scored = sum(store.coverage_tallies(pack).values())
        code, out, err = self.cli("engagements")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines()[1], f"Updated subject · Updated name · {eng['created_date']} · {pack} · {packs} · {entries} · {scored}")
        with Store(self.db) as store:
            store.set_primary_pack("dns-registrar-security-1.0")
        self.assertIn(f"dns-registrar-security-1.0 · {packs} · {entries} · 0", self.cli("engagements")[1])
        self.assertEqual(self.registry.read_bytes(), registry_before)

    def test_listing_orders_by_created_date_then_subject(self):
        for index, (date, subject) in enumerate((
            ("2026-02-01", "A"), ("2026-01-01", "Z"), ("2026-01-01", "B"),
        )):
            db = self.root / f"{index}.db"
            with Store(db) as store:
                store.init_schema()
                store.create_engagement("Name", subject, date, "verify-first")
            self.register(db)
        code, out, err = self.cli("engagements")
        self.assertEqual(code, 0, err)
        self.assertEqual([line.split(" · ")[0] for line in out.splitlines()[1:]], ["B", "Z", "A"])

    def test_packless_database_lists_zero_counts(self):
        with Store(self.db) as store:
            store.init_schema()
            store.create_engagement("Name", "Subject", "2026-11-24", "verify-first")
        self.register()
        self.assertIn("Subject · Name · 2026-11-24 · — · 0 · 0 · 0", self.cli("engagements")[1])

    def test_all_fixture_databases_stay_byte_identical_across_all_commands(self):
        for fixture in sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()):
            with self.subTest(fixture=fixture):
                db = self.load(fixture, self.root / f"{fixture}.db")
                before = digest(db)
                for command in ("register", "engagements", "unregister"):
                    code, _, err = self.cli(command, *([] if command == "engagements" else [db]))
                    self.assertEqual(code, 0, err)
                    self.assertEqual(digest(db), before, command)

    def test_legacy_database_without_primary_column_stays_byte_identical(self):
        self.load()
        with sqlite3.connect(self.db) as conn:
            conn.execute("ALTER TABLE engagement DROP COLUMN primary_pack")
        before = digest(self.db)
        self.register()
        self.assertEqual(digest(self.db), before)
        code, out, err = self.cli("engagements")
        self.assertEqual(code, 0, err)
        self.assertIn("dns-registrar-security-1.0 · 2 · 20 · 0", out)
        self.assertEqual(digest(self.db), before)
        self.assertEqual(self.cli("unregister", self.db)[0], 0)
        self.assertEqual(digest(self.db), before)
        with sqlite3.connect(self.db) as conn:
            self.assertNotIn("primary_pack", [r[1] for r in conn.execute("PRAGMA table_info(engagement)")])

    def test_read_only_connection_rejects_sql_writes(self):
        self.load()
        before = digest(self.db)
        with _ReadOnlyStore(self.db) as store:
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                store.conn.execute("UPDATE engagement SET name = 'Changed'")
        self.assertEqual(digest(self.db), before)

    def test_read_only_uri_quotes_special_characters_in_database_path(self):
        db = self.load(db=self.root / "space ? # ü.db")
        self.register(db)
        self.assertEqual(self.cli("engagements")[0], 0)
        self.assertEqual(self.cli("unregister", db)[0], 0)

    def test_corrupt_registered_database_is_a_clear_listing_error(self):
        self.load()
        self.register()
        self.db.write_bytes(b"corrupt")
        code, out, err = self.cli("engagements")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn(str(self.db), err)
        self.assertEqual(self.db.read_bytes(), b"corrupt")

    def test_atomic_replace_uses_complete_sibling_temp_file(self):
        self.load()
        self.registry.write_text("[]\n")
        replace = os.replace

        def inspect_replace(source, target):
            self.assertEqual(Path(source).parent, self.registry.parent)
            self.assertEqual(Path(target), self.registry)
            self.assertEqual(self.registry.read_text(), "[]\n")
            self.assertEqual(json.loads(Path(source).read_text())[0]["path"], str(self.db))
            replace(source, target)

        with patch("fencewalk.registry.os.replace", side_effect=inspect_replace) as renamed:
            self.register()
        renamed.assert_called_once()
        self.assertEqual(list(self.root.glob(".registry.json.*.tmp")), [])

    def test_failed_replace_preserves_registry_and_cleans_temp_file(self):
        self.load()
        self.register()
        before = self.registry.read_bytes()
        with patch("fencewalk.registry.os.replace", side_effect=OSError("rename failed")):
            code, _, err = self.cli("unregister", self.db)
        self.assertEqual(code, 1)
        self.assertIn("rename failed", err)
        self.assertEqual(self.registry.read_bytes(), before)
        self.assertEqual(list(self.root.glob(".registry.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
