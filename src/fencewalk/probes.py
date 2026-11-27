"""Behavioral verification probes: the read-only listings.

A probe is the operator doing the thing a control claims to govern —
requesting the record, attempting the sign-in path, triggering the
alert — and writing down what happened: confirmed, failed, or
inconclusive (`record-probe`, append-only). Documentary evidence says a
control is on record; a probe says whether it behaved.

`probes` lists, for one pack, each probed item's latest probe. With
--unprobed it lists instead the Covered and Partial items with no probe
on record: the claims resting on documents alone.

Probes never change scores. A failed probe is a fact on record; acting
on it (rescore) stays the operator's hand.

The database is opened with SQLite's mode=ro through the registry's
read-only Store adapter, and Store.list_probes treats a database from
before the probe_result table as having no probes, so no listing can
create the table or write the file.
"""

import sqlite3
from pathlib import Path

from .registry import _ReadOnlyStore

DOCUMENTARY_STATUSES = ("Covered", "Partial")


class ProbesError(ValueError):
    """A refusal: the listing cannot be rendered as asked."""


def _open(path):
    db = Path(path).expanduser()
    if not db.is_file():
        raise ProbesError(f"no such database: {path}")
    try:
        return _ReadOnlyStore(db.resolve())
    except sqlite3.Error as exc:
        raise ProbesError(f"cannot open database {path}: {exc}") from exc


def _pack(store, db_path, pack_id):
    if pack_id is None:
        pack_id = store.default_pack_id()
        if pack_id is None:
            raise ProbesError(f"{db_path} has no rubric pack loaded")
    pack = store.get_pack(pack_id)
    if pack is None:
        raise ProbesError(f"no such pack: {pack_id}")
    return pack


def latest_by_item(probes):
    """item_id -> (latest probe, probe count), from list_probes rows
    (ordered by item, then date, then record order: the last row for an
    item is its latest)."""
    latest = {}
    for probe in probes:
        _, count = latest.get(probe["item_id"], (None, 0))
        latest[probe["item_id"]] = (probe, count + 1)
    return latest


def render_probes(db_path, pack_id=None, unprobed=False):
    """The probes listing (or, with unprobed, the documentary-only
    listing) as text. Never writes to the database."""
    store = _open(db_path)
    try:
        pack = _pack(store, db_path, pack_id)
        groups = {
            i["item_id"]: i["group_name"]
            for i in store.list_pack_items(pack["pack_id"])
        }
        scores = store.list_coverage(pack["pack_id"])
        probes = store.list_probes(pack["pack_id"])
    finally:
        store.close()

    latest = latest_by_item(probes)
    lines = [f"Pack: {pack['pack_id']} ({pack['title']})"]
    if unprobed:
        claims = [s for s in scores if s["status"] in DOCUMENTARY_STATUSES]
        bare = [s for s in claims if s["item_id"] not in latest]
        for score in bare:
            lines.append(
                f"{score['item_id']} ({groups[score['item_id']]})"
                f" {score['status']} — no probe on record"
            )
        if not claims:
            lines.append("No Covered or Partial items are scored.")
        elif not bare:
            lines.append("Every Covered or Partial item has a probe on record.")
        lines.append(
            f"Unprobed: {len(bare)} of {len(claims)} Covered or Partial items"
        )
        return "\n".join(lines) + "\n"

    if not latest:
        lines.append("No probes recorded.")
        return "\n".join(lines) + "\n"
    tallies = {"confirmed": 0, "failed": 0, "inconclusive": 0}
    for item_id, (probe, count) in latest.items():
        tallies[probe["outcome"]] += 1
        lines.append(
            f"{item_id} ({groups[item_id]}) {probe['outcome']}"
            f" — {probe['date']} · {probe['actor']}"
            f" · {count} {'probe' if count == 1 else 'probes'} on record"
        )
        lines.append(f"  method: {probe['method']}")
    lines.append(
        "Latest outcomes: "
        + " · ".join(f"{k} {v}" for k, v in tallies.items())
        + f" · probes on record {len(probes)}"
    )
    return "\n".join(lines) + "\n"
