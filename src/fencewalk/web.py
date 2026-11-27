"""Web interface: one engagement, served as HTML.

The interface is a second front-end to the same store the CLI uses. It
opens the store per request. UI-0 shipped the read surface (GET and
HEAD; every other method refused with 405). UI-1 adds the verification
loop's writes as plain HTML forms — set-label, edit-entry, add-entry,
score/rescore — each mapping one-to-one onto a CLI command and a store
method, with the same invariants, the same refusals, and the same
history recording. UI-2 adds the model pass and adjudication writes
the same way — packet assembly (returned as a download), output
ingest, adjudication decisions, and the apply forms (chain, fix,
verify-next) plus fix transitions. Those eleven POST routes are the
only mutations the process can make; every other path still refuses
POST with 405, and a full GET crawl still leaves the database
byte-identical.

Three bounded controls, none of them authentication. Every request,
on every method, must carry a Host header naming this server — the
bind host or a loopback name, on the bound port — or it is refused
with 403 before anything is read or written (this is what defeats DNS
rebinding). A POST whose Origin (or Referer) host does not match that
validated Host is refused with 403. And every write form carries a
per-process token (generated at server creation, held in memory only,
never printed or logged) that a POST must present, or it is refused
with 403 before any write runs.

Every figure on every page is computed from the store at request time;
nothing is cached across requests, so a page can never serve stale
numbers after the database changes on disk.

Standard library only, no JavaScript, no external assets: the single
stylesheet is the CSS constant below, embedded in each page. The visual
direction is Fencewalk's own (interface plan §4): a quiet, dense
working console — paper-white ground, hairline rules, monospace for
IDs, hashes, dates, and figures, and one amber signal color reserved
for state that needs the operator (UNKNOWN entries, decayed evidence).
"""

import datetime
import hashlib
import hmac
import html
import re
import secrets
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlencode, urlparse, urlsplit

from .checklist import INSTRUCTIONS, _order_key, select_checks
from .draft import STUB, split_sections
from .packet import assemble_packet
from .report import ADJUDICATION_SECTION_LABELS, cite_item, render_report
from .store import (
    ADJUDICATION_DECISIONS,
    ADJUDICATION_SECTIONS,
    COVERAGE_STATUSES,
    EVIDENCE_LABELS,
    FIX_STATUSES,
    UNSET,
    InvariantError,
    Store,
)

LOCAL_HOSTS = ("127.0.0.1", "localhost")

# Host-header names always accepted for this server, on the bound
# port, in addition to the bind host itself.
LOOPBACK_NAMES = ("127.0.0.1", "localhost", "::1")
WILDCARD_BIND_HOSTS = ("0.0.0.0", "::")

# The hidden form field that carries the per-process write token.
TOKEN_FIELD = "token"
MAX_POST_BYTES = 1_048_576

NO_PACK_NOTE = (
    "No rubric pack loaded. Coverage appears once a pack is loaded"
    " with load-pack."
)

NAV = (
    ("/", "Overview"),
    ("/inventory", "Inventory"),
    ("/checklist", "Checklist"),
    ("/coverage", "Coverage"),
    ("/model-pass", "Model pass"),
    ("/adjudication", "Adjudication"),
    ("/fixes", "Fixes"),
    ("/report", "Report"),
)

# Draft section display name -> adjudication section key (draft.py's
# DELIVERABLES names meet the store's ADJUDICATION_SECTIONS here).
DRAFT_SECTION_KEYS = {
    "Coverage map": "coverage",
    "Attack chains": "chains",
    "Fix list": "fixes",
    "Verify-next list": "verify-next",
}

CONTROL_STATUSES = ("present", "absent", "unknown")

CSS = """
:root {
  --paper: #fdfcf8;
  --ink: #1d1d1a;
  --muted: #6f6a5e;
  --hair: #ddd8cb;
  --amber: #b45309;
  --amber-dark: #7c4a03;
  --amber-tint: #fbf0d7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.45;
}
.layout { display: flex; min-height: 100vh; }
.rail {
  flex: 0 0 188px;
  border-right: 1px solid var(--hair);
  padding: 18px 14px;
}
.brand { font-size: 17px; letter-spacing: 0.02em; }
.railsub { color: var(--muted); font-size: 12px; margin: 2px 0 16px; }
.rail a {
  display: block;
  padding: 5px 8px;
  color: var(--ink);
  text-decoration: none;
  border-top: 1px solid var(--hair);
}
.rail a.active { font-weight: 650; }
.rail a:hover { text-decoration: underline; }
main { flex: 1 1 auto; padding: 20px 26px 40px; min-width: 0; }
h1 { font-size: 20px; font-weight: 650; margin: 0 0 4px; }
h2 { font-size: 15px; font-weight: 650; margin: 22px 0 6px; }
h3 { font-size: 13.5px; font-weight: 650; margin: 14px 0 4px; }
a { color: var(--ink); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.signal { color: var(--amber-dark); font-weight: 650; }
.note { color: var(--muted); }
table { border-collapse: collapse; }
th, td {
  text-align: left;
  vertical-align: top;
  padding: 4px 10px 4px 0;
  border-bottom: 1px solid var(--hair);
}
table.facts th, table.posture th { color: var(--muted); font-weight: 550; white-space: nowrap; }
table.coverage { width: 100%; }
table.coverage th { color: var(--muted); font-weight: 550; }
.chip {
  display: inline-block;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 2px;
  white-space: nowrap;
}
.chip-verified { background: var(--ink); color: var(--paper); border: 1px solid var(--ink); }
.chip-onrecord { background: transparent; color: var(--ink); border: 1px solid var(--muted); }
.chip-unknown { background: var(--amber-tint); color: var(--amber-dark); border: 1px dashed var(--amber); }
.entry { border-top: 1px solid var(--hair); padding: 8px 0 4px; }
.entry-head .eid { font-weight: 650; margin-right: 8px; }
.entry-body { margin: 4px 0 2px; }
.entry-meta { margin: 0 0 4px; color: var(--muted); font-size: 12.5px; }
.filters { border-top: 1px solid var(--hair); border-bottom: 1px solid var(--hair); padding: 6px 0; margin: 10px 0 4px; }
.filters .fgroup { margin-right: 18px; }
.filters a { text-decoration: none; }
.filters a:hover { text-decoration: underline; }
.filters a.on { font-weight: 650; text-decoration: underline; }
.active-filters { margin: 6px 0; }
ul.checks { list-style: none; margin: 6px 0; padding: 0; }
li.check { border-top: 1px solid var(--hair); padding: 7px 0; }
li.check .box {
  display: inline-block;
  width: 11px; height: 11px;
  border: 1.5px solid var(--ink);
  margin-right: 9px;
}
li.check-unknown .box { border-style: dashed; border-color: var(--amber); }
li.check .eid { font-weight: 650; }
li.check .src { color: var(--muted); font-size: 12.5px; margin-left: 24px; }
.instructions { color: var(--muted); max-width: 75ch; }
pre.report {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  white-space: pre-wrap;
  border-top: 1px solid var(--hair);
  padding-top: 12px;
}
pre.draft {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  white-space: pre-wrap;
  border-top: 1px solid var(--hair);
  padding-top: 12px;
  margin: 6px 0;
}
.notscored { color: var(--muted); font-style: italic; }
.status-unknown { color: var(--amber-dark); font-weight: 650; }
.na-reason { color: var(--muted); font-size: 12.5px; }
form.write { margin: 6px 0 8px; font-size: 13px; }
form.write label { color: var(--muted); margin-right: 10px; white-space: nowrap; }
form.write .cites label { color: var(--ink); }
input, select, textarea, button {
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: #fff;
  border: 1px solid var(--hair);
  border-radius: 2px;
  padding: 2px 5px;
}
textarea { vertical-align: top; }
button { background: var(--paper); cursor: pointer; }
button:hover { border-color: var(--muted); }
.form-error { border: 1px solid var(--ink); padding: 8px 10px; max-width: 75ch; }
"""


def _esc(text):
    return html.escape(str(text), quote=True)


def _today():
    return datetime.date.today().isoformat()


def startup_warning(host):
    """The no-authentication warning for a non-local bind, or None.

    UI-0 is read-only, but the warning exists from the first version so
    the habit is in place before any write surface arrives: served on
    anything but localhost, this interface lets anyone who can reach
    the port read the engagement.
    """
    if host in LOCAL_HOSTS:
        return None
    return (
        f"warning: serving on {host} — this interface has no"
        " authentication; anyone who can reach this port can read"
        " the engagement."
    )


def _checklist_split(store):
    return select_checks(store.list_inventory(), _today())


def _adjudication_undecided(store):
    """Undecided sections for the latest run, or None when no runs
    exist. The rail shows this count on the Adjudication item, in
    the same treatment as the Checklist count."""
    runs = store.list_runs()
    if not runs:
        return None
    decided = {
        e["section"] for e in store.list_adjudications(runs[-1]["id"])
    }
    return len(
        [s for s in ADJUDICATION_SECTIONS if s not in decided]
    )


def _pack_ids(store):
    """Loaded pack IDs, in load order (via Store.list_packs)."""
    return [pack["pack_id"] for pack in store.list_packs()]


def _tally_html(tallies):
    parts = []
    for status in COVERAGE_STATUSES:
        text = f"{status} {tallies.get(status, 0)}"
        if status == "Unknown" and tallies.get(status, 0):
            text = f'<span class="signal">{text}</span>'
        parts.append(text)
    total = sum(tallies.values())
    return " · ".join(parts) + f" — {total} rows"


def _chip(label):
    cls = {
        "VERIFIED": "chip-verified",
        "ON RECORD": "chip-onrecord",
        "UNKNOWN": "chip-unknown",
    }[label]
    return f'<span class="chip {cls}">{_esc(label)}</span>'


SECTIONS = tuple("ABCDEFGH")


def _label_options(current):
    options = []
    for label in EVIDENCE_LABELS:
        selected = " selected" if label == current else ""
        options.append(
            f'<option value="{_esc(label)}"{selected}>{_esc(label)}</option>'
        )
    return "".join(options)


def _filter_fields(label_filter, section_filter):
    """Hidden inputs carrying the active inventory filters, so a
    write submitted from a filtered view redirects back to it."""
    fields = []
    if label_filter is not None:
        fields.append(
            f'<input type="hidden" name="label_filter" value="{_esc(label_filter)}">'
        )
    if section_filter is not None:
        fields.append(
            f'<input type="hidden" name="section_filter" value="{_esc(section_filter)}">'
        )
    return "".join(fields)


def _label_form(entry, origin, label_filter=None, section_filter=None):
    """The set-label form for one entry (checklist and inventory).

    The select starts on the entry's current label, so changing it is
    a deliberate act. Date and actor are ordinary prefilled inputs —
    today and "operator", the CLI's defaults — visibly editable: the
    record shows what was actually submitted, never a hidden value.
    """
    return (
        f'<form class="write" method="post"'
        f' action="/entry/{_esc(entry["entry_id"])}/label">'
        f'<input type="hidden" name="from" value="{origin}">'
        + _filter_fields(label_filter, section_filter)
        + f'<label>Label <select name="label">'
        + _label_options(entry["label"])
        + "</select></label>"
        + f'<label>date <input name="date" value="{_esc(_today())}" size="10"></label>'
        + '<label>actor <input name="actor" value="operator" size="9"></label>'
        + '<button type="submit">Set label</button></form>'
    )


def _edit_form(entry, label_filter=None, section_filter=None):
    """The edit-entry form for one entry. It has no label field:
    details and labels change through different doors, as in the CLI.

    The date inputs show the current values, which maps the store's
    UNSET / None / string tri-state onto the form: a date left as
    shown re-sets the same value, an emptied date clears it, and only
    a field missing from the submission leaves the date unchanged.
    """
    return (
        f'<form class="write" method="post"'
        f' action="/entry/{_esc(entry["entry_id"])}/edit">'
        + _filter_fields(label_filter, section_filter)
        + f'<label>Body <textarea name="body" rows="2" cols="52">'
        + _esc(entry["body"])
        + "</textarea></label>"
        + f'<label>Source <input name="source" value="{_esc(entry["source"])}" size="26"></label>'
        + f'<label>checked <input name="checked_date"'
        + f' value="{_esc(entry["checked_date"] or "")}" size="10"></label>'
        + f'<label>decay <input name="decay_date"'
        + f' value="{_esc(entry["decay_date"] or "")}" size="10"></label>'
        + '<button type="submit">Save edits</button></form>'
    )


def _add_entry_form():
    section_options = "".join(
        f'<option value="{s}">{s}</option>' for s in SECTIONS
    )
    return (
        "<h2>Add an entry</h2>"
        '<form class="write" method="post" action="/entry/new">'
        f'<label>Section <select name="section">{section_options}</select></label>'
        '<label>Body <textarea name="body" rows="2" cols="52"></textarea></label>'
        '<label>Source <input name="source" size="26"></label>'
        f'<label>Label <select name="label">{_label_options("UNKNOWN")}</select></label>'
        '<label>checked <input name="checked_date" size="10"></label>'
        '<label>decay <input name="decay_date" size="10"></label>'
        f'<label>date <input name="date" value="{_esc(_today())}" size="10"></label>'
        '<label>actor <input name="actor" value="operator" size="9"></label>'
        '<button type="submit">Add entry</button></form>'
    )


def _score_form(store, pack_id, item, score):
    """The score form for an unscored item, the rescore form for a
    scored one — the page mirrors the CLI's score/rescore split, and
    the single POST route dispatches on the item's current state,
    exactly as the two commands divide the work between them. The
    rescore form is prefilled with the current score, citations
    checked, so replacing a score starts from what stands.
    """
    entries = sorted(store.list_inventory(), key=_order_key)
    status_options = []
    for status in COVERAGE_STATUSES:
        selected = " selected" if score and status == score["status"] else ""
        status_options.append(
            f'<option value="{_esc(status)}"{selected}>{_esc(status)}</option>'
        )
    cited_now = set(score["cited_entry_ids"]) if score else set()
    cites = []
    for e in entries:
        checked = " checked" if e["entry_id"] in cited_now else ""
        cites.append(
            f'<label><input type="checkbox" name="cite"'
            f' value="{_esc(e["entry_id"])}"{checked}>'
            f' <span class="mono">{_esc(e["entry_id"])}</span></label>'
        )
    reasoning = _esc(score["reasoning"]) if score else ""
    na_reason = _esc(score["na_reason"] or "") if score else ""
    verb = "Rescore" if score else "Score"
    return (
        f'<form class="write" method="post"'
        f' action="/coverage/{_esc(pack_id)}/{_esc(item["item_id"])}/score">'
        f'<label>Status <select name="status">{"".join(status_options)}</select></label>'
        f'<label>Reasoning <input name="reasoning" value="{reasoning}" size="40"></label>'
        f'<label>N/A reason (required for Not applicable)'
        f' <input name="na_reason" value="{na_reason}" size="28"></label>'
        f'<span class="cites">Cite: {"".join(cites)}</span>'
        f'<button type="submit">{verb}</button></form>'
    )


def _page(title, current, checklist_total, body, adj_undecided=None):
    links = []
    for href, label in NAV:
        cls = ' class="active"' if href == current else ""
        extra = ""
        if href == "/checklist":
            count_cls = "mono signal" if checklist_total else "mono"
            extra = f' <span class="{count_cls}">({checklist_total})</span>'
        if href == "/adjudication" and adj_undecided is not None:
            count_cls = "mono signal" if adj_undecided else "mono"
            extra = f' <span class="{count_cls}">({adj_undecided})</span>'
        links.append(f'<a href="{href}"{cls}>{label}{extra}</a>')
    nav = "\n".join(links)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{_esc(title)} — Fencewalk</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        '<div class="layout">\n<nav class="rail">\n'
        '<div class="brand">Fencewalk</div>\n'
        '<div class="railsub">web interface</div>\n'
        f"{nav}\n</nav>\n<main>\n{body}\n</main>\n</div>\n</body>\n</html>\n"
    )


# -- page bodies (each takes an open store; /report is handled apart) ------


def _overview_body(store):
    eng = store.get_engagement()
    if eng is None:
        return "<h1>Overview</h1>\n<p class=\"note\">This database holds no engagement.</p>"
    entries = store.list_inventory()
    label_counts = store.inventory_label_counts()
    unknown, decayed = _checklist_split(store)
    pack_ids = _pack_ids(store)
    chains = store.list_chains()
    fixes = store.list_fixes()
    fix_counts = store.fix_status_counts()
    verify_next = store.list_verify_next()

    parts = [f"<h1>{_esc(eng['name'])}</h1>"]
    parts.append(
        '<table class="facts">'
        f"<tr><th>Subject</th><td>{_esc(eng['subject_label'])}</td></tr>"
        f'<tr><th>Created</th><td class="mono">{_esc(eng["created_date"])}</td></tr>'
        f"<tr><th>Method order</th><td>{_esc(eng['method_order'])}</td></tr>"
        "</table>"
    )

    label_bits = []
    for label in EVIDENCE_LABELS:
        n = label_counts.get(label, 0)
        num = f'<span class="signal">{n}</span>' if label == "UNKNOWN" and n else str(n)
        href = "/inventory?" + urlencode({"label": label})
        label_bits.append(f'<a href="{href}">{label} <span class="mono">{num}</span></a>')
    check_total = len(unknown) + len(decayed)
    rows = [
        "<tr><th>Inventory</th>"
        f'<td class="mono"><a href="/inventory">{len(entries)} entries</a></td>'
        f"<td>{' · '.join(label_bits)}</td></tr>",
        "<tr><th>Checklist</th>"
        f'<td class="mono"><a href="/checklist">{check_total} to work</a></td>'
        f'<td><span class="signal">{len(unknown)} unknown</span>'
        f' · <span class="signal">{len(decayed)} decayed</span></td></tr>',
    ]
    if pack_ids:
        for pack_id in pack_ids:
            pack = store.get_pack(pack_id)
            items = store.list_pack_items(pack_id)
            tallies = store.coverage_tallies(pack_id)
            not_scored = len(items) - sum(tallies.values())
            rows.append(
                "<tr><th>Coverage</th>"
                f'<td><a href="/coverage">{_esc(pack["title"])}</a></td>'
                f'<td class="mono">{_tally_html(tallies)} · not scored {not_scored}</td></tr>'
            )
    else:
        rows.append(
            "<tr><th>Coverage</th>"
            f'<td class="note" colspan="2">{_esc(NO_PACK_NOTE)}</td></tr>'
        )
    fix_bits = " · ".join(
        f"{status} {fix_counts.get(status, 0)}" for status in FIX_STATUSES
    )
    rows.append(
        "<tr><th>Attack chains</th>"
        f'<td class="mono"><a href="/report">{len(chains)}</a></td><td></td></tr>'
    )
    rows.append(
        "<tr><th>Fixes</th>"
        f'<td class="mono"><a href="/fixes">{len(fixes)}</a></td>'
        f'<td class="mono">{fix_bits}</td></tr>'
    )
    rows.append(
        "<tr><th>Verify next</th>"
        f'<td class="mono"><a href="/report">{len(verify_next)}</a></td><td></td></tr>'
    )
    parts.append('<h2>Posture</h2>\n<table class="posture">\n' + "\n".join(rows) + "\n</table>")

    packets = store.list_packets()
    runs = store.list_runs()
    if packets or runs:
        prov = []
        if packets:
            latest = packets[-1]
            prov.append(
                "<tr><th>Latest packet</th>"
                f'<td><a href="/model-pass"><span class="mono">'
                f'{_esc(latest["assembled_date"])}</span></a>'
                f' · sha256 <span class="mono">{_esc(latest["sha256"])}</span></td></tr>'
            )
        if runs:
            latest = runs[-1]
            prov.append(
                "<tr><th>Latest run</th>"
                f'<td><a href="/model-pass">{_esc(latest["model_label"])}</a>'
                f' · <span class="mono">{_esc(latest["run_date"])}</span></td></tr>'
            )
        parts.append('<h2>Model pass</h2>\n<table class="facts">\n' + "\n".join(prov) + "\n</table>")
        standings = []
        for run in runs:
            events = store.list_adjudications(run["id"])
            if not events:
                continue
            current = {}
            for event in events:
                current[event["section"]] = event
            items = []
            for section in ADJUDICATION_SECTIONS:
                label = ADJUDICATION_SECTION_LABELS[section]
                event = current.get(section)
                if event is None:
                    items.append(f"<li>{label}: no decision recorded</li>")
                else:
                    items.append(f"<li>{label}: {_esc(event['decision'])}</li>")
            standings.append(
                f"<h3><a href=\"/adjudication?run={run['id']}\">Run {run['id']}</a>"
                f" — {_esc(run['model_label'])}"
                f' (<span class="mono">{_esc(run["run_date"])}</span>)</h3>'
                "\n<ul>\n" + "\n".join(items) + "\n</ul>"
            )
        if standings:
            parts.append("<h2>Adjudication standings</h2>\n" + "\n".join(standings))
    return "\n".join(parts)


def _inv_href(label=None, section=None):
    params = {}
    if label is not None:
        params["label"] = label
    if section is not None:
        params["section"] = section
    if not params:
        return "/inventory"
    return "/inventory?" + urlencode(params)


def _inventory_body(store, query):
    entries = sorted(store.list_inventory(), key=_order_key)
    label_filter = query.get("label", [None])[0]
    if label_filter not in EVIDENCE_LABELS:
        label_filter = None
    section_filter = query.get("section", [None])[0] or None
    sections_present = sorted({e["section"] for e in entries})
    filtered = [
        e for e in entries
        if (label_filter is None or e["label"] == label_filter)
        and (section_filter is None or e["section"] == section_filter)
    ]

    parts = ["<h1>Inventory</h1>"]
    if label_filter is None and section_filter is None:
        parts.append(f'<p class="counts mono">{len(entries)} entries</p>')
    else:
        parts.append(
            f'<p class="counts mono">{len(filtered)} of {len(entries)} entries</p>'
        )
    label_links = []
    all_cls = ' class="on"' if label_filter is None else ""
    label_links.append(f'<a href="{_inv_href(section=section_filter)}"{all_cls}>All</a>')
    for label in EVIDENCE_LABELS:
        cls = ' class="on"' if label_filter == label else ""
        label_links.append(
            f'<a href="{_inv_href(label=label, section=section_filter)}"{cls}>{label}</a>'
        )
    section_links = []
    all_cls = ' class="on"' if section_filter is None else ""
    section_links.append(f'<a href="{_inv_href(label=label_filter)}"{all_cls}>All</a>')
    for section in sections_present:
        cls = ' class="on"' if section_filter == section else ""
        section_links.append(
            f'<a href="{_inv_href(label=label_filter, section=section)}"{cls}>{_esc(section)}</a>'
        )
    parts.append(
        '<div class="filters">'
        f'<span class="fgroup">Label: {" · ".join(label_links)}</span>'
        f'<span class="fgroup">Section: {" · ".join(section_links)}</span>'
        "</div>"
    )
    if label_filter is not None or section_filter is not None:
        active = []
        if label_filter is not None:
            active.append(f"label {_esc(label_filter)}")
        if section_filter is not None:
            active.append(f"section {_esc(section_filter)}")
        parts.append(
            '<p class="active-filters">Filters: '
            + " · ".join(active)
            + ' — <a href="/inventory">clear filters</a></p>'
        )
    if not filtered:
        parts.append('<p class="note">No entries match.</p>')
        parts.append(_add_entry_form())
        return "\n".join(parts)
    current_section = None
    for e in filtered:
        if e["section"] != current_section:
            current_section = e["section"]
            parts.append(f"<h2>Section {_esc(current_section)}</h2>")
        meta = f"Source: {_esc(e['source'])}"
        if e["checked_date"]:
            meta += f' · checked <span class="mono">{_esc(e["checked_date"])}</span>'
        if e["decay_date"]:
            meta += f' · decay <span class="mono">{_esc(e["decay_date"])}</span>'
        parts.append(
            f'<article class="entry" id="entry-{_esc(e["entry_id"])}">'
            f'<div class="entry-head"><span class="mono eid">{_esc(e["entry_id"])}</span>'
            f"{_chip(e['label'])}</div>"
            f'<p class="entry-body">{_esc(e["body"])}</p>'
            f'<p class="entry-meta">{meta}</p>'
            + _label_form(e, "inventory", label_filter, section_filter)
            + _edit_form(e, label_filter, section_filter)
            + "</article>"
        )
    parts.append(_add_entry_form())
    return "\n".join(parts)


def _checklist_body(store):
    unknown, decayed = _checklist_split(store)
    total = len(unknown) + len(decayed)
    parts = ["<h1>Verification checklist</h1>"]
    parts.append(
        f'<p class="counts"><span class="mono signal">{len(unknown)}</span> unknown'
        f' · <span class="mono signal">{len(decayed)}</span> decayed evidence'
        f' · <span class="mono">{total}</span> total'
        f' — as of <span class="mono">{_today()}</span></p>'
    )
    parts.append(f'<p class="instructions">{_esc(INSTRUCTIONS)}</p>')
    parts.append("<h2>Unknown entries</h2>")
    if unknown:
        items = []
        for e in unknown:
            items.append(
                '<li class="check check-unknown"><span class="box"></span>'
                f'<span class="mono eid">{_esc(e["entry_id"])}</span>'
                f' (section {_esc(e["section"])}) — {_esc(e["body"])}'
                f'<div class="src">Source: {_esc(e["source"])}</div>'
                + _label_form(e, "checklist")
                + "</li>"
            )
        parts.append('<ul class="checks">\n' + "\n".join(items) + "\n</ul>")
    else:
        parts.append('<p class="note">None.</p>')
    parts.append("<h2>Decayed evidence</h2>")
    if decayed:
        items = []
        for e in decayed:
            checked = e["checked_date"] if e["checked_date"] else "not recorded"
            items.append(
                '<li class="check"><span class="box"></span>'
                f'<span class="mono eid">{_esc(e["entry_id"])}</span>'
                f' (section {_esc(e["section"])}) — {_chip(e["label"])}'
                f', checked <span class="mono">{_esc(checked)}</span>'
                f', decay <span class="mono">{_esc(e["decay_date"])}</span>'
                f' — {_esc(e["body"])}'
                f'<div class="src">Source: {_esc(e["source"])}</div>'
                + _label_form(e, "checklist")
                + "</li>"
            )
        parts.append('<ul class="checks">\n' + "\n".join(items) + "\n</ul>")
    else:
        parts.append('<p class="note">None.</p>')
    return "\n".join(parts)


def _coverage_body(store):
    pack_ids = _pack_ids(store)
    parts = ["<h1>Coverage</h1>"]
    if not pack_ids:
        parts.append(f'<p class="note">{_esc(NO_PACK_NOTE)}</p>')
        return "\n".join(parts)
    for pack_id in pack_ids:
        pack = store.get_pack(pack_id)
        items = store.list_pack_items(pack_id)
        scores = {s["item_id"]: s for s in store.list_coverage(pack_id)}
        tallies = store.coverage_tallies(pack_id)
        not_scored = len(items) - sum(tallies.values())
        parts.append(f"<h2>{_esc(pack['title'])}</h2>")
        parts.append(
            f'<p class="note">{_esc(pack["source_citation"])}'
            f' · version <span class="mono">{_esc(pack["version"])}</span></p>'
        )
        parts.append(
            f'<p class="counts mono">{_tally_html(tallies)} · not scored {not_scored}</p>'
        )
        groups = {}
        for item in items:
            groups.setdefault(item["group_name"], []).append(item)
        for group_name, group_items in groups.items():
            parts.append(f"<h3>{_esc(group_name)}</h3>")
            rows = []
            for item in group_items:
                score = scores.get(item["item_id"])
                if score is None:
                    status_html = '<span class="notscored">not scored</span>'
                    reasoning_html = ""
                    cited_html = "—"
                else:
                    if score["status"] == "Unknown":
                        status_html = '<span class="status-unknown">Unknown</span>'
                    else:
                        status_html = _esc(score["status"])
                    reasoning_html = _esc(score["reasoning"])
                    if score["na_reason"]:
                        reasoning_html += (
                            '<div class="na-reason">N/A reason: '
                            f"{_esc(score['na_reason'])}</div>"
                        )
                    if score["cited_entry_ids"]:
                        cited_html = ", ".join(
                            f'<a class="mono" href="/inventory#entry-{_esc(entry_id)}">'
                            f"{_esc(entry_id)}</a>"
                            for entry_id in score["cited_entry_ids"]
                        )
                    else:
                        cited_html = "—"
                rows.append(
                    f'<tr id="item-{_esc(item["item_id"])}">'
                    f'<td class="mono">{_esc(item["item_id"])}</td>'
                    f"<td>{status_html}</td>"
                    f"<td>{reasoning_html}</td>"
                    f"<td>{cited_html}</td></tr>"
                )
                rows.append(
                    '<tr class="write-row"><td colspan="4">'
                    + _score_form(store, pack_id, item, score)
                    + "</td></tr>"
                )
            parts.append(
                '<table class="coverage"><thead><tr><th>Item</th><th>Status</th>'
                "<th>Reasoning</th><th>Cited entries</th></tr></thead><tbody>\n"
                + "\n".join(rows)
                + "\n</tbody></table>"
            )
    return "\n".join(parts)


def _report_body(db_path):
    try:
        text = render_report(db_path)
    except ValueError as exc:
        return (
            "<h1>Report</h1>\n"
            f'<p class="note">error: {_esc(exc)}</p>'
        )
    return (
        "<h1>Report</h1>\n"
        '<p><a href="/report.md">Download as Markdown</a></p>\n'
        f'<pre class="report">{_esc(text)}</pre>'
    )


def _report_markdown(db_path):
    try:
        text = render_report(db_path)
    except ValueError as exc:
        return f"error: {exc}\n", {}
    return text, {"Content-Disposition": 'attachment; filename="report.md"'}


# -- page bodies (UI-2): model pass, adjudication, fixes --------------------


def _pack_select(store, selected=None):
    """A select of the loaded packs, defaulting to
    Store.default_pack_id (the primary pack, else the
    alphabetically-first loaded pack) — the one default the report,
    packet, and rubric validation all use."""
    packs = store.list_packs()
    default = selected or store.default_pack_id()
    options = []
    for pack in packs:
        pack_id = pack["pack_id"]
        is_selected = pack_id == default
        selected_attr = " selected" if is_selected else ""
        options.append(
            f'<option value="{_esc(pack_id)}"{selected_attr}>'
            f"{_esc(pack_id)} — {_esc(pack['title'])}</option>"
        )
    return "".join(options)


def _rubric_checkboxes(store, pack_id, name="rubric"):
    """One checkbox per rubric item in the pack, for the fix form."""
    if pack_id is None:
        return ""
    items = store.list_items(pack_id)
    boxes = []
    for item in items:
        boxes.append(
            f'<label><input type="checkbox" name="{name}"'
            f' value="{_esc(item["item_id"])}">'
            f' <span class="mono">{_esc(item["item_id"])}</span></label>'
        )
    return "".join(boxes)


def _rubric_select(store, pack_id):
    """A select of the pack's rubric items, blank first (no control
    cited), for the chain form."""
    options = ['<option value="">— none —</option>']
    if pack_id is not None:
        for item in store.list_items(pack_id):
            options.append(
                f'<option value="{_esc(item["item_id"])}">'
                f"{_esc(item['item_id'])}</option>"
            )
    return "".join(options)


def _model_pass_body(store):
    parts = ["<h1>Model pass</h1>"]
    packets = store.list_packets()
    runs = store.list_runs()
    if packets:
        latest = packets[-1]
        pack = store.get_pack(latest["pack_id"])
        title = pack["title"] if pack else latest["pack_id"]
        parts.append("<h2>Latest packet</h2>")
        parts.append(
            '<table class="facts">'
            f"<tr><th>Assembled</th><td class=\"mono\">{_esc(latest['assembled_date'])}</td></tr>"
            f"<tr><th>Pack</th><td>{_esc(title)}</td></tr>"
            f"<tr><th>Word cap</th><td class=\"mono\">{_esc(latest['word_cap'])}</td></tr>"
            f"<tr><th>Byte count</th><td class=\"mono\">{_esc(latest['byte_count'])}</td></tr>"
            f"<tr><th>SHA-256</th><td class=\"mono\">{_esc(latest['sha256'])}</td></tr>"
            "</table>"
        )
    else:
        parts.append(
            '<p class="note">No packet has been assembled yet.</p>'
        )
    parts.append("<h2>Assemble a packet</h2>")
    parts.append(
        '<form class="write" method="post" action="/model-pass/packet">'
        f'<label>Pack <select name="pack">{_pack_select(store)}</select></label>'
        '<label>Word cap <input name="word_cap" value="2500" size="6"></label>'
        f'<label>Date <input name="date" value="{_esc(_today())}" size="10"></label>'
        '<button type="submit">Assemble packet</button></form>'
        '<p class="note">The packet downloads as a file; save it — '
        "the store records only its hash and metadata, so it cannot "
        "be downloaded again later.</p>"
    )
    parts.append("<h2>Ingest model output</h2>")
    if not packets:
        parts.append(
            '<p class="note">No packet has been assembled yet — '
            "assemble one first, then ingest the output that answers it.</p>"
        )
    latest_hash = packets[-1]["sha256"] if packets else ""
    parts.append(
        '<form class="write" method="post" action="/model-pass/ingest">'
        '<label>Output <textarea name="output" rows="6" cols="72"></textarea></label>'
        f'<label>Packet hash <input name="packet_hash" value="{_esc(latest_hash)}" size="64"></label>'
        '<label>Model <input name="model" size="24"></label>'
        f'<label>Date <input name="date" value="{_esc(_today())}" size="10"></label>'
        '<button type="submit">Ingest output</button></form>'
    )
    parts.append("<h2>Runs</h2>")
    if not runs:
        parts.append('<p class="note">No runs recorded yet.</p>')
    else:
        rows = []
        for run in runs:
            rows.append(
                f'<tr><td class="mono">{run["id"]}</td>'
                f"<td>{_esc(run['model_label'])}</td>"
                f'<td class="mono">{_esc(run["run_date"])}</td>'
                f'<td class="mono">{_esc(run["packet_hash"])}</td>'
                f'<td><a href="/adjudication?run={run["id"]}">Adjudicate</a></td></tr>'
            )
        parts.append(
            '<table><thead><tr><th>Run</th><th>Model</th><th>Date</th>'
            "<th>Packet hash</th><th></th></tr></thead><tbody>\n"
            + "\n".join(rows)
            + "\n</tbody></table>"
        )
    return "\n".join(parts)


def _decision_form(run_id, section):
    """The decision form for one adjudication section. The decision
    select starts blank — the operator must pick; the store refuses
    an empty decision, and correct without a note is refused with
    the CLI's message."""
    options = ['<option value="">— choose —</option>']
    for decision in ADJUDICATION_DECISIONS:
        options.append(
            f'<option value="{_esc(decision)}">{_esc(decision)}</option>'
        )
    return (
        f'<form class="write" method="post"'
        f' action="/run/{run_id}/adjudicate/{_esc(section)}">'
        f'<label>Decision <select name="decision">{"".join(options)}</select></label>'
        '<label>Note (required for correct) '
        '<textarea name="note" rows="2" cols="52"></textarea></label>'
        f'<label>date <input name="date" value="{_esc(_today())}" size="10"></label>'
        '<label>actor <input name="actor" value="operator" size="9"></label>'
        '<button type="submit">Record decision</button></form>'
    )


def _section_history(events):
    """The full decision-event history for one section, in record
    order — every event, not just the standing."""
    if not events:
        return ""
    items = []
    for event in events:
        text = f"{_esc(event['decision'])}"
        if event["note"]:
            text += f" — note: {_esc(event['note'])}"
        text += (
            f' (<span class="mono">{_esc(event["date"])}</span>,'
            f" {_esc(event['actor'])})"
        )
        items.append(f"<li>{text}</li>")
    return "<h3>History</h3>\n<ul>\n" + "\n".join(items) + "\n</ul>"


def _standing_line(current, label):
    event = current.get(label)
    if event is None:
        return "<p>Standing: no decision recorded</p>"
    text = (
        f"<p>Standing: <strong>{_esc(event['decision'])}</strong>"
        f' (<span class="mono">{_esc(event["date"])}</span>,'
        f" {_esc(event['actor'])})"
    )
    if event["note"]:
        text += f" — note: {_esc(event['note'])}"
    return text + "</p>"


def _apply_forms(store, run_id):
    """The apply forms: the explicit acts that apply an adjudicated
    deliverable. They live on the Adjudication page, below the draft,
    and each is submitted separately — recording a decision never
    triggers one."""
    pack_ids = _pack_ids(store)
    pack_id = pack_ids[0] if pack_ids else None
    control_options = ['<option value="">— choose —</option>']
    for status in CONTROL_STATUSES:
        control_options.append(
            f'<option value="{_esc(status)}">{_esc(status)}</option>'
        )
    chain = (
        "<h2>Apply the decisions</h2>"
        "<h3>Add a chain</h3>"
        '<form class="write" method="post" action="/chain/new">'
        f'<input type="hidden" name="run" value="{run_id}">'
        '<label>Key <input name="key" size="8"></label>'
        '<label>Name <input name="name" size="30"></label>'
        '<label>Earliest control <input name="control" size="30"></label>'
        f'<label>Control status <select name="control_status">{"".join(control_options)}</select></label>'
        f'<label>Control rubric <select name="control_rubric">{_rubric_select(store, pack_id)}</select></label>'
        '<label>Steps, one &ldquo;&lt;phase&gt;: &lt;text&gt;&rdquo; per line '
        '<textarea name="steps" rows="3" cols="52"></textarea></label>'
        '<button type="submit">Add chain</button></form>'
    )
    fix = (
        "<h3>Add a fix</h3>"
        '<form class="write" method="post" action="/fix/new">'
        f'<input type="hidden" name="run" value="{run_id}">'
        '<label>ID <input name="id" size="8"></label>'
        '<label>Action <input name="action" size="40"></label>'
        '<label>Effort <input name="effort" size="12"></label>'
        '<label>Breaks <input name="breaks" size="20"></label>'
        f'<span class="cites">Rubric: {_rubric_checkboxes(store, pack_id)}</span>'
        f'<label>date <input name="date" value="{_esc(_today())}" size="10"></label>'
        '<label>actor <input name="actor" value="operator" size="9"></label>'
        '<button type="submit">Add fix</button></form>'
    )
    verify_next = (
        "<h3>Add a verify-next item</h3>"
        '<form class="write" method="post" action="/verify-next/new">'
        f'<input type="hidden" name="run" value="{run_id}">'
        '<label>Unknown <input name="unknown" size="40"></label>'
        '<label>Why <input name="why" size="40"></label>'
        '<label>Cheapest check <input name="check" size="40"></label>'
        '<button type="submit">Add verify-next item</button></form>'
    )
    return "\n".join([chain, fix, verify_next])


def _adjudication_body(store, query):
    runs = store.list_runs()
    parts = ["<h1>Adjudication</h1>"]
    if not runs:
        parts.append(
            '<p class="note">No runs recorded yet. Assemble a packet'
            ' and ingest its output on the <a href="/model-pass">'
            "Model pass</a> page first.</p>"
        )
        return "\n".join(parts)
    run_raw = query.get("run", [None])[0]
    run = None
    if run_raw is not None:
        try:
            wanted = int(run_raw)
        except ValueError:
            wanted = None
        if wanted is not None:
            run = store.get_run(wanted)
        if run is None:
            parts.append(
                f'<p class="note">No run {_esc(run_raw)}. Pick one'
                ' below, or go to the <a href="/model-pass">Model pass</a>'
                " page.</p>"
            )
    if run is None:
        run = runs[-1]
    if len(runs) > 1:
        links = []
        for other in runs:
            if other["id"] == run["id"]:
                links.append(
                    f'<span class="mono">{other["id"]}</span>'
                    f" — {_esc(other['model_label'])}"
                )
            else:
                links.append(
                    f'<a href="/adjudication?run={other["id"]}">'
                    f'<span class="mono">{other["id"]}</span>'
                    f" — {_esc(other['model_label'])}</a>"
                )
        parts.append(
            '<p class="note">Runs: ' + " · ".join(links) + "</p>"
        )
    parts.append(
        '<table class="facts">'
        f"<tr><th>Run</th><td class=\"mono\">{run['id']}</td></tr>"
        f"<tr><th>Packet hash</th><td class=\"mono\">{_esc(run['packet_hash'])}</td></tr>"
        f"<tr><th>Model</th><td>{_esc(run['model_label'])}</td></tr>"
        f"<tr><th>Run date</th><td class=\"mono\">{_esc(run['run_date'])}</td></tr>"
        "</table>"
    )
    preamble, sections = split_sections(run["raw_output"])
    if any(line.strip() for line in preamble):
        parts.append("<h2>Preamble</h2>")
        parts.append(
            f'<pre class="draft">{_esc(chr(10).join(preamble))}</pre>'
        )
    events = store.list_adjudications(run["id"])
    current = {}
    by_section = {}
    for event in events:
        current[event["section"]] = event
        by_section.setdefault(event["section"], []).append(event)
    if not sections:
        parts.append("<h2>Unsectioned output</h2>")
        # The full raw output verbatim, followed by the single stub
        # render_draft appends — one block, as the draft renders it.
        unsectioned = run["raw_output"].rstrip("\n") + "\n\n" + STUB
        parts.append(
            f'<pre class="draft">{_esc(unsectioned)}</pre>'
        )
        for section in ADJUDICATION_SECTIONS:
            label = ADJUDICATION_SECTION_LABELS[section]
            parts.append(f"<h3>{label}</h3>")
            parts.append(_standing_line(current, section))
            parts.append(_decision_form(run["id"], section))
            parts.append(_section_history(by_section.get(section, [])))
    else:
        for name, section_lines in sections:
            section = DRAFT_SECTION_KEYS[name]
            label = ADJUDICATION_SECTION_LABELS[section]
            parts.append(f"<h2>{_esc(name)}</h2>")
            parts.append(
                "<p class=\"note\">"
                f"Adjudication section: {label}</p>"
            )
            # The section's lines verbatim, followed by the
            # adjudication stub exactly as render_draft appends it —
            # the stub is part of the draft text, not stripped.
            draft_lines = list(section_lines) + [""] + STUB.splitlines()
            parts.append(
                f'<pre class="draft">{_esc(chr(10).join(draft_lines))}</pre>'
            )
            parts.append(_standing_line(current, section))
            parts.append(_decision_form(run["id"], section))
            parts.append(_section_history(by_section.get(section, [])))
    parts.append(_apply_forms(store, run["id"]))
    parts.append(_applied_section(store))
    return "\n".join(parts)


def _applied_section(store):
    """What the apply forms have recorded so far: the chains, fixes,
    and verify-next items on the record. The redirect after an apply
    lands back on this page, so the result of the write must be
    visible here — that visible change is the confirmation."""
    chains = store.list_chains()
    fixes = store.list_fixes()
    verify_next = store.list_verify_next()
    parts = ["<h2>Applied so far</h2>"]
    parts.append("<h3>Chains</h3>")
    if chains:
        items = [
            f'<li><span class="mono">{_esc(c["chain_key"])}</span>'
            f' — {_esc(c["name"])}</li>'
            for c in chains
        ]
        parts.append("<ul>\n" + "\n".join(items) + "\n</ul>")
    else:
        parts.append('<p class="note">None.</p>')
    parts.append("<h3>Fixes</h3>")
    if fixes:
        items = [
            f'<li><span class="mono">{_esc(f["fix_id"])}</span>'
            f' — {_esc(f["action"])} ({_esc(f["status"])})'
            ' — <a href="/fixes">Fixes</a></li>'
            for f in fixes
        ]
        parts.append("<ul>\n" + "\n".join(items) + "\n</ul>")
    else:
        parts.append('<p class="note">None.</p>')
    parts.append("<h3>Verify-next</h3>")
    if verify_next:
        items = [
            f'<li><span class="mono">{_esc(i["seq"])}</span>'
            f' — {_esc(i["unknown_text"])}</li>'
            for i in verify_next
        ]
        parts.append("<ul>\n" + "\n".join(items) + "\n</ul>")
    else:
        parts.append('<p class="note">None.</p>')
    return "\n".join(parts)


def _fix_transition_form(fix):
    """The status-transition form for one fix. The status select
    starts blank — the operator must pick; submitting the fix's
    current status is refused by the store, and that refusal is
    the clean 400 the operator sees."""
    options = ['<option value="">— choose —</option>']
    for status in FIX_STATUSES:
        options.append(
            f'<option value="{_esc(status)}">{_esc(status)}</option>'
        )
    return (
        f'<form class="write" method="post"'
        f' action="/fix/{_esc(fix["fix_id"])}/status">'
        f'<label>Status <select name="status">{"".join(options)}</select></label>'
        f'<label>date <input name="date" value="{_esc(_today())}" size="10"></label>'
        '<label>actor <input name="actor" value="operator" size="9"></label>'
        '<button type="submit">Set status</button></form>'
    )


def _citation_context(store):
    """(default_pack, item_packs) for annotating rubric citations
    exactly as the report does: the rendered pack is
    Store.default_pack_id(), and item_packs is built as
    gather_report_data builds it — the rendered pack's items first,
    then every other pack in pack_id order, first owner kept."""
    default_pack = store.default_pack_id()
    item_packs = {}
    other_packs = [
        row["pack_id"] for row in store.conn.execute(
            "SELECT pack_id FROM rubric_pack ORDER BY pack_id"
        ).fetchall()
        if row["pack_id"] != default_pack
    ]
    owners = ([default_pack] if default_pack is not None else []) + other_packs
    for owner in owners:
        for item in store.list_items(owner):
            item_packs.setdefault(item["item_id"], owner)
    return default_pack, item_packs


def _fixes_body(store):
    fixes = store.list_fixes()
    default_pack, item_packs = _citation_context(store)
    parts = ["<h1>Fixes</h1>"]
    by_status = {status: [] for status in FIX_STATUSES}
    for fix in fixes:
        by_status[fix["status"]].append(fix)
    for status in FIX_STATUSES:
        group = by_status[status]
        parts.append(f"<h2>{_esc(status)} ({len(group)})</h2>")
        if not group:
            parts.append('<p class="note">None.</p>')
            continue
        for fix in group:
            if fix["rubric_item_ids"]:
                stored = fix.get("rubric_item_packs") or {}
                cites = ", ".join(
                    f'<a class="mono" href="/coverage#item-{_esc(item_id)}">'
                    + _esc(cite_item(
                        item_id, default_pack, item_packs,
                        stored.get(item_id),
                    ))
                    + "</a>"
                    for item_id in fix["rubric_item_ids"]
                )
            else:
                cites = "—"
            parts.append(
                f'<article class="entry" id="fix-{_esc(fix["fix_id"])}">'
                f'<div class="entry-head"><span class="mono eid">{_esc(fix["fix_id"])}</span>'
                f'<span class="mono">{_esc(fix["status"])}</span></div>'
                f'<p class="entry-body">{_esc(fix["action"])}</p>'
                f'<p class="entry-meta">Effort: {_esc(fix["effort"])}'
                f' · Breaks: {_esc(fix["chains_broken"])}'
                f" · Rubric: {cites}"
                f' · {_esc(fix["status"])}'
                f' <span class="mono">{_esc(fix["status_date"])}</span>'
                f' by {_esc(fix["status_actor"])}</p>'
                + _fix_transition_form(fix)
                + "</article>"
            )
    return "\n".join(parts)


# -- writes (UI-1): the verification loop's four POST routes -----------------


class WebRefusal(Exception):
    """A write refused cleanly: the message is shown verbatim with
    HTTP 400 — the CLI's refusal wordings and the store's invariant
    messages, never a traceback."""


def _field(form, name, default=None):
    values = form.get(name)
    return values[0] if values else default


def _host_allowed(host_header, bind_host, bind_port):
    """Layer 1 of the write and read protection: the Host header.

    The request is allowed only when the Host header's host part is
    the bind host or a loopback name (127.0.0.1, localhost, ::1) AND
    its port part equals the bound port. A wildcard bind host
    (0.0.0.0 or ::) is not a name anyone can address, so it is never
    allowed as a Host: a wildcard bind answers loopback names only.
    A missing port counts only
    when the bound port is 80 or 443. A missing or unparseable Host
    header is refused. This defeats DNS rebinding: a page served
    from evil.example that resolves to 127.0.0.1 still sends
    "Host: evil.example:<port>", and is refused before anything is
    read or written.
    """
    if not host_header:
        return False
    try:
        parts = urlsplit("//" + host_header.strip())
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return False
    if not hostname:
        return False
    allowed = {name.lower() for name in LOOPBACK_NAMES}
    if bind_host:
        bind_name = bind_host.strip("[]").lower()
        if bind_name not in WILDCARD_BIND_HOSTS:
            allowed.add(bind_name)
    if hostname.lower() not in allowed:
        return False
    if port is None:
        return bind_port in (80, 443)
    return port == bind_port


_WRITE_FORM_OPEN = re.compile(r'(<form class="write" method="post"[^>]*>)')


def _inject_token(text, token):
    """Add the write token as a hidden field to every write form.

    Every write form the UI renders opens with
    '<form class="write" method="post"'; the token goes in right
    after that opening tag. The token is hex, so it needs no
    escaping.
    """
    if not token:
        return text
    hidden = f'<input type="hidden" name="{TOKEN_FIELD}" value="{token}">'
    return _WRITE_FORM_OPEN.sub(lambda m: m.group(1) + hidden, text)


def _token_valid(form, token):
    """Layer 3: the submitted token must equal the server's token."""
    submitted = _field(form, TOKEN_FIELD)
    if not submitted or not token:
        return False
    return hmac.compare_digest(submitted.encode("utf-8"), token.encode("utf-8"))


def _origin_allowed(headers):
    """The POST origin check. When an Origin header is present, its
    host must equal the request's Host header; with no Origin, a
    Referer is checked the same way; with neither (the operator's own
    scripts), the submission is allowed. This is not authentication —
    it refuses the drive-by form-post from an unrelated web page while
    the server is up.
    """
    host = headers.get("Host")
    origin = headers.get("Origin")
    if origin is not None:
        return urlparse(origin).netloc == host
    referer = headers.get("Referer")
    if referer is not None:
        return urlparse(referer).netloc == host
    return True


def _return_href(form):
    """The inventory view a form was submitted from, filters included."""
    return _inv_href(
        label=_field(form, "label_filter"),
        section=_field(form, "section_filter"),
    )


def _entry_ids(store):
    return {e["entry_id"] for e in store.list_inventory()}


def _apply_set_label(store, entry_id, form):
    if entry_id not in _entry_ids(store):
        raise WebRefusal(f"no such entry: {entry_id}")
    store.set_entry_label(
        entry_id,
        _field(form, "label", ""),
        date=_field(form, "date") or _today(),
        actor=_field(form, "actor") or "operator",
    )
    if _field(form, "from") == "checklist":
        return "/checklist"
    return _return_href(form)


def _apply_edit_entry(store, entry_id, form):
    if entry_id not in _entry_ids(store):
        raise WebRefusal(f"no such entry: {entry_id}")

    def _date(name):
        # The store's tri-state: a field missing from the submission
        # leaves the date unchanged (UNSET); an emptied field clears
        # it (None); any other value sets it.
        value = _field(form, name)
        if value is None:
            return UNSET
        return value if value != "" else None

    # A label field, if one is submitted anyway, is never read:
    # details and labels change through different doors.
    store.update_entry_details(
        entry_id,
        body=_field(form, "body"),
        source=_field(form, "source"),
        checked_date=_date("checked_date"),
        decay_date=_date("decay_date"),
    )
    return _return_href(form)


def _apply_add_entry(store, form):
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    section = _field(form, "section", "")
    if section not in SECTIONS:
        raise WebRefusal("section must be one of " + ", ".join(SECTIONS))
    entry_id = store.next_entry_id(section)
    store.add_inventory_entry(
        eng["id"], entry_id, section,
        _field(form, "body", ""), _field(form, "label", "UNKNOWN"),
        _field(form, "source", ""),
        _field(form, "checked_date") or None,
        _field(form, "decay_date") or None,
        date=_field(form, "date") or _today(),
        actor=_field(form, "actor") or "operator",
    )
    return _inv_href(section=section)


def _apply_score(store, pack_id, item_id, form):
    # The CLI's score-reference checks, with its messages verbatim:
    # every reference resolves before anything writes.
    if store.get_pack(pack_id) is None:
        raise WebRefusal(f"no such pack: {pack_id}")
    item_ids = {i["item_id"] for i in store.list_items(pack_id)}
    if item_id not in item_ids:
        raise WebRefusal(f"no such item in pack {pack_id}: {item_id}")
    cited = form.get("cite", [])
    entry_ids = _entry_ids(store)
    for entry_id in cited:
        if entry_id not in entry_ids:
            raise WebRefusal(f"no such entry: {entry_id}")
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    status = _field(form, "status", "")
    reasoning = _field(form, "reasoning", "")
    na_reason = _field(form, "na_reason") or None
    if store.get_coverage(pack_id, item_id) is None:
        store.save_coverage(
            eng["id"], pack_id, item_id, status, reasoning, cited, na_reason
        )
    else:
        store.replace_coverage(
            eng["id"], pack_id, item_id, status, reasoning, cited, na_reason
        )
    return "/coverage"


# -- writes (UI-2): the model pass and adjudication ------------------------


def _default_pack_id(store):
    """The tool-wide default pack (the primary pack, else
    alphabetically first; Store.default_pack_id), or the CLI's clean
    refusal when none is
    loaded."""
    pack_id = store.default_pack_id()
    if pack_id is None:
        raise WebRefusal(
            "database holds no rubric pack; load one with load-pack"
        )
    return pack_id


def _check_rubric_item(store, pack_id, item_id):
    """The CLI's rubric-item check, with its message verbatim."""
    item_ids = {i["item_id"] for i in store.list_items(pack_id)}
    if item_id not in item_ids:
        raise WebRefusal(f"no such item in pack {pack_id}: {item_id}")


def _adjudication_return(form):
    """The adjudication page the apply forms were submitted from."""
    run = _field(form, "run")
    if run and run.isdigit():
        return f"/adjudication?run={run}"
    return "/adjudication"


def _apply_packet(db_path, store, form):
    """Assemble the packet and return it as a download — the one
    POST that answers with a file instead of a 303 (see §1.2 of the
    UI-2 brief: the packet text exists nowhere after assembly except
    in this response). Returns ("download", filename, text)."""
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    pack_id = _field(form, "pack") or None
    word_cap_raw = _field(form, "word_cap") or "2500"
    try:
        word_cap = int(word_cap_raw)
    except ValueError:
        raise WebRefusal("word cap must be a whole number")
    try:
        assembled_date = datetime.date.fromisoformat(
            _field(form, "date") or _today()
        ).isoformat()
    except ValueError:
        raise WebRefusal("packet date must be a valid ISO date") from None
    try:
        text, pack = assemble_packet(
            db_path, pack_id=pack_id, word_cap=word_cap,
            assembled_date=assembled_date,
        )
    except ValueError as exc:
        raise WebRefusal(str(exc))
    data = text.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    store.record_packet(
        eng["id"], pack["pack_id"], assembled_date,
        word_cap, len(data), sha256,
    )
    filename = f"packet-{assembled_date}-{sha256[:8]}.md"
    return ("download", filename, text)


def _apply_ingest(store, form):
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    packet_hash = _field(form, "packet_hash", "")
    if store.get_packet_by_hash(packet_hash) is None:
        raise WebRefusal(f"no recorded packet with hash: {packet_hash}")
    raw = _field(form, "output", "")
    # Browsers submit textarea newlines as CRLF; the stored text is
    # the LF text the CLI's file ingest would store. This one
    # normalization is the only transformation the paste undergoes.
    output = raw.replace("\r\n", "\n").replace("\r", "\n")
    model = _field(form, "model") or "not stated"
    run_id = store.record_run(
        eng["id"], packet_hash, model,
        _field(form, "date") or _today(), output,
    )
    return ("redirect", f"/adjudication?run={run_id}")


def _apply_adjudicate(store, run_id_raw, section, form):
    try:
        run_id = int(run_id_raw)
    except (TypeError, ValueError):
        raise WebRefusal(f"no such run: {run_id_raw}")
    if store.get_run(run_id) is None:
        raise WebRefusal(f"no such run: {run_id}")
    if section not in ADJUDICATION_SECTIONS:
        raise WebRefusal(
            f"section must be one of {ADJUDICATION_SECTIONS}"
        )
    decision = _field(form, "decision", "")
    if decision not in ADJUDICATION_DECISIONS:
        raise WebRefusal(
            f"decision must be one of {ADJUDICATION_DECISIONS}"
        )
    note = _field(form, "note") or None
    if decision == "correct" and not note:
        raise WebRefusal(
            "--decision correct requires --note;"
            " the note is the correction, preserved in the record"
        )
    store.record_adjudication(
        run_id, section, decision, note,
        _field(form, "date") or _today(),
        _field(form, "actor") or "operator",
    )
    return ("redirect", f"/adjudication?run={run_id}")


def _apply_add_chain(store, form):
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    key = _field(form, "key", "")
    name = _field(form, "name", "")
    control = _field(form, "control", "")
    if not key or not name or not control:
        raise WebRefusal("key, name, and earliest control are required")
    lines = [
        line.strip()
        for line in _field(form, "steps", "").splitlines()
    ]
    lines = [line for line in lines if line]
    if not lines:
        raise WebRefusal("at least one --step is required")
    steps = []
    for raw in lines:
        phase, sep, text = raw.partition(":")
        if not sep or not phase.strip() or not text.strip():
            raise WebRefusal(f"step must be '<phase>: <text>': {raw}")
        steps.append({"phase": phase.strip(), "text": text.strip()})
    if key in {c["chain_key"] for c in store.list_chains()}:
        raise WebRefusal(f"duplicate chain key: {key}")
    control_status = _field(form, "control_status", "")
    if control_status not in CONTROL_STATUSES:
        raise WebRefusal(
            f"control status must be one of {CONTROL_STATUSES}"
        )
    control_rubric = _field(form, "control_rubric") or None
    control_pack = None
    if control_rubric is not None:
        control_pack = _default_pack_id(store)
        _check_rubric_item(store, control_pack, control_rubric)
    store.add_chain(
        eng["id"], key, name, steps, control, control_status,
        control_rubric, control_pack=control_pack,
    )
    return ("redirect", _adjudication_return(form))


def _apply_add_fix(store, form):
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    fix_id = _field(form, "id", "")
    action = _field(form, "action", "")
    effort = _field(form, "effort", "")
    breaks = _field(form, "breaks", "")
    if not fix_id or not action or not effort or not breaks:
        raise WebRefusal(
            "id, action, effort, and chains broken are required"
        )
    if fix_id in {f["fix_id"] for f in store.list_fixes()}:
        raise WebRefusal(f"duplicate fix id: {fix_id}")
    rubric = form.get("rubric", [])
    pack_id = None
    if rubric:
        pack_id = _default_pack_id(store)
        for item_id in rubric:
            _check_rubric_item(store, pack_id, item_id)
    store.add_fix(
        eng["id"], fix_id, action, effort, breaks, rubric,
        status="proposed",
        status_date=_field(form, "date") or _today(),
        status_actor=_field(form, "actor") or "operator",
        rubric_pack_id=pack_id,
    )
    return ("redirect", _adjudication_return(form))


def _apply_set_fix_status(store, fix_id, form):
    store.set_fix_status(
        fix_id, _field(form, "status", ""),
        date=_field(form, "date") or _today(),
        actor=_field(form, "actor") or "operator",
    )
    return ("redirect", "/fixes")


def _apply_add_verify_next(store, form):
    eng = store.get_engagement()
    if eng is None:
        raise WebRefusal("database holds no engagement")
    unknown = _field(form, "unknown", "")
    why = _field(form, "why", "")
    check = _field(form, "check", "")
    if not unknown or not why or not check:
        raise WebRefusal(
            "unknown, why, and cheapest check are required"
        )
    existing = []
    for item in store.list_verify_next():
        try:
            existing.append(int(item["seq"]))
        except (TypeError, ValueError, OverflowError):
            existing.append(0)
    seq = max(existing, default=0) + 1
    store.add_verify_next(eng["id"], seq, unknown, why, check)
    return ("redirect", _adjudication_return(form))


def _apply_post(db_path, path, form):
    """Run one write route.

    Returns ("redirect", location), ("download", filename, text) for
    the packet route, or None when the path is not a write route
    (the caller refuses with 405).

    Refusals raise WebRefusal, InvariantError, or sqlite3.Error; the
    store is closed either way, and because each store method commits
    only on success, a refused write leaves nothing behind.
    """
    segments = [unquote(s) for s in path.split("/") if s != ""]
    store = Store(db_path)
    try:
        if segments == ["entry", "new"]:
            return ("redirect", _apply_add_entry(store, form))
        if len(segments) == 3 and segments[0] == "entry" and segments[2] == "label":
            return ("redirect", _apply_set_label(store, segments[1], form))
        if len(segments) == 3 and segments[0] == "entry" and segments[2] == "edit":
            return ("redirect", _apply_edit_entry(store, segments[1], form))
        if (
            len(segments) == 4 and segments[0] == "coverage"
            and segments[3] == "score"
        ):
            return (
                "redirect",
                _apply_score(store, segments[1], segments[2], form),
            )
        if segments == ["model-pass", "packet"]:
            return _apply_packet(db_path, store, form)
        if segments == ["model-pass", "ingest"]:
            return _apply_ingest(store, form)
        if (
            len(segments) == 4 and segments[0] == "run"
            and segments[2] == "adjudicate"
        ):
            return _apply_adjudicate(
                store, segments[1], segments[3], form
            )
        if segments == ["chain", "new"]:
            return _apply_add_chain(store, form)
        if segments == ["fix", "new"]:
            return _apply_add_fix(store, form)
        if (
            len(segments) == 3 and segments[0] == "fix"
            and segments[2] == "status"
        ):
            return _apply_set_fix_status(store, segments[1], form)
        if segments == ["verify-next", "new"]:
            return _apply_add_verify_next(store, form)
        return None
    finally:
        store.close()


def _error_response(db_path, message):
    """A refused write, rendered plainly in the usual chrome: the
    refusal message verbatim, and a statement that nothing was
    written. (A plain error page rather than the referring page
    re-rendered — the message is the content; the operator goes back
    and corrects the submission.)
    """
    store = Store(db_path)
    try:
        unknown, decayed = _checklist_split(store)
        checklist_total = len(unknown) + len(decayed)
        adj_undecided = _adjudication_undecided(store)
    finally:
        store.close()
    body = (
        "<h1>Not recorded</h1>\n"
        f'<p class="form-error">error: {_esc(message)}</p>\n'
        '<p class="note">Nothing was written. Go back and correct'
        " the submission.</p>"
    )
    return _page("Not recorded", "", checklist_total, body, adj_undecided)


# -- HTTP plumbing ----------------------------------------------------------


def _html_response(db_path, path, query):
    """Render one HTML page. Returns (status, text)."""
    store = Store(db_path)
    try:
        unknown, decayed = _checklist_split(store)
        checklist_total = len(unknown) + len(decayed)
        adj_undecided = _adjudication_undecided(store)
        if path == "/":
            title, body = "Overview", _overview_body(store)
        elif path == "/inventory":
            title, body = "Inventory", _inventory_body(store, query)
        elif path == "/checklist":
            title, body = "Checklist", _checklist_body(store)
        elif path == "/coverage":
            title, body = "Coverage", _coverage_body(store)
        elif path == "/model-pass":
            title, body = "Model pass", _model_pass_body(store)
        elif path == "/adjudication":
            title, body = "Adjudication", _adjudication_body(store, query)
        elif path == "/fixes":
            title, body = "Fixes", _fixes_body(store)
        elif path == "/report":
            title, body = "Report", _report_body(db_path)
        else:
            body = (
                "<h1>Not found</h1>\n"
                f'<p class="note">No page at <span class="mono">{_esc(path)}</span>.</p>'
            )
            return 404, _page(
                "Not found", "", checklist_total, body, adj_undecided
            )
    finally:
        store.close()
    return 200, _page(title, path, checklist_total, body, adj_undecided)


def _is_write_route(path):
    """True when path is one of the routes that accept POST."""
    segments = [s for s in path.split("/") if s != ""]
    return bool(
        segments == ["entry", "new"]
        or (len(segments) == 3 and segments[0] == "entry")
        or (len(segments) == 4 and segments[0] == "coverage")
        or segments == ["model-pass", "packet"]
        or segments == ["model-pass", "ingest"]
        or (
            len(segments) == 4 and segments[0] == "run"
            and segments[2] == "adjudicate"
        )
        or segments == ["chain", "new"]
        or segments == ["fix", "new"]
        or (
            len(segments) == 3 and segments[0] == "fix"
            and segments[2] == "status"
        )
        or segments == ["verify-next", "new"]
    )


def make_handler(db_path, bind_host=None, bind_port=None, token=None):
    """The request handler class for one served database.

    bind_host and bind_port are the server's own authority (the
    bound port, never 0); every request's Host header is checked
    against them before anything else happens. token is the
    per-process write token every POST must carry; it lives in
    server memory only and is never printed or logged.
    """
    class Handler(BaseHTTPRequestHandler):
        server_version = "Fencewalk"

        def log_message(self, *args):
            pass

        def _send(self, status, content_type, payload, head=False, extra=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            # No page may be framed: a framed write form is one
            # tricked click from a same-origin submission. Sent on
            # every response, whatever its status.
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy", "frame-ancestors 'none'"
            )
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if not head:
                self.wfile.write(payload)

        def _host_ok(self, head=False):
            """Layer 1: refuse a foreign Host with 403, nothing served."""
            if _host_allowed(self.headers.get("Host"), bind_host, bind_port):
                return True
            self._send(
                403, "text/plain; charset=utf-8",
                (
                    "403 Forbidden — the request's Host does not name"
                    " this server; nothing was served or written.\n"
                ).encode("utf-8"),
                head,
            )
            return False

        def _handle(self, head=False):
            if not self._host_ok(head):
                return
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/report.md":
                    text, extra = _report_markdown(db_path)
                    self._send(
                        200, "text/plain; charset=utf-8",
                        text.encode("utf-8"), head, extra,
                    )
                    return
                status, text = _html_response(
                    db_path, parsed.path, parse_qs(parsed.query)
                )
                text = _inject_token(text, token)
                self._send(
                    status, "text/html; charset=utf-8",
                    text.encode("utf-8"), head,
                )
            except Exception:
                self._send(
                    500, "text/plain; charset=utf-8",
                    b"500 Internal Server Error\n", head,
                )

        def do_GET(self):
            self._handle(head=False)

        def do_HEAD(self):
            self._handle(head=True)

        def _refuse(self):
            if not self._host_ok():
                return
            self._send_405()

        def _send_405(self):
            allow = "GET, HEAD"
            if _is_write_route(urlparse(self.path).path):
                allow = "GET, HEAD, POST"
            self._send(
                405, "text/plain; charset=utf-8",
                "405 Method Not Allowed\n".encode("utf-8"),
                extra={"Allow": allow},
            )

        def do_POST(self):
            try:
                self._handle_post()
            except Exception:
                self._send(
                    500, "text/plain; charset=utf-8",
                    b"500 Internal Server Error\n",
                )

        def _handle_post(self):
            if not self._host_ok():
                return
            parsed = urlparse(self.path)
            if not _origin_allowed(self.headers):
                self._send(
                    403, "text/plain; charset=utf-8",
                    (
                        "403 Forbidden — the submission's origin does"
                        " not match this server; nothing was written.\n"
                    ).encode("utf-8"),
                )
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length > MAX_POST_BYTES:
                self._send_413()
                return
            raw = self.rfile.read(min(max(0, length), MAX_POST_BYTES + 1))
            if len(raw) > MAX_POST_BYTES:
                self._send_413()
                return
            form = parse_qs(
                raw.decode("utf-8", errors="replace"),
                keep_blank_values=True,
            )
            if not _is_write_route(parsed.path):
                self._send_405()
                return
            if not _token_valid(form, token):
                self._send(
                    403, "text/plain; charset=utf-8",
                    (
                        "403 Forbidden — the submission's write token is"
                        " missing or wrong; nothing was written. Reload"
                        " the page and submit again.\n"
                    ).encode("utf-8"),
                )
                return
            try:
                result = _apply_post(db_path, parsed.path, form)
            except (WebRefusal, InvariantError, sqlite3.Error) as exc:
                text = _inject_token(_error_response(db_path, str(exc)), token)
                self._send(
                    400, "text/html; charset=utf-8", text.encode("utf-8")
                )
                return
            if result is None:
                self._send_405()
                return
            if result[0] == "download":
                _, filename, text = result
                self._send(
                    200, "text/plain; charset=utf-8",
                    text.encode("utf-8"),
                    extra={
                        "Content-Disposition":
                            f'attachment; filename="{filename}"'
                    },
                )
                return
            self._send(
                303, "text/plain; charset=utf-8", b"",
                extra={"Location": result[1]},
            )

        def _send_413(self):
            self.close_connection = True
            self._send(
                413, "text/plain; charset=utf-8",
                b"413 Content Too Large\n",
            )

        do_PUT = _refuse
        do_DELETE = _refuse
        do_PATCH = _refuse

    return Handler


def create_server(db_path, host, port):
    """Bind the server, then give the handler its real authority.

    The handler is built after the bind so it knows the bound port
    even when port 0 (an ephemeral port) was requested. The write
    token is generated here, once per server, and held only in the
    handler class's closure and on the server object (for in-process
    callers such as the tests); it is never printed or logged.
    """
    server = ThreadingHTTPServer((host, port), BaseHTTPRequestHandler)
    bound_port = server.server_address[1]
    token = secrets.token_hex(32)
    server.RequestHandlerClass = make_handler(db_path, host, bound_port, token)
    server.write_token = token
    server.daemon_threads = True
    return server


def serve(db_path, host="127.0.0.1", port=8090):
    server = create_server(db_path, host, port)
    bound_host, bound_port = server.server_address[:2]
    print(f"Fencewalk web interface serving {db_path}")
    print(f"  http://{bound_host}:{bound_port}/")
    warning = startup_warning(host)
    if warning is not None:
        print(warning)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
