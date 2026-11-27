"""Report renderer: Markdown engagement report from the store.

Every count in the output is computed from the store at render time; no
tally appears as a literal here.
"""

from .chains import exposure_sentence, report_exposures
from .store import ADJUDICATION_SECTIONS, COVERAGE_STATUSES, FIX_STATUSES, Store

ADJUDICATION_SECTION_LABELS = {
    "coverage": "Coverage",
    "chains": "Chains",
    "fixes": "Fixes",
    "verify-next": "Verify-next",
}


def _tally_line(tallies, not_scored=0, pack_item_count=None):
    """The coverage tally line.

    When the rendered pack has items with no score, the line ends
    with the disclosure " · not scored N (of M)"; with every item
    scored it is byte-identical to the pre-0.3.3 line.
    """
    parts = [f"{status} {tallies.get(status, 0)}" for status in COVERAGE_STATUSES]
    total = sum(tallies.values())
    line = " · ".join(parts) + f" — {total} rows"
    if not_scored > 0:
        line += f" · not scored {not_scored} (of {pack_item_count})"
    return line


def _citation_owner(item_id, item_packs, stored_pack=None):
    """The pack a citation belongs to: the pack stored with it when
    one was recorded, else the item_packs lookup (citations recorded
    before 0.3.4 carry no pack). None when neither knows the item."""
    if stored_pack is not None:
        return stored_pack
    return item_packs.get(item_id)


def cite_item(item_id, pack_id, item_packs, stored_pack=None):
    """A cited rubric item, suffixed with its pack when that is not
    the rendered pack: "MS.AAD.1.1v1 (scuba-m365-v2.0.0)".

    stored_pack is the pack the citation was validated against when
    it was written; when known it decides the owner, so an item id
    that several packs share is attributed to the pack it was cited
    from. With no stored pack the owner comes from item_packs.
    Citations of the rendered pack, and of items in no loaded pack,
    render bare."""
    owner = _citation_owner(item_id, item_packs, stored_pack)
    if owner is None or owner == pack_id:
        return item_id
    return f"{item_id} ({owner})"


def cross_pack_citations(data):
    """{item_id: [owner pack, ...]} for every fix or chain citation
    that the report annotates with another pack's id (empty when
    none). Each item maps to the sorted list of every distinct
    non-rendered pack that owns one of its citations, so two
    citations of one id under two different packs both reach the
    PDF /ID instead of collapsing to one entry.

    Each citation's owner is resolved exactly as cite_item resolves
    it — the stored pack when known, else item_packs — so the two
    renderers and the PDF /ID agree on what is annotated."""
    pack_id = data["pack_id"]
    item_packs = data["item_packs"]
    cited = []
    for fix in data["fixes"]:
        stored = fix.get("rubric_item_packs") or {}
        for item in fix["rubric_item_ids"] or []:
            cited.append((item, stored.get(item)))
    for chain in data["chains"]:
        if chain["control_rubric"]:
            cited.append((chain["control_rubric"], chain.get("control_pack")))
    owners = {}
    for item, stored_pack in cited:
        owner = _citation_owner(item, item_packs, stored_pack)
        if owner is not None and owner != pack_id:
            owners.setdefault(item, set()).add(owner)
    return {item: sorted(packs) for item, packs in owners.items()}


def gather_report_data(db_path, pack_id=None):
    """Gather everything a report renderer needs, in one place.

    Both renderers — the Markdown report and the PDF report — call
    this and render from the returned dict; no second copy of the
    store reads exists anywhere.

    Besides the rendered rows it carries pack_item_count (items in
    the rendered pack), not_scored (pack items minus scored rows),
    and item_packs ({item_id: pack_id} for every loaded pack's
    items), so the report can disclose unscored items and annotate
    citations of items from another pack. item_packs is the
    fallback owner lookup: a citation that stores the pack it was
    validated against (every one written from 0.3.4 on) is
    attributed to that pack instead.

    pack_id selects which loaded rubric pack the report renders.
    With no pack_id the default is Store.default_pack_id(): the
    engagement's recorded primary pack, else the alphabetically-first
    loaded pack (guaranteed by that query's ORDER BY) — never load
    order. A pack_id
    that is not loaded in this database raises
    ValueError("no such pack: <id>").
    """
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        if eng is None:
            raise ValueError("database holds no engagement")
        label_counts = store.inventory_label_counts()
        entries = store.list_inventory()
        if pack_id is None:
            pack_id = store.default_pack_id()
            if pack_id is None:
                raise ValueError(
                    "database holds no rubric pack; load one with load-pack"
                )
        pack = store.get_pack(pack_id)
        if pack is None:
            raise ValueError(f"no such pack: {pack_id}")
        coverage = store.list_coverage(pack_id)
        tallies = store.coverage_tallies(pack_id)
        pack_item_count = len(store.list_items(pack_id))
        # Every item in every loaded pack, mapped to its pack. The
        # rendered pack's items are entered first so an item id that
        # also appears in another pack is attributed to the rendered
        # one; other packs follow in pack_id order. This is the
        # fallback for citations with no stored pack (recorded
        # before 0.3.4); a stored pack takes precedence.
        item_packs = {}
        other_packs = [
            row["pack_id"] for row in store.conn.execute(
                "SELECT pack_id FROM rubric_pack ORDER BY pack_id"
            ).fetchall()
            if row["pack_id"] != pack_id
        ]
        for owner in [pack_id] + other_packs:
            for item in store.list_items(owner):
                item_packs.setdefault(item["item_id"], owner)
        chains = store.list_chains()
        fixes = store.list_fixes()
        fix_counts = store.fix_status_counts()
        verify_next = store.list_verify_next()
        adjudicated = []
        for run in store.list_runs():
            events = store.list_adjudications(run["id"])
            if events:
                adjudicated.append([run, events])
    finally:
        store.close()
    return {
        "engagement": eng,
        "label_counts": label_counts,
        "entries": entries,
        "pack_id": pack_id,
        "pack": pack,
        "coverage": coverage,
        "tallies": tallies,
        "pack_item_count": pack_item_count,
        "not_scored": pack_item_count - len(coverage),
        "item_packs": item_packs,
        "chains": chains,
        "fixes": fixes,
        "fix_counts": fix_counts,
        "verify_next": verify_next,
        "adjudicated": adjudicated,
    }


def render_report(db_path, pack_id=None):
    data = gather_report_data(db_path, pack_id)
    # Deeper Slice 4b: computed exposure for chains whose steps name
    # items. Empty (and nothing read) when no step names an item, so an
    # unannotated engagement renders exactly as before.
    exposures = report_exposures(db_path, data["chains"])
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
    pack_id = data["pack_id"]
    item_packs = data["item_packs"]
    tally = _tally_line(tallies, data["not_scored"], data["pack_item_count"])

    lines = []
    lines.append(f"# Engagement report — {eng['name']}")
    lines.append("")
    lines.append(f"- Subject: {eng['subject_label']}")
    lines.append(f"- Engagement created: {eng['created_date']}")
    lines.append(f"- Method order: {eng['method_order']}")
    lines.append(f"- Rubric pack: {pack['title']} ({pack['source_citation']})")
    lines.append("")

    lines.append("## Posture summary")
    lines.append("")
    inv_parts = ", ".join(
        f"{label} {label_counts.get(label, 0)}"
        for label in ("VERIFIED", "ON RECORD", "UNKNOWN")
    )
    lines.append(f"- Inventory: {len(entries)} entries ({inv_parts})")
    lines.append(f"- Coverage: {tally}")
    lines.append(f"- Attack chains: {len(chains)}")
    fix_parts = ", ".join(
        f"{status} {fix_counts.get(status, 0)}" for status in FIX_STATUSES
    )
    lines.append(f"- Fixes: {len(fixes)} ({fix_parts})")
    lines.append(f"- Verify-next items: {len(verify_next)}")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append(f"Tallies: {tally}")
    lines.append("")
    lines.append("| Item | Group | Status | Reasoning | Cited entries |")
    lines.append("|---|---|---|---|---|")
    for row in coverage:
        reasoning = row["reasoning"]
        if row["status"] == "Not applicable" and row["na_reason"]:
            reasoning = f"{reasoning} N/A reason: {row['na_reason']}"
        cited = ", ".join(row["cited_entry_ids"]) if row["cited_entry_ids"] else "—"
        lines.append(
            f"| {row['item_id']} | {row['group_name']} | {row['status']}"
            f" | {reasoning} | {cited} |"
        )
    lines.append("")

    lines.append("## Attack chains")
    lines.append("")
    for chain in chains:
        lines.append(f"### Chain {chain['chain_key']}: {chain['name']}")
        lines.append("")
        for step in chain["steps"]:
            lines.append(f"{step['step_no']}. **{step['phase']}.** {step['text']}")
        lines.append("")
        control = chain["earliest_control"]
        if chain["control_rubric"]:
            rubric = cite_item(
                chain["control_rubric"], pack_id, item_packs,
                chain.get("control_pack"),
            )
            control = f"{control} ({rubric})"
        lines.append(
            f"Earliest breaking control: {control} Status: {chain['control_status']}."
        )
        if chain["id"] in exposures:
            lines.append("Computed exposure: " + exposure_sentence(
                exposures[chain["id"]],
                lambda item, pack: cite_item(item, pack_id, item_packs, pack),
            ))
        lines.append("")

    lines.append("## Fixes")
    lines.append("")
    lines.append("| ID | Action | Rubric | Effort | Breaks | Status |")
    lines.append("|---|---|---|---|---|---|")
    for fix in fixes:
        rubric = (
            ", ".join(
                cite_item(
                    i, pack_id, item_packs,
                    (fix.get("rubric_item_packs") or {}).get(i),
                )
                for i in fix["rubric_item_ids"]
            )
            if fix["rubric_item_ids"] else "—"
        )
        lines.append(
            f"| {fix['fix_id']} | {fix['action']} | {rubric} | {fix['effort']}"
            f" | {fix['chains_broken']} | {fix['status']} |"
        )
    lines.append("")

    lines.append("## Verify next")
    lines.append("")
    for item in verify_next:
        lines.append(
            f"{item['seq']}. **Unknown:** {item['unknown_text']}"
            f" **Why it changes the picture:** {item['why']}"
            f" **Cheapest check:** {item['cheapest_check']}"
        )
    lines.append("")

    # The Adjudication section appears only when the record holds at
    # least one adjudication event; a database with none renders exactly
    # as it did before slice 5, byte for byte.
    if adjudicated:
        lines.append("## Adjudication")
        lines.append("")
        for run, events in adjudicated:
            lines.append(
                f"### Run {run['id']} — {run['model_label']}"
                f" ({run['run_date']})"
            )
            lines.append("")
            lines.append(f"- Packet hash: {run['packet_hash']}")
            current = {}
            for event in events:
                current[event["section"]] = event
            for section in ADJUDICATION_SECTIONS:
                label = ADJUDICATION_SECTION_LABELS[section]
                event = current.get(section)
                if event is None:
                    lines.append(f"- {label}: no decision recorded")
                    continue
                line = (
                    f"- {label}: {event['decision']}"
                    f" ({event['date']}, {event['actor']})"
                )
                if event["note"]:
                    line += f" — note: {event['note']}"
                lines.append(line)
            lines.append("")

    return "\n".join(lines)
