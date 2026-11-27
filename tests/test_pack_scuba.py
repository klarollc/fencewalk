"""SCuBA content pack tests: the CISA SCuBA M365 baselines as shipped data.

The pack is derived from the pinned ScubaGear v2.0.0 tag (see the
handback for the derivation method). These tests pin the derived
numbers: 109 items in 7 groups, every statement carrying SHALL or
SHOULD, exactly 11 licence-suffixed items, and verbatim spot-checks
of derived items including the long MS.SECURITYSUITE.3.1v1 statement
taken whole.
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
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "scuba-m365-v2.0.0.json"
PACK_ID = "scuba-m365-v2.0.0"

# Golden counts, measured from the pinned ScubaGear v2.0.0 tag by the
# derivation script (per-file policy-heading counts; see handback).
EXPECTED_GROUP_COUNTS = {
    "Microsoft Entra ID": 34,
    "Exchange Online": 12,
    "Power BI": 8,
    "Power Platform": 9,
    "Security Suite": 24,
    "SharePoint Online and OneDrive": 8,
    "Teams": 14,
}


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class ScubaPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)

    def test_validates(self):
        validated = validate_pack(load_pack(PACK_PATH))
        self.assertEqual(validated["pack_id"], PACK_ID)

    def test_pack_identity(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(self.pack["version"], "2.0.0")
        self.assertIn("ScubaGear v2.0.0", self.pack["title"])
        self.assertIn("CC0 1.0 Universal", self.pack["source_citation"])
        self.assertIn("v2.0.0", self.pack["source_citation"])

    def test_item_keys_exact(self):
        for item in self.pack["items"]:
            self.assertEqual(set(item.keys()), {"group", "item_id", "text"})

    def test_109_items(self):
        self.assertEqual(len(self.pack["items"]), 109)

    def test_unique_ids(self):
        ids = [i["item_id"] for i in self.pack["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_per_group_counts(self):
        counts = {}
        for item in self.pack["items"]:
            counts[item["group"]] = counts.get(item["group"], 0) + 1
        self.assertEqual(counts, EXPECTED_GROUP_COUNTS)

    def test_every_text_has_shall_or_should(self):
        for item in self.pack["items"]:
            text = item["text"]
            self.assertTrue(
                "SHALL" in text or "SHOULD" in text,
                item["item_id"],
            )

    def test_eleven_licence_suffixes(self):
        suffixed = [i for i in self.pack["items"] if " License: " in i["text"]]
        self.assertEqual(len(suffixed), 11)

    def test_no_markdown_link_residue(self):
        for item in self.pack["items"]:
            self.assertNotIn("](", item["text"], item["item_id"])
            self.assertNotIn("\\|", item["text"], item["item_id"])

    def _text_of(self, item_id):
        return next(
            i["text"] for i in self.pack["items"] if i["item_id"] == item_id
        )

    def test_spot_check_aad_1_1(self):
        self.assertEqual(
            self._text_of("MS.AAD.1.1v1"),
            "Legacy authentication SHALL be blocked.",
        )

    def test_spot_check_aad_2_2(self):
        self.assertEqual(
            self._text_of("MS.AAD.2.2v1"),
            "A notification SHOULD be sent to the administrator when "
            "high-risk users are detected.",
        )

    def test_spot_check_licence_suffixed_aad_2_3(self):
        self.assertEqual(
            self._text_of("MS.AAD.2.3v1"),
            "Sign-ins detected as high-risk SHALL be blocked. "
            "License: Requires a Microsoft Entra ID P2 license",
        )

    def test_spot_check_long_securitysuite_3_1(self):
        self.assertEqual(
            self._text_of("MS.SECURITYSUITE.3.1v1"),
            "A DLP policy SHALL be configured to protect PII and sensitive "
            "information, as defined by the agency, blocking at a minimum: "
            "credit card numbers, U.S. Individual Taxpayer Identification "
            "Numbers (ITIN), and U.S. Social Security numbers (SSN).",
        )

    def test_spot_check_multiline_link_securitysuite_2_4(self):
        # The source splits this link across lines; the derivation joins
        # before replacing links, so the text reads as clean prose.
        self.assertEqual(
            self._text_of("MS.SECURITYSUITE.2.4v1"),
            "User warnings, comparable to the user safety tips included "
            "with EOP, SHOULD be displayed. License: Impersonation "
            "protection and advanced phishing thresholds require Defender "
            "for Office 365 Plan 1 or 2. These are included with E5 and "
            "G5 and are available as add-ons for E3 and G3. As of January "
            "2026, anti-phishing for user and domain impersonation and "
            "spoof intelligence are not yet available in M365 Government "
            "Community Cloud (GCC High) and Department of Defense (DoD) "
            "environments. See Platform features | Microsoft Learn for "
            "current offerings.",
        )


class ScubaPackStoreTest(unittest.TestCase):
    """Load the pack through the store API; list-coverage sees 109 items."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "SCuBA pack test",
            "--subject", "Test firm", "--method-order", "verify-first",
            "--date", "2026-11-18",
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
        self.assertEqual(len(rows), 109)
        groups = {r["group_name"] for r in rows}
        self.assertEqual(len(groups), 7)
        self.assertEqual(groups, set(EXPECTED_GROUP_COUNTS))


if __name__ == "__main__":
    unittest.main()
