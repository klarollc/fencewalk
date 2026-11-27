"""Deeper Slice 1 tests: the adversarial second pass.

`fencewalk packet --posture adversarial` assembles a packet whose brief
(templates/adversarial-brief.md) attacks the standing scores, with a
standing-coverage section between the brief and the inventory. The
default posture is the standard packet, whose bytes never change: every
fixture's golden packet at its own packet date is pinned here. The
posture is recorded on packet_record (a lazily migrated, nullable
column; records from before it read as 'standard'), and ingest, draft
and adjudicate run against an adversarial packet's hash unchanged."""

import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.packet import (
    ADVERSARIAL_TEMPLATE_PATH,
    PLACEHOLDERS,
    TEMPLATE_PATH,
    assemble_packet,
)
from fencewalk.store import InvariantError, Store

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "src" / "fencewalk" / "fixtures"
PACKS = REPO_ROOT / "src" / "fencewalk" / "packs"

# Every fixture's golden default packet at that fixture's own packet
# date: (date, byte count, sha256), as pinned in the fixture tests and
# tests/test_model_api.py at the base of this slice. The reference
# case's golden is the fictional fixture's, at its created date.
GOLDEN_PACKETS = {
    "reference-case": (
        "2026-11-05", 18732,
        "e59fc847d218018aa9035dda9fa0ee47269cef1927a27d153c78ae59e7a646d7",
    ),
    "demo-scuba": (
        "2026-10-15", 30166,
        "270dbc5243d4a459edb9c367be082af099762efbf5877adeacd734f53b2cda3d",
    ),
    "github-org": (
        "2026-11-21", 17262,
        "7749f3eb0b76cf1e8c7d8e241e51853eca6418a36faeffa54ce88a70d64704a5",
    ),
    "dns-registrar": (
        "2026-11-20", 15758,
        "3a65cbcabb189943f83a0dfa08cca321bf260a68c6ac9daac485fe5048cb45de",
    ),
    "google-workspace": (
        "2026-11-18", 26727,
        "9f870c739b11bbb3982785b38e1d8eda0b33e44711e29a6383d7a99657a66081",
    ),
}

SYNTHETIC_OUTPUT = """Synthetic adversarial run output.

## Coverage challenges

| ID | Proposed status | Holds/Challenged | Reasoning |
|---|---|---|---|
| R-3.1 | Partial | Challenged | Insufficient evidence: C5 and C6 cover the checkout, but nothing on record limits the donor-management service. |
| R-3.3 | Covered | Holds | C8 is VERIFIED and covers the error-page probe. |

Most material: R-3.1.
"""


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


def packet_record_columns(db):
    with closing(sqlite3.connect(db)) as conn:
        return [r[1] for r in conn.execute("PRAGMA table_info(packet_record)")]


class _FixtureDbCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, fixture, name=None):
        db = str(self.dir / f"{name or fixture}.db")
        code, _, err = run_cli(["load-fixture", str(FIXTURES / fixture), db])
        self.assertEqual(code, 0, err)
        return db

    def packet(self, db, date, posture=None, name="packet.md", extra=()):
        out = self.dir / name
        argv = ["packet", db, "--date", date, "--out", str(out), *extra]
        if posture is not None:
            argv += ["--posture", posture]
        code, stdout, err = run_cli(argv)
        self.assertEqual(code, 0, err)
        return out.read_bytes(), stdout


class DefaultPostureGoldenTests(_FixtureDbCase):
    """The headline gate: under the default posture every fixture's
    packet at its own packet date is its golden, byte for byte."""

    def test_every_fixture_default_packet_is_its_golden(self):
        for fixture, (date, size, sha) in GOLDEN_PACKETS.items():
            with self.subTest(fixture=fixture):
                db = self.load(fixture)
                data, stdout = self.packet(db, date, name=f"{fixture}.md")
                self.assertEqual(len(data), size)
                self.assertEqual(hashlib.sha256(data).hexdigest(), sha)
                self.assertNotIn("posture", stdout)

    def test_explicit_standard_is_the_default(self):
        for fixture, (date, _size, sha) in GOLDEN_PACKETS.items():
            with self.subTest(fixture=fixture):
                db = self.load(fixture)
                data, _ = self.packet(db, date, posture="standard",
                                      name=f"{fixture}.md")
                self.assertEqual(hashlib.sha256(data).hexdigest(), sha)

    def test_default_packet_unchanged_after_adversarial_state(self):
        # A database carrying adversarial packet records, a run and an
        # adjudication still assembles the golden default packet.
        date, _size, sha = GOLDEN_PACKETS["reference-case"]
        db = self.load("reference-case")
        _, stdout = self.packet(db, date, posture="adversarial", name="a.md")
        adv_hash = printed_value(stdout, "sha256:")
        out_file = self.dir / "out.md"
        out_file.write_text(SYNTHETIC_OUTPUT, encoding="utf-8")
        code, _, err = run_cli(["ingest", db, str(out_file),
                                "--packet-hash", adv_hash,
                                "--date", "2026-11-25"])
        self.assertEqual(code, 0, err)
        code, _, err = run_cli(["adjudicate", db, "--run", "1",
                                "--section", "coverage",
                                "--decision", "accept",
                                "--date", "2026-11-25"])
        self.assertEqual(code, 0, err)
        data, _ = self.packet(db, date, name="std.md")
        self.assertEqual(hashlib.sha256(data).hexdigest(), sha)

    def test_standard_template_carries_no_adversarial_text(self):
        text = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Run brief — {engagement_name}"))
        self.assertNotIn("adversarial", text.lower())
        self.assertNotIn("standing", text.lower())


class AdversarialPacketTests(_FixtureDbCase):
    DATE = "2026-11-22"

    def setUp(self):
        super().setUp()
        self.db = self.load("reference-case")
        self.data, self.stdout = self.packet(
            self.db, self.DATE, posture="adversarial"
        )
        self.text = self.data.decode("utf-8")
        scores = json.loads(
            (FIXTURES / "reference-case" / "coverage.json")
            .read_text(encoding="utf-8")
        )["scores"]
        self.scores = scores

    def section(self, heading):
        start = self.text.index(f"\n{heading}\n")
        end = self.text.index("\n---\n", start)
        return self.text[start:end]

    def test_configuration_block_names_the_posture(self):
        config = self.text.split("\n---\n", 1)[0]
        self.assertIn(
            "- Posture: adversarial (second pass against the standing scores)",
            config.splitlines(),
        )
        self.assertIn("the adversarial brief, the standing coverage,"
                      " the inventory, and the rubric", config)
        self.assertIn("Fencewalk does not call a model API", config)

    def test_contents_in_order(self):
        positions = [
            self.text.index("**Run configuration (record for adjudication)**"),
            self.text.index("\n# Adversarial brief — "),
            self.text.index("\n# Standing coverage\n"),
            self.text.index("\n# Inventory\n"),
            self.text.index("\n# Rubric\n"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("# Run brief —", self.text)

    def test_every_scored_item_carries_its_standing_score(self):
        section = self.section("# Standing coverage")
        with closing(Store(self.db)) as store:
            labels = {e["entry_id"]: e["label"] for e in store.list_inventory()}
        for score in self.scores:
            with self.subTest(item=score["item_id"]):
                self.assertIn(
                    f"- **{score['item_id']}** — {score['status']}\n"
                    f"  Reasoning: {score['reasoning']}\n",
                    section,
                )
                if score["na_reason"]:
                    self.assertIn(f"  N/A reason: {score['na_reason']}", section)
                for entry_id in score["cited_entry_ids"]:
                    self.assertIn(f"**{entry_id}** ({labels[entry_id]})", section)
        self.assertIn("20 of 20 items scored, 0 unscored", section)
        self.assertIn("  Cited: none", section)

    def test_brief_substance_and_full_substitution(self):
        brief = self.section("# Adversarial brief — Reference case — "
                             "Marigold Community Food Bank perimeter audit")
        for token in PLACEHOLDERS:
            self.assertNotIn(token, self.text)
        for phrase in (
            "make the strongest honest case that the standing status is wrong",
            "**Insufficient evidence.**",
            "**Overclaiming reasoning.**",
            "**Citations that do not support the status.**",
            "propose the status the evidence actually supports",
            "say so in one line",
            "They are out of scope: make no proposals for them.",
            "Coverage challenges",
            "| ID | Proposed status | Holds/Challenged | Reasoning |",
            "exactly one of Covered, Partial, Gap, Unknown, Not applicable,"
            " written alone",
            "repeat the standing status here",
            "This is the only cell in the row that holds a status",
            "the word Holds or the word Challenged",
            "under roughly 2500 words",
        ):
            self.assertIn(phrase, brief)

    def test_inventory_and_rubric_match_the_standard_packet(self):
        std, _ = self.packet(self.db, self.DATE, name="std.md")
        std = std.decode("utf-8")
        tail = self.text[self.text.index("\n# Inventory\n"):]
        self.assertEqual(tail, std[std.index("\n# Inventory\n"):])

    def test_repeat_is_byte_identical_and_hash_and_posture_recorded(self):
        again, stdout2 = self.packet(self.db, self.DATE, posture="adversarial",
                                     name="again.md")
        self.assertEqual(again, self.data)
        sha = hashlib.sha256(self.data).hexdigest()
        self.assertEqual(printed_value(self.stdout, "sha256:"), sha)
        self.assertEqual(printed_value(self.stdout, "posture:"), "adversarial")
        self.assertEqual(printed_value(stdout2, "sha256:"), sha)
        with closing(Store(self.db)) as store:
            record = store.get_packet_by_hash(sha)
            self.assertEqual(record["posture"], "adversarial")
            self.assertEqual(record["byte_count"], len(self.data))
            self.assertEqual([p["posture"] for p in store.list_packets()],
                             ["adversarial", "adversarial"])

    def test_standard_packet_records_standard(self):
        data, _ = self.packet(self.db, self.DATE, name="std.md")
        sha = hashlib.sha256(data).hexdigest()
        with closing(sqlite3.connect(self.db)) as conn:
            raw = conn.execute(
                "SELECT posture FROM packet_record WHERE sha256 = ?", (sha,)
            ).fetchone()[0]
        self.assertEqual(raw, "standard")

    def test_ingest_draft_adjudicate_run_against_the_adversarial_hash(self):
        sha = printed_value(self.stdout, "sha256:")
        out_file = self.dir / "out.md"
        out_file.write_text(SYNTHETIC_OUTPUT, encoding="utf-8")
        code, stdout, err = run_cli(["ingest", self.db, str(out_file),
                                     "--packet-hash", sha,
                                     "--model", "synthetic/adversarial",
                                     "--date", "2026-11-25"])
        self.assertEqual(code, 0, err)
        self.assertIn("ingested model run 1", stdout)
        code, draft, err = run_cli(["draft", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn(f"- Packet hash: {sha}", draft)
        coverage = draft[draft.index("## Coverage map"):]
        self.assertIn("## Coverage challenges", coverage)
        self.assertIn("| R-3.1 | Partial | Challenged |", coverage)
        code, _, err = run_cli(["adjudicate", self.db, "--run", "1",
                                "--section", "coverage",
                                "--decision", "correct",
                                "--note", "R-3.1 to Partial, rescore by hand",
                                "--date", "2026-11-25"])
        self.assertEqual(code, 0, err)
        code, stdout, err = run_cli(["adjudications", self.db, "--run", "1"])
        self.assertEqual(code, 0, err)
        self.assertIn("coverage: correct (2026-11-25, operator)", stdout)


class UnscoredItemsTests(_FixtureDbCase):
    def test_unscored_items_are_listed_as_unscored(self):
        db = self.load("reference-case")
        pack_file = PACKS / "ncsc-cyber-essentials-3.3.json"
        pack = json.loads(pack_file.read_text(encoding="utf-8"))
        code, _, err = run_cli(["load-pack", db, str(pack_file)])
        self.assertEqual(code, 0, err)
        first = pack["items"][0]["item_id"]
        code, _, err = run_cli(["score", db, "--pack", pack["pack_id"],
                                "--item", first, "--status", "Partial",
                                "--reasoning", "Boundary firewall on record only.",
                                "--cite", "E2"])
        self.assertEqual(code, 0, err)
        data, _ = self.packet(db, "2026-11-22", posture="adversarial",
                              extra=["--pack", pack["pack_id"]])
        text = data.decode("utf-8")
        total = len(pack["items"])
        self.assertIn(f"1 of {total} items scored, {total - 1} unscored", text)
        self.assertIn(f"- **{first}** — Partial\n"
                      "  Reasoning: Boundary firewall on record only.\n"
                      "  Cited: **E2** (ON RECORD)", text)
        for item in pack["items"][1:]:
            self.assertIn(f"- **{item['item_id']}** — unscored\n", text)


class MigrationTests(_FixtureDbCase):
    """A database whose packet_record predates the posture column (as
    base code builds it) gains the column on its first packet write,
    never on a read, and its existing records read as 'standard'."""

    def base_shape_db(self):
        db = self.load("reference-case")
        date, _size, sha = GOLDEN_PACKETS["reference-case"]
        self.packet(db, date, name="p0.md")
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("ALTER TABLE packet_record DROP COLUMN posture")
            conn.commit()
        self.assertNotIn("posture", packet_record_columns(db))
        return db, sha

    def test_reads_never_add_the_column_and_old_records_read_standard(self):
        db, sha = self.base_shape_db()
        before = Path(db).read_bytes()
        for argv in (["report", db, "--out", str(self.dir / "r.md")],
                     ["list-coverage", db, "--pack", "flash-20261113-001"],
                     ["checklist", db, "--date", "2026-11-25"]):
            code, _, err = run_cli(argv)
            self.assertEqual(code, 0, err)
        with closing(Store(db)) as store:
            self.assertEqual([p["posture"] for p in store.list_packets()],
                             ["standard"])
            self.assertEqual(store.get_packet_by_hash(sha)["posture"],
                             "standard")
        self.assertNotIn("posture", packet_record_columns(db))
        self.assertEqual(Path(db).read_bytes(), before)

    def test_first_packet_write_adds_the_column(self):
        db, _sha = self.base_shape_db()
        _, stdout = self.packet(db, "2026-11-22", posture="adversarial",
                                name="p1.md")
        self.assertIn("posture", packet_record_columns(db))
        with closing(sqlite3.connect(db)) as conn:
            raw = conn.execute(
                "SELECT posture FROM packet_record ORDER BY id"
            ).fetchall()
        self.assertEqual(raw, [(None,), ("adversarial",)])
        with closing(Store(db)) as store:
            self.assertEqual([p["posture"] for p in store.list_packets()],
                             ["standard", "adversarial"])
        self.assertEqual(printed_value(stdout, "posture:"), "adversarial")

    def test_database_without_model_pass_tables_gets_the_column(self):
        # A database from before the model-pass tables: packet_record is
        # created lazily, after migrate has run, and still carries it.
        db = self.load("reference-case")
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("DROP TABLE adjudication")
            conn.execute("DROP TABLE model_run")
            conn.execute("DROP TABLE packet_record")
            conn.commit()
        self.packet(db, "2026-11-22", posture="adversarial")
        self.assertIn("posture", packet_record_columns(db))
        with closing(Store(db)) as store:
            self.assertEqual([p["posture"] for p in store.list_packets()],
                             ["adversarial"])


class RefusalTests(_FixtureDbCase):
    def test_store_refuses_an_unknown_posture_and_writes_nothing(self):
        db = self.load("reference-case")
        with closing(Store(db)) as store:
            eng = store.get_engagement()
            with self.assertRaises(InvariantError):
                store.record_packet(eng["id"], "flash-20261113-001",
                                    "2026-11-22", 2500, 10, "a" * 64,
                                    posture="lenient")
            self.assertEqual(store.list_packets(), [])

    def test_assemble_refuses_unknown_posture_and_api_adversarial(self):
        db = self.load("reference-case")
        with self.assertRaises(ValueError):
            assemble_packet(db, assembled_date="2026-11-22", posture="lenient")
        with self.assertRaises(ValueError):
            assemble_packet(db, assembled_date="2026-11-22", run_via="api",
                            model_label="anthropic/x", posture="adversarial")

    def test_cli_rejects_an_unknown_posture(self):
        db = self.load("reference-case")
        with self.assertRaises(SystemExit):
            run_cli(["packet", db, "--out", str(self.dir / "x.md"),
                     "--posture", "lenient"])
        self.assertFalse((self.dir / "x.md").exists())

    def test_adversarial_template_uses_only_the_known_placeholders(self):
        import re
        text = ADVERSARIAL_TEMPLATE_PATH.read_text(encoding="utf-8")
        found = set(re.findall(r"\{[a-z_]+\}", text))
        self.assertEqual(found, set(PLACEHOLDERS))


if __name__ == "__main__":
    unittest.main()
