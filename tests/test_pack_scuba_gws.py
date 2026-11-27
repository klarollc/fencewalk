"""CISA SCuBA Google Workspace pack tests (scuba-gws-v1.1.0).

The pack is the CISA SCuBA Google Workspace baselines as published with
ScubaGoggles v1.1.0 (CC0 1.0), extracted the way the shipped scuba-m365
pack was: one item per policy heading, the CISA policy ID verbatim, the
policy statement verbatim. Classroom, Gemini and Assured Controls are not
included. These tests pin the header, the 124 items in 8 groups with the
per-group counts machine-counted from the pinned baseline files, the CISA
ID shape and each ID's product prefix matching its group, and that the
pack validates and loads through the one validator and load-pack.
"""

import io
import re
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import bundled_pack_path, load_pack, validate_pack
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "scuba-gws-v1.1.0.json"
PACK_ID = "scuba-gws-v1.1.0"

# Group, CISA product prefix, policy count at the pin (ScubaGoggles v1.1.0).
GROUPS = [
    ("Common Controls", "COMMONCONTROLS", 42),
    ("Gmail", "GMAIL", 36),
    ("Drive and Docs", "DRIVEDOCS", 17),
    ("Google Chat", "CHAT", 7),
    ("Google Meet", "MEET", 9),
    ("Google Calendar", "CALENDAR", 6),
    ("Google Groups", "GROUPS", 6),
    ("Google Sites", "SITES", 1),
]
CISA_ID = re.compile(r"^GWS\.([A-Z]+)\.(\d+)\.(\d+)v(\d+)$")


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ScubaGwsPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(PACK_PATH)
        cls.items = cls.pack["items"]
        cls.text = {i["item_id"]: i["text"] for i in cls.items}

    def test_header(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(
            self.pack["title"],
            "CISA SCuBA Google Workspace Secure Configuration Baselines"
            " (ScubaGoggles v1.1.0)",
        )
        self.assertEqual(self.pack["version"], "1.1.0")
        self.assertEqual(
            self.pack["source_citation"],
            "CISA Secure Cloud Business Applications (SCuBA) Google Workspace"
            " baselines, as published with ScubaGoggles v1.1.0 (released Oct 22,"
            " 2026; https://github.com/cisagov/ScubaGoggles/releases/tag/v1.1.0),"
            " CC0 1.0 Universal. Three baselines are not included: Classroom (an"
            " education-sector product), Gemini and Assured Controls (separately"
            " purchased add-ons).",
        )

    def test_exact_keys(self):
        self.assertEqual(
            sorted(self.pack),
            ["items", "pack_id", "source_citation", "title", "version"],
        )
        for item in self.items:
            self.assertEqual(sorted(item), ["group", "item_id", "text"], item)

    def test_validates(self):
        self.assertIs(validate_pack(self.pack), self.pack)

    def test_124_items_in_8_groups_with_pinned_counts(self):
        self.assertEqual(len(self.items), 124)
        self.assertEqual(
            Counter(i["group"] for i in self.items),
            Counter({g: n for g, _, n in GROUPS}),
        )
        self.assertEqual(
            list(dict.fromkeys(i["group"] for i in self.items)),
            [g for g, _, _ in GROUPS],
        )

    def test_ids_unique_cisa_shaped_and_in_their_group(self):
        ids = [i["item_id"] for i in self.items]
        self.assertEqual(len(set(ids)), 124)
        group_of = {prefix: g for g, prefix, _ in GROUPS}
        for item in self.items:
            m = CISA_ID.match(item["item_id"])
            self.assertIsNotNone(m, item["item_id"])
            self.assertEqual(item["group"], group_of[m.group(1)], item["item_id"])
        for excluded in ("CLASSROOM", "GEMINI", "ASSUREDCONTROLS"):
            self.assertFalse(any(f"GWS.{excluded}." in i for i in ids), excluded)

    def test_statements_verbatim_samples(self):
        self.assertEqual(self.text["GWS.COMMONCONTROLS.1.1v1"],
                         "Phishing-Resistant MFA SHALL be required for all users.")
        # Statement only: the list that follows it in the baseline is dropped.
        self.assertEqual(
            self.text["GWS.COMMONCONTROLS.14.1v1"],
            "The following critical logs SHALL be sent to the agency's"
            " centralized SIEM.")
        self.assertEqual(self.text["GWS.GMAIL.4.2v1"],
                         "The DMARC message rejection option SHALL be p=reject.")
        self.assertEqual(
            self.text["GWS.DRIVEDOCS.1.5v1"],
            "Any Organizational Units that allow external sharing SHOULD disable"
            " content availability to \"anyone with the link.\"")
        self.assertEqual(self.text["GWS.SITES.1.1v1"],
                         "Sites Service SHOULD be disabled for all users.")

    def test_every_statement_is_one_normative_line(self):
        for item in self.items:
            text = item["text"]
            self.assertEqual(text, " ".join(text.split()), item["item_id"])
            self.assertRegex(text, r"\b(SHALL|SHOULD)\b", item["item_id"])
            self.assertNotRegex(text, r"^[-*>#]|\[!\[|_Rationale", item["item_id"])

    def test_bundled_by_name(self):
        self.assertEqual(bundled_pack_path(PACK_ID), PACK_PATH)

    def test_load_pack_into_scratch_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "scratch.db")
            code, _, err = run_cli([
                "new", db, "--name", "Pack load", "--subject", "Test firm",
                "--method-order", "verify-first", "--date", "2026-11-24",
            ])
            self.assertEqual(code, 0, err)
            code, out, err = run_cli(["load-pack", db, PACK_ID])
            self.assertEqual(code, 0, err)
            self.assertIn(PACK_ID, out)
            store = Store(db)
            try:
                items = store.list_pack_items(PACK_ID)
            finally:
                store.close()
        self.assertEqual(len(items), 124)
        self.assertEqual(len({i["group_name"] for i in items}), 8)


if __name__ == "__main__":
    unittest.main()
