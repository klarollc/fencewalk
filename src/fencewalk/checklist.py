"""Verification checklist renderer: a derived Markdown view of the store.

The checklist is computed from the database's current state at an as-of
date; rendering it writes nothing to the database. It lists what still
needs verifying — inventory entries labelled UNKNOWN — and evidence
labelled VERIFIED or ON RECORD whose recorded decay date has passed.

Resolutions are recorded with set-label, the store's only label-mutation
path: a resolved entry no longer qualifies as unknown, so regenerating
the checklist after resolutions is itself the record of progress,
alongside the label history set-label already keeps. There is no
checklist state anywhere in the store.

Every count in the output is computed at render time.
"""

import re

from .store import Store

INSTRUCTIONS = (
    "Work each check by examining the source named on it. When an unknown "
    "is settled, record the resolution with `set-label` — for example "
    "`fencewalk set-label <db> <entry-id> VERIFIED --date <date> "
    "--actor <name>` — so the entry leaves the next checklist; the label "
    "history keeps the record of when it was resolved and by whom. "
    "Evidence listed as decayed is re-verified the same way and its dates "
    "updated with `edit-entry`. An unknown that cannot be settled stays "
    "UNKNOWN: it will appear on the next checklist, and that is the "
    "correct outcome, not a failure."
)


def _order_key(entry):
    """Checklist order: by section, then by entry ID with any trailing
    number compared numerically (A2 before A10).

    list_inventory orders by the entry_id string, which puts H10 before
    H2; the checklist is a document an operator works top to bottom, so
    it uses the natural reading order instead. The store is untouched.
    """
    m = re.fullmatch(r"(.*?)(\d+)", entry["entry_id"])
    if m:
        return (entry["section"], m.group(1), int(m.group(2)), entry["entry_id"])
    return (entry["section"], entry["entry_id"], -1, entry["entry_id"])


def select_checks(entries, as_of):
    """Split inventory entries into the (unknown, decayed) checklist sections.

    Both lists are in checklist order (see _order_key). An UNKNOWN entry
    appears only among the unknowns, decayed or not; decayed evidence is
    VERIFIED or ON RECORD entries whose decay date is set and on or
    before as_of.
    """
    ordered = sorted(entries, key=_order_key)
    unknown = [e for e in ordered if e["label"] == "UNKNOWN"]
    decayed = [
        e for e in ordered
        if e["label"] in ("VERIFIED", "ON RECORD")
        and e["decay_date"] is not None
        and e["decay_date"] <= as_of
    ]
    return unknown, decayed


def render_checklist(db_path, as_of):
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        if eng is None:
            raise ValueError("database holds no engagement")
        entries = store.list_inventory()
    finally:
        store.close()

    unknown, decayed = select_checks(entries, as_of)
    total = len(unknown) + len(decayed)

    lines = []
    lines.append(f"# Verification checklist — {eng['name']}")
    lines.append("")
    lines.append(f"- As of: {as_of}")
    lines.append(
        f"- Checks: {len(unknown)} unknown · {len(decayed)} decayed evidence"
        f" · {total} total"
    )
    lines.append("")
    lines.append("## How to work this checklist")
    lines.append("")
    lines.append(INSTRUCTIONS)
    lines.append("")
    lines.append("## Unknown entries")
    lines.append("")
    if unknown:
        for e in unknown:
            lines.append(
                f"- [ ] **{e['entry_id']}** (section {e['section']})"
                f" — {e['body']}"
            )
            lines.append(f"  Source: {e['source']}")
    else:
        lines.append("None.")
    lines.append("")
    lines.append("## Decayed evidence")
    lines.append("")
    if decayed:
        for e in decayed:
            checked = e["checked_date"] if e["checked_date"] else "not recorded"
            lines.append(
                f"- [ ] **{e['entry_id']}** (section {e['section']})"
                f" — {e['label']}, checked {checked},"
                f" decay {e['decay_date']} — {e['body']}"
            )
            lines.append(f"  Source: {e['source']}")
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)
