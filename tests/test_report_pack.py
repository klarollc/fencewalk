"""Report --pack tests: the report and PDF renderers select which
loaded rubric pack they render, and the default stays exactly the
bare-query first row.

The pinned premise (brief section 2): with no --pack, the rendered
report names the alphabetically-first pack_id among the loaded
packs, because gather_report_data reads `SELECT pack_id FROM
rubric_pack` with no ORDER BY and pack_id is a TEXT PRIMARY KEY,
so SQLite serves the bare query from the primary-key index, in
pack_id order — not load order. The characterization test pins
this on the base before any code changes; it must pass on the
base and after the change with no --pack given.
"""

import io
import re
import sqlite3
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import load_fixture
from fencewalk.report import render_report
from fencewalk.report_pdf import render_pdf

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"

FLASH_ID = "flash-20261113-001"
FLASH_TITLE = "ARTEX mitigations rubric"
SCUBA_ID = "scuba-m365-v2.0.0"
SCUBA_TITLE = "CISA SCuBA M365 Secure Configuration Baselines (ScubaGear v2.0.0)"
ASD_ID = "asd-secure-cloud-identity-1.4"
ASD_TITLE = "ASD Blueprint for Secure Cloud — Entra ID expected state (v1.4)"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def rubric_pack_line(text):
    for line in text.splitlines():
        if line.startswith("- Rubric pack: "):
            return line
    raise AssertionError(f"no 'Rubric pack:' line in report: {text!r}")


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


class ThreePackDbTest(unittest.TestCase):
    """One DB, three packs loaded in deliberately non-alphabetical
    order: fixture (FLASH), then SCuBA, then ASD."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = str(Path(cls.tmp.name) / "three-pack.db")
        load_fixture(FIXTURE_DIR, cls.db_path)
        # No recorded primary: the default under test is the
        # alphabetical fallback.
        clear_primary_pack(cls.db_path)
        for pack in (SCUBA_ID, ASD_ID):
            code, _, err = run_cli(["load-pack", cls.db_path, pack])
            assert code == 0, err

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_characterization_default_is_alphabetically_first(self):
        # The premise, verified by direct query: the bare query
        # returns pack_id order (alphabetical); rowid order is load
        # order. If this fails, the brief's section 2 premise is
        # wrong and the slice is mis-scoped.
        conn = sqlite3.connect(self.db_path)
        try:
            bare = [
                r[0]
                for r in conn.execute(
                    "SELECT pack_id FROM rubric_pack"
                ).fetchall()
            ]
            by_rowid = [
                r[0]
                for r in conn.execute(
                    "SELECT pack_id FROM rubric_pack ORDER BY rowid"
                ).fetchall()
            ]
        finally:
            conn.close()
        self.assertEqual(bare, [ASD_ID, FLASH_ID, SCUBA_ID])
        self.assertEqual(by_rowid, [FLASH_ID, SCUBA_ID, ASD_ID])
        # And the rendered report names the ASD pack: the default
        # is the bare-query first row, not the earliest loaded.
        line = rubric_pack_line(render_report(self.db_path))
        self.assertIn(ASD_TITLE, line)
        self.assertNotIn(FLASH_TITLE, line)
        self.assertNotIn(SCUBA_TITLE, line)

    def test_pack_selects_each_pack(self):
        # FLASH: the fixture scores all 20 of its items. SCuBA and
        # ASD: the fixture scores nothing against them, so their
        # coverage tables are empty and the tallies read zero —
        # honest rendering of an unscored pack, not a defect.
        flash = render_report(self.db_path, FLASH_ID)
        self.assertIn(FLASH_TITLE, rubric_pack_line(flash))
        self.assertIn(
            "Tallies: Covered 3 · Partial 8 · Unknown 5"
            " · Not applicable 2 · Gap 2 — 20 rows",
            flash,
        )
        scuba = render_report(self.db_path, SCUBA_ID)
        self.assertIn(SCUBA_TITLE, rubric_pack_line(scuba))
        self.assertIn(
            "Tallies: Covered 0 · Partial 0 · Unknown 0"
            " · Not applicable 0 · Gap 0 — 0 rows",
            scuba,
        )
        asd = render_report(self.db_path, ASD_ID)
        self.assertIn(ASD_TITLE, rubric_pack_line(asd))
        self.assertIn(
            "Tallies: Covered 0 · Partial 0 · Unknown 0"
            " · Not applicable 0 · Gap 0 — 0 rows",
            asd,
        )
        # And the CLI path, at least once: --pack FLASH through
        # `report` names FLASH.
        code, out, err = run_cli(["report", self.db_path, "--pack", FLASH_ID])
        self.assertEqual(code, 0, err)
        self.assertIn(FLASH_TITLE, rubric_pack_line(out))

    def test_unknown_pack_errors(self):
        for cmd in ("report", "pdf"):
            argv = [cmd, self.db_path, "--pack", "nope-1.2.3"]
            if cmd == "pdf":
                argv += ["--out", str(Path(self.tmp.name) / "nope.pdf")]
            code, _, err = run_cli(argv)
            self.assertNotEqual(code, 0)
            self.assertEqual(err, "error: no such pack: nope-1.2.3\n")

    def test_pdf_follows_the_flag(self):
        flash_pdf = render_pdf(self.db_path, FLASH_ID)
        asd_pdf = render_pdf(self.db_path, ASD_ID)
        self.assertNotEqual(flash_pdf, asd_pdf)
        # Determinism holds per selection.
        self.assertEqual(render_pdf(self.db_path, FLASH_ID), flash_pdf)
        self.assertEqual(render_pdf(self.db_path, ASD_ID), asd_pdf)
        # Each PDF names the same pack as the Markdown report for
        # the same selection.
        self.assertIn(FLASH_TITLE, extract_text(flash_pdf))
        self.assertIn(FLASH_TITLE, rubric_pack_line(
            render_report(self.db_path, FLASH_ID)))
        self.assertIn(ASD_TITLE, extract_text(asd_pdf))
        self.assertIn(ASD_TITLE, rubric_pack_line(
            render_report(self.db_path, ASD_ID)))

    def test_golden_render_byte_identical(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            db = str(Path(tmp.name) / "fixture.db")
            load_fixture(FIXTURE_DIR, db)
            expected = (FIXTURE_DIR / "EXPECTED-REPORT.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(render_report(db), expected)
            # The default on the fixture-only DB is FLASH (only
            # pack loaded), with or without an explicit --pack.
            self.assertEqual(
                render_report(db, FLASH_ID), render_report(db)
            )
        finally:
            tmp.cleanup()


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

    Copied from tests/test_report_pdf.py: decompresses every
    FlateDecode content stream, joins the literal strings inside
    each BT block directly, and decodes WinAnsi bytes.
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


if __name__ == "__main__":
    unittest.main()
