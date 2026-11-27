"""PDF renderer: the engagement report as a PDF file.

Renders the same report as the Markdown renderer, from the same data
(gather_report_data in report.py) — one data function, two renderers.
Every count and tally is computed from the store at render time; no
tally appears as a literal here.

Visual rules (brief §5): tables, not cards; the posture summary is
plain lines under a hairline rule; amber appears only for UNKNOWN and
Gap status text in the coverage table; IDs, hashes, dates, and counts
render in Courier, everything else in Helvetica.
"""

import hashlib
import json
import re

from .pdf import AMBER, INK, Document
from .report import (
    ADJUDICATION_SECTION_LABELS,
    _tally_line,
    cite_item,
    cross_pack_citations,
    gather_report_data,
)
from .store import ADJUDICATION_SECTIONS, FIX_STATUSES

COVERAGE_WIDTHS = [62, 78, 62, 212, 90]
FIX_WIDTHS = [38, 190, 62, 44, 84, 86]

_NUM_RUN = re.compile(r"(\d+(?:[.\-]\d+)*)")


def _num_runs(text, size=10):
    """Split text into runs, rendering digit runs in Courier.

    Dates (2026-11-18), decimals (1.4), and bare counts (48) are
    digit runs; the rest stays Helvetica. This is how the "counts in
    Courier" rule is applied to structured lines.

    A space that falls at the start of a run is moved to the end of
    the previous run: PDF readers that position each run separately
    drop a leading space, so "48 entries" would extract as
    "48entries". A trailing space survives extraction.
    """
    parts = []
    for part in _NUM_RUN.split(text):
        if not part:
            continue
        if _NUM_RUN.fullmatch(part):
            parts.append([part, "courier", size])
        else:
            parts.append([part, "helvetica", size])
    for i in range(1, len(parts)):
        if parts[i][0].startswith(" "):
            parts[i][0] = parts[i][0][1:]
            parts[i - 1][0] += " "
    return [(t, f, s) for t, f, s in parts if t]


def render_pdf(db_path, pack_id=None):
    data = gather_report_data(db_path, pack_id)
    # The /ID is content-bound: the SHA-256 of the canonical JSON
    # serialization of the gathered report data. Two renders of the
    # same database produce identical bytes. The 0.3.3 disclosure
    # fields join the hashed data only when they change what is
    # rendered (an unscored item, a cross-pack citation), so a report
    # that renders exactly as before keeps exactly its old /ID. The
    # 0.3.4 stored-pack fields follow the same rule: they are left
    # out of the hashed rows and reach the /ID through
    # cross_pack_citations, which resolves owners from them. The
    # engagement's primary_pack is left out the same way: it only
    # chooses the rendered pack, which the hashed data already names.
    id_data = {
        k: v for k, v in data.items()
        if k not in ("pack_item_count", "not_scored", "item_packs")
    }
    id_data["engagement"] = {
        k: v for k, v in data["engagement"].items() if k != "primary_pack"
    }
    id_data["fixes"] = [
        {k: v for k, v in fix.items() if k != "rubric_item_packs"}
        for fix in data["fixes"]
    ]
    id_data["chains"] = [
        {k: v for k, v in chain.items() if k != "control_pack"}
        for chain in data["chains"]
    ]
    # Deeper Slice 4a's step item references render nothing, so they
    # stay out of the hashed rows, as control_pack does.
    for chain in id_data["chains"]:
        chain["steps"] = [
            {k: v for k, v in step.items() if k not in ("item_id", "item_pack")}
            for step in chain["steps"]
        ]
    if data["not_scored"] > 0:
        id_data["not_scored"] = data["not_scored"]
        id_data["pack_item_count"] = data["pack_item_count"]
    cross = cross_pack_citations(data)
    if cross:
        id_data["cross_pack_citations"] = cross
    canonical = json.dumps(
        id_data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    doc_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    eng = data["engagement"]
    label_counts = data["label_counts"]
    entries = data["entries"]
    pack = data["pack"]
    coverage = data["coverage"]
    tallies = data["tallies"]
    chains = data["chains"]
    fixes = data["fixes"]
    fix_counts = data["fix_counts"]
    verify_next = data["verify_next"]
    adjudicated = data["adjudicated"]
    item_packs = data["item_packs"]
    rendered_pack = data["pack_id"]
    tally = _tally_line(tallies, data["not_scored"], data["pack_item_count"])

    title = f"Fencewalk engagement report — {eng['name']}"
    doc = Document(title=title, doc_id=doc_id, footer_left=title)

    # 1. Title block.
    doc.title_block(f"Engagement report — {eng['name']}")
    doc.paragraph([("Subject: ", "helvetica", 10), (eng["subject_label"], "helvetica", 10)])
    doc.paragraph(
        [("Engagement created: ", "helvetica", 10), (eng["created_date"], "courier", 10)]
    )
    doc.paragraph(
        [("Method order: ", "helvetica", 10), (eng["method_order"], "helvetica", 10)]
    )
    doc.paragraph(
        [
            ("Rubric pack: ", "helvetica", 10),
            (f"{pack['title']} ({pack['source_citation']})", "helvetica", 10),
        ]
    )

    # 2. Posture summary.
    doc.heading("Posture summary", level=1)
    doc.rule()
    inv_parts = ", ".join(
        f"{label} {label_counts.get(label, 0)}"
        for label in ("VERIFIED", "ON RECORD", "UNKNOWN")
    )
    fix_parts = ", ".join(
        f"{status} {fix_counts.get(status, 0)}" for status in FIX_STATUSES
    )
    doc.paragraph(
        [("Inventory: ", "helvetica", 10)]
        + _num_runs(f"{len(entries)} entries ({inv_parts})")
    )
    doc.paragraph(
        [("Coverage: ", "helvetica", 10)] + _num_runs(tally)
    )
    doc.paragraph(
        [("Attack chains: ", "helvetica", 10)] + _num_runs(str(len(chains)))
    )
    doc.paragraph(
        [("Fixes: ", "helvetica", 10)]
        + _num_runs(f"{len(fixes)} ({fix_parts})")
    )
    doc.paragraph(
        [("Verify-next items: ", "helvetica", 10)] + _num_runs(str(len(verify_next)))
    )

    # 3. Coverage.
    doc.heading("Coverage", level=1)
    doc.paragraph([("Tallies: ", "helvetica", 10)] + _num_runs(tally))
    cov_rows = []
    for row in coverage:
        reasoning = row["reasoning"]
        if row["status"] == "Not applicable" and row["na_reason"]:
            reasoning = f"{reasoning} N/A reason: {row['na_reason']}"
        cited = ", ".join(row["cited_entry_ids"]) if row["cited_entry_ids"] else "—"
        status_color = AMBER if row["status"] in ("UNKNOWN", "Gap") else INK
        cov_rows.append(
            [
                (row["item_id"], "courier", INK),
                (row["group_name"], "helvetica", INK),
                (row["status"], "helvetica", status_color),
                (reasoning, "helvetica", INK),
                (cited, "courier", INK),
            ]
        )
    doc.table(
        ["Item", "Group", "Status", "Reasoning", "Cited entries"],
        cov_rows,
        COVERAGE_WIDTHS,
    )

    # 4. Attack chains.
    doc.heading("Attack chains", level=1)
    for chain in chains:
        doc.heading(f"Chain {chain['chain_key']}: {chain['name']}", level=2)
        for step in chain["steps"]:
            doc.paragraph(
                [
                    (f"{step['step_no']}. ", "courier", 10),
                    (f"{step['phase']}. ", "helvetica-bold", 10),
                    (step["text"], "helvetica", 10),
                ]
            )
        control = chain["earliest_control"]
        if chain["control_rubric"]:
            rubric = cite_item(
                chain["control_rubric"], rendered_pack, item_packs,
                chain.get("control_pack"),
            )
            control = f"{control} ({rubric})"
        doc.paragraph(
            [
                ("Earliest breaking control: ", "helvetica", 10),
                (control + " ", "helvetica", 10),
                ("Status: ", "helvetica", 10),
                (chain["control_status"], "helvetica", 10),
                (".", "helvetica", 10),
            ]
        )

    # 5. Fixes.
    doc.heading("Fixes", level=1)
    fix_rows = []
    for fix in fixes:
        rubric = (
            ", ".join(
                cite_item(
                    i, rendered_pack, item_packs,
                    (fix.get("rubric_item_packs") or {}).get(i),
                )
                for i in fix["rubric_item_ids"]
            )
            if fix["rubric_item_ids"] else "—"
        )
        fix_rows.append(
            [
                (fix["fix_id"], "courier", INK),
                (fix["action"], "helvetica", INK),
                (rubric, "courier", INK),
                (fix["effort"], "helvetica", INK),
                (fix["chains_broken"], "helvetica", INK),
                (fix["status"], "helvetica", INK),
            ]
        )
    doc.table(
        ["ID", "Action", "Rubric", "Effort", "Breaks", "Status"],
        fix_rows,
        FIX_WIDTHS,
    )

    # 6. Verify next.
    doc.heading("Verify next", level=1)
    for item in verify_next:
        doc.paragraph(
            [
                (f"{item['seq']}. ", "courier", 10),
                ("Unknown: ", "helvetica-bold", 10),
                (item["unknown_text"] + " ", "helvetica", 10),
                ("Why it changes the picture: ", "helvetica-bold", 10),
                (item["why"] + " ", "helvetica", 10),
                ("Cheapest check: ", "helvetica-bold", 10),
                (item["cheapest_check"], "helvetica", 10),
            ]
        )

    # 7. Adjudication — only when at least one event exists, the same
    # condition as the Markdown renderer.
    if adjudicated:
        doc.heading("Adjudication", level=1)
        for run, events in adjudicated:
            doc.heading(
                f"Run {run['id']} — {run['model_label']} ({run['run_date']})",
                level=2,
            )
            doc.paragraph(
                [
                    ("Packet hash: ", "helvetica", 10),
                    (run["packet_hash"], "courier", 10),
                ]
            )
            current = {}
            for event in events:
                current[event["section"]] = event
            for section in ADJUDICATION_SECTIONS:
                label = ADJUDICATION_SECTION_LABELS[section]
                event = current.get(section)
                if event is None:
                    doc.paragraph(
                        [(f"{label}: no decision recorded", "helvetica", 10)]
                    )
                    continue
                runs = [
                    (f"{label}: ", "helvetica", 10),
                    (event["decision"] + " ", "helvetica", 10),
                    ("(", "helvetica", 10),
                    (event["date"], "courier", 10),
                    (", ", "helvetica", 10),
                    (event["actor"], "helvetica", 10),
                    (") ", "helvetica", 10),
                ]
                if event["note"]:
                    runs.append(("— note: ", "helvetica", 10))
                    runs.append((event["note"], "helvetica", 10))
                doc.paragraph(runs)

    # The substitution note: characters the PDF font cannot represent
    # are drawn as "?"; when any were, say so, with the count, as the
    # last content line. The count is computed from the report's text
    # as it was laid out, so the render stays deterministic.
    substituted = doc.substitutions
    if substituted > 0:
        doc.paragraph(
            [
                (
                    f"Note: {substituted} character(s) in this report could"
                    " not be represented in the PDF font and appear as"
                    ' "?".',
                    "helvetica",
                    10,
                )
            ]
        )

    return doc.build()
