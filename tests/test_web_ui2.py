"""UI-2 web interface tests: the model pass and adjudication writes.

Same harness as the UI-1 tests: the server runs on an ephemeral
port against scratch databases and is driven with urllib. Each write
is checked in the store afterwards, not just by its status code: the
web layer is a second front-end, so the record it leaves must be the
record the CLI would have left — same store methods, same history,
same refusals. The packet download is the one exception to the 303
discipline (the store records only packet metadata, so the packet
text exists nowhere after assembly except in the response).
"""

import hashlib
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

from fencewalk.fixture import load_pack, validate_pack
from fencewalk.packet import assemble_packet
from fencewalk.store import Store
from fencewalk.web import create_server

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PACK_PATH = REPO_ROOT / "tests" / "fixtures" / "sample-pack.json"
PACK_ID = "sample-wharf-2026"

FOUR_SECTION_OUTPUT = (
    "# Coverage map\n"
    "- W-1.1 Covered, cites A2.\n"
    "\n"
    "# Attack chains\n"
    "- Chain A breaks at W-1.1.\n"
    "\n"
    "# Fix list\n"
    "- F-1: enable phishing-resistant MFA.\n"
    "\n"
    "# Verify-next list\n"
    "- Check the sign-in logs for the last 30 days.\n"
)

UNSECTIONED_OUTPUT = "Free-form notes.\nNothing sectioned here.\n"


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


def _scratch_db(tmp, with_pack=True):
    """A scratch engagement: A1 UNKNOWN, A2 VERIFIED, the sample
    pack loaded unless with_pack is False, nothing scored."""
    db_path = Path(tmp) / "eng.db"
    store = Store(db_path)
    try:
        store.init_schema()
        eng_id = store.create_engagement(
            "Model pass test engagement", "A test firm",
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
        if with_pack:
            store.add_pack(validate_pack(load_pack(SAMPLE_PACK_PATH)))
    finally:
        store.close()
    return db_path


def _record_packet(db_path, word_cap=2500, date="2026-11-19"):
    """Assemble and record a packet the CLI way; returns its hash."""
    text, pack = assemble_packet(
        str(db_path), word_cap=word_cap, assembled_date=date
    )
    data = text.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        store.record_packet(
            eng["id"], pack["pack_id"], date, word_cap, len(data), sha256
        )
    finally:
        store.close()
    return sha256


def _record_run(db_path, output, model="Test Model"):
    """Record one run answering the database's packet; returns
    (packet hash, run id)."""
    packet_hash = _record_packet(db_path)
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        run_id = store.record_run(
            eng["id"], packet_hash, model, "2026-11-19", output
        )
    finally:
        store.close()
    return packet_hash, run_id


def _runs(db_path):
    store = Store(db_path)
    try:
        return store.list_runs()
    finally:
        store.close()


def _packets(db_path):
    store = Store(db_path)
    try:
        return store.list_packets()
    finally:
        store.close()


def _adjudications(db_path, run_id):
    store = Store(db_path)
    try:
        return store.list_adjudications(run_id)
    finally:
        store.close()


class PacketTest(unittest.TestCase):
    def test_packet_date_refusal_and_canonical_filename(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                url = base + "/model-pass/packet"
                status, headers, body = _request(
                    url, method="POST", fields={"date": "2026-11-19\r\n"},
                )
                self.assertEqual(status, 400)
                self.assertIn("packet date must be a valid ISO date", body)
                self.assertNotIn("Content-Disposition", headers)
                self.assertEqual(_packets(db_path), [])
                for date in ("2026-11-19", "20261119"):
                    with self.subTest(date=date):
                        status, headers, body = _request(
                            url, method="POST", fields={"date": date},
                        )
                        self.assertEqual(status, 200)
                        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                        self.assertEqual(
                            headers["Content-Disposition"],
                            f'attachment; filename="packet-2026-11-19-{digest[:8]}.md"',
                        )
                self.assertEqual(
                    [packet["assembled_date"] for packet in _packets(db_path)],
                    ["2026-11-19", "2026-11-19"],
                )

    def test_assemble_returns_the_download_and_records_it(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, headers, body = _request(
                    base + "/model-pass/packet", method="POST",
                    fields={
                        "pack": PACK_ID, "word_cap": "2500",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 200)
                self.assertIn("attachment", headers["Content-Disposition"])
                self.assertIn("packet-2026-11-19-", headers["Content-Disposition"])
                self.assertIn(".md", headers["Content-Disposition"])
                # The body is the assembled packet text.
                expected, _ = assemble_packet(
                    str(db_path), pack_id=PACK_ID, word_cap=2500,
                    assembled_date="2026-11-19",
                )
                self.assertEqual(body, expected)
                sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
                self.assertIn(sha256[:8], headers["Content-Disposition"])
            packets = _packets(db_path)
            self.assertEqual(len(packets), 1)
            self.assertEqual(packets[0]["sha256"], sha256)
            self.assertEqual(packets[0]["byte_count"], len(body.encode("utf-8")))
            self.assertEqual(packets[0]["word_cap"], 2500)
            self.assertEqual(packets[0]["pack_id"], PACK_ID)
            # The Model pass page now shows the recorded packet row.
            with Served(db_path) as base:
                status, _, page = _request(base + "/model-pass")
                self.assertEqual(status, 200)
                self.assertIn(sha256, page)
                self.assertIn("Latest packet", page)

    def test_second_assembly_is_byte_identical(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                _, _, first = _request(
                    base + "/model-pass/packet", method="POST",
                    fields={
                        "pack": PACK_ID, "word_cap": "2500",
                        "date": "2026-11-19",
                    },
                )
                _, _, second = _request(
                    base + "/model-pass/packet", method="POST",
                    fields={
                        "pack": PACK_ID, "word_cap": "2500",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(first, second)
            packets = _packets(db_path)
            self.assertEqual(len(packets), 2)
            self.assertEqual(packets[0]["sha256"], packets[1]["sha256"])

    def test_packless_database_is_a_clean_refusal(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp, with_pack=False)
            with Served(db_path) as base:
                # No pack field submitted: the form's pack select has
                # no options on a pack-less database, so the assembly
                # falls back to the database's pack — and there is none.
                status, _, body = _request(
                    base + "/model-pass/packet", method="POST",
                    fields={
                        "word_cap": "2500",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    "database holds no rubric pack; load one with load-pack",
                    body,
                )
            self.assertEqual(_packets(db_path), [])

    def test_unknown_pack_is_a_clean_refusal(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/model-pass/packet", method="POST",
                    fields={
                        "pack": "no-such-pack", "word_cap": "2500",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("no such pack: no-such-pack", body)
            self.assertEqual(_packets(db_path), [])

    def test_non_integer_word_cap_is_a_clean_refusal(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/model-pass/packet", method="POST",
                    fields={
                        "pack": PACK_ID, "word_cap": "many",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("word cap must be a whole number", body)
            self.assertEqual(_packets(db_path), [])


class IngestTest(unittest.TestCase):
    def test_paste_ingests_verbatim_with_crlf_normalized(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            packet_hash = _record_packet(db_path)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/model-pass/ingest", method="POST",
                    fields={
                        "output": "line one\r\nline two\r\n",
                        "packet_hash": packet_hash,
                        "model": "Test Model",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(
                    headers["Location"], "/adjudication?run=1"
                )
            runs = _runs(db_path)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["packet_hash"], packet_hash)
            self.assertEqual(runs[0]["model_label"], "Test Model")
            # The stored output is the LF text the CLI's file ingest
            # would store — the paste's CRLF is normalized, nothing
            # else changes.
            self.assertEqual(runs[0]["raw_output"], "line one\nline two\n")

    def test_blank_model_is_recorded_as_not_stated(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            packet_hash = _record_packet(db_path)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + "/model-pass/ingest", method="POST",
                    fields={
                        "output": "some output",
                        "packet_hash": packet_hash,
                        "model": "",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 303)
            self.assertEqual(_runs(db_path)[0]["model_label"], "not stated")

    def test_unknown_packet_hash_is_refused_and_records_nothing(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/model-pass/ingest", method="POST",
                    fields={
                        "output": "some output",
                        "packet_hash": "0" * 64,
                        "model": "Test Model",
                        "date": "2026-11-19",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    f"no recorded packet with hash: {'0' * 64}", body
                )
            self.assertEqual(_runs(db_path), [])

    def test_second_ingest_creates_a_second_run(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            packet_hash = _record_packet(db_path)
            with Served(db_path) as base:
                for output in ("first output", "second output"):
                    status, headers, _ = _request(
                        base + "/model-pass/ingest", method="POST",
                        fields={
                            "output": output,
                            "packet_hash": packet_hash,
                            "model": "Test Model",
                            "date": "2026-11-19",
                        },
                    )
                    self.assertEqual(status, 303)
            runs = _runs(db_path)
            self.assertEqual([r["id"] for r in runs], [1, 2])
            self.assertEqual(
                [r["raw_output"] for r in runs],
                ["first output", "second output"],
            )


class AdjudicateTest(unittest.TestCase):
    def _db_with_run(self, tmp):
        db_path = _scratch_db(tmp)
        _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
        return db_path, run_id

    def test_accept_records_and_the_standing_shows(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + f"/run/{run_id}/adjudicate/coverage",
                    method="POST",
                    fields={
                        "decision": "accept", "note": "",
                        "date": "2026-11-19", "actor": "operator",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(
                    headers["Location"], f"/adjudication?run={run_id}"
                )
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                self.assertIn("Standing: <strong>accept</strong>", page)
            events = _adjudications(db_path, run_id)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["decision"], "accept")
            self.assertEqual(events[0]["section"], "coverage")

    def test_correct_without_a_note_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + f"/run/{run_id}/adjudicate/chains",
                    method="POST",
                    fields={
                        "decision": "correct", "note": "",
                        "date": "2026-11-19", "actor": "operator",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    "--decision correct requires --note;"
                    " the note is the correction, preserved in the record",
                    body,
                )
            self.assertEqual(_adjudications(db_path, run_id), [])

    def test_correct_with_a_note_records_the_note_verbatim(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + f"/run/{run_id}/adjudicate/fixes",
                    method="POST",
                    fields={
                        "decision": "correct",
                        "note": "F-1 cites the wrong rubric item.",
                        "date": "2026-11-19", "actor": "operator",
                    },
                )
                self.assertEqual(status, 303)
            events = _adjudications(db_path, run_id)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["decision"], "correct")
            self.assertEqual(
                events[0]["note"], "F-1 cites the wrong rubric item."
            )

    def test_readjudication_appends_and_standing_is_the_latest(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                for decision, note in (
                    ("accept", ""),
                    ("reject", "On reflection, the map is wrong."),
                ):
                    status, _, _ = _request(
                        base + f"/run/{run_id}/adjudicate/coverage",
                        method="POST",
                        fields={
                            "decision": decision, "note": note,
                            "date": "2026-11-19", "actor": "operator",
                        },
                    )
                    self.assertEqual(status, 303)
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                self.assertIn("Standing: <strong>reject</strong>", page)
                # The history shows both events, in record order.
                self.assertIn("accept", page)
                self.assertIn("On reflection, the map is wrong.", page)
            events = _adjudications(db_path, run_id)
            self.assertEqual(
                [e["decision"] for e in events], ["accept", "reject"]
            )

    def test_unknown_run_and_bad_values_are_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/run/999/adjudicate/coverage", method="POST",
                    fields={
                        "decision": "accept", "note": "",
                        "date": "2026-11-19", "actor": "operator",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("no such run: 999", body)
                status, _, body = _request(
                    base + f"/run/{run_id}/adjudicate/summary",
                    method="POST",
                    fields={
                        "decision": "accept", "note": "",
                        "date": "2026-11-19", "actor": "operator",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("section must be one of", body)
                status, _, body = _request(
                    base + f"/run/{run_id}/adjudicate/coverage",
                    method="POST",
                    fields={
                        "decision": "maybe", "note": "",
                        "date": "2026-11-19", "actor": "operator",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("decision must be one of", body)
            self.assertEqual(_adjudications(db_path, run_id), [])


class ChainTest(unittest.TestCase):
    def _db_with_run(self, tmp):
        db_path = _scratch_db(tmp)
        _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
        return db_path, run_id

    def _chain_fields(self, run_id, **overrides):
        fields = {
            "key": "A",
            "name": "Third-party app with tenant access",
            "control": "least-privilege consent grants",
            "control_status": "unknown",
            "control_rubric": "W-1.1",
            "steps": "access: the app is granted broad consent\n"
                     "use: the app reads the tenant directory",
            "run": str(run_id),
        }
        fields.update(overrides)
        return fields

    def test_valid_chain_lands_with_steps_in_order(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/chain/new", method="POST",
                    fields=self._chain_fields(run_id),
                )
                self.assertEqual(status, 303)
                self.assertEqual(
                    headers["Location"], f"/adjudication?run={run_id}"
                )
                # The applied chain is visible on the adjudication page.
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                self.assertIn("Third-party app with tenant access", page)
            store = Store(db_path)
            try:
                chains = store.list_chains()
            finally:
                store.close()
            self.assertEqual(len(chains), 1)
            self.assertEqual(chains[0]["chain_key"], "A")
            self.assertEqual(
                [(s["phase"], s["text"]) for s in chains[0]["steps"]],
                [
                    ("access", "the app is granted broad consent"),
                    ("use", "the app reads the tenant directory"),
                ],
            )
            self.assertEqual(chains[0]["control_rubric"], "W-1.1")

    def test_step_without_a_colon_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/chain/new", method="POST",
                    fields=self._chain_fields(
                        run_id, steps="access the app is granted consent"
                    ),
                )
                self.assertEqual(status, 400)
                # The refusal is HTML-escaped on the error page.
                self.assertIn(
                    "step must be &#x27;&lt;phase&gt;: &lt;text&gt;&#x27;:"
                    " access the app is granted consent",
                    body,
                )
            store = Store(db_path)
            try:
                self.assertEqual(store.list_chains(), [])
            finally:
                store.close()

    def test_duplicate_key_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                for _ in range(2):
                    status, _, body = _request(
                        base + "/chain/new", method="POST",
                        fields=self._chain_fields(run_id),
                    )
                self.assertEqual(status, 400)
                self.assertIn("duplicate chain key: A", body)
            store = Store(db_path)
            try:
                self.assertEqual(len(store.list_chains()), 1)
            finally:
                store.close()

    def test_unknown_control_rubric_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/chain/new", method="POST",
                    fields=self._chain_fields(
                        run_id, control_rubric="W-9.9"
                    ),
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    f"no such item in pack {PACK_ID}: W-9.9", body
                )

    def test_invalid_control_status_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/chain/new", method="POST",
                    fields=self._chain_fields(
                        run_id, control_status="maybe"
                    ),
                )
                self.assertEqual(status, 400)
                self.assertIn("control status must be one of", body)


class FixTest(unittest.TestCase):
    def _db_with_run(self, tmp):
        db_path = _scratch_db(tmp)
        _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
        return db_path, run_id

    def _fix_fields(self, run_id, **overrides):
        fields = {
            "id": "F-1",
            "action": "Enable phishing-resistant MFA.",
            "effort": "one hour",
            "breaks": "A",
            "rubric": ["W-1.1"],
            "date": "2026-11-19",
            "actor": "operator",
            "run": str(run_id),
        }
        fields.update(overrides)
        return fields

    def test_valid_fix_lands_proposed_with_citation(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/fix/new", method="POST",
                    fields=self._fix_fields(run_id),
                )
                self.assertEqual(status, 303)
                self.assertEqual(
                    headers["Location"], f"/adjudication?run={run_id}"
                )
                # The applied fix is visible on the adjudication page.
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                self.assertIn("Enable phishing-resistant MFA.", page)
            store = Store(db_path)
            try:
                fixes = store.list_fixes()
            finally:
                store.close()
            self.assertEqual(len(fixes), 1)
            self.assertEqual(fixes[0]["fix_id"], "F-1")
            self.assertEqual(fixes[0]["status"], "proposed")
            self.assertEqual(fixes[0]["rubric_item_ids"], ["W-1.1"])

    def test_duplicate_id_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                for _ in range(2):
                    status, _, body = _request(
                        base + "/fix/new", method="POST",
                        fields=self._fix_fields(run_id),
                    )
                self.assertEqual(status, 400)
                self.assertIn("duplicate fix id: F-1", body)
            store = Store(db_path)
            try:
                self.assertEqual(len(store.list_fixes()), 1)
            finally:
                store.close()

    def test_unknown_rubric_item_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path, run_id = self._db_with_run(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/fix/new", method="POST",
                    fields=self._fix_fields(
                        run_id, rubric=["W-9.9"]
                    ),
                )
                self.assertEqual(status, 400)
                self.assertIn(
                    f"no such item in pack {PACK_ID}: W-9.9", body
                )


class FixStatusTest(unittest.TestCase):
    def _db_with_fix(self, tmp):
        db_path = _scratch_db(tmp)
        store = Store(db_path)
        try:
            eng = store.get_engagement()
            store.add_fix(
                eng["id"], "F-1", "Enable phishing-resistant MFA.",
                "one hour", "A", ["W-1.1"], status="proposed",
                status_date="2026-11-19", status_actor="operator",
                rubric_pack_id="sample-wharf-2026",
            )
        finally:
            store.close()
        return db_path

    def test_transition_moves_the_fix_to_its_new_group(self):
        with TemporaryDirectory() as tmp:
            db_path = self._db_with_fix(tmp)
            with Served(db_path) as base:
                status, headers, _ = _request(
                    base + "/fix/F-1/status", method="POST",
                    fields={
                        "status": "approved",
                        "date": "2026-11-20", "actor": "operator",
                    },
                )
                self.assertEqual(status, 303)
                self.assertEqual(headers["Location"], "/fixes")
                status, _, page = _request(base + "/fixes")
                self.assertEqual(status, 200)
                self.assertIn("approved (1)", page)
                self.assertIn("proposed (0)", page)
                self.assertIn('id="fix-F-1"', page)
            store = Store(db_path)
            try:
                fixes = store.list_fixes()
            finally:
                store.close()
            self.assertEqual(fixes[0]["status"], "approved")
            self.assertEqual(fixes[0]["status_date"], "2026-11-20")

    def test_same_status_is_refused_with_the_store_message(self):
        with TemporaryDirectory() as tmp:
            db_path = self._db_with_fix(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/fix/F-1/status", method="POST",
                    fields={
                        "status": "proposed",
                        "date": "2026-11-20", "actor": "operator",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("fix F-1 is already proposed", body)
            store = Store(db_path)
            try:
                self.assertEqual(store.list_fixes()[0]["status"], "proposed")
            finally:
                store.close()

    def test_unknown_fix_is_refused(self):
        with TemporaryDirectory() as tmp:
            db_path = self._db_with_fix(tmp)
            with Served(db_path) as base:
                status, _, body = _request(
                    base + "/fix/F-9/status", method="POST",
                    fields={
                        "status": "done",
                        "date": "2026-11-20", "actor": "operator",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("no such fix: F-9", body)


class VerifyNextTest(unittest.TestCase):
    def test_legacy_text_seq_renders_escaped_and_keeps_appending(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
            store = Store(db_path)
            try:
                eng_id = store.get_engagement()["id"]
                store.add_verify_next(eng_id, "7", "Known item", "why", "check")
                self.assertIs(type(store.list_verify_next()[0]["seq"]), int)
                store.conn.execute(
                    "INSERT INTO verify_next"
                    " (engagement_id, seq, unknown_text, why, cheapest_check)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (eng_id, "<em>legacy</em>", "Legacy item", "why", "check"),
                )
                store.conn.commit()
                with Served(db_path) as base:
                    status, _, page = _request(base + f"/adjudication?run={run_id}")
                    self.assertEqual(status, 200)
                    self.assertIn("&lt;em&gt;legacy&lt;/em&gt;", page)
                    self.assertNotIn("<em>legacy</em>", page)
                    status, _, _ = _request(
                        base + "/verify-next/new", method="POST",
                        fields={"unknown": "New item", "why": "why", "check": "check"},
                    )
                    self.assertEqual(status, 303)
                self.assertEqual(
                    [item["seq"] for item in store.list_verify_next()],
                    [7, 8, "<em>legacy</em>"],
                )
            finally:
                store.close()

    def test_two_adds_take_sequences_1_and_2(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
            with Served(db_path) as base:
                for unknown, why, check in (
                    (
                        "Sign-in log retention",
                        "The advisory lookback exceeds retention",
                        "Export the sign-in logs",
                    ),
                    (
                        "DKIM signing status",
                        "Never recorded for the domain",
                        "Check the DNS records",
                    ),
                ):
                    status, headers, _ = _request(
                        base + "/verify-next/new", method="POST",
                        fields={
                            "unknown": unknown, "why": why,
                            "check": check, "run": str(run_id),
                        },
                    )
                    self.assertEqual(status, 303)
                    self.assertEqual(
                        headers["Location"], f"/adjudication?run={run_id}"
                    )
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                self.assertIn("Sign-in log retention", page)
                self.assertIn("DKIM signing status", page)
                # The items also render in the report.
                status, _, report = _request(base + "/report")
                self.assertEqual(status, 200)
                self.assertIn("Sign-in log retention", report)
                self.assertIn("DKIM signing status", report)
            store = Store(db_path)
            try:
                items = store.list_verify_next()
            finally:
                store.close()
            self.assertEqual([i["seq"] for i in items], [1, 2])


class PagesTest(unittest.TestCase):
    def test_model_pass_page_shows_packet_card_forms_and_runs(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            packet_hash, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
            with Served(db_path) as base:
                status, _, page = _request(base + "/model-pass")
                self.assertEqual(status, 200)
                self.assertIn("Latest packet", page)
                self.assertIn(packet_hash, page)
                self.assertIn('action="/model-pass/packet"', page)
                self.assertIn('action="/model-pass/ingest"', page)
                self.assertIn("Test Model", page)
                self.assertIn(
                    f'href="/adjudication?run={run_id}"', page
                )

    def test_model_pass_page_with_nothing_recorded(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, page = _request(base + "/model-pass")
                self.assertEqual(status, 200)
                self.assertIn("No packet has been assembled yet.", page)
                self.assertIn("No runs recorded yet.", page)

    def test_adjudication_page_with_no_runs(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, page = _request(base + "/adjudication")
                self.assertEqual(status, 200)
                self.assertIn("No runs recorded yet.", page)
                self.assertIn('href="/model-pass"', page)

    def test_adjudication_page_shows_the_four_sections(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
            with Served(db_path) as base:
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                for heading in (
                    "Coverage map", "Attack chains",
                    "Fix list", "Verify-next list",
                ):
                    self.assertIn(f"<h2>{heading}</h2>", page)
                # Every section's lines verbatim, plus the stub.
                self.assertIn("- W-1.1 Covered, cites A2.", page)
                self.assertIn("- Chain A breaks at W-1.1.", page)
                self.assertIn("&gt; **Adjudication**", page)
                # One decision form per section, no decision yet.
                self.assertEqual(
                    page.count(
                        f'action="/run/{run_id}/adjudicate/'
                    ),
                    4,
                )
                self.assertEqual(
                    page.count("no decision recorded"), 4
                )
                # The apply forms are on the page too.
                self.assertIn('action="/chain/new"', page)
                self.assertIn('action="/fix/new"', page)
                self.assertIn('action="/verify-next/new"', page)
                # The rail counts four undecided sections, in amber.
                self.assertIn(
                    'Adjudication <span class="mono signal">(4)</span>',
                    page,
                )

    def test_adjudication_defaults_to_the_latest_run(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _, first = _record_run(db_path, FOUR_SECTION_OUTPUT)
            _, second = _record_run(db_path, "Second run output.")
            with Served(db_path) as base:
                status, _, page = _request(base + "/adjudication")
                self.assertEqual(status, 200)
                self.assertIn("Second run output.", page)
                self.assertNotIn("- W-1.1 Covered, cites A2.", page)
                # The run selector links to the earlier run.
                self.assertIn(
                    f'href="/adjudication?run={first}"', page
                )
                self.assertEqual(second, 2)

    def test_unsectioned_run_shows_one_block_and_four_forms(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _, run_id = _record_run(db_path, UNSECTIONED_OUTPUT)
            with Served(db_path) as base:
                status, _, page = _request(
                    base + f"/adjudication?run={run_id}"
                )
                self.assertEqual(status, 200)
                self.assertIn("<h2>Unsectioned output</h2>", page)
                self.assertIn("Free-form notes.", page)
                self.assertIn("Nothing sectioned here.", page)
                self.assertEqual(
                    page.count(
                        f'action="/run/{run_id}/adjudicate/'
                    ),
                    4,
                )
                for label in (
                    "Coverage", "Chains", "Fixes", "Verify-next",
                ):
                    self.assertIn(f"<h3>{label}</h3>", page)

    def test_fixes_page_groups_by_status_with_none_under_empties(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            store = Store(db_path)
            try:
                eng = store.get_engagement()
                store.add_fix(
                    eng["id"], "F-1", "Enable phishing-resistant MFA.",
                    "one hour", "A", ["W-1.1"], status="proposed",
                    status_date="2026-11-19", status_actor="operator",
                    rubric_pack_id="sample-wharf-2026",
                )
            finally:
                store.close()
            with Served(db_path) as base:
                status, _, page = _request(base + "/fixes")
                self.assertEqual(status, 200)
                self.assertIn("<h2>proposed (1)</h2>", page)
                self.assertIn("<h2>approved (0)</h2>", page)
                self.assertIn("<h2>done (0)</h2>", page)
                self.assertIn("<h2>deferred (0)</h2>", page)
                self.assertEqual(page.count("None.</p>"), 3)
                self.assertIn('id="fix-F-1"', page)
                self.assertIn('href="/coverage#item-W-1.1"', page)
                self.assertIn('action="/fix/F-1/status"', page)

    def test_rail_carries_the_three_new_items(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                status, _, page = _request(base + "/")
                self.assertEqual(status, 200)
                for href, label in (
                    ("/model-pass", "Model pass"),
                    ("/adjudication", "Adjudication"),
                    ("/fixes", "Fixes"),
                ):
                    self.assertIn(f'href="{href}"', page)
                    self.assertIn(f">{label}", page)
                # No runs yet: no Adjudication count is shown.
                self.assertNotIn("Adjudication <span", page)


class PurityAndFencesTest(unittest.TestCase):
    def test_full_get_crawl_leaves_the_database_byte_identical(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _record_run(db_path, FOUR_SECTION_OUTPUT)
            before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            with Served(db_path) as base:
                for path in (
                    "/", "/inventory", "/checklist", "/coverage",
                    "/model-pass", "/adjudication",
                    "/adjudication?run=1", "/fixes", "/report",
                    "/report.md",
                ):
                    status, _, _ = _request(base + path)
                    self.assertEqual(status, 200, path)
            after = hashlib.sha256(db_path.read_bytes()).hexdigest()
            self.assertEqual(before, after)

    def test_post_to_a_read_page_is_still_405(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as base:
                for path in ("/model-pass", "/adjudication", "/fixes"):
                    status, headers, _ = _request(
                        base + path, method="POST", fields={}
                    )
                    self.assertEqual(status, 405, path)
                    self.assertEqual(headers["Allow"], "GET, HEAD")

    def test_mismatched_origin_on_a_new_route_writes_nothing(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            _, run_id = _record_run(db_path, FOUR_SECTION_OUTPUT)
            with Served(db_path) as base:
                status, _, _ = _request(
                    base + "/fix/new", method="POST",
                    fields={
                        "id": "F-1", "action": "Do a thing.",
                        "effort": "one hour", "breaks": "A",
                        "date": "2026-11-19", "actor": "operator",
                        "run": str(run_id),
                    },
                    headers={"Origin": "http://evil.example"},
                )
                self.assertEqual(status, 403)
            store = Store(db_path)
            try:
                self.assertEqual(store.list_fixes(), [])
            finally:
                store.close()

    def test_serve_help_no_longer_claims_read_only(self):
        from fencewalk.__main__ import build_parser

        help_text = build_parser().format_help()
        # The serve subcommand's own line — other subcommands
        # legitimately carry "(read-only)" in their help.
        self.assertNotIn("serve the read-only web interface", help_text)
        self.assertIn(
            "serve               serve the web interface for one"
            " engagement database",
            help_text,
        )


if __name__ == "__main__":
    unittest.main()
