"""Reference-case attestation: the fixture says it is fictional, says
where it came from, and carries none of the retired fixture's markers.

The markers are the retired fixture's own already-public strings. The
scrub of personal identifiers is not a test: it is a release-gate grep
run at review."""

import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "src" / "fencewalk" / "fixtures" / "reference-case"

RETIRED_MARKERS = (
    "Harborlight",
    "RustDesk",
    "ConnectWise",
    "overlay",
    "Node runtime",
    "GitHub App",
    "programme",
)


def fixture_files():
    return sorted(p for p in FIXTURE_DIR.rglob("*") if p.is_file())


def marker_hits(files, root=FIXTURE_DIR):
    hits = []
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for marker in RETIRED_MARKERS:
            if marker.lower() in text:
                hits.append((path.relative_to(root).as_posix(), marker))
    return hits


class ReferenceCaseAttestationTest(unittest.TestCase):
    def test_readme_states_the_case_is_fictional_and_invented(self):
        readme = (FIXTURE_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("**This case is fictional.**", readme)
        self.assertIn("invented for\nFencewalk", readme)
        self.assertIn("`PROVENANCE.md`", readme)

    def test_provenance_carries_the_retirement_note(self):
        path = FIXTURE_DIR / "PROVENANCE.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("This fixture is an invention.", text)
        self.assertIn("That content was retired", text)

    def test_no_retired_content_markers_in_the_fixture(self):
        self.assertEqual(marker_hits(fixture_files()), [])

    def test_the_marker_scan_reads_every_fixture_file(self):
        files = fixture_files()
        names = {p.name for p in files}
        for name in ("README.md", "PROVENANCE.md", "EXPECTED-REPORT.md",
                     "engagement.json", "inventory.json", "coverage.json",
                     "chains.json", "fixes.json", "verify_next.json"):
            self.assertIn(name, names)

    def test_the_scan_catches_a_marker_in_any_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "planted.md"
            planted.write_text("An OVERLAY on the Programme page.\n",
                               encoding="utf-8")
            found = {marker for _, marker in marker_hits(
                [planted], root=Path(tmp))}
        self.assertEqual(found, {"overlay", "programme"})


if __name__ == "__main__":
    unittest.main()
