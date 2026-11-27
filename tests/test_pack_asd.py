"""ASD scoped content pack tests: the ASD Blueprint for Secure Cloud
Entra ID expected state, v1.4, as shipped data.

Unlike the SCuBA pack this one is curated, not verbatim: the Blueprint's
Entra ID section holds 796 as-built table rows across 54 pages, and the
derivation rule (brief fencewalk-asd-pack-brief-20261122.md, section 3)
turns one configuration object into one item, dropping fill-in-only
rows and generalising the government-specific values the brief names.
These tests pin the derived numbers: 60 items in 8 groups, the three
worked examples verbatim, and verbatim spot-checks of generalised
items. The derivation itself is documented in the handback, with a
source map (every item to its page) and an adaptation log.

One pinned negative: the pack carries no " Requires: " suffix. The
brief expected one for the insider-risk policy (PRT-16), on the
understanding that the design page states a Purview Insider Risk
Management requirement. It does not — neither the configuration page
nor the conditional-access or protection design pages state any
licence or capability requirement — so no suffix is appended, per
the brief's own rule that a suffix appears only where a page states
one. See the handback.
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
    / "asd-secure-cloud-identity-1.4.json"
)
PACK_ID = "asd-secure-cloud-identity-1.4"

# Golden counts, measured from the Nov 23, 2026 snapshot of the
# Blueprint Entra ID section (796 ABAC rows across 54 pages; see
# handback). Counts below are compared against counts computed from
# the loaded pack.
EXPECTED_GROUP_COUNTS = {
    "Identity Properties": 1,
    "Users": 4,
    "Groups": 3,
    "Devices": 3,
    "Applications": 3,
    "Protection": 41,
    "Identity Governance": 2,
    "External Identities": 3,
}


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class AsdPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)

    def test_validates(self):
        validated = validate_pack(load_pack(PACK_PATH))
        self.assertEqual(validated["pack_id"], PACK_ID)

    def test_pack_identity(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(self.pack["version"], "1.4")
        self.assertIn("ASD Blueprint for Secure Cloud", self.pack["title"])
        self.assertIn("Entra ID", self.pack["title"])
        self.assertIn("CC BY 4.0", self.pack["source_citation"])
        self.assertIn(
            "© Commonwealth of Australia 2023", self.pack["source_citation"]
        )
        self.assertIn("adapted for a small organisation",
                      self.pack["source_citation"])

    def test_item_keys_exact(self):
        for item in self.pack["items"]:
            self.assertEqual(set(item.keys()), {"group", "item_id", "text"})

    def test_60_items(self):
        self.assertEqual(len(self.pack["items"]), 60)

    def test_unique_ids(self):
        ids = [i["item_id"] for i in self.pack["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_per_group_counts(self):
        counts = {}
        for item in self.pack["items"]:
            counts[item["group"]] = counts.get(item["group"], 0) + 1
        self.assertEqual(counts, EXPECTED_GROUP_COUNTS)

    def test_no_angle_bracket_placeholders(self):
        for item in self.pack["items"]:
            self.assertNotIn("<", item["text"], item["item_id"])
            self.assertNotIn(">", item["text"], item["item_id"])

    def test_no_markdown_link_residue(self):
        for item in self.pack["items"]:
            self.assertNotIn("](", item["text"], item["item_id"])

    def test_no_requires_suffixes(self):
        # No configuration page or linked design page states a licence
        # or capability requirement (handback); the brief's expected
        # insider-risk suffix did not verify, so the pack has none.
        suffixed = [i for i in self.pack["items"] if " Requires: " in i["text"]]
        self.assertEqual(suffixed, [])

    def _text_of(self, item_id):
        return next(
            i["text"] for i in self.pack["items"] if i["item_id"] == item_id
        )

    def test_worked_example_prt_18(self):
        self.assertEqual(
            self._text_of("ASD-ENTRA-PRT-18"),
            "Conditional Access policy 'USR - B - Block high-risk "
            "sign-ins' exists, is On, applies to all users for all "
            "resources, and blocks access when sign-in risk is High.",
        )

    def test_worked_example_usr_01(self):
        self.assertEqual(
            self._text_of("ASD-ENTRA-USR-01"),
            "Two break-glass accounts exist, both enabled, Member, "
            "Global Administrator, and in the Conditional Access "
            "exclude groups.",
        )

    def test_worked_example_prt_14(self):
        self.assertEqual(
            self._text_of("ASD-ENTRA-PRT-14"),
            "Conditional Access policy 'USR - B - Block access to "
            "sensitive information' exists, is On, applies to all "
            "users for the sensitive-information authentication "
            "context, blocks access, and excludes the "
            "sensitive-access group.",
        )

    def test_spot_check_generalised_prt_20(self):
        # "Australia" as a named location generalises to "the
        # organisation's approved countries" (adaptation log).
        self.assertEqual(
            self._text_of("ASD-ENTRA-PRT-20"),
            "Conditional Access policy 'LOC - B - Block access from "
            "unapproved countries' exists, is On, applies to all "
            "users for all resources, and blocks access from any "
            "network or location except the organisation's approved "
            "countries.",
        )

    def test_spot_check_generalised_prt_09(self):
        # "PROTECTED information" generalises to "sensitive
        # information" (adaptation log).
        self.assertEqual(
            self._text_of("ASD-ENTRA-PRT-09"),
            "An authentication context for sensitive information "
            "exists, is published to apps, and has ID c1.",
        )

    def test_spot_check_disabled_methods_prt_05(self):
        self.assertEqual(
            self._text_of("ASD-ENTRA-PRT-05"),
            "SMS, Hardware OATH tokens, Third-party software OATH "
            "tokens, Voice call, Email OTP, and Certificate-based "
            "authentication are all disabled as authentication methods.",
        )


class AsdPackStoreTest(unittest.TestCase):
    """Load the pack through the store API; list-coverage sees 60 items."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "eng.db")
        code, _, err = run_cli([
            "new", self.db, "--name", "ASD pack test",
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
        self.assertEqual(len(rows), 60)
        groups = {r["group_name"] for r in rows}
        self.assertEqual(len(groups), 8)
        self.assertEqual(groups, set(EXPECTED_GROUP_COUNTS))


if __name__ == "__main__":
    unittest.main()
