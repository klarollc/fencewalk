"""Pack authoring guide tests: the guide's example pack is real.

docs/pack-authoring.md carries one complete example pack in a fenced
json block. These tests extract that block from the guide itself,
run it through the one pack validator, load it into a scratch
database through the store, and read its items back — so the guide's
central claim (a pack written to this document loads the first time)
is machine-checked, not just proofread. They also assert the guide
names every pack the tool ships, so the worked-examples table cannot
silently lose one.
"""

import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from fencewalk.fixture import validate_pack
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE = REPO_ROOT / "docs" / "pack-authoring.md"
PACKS_DIR = REPO_ROOT / "src" / "fencewalk" / "packs"
EXAMPLE_PACK_ID = "example-perimeter-basics-1.0"


def guide_example_pack():
    text = GUIDE.read_text(encoding="utf-8")
    for block in re.findall(r"```json\n(.*?)```", text, re.DOTALL):
        try:
            pack = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(pack, dict) and pack.get("pack_id") == EXAMPLE_PACK_ID:
            return pack
    raise AssertionError("guide carries no example pack json block")


class PackGuideExampleTest(unittest.TestCase):
    def test_example_pack_validates(self):
        pack = guide_example_pack()
        self.assertIs(validate_pack(pack), pack)

    def test_example_pack_loads_and_lists(self):
        pack = guide_example_pack()
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "scratch.db")
            try:
                store.init_schema()
                store.add_pack(pack)
                items = store.list_pack_items(EXAMPLE_PACK_ID)
            finally:
                store.close()
        self.assertEqual(len(items), 3)
        self.assertEqual(
            Counter(i["group_name"] for i in items),
            Counter({"Identity": 2, "Mail": 1}),
        )
        self.assertEqual(
            [i["item_id"] for i in items],
            ["EX-ID-01", "EX-ID-02", "EX-MAIL-01"],
        )

    def test_guide_names_every_shipped_pack(self):
        text = GUIDE.read_text(encoding="utf-8")
        pack_ids = []
        for path in sorted(PACKS_DIR.glob("*.json")):
            pack_ids.append(json.loads(path.read_text(encoding="utf-8"))["pack_id"])
        self.assertEqual(len(pack_ids), 8)
        for pack_id in pack_ids:
            self.assertIn(pack_id, text)


if __name__ == "__main__":
    unittest.main()
