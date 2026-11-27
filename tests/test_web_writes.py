"""UI-1 web interface tests: the verification loop's writes.

The server is started on an ephemeral port against scratch databases
and driven with urllib — the same surface an operator's browser would
use. Each write is checked in the store afterwards, not just by its
status code: the web layer is a second front-end, so the record it
leaves must be the record the CLI would have left — same store
methods, same history, same refusals.
"""

import hashlib
import http.client
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from fencewalk.fixture import load_pack, validate_pack
from fencewalk.store import Store
from fencewalk.web import create_server

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PACK_PATH = REPO_ROOT / "tests" / "fixtures" / "sample-pack.json"
FLASH_PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "flash-20261113-001.json"
PACK_ID = "sample-wharf-2026"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


# The write token of the server most recently entered by Served; a
# POST carries it unless the caller passes token explicitly (None
# omits it, a string sends that value instead).
_SERVED_TOKEN = [None]
_AUTO = object()


def _request(url, method="GET", fields=None, headers=None, token=_AUTO):
    """One HTTP request that never follows redirects.

    Returns (status, headers, body text). A write's 303 and its
    Location are part of the behavior under test, so they are read
    directly rather than followed. A POST carries the served
    server's write token unless token says otherwise.
    """
    data = None
    if method == "POST" and fields is not None:
        fields = dict(fields)
        value = _SERVED_TOKEN[0] if token is _AUTO else token
        if value is not None:
            fields["token"] = value
    if fields is not None:
        data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
    req = urllib.request.Request(
        url, method=method, data=data, headers=headers or {}
    )
    try:
        with _OPENER.open(req, timeout=10) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode("utf-8")


class Served:
    """Serve one database on an ephemeral localhost port."""

    def __init__(self, db_path):
        self.server = create_server(str(db_path), "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )

    def __enter__(self):
        _SERVED_TOKEN[0] = self.server.write_token
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _scratch_db(tmp):
    """A scratch engagement: A1 UNKNOWN, A2 VERIFIED, the sample
    pack loaded, nothing scored."""
    db_path = Path(tmp) / "eng.db"
    store = Store(db_path)
    try:
        store.init_schema()
        eng_id = store.create_engagement(
            "Write test engagement", "A test firm",
            "2026-11-18", "verify-first",
        )
        store.add_inventory_entry(
            eng_id, "A1", "A", "The gate latch is fitted.", "UNKNOWN",
            "site visit notes", date="2026-11-18", actor="tester",
        )
        store.add_inventory_entry(
            eng_id, "A2", "A", "The harbour log is kept daily.", "VERIFIED",
            "log inspection", checked_date="2026-11-18",
            date="2026-11-18", actor="tester",
        )
        store.add_pack(validate_pack(load_pack(SAMPLE_PACK_PATH)))
    finally:
        store.close()
    return db_path


def _entry(db_path, entry_id):
    store = Store(db_path)
    try:
        for e in store.list_inventory():
            if e["entry_id"] == entry_id:
                return e
        return None
    finally:
        store.close()


def _history(db_path, entry_id):
    store = Store(db_path)
    try:
        rows = store.conn.execute(
            "SELECT label, date, actor FROM entry_label_history"
            " WHERE entry_id = ? ORDER BY id",
            (entry_id,),
        ).fetchall()
        return [(r["label"], r["date"], r["actor"]) for r in rows]
    finally:
        store.close()


def _coverage(db_path, item_id):
    store = Store(db_path)
    try:
        return store.get_coverage(PACK_ID, item_id)
    finally:
        store.close()


class SetLabelLoopTest(unittest.TestCase):
    def test_label_from_the_checklist_shrinks_the_checklist(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(base + "/checklist")
                self.assertEqual(status, 200)
                self.assertEqual(body.count('<span class="box"></span>'), 1)
                status, headers, _ = _request(
                    base + "/entry/A1/label", method="POST",
                    fields={
                        "label": "VERIFIED", "date": "2026-11-19",
                        "actor": "operator", "from": "checklist",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(headers["Location"], "/checklist")
                status, _, body = _request(base + "/checklist")
                self.assertEqual(status, 200)
                self.assertEqual(body.count('<span class="box"></span>'), 0)
            self.assertEqual(_entry(db_path, "A1")["label"], "VERIFIED")
            self.assertEqual(
                _history(db_path, "A1"),
                [
                    ("UNKNOWN", "2026-11-18", "tester"),
                    ("VERIFIED", "2026-11-19", "operator"),
                ],
            )

    def test_label_from_a_filtered_inventory_view_returns_to_it(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/entry/A1/label", method="POST",
                    fields={
                        "label": "ON RECORD", "date": "2026-11-19",
                        "actor": "operator", "from": "inventory",
                        "label_filter": "UNKNOWN",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(
                    headers["Location"], "/inventory?label=UNKNOWN"
                )
            self.assertEqual(_entry(db_path, "A1")["label"], "ON RECORD")


class EditEntryTest(unittest.TestCase):
    def test_edit_changes_details_never_the_label(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/entry/A1/edit", method="POST",
                    fields={
                        "body": "The gate latch is fitted and oiled.",
                        "source": "second site visit",
                        "checked_date": "2026-11-19",
                        "decay_date": "",
                        "label": "VERIFIED",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(headers["Location"], "/inventory")
            entry = _entry(db_path, "A1")
            self.assertEqual(entry["body"], "The gate latch is fitted and oiled.")
            self.assertEqual(entry["source"], "second site visit")
            self.assertEqual(entry["checked_date"], "2026-11-19")
            self.assertIsNone(entry["decay_date"])
            # The submitted label parameter is ignored outright, and
            # no history row is written: labels change only through
            # the set-label door.
            self.assertEqual(entry["label"], "UNKNOWN")
            self.assertEqual(
                _history(db_path, "A1"),
                [("UNKNOWN", "2026-11-18", "tester")],
            )

    def test_an_emptied_date_field_clears_the_date(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + "/entry/A2/edit", method="POST",
                    fields={
                        "body": "The harbour log is kept daily.",
                        "source": "log inspection",
                        "checked_date": "",
                        "decay_date": "",
                    },
                )
                self.assertEqual(status, 303)
            entry = _entry(db_path, "A2")
            self.assertIsNone(entry["checked_date"])
            self.assertEqual(entry["label"], "VERIFIED")


class AddEntryTest(unittest.TestCase):
    def test_add_entry_assigns_the_next_id_in_the_section(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/entry/new", method="POST",
                    fields={
                        "section": "B",
                        "body": "The store room door locks.",
                        "source": "site visit notes",
                        "label": "ON RECORD",
                        "checked_date": "",
                        "decay_date": "",
                        "date": "2026-11-19",
                        "actor": "operator",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(
                    headers["Location"], "/inventory?section=B"
                )
                status, _, body = _request(base + "/inventory?section=B")
                self.assertEqual(status, 200)
                self.assertIn('id="entry-B1"', body)
            entry = _entry(db_path, "B1")
            self.assertEqual(entry["section"], "B")
            self.assertEqual(entry["label"], "ON RECORD")
            self.assertEqual(
                _history(db_path, "B1"),
                [("ON RECORD", "2026-11-19", "operator")],
            )


class ScoreDisciplineTest(unittest.TestCase):
    def test_score_then_rescore_replaces_atomically(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + f"/coverage/{PACK_ID}/W-1.1/score",
                    method="POST",
                    fields={
                        "status": "Covered",
                        "reasoning": "Seen fitted on site.",
                        "cite": ["A2"],
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(headers["Location"], "/coverage")
                score = _coverage(db_path, "W-1.1")
                self.assertEqual(score["status"], "Covered")
                self.assertEqual(score["cited_entry_ids"], ["A2"])
                # The page now renders the rescore form for W-1.1 and
                # still a score form for the unscored W-1.2.
                status, _, body = _request(base + "/coverage")
                self.assertEqual(status, 200)
                self.assertIn(
                    f'action="/coverage/{PACK_ID}/W-1.1/score"', body
                )
                self.assertIn(
                    '<button type="submit">Rescore</button>', body
                )
                self.assertIn('<button type="submit">Score</button>', body)
                status, headers, _ = _request(
                    base + f"/coverage/{PACK_ID}/W-1.1/score",
                    method="POST",
                    fields={
                        "status": "Partial",
                        "reasoning": "Fitted, but the inspection is overdue.",
                        "cite": ["A2"],
                    },
                )
                self.assertEqual(status, 303)
            score = _coverage(db_path, "W-1.1")
            self.assertEqual(score["status"], "Partial")
            self.assertEqual(
                score["reasoning"], "Fitted, but the inspection is overdue."
            )
            store = Store(db_path)
            try:
                # The old score is gone: the tallies reflect the new
                # status only, and there is exactly one score row.
                self.assertEqual(
                    store.coverage_tallies(PACK_ID), {"Partial": 1}
                )
                self.assertEqual(len(store.list_coverage(PACK_ID)), 1)
            finally:
                store.close()

    def test_covered_without_citations_is_refused_cleanly(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + f"/coverage/{PACK_ID}/W-1.1/score",
                    method="POST",
                    fields={
                        "status": "Covered",
                        "reasoning": "It looks fine.",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    "A coverage score with no cited inventory entries"
                    " may only be saved as Unknown, or as Not applicable"
                    " with an N/A reason",
                    body,
                )
                self.assertNotIn("Traceback", body)
            self.assertIsNone(_coverage(db_path, "W-1.1"))

    def test_not_applicable_without_a_reason_is_refused_cleanly(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + f"/coverage/{PACK_ID}/W-1.1/score",
                    method="POST",
                    fields={
                        "status": "Not applicable",
                        "reasoning": "There is no ladder at the west quay.",
                        "na_reason": "",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    "Not applicable requires a non-empty N/A reason"
                    " grounded in the inventory",
                    body,
                )
                self.assertNotIn("Traceback", body)
            self.assertIsNone(_coverage(db_path, "W-1.1"))

    def test_unknown_references_are_refused_cleanly(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/coverage/no-such-pack/W-1.1/score",
                    method="POST",
                    fields={"status": "Unknown", "reasoning": "x"},
                )
                self.assertEqual(status, 400)
                self.assertIn("no such pack: no-such-pack", body)
                status, _, body = _request(
                    base + f"/coverage/{PACK_ID}/W-9.9/score",
                    method="POST",
                    fields={"status": "Unknown", "reasoning": "x"},
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    f"no such item in pack {PACK_ID}: W-9.9", body
                )
                status, _, body = _request(
                    base + f"/coverage/{PACK_ID}/W-1.1/score",
                    method="POST",
                    fields={
                        "status": "Unknown", "reasoning": "x",
                        "cite": ["Z9"],
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("no such entry: Z9", body)
                for path in ("/entry/Z9/label", "/entry/Z9/edit"):
                    status, _, body = _request(
                        base + path, method="POST",
                        fields={"label": "VERIFIED"},
                    )
                    self.assertEqual(status, 400, path)
                    self.assertIn("no such entry: Z9", body)
                    self.assertNotIn("Traceback", body)
            # None of the refusals wrote anything.
            self.assertIsNone(_coverage(db_path, "W-1.1"))
            store = Store(db_path)
            try:
                self.assertEqual(len(store.list_inventory()), 2)
                self.assertEqual(store.list_coverage(PACK_ID), [])
            finally:
                store.close()


class PostBodyLimitTest(unittest.TestCase):
    def test_oversized_post_refused_before_read_and_normal_write_lands(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            before = db_path.read_bytes()
            served = Served(db_path)
            with served as base:
                path = "/entry/A1/label"
                conn = http.client.HTTPConnection("127.0.0.1", served.port, timeout=5)
                try:
                    conn.request("POST", path, headers={"Content-Length": "1048577"})
                    with conn.getresponse() as response:
                        self.assertEqual(response.status, 413)
                        response.read()
                finally:
                    conn.close()
                self.assertEqual(db_path.read_bytes(), before)
                status, _, _ = _request(
                    base + path, method="POST",
                    fields={"label": "VERIFIED", "from": "checklist"},
                )
                self.assertEqual(status, 303)
            self.assertEqual(_entry(db_path, "A1")["label"], "VERIFIED")


class OriginCheckTest(unittest.TestCase):
    def test_mismatched_origin_is_refused_and_writes_nothing(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + "/entry/A1/label", method="POST",
                    fields={"label": "VERIFIED", "from": "checklist"},
                    headers={"Origin": "http://evil.example"},
                )
                self.assertEqual(status, 403)
            self.assertEqual(_entry(db_path, "A1")["label"], "UNKNOWN")
            self.assertEqual(
                _history(db_path, "A1"),
                [("UNKNOWN", "2026-11-18", "tester")],
            )

    def test_mismatched_referer_is_refused_when_no_origin(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + "/entry/A1/label", method="POST",
                    fields={"label": "VERIFIED"},
                    headers={"Referer": "http://evil.example/a/page"},
                )
                self.assertEqual(status, 403)
            self.assertEqual(_entry(db_path, "A1")["label"], "UNKNOWN")

    def test_matching_origin_is_allowed(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                port = urllib.parse.urlparse(base).port
                status, _, _ = _request(
                    base + "/entry/A1/label", method="POST",
                    fields={"label": "VERIFIED"},
                    headers={"Origin": f"http://127.0.0.1:{port}"},
                )
                self.assertEqual(status, 303)
            self.assertEqual(_entry(db_path, "A1")["label"], "VERIFIED")

    def test_no_origin_headers_is_allowed(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + "/entry/A2/label", method="POST",
                    fields={"label": "ON RECORD"},
                )
                self.assertEqual(status, 303)
            self.assertEqual(_entry(db_path, "A2")["label"], "ON RECORD")


class ReadSurfaceIntactTest(unittest.TestCase):
    def test_post_to_read_pages_is_still_405(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                for path in (
                    "/", "/inventory", "/checklist", "/coverage", "/report",
                ):
                    status, _, _ = _request(
                        base + path, method="POST", fields={}
                    )
                    self.assertEqual(status, 405, path)
                # The write routes accept POST only.
                status, _, _ = _request(
                    base + "/entry/A1/label", method="PUT", fields={}
                )
                self.assertEqual(status, 405)

    def test_get_crawl_leaves_the_database_byte_identical(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            store = Store(db_path)
            try:
                eng_id = store.get_engagement()["id"]
                store.save_coverage(
                    eng_id, PACK_ID, "W-1.1", "Covered",
                    "Seen fitted on site.", ["A2"],
                )
            finally:
                store.close()
            before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            with Served(db_path) as base:
                for path in (
                    "/",
                    "/inventory",
                    "/inventory?label=UNKNOWN",
                    "/inventory?section=A",
                    "/checklist",
                    "/coverage",
                    "/report",
                    "/report.md",
                    "/no-such-page",
                ):
                    _request(base + path)
            after = hashlib.sha256(db_path.read_bytes()).hexdigest()
            self.assertEqual(before, after)


class ListPacksTest(unittest.TestCase):
    def test_list_packs_returns_packs_in_load_order(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "packs.db"
            store = Store(db_path)
            try:
                store.init_schema()
                store.create_engagement(
                    "Packs", "A firm", "2026-11-18", "verify-first"
                )
                self.assertEqual(store.list_packs(), [])
                store.add_pack(validate_pack(load_pack(SAMPLE_PACK_PATH)))
                store.add_pack(validate_pack(load_pack(FLASH_PACK_PATH)))
                packs = store.list_packs()
            finally:
                store.close()
            self.assertEqual(
                [p["pack_id"] for p in packs],
                [PACK_ID, "flash-20261113-001"],
            )
            self.assertEqual(packs[0]["title"], "Sample Wharf Safety Rubric")
            self.assertEqual(packs[1]["title"], "ARTEX mitigations rubric")


if __name__ == "__main__":
    unittest.main()
