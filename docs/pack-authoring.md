# Authoring a rubric pack

A rubric pack is a single JSON file of requirements that Fencewalk
scores an engagement against. Packs are data, not code: the tool
ships eight in `src/fencewalk/packs/`, loads any of them into an
engagement database with `load-pack`, and never runs anything from a
pack. This guide specifies the format completely, so you can write a
pack for a framework the tool does not ship — and have it load the
first time.

## The format

A pack is one JSON object with exactly five top-level keys:

```json
{
  "pack_id": "example-perimeter-basics-1.0",
  "title": "Example — Perimeter Basics (fictional worked example)",
  "version": "1.0",
  "source_citation": "Worked example for the pack authoring guide; the requirements are illustrative, not a published framework.",
  "items": [
    {"group": "Identity", "item_id": "EX-ID-01", "text": "Phishing-resistant MFA is enforced for all administrator accounts."},
    {"group": "Identity", "item_id": "EX-ID-02", "text": "Legacy authentication protocols are blocked."},
    {"group": "Mail", "item_id": "EX-MAIL-01", "text": "DMARC is enforced at p=reject for the primary domain."}
  ]
}
```

Each item has exactly three keys:

- `item_id` — the item's stable identifier, unique within the pack.
- `group` — the display grouping the item belongs to.
- `text` — the requirement statement itself.

## The rules the loader enforces

`load-pack` validates the whole file before inserting anything; on
any failure it reports a clean error and inserts nothing. The rules
(the validator is `validate_pack` in `src/fencewalk/fixture.py`):

- The pack is a JSON object.
- `pack_id`, `title`, and `version` are present and non-empty.
- `source_citation` is present and non-empty.
- `items` is a non-empty list.
- Every item has an `item_id`, a non-empty `group`, and a non-empty
  `text`.
- Item IDs are unique within the pack.

A database refuses a second pack whose `pack_id` it already holds.
Two packs with different ids can live in one database side by side,
and a report renders one pack at a time.

## What the store keeps — and what it drops

The store inserts only the five top-level fields and, per item, only
`item_id`, `group`, and `text`. The validator does not reject extra
keys, but they are never stored and never rendered: extra keys are
dead data. If a fact about an item matters, it belongs in the item's
`text` (the SCuBA pack's ` License: ` suffix, below, is exactly this)
or in the pack's `source_citation` — not in a key of your own.

## Item IDs

Scores, fixes, and chains all cite items by `item_id`, so an id is a
commitment:

- Never reuse an id for a different requirement, and never change an
  item's id once the pack is in use — the scores recorded against the
  old id do not follow it.
- Coverage lists and reports order items by `item_id` as a plain
  string sort, not by file order. `MS.EXO.13.1v1` therefore lists
  before `MS.EXO.2.2v3`. Choose ids that sort the way you want them
  read: the ASD, NCSC, and Learn packs zero-pad (`ASD-ENTRA-IDP-01`,
  `NCSC-CE-FW-01`, `MS-BSM-AUTH-01`) for exactly this reason. The
  SCuBA and FLASH packs keep their sources' own numbering and accept
  the sort as it falls.
- The style is yours. The shipped packs use four: the source's own
  policy numbers (SCuBA), a rubric number (FLASH, `R-1.1`), and
  prefixed serials (ASD, NCSC, Learn).

## Versioning

`pack_id` is the pack's identity, and the shipped packs embed the
source version in it (`scuba-m365-v2.0.0`,
`asd-secure-cloud-identity-1.4`, `ncsc-cyber-essentials-3.3`). When
the source framework issues a new version, mint a new `pack_id` for
it rather than editing items under the old one: a database that
already holds the old pack keeps scoring against the old items,
which is the behaviour you want for an engagement already in flight.

## Groups

A group is a display heading: coverage lists and reports show items
under their group names. Group names are free text; the shipped
packs take them from the source's own structure (SCuBA's seven
baselines, Cyber Essentials' five requirement areas, the FLASH
advisory's four mitigation groups). Keep groups few, stable, and in
the source's terms — a reader who knows the framework should
recognise them.

## Item text

`text` is the requirement, stated once, as a single requirement:

- One requirement per item. If a source paragraph states two, it is
  two items.
- Take the text verbatim from the source where the licence allows
  (below). Where the source's form does not fit — the ASD pack
  adapts a configuration table into expected-state statements — keep
  the adaptation faithful and say what you did in the
  `source_citation`.
- There is no severity or criticality field. Where the source marks
  one, it lives in the text: every SCuBA item's statement carries
  its SHALL or SHOULD, and the eleven SCuBA items with a licence
  requirement carry it as a ` License: ` suffix on the text, because
  there is nowhere else for it to go.

## Licensing and the source citation

A pack embeds its source's requirements, so the licence is part of
the format, not an afterthought:

- Embed only material you may redistribute: openly licensed
  (CC0, CC BY with attribution, OGL with acknowledgement) or public
  domain. The eight shipped packs are CISA SCuBA for Microsoft 365
  and Google Workspace (CC0 1.0), the ASD
  Blueprint (CC BY 4.0, attributed in the citation), NCSC Cyber
  Essentials (OGL v3.0), Microsoft Learn text (CC BY 4.0), GitHub
  Docs (CC BY 4.0, attributed in the citation), IETF RFCs with CISA
  and NCSC guidance (the DNS pack: US public domain and OGL v3.0),
  and an FBI FLASH advisory (US public domain, TLP:CLEAR).
- `source_citation` carries the full citation: the source, its
  version and date, where it was taken from, and its licence,
  including any attribution the licence requires.
- Some frameworks are not embeddable at any price of care. The CIS
  Benchmarks are the standing example: Fencewalk packs never embed
  CIS content — a CIS-based assessment cites the benchmark and
  works from a copy the operator supplies, it does not ship one.
- If you cannot state the licence in the citation, do not ship the
  pack.

## The eight shipped packs, as worked examples

| pack_id | items | groups | derived how |
|---|---|---|---|
| `flash-20261113-001` | 20 | 4 | Hand-authored from the FBI FLASH-20261113-001 advisory's mitigation list; ids `R-1.1` style. |
| `scuba-m365-v2.0.0` | 109 | 7 | By rule from the ScubaGear v2.0.0 baseline files: one item per policy heading, the policy statement as text, licence requirements appended as a ` License: ` suffix. |
| `asd-secure-cloud-identity-1.4` | 60 | 8 | Adapted from the ASD Blueprint's Entra ID configuration pages into expected-state statements. |
| `ncsc-cyber-essentials-3.3` | 39 | 5 | One item per requirement in the Cyber Essentials requirements document. |
| `ms-learn-baseline-security-mode-2026-11-17` | 45 | 4 | One item per setting on the Microsoft Learn baseline security mode page, taken from a dated page snapshot. |
| `github-org-security-1.0` | 34 | 7 | Curated from GitHub Docs pages at a pinned commit of the docs repository into expected-state statements for a small organization; ids `GH-ID-01` style. |
| `scuba-gws-v1.1.0` | 124 | 8 | By rule from the ScubaGoggles v1.1.0 baseline files, the SCuBA M365 treatment: one item per policy heading, the policy statement verbatim (a list following the statement is dropped); Classroom, Gemini and Assured Controls excluded. |
| `dns-registrar-security-1.0` | 28 | 6 | Curated from IETF RFCs, CISA BOD 18-01, NCSC and NIST guidance into expected-state statements for a small organization's domains, DNS and mail authentication; ids `DNS-EM-04` style. |

Two of these are worth copying deliberately. The SCuBA pack was
derived *by rule*, not by hand: the rule (one item per policy
heading, statement taken whole) is written down with the pack's
history, so anyone can re-derive the pack from the pinned source
and diff it. And the FLASH pack shows the other end of the range: a
short source, read closely, authored by hand. Rule-derived where
the source is large and regular; hand-authored where it is small.

## Load and check a new pack

```sh
# Validate and load (a path, or a bundled pack name)
fencewalk load-pack scratch.db my-pack.json

# See what landed: every item, unscored
fencewalk list-coverage scratch.db --pack my-pack-id

# The packs the tool itself ships
fencewalk packs
```

Before you rely on a pack, check it the way the shipped packs were
checked: the item count and group counts against your own count of
the source (counted from the source, not from the pack you just
wrote), a verbatim spot-check of a few items against the source
text, and one full pass — load, score a few items, render the
report — on a scratch database.

## What a pack is not

- Not code. A pack never runs, calls, or fetches anything.
- Not a scoring. A pack states requirements; whether an engagement
  meets one is recorded per engagement, by the operator and the
  model pass, never in the pack.
- Not a place for metadata. There are no per-item fields beyond
  `item_id`, `group`, and `text`, and no pack-level fields beyond
  the five. Anything else you write into the file is dropped at
  load.
