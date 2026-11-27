"""Report disclosure (0.3.3): unscored items, one pack default,
cross-pack citation annotation, and the PDF substitution note; and
(0.3.4) the stored citation pack, the guaranteed default, and the
schema migration.

- A report over a partly scored pack says how many items are not
  scored, in the same tally line, in Markdown and in the PDF.
- Every pack default in the tool is the alphabetically-first loaded
  pack: report, pdf, packet, rubric validation, and the web pages
  name the same pack with no --pack.
- A fix or chain citing an item from a pack other than the rendered
  one carries that pack's id in parentheses.
- From 0.3.4 a citation stores the pack it was validated against,
  so an item id that several packs share is attributed to the pack
  it was cited from; a database from before 0.3.4 gains the two
  columns on open and renders exactly as it did.
- Characters the PDF font cannot draw still appear as "?", but the
  PDF says so, with the count, as its last content line.
"""

import io
import os
import re
import sqlite3
import stat
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import load_fixture
from fencewalk.packet import assemble_packet
from fencewalk.report import (
    _tally_line,
    cross_pack_citations,
    gather_report_data,
    render_report,
)
from fencewalk.report_pdf import render_pdf
from fencewalk.store import SCHEMA, Store
from fencewalk.web import _default_pack_id, _pack_select


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"
FLASH_ID = "flash-20261113-001"
SCUBA_ID = "scuba-m365-v2.0.0"
ASD_ID = "asd-secure-cloud-identity-1.4"
AAA_ID = "aaa-first"
ZZZ_ID = "zzz-late"
MID_ID = "yyy-mid"
EXPECTED_REPORT = FIXTURE_DIR / "EXPECTED-REPORT.md"


def small_pack(pack_id):
    """A two-item pack whose R-1.1 collides with FLASH's R-1.1."""
    return {
        "pack_id": pack_id,
        "title": f"Collision pack {pack_id}",
        "source_citation": "Invented for the Fencewalk test suite.",
        "version": "1.0",
        "items": [
            {"item_id": "R-1.1", "group": "Group 1",
             "text": f"The {pack_id} reading of R-1.1."},
            {"item_id": "X-9.9", "group": "Group 1",
             "text": f"An item only {pack_id} names."},
        ],
    }


def pre_034_schema():
    """SCHEMA as it stood before 0.3.4: no fix_rubric.pack_id and no
    chain.control_pack (and so no engagement.primary_pack, which came
    later still)."""
    old = SCHEMA
    for new_text, old_text in (
        ("'model-first')),\n    primary_pack  TEXT\n",
         "'model-first'))\n"),
        ("    control_status  TEXT NOT NULL,\n    control_pack    TEXT\n",
         "    control_status  TEXT NOT NULL\n"),
        ("    item_id TEXT NOT NULL,\n    pack_id TEXT,\n",
         "    item_id TEXT NOT NULL,\n"),
    ):
        assert old.count(new_text) == 1, new_text
        old = old.replace(new_text, old_text)
    return old


def downgrade_copy(src_db, dst_db):
    """Copy src_db into a new database with the pre-0.3.4 schema,
    through raw sqlite3 only — every row, minus the two new columns."""
    src = sqlite3.connect(src_db)
    dst = sqlite3.connect(dst_db)
    try:
        dst.executescript(pre_034_schema())
        tables = [
            r[0] for r in dst.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " ORDER BY rowid"
            )
        ]
        for table in tables:
            cols = [r[1] for r in dst.execute(f"PRAGMA table_info({table})")]
            col_list = ", ".join(cols)
            marks = ", ".join("?" for _ in cols)
            rows = src.execute(
                f"SELECT {col_list} FROM {table} ORDER BY rowid"
            ).fetchall()
            dst.executemany(
                f"INSERT INTO {table} ({col_list}) VALUES ({marks})", rows
            )
        dst.commit()
    finally:
        src.close()
        dst.close()


def table_columns(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    finally:
        conn.close()


def dump_rows(db_path, drop=()):
    """Every row of every table, as {table: [row dicts]}, with the
    named columns left out."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        out = {}
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " ORDER BY name"
            )
        ]
        for table in tables:
            out[table] = [
                {k: row[k] for k in row.keys() if k not in drop}
                for row in conn.execute(
                    f"SELECT * FROM {table} ORDER BY rowid"
                )
            ]
        return out
    finally:
        conn.close()


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

    Copied from tests/test_report_pack.py: decompresses every
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


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


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


class DbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        load_fixture(FIXTURE_DIR, self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def cli_ok(self, *argv):
        code, out, err = run_cli(list(argv))
        self.assertEqual(code, 0, err)
        return out

    def load(self, *packs):
        for pack in packs:
            self.cli_ok("load-pack", self.db, f"{pack}.json")


class NotScoredDisclosureTest(DbCase):
    LINE = (
        "Covered 0 · Partial 1 · Unknown 0 · Not applicable 0 · Gap 0"
        " — 1 rows · not scored 108 (of 109)"
    )

    def setUp(self):
        super().setUp()
        self.load(SCUBA_ID)
        self.cli_ok(
            "score", self.db, "--pack", SCUBA_ID, "--item", "MS.AAD.1.1v1",
            "--status", "Partial", "--reasoning", "Probe score.",
            "--cite", "A3",
        )

    def test_markdown_tally_lines_disclose_unscored_items(self):
        text = render_report(self.db, SCUBA_ID)
        self.assertIn(f"- Coverage: {self.LINE}\n", text)
        self.assertIn(f"Tallies: {self.LINE}\n", text)
        # The coverage table stays scores-only: one row.
        rows = [
            line for line in text.splitlines()
            if line.startswith("| MS.")
        ]
        self.assertEqual(len(rows), 1)

    def test_pdf_carries_the_same_disclosure(self):
        pdf = render_pdf(self.db, SCUBA_ID)
        text = extract_text(pdf)
        self.assertIn("not scored 108 (of 109)", text)
        self.assertEqual(text.count("not scored 108"), 2)

    def test_tally_line_is_unchanged_when_all_scored(self):
        tallies = {"Covered": 2, "Partial": 1}
        base = _tally_line(tallies)
        self.assertEqual(_tally_line(tallies, 0, 3), base)
        self.assertNotIn("not scored", base)

    def test_fully_scored_fixture_has_no_disclosure(self):
        text = render_report(self.db, FLASH_ID)
        self.assertNotIn("not scored", text)
        self.assertNotIn("not scored", extract_text(render_pdf(self.db, FLASH_ID)))


class OneDefaultTest(DbCase):
    def setUp(self):
        super().setUp()
        # Load order deliberately differs from alphabetical order:
        # FLASH (fixture) first, then SCuBA, then ASD. With no
        # recorded primary the default is the alphabetical one.
        clear_primary_pack(self.db)
        self.load(SCUBA_ID, ASD_ID)

    def test_report_pdf_packet_and_validation_name_the_same_pack(self):
        text = render_report(self.db)
        self.assertIn("- Rubric pack: ASD Blueprint", text)
        _, pack = assemble_packet(self.db, assembled_date="2026-11-22")
        self.assertEqual(pack["pack_id"], ASD_ID)
        out = self.cli_ok(
            "packet", self.db, "--date", "2026-11-22",
            "--out", str(Path(self.tmp.name) / "p.md"),
        )
        with Store(self.db) as store:
            row = store.conn.execute(
                "SELECT pack_id FROM packet_record ORDER BY id DESC"
            ).fetchone()
            self.assertEqual(row["pack_id"], ASD_ID)
            self.assertEqual(store.default_pack_id(), ASD_ID)
            self.assertEqual(_default_pack_id(store), ASD_ID)
            self.assertIn(
                f'<option value="{ASD_ID}" selected>', _pack_select(store)
            )
        self.assertIn("byte count:", out)
        # Rubric validation with no --pack validates against ASD: a
        # FLASH item is refused, naming the ASD pack.
        code, _, err = run_cli([
            "add-fix", self.db, "--id", "F-X", "--action", "x",
            "--effort", "low", "--breaks", "A", "--rubric", "R-1.4",
        ])
        self.assertEqual(code, 1)
        self.assertIn(f"no such item in pack {ASD_ID}: R-1.4", err)

    def test_default_is_alphabetical_under_reverse_unordered_selects(self):
        # The 0.3.3 default was a bare SELECT that happened to scan
        # the index in order. With SQLite told to reverse every
        # unordered scan, only an ORDER BY keeps the default.
        with Store(self.db) as store:
            store.add_pack(small_pack(ZZZ_ID))
            store.add_pack(small_pack(AAA_ID))
            store.conn.execute("PRAGMA reverse_unordered_selects = ON")
            bare = store.conn.execute(
                "SELECT pack_id FROM rubric_pack"
            ).fetchone()[0]
            self.assertEqual(bare, ZZZ_ID)  # the pragma is in force
            self.assertEqual(store.default_pack_id(), AAA_ID)
            self.assertEqual(_default_pack_id(store), AAA_ID)

    def test_default_query_is_the_pinned_ordered_query(self):
        text = (REPO_ROOT / "src" / "fencewalk" / "store.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"SELECT pack_id FROM rubric_pack ORDER BY pack_id LIMIT 1"',
            text,
        )

    def test_no_load_order_default_remains_in_source(self):
        src = REPO_ROOT / "src" / "fencewalk"
        for path in src.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "rubric_pack" in line and "ORDER BY rowid" in line:
                    # Store.list_packs is the one listing (not a
                    # default) that keeps load order.
                    self.assertEqual(path.name, "store.py", line)


class CrossPackAnnotationTest(DbCase):
    def setUp(self):
        super().setUp()
        clear_primary_pack(self.db)
        self.load(SCUBA_ID, ASD_ID)
        self.cli_ok(
            "add-fix", self.db, "--id", "F-PROBE",
            "--action", "probe fix citing SCuBA", "--effort", "low",
            "--breaks", "A", "--rubric", "MS.AAD.1.1v1",
            "--pack", SCUBA_ID, "--date", "2026-11-22",
        )
        self.cli_ok(
            "add-chain", self.db, "--key", "Z", "--name", "Probe chain",
            "--control", "Phishing-resistant MFA.",
            "--control-status", "absent",
            "--control-rubric", "MS.AAD.1.1v1", "--pack", SCUBA_ID,
            "--step", "Access: a probe step.",
        )

    def test_markdown_annotates_cross_pack_citations(self):
        text = render_report(self.db)  # default: ASD
        self.assertIn(
            "| F-PROBE | probe fix citing SCuBA |"
            " MS.AAD.1.1v1 (scuba-m365-v2.0.0) | low | A | proposed |",
            text,
        )
        self.assertIn(
            "Earliest breaking control: Phishing-resistant MFA."
            " (MS.AAD.1.1v1 (scuba-m365-v2.0.0)) Status: absent.",
            text,
        )
        # The fixture's FLASH citations are cross-pack in an ASD
        # report too.
        self.assertIn("R-4.1 (flash-20261113-001)", text)

    def test_rendered_pack_citations_stay_bare(self):
        text = render_report(self.db, SCUBA_ID)
        self.assertIn("| MS.AAD.1.1v1 | low | A | proposed |", text)
        self.assertNotIn("(scuba-m365-v2.0.0)", text)
        flash = render_report(self.db, FLASH_ID)
        self.assertNotIn("(flash-20261113-001)", flash)
        self.assertIn("MS.AAD.1.1v1 (scuba-m365-v2.0.0)", flash)

    def test_pdf_annotates_cross_pack_citations(self):
        text = extract_text(render_pdf(self.db))
        self.assertIn("(scuba-m365-v2.0.0)", text)
        self.assertIn("(MS.AAD.1.1v1 (scuba-m365-v2.0.0))", text)


class StoredPackCollisionTest(DbCase):
    """An item id that several packs share is attributed to the pack
    the citation was validated against, whichever pack is rendered.

    FLASH (the fixture pack), aaa-first and zzz-late all contain
    R-1.1; the fix and the chain cite FLASH's.
    """

    FIX_ROW = "| F-COLLIDE | collision probe | {cite} | low | A | proposed |"
    CHAIN_LINE = (
        "Earliest breaking control: Collision control."
        " ({cite}) Status: absent."
    )
    ANNOTATED = "R-1.1 (flash-20261113-001)"

    def setUp(self):
        super().setUp()
        clear_primary_pack(self.db)
        with Store(self.db) as store:
            store.add_pack(small_pack(ZZZ_ID))
            store.add_pack(small_pack(AAA_ID))
        self.cli_ok(
            "add-fix", self.db, "--id", "F-COLLIDE",
            "--action", "collision probe", "--effort", "low",
            "--breaks", "A", "--rubric", "R-1.1",
            "--pack", FLASH_ID, "--date", "2026-11-22",
        )
        self.cli_ok(
            "add-chain", self.db, "--key", "Z", "--name", "Collision chain",
            "--control", "Collision control.",
            "--control-status", "absent",
            "--control-rubric", "R-1.1", "--pack", FLASH_ID,
            "--step", "Access: a probe step.",
        )

    def test_the_citation_stores_its_pack(self):
        with Store(self.db) as store:
            self.assertEqual(store.default_pack_id(), AAA_ID)
            fix = [
                f for f in store.list_fixes() if f["fix_id"] == "F-COLLIDE"
            ][0]
            self.assertEqual(fix["rubric_item_packs"], {"R-1.1": FLASH_ID})
            chain = [
                c for c in store.list_chains() if c["chain_key"] == "Z"
            ][0]
            self.assertEqual(chain["control_pack"], FLASH_ID)

    def test_fix_is_annotated_in_all_three_report_views(self):
        default = render_report(self.db)
        self.assertIn("- Rubric pack: Collision pack aaa-first", default)
        self.assertIn(self.FIX_ROW.format(cite=self.ANNOTATED), default)
        flash = render_report(self.db, FLASH_ID)
        self.assertIn(self.FIX_ROW.format(cite="R-1.1"), flash)
        self.assertNotIn("(flash-20261113-001)", flash)
        late = render_report(self.db, ZZZ_ID)
        self.assertIn(self.FIX_ROW.format(cite=self.ANNOTATED), late)
        self.assertEqual(render_report(self.db, AAA_ID), default)

    def test_chain_is_annotated_in_all_three_report_views(self):
        annotated = self.CHAIN_LINE.format(cite=self.ANNOTATED)
        self.assertIn(annotated, render_report(self.db))
        self.assertIn(annotated, render_report(self.db, ZZZ_ID))
        self.assertIn(
            self.CHAIN_LINE.format(cite="R-1.1"),
            render_report(self.db, FLASH_ID),
        )

    def test_a_citation_of_the_rendered_pack_stays_bare(self):
        # The same id cited from aaa-first: bare under aaa-first,
        # annotated with aaa-first everywhere else.
        self.cli_ok(
            "add-fix", self.db, "--id", "F-AAA",
            "--action", "aaa probe", "--effort", "low",
            "--breaks", "A", "--rubric", "R-1.1", "--date", "2026-11-22",
        )
        self.assertIn(
            "| F-AAA | aaa probe | R-1.1 | low |", render_report(self.db)
        )
        self.assertIn(
            "| F-AAA | aaa probe | R-1.1 (aaa-first) | low |",
            render_report(self.db, FLASH_ID),
        )
        self.assertIn(
            "| F-AAA | aaa probe | R-1.1 (aaa-first) | low |",
            render_report(self.db, ZZZ_ID),
        )

    def test_pdf_agrees_with_markdown(self):
        default = extract_text(render_pdf(self.db))
        self.assertIn("(R-1.1 (flash-20261113-001))", default)
        self.assertIn(self.ANNOTATED, extract_text(render_pdf(self.db, ZZZ_ID)))
        flash = extract_text(render_pdf(self.db, FLASH_ID))
        self.assertNotIn("(flash-20261113-001)", flash)
        self.assertIn("(R-1.1)", flash)

    def test_pdf_id_tracks_the_stored_pack(self):
        # Two databases that differ only in which pack a citation was
        # validated against render differently, so their /IDs differ.
        before = render_pdf(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "UPDATE fix_rubric SET pack_id = ? WHERE fix_pk ="
                " (SELECT id FROM fix WHERE fix_id = 'F-COLLIDE')",
                (ZZZ_ID,),
            )
            conn.commit()
        finally:
            conn.close()
        after = render_pdf(self.db)
        self.assertNotEqual(before, after)
        # The PDF table wraps the cell, so allow a line break.
        self.assertRegex(extract_text(after), r"R-1\.1\s+\(zzz-late\)")

    def test_web_writes_store_the_default_pack(self):
        from fencewalk.web import _apply_add_chain, _apply_add_fix
        with Store(self.db) as store:
            _apply_add_fix(store, {
                "id": ["F-WEB"], "action": ["web probe"], "effort": ["low"],
                "breaks": ["A"], "rubric": ["R-1.1"],
                "date": ["2026-11-22"],
            })
            _apply_add_chain(store, {
                "key": ["W"], "name": ["Web chain"],
                "control": ["Web control."], "control_status": ["absent"],
                "control_rubric": ["R-1.1"],
                "steps": ["Access: a web step."],
            })
            fix = [f for f in store.list_fixes() if f["fix_id"] == "F-WEB"][0]
            self.assertEqual(fix["rubric_item_packs"], {"R-1.1": AAA_ID})
            chain = [
                c for c in store.list_chains() if c["chain_key"] == "W"
            ][0]
            self.assertEqual(chain["control_pack"], AAA_ID)
        self.assertIn(
            "| F-WEB | web probe | R-1.1 (aaa-first) | low |",
            render_report(self.db, FLASH_ID),
        )

    def test_fixture_citations_carry_the_fixture_pack(self):
        with Store(self.db) as store:
            for fix in store.list_fixes():
                self.assertEqual(
                    fix["rubric_item_packs"],
                    {item: FLASH_ID for item in fix["rubric_item_ids"]},
                    fix["fix_id"],
                )
            for chain in store.list_chains():
                if chain["control_rubric"]:
                    self.assertEqual(chain["control_pack"], FLASH_ID)
                else:
                    self.assertIsNone(chain["control_pack"])


class CrossPackOwnersTest(DbCase):
    """0.3.5 (D2): cross_pack_citations maps each annotated item id
    to the sorted list of every distinct non-rendered pack that owns
    one of its citations, so two citations of one id under two packs
    both reach the PDF /ID. The rendered text is unchanged."""

    def _cite(self, fix_id, pack_id):
        with Store(self.db) as store:
            store.add_fix(
                1, fix_id, f"owner probe {fix_id}", "low", "A", ["R-1.1"],
                status="proposed", status_date="2026-11-22",
                status_actor="test", rubric_pack_id=pack_id,
            )

    def setUp(self):
        super().setUp()
        with Store(self.db) as store:
            store.add_pack(small_pack(ZZZ_ID))
            store.add_pack(small_pack(MID_ID))

    def test_fixture_has_no_cross_pack_citations(self):
        fresh = str(Path(self.tmp.name) / "fresh.db")
        load_fixture(FIXTURE_DIR, fresh)
        self.assertEqual(cross_pack_citations(gather_report_data(fresh)), {})

    def test_one_owner_is_a_one_element_list(self):
        self._cite("F-A", ZZZ_ID)
        self.assertEqual(
            cross_pack_citations(gather_report_data(self.db, FLASH_ID)),
            {"R-1.1": [ZZZ_ID]},
        )

    def test_two_owners_of_one_id_are_both_recorded(self):
        self._cite("F-A", MID_ID)
        self._cite("F-B", ZZZ_ID)
        data = gather_report_data(self.db, FLASH_ID)
        self.assertEqual(
            cross_pack_citations(data), {"R-1.1": [MID_ID, ZZZ_ID]}
        )
        # Sorted and distinct, whatever the citation order.
        self._cite("F-C", MID_ID)
        self.assertEqual(
            cross_pack_citations(gather_report_data(self.db, FLASH_ID)),
            {"R-1.1": [MID_ID, ZZZ_ID]},
        )
        # The rendered text still annotates each citation with its
        # own owner.
        md = render_report(self.db, FLASH_ID)
        self.assertIn("| F-A | owner probe F-A | R-1.1 (yyy-mid) |", md)
        self.assertIn("| F-B | owner probe F-B | R-1.1 (zzz-late) |", md)

    def test_rendered_pack_owner_is_left_out(self):
        self._cite("F-A", MID_ID)
        self._cite("F-B", ZZZ_ID)
        # Rendering zzz-late: the zzz-late citation is left out, the
        # yyy-mid one is annotated, and the FLASH fixture citations
        # are now cross-pack too (fixture fix F-16 cites FLASH R-1.1).
        cross = cross_pack_citations(gather_report_data(self.db, ZZZ_ID))
        self.assertEqual(cross["R-1.1"], [FLASH_ID, MID_ID])
        self.assertTrue(all(owners == [FLASH_ID]
                            for item, owners in cross.items()
                            if item != "R-1.1"))


class MigrationTest(unittest.TestCase):
    """A database from before 0.3.4 is never written by opening it
    (0.3.5); its first write migrates it — the two columns appear,
    determined packs are backfilled, every other row stays as it
    was — and it renders exactly as it did throughout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.new_db = str(Path(self.tmp.name) / "new.db")
        self.old_db = str(Path(self.tmp.name) / "old.db")
        load_fixture(FIXTURE_DIR, self.new_db)
        downgrade_copy(self.new_db, self.old_db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_old_schema_gains_the_columns_on_first_write(self):
        self.assertNotIn("pack_id", table_columns(self.old_db, "fix_rubric"))
        self.assertNotIn("control_pack", table_columns(self.old_db, "chain"))
        before = dump_rows(self.old_db)
        self.assertTrue(before["fix_rubric"])
        self.assertTrue(before["chain"])
        # Opening (and reading) does not migrate.
        with Store(self.old_db) as store:
            store.list_fixes()
            store.list_chains()
        self.assertNotIn("pack_id", table_columns(self.old_db, "fix_rubric"))
        self.assertNotIn("control_pack", table_columns(self.old_db, "chain"))
        # The first write does.
        with Store(self.old_db) as store:
            store.set_entry_label(
                "E5", "VERIFIED", date="2026-11-22", actor="operator"
            )
        self.assertEqual(
            table_columns(self.old_db, "fix_rubric"),
            table_columns(self.new_db, "fix_rubric"),
        )
        self.assertEqual(
            table_columns(self.old_db, "chain"),
            table_columns(self.new_db, "chain"),
        )
        # The fixture loads only FLASH, so every old citation's pack
        # is determined and the backfill restores exactly what a
        # 0.3.4 load stored: the migrated rows equal the new rows.
        after = dump_rows(self.old_db)
        new = dump_rows(self.new_db)
        self.assertEqual(after["fix_rubric"], new["fix_rubric"])
        self.assertEqual(after["chain"], new["chain"])
        # No other data changed, apart from the write itself.
        stripped = dump_rows(
            self.old_db, drop=("control_pack", "primary_pack")
        )
        for row in stripped["fix_rubric"]:
            del row["pack_id"]
        for table in ("inventory_entry", "entry_label_history"):
            del stripped[table]
            del before[table]
        self.assertEqual(stripped, before)
        # The migration adds the primary pack column and records none.
        self.assertEqual(
            table_columns(self.old_db, "engagement"),
            table_columns(self.new_db, "engagement"),
        )
        self.assertEqual(
            [r["primary_pack"] for r in after["engagement"]], [None]
        )

    def test_migration_writes_once_then_never_again(self):
        untouched = Path(self.old_db).read_bytes()
        Store(self.old_db).close()
        self.assertEqual(Path(self.old_db).read_bytes(), untouched)
        with Store(self.old_db) as store:
            store.set_entry_label(
                "E5", "VERIFIED", date="2026-11-22", actor="operator"
            )
        first = Path(self.old_db).read_bytes()
        Store(self.old_db).close()
        with Store(self.old_db) as store:
            self.assertEqual(store.migrate(), {
                "columns_added": 0,
                "fix_rubric_backfilled": 0,
                "chain_backfilled": 0,
            })
        self.assertEqual(Path(self.old_db).read_bytes(), first)
        # An up-to-date database is never written by opening it.
        fresh = Path(self.new_db).read_bytes()
        Store(self.new_db).close()
        self.assertEqual(Path(self.new_db).read_bytes(), fresh)

    def test_old_rows_read_with_null_packs(self):
        with Store(self.old_db) as store:
            fixes = store.list_fixes()
            self.assertTrue(fixes)
            for fix in fixes:
                self.assertEqual(
                    fix["rubric_item_packs"],
                    {item: None for item in fix["rubric_item_ids"]},
                    fix["fix_id"],
                )
            self.assertTrue(any(f["rubric_item_ids"] for f in fixes))
            for chain in store.list_chains():
                # Un-migrated: the column, and so the key, is absent;
                # every reader uses .get("control_pack").
                self.assertIsNone(chain.get("control_pack"))
        self.assertNotIn("pack_id", table_columns(self.old_db, "fix_rubric"))

    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "root ignores file permissions",
    )
    def test_read_only_old_database_reads_through_the_cli(self):
        # 0.3.5: a pre-0.3.4 database on read-only storage opens, and
        # every read command exits 0 leaving the file's bytes and
        # mtime unchanged. (packet is not a read: it records the
        # packet, so on a read-only file it fails cleanly.)
        db = Path(self.old_db)
        db.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        try:
            before = (db.read_bytes(), os.stat(db).st_mtime_ns)
            out = str(Path(self.tmp.name) / "out")
            for argv in (
                ["report", self.old_db],
                ["checklist", self.old_db],
                ["pdf", self.old_db, "--out", out + ".pdf"],
                ["list-coverage", self.old_db, "--pack", FLASH_ID],
            ):
                code, _, err = run_cli(argv)
                self.assertEqual(code, 0, f"{argv[0]}: {err}")
            code, _, err = run_cli(
                ["packet", self.old_db, "--out", out + ".md"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(err, "error: attempt to write a readonly database\n")
            self.assertEqual((db.read_bytes(), os.stat(db).st_mtime_ns), before)
            self.assertNotIn("pack_id", table_columns(self.old_db, "fix_rubric"))
        finally:
            db.chmod(stat.S_IRUSR | stat.S_IWUSR)

    def test_migrated_database_renders_exactly_as_before(self):
        expected = EXPECTED_REPORT.read_text(encoding="utf-8")
        self.assertEqual(render_report(self.old_db), expected)
        self.assertEqual(render_report(self.new_db), expected)
        self.assertEqual(render_pdf(self.old_db), render_pdf(self.new_db))

    def test_null_packs_fall_back_to_the_item_lookup(self):
        # Old rows carry no pack, so the report resolves them as
        # 0.3.3 did: the rendered pack first, then pack_id order.
        # F-1 gains an old-style (no pack) citation of R-1.1, which
        # FLASH and both small packs contain. The two small packs go
        # in through raw sqlite3, as a pre-0.3.4 tool would have
        # loaded them: a Store write would migrate first (0.3.5), and
        # the backfill would then pin R-1.1 to FLASH while it was
        # still the only pack — this test is about the ambiguous case.
        conn = sqlite3.connect(self.old_db)
        try:
            conn.execute(
                "INSERT INTO fix_rubric (fix_pk, item_id)"
                " SELECT id, 'R-1.1' FROM fix WHERE fix_id = 'F-1'"
            )
            for pack_id in (ZZZ_ID, AAA_ID):
                pack = small_pack(pack_id)
                conn.execute(
                    "INSERT INTO rubric_pack"
                    " (pack_id, title, source_citation, version)"
                    " VALUES (?, ?, ?, ?)",
                    (pack["pack_id"], pack["title"],
                     pack["source_citation"], pack["version"]),
                )
                for item in pack["items"]:
                    conn.execute(
                        "INSERT INTO rubric_item"
                        " (pack_id, item_id, group_name, text)"
                        " VALUES (?, ?, ?, ?)",
                        (pack["pack_id"], item["item_id"],
                         item["group"], item["text"]),
                    )
            conn.commit()
        finally:
            conn.close()
        fallback = "| R-1.1, R-4.3 (flash-20261113-001) |"
        flash_view = "| R-1.1, R-4.3 |"
        for pack in (None, AAA_ID, ZZZ_ID):
            self.assertIn(fallback, render_report(self.old_db, pack), pack)
        self.assertIn(flash_view, render_report(self.old_db, FLASH_ID))
        # After a write migrates the database, R-1.1 (in three packs)
        # keeps its NULL and its fallback; R-4.3 (FLASH only) is
        # backfilled to FLASH — the owner the fallback already gave
        # it — so every rendering is unchanged.
        with Store(self.old_db) as store:
            store.set_entry_label(
                "E5", "VERIFIED", date="2026-11-22", actor="operator"
            )
            f1 = [f for f in store.list_fixes() if f["fix_id"] == "F-1"][0]
        self.assertEqual(f1["rubric_item_packs"], {
            "R-1.1": None, "R-4.3": FLASH_ID,
        })
        for pack in (None, AAA_ID, ZZZ_ID):
            self.assertIn(fallback, render_report(self.old_db, pack), pack)
        self.assertIn(flash_view, render_report(self.old_db, FLASH_ID))

    def test_new_writes_on_a_migrated_database_store_the_pack(self):
        code, _, err = run_cli([
            "add-fix", self.old_db, "--id", "F-NEW", "--action", "new fix",
            "--effort", "low", "--breaks", "A", "--rubric", "R-1.1",
            "--date", "2026-11-22",
        ])
        self.assertEqual(code, 0, err)
        with Store(self.old_db) as store:
            fix = [f for f in store.list_fixes() if f["fix_id"] == "F-NEW"][0]
            self.assertEqual(fix["rubric_item_packs"], {"R-1.1": FLASH_ID})

    def test_uninitialised_database_is_left_for_init_schema(self):
        blank = str(Path(self.tmp.name) / "blank.db")
        with Store(blank) as store:
            self.assertEqual(table_columns(blank, "fix_rubric"), [])
            store.init_schema()
        self.assertIn("pack_id", table_columns(blank, "fix_rubric"))
        self.assertIn("control_pack", table_columns(blank, "chain"))


class PdfSubstitutionNoteTest(DbCase):
    NOTE = (
        'Note: {n} character(s) in this report could not be represented'
        ' in the PDF font and appear as "?".'
    )

    def _set_reasoning(self, item_id, suffix):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "UPDATE coverage_score SET reasoning = reasoning || ?"
                " WHERE item_id = ?", (suffix, item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _last_content_line(self, text):
        # The last page ends: ..., last content line, footer, page no.
        return text.splitlines()[-3]

    def test_fixture_pdf_has_no_note(self):
        text = extract_text(render_pdf(self.db))
        self.assertNotIn("could not be represented", text)

    def test_note_counts_one_substitution(self):
        self._set_reasoning("R-1.4", " Next → R-3.3.")
        md = render_report(self.db)
        self.assertIn("Next → R-3.3.", md)
        self.assertNotIn("could not be represented", md)
        text = extract_text(render_pdf(self.db))
        self.assertRegex(text, r"Next\s+\?\s+R-3\.3\.")
        self.assertEqual(self._last_content_line(text), self.NOTE.format(n=1))

    def test_note_counts_every_substitution(self):
        self._set_reasoning("R-1.4", " → ✓")
        self._set_reasoning("R-3.3", " ≥ é")  # é is outside the table
        text = extract_text(render_pdf(self.db))
        self.assertEqual(self._last_content_line(text), self.NOTE.format(n=4))

    def test_note_render_is_deterministic(self):
        self._set_reasoning("R-1.4", " → ")
        self.assertEqual(render_pdf(self.db), render_pdf(self.db))


if __name__ == "__main__":
    unittest.main()
