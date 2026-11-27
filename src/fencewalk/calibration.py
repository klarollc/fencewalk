"""Calibration report: how past model runs' coverage proposals compare
with the record.

For every stored run recorded against a packet for the compared pack
that has at least one adjudication event in the coverage section, the
run's per-item proposed statuses are read from its coverage section and
compared with each item's current standing status. The tallies — by
rubric group, by packet posture, by run, and overall — are a prior the
operator can hold before the next pass: where this kind of pass has
over- or under-called.

Proposals are read through the draft's own section machinery
(draft.split_sections): the coverage section is the one the draft
recognises, and within it a row is a Markdown table row. A row is read
when exactly one of its cells is a pack item ID and exactly one is a
status — the shape the run brief and the adversarial brief both
mandate, whatever the column order. A row that names a pack item but
does not hold exactly one status cell, or that names an item another
row of the same run also names, is excluded and counted, never guessed.

The database is opened with SQLite's mode=ro through the registry's
read-only Store adapter, so no read here can migrate or write the file.
A database from before the model-pass tables raises on the read-only
open of those tables instead of creating them; that is caught and
treated as no runs recorded. The output carries no wall-clock value:
the same database renders byte-identical text.
"""

import sqlite3
from pathlib import Path

from .draft import split_sections
from .registry import _ReadOnlyStore

COVERAGE_SECTION = "Coverage map"  # the draft's name for the deliverable

# The optimism axis. Not applicable is off the axis.
AXIS_RANK = {"Covered": 4, "Partial": 3, "Unknown": 2, "Gap": 1}
NOT_APPLICABLE = "Not applicable"
STATUSES = tuple(AXIS_RANK) + (NOT_APPLICABLE,)

BUCKETS = (
    "agree",
    "model optimistic",
    "model pessimistic",
    "n/a-involved",
    "standing unscored",
)
POSTURES = ("standard", "adversarial")

TALLY_HEADER = (
    "Compared", "Agree", "Model optimistic", "Model pessimistic",
    "N/A-involved", "Standing unscored", "Agreement",
)


class CalibrationError(ValueError):
    """A refusal: the database cannot be calibrated as asked."""


def _open(path):
    db = Path(path).expanduser()
    if not db.is_file():
        raise CalibrationError(f"no such database: {path}")
    try:
        return _ReadOnlyStore(db.resolve())
    except sqlite3.Error as exc:
        raise CalibrationError(f"cannot open database {path}: {exc}") from exc


def _plain(cell):
    """A table cell's text without surrounding whitespace, emphasis or
    code marks (formatting, not content)."""
    return cell.strip().strip("*_`").strip()


def _row_cells(line):
    """The cells of a Markdown table row, or None for a line that is not
    a table row or is a header separator."""
    text = line.strip()
    if not text.startswith("|"):
        return None
    cells = [_plain(c) for c in text.strip("|").split("|")]
    if all(set(c) <= set("-: ") for c in cells):
        return None
    return cells


def read_proposals(raw_output, item_ids):
    """(proposals, unreadable) for one run's raw output.

    proposals maps item_id -> proposed status; unreadable is the count
    of coverage rows that name a pack item but are not read: no status
    cell or more than one, more than one item ID, or an item another
    row also names (every row naming that item is then excluded).
    """
    _preamble, sections = split_sections(raw_output)
    coverage = dict(sections).get(COVERAGE_SECTION, [])
    named = []  # (item_ids named in the row, statuses in the row)
    for line in coverage:
        cells = _row_cells(line)
        if cells is None:
            continue
        ids = [c for c in cells if c in item_ids]
        if not ids:
            continue
        named.append((ids, [c for c in cells if c in STATUSES]))
    rows_per_item = {}
    for ids, _statuses in named:
        for item_id in ids:
            rows_per_item[item_id] = rows_per_item.get(item_id, 0) + 1
    proposals, unreadable = {}, 0
    for ids, statuses in named:
        if (len(ids) == 1 and len(statuses) == 1
                and rows_per_item[ids[0]] == 1):
            proposals[ids[0]] = statuses[0]
        else:
            unreadable += 1
    return proposals, unreadable


def bucket(proposed, standing):
    """The comparison bucket for one proposal against the standing
    status (None when the item has no standing score)."""
    if standing is None:
        return "standing unscored"
    if proposed == standing:
        return "agree"
    if NOT_APPLICABLE in (proposed, standing):
        return "n/a-involved"
    if AXIS_RANK[proposed] > AXIS_RANK[standing]:
        return "model optimistic"
    return "model pessimistic"


def _empty():
    return {b: 0 for b in BUCKETS}


def _share(tally):
    compared = sum(tally.values())
    if not compared:
        return "—"
    return f"{100 * tally['agree'] / compared:.1f}%"


def _tally_cells(tally):
    return [str(sum(tally.values()))] + [str(tally[b]) for b in BUCKETS] + [
        _share(tally)
    ]


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


def _model_pass_records(store):
    """(runs, adjudications by run id), each run carrying its packet's
    posture and pack, or empty records for a database from before the model-pass tables:
    the read-only open of a missing table raises instead of creating
    it, and that is read as no runs recorded."""
    try:
        runs = store.list_runs()
    except sqlite3.OperationalError:
        return [], {}
    postures, packs, adjudications = {}, {}, {}
    for run in runs:
        record = store.get_packet_by_hash(run["packet_hash"])
        if record is not None:
            postures[run["packet_hash"]] = record["posture"]
            packs[run["packet_hash"]] = record["pack_id"]
        try:
            adjudications[run["id"]] = store.list_adjudications(run["id"])
        except sqlite3.OperationalError:
            adjudications[run["id"]] = []
    runs = [
        dict(run, posture=postures[run["packet_hash"]],
             pack_id=packs[run["packet_hash"]])
        for run in runs if run["packet_hash"] in packs
    ]
    return runs, adjudications


def render_calibration(db_path, pack_id=None):
    """Render the Markdown calibration report for one database.

    pack_id names the compared pack; the default is the database's
    default pack (Store.default_pack_id). Never writes to the database.
    """
    store = _open(db_path)
    try:
        return _render(store, db_path, pack_id)
    finally:
        store.close()


def _render(store, db_path, pack_id):
    try:
        eng = store.get_engagement()
    except sqlite3.Error as exc:
        raise CalibrationError(
            f"not an engagement database: {db_path}: {exc}"
        ) from exc
    if eng is None:
        raise CalibrationError(f"{db_path} holds no engagement")
    if pack_id is None:
        pack_id = store.default_pack_id()
        if pack_id is None:
            raise CalibrationError(f"{db_path} has no rubric pack loaded")
    pack = store.get_pack(pack_id)
    if pack is None:
        raise CalibrationError(f"pack {pack_id} is not loaded in {db_path}")
    items = store.list_pack_items(pack_id)
    item_ids = {item["item_id"] for item in items}
    group_of = {item["item_id"]: item["group_name"] for item in items}
    groups = []
    for item in items:
        if item["group_name"] not in groups:
            groups.append(item["group_name"])
    standing = {c["item_id"]: c["status"] for c in store.list_coverage(pack_id)}

    runs, adjudications = _model_pass_records(store)
    pack_runs = [run for run in runs if run["pack_id"] == pack_id]
    qualifying = [
        run for run in pack_runs
        if any(a["section"] == "coverage" for a in adjudications[run["id"]])
    ]
    excluded = len(pack_runs) - len(qualifying)

    by_group = {group: _empty() for group in groups}
    by_posture = {posture: _empty() for posture in POSTURES}
    overall = _empty()
    run_rows = []
    unreadable = 0
    for run in qualifying:
        proposals, run_unreadable = read_proposals(run["raw_output"], item_ids)
        unreadable += run_unreadable
        run_tally = _empty()
        for item_id, proposed in proposals.items():
            b = bucket(proposed, standing.get(item_id))
            for tally in (by_group[group_of[item_id]],
                          by_posture[run["posture"]], overall, run_tally):
                tally[b] += 1
        run_rows.append((
            run["id"], run["model_label"], run["run_date"], run["posture"],
            sum(run_tally.values()), _share(run_tally),
        ))

    lines = [
        f"# Calibration report — {eng['name']}",
        "",
        f"- Subject: {eng['subject_label']}",
        f"- Engagement: {eng['name']}",
        f"- Compared pack: `{pack_id}` — {pack['title']}",
        f"- Runs qualifying: {len(qualifying)}",
        f"- {excluded} runs not adjudicated for coverage — excluded",
        f"- {unreadable} rows not readable — excluded",
        "",
    ]
    if not qualifying:
        lines += [
            "No run qualifies for calibration: no model run recorded"
            f" against a `{pack_id}` packet has an adjudication event in"
            " the coverage section.",
            "",
        ]
        return "\n".join(lines)

    lines += ["## By group", ""]
    lines += _table(
        ("Group",) + TALLY_HEADER,
        [[group] + _tally_cells(by_group[group]) for group in groups],
    )
    lines += ["", "## By posture", ""]
    lines += _table(
        ("Posture",) + TALLY_HEADER,
        [[posture] + _tally_cells(by_posture[posture]) for posture in POSTURES],
    )
    lines += ["", "## By run", ""]
    lines += _table(
        ("Run", "Model", "Run date", "Posture", "Compared", "Agreement"),
        run_rows,
    )
    lines += ["", "## Overall", ""]
    lines += _table(TALLY_HEADER, [_tally_cells(overall)])
    lines += [
        "",
        "## Reading this",
        "",
        "Each proposal a qualifying run made in its coverage section is"
        " compared with the item's standing status as it is recorded"
        " today. Model optimistic means the proposal sits above the"
        " standing status on the axis Covered > Partial > Unknown > Gap;"
        " model pessimistic means below it. Not applicable is off that"
        " axis: a pair with exactly one side Not applicable is"
        " n/a-involved, and two Not applicable sides agree. Compared"
        " counts every proposal read, including those whose item has no"
        " standing score; agreement is agree divided by compared.",
        "",
        "Standing scores are as of today. A score changed since"
        " adjudication for any reason counts exactly as an overturn does,"
        " and agreement is measured against the record, not against the"
        " adjudicator's intent.",
        "",
    ]
    return "\n".join(lines)
