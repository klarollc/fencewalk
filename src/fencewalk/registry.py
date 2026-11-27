"""Local engagement paths; metadata is always read from the databases.

The JSON file is a list of {path, registered_date} objects. Reads never
create it. Database connections use SQLite's mode=ro, including when
validating a registration; no migration or write is possible.
"""

import datetime
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .store import ADDED_COLUMNS, Store


def registry_path(override=None):
    """Flag beats environment beats the per-user default."""
    return Path(
        override if override is not None else
        os.environ.get("FENCEWALK_REGISTRY", "~/.fencewalk/registry.json")
    ).expanduser().resolve()


def canonical_path(db):
    return Path(db).expanduser().resolve()


class _ReadOnlyStore(Store):
    """Use the existing Store reads with an explicitly read-only connection.

    Store's constructor opens a writable connection. This local adapter
    supplies the same read state without changing Store or invoking its
    migration path. default_pack_id() remains the single pack-default rule.
    """

    def __init__(self, path):
        self.db_path = str(path)
        self.conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        try:
            self._added_columns = {
                (table, column): self._probe_column(table, column)
                for table, column, _decl in ADDED_COLUMNS
            }
            self._migrated = False
        except Exception:
            self.conn.close()
            raise


def engagement_details(path):
    """Read live metadata and counts, never opening a writable database."""
    try:
        with _ReadOnlyStore(path) as store:
            eng = store.get_engagement()
            if eng is None:
                raise ValueError("database holds no engagement")
            for field in ("name", "subject_label", "created_date", "method_order"):
                if field not in eng:
                    raise ValueError(f"engagement lacks field: {field}")
            pack = store.default_pack_id()
            entries = store.conn.execute(
                "SELECT COUNT(*) FROM inventory_entry WHERE engagement_id = ?",
                (eng["id"],),
            ).fetchone()[0]
            scored = store.conn.execute(
                "SELECT COUNT(*) FROM coverage_score"
                " WHERE engagement_id = ? AND pack_id = ? AND status IS NOT NULL",
                (eng["id"], pack),
            ).fetchone()[0]
            return {
                "subject": eng["subject_label"], "name": eng["name"],
                "created": eng["created_date"], "default_pack": pack,
                "packs": len(store.list_packs()), "entries": entries,
                "scored": scored,
            }
    except (sqlite3.Error, ValueError) as exc:
        raise ValueError(f"invalid engagement database {path}: {exc}") from exc


def _read(path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except UnicodeError as exc:
        raise ValueError(f"invalid registry {path}: {exc}") from exc
    try:
        entries = json.loads(text)
        if not isinstance(entries, list):
            raise ValueError("expected a list")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "registered_date"}:
                raise ValueError("expected only path and registered_date per entry")
            db, date = entry["path"], entry["registered_date"]
            if not isinstance(db, str) or not Path(db).is_absolute():
                raise ValueError("expected an absolute database path")
            if not isinstance(date, str) or datetime.date.fromisoformat(date).isoformat() != date:
                raise ValueError("expected an ISO registration date")
            if db in seen:
                raise ValueError("duplicate database path")
            seen.add(db)
        return entries
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid registry {path}: {exc}") from exc


def _write(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(entries, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def register(db, path):
    entries = _read(path)
    db = canonical_path(db)
    if any(entry["path"] == str(db) for entry in entries):
        raise ValueError(f"database already registered: {db}")
    if not db.is_file():
        raise ValueError(f"no such database file: {db}")
    details = engagement_details(db)
    entries.append({
        "path": str(db), "registered_date": datetime.date.today().isoformat(),
    })
    _write(path, entries)
    return details["subject"]


def unregister(db, path):
    entries = _read(path)
    db = canonical_path(db)
    remaining = [entry for entry in entries if entry["path"] != str(db)]
    if len(remaining) == len(entries):
        raise ValueError(f"database is not registered: {db}")
    # Deliberately never open the database: it may be missing or unreadable.
    _write(path, remaining)


def engagements(path):
    rows, missing = [], []
    for entry in _read(path):
        db = Path(entry["path"])
        if not db.exists():
            missing.append({"path": str(db), "missing": True})
        else:
            rows.append({"path": str(db), **engagement_details(db)})
    rows.sort(key=lambda row: (row["created"], row["subject"], row["path"]))
    # Missing databases have no created date or subject to sort on.
    return rows + sorted(missing, key=lambda row: row["path"])
