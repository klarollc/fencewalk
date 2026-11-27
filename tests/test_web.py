"""UI-0 web interface tests: the read-only server over the store.

The server is started on an ephemeral port against real databases (the
reference fixture, a pack-less database, a scratch database with hostile
text) and fetched with urllib — the same surface an operator's browser
would see. The read-only fence is tested as behavior: non-GET methods
are refused, and a full crawl leaves the database file byte-identical.
"""

import hashlib
import os
import re
import sqlite3
import stat
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from fencewalk.fixture import load_fixture
from fencewalk.report import cite_item, gather_report_data
from fencewalk.store import Store
from fencewalk.web import _citation_context, create_server, startup_warning

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"


def _fetch(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


class Served:
    """Serve one database on an ephemeral localhost port."""

    def __init__(self, db_path):
        self.server = create_server(str(db_path), "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class FixturePagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.db_path = Path(cls.tmp.name) / "reference.db"
        load_fixture(FIXTURE_DIR, cls.db_path)
        cls.served = Served(cls.db_path)
        cls.base = cls.served.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.served.__exit__()
        cls.tmp.cleanup()

    def test_overview_shows_the_fixture_figures(self):
        status, body = _fetch(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn(
            "Reference case — Marigold Community Food Bank perimeter audit", body
        )
        self.assertIn("52 entries", body)
        # The tally figures, with the Unknown figure carrying the
        # amber signal treatment (so the plain string is interrupted
        # by the span markup, by design).
        self.assertIn("Covered 3 · Partial 8 · ", body)
        self.assertIn('<span class="signal">Unknown 5</span>', body)
        self.assertIn("Not applicable 2 · Gap 2 — 20 rows", body)
        self.assertIn("18 to work", body)

    def test_inventory_lists_entries_with_labels(self):
        status, body = _fetch(self.base + "/inventory")
        self.assertEqual(status, 200)
        # A4 is UNKNOWN in the fixture; A6 is VERIFIED.
        self.assertIn('id="entry-A4"', body)
        self.assertIn("registering a second sign-in factor", body)
        self.assertIn('id="entry-A6"', body)
        self.assertIn("52 entries", body)

    def test_inventory_label_filter_narrows(self):
        status, body = _fetch(self.base + "/inventory?label=UNKNOWN")
        self.assertEqual(status, 200)
        self.assertIn('id="entry-A4"', body)
        self.assertNotIn('id="entry-A6"', body)
        self.assertIn("18 of 52 entries", body)
        self.assertIn("clear filters", body)

    def test_inventory_section_filter_narrows(self):
        status, body = _fetch(self.base + "/inventory?section=H")
        self.assertEqual(status, 200)
        self.assertIn('id="entry-H1"', body)
        self.assertNotIn('id="entry-A3"', body)

    def test_checklist_lists_the_18_unknowns(self):
        status, body = _fetch(self.base + "/checklist")
        self.assertEqual(status, 200)
        self.assertEqual(body.count('<span class="box"></span>'), 18)
        self.assertIn('>A4</span>', body)

    def test_coverage_shows_scores_and_no_unscored_items(self):
        status, body = _fetch(self.base + "/coverage")
        self.assertEqual(status, 200)
        self.assertIn("R-1.4", body)
        self.assertIn(">Covered<", body)
        # Every fixture item is scored: no row is in the unscored state,
        # and the tallies say so.
        self.assertNotIn('class="notscored"', body)
        self.assertIn("not scored 0", body)

    def test_report_page_contains_the_report(self):
        status, body = _fetch(self.base + "/report")
        self.assertEqual(status, 200)
        self.assertIn("# Engagement report —", body)
        self.assertIn("Verify-next items: 10", body)

    def test_report_markdown_download(self):
        status, body = _fetch(self.base + "/report.md")
        self.assertEqual(status, 200)
        self.assertIn("# Engagement report —", body)
        self.assertIn(
            "Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows",
            body,
        )

    def test_unknown_path_is_404(self):
        status, _body = _fetch(self.base + "/no-such-page")
        self.assertEqual(status, 404)

    def test_write_methods_are_refused(self):
        for method, path in (
            ("POST", "/"),
            ("POST", "/inventory"),
            ("PUT", "/"),
            ("DELETE", "/inventory"),
            ("PATCH", "/coverage"),
        ):
            status, _body = _fetch(self.base + path, method=method, data=b"")
            self.assertEqual(status, 405, f"{method} {path}")

    def test_full_crawl_leaves_the_database_byte_identical(self):
        before = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        for path in (
            "/",
            "/inventory",
            "/inventory?label=UNKNOWN",
            "/inventory?section=H",
            "/checklist",
            "/coverage",
            "/report",
            "/report.md",
            "/no-such-page",
        ):
            _fetch(self.base + path)
        _fetch(self.base + "/", method="POST", data=b"")
        after = hashlib.sha256(self.db_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)


FLASH_ID = "flash-20261113-001"
GET_PATHS = (
    "/", "/inventory", "/inventory?label=UNKNOWN", "/checklist",
    "/coverage", "/model-pass", "/adjudication", "/fixes", "/report",
    "/report.md",
)


def clear_primary_pack(db):
    """Clear the recorded primary pack, so the database is as every
    database was before the primary pack existed: the default falls
    back to the alphabetically-first loaded pack, the rule this
    test exercises. Raw sqlite3: the store records a primary but
    offers no way to clear one."""
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("UPDATE engagement SET primary_pack = NULL")
        conn.commit()
    finally:
        conn.close()


def _collision_pack(pack_id):
    """A one-item pack whose R-1.1 collides with FLASH's R-1.1."""
    return {
        "pack_id": pack_id, "title": f"Collision pack {pack_id}",
        "source_citation": "Invented for the Fencewalk test suite.",
        "version": "1.0",
        "items": [{"item_id": "R-1.1", "group": "G",
                   "text": f"The {pack_id} reading of R-1.1."}],
    }


def _fix_rubric_texts(body):
    """{fix_id: [anchor text, ...]} for each fix's Rubric links."""
    out = {}
    for article in re.findall(
        r'<article class="entry" id="fix-([^"]+)">(.*?)</article>',
        body, re.S,
    ):
        fix_id, inner = article
        meta = re.search(r"· Rubric: (.*?) · ", inner, re.S).group(1)
        out[fix_id] = re.findall(
            r'<a class="mono" href="/coverage#item-[^"]*">([^<]*)</a>', meta
        )
    return out


class FixesCitationAnnotationTest(unittest.TestCase):
    """0.3.5: the fixes page annotates each rubric citation exactly as
    the report does (cite_item against Store.default_pack_id()), and
    keeps the /coverage#item-<id> link target."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.db = Path(self.tmp.name) / "collide.db"
        load_fixture(FIXTURE_DIR, self.db)
        with Store(self.db) as store:
            store.add_pack(_collision_pack("zzz-late"))
            store.add_fix(
                1, "F-ZZZ", "collision probe", "low", "A", ["R-1.1"],
                status="proposed", status_date="2026-11-22",
                status_actor="test", rubric_pack_id="zzz-late",
            )

    def tearDown(self):
        self.tmp.cleanup()

    def test_second_pack_citation_is_annotated_flash_is_bare(self):
        with Served(self.db) as base:
            status, body = _fetch(base + "/fixes")
        self.assertEqual(status, 200)
        self.assertIn(
            '<a class="mono" href="/coverage#item-R-1.1">'
            "R-1.1 (zzz-late)</a>",
            body,
        )
        texts = _fix_rubric_texts(body)
        self.assertEqual(texts["F-ZZZ"], ["R-1.1 (zzz-late)"])
        # A FLASH citation on the same page renders bare (FLASH is
        # the default pack): F-2 cites R-1.2 and R-1.5.
        self.assertEqual(texts["F-2"], ["R-1.2", "R-1.5"])
        self.assertNotIn("(flash-20261113-001)", body)

    def test_annotations_match_the_report_for_every_fix(self):
        # aaa-first sorts before FLASH, so with no recorded primary it
        # becomes the default pack and every FLASH citation is
        # annotated — on the page exactly as in the report.
        clear_primary_pack(self.db)
        with Store(self.db) as store:
            store.add_pack(_collision_pack("aaa-first"))
        data = gather_report_data(str(self.db))
        self.assertEqual(data["pack_id"], "aaa-first")
        with Served(self.db) as base:
            _status, body = _fetch(base + "/fixes")
        texts = _fix_rubric_texts(body)
        for fix in data["fixes"]:
            stored = fix.get("rubric_item_packs") or {}
            expected = [
                cite_item(i, data["pack_id"], data["item_packs"],
                          stored.get(i))
                for i in fix["rubric_item_ids"]
            ]
            self.assertEqual(texts[fix["fix_id"]], expected, fix["fix_id"])
        self.assertEqual(texts["F-ZZZ"], ["R-1.1 (zzz-late)"])
        self.assertEqual(
            texts["F-2"],
            ["R-1.2 (flash-20261113-001)", "R-1.5 (flash-20261113-001)"],
        )

    def test_citation_context_is_the_reports(self):
        with Store(self.db) as store:
            store.add_pack(_collision_pack("aaa-first"))
        data = gather_report_data(str(self.db))
        with Store(self.db) as store:
            default_pack, item_packs = _citation_context(store)
        self.assertEqual(default_pack, data["pack_id"])
        self.assertEqual(item_packs, data["item_packs"])
        self.assertEqual(list(item_packs), list(data["item_packs"]))


class ReadOnlyOldDatabaseServeTest(unittest.TestCase):
    """0.3.5: a pre-0.3.4 database served from read-only storage
    answers every GET (the fixes page reads list_fixes on the
    un-migrated schema) and is left byte- and mtime-identical."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.db = Path(self.tmp.name) / "old.db"
        load_fixture(FIXTURE_DIR, self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("ALTER TABLE fix_rubric DROP COLUMN pack_id")
            conn.execute("ALTER TABLE chain DROP COLUMN control_pack")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.db.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self.tmp.cleanup()

    def _crawl(self):
        before = (self.db.read_bytes(), os.stat(self.db).st_mtime_ns)
        with Served(self.db) as base:
            results = {path: _fetch(base + path) for path in GET_PATHS}
        for path, (status, _body) in results.items():
            self.assertEqual(status, 200, path)
        self.assertEqual(
            (self.db.read_bytes(), os.stat(self.db).st_mtime_ns), before
        )
        return results

    def test_writable_old_database_is_not_written_by_gets(self):
        results = self._crawl()
        texts = _fix_rubric_texts(results["/fixes"][1])
        self.assertEqual(texts["F-2"], ["R-1.2", "R-1.5"])

    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "root ignores file permissions",
    )
    def test_read_only_old_database_serves_every_get(self):
        self.db.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        self._crawl()


class EscapingTest(unittest.TestCase):
    def test_script_in_entry_body_is_served_as_text(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "esc.db"
            store = Store(db_path)
            try:
                store.init_schema()
                eng_id = store.create_engagement(
                    "Escape test", "Subject", "2026-11-18", "verify-first"
                )
                store.add_inventory_entry(
                    eng_id, "A1", "A", "<script>alert(1)</script>",
                    "UNKNOWN", "test source",
                    date="2026-11-18", actor="tester",
                )
            finally:
                store.close()
            with Served(db_path) as base:
                status, body = _fetch(base + "/inventory")
            self.assertEqual(status, 200)
            self.assertNotIn("<script>alert(1)</script>", body)
            self.assertNotIn("<script", body)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)


class PackLessPagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.db_path = Path(cls.tmp.name) / "fresh.db"
        store = Store(cls.db_path)
        try:
            store.init_schema()
            store.create_engagement(
                "Fresh engagement", "A firm", "2026-11-18", "verify-first"
            )
        finally:
            store.close()
        cls.served = Served(cls.db_path)
        cls.base = cls.served.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.served.__exit__()
        cls.tmp.cleanup()

    def test_overview_packless(self):
        status, body = _fetch(self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn("No rubric pack loaded", body)
        self.assertNotIn("Traceback", body)

    def test_coverage_packless(self):
        status, body = _fetch(self.base + "/coverage")
        self.assertEqual(status, 200)
        self.assertIn("No rubric pack loaded", body)
        self.assertNotIn("Traceback", body)

    def test_report_packless_shows_the_clean_error(self):
        status, body = _fetch(self.base + "/report")
        self.assertEqual(status, 200)
        self.assertIn(
            "error: database holds no rubric pack; load one with load-pack",
            body,
        )
        self.assertNotIn("Traceback", body)

    def test_other_pages_packless(self):
        for path in ("/inventory", "/checklist"):
            status, body = _fetch(self.base + path)
            self.assertEqual(status, 200, path)
            self.assertNotIn("Traceback", body)


class StartupWarningTest(unittest.TestCase):
    def test_localhost_binds_do_not_warn(self):
        self.assertIsNone(startup_warning("127.0.0.1"))
        self.assertIsNone(startup_warning("localhost"))

    def test_non_local_bind_warns(self):
        warning = startup_warning("0.0.0.0")
        self.assertIsNotNone(warning)
        self.assertIn("no authentication", warning)


if __name__ == "__main__":
    unittest.main()
