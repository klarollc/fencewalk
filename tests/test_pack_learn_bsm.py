"""Microsoft Learn Baseline Security Mode content pack tests: the
Baseline Security Mode settings article, ms.date 2026-11-17, as
shipped data.

Like the ASD and NCSC packs this one is curated, not verbatim: the
article is a settings page with four tables (Setting | More
information), not a numbered policy list, so one pack item is one
distinct setting, per the derivation rule in brief
fencewalk-learn-bsm-pack-brief-20261122.md, section 3. The setting
names are reproduced verbatim as printed in the table's Setting
column — no rewording, no added rationale — so these tests pin the
derived numbers (45 unique items in 4 groups) and the verbatim
names, including the four worked examples and the three long names
most likely to be mistyped or "corrected". The derivation itself is
documented in the handback, with a per-item source map (every item
to its section and table row).

Two pinned facts: the duplicate "Require multifactor authentication
for device enrollment" (Authentication row 16 and Room devices row
4, the same setting with one toggle) appears exactly once, as
AUTH-16; and the pack carries no " Requires: " suffix — BSM states
no licence or capability requirement.
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
    / "ms-learn-baseline-security-mode-2026-11-17.json"
)
PACK_ID = "ms-learn-baseline-security-mode-2026-11-17"

# Golden counts, measured from the pinned live-page snapshot
# (bsm-settings.html, sha256 49a789c9..., 95,503 bytes; four tables
# machine-parsed: Authentication 21 rows, Applications 12, Files 6,
# Room devices 7 rows, 46 rows total, 1 duplicate folded — see
# handback). Counts below are compared against counts computed from
# the loaded pack.
EXPECTED_GROUP_COUNTS = {
    "Authentication": 21,
    "Applications": 12,
    "Files": 6,
    "Room devices": 6,
}

DUPLICATE_TEXT = "Require multifactor authentication for device enrollment"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class LearnBsmPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)

    def test_validates(self):
        validated = validate_pack(load_pack(PACK_PATH))
        self.assertEqual(validated["pack_id"], PACK_ID)

    def test_pack_identity(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(self.pack["version"], "2026-11-17")
        self.assertIn("Baseline Security Mode", self.pack["title"])
        self.assertIn("ms.date 2026-11-17", self.pack["title"])
        self.assertIn("Microsoft Learn", self.pack["source_citation"])
        self.assertIn("Baseline security mode settings",
                      self.pack["source_citation"])
        self.assertIn("ms.date 2026-11-17", self.pack["source_citation"])
        self.assertIn("Microsoft Corporation", self.pack["source_citation"])
        self.assertIn("CC BY 4.0", self.pack["source_citation"])
        self.assertIn("https://creativecommons.org/licenses/by/4.0/",
                      self.pack["source_citation"])

    def test_item_keys_exact(self):
        for item in self.pack["items"]:
            self.assertEqual(set(item.keys()), {"group", "item_id", "text"})

    def test_45_items(self):
        self.assertEqual(len(self.pack["items"]), 45)

    def test_unique_ids(self):
        ids = [i["item_id"] for i in self.pack["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_per_group_counts(self):
        counts = {}
        for item in self.pack["items"]:
            counts[item["group"]] = counts.get(item["group"], 0) + 1
        self.assertEqual(counts, EXPECTED_GROUP_COUNTS)

    def test_no_requires_suffixes(self):
        # BSM states no licence or capability requirement (handback);
        # the pack has none.
        suffixed = [i for i in self.pack["items"] if " Requires: " in i["text"]]
        self.assertEqual(suffixed, [])

    def test_duplicate_folded_to_auth_16(self):
        # "Require multifactor authentication for device enrollment"
        # is Authentication row 16 and Room devices row 4 — one
        # setting, one toggle, one item.
        holders = [i for i in self.pack["items"] if i["text"] == DUPLICATE_TEXT]
        self.assertEqual(len(holders), 1)
        self.assertEqual(holders[0]["item_id"], "MS-BSM-AUTH-16")
        self.assertEqual(holders[0]["group"], "Authentication")
        room_ids = [i["item_id"] for i in self.pack["items"]
                    if i["group"] == "Room devices"]
        self.assertEqual(room_ids, ["MS-BSM-ROOM-%02d" % n for n in range(1, 7)])

    def _text_of(self, item_id):
        return next(
            i["text"] for i in self.pack["items"] if i["item_id"] == item_id
        )

    def test_worked_example_auth_01(self):
        self.assertEqual(
            self._text_of("MS-BSM-AUTH-01"),
            "Protect admin access to Microsoft admin portals with "
            "phishing resistant authentication",
        )

    def test_worked_example_app_03(self):
        self.assertEqual(
            self._text_of("MS-BSM-APP-03"),
            "Block COM add-ins that aren't on the admin allow list",
        )

    def test_worked_example_file_03(self):
        self.assertEqual(
            self._text_of("MS-BSM-FILE-03"),
            "Block ActiveX controls",
        )

    def test_worked_example_room_04(self):
        self.assertEqual(
            self._text_of("MS-BSM-ROOM-04"),
            "Require a device compliance policy",
        )

    def test_spot_check_long_name_auth_08(self):
        # The Relying Party suite (RPS) protocol name, verbatim.
        self.assertEqual(
            self._text_of("MS-BSM-AUTH-08"),
            "Block legacy browser authentication connections to "
            "SharePoint and OneDrive with legacy Relying Party suite "
            "(RPS) protocol",
        )

    def test_spot_check_long_name_auth_09(self):
        # The Identity Client Runtime Library (IDCRL) protocol name,
        # verbatim.
        self.assertEqual(
            self._text_of("MS-BSM-AUTH-09"),
            "Block legacy client authentication connections to "
            "SharePoint and OneDrive with legacy Identity Client "
            "Runtime Library (IDCRL) protocol",
        )

    def test_spot_check_app_11_sharepoint_spelling(self):
        # The source spells it "Sharepoint" here; do not "correct"
        # it to "SharePoint".
        self.assertEqual(
            self._text_of("MS-BSM-APP-11"),
            "Block third-party applications that use HPA permissions "
            "to files and sites in Sharepoint and OneDrive",
        )

    def test_near_duplicates_are_distinct_items(self):
        # Lookups vs launches, portal access vs enrollment policy,
        # file opens vs worksheet functions — distinct settings, all
        # present (brief section 5).
        self.assertEqual(
            self._text_of("MS-BSM-APP-06"),
            "Block DDE server lookups in Excel",
        )
        self.assertEqual(
            self._text_of("MS-BSM-FILE-05"),
            "Dynamic Data Exchange (DDE) server launches are blocked "
            "in Excel",
        )
        self.assertEqual(
            self._text_of("MS-BSM-AUTH-15"),
            "Require device compliance for Intune portal access",
        )
        self.assertEqual(
            self._text_of("MS-BSM-ROOM-04"),
            "Require a device compliance policy",
        )
        self.assertEqual(
            self._text_of("MS-BSM-AUTH-06"),
            "Block insecure protocols for file opens",
        )
        self.assertEqual(
            self._text_of("MS-BSM-APP-05"),
            "Block Excel worksheet functions from accessing the web "
            "using insecure protocols",
        )


class LearnBsmPackStoreTest(unittest.TestCase):
    """Load the pack through the store API; list-coverage sees 45 items."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "Learn BSM pack test",
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
        self.assertEqual(len(rows), 45)
        groups = {r["group_name"] for r in rows}
        self.assertEqual(len(groups), 4)
        self.assertEqual(groups, set(EXPECTED_GROUP_COUNTS))

    def test_packs_lists_new_pack(self):
        code, out, err = run_cli(["packs"])
        self.assertEqual(code, 0, err)
        self.assertIn(PACK_ID, out)
        self.assertIn("45 items, 4 groups", out)


if __name__ == "__main__":
    unittest.main()
