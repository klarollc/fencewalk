"""Slice 4 tests: model-pass packet assembly (determinism, hash,
content, pack-less refusal), output ingest (verbatim storage against a
recorded packet hash, nothing else changed), the adjudication draft
(sectioning with verbatim preservation), and pre-slice-4 databases."""

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"
PACK_FILE = REPO_ROOT / "src" / "fencewalk" / "packs" / "flash-20261113-001.json"
SAMPLE_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "sample-model-output.md"

PLACEHOLDERS = (
    "{engagement_name}", "{subject_label}", "{pack_title}",
    "{pack_citation}", "{word_cap}",
)
PACK_CITATION = (
    'FBI FLASH-20261113-001, "Threat Overview of ARTEX Autonomous '
    'Penetration Testing Framework," Nov 13, 2026, TLP:CLEAR'
)
ASSEMBLED = "2026-11-18"


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


def assert_lines_in_order(testcase, haystack, needle):
    """Every line of needle appears in haystack, verbatim and in order."""
    lines = haystack.splitlines()
    pos = 0
    for want in needle.splitlines():
        while pos < len(lines) and lines[pos] != want:
            pos += 1
        testcase.assertTrue(
            pos < len(lines), f"line not found in order: {want!r}"
        )
        pos += 1


class FixtureDbTestCase(unittest.TestCase):
    """Base: the reference fixture loaded into a temp database."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "ref.db")
        code, _, err = run_cli(["load-fixture", str(FIXTURE_DIR), self.db])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def packet(self, name="packet.md", **extra):
        out_path = str(Path(self.tmp.name) / name)
        argv = ["packet", self.db, "--out", out_path, "--date", ASSEMBLED]
        for key, value in extra.items():
            argv += [f"--{key.replace('_', '-')}", str(value)]
        code, out, err = run_cli(argv)
        self.assertEqual(code, 0, err)
        return out_path, out

    def packet_hash(self, **extra):
        _, out = self.packet(**extra)
        return printed_value(out, "sha256:")


class PacketTest(FixtureDbTestCase):
    def test_no_placeholders_and_default_word_cap(self):
        out_path, _ = self.packet()
        text = Path(out_path).read_text(encoding="utf-8")
        for token in PLACEHOLDERS:
            self.assertNotIn(token, text)
        self.assertIn("under roughly 2500 words", text)

    def test_non_default_word_cap_is_reflected(self):
        out_path, _ = self.packet(word_cap=1200)
        text = Path(out_path).read_text(encoding="utf-8")
        self.assertIn("under roughly 1200 words", text)

    def test_packet_content(self):
        out_path, _ = self.packet()
        text = Path(out_path).read_text(encoding="utf-8")
        inventory = json.loads(
            (FIXTURE_DIR / "inventory.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(inventory["entries"]), 52)
        for entry in inventory["entries"]:
            self.assertIn(f"**{entry['entry_id']}**", text)
        pack = json.loads(PACK_FILE.read_text(encoding="utf-8"))
        self.assertEqual(len(pack["items"]), 20)
        for item in pack["items"]:
            self.assertIn(f"**{item['item_id']}**", text)
        self.assertIn(PACK_CITATION, text)
        self.assertIn("verify-first", text)

    def test_determinism_and_printed_hash(self):
        path1, out1 = self.packet("p1.md")
        path2, out2 = self.packet("p2.md")
        bytes1 = Path(path1).read_bytes()
        bytes2 = Path(path2).read_bytes()
        self.assertEqual(bytes1, bytes2)
        sha = printed_value(out1, "sha256:")
        self.assertEqual(sha, printed_value(out2, "sha256:"))
        self.assertEqual(sha, hashlib.sha256(bytes1).hexdigest())
        self.assertEqual(int(printed_value(out1, "byte count:")), len(bytes1))

    def test_packet_is_recorded(self):
        _, out = self.packet()
        sha = printed_value(out, "sha256:")
        with Store(self.db) as store:
            packets = store.list_packets()
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["sha256"], sha)
        self.assertEqual(packets[0]["pack_id"], "flash-20261113-001")
        self.assertEqual(packets[0]["word_cap"], 2500)
        self.assertEqual(packets[0]["assembled_date"], ASSEMBLED)


class PacklessPacketTest(unittest.TestCase):
    def test_packet_on_packless_database_fails_cleanly_and_records_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "eng.db")
            code, _, err = run_cli([
                "new", db, "--name", "No pack", "--subject", "Test firm",
                "--method-order", "verify-first", "--date", ASSEMBLED,
            ])
            self.assertEqual(code, 0, err)
            out_path = str(Path(tmp) / "packet.md")
            code, _, err = run_cli(
                ["packet", db, "--out", out_path, "--date", ASSEMBLED]
            )
            self.assertEqual(code, 1)
            self.assertIn("database holds no rubric pack", err)
            self.assertFalse(Path(out_path).exists())
            with Store(db) as store:
                self.assertEqual(store.list_packets(), [])


class IngestTest(FixtureDbTestCase):
    def setUp(self):
        super().setUp()
        self.sha = self.packet_hash()

    def ingest(self, output_file, *extra):
        argv = [
            "ingest", self.db, str(output_file),
            "--packet-hash", self.sha, "--date", ASSEMBLED,
        ]
        argv += list(extra)
        return run_cli(argv)

    def test_unknown_packet_hash_refused(self):
        code, _, err = self.ingest(SAMPLE_OUTPUT)
        self.assertEqual(code, 0, err)  # sanity: the known hash works
        code, _, err = run_cli([
            "ingest", self.db, str(SAMPLE_OUTPUT),
            "--packet-hash", "0" * 64, "--date", ASSEMBLED,
        ])
        self.assertEqual(code, 1)
        self.assertIn("no recorded packet with hash", err)
        with Store(self.db) as store:
            self.assertEqual(len(store.list_runs()), 1)  # only the good one

    def test_ingest_stores_output_verbatim_and_defaults_model(self):
        code, out, err = self.ingest(SAMPLE_OUTPUT)
        self.assertEqual(code, 0, err)
        self.assertEqual(printed_value(out, "packet hash:"), self.sha)
        expected = SAMPLE_OUTPUT.read_bytes()
        self.assertEqual(
            int(printed_value(out, "output byte count:")), len(expected)
        )
        with Store(self.db) as store:
            run = store.get_run(1)
        self.assertEqual(run["raw_output"], expected.decode("utf-8"))
        self.assertEqual(run["model_label"], "not stated")
        self.assertEqual(run["packet_hash"], self.sha)
        self.assertEqual(run["run_date"], ASSEMBLED)

    def test_second_ingest_creates_a_second_run(self):
        code, _, err = self.ingest(SAMPLE_OUTPUT)
        self.assertEqual(code, 0, err)
        code, out, err = self.ingest(
            SAMPLE_OUTPUT, "--model", "Example Model 1"
        )
        self.assertEqual(code, 0, err)
        self.assertIn("ingested model run 2", out)
        with Store(self.db) as store:
            runs = store.list_runs()
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[1]["model_label"], "Example Model 1")

    def test_ingest_changes_nothing_else(self):
        with Store(self.db) as store:
            before = (
                store.coverage_tallies("flash-20261113-001"),
                len(store.list_chains()),
                len(store.list_fixes()),
                len(store.list_verify_next()),
            )
        code, _, err = self.ingest(SAMPLE_OUTPUT)
        self.assertEqual(code, 0, err)
        with Store(self.db) as store:
            after = (
                store.coverage_tallies("flash-20261113-001"),
                len(store.list_chains()),
                len(store.list_fixes()),
                len(store.list_verify_next()),
            )
        self.assertEqual(before, after)


class DraftTest(FixtureDbTestCase):
    def setUp(self):
        super().setUp()
        self.sha = self.packet_hash()
        code, self.ingest_out, err = run_cli([
            "ingest", self.db, str(SAMPLE_OUTPUT),
            "--packet-hash", self.sha,
            "--model", "Example Model 1", "--date", ASSEMBLED,
        ])
        self.assertEqual(code, 0, err)

    def draft(self, run_id=1):
        code, out, err = run_cli(["draft", self.db, "--run", str(run_id)])
        self.assertEqual(code, 0, err)
        return out

    def test_end_to_end_hash_flows_from_packet_through_ingest_to_draft(self):
        self.assertEqual(
            printed_value(self.ingest_out, "packet hash:"), self.sha
        )
        text = self.draft()
        self.assertIn(f"- Packet hash: {self.sha}", text)

    def test_draft_header(self):
        text = self.draft()
        self.assertIn("- Run: 1", text)
        self.assertIn(f"- Packet hash: {self.sha}", text)
        self.assertIn("- Model: Example Model 1", text)
        self.assertIn("- Run date: 2026-11-18", text)

    def test_four_sections_with_four_stubs(self):
        text = self.draft()
        for heading in (
            "## Coverage map", "## Attack chains",
            "## Fix list", "## Verify-next list",
        ):
            self.assertIn(heading, text)
        self.assertEqual(
            text.count("Decision: (accept / correct / reject)"), 4
        )
        self.assertEqual(text.count("Correction or note:"), 4)

    def test_every_output_line_verbatim_and_in_order(self):
        text = self.draft()
        raw = SAMPLE_OUTPUT.read_text(encoding="utf-8")
        assert_lines_in_order(self, text, raw)

    def test_preamble_preserved_before_first_section(self):
        text = self.draft()
        self.assertIn("## Preamble", text)
        first_line = SAMPLE_OUTPUT.read_text(
            encoding="utf-8"
        ).splitlines()[0]
        self.assertIn(first_line, text)
        self.assertLess(
            text.index("## Preamble"), text.index("## Coverage map")
        )

    def test_unsectioned_output_drafts_as_one_block(self):
        plain = (
            "# Some model output\n"
            "\n"
            "No deliverable structure was returned.\n"
            "Everything is unknown; check the tenant first.\n"
        )
        plain_path = Path(self.tmp.name) / "plain-output.md"
        plain_path.write_text(plain, encoding="utf-8")
        code, _, err = run_cli([
            "ingest", self.db, str(plain_path),
            "--packet-hash", self.sha, "--date", ASSEMBLED,
        ])
        self.assertEqual(code, 0, err)
        text = self.draft(run_id=2)
        self.assertIn("No deliverable headings were recognized", text)
        self.assertIn("## Unsectioned output", text)
        self.assertEqual(
            text.count("Decision: (accept / correct / reject)"), 1
        )
        assert_lines_in_order(self, text, plain)

    def test_no_such_run_is_a_clean_error(self):
        code, _, err = run_cli(["draft", self.db, "--run", "99"])
        self.assertEqual(code, 1)
        self.assertIn("no such run: 99", err)


class PreSlice4DatabaseTest(FixtureDbTestCase):
    def test_packet_and_ingest_work_after_new_tables_are_dropped(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE packet_record")
        conn.execute("DROP TABLE model_run")
        conn.commit()
        conn.close()
        sha = self.packet_hash()
        code, _, err = run_cli([
            "ingest", self.db, str(SAMPLE_OUTPUT),
            "--packet-hash", sha, "--date", ASSEMBLED,
        ])
        self.assertEqual(code, 0, err)
        code, out, err = run_cli(["draft", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn(f"- Packet hash: {sha}", out)


if __name__ == "__main__":
    unittest.main()
