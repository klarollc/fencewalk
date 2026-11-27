"""The computed attack-path graph: each chain's exposure, derived from
the standing scores its annotated steps name.

A chain step may name the rubric item it exercises (Deeper Slice 4a).
A chain's annotated steps are the steps that do; each is marked with
its item's standing status in the step's own pack — Covered, Partial,
Unknown, Not applicable, Gap — or "unscored" when the item has no
coverage row. From the annotated steps, in step order:

- interrupted: at least one annotated step is Covered; the earliest
  such step is named — the path reaches it and the control holds there;
- contested: none is Covered and at least one is Partial or Unknown;
  the earliest such step is named;
- open: every annotated step is Gap, Not applicable, or unscored.

The honesty constraint: a chain whose steps name no items is not
computed, and says so; it is never rendered as open, interrupted or
safe. Steps that name no item, in a partly annotated chain, are shown
unmarked and are not judged; the derivation rests on the annotated
steps only and says so.

A fix is related to a chain when its mapped rubric items intersect the
chain's annotated-step items. Related fixes are listed with their
status; nothing further is derived from them (a proposed fix interrupts
nothing until the rescore lands).

Everything is computed at render time from the store's current state
and never stored, so a rescore changes the derivation on the next
render. The database is opened with SQLite's mode=ro through the
registry's read-only Store adapter; no render can write the file.
"""

import sqlite3
from pathlib import Path

from .registry import _ReadOnlyStore

UNSCORED = "unscored"
HOLDS = ("Covered",)
CONTESTS = ("Partial", "Unknown")
INTERRUPTED, CONTESTED, OPEN = "interrupted", "contested", "open"


class ChainsError(ValueError):
    """A refusal: the chains cannot be rendered as asked."""


def annotated_steps(chain):
    """The chain's steps that name a rubric item, in step order."""
    return [s for s in chain["steps"] if s.get("item_id") is not None]


def has_annotated_step(chain):
    return bool(annotated_steps(chain))


def standing_statuses(store, chains):
    """{(item_pack, item_id): status} for every pack an annotated step
    names, from the store's current coverage."""
    packs = sorted({
        s["item_pack"] for chain in chains for s in annotated_steps(chain)
    })
    statuses = {}
    for pack_id in packs:
        for row in store.list_coverage(pack_id):
            statuses[(pack_id, row["item_id"])] = row["status"]
    return statuses


def mark(step, statuses):
    """An annotated step's mark: its item's standing status, or
    'unscored'."""
    return statuses.get((step["item_pack"], step["item_id"]), UNSCORED)


def derive(chain, statuses):
    """The chain's derived exposure, or None when it is not computed
    (no step names an item). Returns a dict: kind (interrupted /
    contested / open), step (the deciding annotated step, None for
    open), mark (that step's mark), annotated and steps (counts)."""
    annotated = annotated_steps(chain)
    if not annotated:
        return None
    marks = [(s, mark(s, statuses)) for s in annotated]
    result = {
        "annotated": len(annotated),
        "steps": len(chain["steps"]),
        "step": None,
        "mark": None,
    }
    for kind, deciding in ((INTERRUPTED, HOLDS), (CONTESTED, CONTESTS)):
        for step, step_mark in marks:
            if step_mark in deciding:
                result.update(kind=kind, step=step, mark=step_mark)
                return result
    result["kind"] = OPEN
    return result


def exposure_sentence(derivation, label):
    """The derivation in one sentence. label(item_id, item_pack) renders
    an item reference for the surface it appears on."""
    d = derivation
    if d["kind"] == INTERRUPTED:
        head = (
            f"interrupted at step {d['step']['step_no']}, where"
            f" {label(d['step']['item_id'], d['step']['item_pack'])}"
            " is Covered."
        )
    elif d["kind"] == CONTESTED:
        head = (
            f"contested at step {d['step']['step_no']}, where"
            f" {label(d['step']['item_id'], d['step']['item_pack'])}"
            f" is {d['mark']}; no annotated step is Covered."
        )
    else:
        head = (
            "open: every annotated step is Gap, Not applicable, or"
            " unscored, so nothing annotated holds."
        )
    if d["annotated"] == d["steps"]:
        basis = f" Derived from all {d['steps']} steps."
    else:
        which = (
            "the one that names an item" if d["annotated"] == 1
            else "those that name an item"
        )
        basis = (
            f" Derived from {d['annotated']} of {d['steps']} steps ({which});"
            " the other steps are not judged."
        )
    return head + basis


NOT_COMPUTED = (
    "not computed: no step of this chain names the rubric item it"
    " exercises."
)


def related_fixes(chain, fixes):
    """The fixes whose mapped rubric items intersect the chain's
    annotated-step items, in fix order. A mapping that stores its pack
    matches on (pack, item); one recorded before 0.3.4, with no stored
    pack, matches on the item alone."""
    step_items = {(s["item_pack"], s["item_id"]) for s in annotated_steps(chain)}
    step_ids = {item for _, item in step_items}
    related = []
    for fix in fixes:
        packs = fix.get("rubric_item_packs") or {}
        for item_id in fix["rubric_item_ids"]:
            stored = packs.get(item_id)
            if (stored, item_id) in step_items or (
                stored is None and item_id in step_ids
            ):
                related.append(fix)
                break
    return related


def report_exposures(db_path, chains):
    """For the report: {chain id: (derivation)} for every computed chain
    in chains (the report's gathered list_chains rows). Reads only the
    standing statuses the annotated steps need."""
    computed = [c for c in chains if has_annotated_step(c)]
    if not computed:
        return {}
    store = _open(db_path)
    try:
        statuses = standing_statuses(store, computed)
    finally:
        store.close()
    return {c["id"]: derive(c, statuses) for c in computed}


def _open(path):
    db = Path(path).expanduser()
    if not db.is_file():
        raise ChainsError(f"no such database: {path}")
    try:
        return _ReadOnlyStore(db.resolve())
    except sqlite3.Error as exc:
        raise ChainsError(f"cannot open database {path}: {exc}") from exc


def _item_ref(item_id, item_pack):
    return f"{item_id} ({item_pack})"


def render_chains(db_path):
    """Every chain, ordered by chain key: head, control line, steps with
    marks, derivation, related fixes. Never writes to the database."""
    store = _open(db_path)
    try:
        if store.get_engagement() is None:
            raise ChainsError(f"{db_path} holds no engagement")
        chains = store.list_chains()
        fixes = store.list_fixes()
        statuses = standing_statuses(store, chains)
    finally:
        store.close()

    if not chains:
        return "No chains recorded.\n"
    lines = []
    tally = {INTERRUPTED: 0, CONTESTED: 0, OPEN: 0, "not computed": 0}
    for chain in chains:
        lines.append(f"Chain {chain['chain_key']}: {chain['name']}")
        control = chain["earliest_control"]
        if chain["control_rubric"]:
            ref = chain["control_rubric"]
            if chain.get("control_pack"):
                ref = f"{chain['control_rubric']}, {chain['control_pack']}"
            control = f"{control} ({ref})"
        lines.append(
            f"  Earliest breaking control: {control}"
            f" Status: {chain['control_status']}."
        )
        for step in chain["steps"]:
            line = f"  {step['step_no']}. {step['phase']}: {step['text']}"
            if step.get("item_id") is not None:
                line += (
                    f"\n     item {_item_ref(step['item_id'], step['item_pack'])}"
                    f" — {mark(step, statuses)}"
                )
            lines.append(line)
        derivation = derive(chain, statuses)
        if derivation is None:
            lines.append(f"  Exposure: {NOT_COMPUTED}")
            tally["not computed"] += 1
        else:
            lines.append(
                f"  Exposure: {exposure_sentence(derivation, _item_ref)}"
            )
            tally[derivation["kind"]] += 1
        if derivation is None:
            lines.append("  Related fixes: none (no step names an item)")
        else:
            related = related_fixes(chain, fixes)
            lines.append(
                "  Related fixes: "
                + (", ".join(f"{f['fix_id']} ({f['status']})" for f in related)
                   if related else "none")
            )
        lines.append("")
    lines.append(
        "Exposure: " + " · ".join(f"{k} {v}" for k, v in tally.items())
    )
    return "\n".join(lines) + "\n"
