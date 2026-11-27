# Fencewalk

Fencewalk is a local-first tool that runs one repeatable method for auditing a
small organization's perimeter: build a structured, evidence-labeled inventory;
score it against a sourced rubric; run a bounded model pass that maps coverage,
builds attack chains, and drafts fixes; adjudicate the model's output against
the evidence; and track the fixes to done.

It is not a scanner. Evidence enters through the operator (console reads,
exports, captures); the tool's value is the evidence discipline. Every
inventory entry carries a label — VERIFIED (checked, with date and source),
ON RECORD (asserted in the operator's records, not freshly checked), or
UNKNOWN — and UNKNOWN is a first-class value that nothing silently upgrades.

Fencewalk reports findings; it does not guarantee security. Findings are
advisory: a clean report is evidence about the checks that ran, not proof
that nothing is wrong.

## Install

Python 3.11 or later, standard library only, zero third-party
dependencies.

```sh
pipx install fencewalk
```

That puts a `fencewalk` command on PATH. The tool ships with eight rubric
packs (FLASH, CISA SCuBA M365 and Google Workspace, ASD, NCSC Cyber
Essentials, Microsoft Learn Baseline Security Mode, GitHub, and DNS and
registrar) and the Marigold reference fixture bundled in, so an
installed run needs no checkout: `fencewalk load-fixture reference-case
eng.db` works from anywhere, and `fencewalk packs` lists what it ships.

Git clone stays as the fallback (for reading the source, or for
auditing exactly what runs):

```sh
git clone https://github.com/klarollc/fencewalk.git
cd fencewalk
PYTHONPATH=src python -m fencewalk --version
```

The commands below are written in the `fencewalk ...` form; from a
checkout, prefix them with `PYTHONPATH=src python -m` instead.
Publishing a release is a separate, manual step — see
`RELEASING.md`; nothing here publishes anything.

## Quickstart

The shortest path from install to a PDF report, on the bundled
Marigold fixture (a wholly fictional food bank, invented for
Fencewalk):

```sh
pipx install fencewalk
fencewalk load-fixture reference-case eng.db
fencewalk load-pack eng.db scuba-m365-v2.0.0
fencewalk report eng.db
fencewalk pdf eng.db --out eng.pdf
```

The fixture arrives already scored, so the report opens with its
golden numbers:

```text
## Posture summary

- Inventory: 52 entries (VERIFIED 15, ON RECORD 19, UNKNOWN 18)
- Coverage: Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows
- Attack chains: 3
- Fixes: 16 (proposed 13, approved 1, done 1, deferred 1)
- Verify-next items: 10
```

And the last command writes the PDF:

```text
pdf written to eng.pdf
```

To work the loop instead of just reading it, follow
[`docs/walkthrough.md`](docs/walkthrough.md): it runs the same
fixture end to end — checklist, packet, adjudication, fix
tracking — with real commands and real outputs. Check the
installed version any time with `fencewalk --version`.

### Demo dataset: a SCuBA-scored tenant

A second bundled fixture, `demo-scuba`, is a realistic Microsoft 365
engagement built from the sample reports that ship with CISA's
ScubaGear v2.0.0 (CC0 1.0 Universal). Every identifier in those
reports is replaced with one fictional tenant, Tidewater Advisory LLC
at `tidewateradvisory.example`. Coverage scores all 109 items of the
bundled SCuBA pack straight from the sample run's results: Covered 72 ·
Partial 14 · Unknown 0 · Not applicable 8 · Gap 15. Four attack chains,
15 proposed fixes (one per failing policy) and 5 verify-next items sit
on top.

```sh
fencewalk load-fixture demo-scuba demo.db
fencewalk report demo.db
```

The fixture's `README.md` documents the derivation; its `SCRUB.md`
lists what was replaced and is backed by a test.

## The method (five stages, one loop)

1. **Intake.** Build the inventory in sections, every entry evidence-labeled.
2. **Verification.** Generate a read-only checklist from the UNKNOWN entries;
   resolved unknowns return as VERIFIED with dates. Default order is
   verify-first; an engagement records which order it used.
3. **Model pass.** Assemble a single self-contained packet (brief, inventory,
   rubric) for the operator to run in their own model session. Fencewalk
   itself makes no model call in this flow; the one exception is the
   optional `run-model` command (see Local-first, below).
4. **Adjudication.** Review the returned output against the inventory —
   accept, correct, or reject, with corrections preserved. Model-flagged
   inventory gaps flow back into the inventory as new UNKNOWNs.
5. **Fix tracking.** Each adjudicated fix carries a rubric citation, an effort
   estimate, the chain(s) it breaks, and a status that changes only on the
   operator's explicit action.

## Posture

- **Local-first.** The audit method makes no network calls, sends no telemetry, and needs no accounts. An inventory is a map of someone's attack surface; it stays on the operator's machine. The one exception is `run-model`, which calls the operator's own model provider with the operator's own key, only when the operator runs it.
- **Files are the interchange.** One SQLite database per engagement is the
  working store; the inventory, rubric packs, and reports also exist as plain
  files (JSON / Markdown) that build the store and render from it.
- **Rubric packs are data, not code.** A versioned file of items with stable
  IDs, groups, and a source citation. The engine is rubric-agnostic.
- **Counts are computed, never typed.** Every tally in a rendered report is
  computed from the store at render time.
- **Repo posture:** public at https://github.com/klarollc/fencewalk since
  Nov 22, 2026.

## Command reference

Commands are grouped by stage, in the `fencewalk ...` form. From a
checkout, prefix each with `PYTHONPATH=src python -m`. Layout of a
checkout: `src/fencewalk/` is the package; `src/fencewalk/packs/`
holds the rubric packs as data files; `src/fencewalk/fixtures/`
holds the bundled fixtures: the reference case, wholly fictional,
with its provenance note (`PROVENANCE.md`), and the others each with
a scrub audit note (`SCRUB.md`); `tests/` holds stdlib `unittest`
suites.

### Engagement registry

Keep a local list of engagement database paths:

```sh
fencewalk register /path/to/engagement.db
fencewalk engagements
fencewalk unregister /path/to/engagement.db
```

The registry defaults to `~/.fencewalk/registry.json`. Each command
accepts `--registry <path>`, which takes precedence over
`FENCEWALK_REGISTRY`, which takes precedence over the default.
Only `register` creates a registry; an empty list prints
`no engagements registered`.

Registration stores only the canonical absolute database path and
registration date. `register` validates the database and prints its
subject label; registering the same canonical path twice is refused.
`engagements` reads each database afresh and lists SUBJECT, NAME,
CREATED, DEFAULT PACK, PACKS, ENTRIES, and SCORED, ordered by created
date then subject. The default pack follows the engagement's primary
pack, or the alphabetical fallback; SCORED counts coverage rows with
a status for that pack, including Unknown and Not applicable.

A missing database appears after the dated rows as `MISSING` with
its path and no counts. Unregistering removes only the registry
entry and works even if the database is missing. An unregistered
path is refused. Registry writes replace the JSON file atomically;
an invalid registry is an error naming its path and is never repaired
automatically. Validation and listing open databases read-only,
including older databases without a primary pack column. These
commands leave their database bytes unchanged. `serve` still takes
a database path directly.

### Intake

- **Labels are never edited in place.** `edit-entry` changes an
  entry's body, source, and checked/decay dates only. A label
  changes solely through `set-label`, which appends the change
  (date and actor) to the entry's label history. There is no entry
  deletion.
- **Import never guesses.** `import-inventory` reads the bundle
  format (`## A.` … `## H.` sections, `- ` bullets, numbered
  entries in section H) into an empty inventory. An entry whose
  text carries two or more distinct label markers (VERIFIED /
  ON RECORD / UNKNOWN) is skipped and listed in the import report
  for manual entry; an entry with no marker imports as UNKNOWN
  with a source noting the label was not stated. For a VERIFIED
  entry, the checked date is read from the same sentence as the
  marker.

```sh
# Create a fresh engagement database (refuses to overwrite an existing file)
fencewalk new /tmp/eng.db --name "Example audit" --subject "Example firm" --method-order verify-first --date 2026-11-18

# Add an entry (without --id, the next free ID in the section is assigned)
fencewalk add-entry /tmp/eng.db --section A --body "Mail is hosted by Example Mail." --label VERIFIED --source "console read" --checked-date 2026-11-18

# List entries (read-only; --section filters)
fencewalk list-entries /tmp/eng.db

# Change a label (the only label path; recorded in history)
fencewalk set-label /tmp/eng.db A1 "ON RECORD" --date 2026-11-19

# Edit body, source, or dates (never the label; --clear-*-date clears a date)
fencewalk edit-entry /tmp/eng.db A1 --body "Mail is hosted by Example Mail, verified at the console."

# Import a bundle-format Markdown inventory (inventory must be empty)
fencewalk import-inventory /tmp/eng.db inventory.md

# Build an engagement database from a bundled fixture (by name, or a directory path)
fencewalk load-fixture reference-case /tmp/reference.db
```

### Scoring

- **Pack loading is explicit and validated.** `new` does not seed
  a pack. `load-pack` validates the whole file first (pack id,
  title, source citation, and version present and non-empty; a
  non-empty items list with unique IDs and a group and text on
  every item) and inserts nothing on failure. Loading a pack whose
  id is already in the database is refused. A pack argument is
  either a file path or a bundled pack name.
- **Scoring goes through the store invariants.** A score with no
  cited entries can only be Unknown, or Not applicable with a
  written N/A reason; Not applicable always requires the reason.
  Citations must name entries that exist, and the item must belong
  to the pack.
- **Replacement is an explicit act.** `score` refuses an item that
  already has a score and names the existing status; `rescore`
  replaces a score and its citations atomically (a failed rescore
  leaves the old score intact) and prints the previous status and
  reasoning beside the new ones. The record of why a score changed
  lives in adjudication, not in a score history.
- **"Not scored" is not "Unknown".** `list-coverage` lists every
  item in the pack; an item with no score is marked `not scored`,
  and the tallies line counts it separately from the Unknown
  status.
- **A database with no pack has no report.** `report` on a
  pack-less database exits with `error: database holds no rubric
  pack; load one with load-pack` instead of rendering.
- **One default pack.** With no `--pack`, `report`, `pdf`,
  `packet` and rubric validation use the engagement's primary pack:
  a fixture records its own pack when it loads, and
  `set-primary-pack` records one (it refuses a pack that is not
  loaded). With no primary recorded, the default is the
  alphabetically-first loaded pack, as it always was.

Eight packs ship with the tool. The FLASH pack is the ARTEX
mitigations rubric: 20 items in 4 groups, from FBI
FLASH-20261113-001. The SCuBA pack is the CISA SCuBA Microsoft
365 secure configuration baselines, pinned to ScubaGear **v2.0.0**
(released Oct 22, 2026), **109 items in 7 groups** (Entra ID 34,
Exchange Online 12, Power BI 8, Power Platform 9, Security Suite
24, SharePoint Online and OneDrive 8, Teams 14). The baselines
are CC0 1.0 Universal; the pack file carries the full source
citation. Each item is one baseline policy, stated verbatim, with
a ` License: ` annotation where the baseline names a licence
requirement (11 items). The SCuBA Google Workspace pack is the CISA
SCuBA Google Workspace secure configuration baselines, pinned to
ScubaGoggles **v1.1.0** (released Oct 22, 2026), **124 items in 8
groups** (Common Controls 42, Gmail 36, Drive and Docs 17, Google Chat
7, Google Meet 9, Google Calendar 6, Google Groups 6, Google Sites 1),
CC0 1.0 Universal; each item is one baseline policy, stated verbatim.
The Classroom, Gemini and Assured Controls baselines are not included.
Load it with `fencewalk load-pack <db> scuba-gws-v1.1.0`. The ASD pack is the ASD Blueprint for
Secure Cloud Entra ID expected state, pinned to **v1.4** (18
September 2026), **60 items in 8 groups** (Identity Properties 1,
Users 4, Groups 3, Devices 3, Applications 3, Protection 41,
Identity Governance 2, External Identities 3). The Blueprint is
CC BY 4.0, attributed © Commonwealth of Australia 2023; the pack
is adapted for a small organisation — the Blueprint's PROTECTED
classification generalises to sensitive information, and its
named location "Australia" to the organisation's approved
countries. Load it with `fencewalk load-pack <db>
asd-secure-cloud-identity-1.4`. The NCSC pack is the NCSC Cyber
Essentials requirements for IT infrastructure, pinned to **v3.3**
(April 2026), **39 items in 5 groups** (Firewalls 7, Secure
Configuration 9, Security Update Management 4, User Access
Control 12, Malware protection 7). The requirements are © Crown
copyright 2026, under the Open Government Licence v3.0; the pack
is curated — one item per requirement statement, thresholds
preserved. Load it with `fencewalk load-pack <db>
ncsc-cyber-essentials-3.3`. The Microsoft Learn pack is the Baseline
Security Mode settings, pinned to **ms.date 2026-11-17**, **45 items
in 4 groups** (Authentication 21, Applications 12, Files 6, Room
devices 6). The settings are CC BY 4.0, attributed to Microsoft
Corporation; the pack is curated — one item per distinct setting,
the duplicate folded. Load it with `fencewalk load-pack <db>
ms-learn-baseline-security-mode-2026-11-17`. The GitHub pack is the
organization security expected state curated from GitHub Docs
(github/docs @ bd60abd, CC BY 4.0, © GitHub, Inc.), **34 items in 7
groups**; load it with `fencewalk load-pack <db> github-org-security-1.0`.
The DNS and registrar pack is the domain, DNS and mail-authentication
expected state curated from IETF RFCs, CISA BOD 18-01 (US public
domain) and NCSC guidance (Open Government Licence v3.0), **28 items in
6 groups**; load it with `fencewalk load-pack <db>
dns-registrar-security-1.0`.

To write a pack of your own for a framework the tool does not
ship, see `docs/pack-authoring.md` — the format, the rules the
loader enforces, and the eight shipped packs as worked examples.

```sh
# List the rubric packs shipped with the tool (read-only)
fencewalk packs

# Validate and load a rubric pack into a database (refuses a duplicate pack id)
fencewalk load-pack /tmp/eng.db flash-20261113-001
fencewalk load-pack /tmp/eng.db scuba-m365-v2.0.0

# Record the engagement's primary pack: the default when no --pack is given
fencewalk set-primary-pack /tmp/eng.db flash-20261113-001

# Score one item (--cite is repeatable; --na-reason is required for Not applicable)
fencewalk score /tmp/eng.db --pack flash-20261113-001 --item R-1.4 --status Covered --reasoning "Built from Git; nothing to modify in place." --cite C1 --cite C2

# Replace an existing score (prints the previous status and reasoning beside the new ones)
fencewalk rescore /tmp/eng.db --pack flash-20261113-001 --item R-1.4 --status Partial --reasoning "Revised after a second look." --cite C1

# List every pack item with its score, or "not scored" (read-only)
fencewalk list-coverage /tmp/eng.db --pack flash-20261113-001
```

### Checklist

The checklist is a **derived view**: it is computed from the
database's current state at an as-of date and stores nothing —
there is no checklist table and no check-off state. It lists the
inventory entries still labelled UNKNOWN and, separately,
VERIFIED or ON RECORD evidence whose recorded decay date has
passed. It covers UNKNOWN inventory entries, not Unknown
coverage scores. Resolutions are recorded with `set-label`: a
settled entry leaves the next checklist, and the label history
keeps the record. An unknown that cannot be settled stays
UNKNOWN and stays on the list; that is the correct outcome, not a
failure.

```sh
# Render the verification checklist as of a date (default: today)
fencewalk checklist /tmp/eng.db --date 2026-11-18

# Or write it to a file
fencewalk checklist /tmp/eng.db --date 2026-11-18 --out /tmp/checklist.md

# Record a resolution; the entry leaves the next checklist
fencewalk set-label /tmp/eng.db A3 VERIFIED --date 2026-11-18 --actor operator
```

### Model pass

- **The packet is self-contained and deterministic.** `packet`
  assembles the run brief (the bundled template
  `src/fencewalk/templates/run-brief.md`, every placeholder
  substituted), the full labeled inventory in the bundle's
  section shape, and the full rubric, preceded by a
  run-configuration block. The same database state and options
  produce a byte-identical packet; the command prints its byte
  count and SHA-256 and records them, so a returned output can be
  tied to the exact bytes that were run. The model is not named
  in the packet — the operator chooses it at run time.
- **Ingest stores output verbatim, and changes nothing else.**
  `ingest` refuses an output whose `--packet-hash` names no
  recorded packet. It stores the output text exactly as returned,
  with the operator-stated model label (or `not stated` — the
  tool never guesses a model), and writes no coverage scores,
  chains, fixes, or verify-next items. Parsing output into the
  record is adjudication's work.
- **`run-model` calls a provider API instead of hand-carrying
  the packet.** It assembles and records the packet exactly as
  `packet` does, calls the Anthropic Messages API with the
  operator's own `ANTHROPIC_API_KEY`, and writes the raw output
  to a file. It records no run — inspect the file, then `ingest`
  it as above. The packet states it was run via the API.
- **The draft sections without altering.** `draft` splits a stored
  run's output at its deliverable headings (coverage, attack
  chains, fixes, verify-next), reproduces each section verbatim
  under a heading naming the deliverable, and follows each with an
  adjudication stub (accept / correct / reject, plus a correction
  line). Text before the first deliverable heading is kept as a
  preamble; an output with no recognizable headings drafts as one
  unsectioned block, stated plainly in the header.
- **An adversarial second pass attacks the standing scores.**
  `packet --posture adversarial` assembles a packet whose brief
  (the bundled `src/fencewalk/templates/adversarial-brief.md`)
  asks the model, for each scored item, for the strongest case
  that the status is wrong — evidence too thin for the status,
  reasoning that overclaims, citations that do not support it —
  and the status the evidence does support, or a one-line "holds".
  Between the brief and the inventory it carries a standing-coverage
  section: every rubric item with its status, reasoning, N/A reason
  and cited entries with their labels, or `unscored` (out of scope
  for proposals). It is deterministic and hash-recorded like the
  standard packet, the record notes its posture, and `ingest`,
  `draft` and `adjudicate` take its run as they take any other.
  The default posture is `standard`, whose packet is unchanged.
  `run-model` sends standard packets only.
- **Older databases just work.** The `packet_record` and
  `model_run` tables are part of the schema for new databases and
  are created on first use in databases built before them — no
  migration step. The packet record's posture column is added on
  the first write; packets recorded before it read as `standard`.

```sh
# Assemble the packet and record its hash (deterministic for the same state)
fencewalk packet /tmp/eng.db --out /tmp/packet.md --date 2026-11-18

# Or a second pass that attacks the standing scores (posture recorded with the hash)
fencewalk packet /tmp/eng.db --posture adversarial --out /tmp/adversarial-packet.md --date 2026-11-18

# Or call the Anthropic API with your own key (records the packet, writes the raw output; ingest it as above)
fencewalk run-model /tmp/eng.db --provider anthropic --model <model-id> --out /tmp/model-output.md --date 2026-11-18

# Store a returned output against the packet it answers (model label is the operator's statement)
fencewalk ingest /tmp/eng.db /tmp/model-output.md --packet-hash <sha256> --model "Example Model 1"

# Render the adjudication draft for a stored run
fencewalk draft /tmp/eng.db --run 1
```

### Adjudication

- **Decisions are append-only events.** `adjudicate` records one
  decision (accept / correct / reject) for one deliverable
  section of one run, with a date and an actor. Adjudicating a
  section again adds a new event; the section's current standing
  is its latest event, and the full history stays one
  `adjudications` call away. A `correct` decision **requires**
  `--note`: the note is the correction, preserved verbatim in the
  record.
- **A decision never applies anything by itself.** Accepting or
  correcting a deliverable does not make the tool parse model
  output into record entries — that silent, fragile step is
  refused by design. Applying an adjudicated deliverable is
  always a separate explicit command (see Fixes, below).

```sh
# Record one adjudication decision (a correction requires its note)
fencewalk adjudicate /tmp/eng.db --run 1 --section coverage --decision correct --note "W-1.2 is scored from the checklist, not taken from the run."

# List a run's decision events and current standings
fencewalk adjudications /tmp/eng.db --run 1
```

### Calibration

- **Where past passes over- or under-called.** `calibration`
  reads every model run recorded against a packet for the
  compared pack (default: the engagement's primary pack, else
  the alphabetically-first loaded pack) that has at least one
  adjudication event in the coverage section. For each, it
  reads the run's proposed statuses from its coverage section
  and compares them with each item's standing status today:
  agree, model optimistic or model pessimistic (on the axis
  Covered > Partial > Unknown > Gap), n/a-involved (exactly one
  side Not applicable), or standing unscored. Tallies and the
  agreement share are given by rubric group, by packet posture
  (standard / adversarial), by run, and overall.
- **Proposals are read, never guessed.** The coverage section is
  found with the same section rule `draft` uses. Within it, a
  table row is read when exactly one cell is a pack item ID and
  exactly one cell is a status, in any column order. A row that
  names a pack item any other way is excluded and counted in the
  header, as are runs with no coverage adjudication.
- **Read-only.** The database is opened read-only: rendering
  never writes to it, and the same database renders the same
  bytes. Reading proposals for tallies records nothing; applying
  a proposal stays a separate explicit command.
- **Standing scores are as of today.** A score changed since
  adjudication for any reason counts exactly as an overturn
  does; the report says so in its closing note.

```sh
# Render the calibration report (Markdown, to stdout or --out)
fencewalk calibration /tmp/eng.db
fencewalk calibration /tmp/eng.db --pack flash-20261113-001 --out /tmp/calibration.md
```

### Probes

- **A probe tests a claim in behavior.** Documentary evidence
  says a control is on record; a probe records the operator doing
  the thing the control claims to govern — requesting the record,
  attempting the sign-in path, triggering the alert — and what
  happened. `record-probe` stores the item, the method (free
  text), the outcome (confirmed / failed / inconclusive), the date
  and the actor. It refuses an unknown pack or an item outside the
  pack, and writes nothing when it refuses.
- **Append-only, and it moves no score.** A probe is never edited
  or deleted; probing again adds a record, and the latest stands.
  A failed probe is a fact on record — acting on it (a `rescore`)
  stays the operator's decision.
- **The documentary-only claims.** `probes` lists each probed
  item's latest probe for the default pack (or `--pack`).
  `probes --unprobed` lists instead the Covered and Partial items
  with no probe on record. Both are read-only.
- **Older databases just work.** The `probe_result` table is in
  the schema for new databases and is created by the first
  `record-probe` in older ones; the listings treat a missing table
  as no probes and never create it.

```sh
# The Covered and Partial items no probe has tested (read-only)
fencewalk probes /tmp/eng.db --unprobed

# Record one probe (append-only; scores are unchanged)
fencewalk record-probe /tmp/eng.db --pack flash-20261113-001 --item R-4.3 --method "Tried the recovery path; no second admin exists." --outcome failed --date 2026-11-18

# Each probed item's latest probe (read-only)
fencewalk probes /tmp/eng.db
```

### Chain step items

- **A step can name the rubric item it exercises.** Each chain
  step may carry a rubric item and the pack it was validated
  against — both or neither, as the chain's own control
  reference does. `add-chain --step-item <step_no>=<item_id>`
  (repeatable, 1-based) names them as the chain is created;
  `set-step-item` names or `--clear`s one step of an existing
  chain. Both validate the item against the pack resolved as
  `--control-rubric` resolves it (`--pack`, else the primary
  pack, else the alphabetically-first loaded pack), and refuse an
  unknown chain, step, or item without writing.
- **What it feeds.** The reference is what `chains` and the
  report's computed-exposure line derive from (see Attack paths,
  below). A chain whose steps name no item renders exactly as
  before everywhere.
- **Older databases just work.** The two columns are added on the
  first write; steps recorded before them name no item.

```sh
# Name items as the chain is created (step numbers are 1-based)
fencewalk add-chain /tmp/eng.db --key D --name "An old API key" --control "an API key inventory" --control-status unknown --step "Reconnaissance: No inventory says where the key lives." --step "Initial access: A found key is tried." --step-item 1=R-3.4

# Name, or clear, the item one step of an existing chain exercises
fencewalk set-step-item /tmp/eng.db --chain D --step 2 --item R-3.1
fencewalk set-step-item /tmp/eng.db --chain D --step 2 --clear
```

### Attack paths

- **A chain's exposure, computed from the record.** For each chain,
  the steps that name a rubric item are marked with that item's
  standing status in its own pack (or `unscored`). The chain is
  **interrupted** at its earliest Covered step; **contested** at its
  earliest Partial or Unknown step when none is Covered; **open**
  when every annotated step is Gap, Not applicable, or unscored.
- **Not computed is said, never guessed.** A chain whose steps name
  no items renders as not computed, in so many words — never as
  open or safe. In a partly annotated chain, the unannotated steps
  are shown unmarked and not judged, and the derivation says it
  rests on the annotated steps only.
- **Related fixes.** A fix is related to a chain when its mapped
  rubric items intersect the chain's annotated-step items; it is
  listed with its status. A proposed fix interrupts nothing until
  the rescore lands.
- **Computed at render, never stored.** `chains` is read-only and
  deterministic; a rescore changes the derivation on the next
  render. The Markdown report's Attack chains section carries the
  derivation as one "Computed exposure" line under each computed
  chain's control line, and is otherwise unchanged; an engagement
  with no annotated chain renders exactly as before. The PDF
  report does not carry the computed-exposure line yet.

```sh
# Every chain: steps with their items' standing statuses, the derivation, related fixes
fencewalk chains /tmp/eng.db
```

### Fixes

- **Application is by hand, never by parsing.** The operator
  applies each deliverable with explicit, checked commands:
  `score`/`rescore` for coverage, `add-chain`, `add-fix`, and
  `add-verify-next` for the rest, and `add-entry` for
  model-flagged inventory gaps, which enter as UNKNOWN like any
  other unverified fact. Duplicate chain keys and fix IDs are
  refused, and rubric citations are validated against the pack.
- **Fix status changes only on the operator's explicit action.**
  `add-fix` creates a fix as `proposed`; `set-fix-status` is the
  only path that moves it (proposed / approved / done /
  deferred), records the change in the fix's history, and refuses
  a same-status no-op. Nothing anywhere in the tool marks a fix
  done, changes a label, or enters a score by inference from a
  decision.

```sh
# Apply an adjudicated chain by hand (steps are "<phase>: <text>")
fencewalk add-chain /tmp/eng.db --key A --name "a borrowed ladder reaches the office window" --control "a lock on the window latch" --control-status unknown --control-rubric W-1.1 --step "Reconnaissance: the ladder is stored in the open yard" --step "Initial access: the window is climbed at night"

# Apply an adjudicated fix (created as proposed) and track it
fencewalk add-fix /tmp/eng.db --id F-1 --action "Fit a lock to the office window latch" --effort "An hour" --breaks A --rubric W-1.1
fencewalk set-fix-status /tmp/eng.db F-1 approved
fencewalk list-fixes /tmp/eng.db

# Render one fix's packet, to work it by hand (read-only; records nothing)
fencewalk fix-packet /tmp/eng.db F-1
fencewalk fix-packet /tmp/eng.db F-1 --out /tmp/F-1.md

# Apply an adjudicated verify-next item (sequence number assigned)
fencewalk add-verify-next /tmp/eng.db --unknown "whether the yard gate is locked at night" --why "chain A stands or falls on it" --check "the harbour log's gate page"
```

A **fix packet** gathers everything recorded about one fix: the
action as its title; the subject and engagement; the current
status with its date and actor, the effort, and the chains it
breaks; every status-history row, oldest first; and, for each
mapped rubric item (ordered by pack, then item ID), the item's
full rubric text, its pack, its current coverage status and
reasoning (or "not scored"), and the inventory entries the score
cites with their current labels. It ends with **Verify by
rescore**: the mapped items not yet Covered, the rescore list for
when the fix lands, or "All mapped items are Covered." A fix with
no mapped items reads "No mapped rubric items." An unknown fix ID
is refused. The fix packet is a view, unlike `packet`: it opens
the database read-only (including an older database without a
primary pack column), changes no byte of it, records no run, and
renders the same text every time. It adds no remediation steps
beyond the fix's own action text.

### Report

The report renders the engagement from the store: posture
summary, coverage table, attack chains, fixes, verify-next, and —
only when at least one adjudication event exists — an Adjudication
section carrying, per run, the model label, run date, and packet
hash, then each deliverable's current decision, date, actor, and
note. A database with no adjudication events renders exactly as
before, byte for byte.

The PDF is the same report as a file, for handing to a client or
filing: the same sections in the same order, the same wording, the
same computed counts, from the same gathered data, so the two
never drift apart (one exception: the computed-exposure line of
an annotated chain appears in the Markdown report only; see
Attack paths). The writer is hand-rolled (the standard
library has no PDF writer and the tool takes no dependencies):
US Letter, the standard 14 fonts only, FlateDecode streams, no
JavaScript, no forms, no links. Rendering the same database
twice produces byte-identical output: the file carries no
timestamps, and its `/ID` is the SHA-256 of the gathered report
data, so the document is bound to the record it reports. `--out`
is required — a PDF to stdout is hostile.

```sh
# Render the engagement report (Markdown) from a database
fencewalk report /tmp/reference.db

# Render and save the report (this is how src/fencewalk/fixtures/reference-case/EXPECTED-REPORT.md was produced)
fencewalk report /tmp/reference.db --out src/fencewalk/fixtures/reference-case/EXPECTED-REPORT.md

# Render the same report as a PDF file (same data, same sections, same wording; computed-exposure lines are Markdown-only, see Attack paths)
fencewalk pdf /tmp/reference.db --out /tmp/reference.pdf
```

### Re-audit drift

A re-audit changes the engagement database in place. To answer
"what changed since the last audit?", copy the database before the
re-audit, then diff the copy against the current database:

```sh
# Before the re-audit: keep a copy
cp engagement.db engagement-2026-11.db

# After it: render the drift report (Markdown, to stdout or --out)
fencewalk diff engagement-2026-11.db engagement.db
fencewalk diff engagement-2026-11.db engagement.db --out drift.md
```

The report names the subject, the engagement, both file paths, the
compared pack, and each side's coverage tally line. It then lists,
for the compared pack, every item whose coverage status differs
(ITEM · WAS · NOW, with "not scored" for an item scored on one side
only); every inventory entry whose current label differs, or that
exists on one side only (added / removed); and every fix whose
current status differs, or that exists on one side only, with the
newer side's status date. Unchanged items, entries, and fixes are
counted, not listed, and a closing line totals the three kinds of
change. A pair with nothing changed reads "No changes." in every
section.

`--pack` names the compared pack; the default is the newer
database's default pack (its primary pack, else the alphabetical
fallback). The pack must be loaded in both databases. `diff` refuses
two different engagements (a different subject label or created
date), and a database holding other than exactly one engagement
row. It compares current state only: a changed reasoning with the
same status counts as unchanged, and chains and verify-next items
are not compared. Both databases are opened read-only, including
older databases without a primary pack column; their bytes never
change, and the same pair always renders the same report.

## The web interface

`serve` puts one engagement database on a local web page: an
overview (posture figures, checklist counts, coverage tallies,
model-pass provenance), the inventory (filterable by label and
section), the verification checklist, the coverage matrix, the
model-pass page (packet assembly and output ingest), the
adjudication page (draft sections, decision forms, apply forms),
the fixes list, and the report — the same store and the same
computed counts as the CLI, rendered as HTML.

- **Reads are reads.** GET and HEAD never write: a full crawl of
  every page leaves the database file byte-identical, and the
  store is opened fresh per request, so figures can never go
  stale against the database on disk.
- **The verification loop writes in the browser.** Four form
  submissions — set-label, edit-entry, add-entry, and
  score/rescore — each maps one-to-one onto the CLI command of
  the same name and calls the same store method, with the same
  invariants, the same refusals, and the same history recording;
  a refused write shows the refusal message verbatim and writes
  nothing. Every other path still refuses POST with 405, and PUT,
  DELETE, and PATCH are refused everywhere.
- **The model pass and adjudication write in the browser.** Seven
  further form submissions — packet assembly, output ingest,
  adjudication decisions, add-chain, add-fix, fix-status
  transitions, and add-verify-next — each mapping one-to-one onto
  the CLI command of the same name with the same invariants and
  refusals. The packet assembly is the one submission that
  answers with a file download instead of a redirect: the store
  records only the packet's hash and metadata, so the packet text
  exists nowhere after assembly except in that response. Ingest
  takes pasted output (CRLF normalized to LF, the one documented
  transformation); a decision never applies anything by itself —
  applying an adjudicated deliverable is always a separate
  explicit submission.
- **Bounded request checks, not authentication.** The interface
  has no authentication. As the proportionate control for that,
  three checks run on every request, at zero dependency cost.
  First, the Host header must name this server — the bind address
  or a loopback name (`127.0.0.1`, `localhost`, `::1`) on the
  bound port — or the request is refused with 403 and nothing is
  served or written; this defeats DNS rebinding, where a hostile
  page's own hostname resolves to 127.0.0.1. Second, a form
  submission whose Origin (or, failing that, Referer) host does
  not match the Host is refused with 403. Third, every write form
  carries a random per-process token, held only in the server's
  memory and never printed; a submission without it is refused
  with 403 before anything is written (reload the page after a
  restart). None of this identifies the operator, and it is not a
  substitute for keeping the server local.
- **Local by default.** `serve` binds `127.0.0.1:8090`. Binding
  any other host prints a plain warning at startup: the interface
  has no authentication, and anyone who can reach the port can
  read the engagement — and change it through the forms above.
  Because of the Host check, a non-local bind answers only
  requests addressed to the bind address itself (or a loopback
  name): bind the specific interface address you will browse to.
  A wildcard bind (`0.0.0.0`) answers loopback names only.
- **Nothing extra to install.** Standard library only, no
  JavaScript, no external assets — the stylesheet is embedded in
  the page. A database with no rubric pack renders with a plain
  "no rubric pack loaded" note where coverage would go, and its
  report page shows the CLI's clean error line instead of
  failing.

```sh
# Serve an engagement database on http://127.0.0.1:8090/
fencewalk serve /tmp/eng.db

# Choose the port, or bind another address (prints the no-auth warning);
# browse to that same address, e.g. http://192.0.2.10:8090/
fencewalk serve /tmp/eng.db --port 8091
fencewalk serve /tmp/eng.db --host 192.0.2.10
```

## Licence

Fencewalk is released under the MIT licence. See `LICENSE`.

## Build history

- **Slice 0** — the store and the counts: engagement data model,
  FLASH pack as data, the reference fixture (then a scrubbed
  derivative of a real engagement, since replaced by a wholly
  fictional case), the fixture loader, and the Markdown report
  renderer.
- **Slice 1** — intake: `new`, `add-entry` / `edit-entry` /
  `set-label` / `list-entries`, and bundle-Markdown import.
- **Slice 2** — rubric packs and manual coverage scoring:
  `load-pack`, `score` / `rescore`, `list-coverage`.
- **Slice 3** — verification checklists: a derived view that
  stores nothing.
- **Slice 4** — the model pass: `packet`, `ingest`, `draft`.
- **Slice 5** — adjudication and fix tracking: `adjudicate` /
  `adjudications`, `add-chain`, `add-fix`, `set-fix-status`,
  `add-verify-next`.
- **UI-0** — the web interface, read-only: overview, inventory,
  checklist, coverage, report.
- **UI-1** — the verification loop writes in the browser.
- **UI-2** — the model pass, adjudication, and fix transitions
  write in the browser.
- **SCuBA pack (Phase 1)** — the second rubric pack, from pinned
  ScubaGear v2.0.0.
- **PDF report (Phase 1)** — the engagement report as a
  deterministic PDF file.
- **Packaging (Phase 1)** — `pipx install fencewalk`: a console
  entry point, one version source, and the packs, fixture, and
  template bundled as package data.
- **ASD pack (Phase 1)** — the third rubric pack, the ASD
  Blueprint for Secure Cloud Entra ID expected state, v1.4,
  adapted for a small organisation.
