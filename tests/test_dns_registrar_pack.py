"""DNS and registrar pack tests (dns-registrar-security-1.0).

The pack is curated from IETF RFCs, CISA BOD 18-01, NCSC guidance
(OGL v3.0) and the other sources named in docs/dns-registrar-evidence.md
for a small organization. These tests pin its header, its 28 items in
6 groups in the designed order (each group's ids also sort in report
order), the exact five top-level keys and three per-item keys, the
amended item wording (Amendment 1, R1-R6), and that it validates and
loads through the one pack validator and the load-pack command.
"""

import io
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fencewalk.__main__ import main
from fencewalk.fixture import bundled_pack_path, load_pack, validate_pack
from fencewalk.store import Store

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = (REPO_ROOT / "src" / "fencewalk" / "packs"
             / "dns-registrar-security-1.0.json")
PACK_ID = "dns-registrar-security-1.0"

GROUPS = [
    ("Registrar account and domains", "REG", 5),
    ("Zone integrity", "ZONE", 4),
    ("Nameserver resilience", "NS", 3),
    ("Email authentication", "EM", 8),
    ("Mail transport and certificate issuance", "TLS", 4),
    ("Subdomain hygiene", "SUB", 4),
]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class DnsRegistrarPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack(PACK_PATH)
        cls.items = cls.pack["items"]
        cls.text = {i["item_id"]: i["text"] for i in cls.items}

    def test_header(self):
        self.assertEqual(self.pack["pack_id"], PACK_ID)
        self.assertEqual(
            self.pack["title"],
            "DNS and Registrar — Domain Security Expected State (curated)",
        )
        self.assertEqual(self.pack["version"], "1.0")
        self.assertEqual(
            self.pack["source_citation"],
            "Curated from the IETF RFCs named in docs/dns-registrar-evidence.md,"
            " CISA BOD 18-01, and NCSC guidance (Open Government Licence v3.0),"
            " retrieved 2026-11-24. Items are selected and reworded for a small"
            " organization.",
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

    def test_28_items_in_6_groups(self):
        self.assertEqual(len(self.items), 28)
        counts = Counter(i["group"] for i in self.items)
        self.assertEqual(counts, Counter({g: n for g, _, n in GROUPS}))

    def test_ids_unique_and_in_designed_order(self):
        expected = [
            f"DNS-{prefix}-{n:02d}"
            for _, prefix, count in GROUPS
            for n in range(1, count + 1)
        ]
        ids = [i["item_id"] for i in self.items]
        self.assertEqual(ids, expected)
        self.assertEqual(len(set(ids)), 28)
        group_of = {prefix: g for g, prefix, _ in GROUPS}
        for item in self.items:
            prefix = item["item_id"].split("-")[1]
            self.assertEqual(item["group"], group_of[prefix], item["item_id"])

    def test_amended_items_verbatim(self):
        self.assertEqual(
            self.text["DNS-EM-04"],
            "A DMARC record is published for every domain, with an enforcement"
            " policy in force (p=quarantine or p=reject). Monitoring only"
            " (p=none) appears only as a dated step toward enforcement, and"
            " p=reject is adopted only after aggregate reports show it will not"
            " break the domain's mailing-list or forwarded mail.",
        )
        self.assertEqual(
            self.text["DNS-NS-03"],
            "A current copy of every zone's records is kept under the"
            " organization's own control (as records-as-code or an export), so"
            " the zone can be rebuilt at another provider.",
        )
        self.assertEqual(
            self.text["DNS-REG-03"],
            "Registry lock is enabled where the registry offers it, so the"
            " domain cannot be changed until the lock is removed.",
        )
        self.assertEqual(
            self.text["DNS-ZONE-01"],
            "The DNS provider account requires two-step verification, and"
            " access to it is limited to the administrators who manage the zone.",
        )
        self.assertNotIn("out-of-band", " ".join(self.text.values()))
        self.assertNotIn("API token", " ".join(self.text.values()))

    def test_text_is_plain(self):
        for item in self.items:
            text = item["text"]
            self.assertEqual(text, " ".join(text.split()), item["item_id"])
            self.assertTrue(text.endswith("."), item["item_id"])
            self.assertNotRegex(text, r"<[^>]+>|`|\bCIS\b", item["item_id"])
            self.assertNotIn("7489", text, item["item_id"])

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
        self.assertEqual(len(items), 28)
        self.assertEqual(len({i["group_name"] for i in items}), 6)
        self.assertEqual(
            [i["item_id"] for i in items], [i["item_id"] for i in self.items]
        )


if __name__ == "__main__":
    unittest.main()
