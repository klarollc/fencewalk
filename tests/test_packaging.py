"""Packaging slice tests: entry point, single-source version, bundled
data resolution (importlib.resources), the packs command, and the
package-data declaration. No test here publishes anything."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk import __version__
from fencewalk.__main__ import main
from fencewalk.fixture import (
    bundled_data_path,
    bundled_fixture_dir,
    bundled_fixture_names,
    bundled_pack_names,
    bundled_pack_path,
    load_pack,
)
from fencewalk.packet import TEMPLATE_PATH
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "src" / "fencewalk"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class PackagingDeclarationTest(unittest.TestCase):
    def test_entry_point_declared(self):
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project.scripts]", text)
        self.assertIn('fencewalk = "fencewalk.__main__:main"', text)

    def test_version_is_single_source(self):
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('dynamic = ["version"]', text)
        self.assertIn('version = {attr = "fencewalk.__version__"}', text)
        self.assertNotIn('version = "0.1.0"', text)
        self.assertNotIn('version = "0.0.1"', text)
        self.assertEqual(__version__, "0.6.1")

    def test_package_data_declared(self):
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[tool.setuptools.package-data]", text)
        for glob in (
            "packs/*.json",
            "fixtures/reference-case/*",
            "fixtures/demo-scuba/*",
            "fixtures/github-org/*",
            "fixtures/dns-registrar/*",
            "fixtures/google-workspace/*",
            "templates/*.md",
        ):
            self.assertIn(f'"{glob}"', text)

    def test_no_runtime_dependencies(self):
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("dependencies = []", text)


class BundledDataCountTest(unittest.TestCase):
    """What a wheel built from this tree carries: the package-data
    globs ship every pack file and every file of every bundled
    fixture directory, so these counts are the wheel's counts."""

    def test_eight_packs_ship(self):
        self.assertEqual(len(bundled_pack_names()), 8)
        self.assertEqual(
            bundled_pack_names(),
            sorted(p.name for p in (PACKAGE_DIR / "packs").glob("*.json")),
        )
        self.assertIn("github-org-security-1.0.json", bundled_pack_names())
        self.assertIn("dns-registrar-security-1.0.json", bundled_pack_names())
        self.assertIn("scuba-gws-v1.1.0.json", bundled_pack_names())

    def test_45_fixture_files_ship(self):
        names = bundled_fixture_names()
        self.assertEqual(
            names, ["demo-scuba", "dns-registrar", "github-org",
                    "google-workspace", "reference-case"])
        text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        files = []
        for name in names:
            self.assertIn(f'"fixtures/{name}/*"', text)
            files += [p for p in (PACKAGE_DIR / "fixtures" / name).iterdir()
                      if p.is_file()]
        self.assertEqual(len(files), 45)


class VersionFlagTest(unittest.TestCase):
    def test_version_flag_prints_package_version(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), f"fencewalk {__version__}")

    def test_failing_invocation_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(
                ["report", str(Path(tmp) / "no-such.db")]
            )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertNotIn("Traceback", err)


class BundledResolutionTest(unittest.TestCase):
    def test_bundled_pack_path_by_stem(self):
        path = bundled_pack_path("scuba-m365-v2.0.0")
        self.assertIsInstance(path, Path)
        self.assertTrue(path.is_file())
        self.assertEqual(
            path, PACKAGE_DIR / "packs" / "scuba-m365-v2.0.0.json"
        )

    def test_bundled_pack_path_by_filename(self):
        path = bundled_pack_path("flash-20261113-001.json")
        self.assertTrue(path.is_file())
        self.assertEqual(
            path, PACKAGE_DIR / "packs" / "flash-20261113-001.json"
        )

    def test_bundled_pack_path_existing_path_loads_as_path(self):
        path = bundled_pack_path(
            str(PACKAGE_DIR / "packs" / "flash-20261113-001.json")
        )
        self.assertTrue(path.is_file())

    def test_bundled_fixture_dir_by_name(self):
        path = bundled_fixture_dir("reference-case")
        self.assertIsInstance(path, Path)
        self.assertTrue(path.is_dir())
        self.assertEqual(
            path, PACKAGE_DIR / "fixtures" / "reference-case"
        )

    def test_template_resolves_inside_package_tree(self):
        self.assertIsInstance(TEMPLATE_PATH, Path)
        self.assertTrue(TEMPLATE_PATH.is_file())
        # Inside the installed package tree, never repo-root-relative:
        # the old parents[2] computation is gone.
        self.assertIn("fencewalk" + "/" + "templates" + "/" + "run-brief.md",
                      str(TEMPLATE_PATH))
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("{engagement_name}", text)

    def test_bundled_data_path_is_importlib_resources(self):
        path = bundled_data_path("packs", "flash-20261113-001.json")
        self.assertTrue(path.is_file())
        self.assertEqual(
            path, PACKAGE_DIR / "packs" / "flash-20261113-001.json"
        )


class PacksCommandTest(unittest.TestCase):
    def test_packs_lists_bundled_packs(self):
        code, out, err = run_cli(["packs"])
        self.assertEqual(code, 0, err)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), len(bundled_pack_names()))
        for filename in bundled_pack_names():
            pack = load_pack(bundled_pack_path(filename))
            groups = {item["group"] for item in pack["items"]}
            expected = (
                f"{pack['pack_id']}: {pack['title']}"
                f" — {len(pack['items'])} items, {len(groups)} groups"
            )
            self.assertIn(expected, lines)


class BundledCliTest(unittest.TestCase):
    """load-pack / load-fixture through the CLI, by bundled name."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "Packaging test", "--subject",
            "Test firm", "--method-order", "verify-first",
            "--date", "2026-11-18",
        ])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_pack_by_bundled_name(self):
        code, out, err = run_cli(
            ["load-pack", self.db, "scuba-m365-v2.0.0"]
        )
        self.assertEqual(code, 0, err)
        pack = load_pack(bundled_pack_path("scuba-m365-v2.0.0"))
        store = Store(self.db)
        try:
            items = store.list_pack_items(pack["pack_id"])
        finally:
            store.close()
        self.assertEqual(len(items), len(pack["items"]))
        self.assertIn(pack["pack_id"], out)

    def test_load_pack_by_bundled_filename(self):
        code, _, err = run_cli(
            ["load-pack", self.db, "flash-20261113-001.json"]
        )
        self.assertEqual(code, 0, err)

    def test_load_pack_unknown_name_fails_clean(self):
        code, _, err = run_cli(["load-pack", self.db, "no-such-pack"])
        self.assertEqual(code, 1)
        self.assertIn("error: no such pack: no-such-pack", err)
        self.assertIn("bundled packs:", err)
        self.assertNotIn("Traceback", err)

    def test_load_pack_nonexistent_path_fails_clean(self):
        missing = str(Path(self.tmp.name) / "nope.json")
        code, _, err = run_cli(["load-pack", self.db, missing])
        self.assertEqual(code, 1)
        self.assertIn(f"error: no such pack: {missing}", err)
        self.assertNotIn("Traceback", err)

    def test_load_fixture_by_bundled_name(self):
        fixture_db = str(Path(self.tmp.name) / "fixture.db")
        code, out, err = run_cli(
            ["load-fixture", "reference-case", fixture_db]
        )
        self.assertEqual(code, 0, err)
        engagement = json.loads(
            (PACKAGE_DIR / "fixtures" / "reference-case"
             / "engagement.json").read_text(encoding="utf-8")
        )
        store = Store(fixture_db)
        try:
            eng = store.get_engagement()
        finally:
            store.close()
        self.assertEqual(eng["name"], engagement["name"])
        self.assertIn("reference-case", out)

    def test_load_fixture_unknown_name_fails_clean(self):
        fixture_db = str(Path(self.tmp.name) / "fixture.db")
        code, _, err = run_cli(
            ["load-fixture", "no-such-fixture", fixture_db]
        )
        self.assertEqual(code, 1)
        self.assertIn("error: no such fixture: no-such-fixture", err)
        self.assertIn("bundled fixtures:", err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
