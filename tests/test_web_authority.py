"""Web interface authority checks: Host validation and the write token.

Three layers protect the local server. Layer 1 refuses any request
whose Host header does not name this server (the bind host or a
loopback name, on the bound port) — this is what defeats DNS
rebinding, where a hostile page's own name resolves to 127.0.0.1.
Layer 2 is the existing Origin/Referer check, now run against a
Host that layer 1 has validated. Layer 3 is a per-process token that
every write form carries and every POST must present.
"""

import http.client
import re
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

from fencewalk.fixture import load_pack, validate_pack
from fencewalk.store import Store
from fencewalk.web import _host_allowed, _inject_token, create_server

SAMPLE_PACK_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "sample-pack.json"
)

MARKER = "The harbour log is kept daily."


def _scratch_db(tmp):
    db_path = Path(tmp) / "eng.db"
    store = Store(db_path)
    try:
        store.init_schema()
        eng_id = store.create_engagement(
            "Authority test engagement", "A test firm",
            "2026-11-18", "verify-first",
        )
        store.add_inventory_entry(
            eng_id, "A1", "A", "The gate latch is fitted.", "UNKNOWN",
            "site visit notes", date="2026-11-18", actor="tester",
        )
        store.add_inventory_entry(
            eng_id, "A2", "A", MARKER, "ON RECORD",
            "log inspection", date="2026-11-18", actor="tester",
        )
        store.add_pack(validate_pack(load_pack(SAMPLE_PACK_PATH)))
    finally:
        store.close()
    return db_path


def _label(db_path, entry_id):
    store = Store(db_path)
    try:
        for e in store.list_inventory():
            if e["entry_id"] == entry_id:
                return e["label"]
        return None
    finally:
        store.close()


class Served:
    def __init__(self, db_path, bind="127.0.0.1"):
        self.server = create_server(str(db_path), bind, 0)
        self.port = self.server.server_address[1]
        self.token = self.server.write_token
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, host=None, headers=None, fields=None,
                skip_host=False):
        """Send one request with an exact Host header (or none)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            body = None
            if fields is not None:
                body = urlencode(fields).encode("utf-8")
            conn.putrequest(method, path, skip_host=True)
            if not skip_host:
                conn.putheader(
                    "Host", host if host is not None
                    else f"127.0.0.1:{self.port}"
                )
            for key, value in (headers or {}).items():
                conn.putheader(key, value)
            if body is not None:
                conn.putheader(
                    "Content-Type", "application/x-www-form-urlencoded"
                )
                conn.putheader("Content-Length", str(len(body)))
            else:
                conn.putheader("Content-Length", "0")
            conn.endheaders(body)
            resp = conn.getresponse()
            self.last_headers = resp.getheaders()
            return resp.status, resp.read().decode("utf-8")
        finally:
            conn.close()

    def header_values(self, name):
        """Every value of one header on the last response."""
        return [
            value for key, value in self.last_headers
            if key.lower() == name.lower()
        ]


class HostValidationTest(unittest.TestCase):
    def test_foreign_host_get_is_refused_with_no_inventory_data(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                for path in ("/", "/inventory", "/report", "/report.md"):
                    status, body = s.request(
                        "GET", path, host=f"evil.example:{s.port}"
                    )
                    self.assertEqual(status, 403, path)
                    self.assertNotIn("harbour", body, path)
                    self.assertNotIn("A2", body, path)
                status, body = s.request("GET", "/", host="evil.example")
                self.assertEqual(status, 403)
                self.assertNotIn("harbour", body)

    def test_foreign_host_head_and_put_are_refused(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                status, _ = s.request("HEAD", "/", host="evil.example")
                self.assertEqual(status, 403)
                status, _ = s.request("PUT", "/", host="evil.example")
                self.assertEqual(status, 403)

    def test_foreign_host_post_is_refused_and_writes_nothing(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                status, _ = s.request(
                    "POST", "/entry/A2/label", host="evil.example",
                    fields={"label": "UNKNOWN", "token": s.token},
                )
                self.assertEqual(status, 403)
            self.assertEqual(_label(db_path, "A2"), "ON RECORD")

    def test_matching_attacker_host_and_origin_is_refused(self):
        # The rebinding shape: Origin matches Host, both foreign.
        # Layer 1 kills it even though the origin check would pass.
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                for host in ("evil.example", f"evil.example:{s.port}"):
                    status, _ = s.request(
                        "POST", "/entry/A2/label", host=host,
                        headers={"Origin": f"http://{host}"},
                        fields={"label": "UNKNOWN", "token": s.token},
                    )
                    self.assertEqual(status, 403, host)
            self.assertEqual(_label(db_path, "A2"), "ON RECORD")

    def test_wrong_port_and_missing_host_are_refused(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                other = s.port + 1 if s.port < 65535 else s.port - 1
                status, _ = s.request("GET", "/", host=f"127.0.0.1:{other}")
                self.assertEqual(status, 403)
                status, _ = s.request("GET", "/", host="127.0.0.1")
                self.assertEqual(status, 403)
                status, _ = s.request("GET", "/", skip_host=True)
                self.assertEqual(status, 403)

    def test_loopback_hosts_are_served(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                for host in (f"127.0.0.1:{s.port}", f"localhost:{s.port}",
                             f"LOCALHOST:{s.port}"):
                    status, body = s.request("GET", "/inventory", host=host)
                    self.assertEqual(status, 200, host)
                    self.assertIn("harbour", body, host)


class FramingHeadersTest(unittest.TestCase):
    """No response may be framed: a framed write form is one tricked
    click from a same-origin submission that carries the token."""

    def assert_unframeable(self, s, label):
        self.assertEqual(s.header_values("X-Frame-Options"), ["DENY"], label)
        self.assertEqual(
            s.header_values("Content-Security-Policy"),
            ["frame-ancestors 'none'"], label,
        )

    def test_every_response_carries_both_framing_headers(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                status, _ = s.request("GET", "/")
                self.assertEqual(status, 200)
                self.assert_unframeable(s, "GET / 200")
                # A page whose forms carry the write token — the page
                # a hostile frame would want.
                status, body = s.request("GET", "/checklist")
                self.assertEqual(status, 200)
                self.assertIn(f'name="token" value="{s.token}"', body)
                self.assert_unframeable(s, "GET /checklist 200")

                status, _ = s.request(
                    "GET", "/", host=f"evil.example:{s.port}"
                )
                self.assertEqual(status, 403)
                self.assert_unframeable(s, "foreign-Host GET 403")

                status, _ = s.request(
                    "POST", "/inventory",
                    headers={"Origin": f"http://127.0.0.1:{s.port}"},
                    fields={"token": s.token},
                )
                self.assertEqual(status, 405)
                self.assert_unframeable(s, "POST read-only route 405")

    def test_other_statuses_carry_them_too(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                origin = {"Origin": f"http://127.0.0.1:{s.port}"}
                cases = (
                    (404, "GET", "/no-such-page", None, None),
                    (200, "GET", "/report.md", None, None),
                    (200, "HEAD", "/", None, None),
                    (405, "PUT", "/", None, None),
                    (403, "POST", "/entry/A2/label", origin,
                     {"label": "UNKNOWN"}),
                    (403, "POST", "/entry/A2/label",
                     {"Origin": "http://evil.example"},
                     {"label": "UNKNOWN", "token": s.token}),
                    (400, "POST", "/entry/A2/label", origin,
                     {"label": "NOT-A-LABEL", "token": s.token}),
                    (303, "POST", "/entry/A2/label", origin,
                     {"label": "UNKNOWN", "token": s.token}),
                )
                for want, method, path, headers, fields in cases:
                    label = f"{method} {path} {want}"
                    status, _ = s.request(
                        method, path, headers=headers, fields=fields
                    )
                    self.assertEqual(status, want, label)
                    self.assert_unframeable(s, label)


class WildcardBindTest(unittest.TestCase):
    """A wildcard bind answers loopback names only (README)."""

    def test_wildcard_bound_server_refuses_its_own_wildcard_name(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path, bind="0.0.0.0") as s:
                status, body = s.request(
                    "GET", "/inventory", host=f"0.0.0.0:{s.port}"
                )
                self.assertEqual(status, 403)
                self.assertNotIn("harbour", body)
                status, _ = s.request(
                    "POST", "/entry/A2/label", host=f"0.0.0.0:{s.port}",
                    headers={"Origin": f"http://0.0.0.0:{s.port}"},
                    fields={"label": "UNKNOWN", "token": s.token},
                )
                self.assertEqual(status, 403)
                for host in (f"127.0.0.1:{s.port}", f"localhost:{s.port}"):
                    status, body = s.request("GET", "/inventory", host=host)
                    self.assertEqual(status, 200, host)
                    self.assertIn("harbour", body, host)
            self.assertEqual(_label(db_path, "A2"), "ON RECORD")


class WriteTokenTest(unittest.TestCase):
    def test_valid_loopback_host_with_valid_token_writes(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                status, _ = s.request(
                    "POST", "/entry/A2/label", host=f"127.0.0.1:{s.port}",
                    headers={"Origin": f"http://127.0.0.1:{s.port}"},
                    fields={"label": "UNKNOWN", "token": s.token},
                )
                self.assertEqual(status, 303)
                self.assertEqual(_label(db_path, "A2"), "UNKNOWN")
                status, _ = s.request(
                    "POST", "/entry/A2/label", host=f"localhost:{s.port}",
                    headers={"Origin": f"http://localhost:{s.port}"},
                    fields={"label": "VERIFIED", "token": s.token},
                )
                self.assertEqual(status, 303)
            self.assertEqual(_label(db_path, "A2"), "VERIFIED")

    def test_missing_or_wrong_token_is_refused_and_writes_nothing(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                for fields in (
                    {"label": "UNKNOWN"},
                    {"label": "UNKNOWN", "token": ""},
                    {"label": "UNKNOWN", "token": "0" * 64},
                    {"label": "UNKNOWN", "token": s.token[:-1]},
                ):
                    status, body = s.request(
                        "POST", "/entry/A2/label", fields=fields,
                    )
                    self.assertEqual(status, 403, fields)
                    self.assertIn("token", body)
            self.assertEqual(_label(db_path, "A2"), "ON RECORD")

    def test_packet_download_needs_the_token(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                status, _ = s.request(
                    "POST", "/model-pass/packet",
                    fields={"word_cap": "2500"},
                )
                self.assertEqual(status, 403)
            store = Store(db_path)
            try:
                count = store.conn.execute(
                    "SELECT COUNT(*) FROM packet_record"
                ).fetchone()[0]
            finally:
                store.close()
            self.assertEqual(count, 0)

    def test_every_write_form_carries_the_token(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            with Served(db_path) as s:
                pages = ("/", "/inventory", "/checklist", "/coverage",
                         "/model-pass", "/fixes", "/entry/A1",
                         "/entry/new")
                seen = 0
                for path in pages:
                    status, body = s.request("GET", path)
                    if status != 200:
                        continue
                    forms = re.findall(
                        r'<form class="write" method="post"[^>]*>(.{0,200})',
                        body,
                    )
                    for tail in forms:
                        self.assertTrue(
                            tail.startswith(
                                f'<input type="hidden" name="token"'
                                f' value="{s.token}">'
                            ),
                            path,
                        )
                    seen += len(forms)
                self.assertGreater(seen, 0)

    def test_each_server_has_its_own_token(self):
        with TemporaryDirectory() as tmp:
            db_path = _scratch_db(tmp)
            a = create_server(str(db_path), "127.0.0.1", 0)
            b = create_server(str(db_path), "127.0.0.1", 0)
            try:
                self.assertNotEqual(a.write_token, b.write_token)
                self.assertEqual(len(a.write_token), 64)
            finally:
                a.server_close()
                b.server_close()


class HostAllowedUnitTest(unittest.TestCase):
    def test_rules(self):
        self.assertTrue(_host_allowed("127.0.0.1:8090", "127.0.0.1", 8090))
        self.assertTrue(_host_allowed("localhost:8090", "127.0.0.1", 8090))
        self.assertTrue(_host_allowed("[::1]:8090", "127.0.0.1", 8090))
        self.assertTrue(
            _host_allowed("10.0.0.5:8090", "10.0.0.5", 8090)
        )
        self.assertFalse(_host_allowed("10.0.0.5:8090", "127.0.0.1", 8090))
        self.assertFalse(_host_allowed("127.0.0.1", "127.0.0.1", 8090))
        self.assertTrue(_host_allowed("127.0.0.1", "127.0.0.1", 80))
        self.assertTrue(_host_allowed("localhost", "127.0.0.1", 443))
        self.assertFalse(_host_allowed("127.0.0.1:81", "127.0.0.1", 80))
        self.assertFalse(_host_allowed(None, "127.0.0.1", 8090))
        self.assertFalse(_host_allowed("", "127.0.0.1", 8090))
        self.assertFalse(
            _host_allowed("127.0.0.1:notaport", "127.0.0.1", 8090)
        )
        self.assertFalse(
            _host_allowed("evil.example:8090", "127.0.0.1", 8090)
        )
        self.assertFalse(
            _host_allowed("127.0.0.1.evil.example:8090", "127.0.0.1", 8090)
        )

    def test_wildcard_bind_answers_loopback_names_only(self):
        self.assertFalse(_host_allowed("0.0.0.0:8090", "0.0.0.0", 8090))
        self.assertFalse(_host_allowed("[::]:8090", "::", 8090))
        self.assertFalse(_host_allowed("[::]:8090", "[::]", 8090))
        self.assertFalse(_host_allowed("0.0.0.0", "0.0.0.0", 80))
        for bind in ("0.0.0.0", "::", "[::]"):
            self.assertTrue(_host_allowed("127.0.0.1:8090", bind, 8090), bind)
            self.assertTrue(_host_allowed("localhost:8090", bind, 8090), bind)
            self.assertTrue(_host_allowed("[::1]:8090", bind, 8090), bind)
            # A LAN address on a wildcard bind stays refused.
            self.assertFalse(_host_allowed("10.0.0.5:8090", bind, 8090), bind)
        # A specific bind still answers its own address.
        self.assertTrue(_host_allowed("10.0.0.5:8090", "10.0.0.5", 8090))
        self.assertTrue(_host_allowed("[fe80::1]:8090", "fe80::1", 8090))

    def test_inject_token_only_touches_write_forms(self):
        page = (
            '<form method="get" action="/inventory"></form>'
            '<form class="write" method="post" action="/entry/new"></form>'
        )
        out = _inject_token(page, "ab12")
        self.assertEqual(out.count('name="token"'), 1)
        self.assertIn(
            '<form class="write" method="post" action="/entry/new">'
            '<input type="hidden" name="token" value="ab12">',
            out,
        )


if __name__ == "__main__":
    unittest.main()
