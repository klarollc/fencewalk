"""Pack validation tests: the FLASH pack as shipped data."""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "flash-20261113-001.json"


class PackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PACK_PATH, encoding="utf-8") as f:
            cls.pack = json.load(f)

    def test_twenty_items(self):
        self.assertEqual(len(self.pack["items"]), 20)

    def test_unique_ids(self):
        ids = [i["item_id"] for i in self.pack["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_expected_id_set(self):
        expected = {
            f"R-{g}.{n}"
            for g, count in ((1, 6), (2, 6), (3, 4), (4, 4))
            for n in range(1, count + 1)
        }
        self.assertEqual({i["item_id"] for i in self.pack["items"]}, expected)

    def test_four_groups(self):
        groups = {i["group"] for i in self.pack["items"]}
        self.assertEqual(len(groups), 4)

    def test_citation_present(self):
        self.assertTrue(self.pack["source_citation"])
        self.assertIn("FLASH-20261113-001", self.pack["source_citation"])

    def test_every_item_has_text(self):
        for item in self.pack["items"]:
            self.assertTrue(item["text"].strip(), item["item_id"])


if __name__ == "__main__":
    unittest.main()
