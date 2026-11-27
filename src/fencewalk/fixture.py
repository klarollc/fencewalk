"""Fixture loading: build a fresh engagement database entirely from files.

A fixture directory holds JSON data files (documented in the fixture's own
README): engagement.json, inventory.json, coverage.json, chains.json,
fixes.json, verify_next.json. engagement.json names the rubric pack file
(pack_file, resolved relative to the fixture directory) and, optionally,
further packs to load beside it (extra_pack_files, same resolution), so a
chain (control_pack) or a fix (rubric_pack_id) can cite another pack.
The pack_file pack is recorded as the engagement's primary pack, so the
default render is the fixture's own pack, whatever the other packs are
called.
"""

import importlib.resources as resources
import json
from pathlib import Path

from .store import Store


def load_pack(pack_path):
    with open(pack_path, encoding="utf-8") as f:
        return json.load(f)


def validate_pack(pack):
    """Raise ValueError unless the pack is structurally sound.

    The pack must name a pack_id, a title, a source citation, and a
    version (all present and non-empty), and carry a non-empty items
    list whose IDs are unique and whose every item has an item_id, a
    group, and text (all non-empty). This is the one pack validator:
    fixture loading and the load-pack command both go through it.
    """
    if not isinstance(pack, dict):
        raise ValueError("rubric pack is not a JSON object")
    for field in ("pack_id", "title", "version"):
        if not pack.get(field) or not str(pack[field]).strip():
            raise ValueError(f"rubric pack has no {field}")
    if not pack.get("source_citation") or not str(pack["source_citation"]).strip():
        raise ValueError("rubric pack has no source citation")
    items = pack.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("rubric pack has no items")
    ids = []
    for item in items:
        if not isinstance(item, dict) or not item.get("item_id"):
            raise ValueError("rubric item has no item_id")
        if not item.get("group") or not str(item["group"]).strip():
            raise ValueError(f"rubric item {item['item_id']} lacks a group")
        if not item.get("text") or not str(item["text"]).strip():
            raise ValueError(f"rubric item {item['item_id']} lacks text")
        ids.append(item["item_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("rubric pack has duplicate item IDs")
    return pack


def _bundled_names(subdir):
    """Filenames shipped under the package's bundled data directory."""
    return sorted(p.name for p in resources.files("fencewalk").joinpath(subdir).iterdir())


def bundled_data_path(subdir, filename):
    """A bundled data file as a filesystem path.

    In a checkout, an editable install, or an installed wheel the
    package lives on the filesystem and the traversable is already a
    Path. The as_file fallback covers loaders that keep the package
    elsewhere (a zipped import); pip installs wheels unpacked, so
    that branch is a fallback only.
    """
    target = resources.files("fencewalk").joinpath(subdir, filename)
    if isinstance(target, Path):
        return target
    with resources.as_file(target) as fp:
        return Path(fp)


def bundled_pack_names():
    """The pack filenames shipped with the tool (e.g. flash-....json)."""
    return _bundled_names("packs")


def bundled_fixture_names():
    """The fixture directory names shipped with the tool."""
    return _bundled_names("fixtures")


def bundled_pack_path(name):
    """Resolve a pack argument to a filesystem path.

    An existing filesystem path loads as a path (today's behavior).
    Otherwise the name matches a bundled pack filename with or
    without the .json suffix — which equals the pack_id for every
    pack the tool ships. Anything else is a clean error naming the
    argument and listing the bundled packs available.
    """
    candidate = Path(name)
    if candidate.exists():
        return candidate
    filenames = bundled_pack_names()
    stem = name[:-5] if name.endswith(".json") else name
    for filename in filenames:
        if name == filename or stem == filename[:-5]:
            return bundled_data_path("packs", filename)
    available = ", ".join(f[:-5] for f in filenames)
    raise ValueError(f"no such pack: {name} (bundled packs: {available})")


def bundled_fixture_dir(name):
    """Resolve a fixture argument to a filesystem directory.

    An existing directory path loads as a directory (today's
    behavior). Otherwise the name matches a bundled fixture
    directory. Anything else is a clean error naming the argument
    and listing the bundled fixtures available.
    """
    candidate = Path(name)
    if candidate.is_dir():
        return candidate
    names = bundled_fixture_names()
    if name in names:
        return bundled_data_path("fixtures", name)
    available = ", ".join(names)
    raise ValueError(f"no such fixture: {name} (bundled fixtures: {available})")


def _read_json(fixture_dir, name):
    with open(Path(fixture_dir) / name, encoding="utf-8") as f:
        return json.load(f)


def load_fixture(fixture_dir, db_path):
    """Build a fresh engagement database at db_path from a fixture directory.

    Returns the engagement id. Refuses to overwrite an existing database.
    """
    fixture_dir = Path(fixture_dir)
    db_path = Path(db_path)
    if db_path.exists():
        raise FileExistsError(f"database already exists: {db_path}")

    engagement = _read_json(fixture_dir, "engagement.json")
    pack = validate_pack(load_pack(fixture_dir / engagement["pack_file"]))
    extra_packs = [
        validate_pack(load_pack(fixture_dir / extra))
        for extra in engagement.get("extra_pack_files", [])
    ]
    inventory = _read_json(fixture_dir, "inventory.json")
    coverage = _read_json(fixture_dir, "coverage.json")
    chains = _read_json(fixture_dir, "chains.json")
    fixes = _read_json(fixture_dir, "fixes.json")
    verify_next = _read_json(fixture_dir, "verify_next.json")

    # Cross-pack citations: a chain's control_pack or a fix's
    # rubric_pack_id overrides the primary pack, and must name a pack
    # this fixture loads. The store accepts any pack id silently, so
    # this check is the guard; it runs before the database is created.
    loaded_ids = {pack["pack_id"]} | {p["pack_id"] for p in extra_packs}
    for chain in chains["chains"]:
        if "control_pack" in chain:
            if not chain.get("control_rubric"):
                raise ValueError(
                    f"chain {chain['chain_key']}: control_pack without control_rubric"
                )
            if chain["control_pack"] not in loaded_ids:
                raise ValueError(
                    f"chain {chain['chain_key']}: unknown pack {chain['control_pack']}"
                )
    for fix in fixes["fixes"]:
        if "rubric_pack_id" in fix and fix["rubric_pack_id"] not in loaded_ids:
            raise ValueError(
                f"fix {fix['fix_id']}: unknown pack {fix['rubric_pack_id']}"
            )

    store = Store(db_path)
    try:
        store.init_schema()
        eng_id = store.create_engagement(
            engagement["name"],
            engagement["subject_label"],
            engagement["created_date"],
            engagement["method_order"],
        )
        store.add_pack(pack)
        for extra in extra_packs:
            store.add_pack(extra)
        store.set_primary_pack(pack["pack_id"])
        for entry in inventory["entries"]:
            store.add_inventory_entry(
                eng_id,
                entry["entry_id"],
                entry["section"],
                entry["body"],
                entry["label"],
                entry["source"],
                entry.get("checked_date"),
                entry.get("decay_date"),
                date=engagement["created_date"],
                actor="fixture",
            )
        for row in coverage["scores"]:
            store.save_coverage(
                eng_id,
                pack["pack_id"],
                row["item_id"],
                row["status"],
                row["reasoning"],
                row.get("cited_entry_ids", []),
                row.get("na_reason"),
            )
        for chain in chains["chains"]:
            store.add_chain(
                eng_id,
                chain["chain_key"],
                chain["name"],
                chain["steps"],
                chain["earliest_control"],
                chain["control_status"],
                chain.get("control_rubric"),
                control_pack=(
                    chain.get("control_pack", pack["pack_id"])
                    if chain.get("control_rubric") else None
                ),
            )
        for fix in fixes["fixes"]:
            store.add_fix(
                eng_id,
                fix["fix_id"],
                fix["action"],
                fix["effort"],
                fix["chains_broken"],
                fix.get("rubric_item_ids", []),
                status=fix["status"],
                status_date=fix["status_date"],
                status_actor=fix["status_actor"],
                rubric_pack_id=fix.get("rubric_pack_id", pack["pack_id"]),
            )
        for item in verify_next["items"]:
            store.add_verify_next(
                eng_id, item["seq"], item["unknown"], item["why"], item["cheapest_check"]
            )
    finally:
        store.close()
    return eng_id
