"""API model pass tests: `run-model` against a local stub Anthropic
server (stdlib http.server, ephemeral port, in a thread). No live API
key is used anywhere here: the key the tests present is the visibly
fake "test-key", and the stub stands in for api.anthropic.com.

The stub and its canned response live in this test file only, never
in shipped code. The shipped driver takes its base URL as a
parameter (defaulting to the real API); the command function takes
the driver as an optional parameter (`_call`) — that is the seam
these tests use, plus one test through main() with the module-level
dispatch patched.
"""

import difflib
import hashlib
import io
import json
import os
import shlex
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from fencewalk.__main__ import build_parser, cmd_run_model, main
from fencewalk.model_api import call_anthropic
from fencewalk.packet import assemble_packet
from fencewalk.report import render_report
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"
EXPECTED_REPORT = FIXTURE_DIR / "EXPECTED-REPORT.md"

# The pristine fixture packet (18,732 bytes) is the packet assembled
# 2026-11-05 — the fixture's own date. The date string is fixed-width,
# so the byte count holds for any date; the hash pins the date.
ASSEMBLED = "2026-11-05"
PRISTINE_BYTES = 18732
PRISTINE_SHA256 = (
    "e59fc847d218018aa9035dda9fa0ee47269cef1927a27d153c78ae59e7a646d7"
)
MODEL = "test-model"
MODEL_LABEL = f"anthropic/{MODEL}"
FAKE_KEY = "test-key"  # visibly fake; never a real credential

CANNED_RESPONSE = {
    "id": "msg_stub01",
    "type": "message",
    "role": "assistant",
    "content": [
        {"type": "text", "text": "## Coverage map\n\nR-1.4 Partial — stub.\n"},
        {"type": "text", "text": "\n## Attack chains\n\nNone in this stub.\n"},
    ],
    "model": MODEL,
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 1234, "output_tokens": 56},
}
CANNED_TEXT = "".join(b["text"] for b in CANNED_RESPONSE["content"])

API_SENTENCE = (
    "Fencewalk called the provider API on the operator's behalf"
    " with the operator's key; the output is recorded as a model run"
    " when the operator ingests it."
)
MANUAL_SENTENCE = (
    "The operator runs this packet in their own model session;"
    " Fencewalk does not call a model API."
)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def printed_value(stdout, label):
    for line in stdout.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    raise AssertionError(f"no '{label}' line in output: {stdout!r}")


class StubAnthropicHandler(BaseHTTPRequestHandler):
    """Records each request on the server; answers with the server's
    canned status and body. Never logs the key (or anything)."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        self.server.requests.append({
            "path": self.path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": raw,
        })
        payload = json.dumps(self.server.response_body).encode("utf-8")
        self.send_response(self.server.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class FixtureDbTestCase(unittest.TestCase):
    """Base: the reference fixture loaded into a temp database."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "ref.db")
        code, _, err = run_cli(["load-fixture", str(FIXTURE_DIR), self.db])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()


class StubServerTestCase(FixtureDbTestCase):
    """Base plus a stub Anthropic server and a fake key in the env."""

    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), StubAnthropicHandler
        )
        self.server.requests = []
        self.server.response_status = 200
        self.server.response_body = CANNED_RESPONSE
        self.stub_url = (
            f"http://127.0.0.1:{self.server.server_address[1]}"
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        key_patcher = mock.patch.dict(
            os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY}
        )
        key_patcher.start()
        self.addCleanup(key_patcher.stop)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def stub_call(self, provider, model, packet_text, api_key, max_tokens):
        """The real driver, pointed at the stub: the _call seam."""
        return call_anthropic(
            model, packet_text, api_key, max_tokens,
            base_url=self.stub_url,
        )

    def run_model(self, *extra, call=None):
        """Run run-model the way main() would, with the driver
        parameterised. Returns (code, stdout, stderr); driver and
        CLI errors are reported exactly as main() reports them."""
        out_path = str(Path(self.tmp.name) / "model-output.md")
        argv = [
            "run-model", self.db, "--provider", "anthropic",
            "--model", MODEL, "--out", out_path, "--date", ASSEMBLED,
        ]
        argv += list(extra)
        args = build_parser().parse_args(argv)
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = cmd_run_model(args, _call=call)
        except (ValueError, OSError, sqlite3.Error) as exc:
            code = 1
            err.write(f"error: {exc}\n")
        return code, out.getvalue(), err.getvalue(), out_path


class PacketSentenceTest(FixtureDbTestCase):
    def test_manual_packet_is_the_pristine_packet(self):
        text, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED
        )
        data = text.encode("utf-8")
        self.assertEqual(len(data), PRISTINE_BYTES)
        self.assertEqual(hashlib.sha256(data).hexdigest(), PRISTINE_SHA256)
        self.assertIn(MANUAL_SENTENCE, text)
        self.assertNotIn("Run via:", text)
        # And end to end through the packet command.
        out_path = str(Path(self.tmp.name) / "packet.md")
        code, out, err = run_cli([
            "packet", self.db, "--out", out_path, "--date", ASSEMBLED,
        ])
        self.assertEqual(code, 0, err)
        file_bytes = Path(out_path).read_bytes()
        self.assertEqual(len(file_bytes), PRISTINE_BYTES)
        self.assertEqual(
            hashlib.sha256(file_bytes).hexdigest(), PRISTINE_SHA256
        )
        self.assertEqual(printed_value(out, "sha256:"), PRISTINE_SHA256)

    def test_api_packet_differs_only_where_the_brief_says(self):
        manual, _ = assemble_packet(self.db, assembled_date=ASSEMBLED)
        api, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=MODEL_LABEL,
        )
        self.assertIn(f"- Run via: {MODEL_LABEL}", api)
        self.assertIn(API_SENTENCE, api)
        self.assertNotIn(MANUAL_SENTENCE, api)
        ops = difflib.SequenceMatcher(
            None, manual.splitlines(), api.splitlines()
        ).get_opcodes()
        kinds = [tag for tag, _, _, _, _ in ops]
        self.assertEqual(kinds, ["equal", "insert", "equal", "replace", "equal"])
        inserted = [
            api.splitlines()[j]
            for tag, _, _, j1, j2 in ops if tag == "insert"
            for j in range(j1, j2)
        ]
        self.assertEqual(inserted, [f"- Run via: {MODEL_LABEL}"])
        replaced = [
            (manual.splitlines()[i], api.splitlines()[j])
            for tag, i1, i2, j1, j2 in ops if tag == "replace"
            for i, j in zip(range(i1, i2), range(j1, j2))
        ]
        self.assertEqual(len(replaced), 1)
        old_line, new_line = replaced[0]
        self.assertIn(MANUAL_SENTENCE, old_line)
        self.assertIn(API_SENTENCE, new_line)

    def test_api_session_sentence_defers_the_run_to_ingest(self):
        # 0.3.5: run-model records no run, so the API packet's
        # session sentence says the output becomes a model run when
        # the operator ingests it. The insertion is 29 bytes; the
        # measured counts with claude-opus-5-5 are 18,826 for the
        # pristine fixture and 18,827 with E5 resolved (the
        # walkthrough state). The manual packet does not move.
        label = "anthropic/claude-opus-5-5"
        old_sentence = (
            "Fencewalk called the provider API on the operator's behalf"
            " with the operator's key; the output is recorded as a model"
            " run."
        )
        self.assertEqual(
            len(API_SENTENCE.encode("utf-8"))
            - len(old_sentence.encode("utf-8")),
            len(" when the operator ingests it".encode("utf-8")),
        )
        self.assertEqual(len(" when the operator ingests it"), 29)
        api, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=label,
        )
        self.assertIn(API_SENTENCE, api)
        self.assertNotIn(old_sentence, api)
        self.assertEqual(len(api.encode("utf-8")), 18826)
        store = Store(self.db)
        try:
            store.set_entry_label(
                "E5", "VERIFIED", date=ASSEMBLED, actor="operator"
            )
        finally:
            store.close()
        api_walk, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=label,
        )
        self.assertEqual(len(api_walk.encode("utf-8")), 18827)
        manual_walk, _ = assemble_packet(self.db, assembled_date=ASSEMBLED)
        self.assertEqual(len(manual_walk.encode("utf-8")), PRISTINE_BYTES + 1)


class DriverStubTest(StubServerTestCase):
    def test_request_shape_and_response_parsing(self):
        api_text, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=MODEL_LABEL,
        )
        text, in_tokens, out_tokens, skipped = call_anthropic(
            MODEL, api_text, FAKE_KEY, 16384, base_url=self.stub_url
        )
        self.assertEqual(text, CANNED_TEXT)
        self.assertEqual((in_tokens, out_tokens), (1234, 56))
        self.assertEqual(skipped, 0)
        self.assertEqual(len(self.server.requests), 1)
        req = self.server.requests[0]
        self.assertEqual(req["path"], "/v1/messages")
        self.assertEqual(req["headers"]["x-api-key"], FAKE_KEY)
        self.assertEqual(req["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(
            req["headers"]["content-type"], "application/json"
        )
        body = json.loads(req["body"].decode("utf-8"))
        self.assertEqual(body["model"], MODEL)
        self.assertEqual(body["max_tokens"], 16384)
        self.assertEqual(len(body["messages"]), 1)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertEqual(body["messages"][0]["content"], api_text)

    def test_non_text_content_block_is_an_error(self):
        self.server.response_body = {
            "id": "msg_stub02", "type": "message", "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "x"}],
            "model": MODEL, "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        with self.assertRaises(ValueError) as ctx:
            call_anthropic(
                MODEL, "packet", FAKE_KEY, 16384, base_url=self.stub_url
            )
        self.assertIn("unexpected model response", str(ctx.exception))
        self.assertIn("non-text", str(ctx.exception))


class RunModelCommandTest(StubServerTestCase):
    def test_full_command_path_then_ingest(self):
        code, out, err, out_path = self.run_model(call=self.stub_call)
        self.assertEqual(code, 0, err)
        self.assertEqual(
            Path(out_path).read_bytes(), CANNED_TEXT.encode("utf-8")
        )
        sha = printed_value(out, "packet sha256:")
        api_text, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=MODEL_LABEL,
        )
        self.assertEqual(
            sha, hashlib.sha256(api_text.encode("utf-8")).hexdigest()
        )
        self.assertIn("input tokens: 1234", out)
        self.assertIn("output tokens: 56", out)
        self.assertNotIn("note:", out)
        ingest_line = next(
            line for line in out.splitlines()
            if line.startswith("fencewalk ingest ")
        )
        self.assertEqual(
            ingest_line,
            f"fencewalk ingest {self.db} {out_path}"
            f" --packet-hash {sha} --model {MODEL_LABEL}",
        )
        with Store(self.db) as store:
            packet = store.get_packet_by_hash(sha)
            self.assertIsNotNone(packet)
            self.assertEqual(packet["pack_id"], "flash-20261113-001")
            self.assertEqual(store.list_runs(), [])
        # The printed invocation works for real, and the run holds
        # the canned text verbatim under the same packet hash.
        code, out, err = run_cli(shlex.split(ingest_line)[1:])
        self.assertEqual(code, 0, err)
        self.assertIn("ingested model run 1", out)
        with Store(self.db) as store:
            run = store.get_run(1)
        self.assertEqual(run["raw_output"], CANNED_TEXT)
        self.assertEqual(run["packet_hash"], sha)
        self.assertEqual(run["model_label"], MODEL_LABEL)

    def test_thinking_block_interleaved_is_skipped(self):
        first = "## Coverage map\n\nR-1.4 Partial — stub.\n"
        second = "\n## Attack chains\n\nNone in this stub.\n"
        self.server.response_body = {
            "id": "msg_stub03", "type": "message", "role": "assistant",
            "content": [
                {"type": "text", "text": first},
                {
                    "type": "thinking",
                    "thinking": "internal reasoning",
                    "signature": "stub-signature",
                },
                {"type": "text", "text": second},
            ],
            "model": MODEL, "stop_reason": "end_turn",
            "usage": {"input_tokens": 1234, "output_tokens": 99},
        }
        code, out, err, out_path = self.run_model(call=self.stub_call)
        self.assertEqual(code, 0, err)
        self.assertEqual(
            Path(out_path).read_bytes(),
            (first + second).encode("utf-8"),
        )
        self.assertIn("note: skipped 1 thinking block\n", out)
        self.assertIn("input tokens: 1234", out)
        self.assertIn("output tokens: 99", out)
        ingest_line = next(
            line for line in out.splitlines()
            if line.startswith("fencewalk ingest ")
        )
        code, out, err = run_cli(shlex.split(ingest_line)[1:])
        self.assertEqual(code, 0, err)
        self.assertIn("ingested model run 1", out)
        with Store(self.db) as store:
            run = store.get_run(1)
        self.assertEqual(run["raw_output"], first + second)
        self.assertEqual(run["model_label"], MODEL_LABEL)

    def test_redacted_thinking_block_is_skipped_and_counted(self):
        first = "## Coverage map\n\nR-1.4 Partial — stub.\n"
        second = "\n## Attack chains\n\nNone in this stub.\n"
        self.server.response_body = {
            "id": "msg_stub04", "type": "message", "role": "assistant",
            "content": [
                {"type": "text", "text": first},
                {
                    "type": "thinking",
                    "thinking": "internal reasoning",
                    "signature": "stub-signature",
                },
                {"type": "redacted_thinking", "data": "redacted"},
                {"type": "text", "text": second},
            ],
            "model": MODEL, "stop_reason": "end_turn",
            "usage": {"input_tokens": 1234, "output_tokens": 77},
        }
        code, out, err, out_path = self.run_model(call=self.stub_call)
        self.assertEqual(code, 0, err)
        self.assertEqual(
            Path(out_path).read_bytes(),
            (first + second).encode("utf-8"),
        )
        # thinking and redacted_thinking count together, one wording.
        self.assertIn("note: skipped 2 thinking blocks\n", out)

    def test_thinking_only_response_is_an_error_with_no_output(self):
        self.server.response_body = {
            "id": "msg_stub05", "type": "message", "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "internal reasoning",
                    "signature": "stub-signature",
                },
            ],
            "model": MODEL, "stop_reason": "end_turn",
            "usage": {"input_tokens": 1234, "output_tokens": 10},
        }
        code, out, err, out_path = self.run_model(call=self.stub_call)
        self.assertEqual(code, 1)
        self.assertEqual(
            err, "error: unexpected model response: no text content\n"
        )
        self.assertFalse(Path(out_path).exists())

    def _truncation_case(self, body, expected_err):
        self.server.response_body = body
        code, out, err, out_path = self.run_model(call=self.stub_call)
        self.assertEqual(code, 1)
        self.assertEqual(err, expected_err)
        self.assertNotIn("model output written", out)
        self.assertFalse(Path(out_path).exists())
        with Store(self.db) as store:
            self.assertEqual(store.list_runs(), [])

    def test_max_tokens_stop_reason_is_refused(self):
        body = dict(CANNED_RESPONSE, stop_reason="max_tokens")
        self._truncation_case(
            body,
            "error: unexpected model response: stop_reason is max_tokens,"
            " not end_turn\n",
        )

    def test_other_stop_reasons_are_refused(self):
        for value in ("stop_sequence", "tool_use", "refusal", None):
            with self.subTest(stop_reason=value):
                body = dict(CANNED_RESPONSE, stop_reason=value)
                self._truncation_case(
                    body,
                    f"error: unexpected model response: stop_reason is"
                    f" {value}, not end_turn\n",
                )

    def test_missing_stop_reason_is_refused(self):
        body = {
            k: v for k, v in CANNED_RESPONSE.items() if k != "stop_reason"
        }
        self._truncation_case(
            body, "error: unexpected model response: missing stop_reason\n"
        )

    def test_end_turn_is_accepted_unchanged(self):
        self.assertEqual(CANNED_RESPONSE["stop_reason"], "end_turn")
        code, out, err, out_path = self.run_model(call=self.stub_call)
        self.assertEqual(code, 0, err)
        self.assertEqual(
            Path(out_path).read_bytes(), CANNED_TEXT.encode("utf-8")
        )

    def test_provider_errors_have_no_output_no_run_no_retry(self):
        api_text, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=MODEL_LABEL,
        )
        expected_sha = hashlib.sha256(api_text.encode("utf-8")).hexdigest()
        for status in (400, 429, 500):
            with self.subTest(status=status):
                self.server.response_status = status
                self.server.response_body = {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": f"stub error {status}",
                    },
                }
                self.server.requests = []
                code, out, err, out_path = self.run_model(
                    call=self.stub_call
                )
                self.assertEqual(code, 1)
                self.assertIn(str(status), err)
                self.assertFalse(Path(out_path).exists())
                with Store(self.db) as store:
                    self.assertEqual(store.list_runs(), [])
                    # The packet record stands: the packet was
                    # recorded before the call, as if the operator
                    # had assembled a packet and never run it.
                    self.assertIsNotNone(
                        store.get_packet_by_hash(expected_sha)
                    )
                self.assertEqual(len(self.server.requests), 1)

    def test_usage_printed(self):
        code, out, err, _ = self.run_model(call=self.stub_call)
        self.assertEqual(code, 0, err)
        self.assertIn("input tokens: 1234", out)
        self.assertIn("output tokens: 56", out)


class RunModelCliErrorsTest(FixtureDbTestCase):
    def test_missing_key_fails_before_anything(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            out_path = str(Path(self.tmp.name) / "model-output.md")
            code, out, err = run_cli([
                "run-model", self.db, "--provider", "anthropic",
                "--model", MODEL, "--out", out_path,
                "--date", ASSEMBLED,
            ])
        self.assertEqual(code, 1)
        self.assertEqual(err, "error: ANTHROPIC_API_KEY is not set\n")
        self.assertFalse(Path(out_path).exists())
        with Store(self.db) as store:
            self.assertEqual(store.list_packets(), [])

    def test_unknown_provider(self):
        out_path = str(Path(self.tmp.name) / "model-output.md")
        code, _, err = run_cli([
            "run-model", self.db, "--provider", "nope",
            "--model", MODEL, "--out", out_path, "--date", ASSEMBLED,
        ])
        self.assertEqual(code, 1)
        self.assertEqual(err, "error: unknown provider: nope\n")
        self.assertFalse(Path(out_path).exists())

    def test_dry_run_sends_nothing_writes_nothing_records_nothing(self):
        # Dry-run needs no key: it verifies what would leave the
        # machine before the operator sets one up.
        with mock.patch.dict(os.environ):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            out_path = str(Path(self.tmp.name) / "model-output.md")
            code, out, err = run_cli([
                "run-model", self.db, "--provider", "anthropic",
                "--model", MODEL, "--out", out_path,
                "--date", ASSEMBLED, "--dry-run",
            ])
        self.assertEqual(code, 0, err)
        self.assertIn(
            "url: https://api.anthropic.com/v1/messages", out
        )
        self.assertIn(f"model: {MODEL}", out)
        self.assertIn("max_tokens: 16384", out)
        api_text, _ = assemble_packet(
            self.db, assembled_date=ASSEMBLED,
            run_via="api", model_label=MODEL_LABEL,
        )
        data = api_text.encode("utf-8")
        self.assertIn(f"packet byte count: {len(data)}", out)
        self.assertIn(
            f"packet sha256: {hashlib.sha256(data).hexdigest()}", out
        )
        self.assertIn("headers: x-api-key, anthropic-version", out)
        self.assertNotIn(FAKE_KEY, out)
        self.assertFalse(Path(out_path).exists())
        with Store(self.db) as store:
            self.assertEqual(store.list_packets(), [])


class NoBehaviourChangeTest(FixtureDbTestCase):
    def test_golden_render_byte_identical(self):
        text = render_report(self.db)
        self.assertEqual(
            text.encode("utf-8"),
            EXPECTED_REPORT.read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
