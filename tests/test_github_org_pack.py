"""GitHub organization security pack tests (github-org-security-1.0).

The pack is curated from GitHub Docs (github/docs at a pinned commit,
CC BY 4.0) for a small organization. These tests pin its header, its
34 items in 7 groups in the designed order, the exact five top-level
keys and three per-item keys, the CC BY attribution and the CIS fence
in the citation, and that it validates and loads through the one pack
validator and the load-pack command.
"""

import io
import json
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import bundled_pack_path, load_pack, validate_pack
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = REPO_ROOT / "src" / "fencewalk" / "packs" / "github-org-security-1.0.json"
PACK_ID = "github-org-security-1.0"
DOCS_COMMIT = "bd60abd2de5c9285e34ce3ea794274e973b0633e"

GROUPS = [
    ("Identity and access", "ID", 5),
    ("Membership and ownership", "MEM", 5),
    ("Programmatic access", "TOK", 6),
    ("GitHub Actions", "ACT", 6),
    ("Code security defaults", "CODE", 6),
    ("Webhooks", "WH", 3),
    ("Audit", "AUD", 3),
]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class GitHubOrgPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(PACK_PATH)
        cls.items = cls.pack["items"]
        cls.text = {i["item_id"]: i["text"] for i in cls.items}

    def test_header(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(
            self.pack["title"],
            "GitHub — Organization Security Expected State (curated)",
        )
        self.assertEqual(self.pack["version"], "1.0")

    def test_exact_keys(self):
        self.assertEqual(
            sorted(self.pack),
            ["items", "pack_id", "source_citation", "title", "version"],
        )
        for item in self.items:
            self.assertEqual(sorted(item), ["group", "item_id", "text"], item)

    def test_citation_attributes_and_fences(self):
        cite = self.pack["source_citation"]
        self.assertIn(f"github/docs @ {DOCS_COMMIT}", cite)
        self.assertIn("© GitHub, Inc.", cite)
        self.assertIn("CC BY 4.0", cite)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", cite)
        self.assertIn("No CIS Benchmark content is used.", cite)

    def test_validates(self):
        self.assertIs(validate_pack(self.pack), self.pack)

    def test_34_items_in_7_groups(self):
        self.assertEqual(len(self.items), 34)
        counts = Counter(i["group"] for i in self.items)
        self.assertEqual(counts, Counter({g: n for g, _, n in GROUPS}))

    def test_ids_unique_and_in_designed_order(self):
        expected = [
            f"GH-{prefix}-{n:02d}"
            for _, prefix, count in GROUPS
            for n in range(1, count + 1)
        ]
        self.assertEqual([i["item_id"] for i in self.items], expected)
        self.assertEqual(len(set(expected)), 34)
        group_of = {prefix: g for g, prefix, _ in GROUPS}
        for item in self.items:
            prefix = item["item_id"].split("-")[1]
            self.assertEqual(item["group"], group_of[prefix], item["item_id"])

    def test_amended_items_verbatim(self):
        # Amendment 1, R1-R3 and R5: wording that traces to the pinned docs.
        self.assertEqual(
            self.text["GH-ID-04"],
            "An IP allow list limits access to the organization to known"
            " networks. Requires GitHub Enterprise Cloud.",
        )
        self.assertEqual(
            self.text["GH-MEM-02"],
            "Members cannot create public repositories; creating private"
            " repositories is limited to organization owners.",
        )
        self.assertEqual(
            self.text["GH-MEM-04"],
            "The organization has at least two owners and no more than three.",
        )
        self.assertEqual(
            self.text["GH-MEM-05"],
            "Publication of GitHub Pages sites from organization repositories"
            " is prohibited, or limited to privately published sites.",
        )

    def test_text_is_plain(self):
        for item in self.items:
            text = item["text"]
            self.assertEqual(text, " ".join(text.split()), item["item_id"])
            self.assertTrue(text.endswith("."), item["item_id"])
            self.assertNotRegex(text, r"<[^>]+>|\{%|`", item["item_id"])
            self.assertNotRegex(text, r"\bCIS\b", item["item_id"])

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
                pack = store.get_pack(PACK_ID)
            finally:
                store.close()
        self.assertEqual(len(items), 34)
        self.assertEqual(pack["source_citation"], self.pack["source_citation"])
        self.assertEqual(
            [i["item_id"] for i in items], [i["item_id"] for i in self.items]
        )


if __name__ == "__main__":
    unittest.main()
