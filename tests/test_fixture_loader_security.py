import io
import json
import shutil
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fencewalk.__main__ import main
from fencewalk.fixture import bundled_fixture_dir, load_fixture


class FixtureLoaderSecurityTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.fixture = self.root / "fixture"
        self.db = self.root / "eng.db"
        source = Path(bundled_fixture_dir("reference-case"))
        shutil.copytree(source, self.fixture)
        self.engagement_path = self.fixture / "engagement.json"
        self.engagement = self._read(self.engagement_path)
        self.pack = (source / self.engagement["pack_file"]).resolve()
        shutil.copyfile(self.pack, self.fixture / "local-pack.json")
        self.engagement["pack_file"] = "local-pack.json"
        self._write(self.engagement_path, self.engagement)

    def _read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, path, content):
        path.write_text(json.dumps(content), encoding="utf-8")

    def _run_cli(self, *args):
        stderr = io.StringIO()
        with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            code = main(["load-fixture", str(self.fixture), str(self.db), *args])
        return code, stderr.getvalue()

    def test_invalid_verify_next_seq_is_a_clean_cli_refusal(self):
        path = self.fixture / "verify_next.json"
        verify_next = self._read(path)
        for seq in ("<em>text</em>", "01", "+1", "1 ", True, 1.5):
            with self.subTest(seq=seq):
                verify_next["items"][0]["seq"] = seq
                self._write(path, verify_next)
                self.assertEqual(
                    self._run_cli(),
                    (1, "error: verify-next seq must be a canonical integer\n"),
                )
                self.assertFalse(self.db.exists())

    def test_primary_traversal_and_extra_symlink_refused_before_pack_open(self):
        outside = self.root / "outside.json"
        shutil.copyfile(self.pack, outside)
        (self.fixture / "link.json").symlink_to(outside)
        for field, name, value in (
            ("pack_file", "../outside.json", "../outside.json"),
            ("extra_pack_files", "link.json", ["link.json"]),
        ):
            with self.subTest(field=field):
                self._write(self.engagement_path, {**self.engagement, field: value})
                with patch("fencewalk.fixture.load_pack") as load_pack:
                    with self.assertRaises(ValueError) as refusal:
                        load_fixture(self.fixture, self.db)
                    load_pack.assert_not_called()
                self.assertIn(name, str(refusal.exception))
                self.assertIn("outside the allowed pack roots", str(refusal.exception))
                self.assertFalse(self.db.exists())

    def test_missing_pack_inside_fixture_keeps_clean_not_found_error(self):
        self.engagement["pack_file"] = "missing.json"
        self._write(self.engagement_path, self.engagement)
        code, error = self._run_cli()
        self.assertEqual(code, 1)
        self.assertIn("No such file or directory", error)
        self.assertIn("missing.json", error)
        self.assertNotIn("Traceback", error)

    def test_repeatable_cli_pack_roots_allow_external_pack(self):
        outside = self.root / "external"
        outside.mkdir()
        shutil.copyfile(self.pack, outside / "pack.json")
        self.engagement["pack_file"] = str(outside / "pack.json")
        self._write(self.engagement_path, self.engagement)
        self.assertEqual(
            self._run_cli("--pack-root", str(self.fixture), "--pack-root", str(outside)),
            (0, ""),
        )
        self.assertTrue(self.db.is_file())
