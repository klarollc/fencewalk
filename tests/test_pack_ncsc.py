"""NCSC Cyber Essentials content pack tests: the NCSC Cyber Essentials
Requirements for IT Infrastructure v3.3, as shipped data.

Like the ASD pack this one is curated, not verbatim: the requirements
document states its requirements as prose with bullet lists, not as
numbered policy statements, so one pack item is one requirement
statement synthesised from the document, per the derivation rule in
brief fencewalk-ncsc-pack-brief-20261122.md, section 3 (lead
paragraphs, top-level bullets, and named sub-block musts; sub-bullets,
notes, the passwordless subsection, and the factor-type list are not
items). These tests pin the derived numbers: 39 items in 5 groups, the
five worked examples verbatim, and the thresholds verbatim. The
derivation itself is documented in the handback, with a per-item source
map (every item to its control, subsection, and bullet/paragraph).

One pinned negative: the pack carries no " Requires: " suffix. Cyber
Essentials states no licence or capability requirement.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import load_pack, validate_pack
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = (
    REPO_ROOT / "src" / "fencewalk" / "packs"
    / "ncsc-cyber-essentials-3.3.json"
)
PACK_ID = "ncsc-cyber-essentials-3.3"

# Golden counts, measured from the pinned PDF (NCSC Cyber Essentials:
# Requirements for IT Infrastructure v3.3, April 2026, section E,
# PDF pp.13-24; see handback). Counts below are compared against
# counts computed from the loaded pack.
EXPECTED_GROUP_COUNTS = {
    "Firewalls": 7,
    "Secure Configuration": 9,
    "Security Update Management": 4,
    "User Access Control": 12,
    "Malware protection": 7,
}


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class NcscPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)

    def test_validates(self):
        validated = validate_pack(load_pack(PACK_PATH))
        self.assertEqual(validated["pack_id"], PACK_ID)

    def test_pack_identity(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(self.pack["version"], "3.3")
        self.assertIn("NCSC Cyber Essentials", self.pack["title"])
        self.assertIn("Requirements for IT Infrastructure", self.pack["title"])
        self.assertIn("v3.3", self.pack["title"])
        self.assertIn("April 2026", self.pack["source_citation"])
        self.assertIn("© Crown copyright 2026", self.pack["source_citation"])
        self.assertIn("Open Government Licence v3.0",
                      self.pack["source_citation"])

    def test_item_keys_exact(self):
        for item in self.pack["items"]:
            self.assertEqual(set(item.keys()), {"group", "item_id", "text"})

    def test_39_items(self):
        self.assertEqual(len(self.pack["items"]), 39)

    def test_unique_ids(self):
        ids = [i["item_id"] for i in self.pack["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_per_group_counts(self):
        counts = {}
        for item in self.pack["items"]:
            counts[item["group"]] = counts.get(item["group"], 0) + 1
        self.assertEqual(counts, EXPECTED_GROUP_COUNTS)

    def test_single_sentence_texts(self):
        for item in self.pack["items"]:
            self.assertNotIn("\n", item["text"], item["item_id"])
            self.assertTrue(item["text"].endswith("."), item["item_id"])

    def test_no_requires_suffixes(self):
        # Cyber Essentials states no licence or capability requirement
        # (handback); the pack has none.
        suffixed = [i for i in self.pack["items"] if " Requires: " in i["text"]]
        self.assertEqual(suffixed, [])

    def _text_of(self, item_id):
        return next(
            i["text"] for i in self.pack["items"] if i["item_id"] == item_id
        )

    def test_worked_example_fw_01(self):
        self.assertEqual(
            self._text_of("NCSC-CE-FW-01"),
            "Every device in scope is protected by a correctly "
            "configured firewall, or by a network device with firewall "
            "functionality.",
        )

    def test_worked_example_sc_01(self):
        self.assertEqual(
            self._text_of("NCSC-CE-SC-01"),
            "Unnecessary user accounts, such as guest accounts and "
            "administrative accounts that will not be used, are removed "
            "and disabled.",
        )

    def test_worked_example_um_04(self):
        self.assertEqual(
            self._text_of("NCSC-CE-UM-04"),
            "Software is updated, including vulnerability fixes, within "
            "14 days of release where the vendor describes the "
            "vulnerabilities as critical or high risk, where they carry "
            "a CVSS v3 base score of 7 or above, or where the vendor "
            "provides no details of the level of vulnerabilities the "
            "update fixes.",
        )

    def test_worked_example_ua_04(self):
        self.assertEqual(
            self._text_of("NCSC-CE-UA-04"),
            "Multi-factor authentication is implemented where "
            "available, and authentication to cloud services always "
            "uses multi-factor authentication.",
        )

    def test_worked_example_mp_06(self):
        self.assertEqual(
            self._text_of("NCSC-CE-MP-06"),
            "Only approved applications, restricted by code signing, "
            "are allowed to execute on devices, and applications are "
            "actively approved before being deployed to devices.",
        )

    def test_thresholds(self):
        text = self._text_of
        self.assertIn("14 days", text("NCSC-CE-UM-04"))
        self.assertIn("CVSS v3 base score of 7", text("NCSC-CE-UM-04"))
        self.assertIn("10 guesses in 5 minutes", text("NCSC-CE-SC-08"))
        self.assertIn("10 unsuccessful attempts", text("NCSC-CE-SC-08"))
        self.assertIn("10 guesses in 5 minutes", text("NCSC-CE-UA-09"))
        self.assertIn("10 unsuccessful attempts", text("NCSC-CE-UA-09"))
        self.assertIn("12 characters", text("NCSC-CE-UA-10"))
        self.assertIn("8 characters", text("NCSC-CE-UA-10"))
        self.assertIn("8 characters", text("NCSC-CE-UA-08"))
        self.assertIn("6 characters", text("NCSC-CE-SC-09"))


class NcscPackStoreTest(unittest.TestCase):
    """Load the pack through the store API; list-coverage sees 39 items."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "NCSC pack test",
            "--subject", "Test firm", "--method-order", "verify-first",
            "--date", "2026-11-22",
        ])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_pack_and_list_coverage(self):
        # The CLI's list-coverage lists store.list_pack_items(); the
        # score rows (store.list_coverage) are empty until items are
        # scored. Assert the pack items through the store API.
        store = Store(self.db)
        try:
            store.add_pack(validate_pack(load_pack(PACK_PATH)))
            rows = store.list_pack_items(PACK_ID)
        finally:
            store.close()
        self.assertEqual(len(rows), 39)
        groups = {r["group_name"] for r in rows}
        self.assertEqual(len(groups), 5)
        self.assertEqual(groups, set(EXPECTED_GROUP_COUNTS))

    def test_packs_lists_new_pack(self):
        code, out, err = run_cli(["packs"])
        self.assertEqual(code, 0, err)
        self.assertIn(PACK_ID, out)
        self.assertIn("39 items, 5 groups", out)


if __name__ == "__main__":
    unittest.main()
