"""Adjudication draft renderer: one stored model run, sectioned.

The draft splits the run's raw output at its Markdown headings into
the four deliverable sections the run brief asks for, reproduces each
section verbatim under a draft heading naming the deliverable, and
follows each with an adjudication stub for the operator's decision.

No line of the raw output is dropped, reordered, or altered: a
section's text includes its original heading line, text under an
unrecognized heading stays with the section it appears in, and text
before the first recognized heading is kept as the preamble. Recording
the decisions themselves is slice 5; this draft only prepares them.
"""

import re

from .store import Store

# (keyword matched case-insensitively in a heading, deliverable name)
DELIVERABLES = (
    ("coverage", "Coverage map"),
    ("attack chain", "Attack chains"),
    ("fix", "Fix list"),
    ("verify", "Verify-next list"),
)

HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")

STUB = (
    "> **Adjudication**\n"
    "> Decision: (accept / correct / reject)\n"
    "> Correction or note:"
)


def _deliverable_for(line, started):
    """The deliverable a heading line starts, or None.

    A heading starts a deliverable only the first time that deliverable
    is seen; a later heading naming an already-started deliverable is
    ordinary text within the current section.
    """
    m = HEADING_RE.match(line)
    if not m:
        return None
    text = m.group(1).lower()
    for keyword, name in DELIVERABLES:
        if keyword in text and name not in started:
            return name
    return None


def split_sections(raw_output):
    """Split raw output into (preamble_lines, [(name, lines), ...]).

    Sections are in the order their headings appear. The preamble is
    every line before the first recognized deliverable heading.
    """
    preamble = []
    sections = []
    started = set()
    current = None
    for line in raw_output.splitlines():
        name = _deliverable_for(line, started)
        if name is not None:
            started.add(name)
            current = (name, [line])
            sections.append(current)
        elif current is None:
            preamble.append(line)
        else:
            current[1].append(line)
    return preamble, sections


def render_draft(db_path, run_id):
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        if eng is None:
            raise ValueError("database holds no engagement")
        run = store.get_run(run_id)
        if run is None:
            raise ValueError(f"no such run: {run_id}")
    finally:
        store.close()

    preamble, sections = split_sections(run["raw_output"])

    lines = []
    lines.append(f"# Adjudication draft — {eng['name']}")
    lines.append("")
    lines.append(f"- Run: {run['id']}")
    lines.append(f"- Packet hash: {run['packet_hash']}")
    lines.append(f"- Model: {run['model_label']}")
    lines.append(f"- Run date: {run['run_date']}")
    if not sections:
        lines.append("- No deliverable headings were recognized in this output.")
    lines.append("")

    if not sections:
        lines.append("## Unsectioned output")
        lines.append("")
        lines.extend(run["raw_output"].splitlines())
        lines.append("")
        lines.extend(STUB.splitlines())
        lines.append("")
        return "\n".join(lines)

    if any(line.strip() for line in preamble):
        lines.append("## Preamble")
        lines.append("")
        lines.extend(preamble)
        lines.append("")

    for name, section_lines in sections:
        lines.append(f"## {name}")
        lines.append("")
        lines.extend(section_lines)
        lines.append("")
        lines.extend(STUB.splitlines())
        lines.append("")
    return "\n".join(lines)
