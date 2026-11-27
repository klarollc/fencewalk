"""Fencewalk CLI.

Usage:
    python -m fencewalk --version
    python -m fencewalk packs
    python -m fencewalk register <db-path> [--registry <path>]
    python -m fencewalk unregister <db-path> [--registry <path>]
    python -m fencewalk engagements [--registry <path>]
    python -m fencewalk load-fixture <fixture-dir> <db-path>
    python -m fencewalk report <db-path> [--pack <pack-id>] [--out <file>]
    python -m fencewalk pdf <db-path> --out <file> [--pack <pack-id>]
    python -m fencewalk diff <older-db> <newer-db> [--pack <pack-id>]
        [--out <file>]
    python -m fencewalk new <db-path> --name <name> --subject <subject>
        --method-order <verify-first|model-first> [--date <YYYY-MM-DD>]
    python -m fencewalk add-entry <db-path> --section <A-H> --body <text>
        --label <VERIFIED|ON RECORD|UNKNOWN> --source <text>
        [--id <entry-id>] [--checked-date <date>] [--decay-date <date>]
        [--date <date>] [--actor <actor>]
    python -m fencewalk edit-entry <db-path> <entry-id>
        [--body <text>] [--source <text>] [--checked-date <date>]
        [--decay-date <date>] [--clear-checked-date] [--clear-decay-date]
    python -m fencewalk set-label <db-path> <entry-id> <label>
        [--date <date>] [--actor <actor>]
    python -m fencewalk list-entries <db-path> [--section <A-H>]
    python -m fencewalk import-inventory <db-path> <markdown-file>
        [--date <date>] [--actor <actor>]
    python -m fencewalk load-pack <db-path> <pack-file>
    python -m fencewalk score <db-path> --pack <pack-id> --item <item-id>
        --status <status> --reasoning <text> [--cite <entry-id>]...
        [--na-reason <text>]
    python -m fencewalk rescore <db-path> --pack <pack-id> --item <item-id>
        --status <status> --reasoning <text> [--cite <entry-id>]...
        [--na-reason <text>]
    python -m fencewalk list-coverage <db-path> --pack <pack-id>
    python -m fencewalk checklist <db-path> [--date <YYYY-MM-DD>]
        [--out <file>]
    python -m fencewalk packet <db-path> --out <file>
        [--pack <pack-id>] [--word-cap <n>] [--date <YYYY-MM-DD>]
        [--posture standard|adversarial]
    python -m fencewalk fix-packet <db-path> <fix-id> [--out <file>]
    python -m fencewalk calibration <db-path> [--pack <pack-id>] [--out <file>]
    python -m fencewalk run-model <db-path> --provider anthropic --model <model-id>
        --out <file> [--pack <pack-id>] [--word-cap <n>]
        [--max-output-tokens <n>] [--date <YYYY-MM-DD>] [--dry-run]
    python -m fencewalk ingest <db-path> <output-file>
        --packet-hash <sha256> [--model <label>] [--date <YYYY-MM-DD>]
    python -m fencewalk draft <db-path> --run <run-id> [--out <file>]
    python -m fencewalk adjudicate <db-path> --run <run-id>
        --section <coverage|chains|fixes|verify-next>
        --decision <accept|correct|reject> [--note <text>]
        [--date <YYYY-MM-DD>] [--actor <actor>]
    python -m fencewalk adjudications <db-path> --run <run-id>
    python -m fencewalk record-probe <db-path> --pack <pack-id> --item <item-id>
        --method <text> --outcome confirmed|failed|inconclusive
        [--date <YYYY-MM-DD>] [--actor <name>]
    python -m fencewalk probes <db-path> [--pack <pack-id>] [--unprobed]
    python -m fencewalk add-chain <db-path> --key <key> --name <text>
        --control <text> --control-status <present|absent|unknown>
        [--control-rubric <item-id>] [--pack <pack-id>]
        --step "<phase>: <text>" [--step ...]
        [--step-item <step-no>=<item-id> ...]
    python -m fencewalk set-step-item <db-path> --chain <key> --step <n>
        (--item <item-id> [--pack <pack-id>] | --clear)
    python -m fencewalk chains <db-path>
    python -m fencewalk add-fix <db-path> --id <fix-id> --action <text>
        --effort <text> --breaks <text> [--rubric <item-id>]...
        [--pack <pack-id>] [--date <YYYY-MM-DD>] [--actor <actor>]
    python -m fencewalk set-fix-status <db-path> <fix-id> <status>
        [--date <YYYY-MM-DD>] [--actor <actor>]
    python -m fencewalk list-fixes <db-path>
    python -m fencewalk add-verify-next <db-path> --unknown <text>
        --why <text> --check <text>
    python -m fencewalk serve <db-path> [--host <host>] [--port <port>]

Errors are reported as a single 'error: ...' line on stderr with exit
status 1 — never a traceback.
"""

import argparse
import datetime
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .calibration import render_calibration
from .chains import render_chains
from .checklist import render_checklist
from .diff import render_diff
from .draft import render_draft
from .fixpacket import render_fix_packet
from .model_api import call_provider
from .fixture import (
    bundled_fixture_dir,
    bundled_pack_names,
    bundled_pack_path,
    load_fixture,
    load_pack,
    validate_pack,
)
from .intake import format_import_report, import_inventory
from .packet import assemble_packet
from .probes import render_probes
from .report import render_report
from .report_pdf import render_pdf
from .registry import engagements, register, registry_path, unregister
from .store import (
    ADJUDICATION_DECISIONS,
    ADJUDICATION_SECTIONS,
    COVERAGE_STATUSES,
    EVIDENCE_LABELS,
    FIX_STATUSES,
    METHOD_ORDERS,
    PACKET_POSTURES,
    PROBE_OUTCOMES,
    UNSET,
    InvariantError,
    Store,
)
from .web import serve

SECTIONS = list("ABCDEFGH")


class CliError(Exception):
    """A user-facing error: printed cleanly, exit status 1."""


def _today():
    return datetime.date.today().isoformat()


def _open_store(db_path):
    if not Path(db_path).exists():
        raise CliError(f"no such database: {db_path}")
    return Store(db_path)


def _refuse_out_onto_db(args):
    """Refuse an --out that names the database file itself.

    Both paths are resolved (relative paths, `..`, and symlinks
    collapse to the real file), and the refusal happens before any
    rendering, provider call, or packet recording, so nothing is
    written and nothing is billed. Overwriting any other existing
    file stays allowed.
    """
    out = getattr(args, "out", None)
    if not out:
        return
    try:
        same = Path(out).resolve() == Path(args.db_path).resolve()
    except (OSError, RuntimeError):
        same = False
    if not same:
        try:
            same = Path(out).samefile(args.db_path)
        except OSError:
            same = False
    if same:
        raise CliError(f"--out must not be the database path: {out}")


def _engagement_id(store):
    eng = store.get_engagement()
    if eng is None:
        raise CliError("database holds no engagement")
    return eng["id"]


def _entry_ids(store):
    return {e["entry_id"] for e in store.list_inventory()}


def cmd_load_fixture(args):
    eng_id = load_fixture(
        bundled_fixture_dir(args.fixture_dir), args.db_path, pack_roots=args.pack_root,
    )
    print(f"loaded fixture from {args.fixture_dir} into {args.db_path} (engagement {eng_id})")
    return 0


def cmd_report(args):
    _refuse_out_onto_db(args)
    text = render_report(args.db_path, args.pack)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"report written to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_pdf(args):
    _refuse_out_onto_db(args)
    data = render_pdf(args.db_path, args.pack)
    Path(args.out).write_bytes(data)
    print(f"pdf written to {args.out}")
    return 0


def cmd_diff(args):
    # Refuse an --out naming either input before anything is read.
    for db_path in (args.older, args.newer):
        _refuse_out_onto_db(argparse.Namespace(out=args.out, db_path=db_path))
    text = render_diff(args.older, args.newer, args.pack)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"drift report written to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_new(args):
    db_path = Path(args.db_path)
    if db_path.exists():
        raise FileExistsError(f"database already exists: {db_path}")
    store = Store(db_path)
    try:
        store.init_schema()
        eng_id = store.create_engagement(
            args.name, args.subject, args.date or _today(), args.method_order
        )
    finally:
        store.close()
    print(f"created engagement {eng_id} in {db_path}")
    return 0


def cmd_add_entry(args):
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        entry_id = args.id or store.next_entry_id(args.section)
        if entry_id in _entry_ids(store):
            raise CliError(f"duplicate entry id: {entry_id}")
        store.add_inventory_entry(
            eng_id, entry_id, args.section, args.body, args.label,
            args.source, args.checked_date, args.decay_date,
            date=args.date or _today(), actor=args.actor,
        )
    finally:
        store.close()
    print(f"added {entry_id} ({args.label})")
    return 0


def cmd_edit_entry(args):
    if args.clear_checked_date and args.checked_date is not None:
        raise CliError("--checked-date and --clear-checked-date are mutually exclusive")
    if args.clear_decay_date and args.decay_date is not None:
        raise CliError("--decay-date and --clear-decay-date are mutually exclusive")
    checked_date = (
        None if args.clear_checked_date
        else args.checked_date if args.checked_date is not None
        else UNSET
    )
    decay_date = (
        None if args.clear_decay_date
        else args.decay_date if args.decay_date is not None
        else UNSET
    )
    store = _open_store(args.db_path)
    try:
        store.update_entry_details(
            args.entry_id, body=args.body, source=args.source,
            checked_date=checked_date, decay_date=decay_date,
        )
    finally:
        store.close()
    print(f"updated {args.entry_id}")
    return 0


def cmd_set_label(args):
    store = _open_store(args.db_path)
    try:
        if args.entry_id not in _entry_ids(store):
            raise CliError(f"no such entry: {args.entry_id}")
        store.set_entry_label(
            args.entry_id, args.label,
            date=args.date or _today(), actor=args.actor,
        )
    finally:
        store.close()
    print(f"{args.entry_id} label set to {args.label}")
    return 0


def cmd_list_entries(args):
    store = _open_store(args.db_path)
    try:
        entries = store.list_inventory()
    finally:
        store.close()
    if args.section:
        entries = [e for e in entries if e["section"] == args.section]
    for e in entries:
        first = e["body"].splitlines()[0] if e["body"] else ""
        if len(first) > 80:
            first = first[:77] + "..."
        dates = ""
        if e["checked_date"]:
            dates += f" checked {e['checked_date']}"
        if e["decay_date"]:
            dates += f" decay {e['decay_date']}"
        print(f"{e['entry_id']} [{e['label']}] section {e['section']}{dates} — {first}")
    return 0


def cmd_load_pack(args):
    pack = validate_pack(load_pack(bundled_pack_path(args.pack_file)))
    store = _open_store(args.db_path)
    try:
        if store.get_pack(pack["pack_id"]) is not None:
            raise CliError(f"pack already loaded: {pack['pack_id']}")
        store.add_pack(pack)
    finally:
        store.close()
    groups = {item["group"] for item in pack["items"]}
    print(
        f"loaded pack {pack['pack_id']}: {pack['title']}"
        f" — {len(pack['items'])} items, {len(groups)} groups"
    )
    return 0


def cmd_set_primary_pack(args):
    """Record a loaded pack as the engagement's primary pack: the
    default for report, packet, pdf and rubric validation."""
    store = _open_store(args.db_path)
    try:
        _engagement_id(store)
        _pack_or_error(store, args.pack_id)
        store.set_primary_pack(args.pack_id)
    finally:
        store.close()
    print(f"primary pack set to {args.pack_id}")
    return 0


def cmd_packs(args):
    """List the rubric packs shipped with the tool (read-only)."""
    for filename in bundled_pack_names():
        pack = load_pack(bundled_pack_path(filename))
        groups = {item["group"] for item in pack["items"]}
        print(
            f"{pack['pack_id']}: {pack['title']}"
            f" — {len(pack['items'])} items, {len(groups)} groups"
        )
    return 0


def _pack_or_error(store, pack_id):
    pack = store.get_pack(pack_id)
    if pack is None:
        raise CliError(f"no such pack: {pack_id}")
    return pack


def _check_score_refs(store, args):
    """score/rescore references must all resolve before anything writes."""
    _pack_or_error(store, args.pack)
    item_ids = {i["item_id"] for i in store.list_items(args.pack)}
    if args.item not in item_ids:
        raise CliError(f"no such item in pack {args.pack}: {args.item}")
    entries = _entry_ids(store)
    for entry_id in args.cite or []:
        if entry_id not in entries:
            raise CliError(f"no such entry: {entry_id}")


def cmd_score(args):
    store = _open_store(args.db_path)
    try:
        _check_score_refs(store, args)
        eng_id = _engagement_id(store)
        existing = store.get_coverage(args.pack, args.item)
        if existing is not None:
            raise CliError(
                f"{args.item} is already scored as {existing['status']}"
                f" in pack {args.pack}; use rescore to replace it"
            )
        store.save_coverage(
            eng_id, args.pack, args.item, args.status, args.reasoning,
            args.cite or [], args.na_reason,
        )
    finally:
        store.close()
    print(f"scored {args.item} as {args.status} in pack {args.pack}")
    return 0


def cmd_rescore(args):
    store = _open_store(args.db_path)
    try:
        _check_score_refs(store, args)
        eng_id = _engagement_id(store)
        existing = store.get_coverage(args.pack, args.item)
        if existing is None:
            raise CliError(
                f"{args.item} has no score in pack {args.pack};"
                " use score to create one"
            )
        old, _new_id = store.replace_coverage(
            eng_id, args.pack, args.item, args.status, args.reasoning,
            args.cite or [], args.na_reason,
        )
    finally:
        store.close()
    print(f"rescored {args.item} in pack {args.pack}")
    print(f"  was: {old['status']} — {old['reasoning']}")
    print(f"  now: {args.status} — {args.reasoning}")
    return 0


def cmd_list_coverage(args):
    store = _open_store(args.db_path)
    try:
        _pack_or_error(store, args.pack)
        items = store.list_pack_items(args.pack)
        scores = {s["item_id"]: s for s in store.list_coverage(args.pack)}
        tallies = store.coverage_tallies(args.pack)
    finally:
        store.close()
    for item in items:
        score = scores.get(item["item_id"])
        if score is None:
            print(f"{item['item_id']} ({item['group_name']}) not scored")
            continue
        line = f"{item['item_id']} ({item['group_name']}) {score['status']}"
        if score["cited_entry_ids"]:
            line += " — cites " + ", ".join(score["cited_entry_ids"])
        if score["na_reason"]:
            line += f" — N/A reason: {score['na_reason']}"
        print(line)
    scored = sum(tallies.values())
    parts = [f"{s} {tallies.get(s, 0)}" for s in COVERAGE_STATUSES]
    print(
        "Tallies: " + " · ".join(parts)
        + f" · not scored {len(items) - scored}"
    )
    return 0


def cmd_checklist(args):
    _refuse_out_onto_db(args)
    text = render_checklist(args.db_path, args.date or _today())
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"checklist written to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_packet(args):
    _refuse_out_onto_db(args)
    assembled_date = args.date or _today()
    text, pack = assemble_packet(
        args.db_path, pack_id=args.pack,
        word_cap=args.word_cap, assembled_date=assembled_date,
        posture=args.posture,
    )
    data = text.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    Path(args.out).write_bytes(data)
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        store.record_packet(
            eng_id, pack["pack_id"], assembled_date,
            args.word_cap, len(data), sha256, posture=args.posture,
        )
    finally:
        store.close()
    print(f"packet written to {args.out}")
    print(f"byte count: {len(data)}")
    print(f"sha256: {sha256}")
    if args.posture != "standard":
        print(f"posture: {args.posture}")
    return 0


def cmd_calibration(args):
    _refuse_out_onto_db(args)
    text = render_calibration(args.db_path, args.pack)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"calibration report written to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_fix_packet(args):
    _refuse_out_onto_db(args)
    text = render_fix_packet(args.db_path, args.fix_id)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"fix packet written to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_run_model(args, _call=None):
    """Assemble the packet, call the provider API, write the raw output.

    The packet is assembled and recorded exactly as `packet` does it
    (run_via="api", so the packet states how it was run), then the
    provider is called once and the raw output written to --out. No
    run is recorded here: the operator inspects the file and runs
    `ingest`, which is the only path into model_run. On API failure
    there is no output file and no run; the packet record stands.
    No retry, ever: a retry re-sends the packet and can
    double-charge; the operator re-runs the command.

    _call is the driver seam for tests: a callable
    (provider, model, packet_text, api_key, max_tokens) returning
    (text, input_tokens, output_tokens, skipped_thinking_blocks).
    Production passes None and the real provider dispatch is used.
    No test-only environment variable exists in shipped code.
    """
    _refuse_out_onto_db(args)
    if args.provider != "anthropic":
        raise CliError(f"unknown provider: {args.provider}")
    model_label = f"anthropic/{args.model}"
    assembled_date = args.date or _today()
    if not args.dry_run:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or ""
        if not api_key:
            raise CliError("ANTHROPIC_API_KEY is not set")
    text, pack = assemble_packet(
        args.db_path, pack_id=args.pack, word_cap=args.word_cap,
        assembled_date=assembled_date, run_via="api",
        model_label=model_label,
    )
    data = text.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    if args.dry_run:
        print("dry run: no request sent, no file written, no packet recorded")
        print("url: https://api.anthropic.com/v1/messages")
        print(f"model: {args.model}")
        print(f"max_tokens: {args.max_output_tokens}")
        print(f"packet byte count: {len(data)}")
        print(f"packet sha256: {sha256}")
        print("headers: x-api-key, anthropic-version, content-type")
        return 0
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        store.record_packet(
            eng_id, pack["pack_id"], assembled_date,
            args.word_cap, len(data), sha256,
        )
    finally:
        store.close()
    call = _call if _call is not None else call_provider
    output, input_tokens, output_tokens, skipped = call(
        args.provider, args.model, text, api_key, args.max_output_tokens
    )
    Path(args.out).write_text(output, encoding="utf-8")
    print(f"model output written to {args.out}")
    print(f"packet sha256: {sha256}")
    print(f"packet byte count: {len(data)}")
    print(f"output byte count: {len(output.encode('utf-8'))}")
    if skipped > 0:
        noun = "block" if skipped == 1 else "blocks"
        print(f"note: skipped {skipped} thinking {noun}")
    print(f"input tokens: {input_tokens}")
    print(f"output tokens: {output_tokens}")
    print("To record this output as a run:")
    print(
        f"fencewalk ingest {args.db_path} {args.out}"
        f" --packet-hash {sha256} --model {model_label}"
    )
    return 0


def cmd_ingest(args):
    raw_bytes = Path(args.output_file).read_bytes()
    raw_output = raw_bytes.decode("utf-8")
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        if store.get_packet_by_hash(args.packet_hash) is None:
            raise CliError(
                f"no recorded packet with hash: {args.packet_hash}"
            )
        run_id = store.record_run(
            eng_id, args.packet_hash, args.model or "not stated",
            args.date or _today(), raw_output,
        )
    finally:
        store.close()
    print(f"ingested model run {run_id}")
    print(f"packet hash: {args.packet_hash}")
    print(f"output byte count: {len(raw_bytes)}")
    return 0


def cmd_draft(args):
    _refuse_out_onto_db(args)
    text = render_draft(args.db_path, args.run)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"draft written to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def _rubric_pack_or_error(store, pack_id):
    """Resolve the pack that rubric citations are validated against:
    the --pack choice, else the tool-wide default (the engagement's
    primary pack, else the alphabetically-first loaded pack;
    Store.default_pack_id)."""
    if pack_id is None:
        pack_id = store.default_pack_id()
        if pack_id is None:
            raise CliError(
                "database holds no rubric pack; load one with load-pack"
            )
    _pack_or_error(store, pack_id)
    return pack_id


def _check_rubric_item(store, pack_id, item_id):
    item_ids = {i["item_id"] for i in store.list_items(pack_id)}
    if item_id not in item_ids:
        raise CliError(f"no such item in pack {pack_id}: {item_id}")


def cmd_adjudicate(args):
    if args.decision == "correct" and not args.note:
        raise CliError(
            "--decision correct requires --note;"
            " the note is the correction, preserved in the record"
        )
    store = _open_store(args.db_path)
    try:
        if store.get_run(args.run) is None:
            raise CliError(f"no such run: {args.run}")
        event_id = store.record_adjudication(
            args.run, args.section, args.decision, args.note,
            args.date or _today(), args.actor,
        )
    finally:
        store.close()
    print(
        f"recorded adjudication event {event_id}"
        f" (run {args.run}, {args.section}, {args.decision})"
    )
    return 0


def cmd_adjudications(args):
    store = _open_store(args.db_path)
    try:
        if store.get_run(args.run) is None:
            raise CliError(f"no such run: {args.run}")
        events = store.list_adjudications(args.run)
    finally:
        store.close()
    for event in events:
        print(
            f"{event['section']}: {event['decision']}"
            f" ({event['date']}, {event['actor']})"
        )
        if event["note"]:
            print(f"  note: {event['note']}")
    current = {}
    for event in events:
        current[event["section"]] = event
    print("Current standings:")
    for section in ADJUDICATION_SECTIONS:
        event = current.get(section)
        if event is None:
            print(f"{section}: no decision recorded")
        else:
            print(f"{section}: {event['decision']}")
    return 0


def cmd_record_probe(args):
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        # Every reference resolves before anything writes.
        _pack_or_error(store, args.pack)
        _check_rubric_item(store, args.pack, args.item)
        probe_id = store.record_probe(
            eng_id, args.pack, args.item, args.method, args.outcome,
            args.date or _today(), args.actor,
        )
    finally:
        store.close()
    print(
        f"recorded probe {probe_id}"
        f" ({args.item}, {args.outcome}); scores are unchanged"
    )
    return 0


def cmd_probes(args):
    sys.stdout.write(render_probes(args.db_path, args.pack, args.unprobed))
    return 0


def cmd_add_chain(args):
    if not args.step:
        raise CliError("at least one --step is required")
    steps = []
    for raw in args.step:
        phase, sep, text = raw.partition(":")
        if not sep or not phase.strip() or not text.strip():
            raise CliError(f"step must be '<phase>: <text>': {raw}")
        steps.append({"phase": phase.strip(), "text": text.strip()})
    step_items = _parse_step_items(args.step_item or [], len(steps))
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        keys = {c["chain_key"] for c in store.list_chains()}
        if args.key in keys:
            raise CliError(f"duplicate chain key: {args.key}")
        control_pack = None
        if args.control_rubric is not None:
            control_pack = _rubric_pack_or_error(store, args.pack)
            _check_rubric_item(store, control_pack, args.control_rubric)
        if step_items:
            # Resolved exactly as --control-rubric resolves it.
            item_pack = _rubric_pack_or_error(store, args.pack)
            for step_no, item_id in sorted(step_items.items()):
                _check_rubric_item(store, item_pack, item_id)
                steps[step_no - 1]["item_id"] = item_id
                steps[step_no - 1]["item_pack"] = item_pack
        store.add_chain(
            eng_id, args.key, args.name, steps,
            args.control, args.control_status, args.control_rubric,
            control_pack=control_pack,
        )
    finally:
        store.close()
    if step_items:
        print(
            f"added chain {args.key} ({len(steps)} steps,"
            f" {len(step_items)} naming"
            f" {'a rubric item' if len(step_items) == 1 else 'rubric items'})"
        )
    else:
        print(f"added chain {args.key} ({len(steps)} steps)")
    return 0


def _parse_step_items(raw_mappings, step_count):
    """--step-item values as {step_no: item_id}, refused before the
    database is opened: '<step_no>=<item_id>', 1-based, naming a step
    this command creates, each step at most once."""
    mapping = {}
    for raw in raw_mappings:
        number, sep, item_id = raw.partition("=")
        number, item_id = number.strip(), item_id.strip()
        if not sep or not item_id or not number.isdigit():
            raise CliError(f"step item must be '<step_no>=<item_id>': {raw}")
        step_no = int(number)
        if not 1 <= step_no <= step_count:
            raise CliError(
                f"--step-item names step {step_no}, but the chain has"
                f" {step_count} step{'s' if step_count != 1 else ''}"
            )
        if step_no in mapping:
            raise CliError(f"--step-item names step {step_no} twice")
        mapping[step_no] = item_id
    return mapping


def cmd_set_step_item(args):
    store = _open_store(args.db_path)
    try:
        chain = next(
            (c for c in store.list_chains() if c["chain_key"] == args.chain),
            None,
        )
        if chain is None:
            raise CliError(f"no such chain: {args.chain}")
        if args.step not in {s["step_no"] for s in chain["steps"]}:
            raise CliError(f"chain {args.chain} has no step {args.step}")
        if args.clear:
            item_id = item_pack = None
        else:
            item_pack = _rubric_pack_or_error(store, args.pack)
            _check_rubric_item(store, item_pack, args.item)
            item_id = args.item
        was_item, was_pack = store.set_chain_step_item(
            args.chain, args.step, item_id, item_pack,
        )
    finally:
        store.close()
    was = f"{was_item} ({was_pack})" if was_item is not None else "none"
    now = f"{item_id} ({item_pack})" if item_id is not None else "none"
    print(f"chain {args.chain} step {args.step}: item {now} (was {was})")
    return 0


def cmd_chains(args):
    sys.stdout.write(render_chains(args.db_path))
    return 0


def cmd_add_fix(args):
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        ids = {f["fix_id"] for f in store.list_fixes()}
        if args.id in ids:
            raise CliError(f"duplicate fix id: {args.id}")
        rubric = args.rubric or []
        pack_id = None
        if rubric:
            pack_id = _rubric_pack_or_error(store, args.pack)
            for item_id in rubric:
                _check_rubric_item(store, pack_id, item_id)
        store.add_fix(
            eng_id, args.id, args.action, args.effort, args.breaks,
            rubric, status="proposed",
            status_date=args.date or _today(), status_actor=args.actor,
            rubric_pack_id=pack_id,
        )
    finally:
        store.close()
    print(f"added fix {args.id} (proposed)")
    return 0


def cmd_set_fix_status(args):
    store = _open_store(args.db_path)
    try:
        store.set_fix_status(
            args.fix_id, args.status,
            date=args.date or _today(), actor=args.actor,
        )
    finally:
        store.close()
    print(f"{args.fix_id} status set to {args.status}")
    return 0


def cmd_list_fixes(args):
    store = _open_store(args.db_path)
    try:
        fixes = store.list_fixes()
        counts = store.fix_status_counts()
    finally:
        store.close()
    for fix in fixes:
        rubric = (
            ", ".join(fix["rubric_item_ids"]) if fix["rubric_item_ids"]
            else "—"
        )
        print(
            f"{fix['fix_id']} [{fix['status']}] {fix['action']}"
            f" — rubric {rubric} · effort {fix['effort']}"
            f" · breaks {fix['chains_broken']}"
        )
    parts = [f"{s} {counts.get(s, 0)}" for s in FIX_STATUSES]
    print("Tallies: " + " · ".join(parts))
    return 0


def cmd_add_verify_next(args):
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        existing = store.list_verify_next()
        seq = max((item["seq"] for item in existing), default=0) + 1
        store.add_verify_next(
            eng_id, seq, args.unknown, args.why, args.check
        )
    finally:
        store.close()
    print(f"added verify-next item {seq}")
    return 0


def cmd_serve(args):
    if not Path(args.db_path).exists():
        raise CliError(f"no such database: {args.db_path}")
    serve(args.db_path, args.host, args.port)
    return 0


def cmd_register(args):
    subject = register(args.db_path, registry_path(args.registry))
    print(f"registered: {subject}")
    return 0


def cmd_unregister(args):
    unregister(args.db_path, registry_path(args.registry))
    print(f"unregistered: {args.db_path}")
    return 0


def cmd_engagements(args):
    rows = engagements(registry_path(args.registry))
    if not rows:
        print("no engagements registered")
        return 0
    print("SUBJECT · NAME · CREATED · DEFAULT PACK · PACKS · ENTRIES · SCORED")
    for row in rows:
        if row.get("missing"):
            print(f"MISSING · {row['path']}")
        else:
            print(" · ".join(str(row[key]) if row[key] is not None else "—"
                             for key in ("subject", "name", "created", "default_pack",
                                         "packs", "entries", "scored")))
    return 0


def cmd_import_inventory(args):
    store = _open_store(args.db_path)
    try:
        eng_id = _engagement_id(store)
        report = import_inventory(
            store, eng_id, args.markdown_file,
            date=args.date or _today(), actor=args.actor,
        )
    finally:
        store.close()
    sys.stdout.write(format_import_report(report))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="fencewalk")
    parser.add_argument(
        "--version", action="version", version=f"fencewalk {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for command, handler, help_text in (
        ("register", cmd_register, "register an engagement database path"),
        ("unregister", cmd_unregister, "remove a registered database path"),
        ("engagements", cmd_engagements, "list registered engagements and live counts"),
    ):
        p_registry = sub.add_parser(command, help=help_text)
        if command != "engagements":
            p_registry.add_argument("db_path")
        p_registry.add_argument(
            "--registry", help="registry JSON path (overrides FENCEWALK_REGISTRY; default: ~/.fencewalk/registry.json)"
        )
        p_registry.set_defaults(func=handler)

    p_load = sub.add_parser("load-fixture", help="build an engagement database from a fixture directory")
    p_load.add_argument("fixture_dir")
    p_load.add_argument("db_path")
    p_load.add_argument(
        "--pack-root", action="append", default=[],
        help="allow fixture pack files under this directory (repeatable)",
    )
    p_load.set_defaults(func=cmd_load_fixture)

    p_report = sub.add_parser("report", help="render the Markdown engagement report from a database")
    p_report.add_argument("db_path")
    p_report.add_argument("--pack", help="rubric pack id (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_report.add_argument("--out", help="write the report to this file instead of stdout")
    p_report.set_defaults(func=cmd_report)

    p_pdf = sub.add_parser("pdf", help="render the engagement report as a PDF file")
    p_pdf.add_argument("db_path")
    p_pdf.add_argument("--out", required=True, help="write the PDF to this file")
    p_pdf.add_argument("--pack", help="rubric pack id (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_pdf.set_defaults(func=cmd_pdf)

    p_diff = sub.add_parser("diff", help="render a Markdown drift report between two copies of one engagement database (read-only)")
    p_diff.add_argument("older", help="the earlier copy (for example, taken before a re-audit)")
    p_diff.add_argument("newer", help="the current database")
    p_diff.add_argument("--pack", help="rubric pack id to compare (default: the newer database's primary pack, else its alphabetically-first loaded pack)")
    p_diff.add_argument("--out", help="write the drift report to this file instead of stdout")
    p_diff.set_defaults(func=cmd_diff)

    p_new = sub.add_parser("new", help="create a fresh engagement database")
    p_new.add_argument("db_path")
    p_new.add_argument("--name", required=True)
    p_new.add_argument("--subject", required=True)
    p_new.add_argument("--method-order", required=True, choices=list(METHOD_ORDERS))
    p_new.add_argument("--date", help="engagement creation date, YYYY-MM-DD (default: today)")
    p_new.set_defaults(func=cmd_new)

    p_add = sub.add_parser("add-entry", help="add an inventory entry")
    p_add.add_argument("db_path")
    p_add.add_argument("--section", required=True, choices=SECTIONS)
    p_add.add_argument("--body", required=True)
    p_add.add_argument("--label", required=True, choices=list(EVIDENCE_LABELS))
    p_add.add_argument("--source", required=True)
    p_add.add_argument("--id", help="entry ID (default: next free ID in the section)")
    p_add.add_argument("--checked-date")
    p_add.add_argument("--decay-date")
    p_add.add_argument("--date", help="date recorded for this change (default: today)")
    p_add.add_argument("--actor", default="operator")
    p_add.set_defaults(func=cmd_add_entry)

    p_edit = sub.add_parser("edit-entry", help="edit an entry's body, source, or dates (never its label)")
    p_edit.add_argument("db_path")
    p_edit.add_argument("entry_id")
    p_edit.add_argument("--body")
    p_edit.add_argument("--source")
    p_edit.add_argument("--checked-date")
    p_edit.add_argument("--decay-date")
    p_edit.add_argument("--clear-checked-date", action="store_true")
    p_edit.add_argument("--clear-decay-date", action="store_true")
    p_edit.set_defaults(func=cmd_edit_entry)

    p_label = sub.add_parser("set-label", help="change an entry's evidence label (recorded in history)")
    p_label.add_argument("db_path")
    p_label.add_argument("entry_id")
    p_label.add_argument("label", choices=list(EVIDENCE_LABELS))
    p_label.add_argument("--date", help="date recorded for this change (default: today)")
    p_label.add_argument("--actor", default="operator")
    p_label.set_defaults(func=cmd_set_label)

    p_list = sub.add_parser("list-entries", help="list inventory entries (read-only)")
    p_list.add_argument("db_path")
    p_list.add_argument("--section", choices=SECTIONS)
    p_list.set_defaults(func=cmd_list_entries)

    p_import = sub.add_parser("import-inventory", help="import a bundle-format Markdown inventory into an empty inventory")
    p_import.add_argument("db_path")
    p_import.add_argument("markdown_file")
    p_import.add_argument("--date", help="date recorded for the import (default: today)")
    p_import.add_argument("--actor", default="operator")
    p_import.set_defaults(func=cmd_import_inventory)

    p_pack = sub.add_parser("load-pack", help="validate and load a rubric pack file into a database")
    p_pack.add_argument("db_path")
    p_pack.add_argument("pack_file")
    p_pack.set_defaults(func=cmd_load_pack)

    p_primary = sub.add_parser("set-primary-pack", help="record a loaded pack as the engagement's primary pack (the default when no --pack is given)")
    p_primary.add_argument("db_path")
    p_primary.add_argument("pack_id")
    p_primary.set_defaults(func=cmd_set_primary_pack)

    p_packs = sub.add_parser("packs", help="list the rubric packs shipped with the tool (read-only)")
    p_packs.set_defaults(func=cmd_packs)

    for name, func, helptext in (
        ("score", cmd_score,
         "score one rubric item (refuses if the item is already scored; see rescore)"),
        ("rescore", cmd_rescore,
         "replace an existing score for one rubric item (refuses if unscored; see score)"),
    ):
        p_sc = sub.add_parser(name, help=helptext)
        p_sc.add_argument("db_path")
        p_sc.add_argument("--pack", required=True)
        p_sc.add_argument("--item", required=True)
        p_sc.add_argument("--status", required=True, choices=list(COVERAGE_STATUSES))
        p_sc.add_argument("--reasoning", required=True)
        p_sc.add_argument("--cite", action="append", metavar="ENTRY_ID",
                          help="inventory entry cited by this score (repeatable)")
        p_sc.add_argument("--na-reason", help="written N/A reason (required for Not applicable)")
        p_sc.set_defaults(func=func)

    p_cov = sub.add_parser("list-coverage", help="list every pack item with its score, or 'not scored' (read-only)")
    p_cov.add_argument("db_path")
    p_cov.add_argument("--pack", required=True)
    p_cov.set_defaults(func=cmd_list_coverage)

    p_check = sub.add_parser("checklist", help="render the verification checklist: UNKNOWN entries plus decayed evidence (read-only, derived)")
    p_check.add_argument("db_path")
    p_check.add_argument("--date", help="as-of date, YYYY-MM-DD (default: today)")
    p_check.add_argument("--out", help="write the checklist to this file instead of stdout")
    p_check.set_defaults(func=cmd_checklist)

    p_packet = sub.add_parser("packet", help="assemble the self-contained model-run packet (brief + inventory + rubric) and record its hash")
    p_packet.add_argument("db_path")
    p_packet.add_argument("--out", required=True, help="write the packet to this file")
    p_packet.add_argument("--pack", help="rubric pack id (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_packet.add_argument("--word-cap", type=int, default=2500, help="word cap stated in the run brief (default: 2500)")
    p_packet.add_argument("--date", help="assembled date, YYYY-MM-DD (default: today)")
    p_packet.add_argument("--posture", choices=list(PACKET_POSTURES), default="standard", help="standard (default): the run brief, scoring blind; adversarial: a second pass that attacks the standing scores (brief, standing coverage, inventory, rubric)")
    p_packet.set_defaults(func=cmd_packet)

    p_fixpk = sub.add_parser("fix-packet", help="render one fix's packet: its status history, mapped rubric items with coverage and cited entries, and the rescore list (read-only; records nothing)")
    p_fixpk.add_argument("db_path")
    p_fixpk.add_argument("fix_id")
    p_fixpk.add_argument("--out", help="write the fix packet to this file instead of stdout")
    p_fixpk.set_defaults(func=cmd_fix_packet)

    p_calib = sub.add_parser("calibration", help="render the calibration report: coverage-adjudicated model runs' proposals against today's standing scores, by group, posture and run (read-only)")
    p_calib.add_argument("db_path")
    p_calib.add_argument("--pack", help="rubric pack id to compare (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_calib.add_argument("--out", help="write the calibration report to this file instead of stdout")
    p_calib.set_defaults(func=cmd_calibration)

    p_run = sub.add_parser("run-model", help="assemble the packet, call a model provider API with your own key, and write the raw output (records the packet; ingest records the run)")
    p_run.add_argument("db_path")
    p_run.add_argument("--provider", required=True, help="model provider (only anthropic in this slice)")
    p_run.add_argument("--model", required=True, help="model id, as named by the operator (recorded as anthropic/<model-id>)")
    p_run.add_argument("--out", required=True, help="write the model's raw text output to this file")
    p_run.add_argument("--pack", help="rubric pack id (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_run.add_argument("--word-cap", type=int, default=2500, help="word cap stated in the run brief (default: 2500)")
    p_run.add_argument("--max-output-tokens", type=int, default=16384, help="max output tokens requested from the provider (default: 16384)")
    p_run.add_argument("--date", help="assembled date, YYYY-MM-DD (default: today)")
    p_run.add_argument("--dry-run", action="store_true", help="print the request that would be sent and exit without sending, writing, or recording")
    p_run.set_defaults(func=cmd_run_model)

    p_ingest = sub.add_parser("ingest", help="store a model run's output verbatim against a recorded packet hash (changes nothing else)")
    p_ingest.add_argument("db_path")
    p_ingest.add_argument("output_file")
    p_ingest.add_argument("--packet-hash", required=True, help="SHA-256 of the packet this output answers")
    p_ingest.add_argument("--model", help="model label, as stated by the operator (default: recorded as 'not stated')")
    p_ingest.add_argument("--date", help="run date, YYYY-MM-DD (default: today)")
    p_ingest.set_defaults(func=cmd_ingest)

    p_draft = sub.add_parser("draft", help="render the adjudication draft for one stored model run (read-only)")
    p_draft.add_argument("db_path")
    p_draft.add_argument("--run", required=True, type=int, help="model run id")
    p_draft.add_argument("--out", help="write the draft to this file instead of stdout")
    p_draft.set_defaults(func=cmd_draft)

    p_adj = sub.add_parser("adjudicate", help="record one adjudication decision event for a model run (append-only; a decision applies nothing by itself)")
    p_adj.add_argument("db_path")
    p_adj.add_argument("--run", required=True, type=int, help="model run id")
    p_adj.add_argument("--section", required=True, choices=list(ADJUDICATION_SECTIONS))
    p_adj.add_argument("--decision", required=True, choices=list(ADJUDICATION_DECISIONS))
    p_adj.add_argument("--note", help="note (required for --decision correct: the note is the correction)")
    p_adj.add_argument("--date", help="decision date, YYYY-MM-DD (default: today)")
    p_adj.add_argument("--actor", default="operator")
    p_adj.set_defaults(func=cmd_adjudicate)

    p_adjs = sub.add_parser("adjudications", help="list a run's adjudication events and current standings (read-only)")
    p_adjs.add_argument("db_path")
    p_adjs.add_argument("--run", required=True, type=int, help="model run id")
    p_adjs.set_defaults(func=cmd_adjudications)

    p_probe = sub.add_parser("record-probe", help="record one behavioral verification probe of a rubric item (append-only; a probe never changes a score)")
    p_probe.add_argument("db_path")
    p_probe.add_argument("--pack", required=True)
    p_probe.add_argument("--item", required=True)
    p_probe.add_argument("--method", required=True, help="what was done: the behavior exercised")
    p_probe.add_argument("--outcome", required=True, choices=list(PROBE_OUTCOMES))
    p_probe.add_argument("--date", help="probe date, YYYY-MM-DD (default: today)")
    p_probe.add_argument("--actor", default="operator")
    p_probe.set_defaults(func=cmd_record_probe)

    p_probes = sub.add_parser("probes", help="list each probed item's latest probe, or with --unprobed the Covered/Partial items with no probe on record (read-only)")
    p_probes.add_argument("db_path")
    p_probes.add_argument("--pack", help="rubric pack id (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_probes.add_argument("--unprobed", action="store_true", help="list the Covered and Partial items with no probe on record instead")
    p_probes.set_defaults(func=cmd_probes)

    p_chain = sub.add_parser("add-chain", help="record one attack chain (applying an adjudicated deliverable, by hand)")
    p_chain.add_argument("db_path")
    p_chain.add_argument("--key", required=True)
    p_chain.add_argument("--name", required=True)
    p_chain.add_argument("--control", required=True, help="the earliest breaking control")
    p_chain.add_argument("--control-status", required=True, choices=["present", "absent", "unknown"])
    p_chain.add_argument("--control-rubric", help="rubric item id naming the control (validated against the pack)")
    p_chain.add_argument("--pack", help="rubric pack id for --control-rubric and --step-item validation (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_chain.add_argument("--step", action="append", metavar="STEP", help="'<phase>: <text>' (repeatable; at least one required)")
    p_chain.add_argument("--step-item", action="append", metavar="N=ITEM", help="'<step_no>=<item_id>': the rubric item step N (1-based) exercises (repeatable; validated against the pack)")
    p_chain.set_defaults(func=cmd_add_chain)

    p_stepitem = sub.add_parser("set-step-item", help="name (or --clear) the rubric item one step of an existing chain exercises")
    p_stepitem.add_argument("db_path")
    p_stepitem.add_argument("--chain", required=True, help="chain key")
    p_stepitem.add_argument("--step", required=True, type=int, help="step number (1-based)")
    which = p_stepitem.add_mutually_exclusive_group(required=True)
    which.add_argument("--item", help="rubric item id the step exercises (validated against the pack)")
    which.add_argument("--clear", action="store_true", help="remove the step's item reference")
    p_stepitem.add_argument("--pack", help="rubric pack id for --item validation (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_stepitem.set_defaults(func=cmd_set_step_item)

    p_chains = sub.add_parser("chains", help="list every chain with its steps' rubric items and standing statuses, its computed exposure (interrupted / contested / open, or not computed), and related fixes (read-only)")
    p_chains.add_argument("db_path")
    p_chains.set_defaults(func=cmd_chains)

    p_fix = sub.add_parser("add-fix", help="record one fix in status 'proposed' (applying an adjudicated deliverable, by hand)")
    p_fix.add_argument("db_path")
    p_fix.add_argument("--id", required=True)
    p_fix.add_argument("--action", required=True)
    p_fix.add_argument("--effort", required=True)
    p_fix.add_argument("--breaks", required=True, help="the chain(s) this fix breaks")
    p_fix.add_argument("--rubric", action="append", metavar="ITEM_ID", help="rubric item cited by this fix (repeatable; validated against the pack)")
    p_fix.add_argument("--pack", help="rubric pack id for --rubric validation (default: the engagement's primary pack, else the alphabetically-first loaded pack)")
    p_fix.add_argument("--date", help="creation date, YYYY-MM-DD (default: today)")
    p_fix.add_argument("--actor", default="operator")
    p_fix.set_defaults(func=cmd_add_fix)

    p_fixst = sub.add_parser("set-fix-status", help="change a fix's status (the only path; history recorded; same-status refused)")
    p_fixst.add_argument("db_path")
    p_fixst.add_argument("fix_id")
    p_fixst.add_argument("status", choices=list(FIX_STATUSES))
    p_fixst.add_argument("--date", help="status date, YYYY-MM-DD (default: today)")
    p_fixst.add_argument("--actor", default="operator")
    p_fixst.set_defaults(func=cmd_set_fix_status)

    p_fixes = sub.add_parser("list-fixes", help="list every fix with its status and per-status tallies (read-only)")
    p_fixes.add_argument("db_path")
    p_fixes.set_defaults(func=cmd_list_fixes)

    p_vn = sub.add_parser("add-verify-next", help="append one verify-next item (the next sequence number is assigned)")
    p_vn.add_argument("db_path")
    p_vn.add_argument("--unknown", required=True)
    p_vn.add_argument("--why", required=True)
    p_vn.add_argument("--check", required=True)
    p_vn.set_defaults(func=cmd_add_verify_next)

    p_serve = sub.add_parser("serve", help="serve the web interface for one engagement database")
    p_serve.add_argument("db_path")
    p_serve.add_argument("--host", default="127.0.0.1", help="address to bind (default: 127.0.0.1; any other value prints a no-authentication warning)")
    p_serve.add_argument("--port", type=int, default=8090, help="port to bind (default: 8090)")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (CliError, InvariantError, FileExistsError, OSError,
            sqlite3.Error, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
