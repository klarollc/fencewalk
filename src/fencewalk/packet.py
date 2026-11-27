"""Model-pass packet assembly: one self-contained Markdown packet.

The packet is the run brief (the bundled templates/run-brief.md,
placeholders substituted), the full labeled inventory, and the full
rubric, in that order, preceded by a run-configuration block. The
operator runs the packet in their own model session, or Fencewalk
calls a model API on the operator's behalf (`run-model`, with the
operator's own key); either way the output enters the record only
through `ingest`.

Assembly is deterministic: the same database state and the same options
produce a byte-identical packet, so the SHA-256 the packet command
prints and records identifies the exact bytes the operator ran.

Posture (Deeper Slice 1): the default "standard" packet is the one
above, and its bytes never change. An "adversarial" packet is a second
pass that attacks the standing scores: its brief is the bundled
templates/adversarial-brief.md (same placeholders, same substitution),
and a standing-coverage section — every rubric item with its standing
score, reasoning, N/A reason and cited entries with their labels, or
"unscored" — sits between the brief and the inventory.
"""

from .checklist import _order_key
from .fixture import bundled_data_path
from .store import PACKET_POSTURES, Store

# Resolved through importlib.resources, not from __file__: a
# repo-root-relative path does not exist under site-packages, so an
# installed run could never find the template.
TEMPLATE_PATH = bundled_data_path("templates", "run-brief.md")
ADVERSARIAL_TEMPLATE_PATH = bundled_data_path(
    "templates", "adversarial-brief.md"
)

SECTION_TITLES = {
    "A": "Identity and tenant",
    "B": "Domain and DNS",
    "C": "Public web",
    "D": "Voice and communications",
    "E": "Fleet and remote access",
    "F": "Data and backups",
    "G": "AI and API keys",
    "H": "Standing unknowns",
}
SECTION_ORDER = list("ABCDEFGH")

PLACEHOLDERS = (
    "{engagement_name}",
    "{subject_label}",
    "{pack_title}",
    "{pack_citation}",
    "{word_cap}",
)


def render_brief(values, template_path=TEMPLATE_PATH):
    """A brief template (the run brief by default) with every
    placeholder substituted.

    Substitution must be total: a packet carrying an unsubstituted
    placeholder is a defect, so any survivor raises ValueError.
    """
    text = template_path.read_text(encoding="utf-8").strip()
    for token in PLACEHOLDERS:
        text = text.replace(token, str(values[token]))
    for token in PLACEHOLDERS:
        if token in text:
            raise ValueError(f"unsubstituted placeholder in run brief: {token}")
    return text


def _standing_coverage_lines(pack, items, scores, entries):
    """The adversarial packet's standing-coverage section: every rubric
    item in rubric order, grouped as the rubric is, with its standing
    score or "unscored". Deterministic: items keep the store's rubric
    order and citations its entry_id order."""
    labels = {entry["entry_id"]: entry["label"] for entry in entries}
    by_item = {score["item_id"]: score for score in scores}
    scored = sum(1 for item in items if item["item_id"] in by_item)
    lines = ["# Standing coverage", ""]
    lines.append(
        f"Standing scores for {pack['title']}: {scored} of {len(items)}"
        f" items scored, {len(items) - scored} unscored. Unscored items"
        " are out of scope for proposals."
    )
    groups = []
    for item in items:
        if item["group_name"] not in groups:
            groups.append(item["group_name"])
    for group in groups:
        lines.append("")
        lines.append(f"## {group}")
        lines.append("")
        for item in items:
            if item["group_name"] != group:
                continue
            score = by_item.get(item["item_id"])
            if score is None:
                lines.append(f"- **{item['item_id']}** — unscored")
                continue
            lines.append(f"- **{item['item_id']}** — {score['status']}")
            lines.append(f"  Reasoning: {score['reasoning']}")
            if score["na_reason"]:
                lines.append(f"  N/A reason: {score['na_reason']}")
            cited = score["cited_entry_ids"]
            if cited:
                lines.append(
                    "  Cited: " + ", ".join(
                        f"**{entry_id}** ({labels.get(entry_id, 'no such entry')})"
                        for entry_id in cited
                    )
                )
            else:
                lines.append("  Cited: none")
    return lines


def assemble_packet(db_path, pack_id=None, word_cap=2500, assembled_date=None,
                     run_via="manual", model_label=None, posture="standard"):
    """Assemble the packet text for an engagement database.

    Returns (packet_text, pack) where pack is the rubric pack dict used.
    Raises ValueError on a database with no engagement, no rubric pack
    (the slice-2 pack-less error), or an unknown --pack id.

    run_via is "manual" (default) or "api". The manual packet is the
    golden packet: its bytes never change. The API packet differs in
    exactly two places: the run-configuration block gains a
    "- Run via: <model_label>" line, and the session sentence states
    the provider API was called on the operator's behalf. model_label
    (e.g. "anthropic/<model-id>") is required when run_via is "api".

    posture is "standard" (default; the golden packet above) or
    "adversarial" (see the module docstring). The adversarial posture
    is manual-only: run-model does not offer it.
    """
    if run_via not in ("manual", "api"):
        raise ValueError(f"unknown run_via: {run_via}")
    if run_via == "api" and not model_label:
        raise ValueError("model_label is required when run_via is 'api'")
    if posture not in PACKET_POSTURES:
        raise ValueError(f"unknown posture: {posture}")
    adversarial = posture == "adversarial"
    if adversarial and run_via != "manual":
        raise ValueError("the adversarial posture is manual-only")
    store = Store(db_path)
    try:
        eng = store.get_engagement()
        if eng is None:
            raise ValueError("database holds no engagement")
        if pack_id is None:
            # The one tool-wide default: the primary pack, else the
            # alphabetically-first loaded pack (Store.default_pack_id),
            # as report/pdf use.
            pack_id = store.default_pack_id()
            if pack_id is None:
                raise ValueError(
                    "database holds no rubric pack; load one with load-pack"
                )
        pack = store.get_pack(pack_id)
        if pack is None:
            raise ValueError(f"no such pack: {pack_id}")
        items = store.list_pack_items(pack_id)
        entries = store.list_inventory()
        scores = store.list_coverage(pack_id) if adversarial else None
    finally:
        store.close()

    brief = render_brief({
        "{engagement_name}": eng["name"],
        "{subject_label}": eng["subject_label"],
        "{pack_title}": pack["title"],
        "{pack_citation}": pack["source_citation"],
        "{word_cap}": word_cap,
    }, ADVERSARIAL_TEMPLATE_PATH if adversarial else TEMPLATE_PATH)

    lines = []
    lines.append(f"# Model run packet — {eng['name']}")
    lines.append("")
    lines.append("**Run configuration (record for adjudication)**")
    lines.append(f"- Subject: {eng['subject_label']}")
    lines.append(f"- Engagement created: {eng['created_date']}")
    lines.append(f"- Method order: {eng['method_order']}")
    lines.append(
        f"- Rubric pack: {pack['title']} ({pack['source_citation']}),"
        f" version {pack['version']}"
    )
    lines.append(f"- Word cap: ~{word_cap} words")
    if adversarial:
        lines.append("- Posture: adversarial (second pass against the standing scores)")
    if run_via == "api":
        lines.append(f"- Run via: {model_label}")
    lines.append(f"- Assembled: {assembled_date}")
    lines.append("")
    if run_via == "api":
        session_sentence = (
            "Fencewalk called the provider API on the operator's behalf"
            " with the operator's key; the output is recorded as a model"
            " run when the operator ingests it."
        )
    else:
        session_sentence = (
            "The operator runs this packet in their own model session;"
            " Fencewalk does not call a model API."
        )
    if adversarial:
        contents_sentence = (
            "Assembled by Fencewalk from the engagement database: the"
            " adversarial brief, the standing coverage, the inventory, and"
            " the rubric, inlined in that order. "
        )
    else:
        contents_sentence = (
            "Assembled by Fencewalk from the engagement database: the run"
            " brief, the inventory, and the rubric, inlined in that order. "
        )
    lines.append(contents_sentence + session_sentence)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.extend(brief.splitlines())
    lines.append("")
    lines.append("---")
    lines.append("")
    if adversarial:
        lines.extend(_standing_coverage_lines(pack, items, scores, entries))
        lines.append("")
        lines.append("---")
        lines.append("")
    lines.append("# Inventory")
    by_section = {section: [] for section in SECTION_ORDER}
    for entry in entries:
        by_section.setdefault(entry["section"], []).append(entry)
    for section in SECTION_ORDER:
        lines.append("")
        lines.append(f"## {section} — {SECTION_TITLES[section]}")
        lines.append("")
        section_entries = sorted(by_section.get(section, []), key=_order_key)
        if not section_entries:
            lines.append("No entries recorded.")
            continue
        for entry in section_entries:
            lines.append(
                f"- **{entry['entry_id']}** ({entry['label']})"
                f" — {entry['body']}"
            )
            source_line = f"  Source: {entry['source']}"
            if entry["checked_date"]:
                source_line += f" · Checked: {entry['checked_date']}"
            lines.append(source_line)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("# Rubric")
    groups = []
    for item in items:
        if item["group_name"] not in groups:
            groups.append(item["group_name"])
    for group in groups:
        lines.append("")
        lines.append(f"## {group}")
        lines.append("")
        for item in items:
            if item["group_name"] == group:
                lines.append(f"- **{item['item_id']}** — {item['text']}")
    lines.append("")
    return "\n".join(lines), pack
