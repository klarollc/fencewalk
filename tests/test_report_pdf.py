"""Renderer tests: the PDF report carries the same report as the
Markdown renderer, from the same data — golden figures, row-ID
parity, adjudication presence/absence, end-to-end determinism, and
the CLI contract. The Markdown fixture-render fence (§2) is pinned
here too: render_report must stay byte-identical to the golden
render."""

import io
import re
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import load_fixture
from fencewalk.report import render_report
from fencewalk.store import Store
from fencewalk.report_pdf import render_pdf

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"
EXPECTED_REPORT = FIXTURE_DIR / "EXPECTED-REPORT.md"
SAMPLE_PACK = REPO_ROOT / "tests" / "fixtures" / "sample-pack.json"
SAMPLE_OUTPUT = REPO_ROOT / "tests" / "fixtures" / "sample-model-output.md"
DATE = "2026-11-18"

_WINANSI_DECODE = {
    133: "…",
    145: "‘",
    146: "’",
    147: "“",
    148: "”",
    149: "•",
    150: "–",
    151: "—",
    183: "·",
}


def extract_text(pdf_bytes):
    """Plain text of a rendered PDF, one line per BT block.

    Decompresses every FlateDecode content stream, joins the literal
    strings inside each BT block directly (runs of one line belong
    together), and decodes WinAnsi bytes. Spaces survive because the
    renderer puts them at the end of the preceding run.
    """
    lines = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        try:
            raw = zlib.decompress(match.group(1).strip(b"\r\n"))
        except zlib.error:
            continue
        for block in re.finditer(rb"BT(.*?)ET", raw, re.S):
            parts = []
            for sm in re.finditer(rb"\((?:\\.|[^\\()])*\)", block.group(1)):
                s = sm.group(0)[1:-1]
                s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
                parts.append(bytes(s))
            joined = b"".join(parts)
            lines.append(
                "".join(
                    _WINANSI_DECODE.get(b, chr(b)) for b in joined
                )
            )
    return "\n".join(lines)


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def printed_value(stdout, label):
    for line in stdout.splitlines():
        if line.startswith(label):
            return line[len(label) :].strip()
    raise AssertionError(f"no '{label}' line in output: {stdout!r}")


class FixturePdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp.name) / "reference.db")
        load_fixture(FIXTURE_DIR, cls.db_path)
        cls.markdown = render_report(cls.db_path)
        cls.pdf_bytes = render_pdf(cls.db_path)
        cls.text = extract_text(cls.pdf_bytes)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_golden_figures_present(self):
        self.assertIn("Inventory: 52 entries", self.text)
        self.assertIn(
            "Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows",
            self.text,
        )
        self.assertIn("Attack chains: 3", self.text)
        self.assertIn("Verify-next items: 10", self.text)

    def test_every_row_id_present(self):
        item_ids = set(re.findall(r"\bR-\d+\.\d+\b", self.markdown))
        self.assertEqual(len(item_ids), 20)
        for item_id in item_ids:
            self.assertIn(item_id, self.text, item_id)
        fix_ids = set(re.findall(r"\bF-\d+\b", self.markdown))
        self.assertEqual(len(fix_ids), 16)
        for fix_id in fix_ids:
            self.assertIn(fix_id, self.text, fix_id)
        for key in ("Chain A:", "Chain B:", "Chain C:"):
            self.assertIn(key, self.text)

    def test_tallies_match_word_for_word(self):
        tally = (
            "Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows"
        )
        self.assertEqual(self.markdown.count(tally), 2)
        self.assertEqual(self.text.count(tally), 2)

    def test_adjudication_absent_for_fixture(self):
        self.assertNotIn("Adjudication", self.text)
        self.assertNotIn("Run 1", self.text)

    def test_determinism_end_to_end(self):
        self.assertEqual(render_pdf(self.db_path), self.pdf_bytes)

    def test_pdf_is_valid(self):
        self.assertTrue(self.pdf_bytes.startswith(b"%PDF-1.4\n"))
        self.assertTrue(self.pdf_bytes.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/FlateDecode", self.pdf_bytes)

    def test_markdown_fixture_render_still_byte_identical(self):
        # The §2 refactor fence: the Markdown render must not move.
        self.assertEqual(
            self.markdown.encode("utf-8"),
            EXPECTED_REPORT.read_bytes(),
        )


class AdjudicationPdfTest(unittest.TestCase):
    """A DB with adjudication events renders the Adjudication section."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli(
            ["new", self.db, "--name", "Adjudication scratch",
             "--subject", "Scratch subject", "--method-order", "model-first",
             "--date", DATE]
        )
        self.assertEqual(code, 0, err)
        code, _, err = run_cli(["load-pack", self.db, str(SAMPLE_PACK)])
        self.assertEqual(code, 0, err)
        out_path = str(Path(self.tmp.name) / "packet.md")
        code, out, err = run_cli(
            ["packet", self.db, "--out", out_path, "--date", DATE]
        )
        self.assertEqual(code, 0, err)
        packet_hash = printed_value(out, "sha256:")
        code, _, err = run_cli(
            ["ingest", self.db, str(SAMPLE_OUTPUT),
             "--packet-hash", packet_hash,
             "--model", "Example Model 1", "--date", DATE]
        )
        self.assertEqual(code, 0, err)
        code, _, err = run_cli(
            ["adjudicate", self.db, "--run", "1", "--section", "coverage",
             "--decision", "accept", "--date", DATE]
        )
        self.assertEqual(code, 0, err)
        code, _, err = run_cli(
            ["adjudicate", self.db, "--run", "1", "--section", "fixes",
             "--decision", "correct", "--note", "F-1 needs a date.",
             "--date", DATE]
        )
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def test_adjudication_present_with_decisions(self):
        text = extract_text(render_pdf(self.db))
        self.assertIn("Adjudication", text)
        self.assertIn("Run 1 — Example Model 1 (2026-11-18)", text)
        self.assertIn("Coverage: accept (2026-11-18, operator)", text)
        self.assertIn("Fixes: correct (2026-11-18, operator)", text)
        self.assertIn("— note: F-1 needs a date.", text)
        self.assertIn("Chains: no decision recorded", text)


class PdfCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "reference.db")
        load_fixture(FIXTURE_DIR, self.db_path)
        self.out_path = str(Path(self.tmp.name) / "report.pdf")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pdf_writes_file_and_prints_path(self):
        code, out, err = run_cli(
            ["pdf", self.db_path, "--out", self.out_path]
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(out, f"pdf written to {self.out_path}\n")
        self.assertTrue(Path(self.out_path).exists())
        self.assertTrue(Path(self.out_path).read_bytes().startswith(b"%PDF-1.4"))

    def test_pdf_without_out_exits_nonzero(self):
        with self.assertRaises(SystemExit) as caught:
            main(["pdf", self.db_path])
        self.assertNotEqual(caught.exception.code, 0)

    def test_pdf_on_packless_db_matches_report_error(self):
        packless = str(Path(self.tmp.name) / "nopack.db")
        code, _, err = run_cli(
            ["new", packless, "--name", "No pack", "--subject", "S",
             "--method-order", "verify-first", "--date", DATE]
        )
        self.assertEqual(code, 0, err)
        code, _, pdf_err = run_cli(["pdf", packless, "--out", self.out_path])
        self.assertEqual(code, 1)
        self.assertEqual(
            pdf_err,
            "error: database holds no rubric pack; load one with load-pack\n",
        )
        code, _, report_err = run_cli(["report", packless])
        self.assertEqual(code, 1)
        self.assertEqual(report_err, pdf_err)

    def test_pdf_on_engagementless_db_matches_report_error(self):
        from fencewalk.store import Store

        empty = str(Path(self.tmp.name) / "empty.db")
        store = Store(empty)
        try:
            store.init_schema()
        finally:
            store.close()
        code, _, pdf_err = run_cli(["pdf", empty, "--out", self.out_path])
        self.assertEqual(code, 1)
        code, _, report_err = run_cli(["report", empty])
        self.assertEqual(code, 1)
        self.assertEqual(pdf_err, report_err)
        self.assertEqual(pdf_err, "error: database holds no engagement\n")


class CrossPackIdTest(unittest.TestCase):
    """0.3.5 (D2): the /ID records every owner of a cross-pack
    citation. Before, cross_pack_citations kept one owner per item
    id (the last citation's), and the stored packs are left out of
    the hashed rows, so two databases whose citations of one id
    differed only in the first citation's pack rendered different
    text under one /ID."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _pack(pack_id):
        return {
            "pack_id": pack_id, "title": pack_id,
            "source_citation": "Invented for the Fencewalk test suite.",
            "version": "1.0",
            "items": [{"item_id": "R-1.1", "group": "G", "text": pack_id}],
        }

    def _db(self, first, second):
        db = str(Path(self.tmp.name) / f"{first}--{second}.db")
        load_fixture(FIXTURE_DIR, db)
        with Store(db) as store:
            store.add_pack(self._pack("yyy-mid"))
            store.add_pack(self._pack("zzz-late"))
            for fix_id, pack_id in (("F-A", first), ("F-B", second)):
                store.add_fix(
                    1, fix_id, f"id probe {fix_id}", "low", "A", ["R-1.1"],
                    status="proposed", status_date=DATE,
                    status_actor="test", rubric_pack_id=pack_id,
                )
        return db

    @staticmethod
    def _doc_id(pdf_bytes):
        return re.search(rb"/ID \[<([0-9a-f]{64})>", pdf_bytes).group(1)

    def test_first_citation_pack_changes_the_id(self):
        mixed = self._db("yyy-mid", "zzz-late")
        same = self._db("zzz-late", "zzz-late")
        self.assertNotEqual(render_report(mixed), render_report(same))
        self.assertNotEqual(
            self._doc_id(render_pdf(mixed)), self._doc_id(render_pdf(same))
        )

    def test_second_citation_pack_changes_the_id(self):
        mixed = self._db("yyy-mid", "zzz-late")
        same = self._db("yyy-mid", "yyy-mid")
        self.assertNotEqual(
            self._doc_id(render_pdf(mixed)), self._doc_id(render_pdf(same))
        )

    def test_id_is_stable_for_the_same_database(self):
        mixed = self._db("yyy-mid", "zzz-late")
        self.assertEqual(render_pdf(mixed), render_pdf(mixed))


if __name__ == "__main__":
    unittest.main()
