"""Bundle-Markdown inventory import (slice 1 intake).

Parses the audit-bundle inventory format: a '#' title and preamble
paragraphs, then '## A.' ... '## H.' section headers whose entries are
'- ' bullets (in section H only, numbered '1. ' lines are entries too).

The import is deterministic and never guesses:

- Label: the markers VERIFIED / ON RECORD / UNKNOWN (word-boundary,
  case-sensitive) found in the entry body. Exactly one distinct marker
  determines the label. A body with two or more distinct markers is NOT
  imported; it is listed in the import report for the operator to add
  manually. A body with no marker imports as UNKNOWN, with a source
  noting the label was not stated in the source.
- Checked date: for a VERIFIED entry, a 'Mon D, YYYY' date inside the
  same sentence as the VERIFIED marker (sentences are delimited by '. '
  or a final '.' — deliberately simple). Covers both 'VERIFIED Nov 13,
  2026' and 'VERIFIED as performed, Nov 18, 2026'. If none parses, the
  checked date stays unset and the entry is counted in the report as
  verified, date not parsed.
- Anything before the first '## ' header is preamble: skipped, and its
  non-blank lines are counted in the report. A '## ' header outside A-H
  ends the current section; lines under it are not entries.
- Entry IDs are auto-assigned per section in file order, by the same
  rule as the add-entry command (Store.next_entry_id). Skipped entries
  consume no ID.
"""

import datetime
import re
from pathlib import Path

from .store import EVIDENCE_LABELS, InvariantError

SECTION_HEADER = re.compile(r"^## ([A-H])\.")
OTHER_HEADER = re.compile(r"^## ")
BULLET = re.compile(r"^- (.*)$")
NUMBERED = re.compile(r"^\d+\. (.*)$")
LABEL_PATTERNS = {
    label: re.compile(r"\b" + re.escape(label) + r"\b")
    for label in EVIDENCE_LABELS
}
DATE_PATTERN = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2}), (\d{4})\b"
)
MONTHS = {
    name: i + 1
    for i, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    )
}
SECTIONS = "ABCDEFGH"


def _find_markers(body):
    """Distinct label markers in the body, in order of first appearance.

    Returns a list of (position, label) pairs.
    """
    found = []
    for label in EVIDENCE_LABELS:
        m = LABEL_PATTERNS[label].search(body)
        if m:
            found.append((m.start(), label))
    found.sort()
    return found


def _sentence_span(text, pos):
    """(start, end) offsets of the sentence containing offset pos."""
    start = text.rfind(". ", 0, pos)
    start = 0 if start == -1 else start + 2
    end = text.find(".", pos)
    end = len(text) if end == -1 else end + 1
    return start, end


def _checked_date(body, marker_pos):
    """ISO date from the marker's sentence, or None if none parses."""
    start, end = _sentence_span(body, marker_pos)
    m = DATE_PATTERN.search(body, start, end)
    if not m:
        return None
    try:
        parsed = datetime.date(
            int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))
        )
    except ValueError:
        return None
    return parsed.isoformat()


def parse_inventory_markdown(text):
    """Parse bundle-format Markdown text.

    Returns (entries, skipped, preamble_lines). Each entry is a dict with
    section, line_no, body, label (None when no marker was stated),
    checked_date (None unless parsed), and verified_date_not_parsed.
    Each skipped item is a dict with section, line_no, and the distinct
    markers found, in order of first appearance.
    """
    entries = []
    skipped = []
    preamble_lines = 0
    section = None
    seen_header = False
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        m = SECTION_HEADER.match(line)
        if m:
            section = m.group(1)
            seen_header = True
            continue
        if OTHER_HEADER.match(line):
            section = None
            seen_header = True
            continue
        if not seen_header:
            if line.strip():
                preamble_lines += 1
            continue
        if section is None:
            continue
        body_text = None
        b = BULLET.match(line)
        if b:
            body_text = b.group(1)
        elif section == "H":
            n = NUMBERED.match(line)
            if n:
                body_text = n.group(1)
        if body_text is None:
            continue
        body = body_text.replace("**", "").strip()
        markers = _find_markers(body)
        distinct = [label for _, label in markers]
        if len(distinct) >= 2:
            skipped.append(
                {"section": section, "line_no": line_no, "markers": distinct}
            )
            continue
        if not distinct:
            entries.append(
                {
                    "section": section,
                    "line_no": line_no,
                    "body": body,
                    "label": None,
                    "checked_date": None,
                    "verified_date_not_parsed": False,
                }
            )
            continue
        label = distinct[0]
        checked_date = None
        not_parsed = False
        if label == "VERIFIED":
            checked_date = _checked_date(body, markers[0][0])
            if checked_date is None:
                not_parsed = True
        entries.append(
            {
                "section": section,
                "line_no": line_no,
                "body": body,
                "label": label,
                "checked_date": checked_date,
                "verified_date_not_parsed": not_parsed,
            }
        )
    return entries, skipped, preamble_lines


def import_inventory(store, engagement_id, md_path, *, date, actor):
    """Import a bundle-format Markdown inventory into an empty inventory.

    Raises InvariantError if the database's inventory is not empty.
    Returns the import report as a dict (see format_import_report).
    """
    md_path = Path(md_path)
    if store.list_inventory():
        raise InvariantError("import-inventory requires an empty inventory")
    text = md_path.read_text(encoding="utf-8")
    entries, skipped, preamble_lines = parse_inventory_markdown(text)
    per_section = {}
    label_tallies = {}
    unlabeled = 0
    not_parsed = 0
    for entry in entries:
        label = entry["label"]
        if label is None:
            label = "UNKNOWN"
            unlabeled += 1
            source = (
                f"imported from {md_path.name}; label not stated in source"
            )
        else:
            source = f"imported from {md_path.name}"
        if entry["verified_date_not_parsed"]:
            not_parsed += 1
        entry_id = store.next_entry_id(entry["section"])
        store.add_inventory_entry(
            engagement_id,
            entry_id,
            entry["section"],
            entry["body"],
            label,
            source,
            entry["checked_date"],
            None,
            date=date,
            actor=actor,
        )
        per_section[entry["section"]] = per_section.get(entry["section"], 0) + 1
        label_tallies[label] = label_tallies.get(label, 0) + 1
    return {
        "file_name": md_path.name,
        "per_section": per_section,
        "label_tallies": label_tallies,
        "unlabeled": unlabeled,
        "verified_date_not_parsed": not_parsed,
        "skipped_multi_label": skipped,
        "preamble_lines": preamble_lines,
        "total_imported": len(entries),
    }


def format_import_report(report):
    """Render an import report dict as the printed import report."""
    lines = []
    lines.append(f"Import report for {report['file_name']}")
    per_section = " · ".join(
        f"{s} {report['per_section'].get(s, 0)}" for s in SECTIONS
    )
    lines.append(f"Imported by section: {per_section}")
    tallies = " · ".join(
        f"{label} {report['label_tallies'].get(label, 0)}"
        for label in EVIDENCE_LABELS
    )
    lines.append(f"Label tallies: {tallies}")
    lines.append(
        f"Unlabeled entries imported as UNKNOWN: {report['unlabeled']}"
    )
    lines.append(
        "VERIFIED entries with no parseable checked date: "
        f"{report['verified_date_not_parsed']}"
    )
    skipped = report["skipped_multi_label"]
    lines.append(f"Skipped multi-label entries: {len(skipped)}")
    for item in skipped:
        markers = ", ".join(item["markers"])
        lines.append(
            f"  section {item['section']}, line {item['line_no']}: {markers}"
        )
    lines.append(f"Skipped preamble lines: {report['preamble_lines']}")
    lines.append(f"Total imported: {report['total_imported']}")
    return "\n".join(lines) + "\n"
