"""Drift report: what changed between two copies of one engagement.

The operator's re-audit discipline: copy the engagement database
before a re-audit, then diff the copy (older) against the current
database (newer). The comparison is of current state only — each
item's coverage status, each inventory entry's label, each fix's
status — never of history tables, reasoning text, chains, or
verify-next items.

Both databases are opened with SQLite's mode=ro through the
registry's read-only Store adapter, so no read here can migrate or
write either file. The output carries no wall-clock value: the same
pair of databases renders byte-identical text.
"""

import sqlite3
from pathlib import Path

from .registry import _ReadOnlyStore
from .report import _tally_line


class DiffError(ValueError):
    """A refusal: the pair cannot be compared as asked."""


def _open(path):
    db = Path(path).expanduser()
    if not db.is_file():
        raise DiffError(f"no such database: {path}")
    try:
        return _ReadOnlyStore(db.resolve())
    except sqlite3.Error as exc:
        raise DiffError(f"cannot open database {path}: {exc}") from exc


def _engagement(store, path):
    """The database's one engagement row. Exactly one is required:
    the schema does not forbid a second row, and with two the
    same-engagement check would have no single answer."""
    try:
        rows = store.conn.execute(
            "SELECT COUNT(*) FROM engagement"
        ).fetchone()[0]
    except sqlite3.Error as exc:
        raise DiffError(f"not an engagement database: {path}: {exc}") from exc
    if rows != 1:
        raise DiffError(
            f"{path} holds {rows} engagement rows; diff needs exactly one"
        )
    return store.get_engagement()


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(header, rows):
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return lines


def _section(title, header, rows, unchanged, noun):
    lines = [f"## {title}", ""]
    if rows:
        lines += _table(header, rows)
    else:
        lines.append("No changes.")
    lines += ["", f"{unchanged} {noun} unchanged.", ""]
    return lines


def _coverage_changes(old, new):
    """(rows, unchanged) for one pack's coverage, keyed by item_id."""
    rows, unchanged = [], 0
    for item in sorted(set(old) | set(new)):
        was = old.get(item, "not scored")
        now = new.get(item, "not scored")
        if was == now:
            unchanged += 1
        else:
            rows.append((f"`{item}`", was, now))
    return rows, unchanged


def _keyed_changes(old, new, status_date=None):
    """(rows, unchanged) for inventory entries or fixes: a status that
    differs, or a key present on one side only (added / removed).
    old and new map key -> current status; status_date, when given,
    maps key -> the newer side's status date and adds that column."""
    rows, unchanged = [], 0
    for key in sorted(set(old) | set(new)):
        if key in old and key in new:
            if old[key] == new[key]:
                unchanged += 1
                continue
            row = [f"`{key}`", "changed", old[key], new[key]]
        elif key in new:
            row = [f"`{key}`", "added", "—", new[key]]
        else:
            row = [f"`{key}`", "removed", old[key], "—"]
        if status_date is not None:
            row.append(status_date.get(key, "—"))
        rows.append(tuple(row))
    return rows, unchanged


def render_diff(older_path, newer_path, pack_id=None):
    """Render the Markdown drift report for older_path -> newer_path.

    pack_id names the compared pack; the default is the newer
    database's default pack. Raises DiffError when the two databases
    are different engagements, or the pack is not loaded on both
    sides. Never writes to either database.
    """
    older = _open(older_path)
    try:
        newer = _open(newer_path)
        try:
            return _render(older, newer, older_path, newer_path, pack_id)
        finally:
            newer.close()
    finally:
        older.close()


def _render(older, newer, older_path, newer_path, pack_id):
    old_eng = _engagement(older, older_path)
    new_eng = _engagement(newer, newer_path)
    for field in ("subject_label", "created_date"):
        if old_eng[field] != new_eng[field]:
            raise DiffError(
                "the databases are different engagements"
                f" ({field}: {old_eng[field]!r} vs {new_eng[field]!r});"
                " diff compares two copies of one engagement"
            )

    if pack_id is None:
        pack_id = newer.default_pack_id()
        if pack_id is None:
            raise DiffError(f"{newer_path} has no rubric pack loaded")
    elif newer.get_pack(pack_id) is None:
        raise DiffError(f"pack {pack_id} is not loaded in {newer_path}")
    if older.get_pack(pack_id) is None:
        raise DiffError(f"pack {pack_id} is not loaded in {older_path}")
    pack = newer.get_pack(pack_id)

    cov_rows, cov_same = _coverage_changes(
        {c["item_id"]: c["status"] for c in older.list_coverage(pack_id)},
        {c["item_id"]: c["status"] for c in newer.list_coverage(pack_id)},
    )
    inv_rows, inv_same = _keyed_changes(
        {e["entry_id"]: e["label"] for e in older.list_inventory()},
        {e["entry_id"]: e["label"] for e in newer.list_inventory()},
    )
    new_fixes = newer.list_fixes()
    fix_rows, fix_same = _keyed_changes(
        {f["fix_id"]: f["status"] for f in older.list_fixes()},
        {f["fix_id"]: f["status"] for f in new_fixes},
        status_date={f["fix_id"]: f["status_date"] for f in new_fixes},
    )

    name = new_eng["name"]
    if old_eng["name"] != name:
        name = f"{old_eng['name']} → {name}"
    lines = [
        f"# Drift report — {name}",
        "",
        f"- Subject: {new_eng['subject_label']}",
        f"- Engagement: {name}",
        f"- Engagement created: {new_eng['created_date']}",
        f"- Older: `{older_path}`",
        f"- Newer: `{newer_path}`",
        f"- Compared pack: `{pack_id}` — {pack['title']}",
        f"- Older posture: {_tally_line(older.coverage_tallies(pack_id))}",
        f"- Newer posture: {_tally_line(newer.coverage_tallies(pack_id))}",
        "",
    ]
    lines += _section(
        "Coverage changes", ("Item", "Was", "Now"),
        cov_rows, cov_same, "items",
    )
    lines += _section(
        "Inventory changes", ("Entry", "Change", "Was", "Now"),
        inv_rows, inv_same, "entries",
    )
    lines += _section(
        "Fix changes", ("Fix", "Change", "Was", "Now", "Status date"),
        fix_rows, fix_same, "fixes",
    )
    lines += [
        "## Totals",
        "",
        f"Coverage changes {len(cov_rows)} · inventory changes"
        f" {len(inv_rows)} · fix changes {len(fix_rows)}",
        "",
    ]
    return "\n".join(lines)
