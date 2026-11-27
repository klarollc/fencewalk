"""Single-fix packet: everything recorded about one fix, for working it
by hand.

A view, not a record: unlike `packet` (the whole-engagement packet,
which is recorded with its hash), rendering a fix packet writes
nothing and records no run. The database is opened with SQLite's
mode=ro through the registry's read-only Store adapter, so no read
here can migrate or write it. The output carries no wall-clock value:
repeated renders of the same database are byte-identical.

Rubric text, reasoning and action text are rendered verbatim, outside
tables, so no escaping touches them.
"""

import sqlite3
from pathlib import Path

from .registry import _ReadOnlyStore


class FixPacketError(ValueError):
    """A refusal: the packet cannot be rendered as asked."""


def _open(path):
    db = Path(path).expanduser()
    if not db.is_file():
        raise FixPacketError(f"no such database: {path}")
    try:
        return _ReadOnlyStore(db.resolve())
    except sqlite3.Error as exc:
        raise FixPacketError(f"cannot open database {path}: {exc}") from exc


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _item_pack(item_id, stored_pack, packs):
    """The pack a mapping belongs to: the pack stored with it, else
    (a citation recorded before 0.3.4) the one loaded pack holding the
    item, else None."""
    if stored_pack is not None:
        return stored_pack
    owners = [p for p in packs if item_id in packs[p]]
    return owners[0] if len(owners) == 1 else None


def render_fix_packet(db_path, fix_id):
    """Render the Markdown packet for one fix. Raises FixPacketError for
    an unknown fix_id. Never writes to the database."""
    store = _open(db_path)
    try:
        return _render(store, fix_id)
    finally:
        store.close()


def _render(store, fix_id):
    fix = next((f for f in store.list_fixes() if f["fix_id"] == fix_id), None)
    if fix is None:
        raise FixPacketError(f"no such fix: {fix_id}")
    eng = store.get_engagement() or {}
    packs = {
        p["pack_id"]: {i["item_id"]: i for i in store.list_items(p["pack_id"])}
        for p in store.list_packs()
    }
    titles = {p["pack_id"]: p["title"] for p in store.list_packs()}
    labels = {e["entry_id"]: e["label"] for e in store.list_inventory()}

    mapped = []
    for item_id in fix["rubric_item_ids"]:
        pack_id = _item_pack(
            item_id, fix["rubric_item_packs"].get(item_id), packs
        )
        mapped.append((pack_id, item_id))
    # By pack, then item_id; a mapping whose pack is unknowable sorts last.
    mapped.sort(key=lambda m: (m[0] is None, m[0] or "", m[1]))

    lines = [
        f"# {fix['fix_id']} — {fix['action']}",
        "",
        f"- Subject: {eng.get('subject_label', '—')}",
        f"- Engagement: {eng.get('name', '—')}",
        f"- Status: {fix['status']} ({fix['status_date']},"
        f" {fix['status_actor']}) · effort {fix['effort']}"
        f" · breaks {fix['chains_broken']}",
        "",
        "## Status history",
        "",
        "| Status | Date | Actor |",
        "|---|---|---|",
    ]
    for row in store.list_fix_status_history(fix_id):
        lines.append(
            f"| {_cell(row['status'])} | {_cell(row['date'])}"
            f" | {_cell(row['actor'])} |"
        )
    lines += ["", "## Mapped rubric items", ""]

    to_verify = []
    if not mapped:
        lines += ["No mapped rubric items.", ""]
    for pack_id, item_id in mapped:
        item = packs.get(pack_id, {}).get(item_id) if pack_id else None
        score = store.get_coverage(pack_id, item_id) if item else None
        status = score["status"] if score else "not scored"
        if status != "Covered":
            to_verify.append((item_id, status))
        if pack_id is None:
            pack_line = "not recorded (the item is in no single loaded pack)"
        else:
            pack_line = f"`{pack_id}` — {titles.get(pack_id, 'not loaded')}"
        lines += [
            f"### `{item_id}`",
            "",
            f"- Pack: {pack_line}",
            "- Rubric text: "
            + (item["text"] if item else "not in a loaded pack"),
        ]
        if score:
            lines.append(f"- Coverage: {status} — {score['reasoning']}")
            if score["na_reason"]:
                lines.append(f"- N/A reason: {score['na_reason']}")
            cited = score["cited_entry_ids"]
            lines.append(
                "- Cited entries: "
                + (", ".join(
                    f"`{e}` ({labels.get(e, 'not in inventory')})"
                    for e in cited
                ) if cited else "none")
            )
        else:
            lines.append("- Coverage: not scored")
        lines.append("")

    lines += ["## Verify by rescore", ""]
    if not mapped:
        lines.append("No mapped rubric items to rescore.")
    elif not to_verify:
        lines.append("All mapped items are Covered.")
    else:
        lines.append("When the fix lands, rescore:")
        lines.append("")
        lines += [f"- `{item_id}` · {status}" for item_id, status in to_verify]
    lines.append("")
    return "\n".join(lines)
