"""--out must never name the database: the six writing commands refuse.

report, pdf, checklist, packet, run-model, and draft all write to
--out. Pointed at the database itself (directly, through a relative
path, or through a symlink), each refuses before rendering, before
any provider call, and before any packet is recorded; the database
is left byte-identical and readable. --out anywhere else behaves as
before, including overwriting an existing file.
"""

import hashlib
import io
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from fencewalk.__main__ import main
from fencewalk.fixture import load_fixture
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def _build_db(db_path):
    """The reference fixture plus one recorded packet and one run, so
    draft has a run to render."""
    load_fixture(FIXTURE_DIR, db_path)
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        pack_id = store.conn.execute(
            "SELECT pack_id FROM rubric_pack"
        ).fetchone()["pack_id"]
        store.record_packet(eng["id"], pack_id, "2026-11-22", 2500, 10, "a" * 64)
        store.record_run(eng["id"], "a" * 64, "anthropic/test", "2026-11-22",
                         "## Coverage map\n\nstub\n")
    finally:
        store.close()


def _argv(command, db, out):
    return {
        "report": ["report", db, "--out", out],
        "pdf": ["pdf", db, "--out", out],
        "checklist": ["checklist", db, "--date", "2026-11-22", "--out", out],
        "packet": ["packet", db, "--date", "2026-11-22", "--out", out],
        "run-model": ["run-model", db, "--provider", "anthropic",
                      "--model", "test-model", "--date", "2026-11-22",
                      "--out", out],
        "draft": ["draft", db, "--run", "1", "--out", out],
    }[command]


COMMANDS = ("report", "pdf", "checklist", "packet", "run-model", "draft")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _db_readable(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM packet_record").fetchone()[0]
    finally:
        conn.close()


class OutIsDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "eng.db"
        _build_db(self.db)
        self.old_cwd = os.getcwd()
        os.chdir(self.dir)
        (self.dir / "sub").mkdir()
        os.symlink(self.db, self.dir / "link.db")

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def _assert_refused(self, command, db_arg, out_arg):
        before = _sha(self.db)
        packets_before = _db_readable(self.db)
        provider = mock.Mock(side_effect=AssertionError("provider called"))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
                mock.patch("fencewalk.__main__.call_provider", provider):
            code, out, err = run_cli(_argv(command, db_arg, out_arg))
        label = f"{command} db={db_arg} out={out_arg}"
        self.assertNotEqual(code, 0, label)
        self.assertEqual(
            err, f"error: --out must not be the database path: {out_arg}\n",
            label,
        )
        self.assertEqual(out, "", label)
        provider.assert_not_called()
        self.assertEqual(_sha(self.db), before, label)
        self.assertEqual(_db_readable(self.db), packets_before, label)

    def test_direct_path_is_refused(self):
        for command in COMMANDS:
            self._assert_refused(command, str(self.db), str(self.db))

    def test_relative_paths_that_resolve_to_the_database_are_refused(self):
        for command in COMMANDS:
            self._assert_refused(command, str(self.db), "eng.db")
            self._assert_refused(command, str(self.db), "./sub/../eng.db")
            self._assert_refused(command, "eng.db", str(self.db))

    def test_symlink_to_the_database_is_refused(self):
        for command in COMMANDS:
            self._assert_refused(command, str(self.db), "link.db")
            self._assert_refused(command, "link.db", "eng.db")


class OutElsewhereTest(unittest.TestCase):
    def test_other_paths_still_write_and_may_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "eng.db"
            _build_db(db)
            for command in ("report", "pdf", "checklist", "packet", "draft"):
                target = Path(tmp) / f"{command}.out"
                target.write_text("previous content\n", encoding="utf-8")
                code, out, err = run_cli(_argv(command, str(db), str(target)))
                self.assertEqual(code, 0, f"{command}: {err}")
                self.assertNotEqual(
                    target.read_bytes(), b"previous content\n", command
                )
            # The database is still a database.
            self.assertGreaterEqual(_db_readable(db), 2)

    def test_run_model_elsewhere_still_calls_and_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "eng.db"
            _build_db(db)
            target = Path(tmp) / "model.md"
            provider = mock.Mock(return_value=("model text\n", 10, 2, 0))
            with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
                    mock.patch("fencewalk.__main__.call_provider", provider):
                code, _, err = run_cli(_argv("run-model", str(db), str(target)))
            self.assertEqual(code, 0, err)
            provider.assert_called_once()
            self.assertEqual(target.read_text(encoding="utf-8"), "model text\n")


if __name__ == "__main__":
    unittest.main()
