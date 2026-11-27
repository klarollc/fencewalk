# Walkthrough: the Marigold fixture, end to end

Run the whole method once, on fictional data, before you run it on
a real engagement. This walkthrough loads the bundled Marigold
reference fixture — Marigold Community Food Bank, an organization
invented for Fencewalk, on a `.example` domain — into a scratch
database, works all five
stages, and ends with a rendered report and PDF. Nothing here
touches the golden fixture files: the walkthrough's database is a
scratch copy, and its final report is that scratch database's
report.

Work in a scratch directory:

```sh
mkdir -p ~/fencewalk-walkthrough && cd ~/fencewalk-walkthrough
```

Two reading conventions, because two things vary by run. **Dates**
read the day you run a command: the outputs below are from a run
on 2026-11-26, and yours will show your date. **The packet hash**
is a 64-character SHA-256 of the packet you assembled: wherever
an output below shows `<64 hex characters>`, your run will show
your hash. Everything else — counts, tallies, byte counts — is
stable for this fixture and should match exactly.

## What you will do

The five stages on the fixture, in one loop: take in the
52-entry inventory and its 20 scored rubric items; work the
verification checklist down by one entry; assemble the model-run
packet, bring back an illustrative sample output (or, on a real
engagement, run it through `run-model`), and draft it; adjudicate
the draft's four sections; apply one chain, two fixes, and two
verify-next items by hand; move one fix to done; and render the
final report and PDF.

## Install

```sh
pipx install fencewalk
```

That puts a `fencewalk` command on PATH. Check it with
`fencewalk --version`. The tool ships with five rubric packs
(FLASH, CISA SCuBA, ASD, NCSC Cyber Essentials, and Microsoft Learn Baseline Security Mode) and the Marigold reference fixture
bundled in, so nothing below needs a checkout.

## Stage 1 — intake

Load the fixture into a fresh database, then look at the report.
The fixture arrives already scored: 20 rubric items, 3 chains,
16 fixes, 10 verify-next items.

```sh
fencewalk load-fixture reference-case walk.db
```

```text
loaded fixture from reference-case into walk.db (engagement 1)
```

```sh
fencewalk report walk.db
```

The report opens with the posture summary. These are the golden
numbers for the fixture — check yours match:

```text
## Posture summary

- Inventory: 52 entries (VERIFIED 15, ON RECORD 19, UNKNOWN 18)
- Coverage: Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows
- Attack chains: 3
- Fixes: 16 (proposed 13, approved 1, done 1, deferred 1)
- Verify-next items: 10
```

One fix is already `done` in the fixture (F-1, the printed
incident sheet), one is `approved` (F-2, closing the NAS port
forward), one is `deferred` (F-16, replacing the warehouse
camera), and the other thirteen are `proposed`. The coverage tallies are the
fixture's adjudicated scores against the FLASH rubric pack.

Load the second bundled pack the same way. It does not change
this report — the report renders the engagement's primary pack,
FLASH, which the fixture recorded when it loaded — but the pack is
now in the database for scoring:

```sh
fencewalk load-pack walk.db scuba-m365-v2.0.0
```

```text
loaded pack scuba-m365-v2.0.0: CISA SCuBA M365 Secure Configuration Baselines (ScubaGear v2.0.0) — 109 items, 7 groups
```

## Stage 2 — verification

Render the checklist. It is a derived view: computed from the
database at this moment, storing nothing.

```sh
fencewalk checklist walk.db
```

```text
# Verification checklist — Reference case — Marigold Community Food Bank perimeter audit

- As of: 2026-11-26
- Checks: 18 unknown · 0 decayed evidence · 18 total
```

The list that follows names all 18 UNKNOWN entries with their
sources. Pick one and resolve it. Here we take E5, whether the
warehouse router's own admin page answers from the internet — on
this fictional fixture the resolution is a demonstration of the
command, not a real verification: the operator loads the router's
public address from a phone off the warehouse network, finds no
admin page answering, and records it.

```sh
fencewalk set-label walk.db E5 VERIFIED --actor operator
```

```text
E5 label set to VERIFIED
```

The date recorded is today, unless you pass `--date`. Render the
checklist again: E5 is gone, and the count drops by one.

```sh
fencewalk checklist walk.db
```

```text
- Checks: 17 unknown · 0 decayed evidence · 17 total
```

An unknown that cannot be settled stays UNKNOWN and stays on the
list. That is the correct outcome, not a failure.

### Probes: testing a claim in behavior

Every standing score rests on documents — entries labeled
VERIFIED or ON RECORD, cited. A probe is different: you do the
thing the control claims to govern, and write down what actually
happened. Start with the claims that have never been tested that
way — the Covered and Partial items with no probe on record:

```sh
fencewalk probes walk.db --unprobed
```

```text
Pack: flash-20261113-001 (ARTEX mitigations rubric)
R-1.1 (Group 1 — Reduce external attack surface) Partial — no probe on record
R-1.3 (Group 1 — Reduce external attack surface) Partial — no probe on record
R-1.6 (Group 1 — Reduce external attack surface) Partial — no probe on record
R-2.2 (Group 2 — Harden identity and access) Partial — no probe on record
R-2.5 (Group 2 — Harden identity and access) Partial — no probe on record
R-3.1 (Group 3 — Strengthen application protections) Covered — no probe on record
R-3.2 (Group 3 — Strengthen application protections) Partial — no probe on record
R-3.3 (Group 3 — Strengthen application protections) Covered — no probe on record
R-3.4 (Group 3 — Strengthen application protections) Partial — no probe on record
R-4.1 (Group 4 — Preserve evidence and respond) Partial — no probe on record
R-4.3 (Group 4 — Preserve evidence and respond) Covered — no probe on record
Unprobed: 11 of 11 Covered or Partial items
```

All eleven rest on documents alone. Take R-4.1, preserving the
audit records: the record says Purview audit keeps 180 days of
events, but that figure came from the licence documentation, not
from the tenant. Run one search and record the outcome —
confirmed, failed, or inconclusive:

```sh
fencewalk record-probe walk.db --pack flash-20261113-001 --item R-4.1 --method "Ran a Purview audit search for donations@ over the last 30 days: it returned no events at all, not even the failed sign-ins the Entra sign-in log shows." --outcome failed
```

```text
recorded probe 1 (R-4.1, failed); scores are unchanged
```

```sh
fencewalk probes walk.db
```

```text
Pack: flash-20261113-001 (ARTEX mitigations rubric)
R-4.1 (Group 4 — Preserve evidence and respond) failed — 2026-11-26 · operator · 1 probe on record
  method: Ran a Purview audit search for donations@ over the last 30 days: it returned no events at all, not even the failed sign-ins the Entra sign-in log shows.
Latest outcomes: confirmed 0 · failed 1 · inconclusive 0 · probes on record 1
```

R-4.1 leaves the unprobed list (10 of 11 now), and its score is
still Partial. **A probe never changes a score.** A failed probe
is a fact on record; acting on it — rescoring the item — is your
decision and your command, exactly as with an adjudicated run.
Probes are append-only: probing the item again adds a record, and
the listing shows the latest.

## Stage 3 — model pass

Assemble the packet: the run brief, the full labeled inventory,
and the rubric, preceded by a run-configuration block.

```sh
fencewalk packet walk.db --out packet.md
```

```text
packet written to packet.md
byte count: 18733
sha256: <64 hex characters>
```

The byte count is for this state: resolving E5 changed one
label, which changed one byte. For the untouched fixture the
packet is 18,732 bytes. The packet is deterministic for the same
state — assemble it again and the bytes, and the hash, are the
same.

Now the part Fencewalk does not do. Take `packet.md` to your own
model session, run it there under your own model access and
terms, and bring the output back by hand. On this manual path
Fencewalk does not call a model API, and the packet names no model —
you choose it at run time. (The one exception in the tool is the
optional `run-model` command, which sends the packet to your own
model provider with your own key, only when you run it.)

### Run it with run-model instead

On a real engagement you can skip the hand-carry. `run-model`
calls a provider API instead of hand-carrying the packet: it
assembles and records the packet exactly as `packet` does, calls
the Anthropic Messages API with your own `ANTHROPIC_API_KEY`, and
writes the raw output to a file. This walkthrough shows the
commands and a dry run; it makes no live call.

Start with a dry run. It needs no key, sends nothing, writes no
file, and records no packet:

```sh
fencewalk run-model walk.db --provider anthropic --model <model-id> --out model-output.md --dry-run
```

With `claude-opus-5-5` as the model id, in this walkthrough's
state (E5 resolved), the dry run prints:

```text
dry run: no request sent, no file written, no packet recorded
url: https://api.anthropic.com/v1/messages
model: claude-opus-5-5
max_tokens: 16384
packet byte count: 18827
packet sha256: <64 hex characters>
headers: x-api-key, anthropic-version, content-type
```

The API packet is not the 18,733-byte manual packet above: it
adds a `Run via: anthropic/<model-id>` line and states that
Fencewalk called the provider API, so its byte count depends on
the length of the model id you name. Yours matches 18827 only if
you name the same id. The headers line names the headers the
request would carry, not their values.

For the live call, the key is your own `ANTHROPIC_API_KEY`, read
from the environment only — never put it in a file, and never
paste it into a chat. Read it without echoing it, and export it
for the call:

```sh
read -s ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY
```

If the key is not set, the command fails before anything is
assembled:

```text
error: ANTHROPIC_API_KEY is not set
```

Then run the same command without `--dry-run`, and unset the key
when it returns:

```sh
fencewalk run-model walk.db --provider anthropic --model <model-id> --out model-output.md
unset ANTHROPIC_API_KEY
```

The live call first prints
`model output written to model-output.md` and the packet's hash
and byte count, then the output's byte count; a
`note: skipped N thinking block(s)` line when the model thinks
(thinking blocks are skipped, and only the text is written to the
output file); the input and output token usage; and, under the
line `To record this output as a run:`, the exact `ingest`
invocation for that output, in this shape:

```sh
fencewalk ingest walk.db model-output.md --packet-hash <packet hash> --model anthropic/<model-id>
```

`run-model` assembles and records the packet exactly as `packet`
does and writes the raw output, but it records no run — inspect
the file, then `ingest` it as above; ingest stays the only path
into the record.

The packet says how it was run: the API packet carries a
`Run via: anthropic/<model-id>` line in its run configuration,
and the manual packet carries no `Run via` line at all — it names
no model. The model is recorded as exactly what you name; the
tool never guesses a model.

### This walkthrough's route: the sample output

For this walkthrough, use the illustrative sample output below
instead of a real run. Save it as `sample-output.md` in the
scratch directory. It is labeled illustrative in the file itself:
an example of the shape a run's output takes, not a real run.
(The same text ships in the repo as
`docs/sample-model-output.md`.)

```markdown
# Illustrative sample model output

This file is ILLUSTRATIVE. It is an example of the shape a model
run's output takes, written to demonstrate the walkthrough. It is
not a real model run, and nothing in it is evidence about
Marigold Community Food Bank, which is itself fictional. It
references real fixture rubric items (R-1.1, R-1.6, R-2.1, R-3.2)
and real fixture entries (A7, A8, C1, D1, D2, D5, E1, E6, H8) so
the walkthrough's apply commands are coherent.

# Coverage map

| Item | Status | Reasoning | Cited entries |
|---|---|---|---|
| R-1.1 | Partial | The website, the hosted checkout and the donor-management service are on the list, but the NAS login page and the camera's cloud viewer were found only by this audit. | C1, D1, E1, E6 |
| R-2.1 | Unknown | The three connected apps are named, but no one has read what each may do or who agreed to it. | A7, A8 |
| R-3.2 | Not applicable | There is no client portal: households are signed in on paper at the pantry window. | D5 |

# Attack chains

## Chain D: Donor list exported through a staff donor-management login

1. Reconnaissance: Staff names and work addresses are printed on appeal letters, and the donor-management service's sign-in page is public (D1).
2. Initial access: One of the six staff passwords is phished or reused from another site's breach. This depends on an UNKNOWN: whether the service asks for a second factor at all (D2, H8).
3. Privilege escalation: None needed if the account can run exports, which no record limits to the development director.
4. Collection-exfiltration: All 4,200 donor records, with home addresses and gift history, leave in one export. Whether any alert fires on a bulk export is UNKNOWN (D2).

Earliest breaking control: two-step sign-in on every donor-management account, with an alert on bulk exports. Status: unknown. Rubric: R-3.2.

# Fix list

- F-17: Turn on two-step sign-in for every donor-management account, and remove the accounts of staff who have left. Rubric: R-1.6. Effort: Minutes. Breaks: D.
- F-18: Limit full donor exports to the development director's account, and read the service's export history back to October 1. Rubric: R-3.2. Effort: An hour. Breaks: D.

# Verify-next list

1. Unknown: Whether the donor-management service's export history shows any full export since October 1. Why it changes the picture: It decides whether Chain D has already run or is still ahead. Cheapest check: The service's activity log, filtered to exports.
2. Unknown: Which of the six donor-management accounts belong to people who still work at the food bank. Why it changes the picture: Every account left behind is another way into Chain D at step two. Cheapest check: Compare the service's user list with the current staff list.
```

Ingest the output against the packet it answers. The model label
is your own statement — here it names the sample for what it is.
Paste the `sha256` from your packet output above in place of
`<packet hash>`:

```sh
fencewalk ingest walk.db sample-output.md --packet-hash <packet hash> --model "Example Model 1"
```

```text
ingested model run 1
packet hash: <64 hex characters>
output byte count: 2753
```

Ingest stores the output verbatim and changes nothing else: no
scores, no chains, no fixes, no verify-next items. Parsing the
output into the record is adjudication's work, and it is done by
hand in the next stage.

Render the draft. It splits the stored output at its deliverable
headings, reproduces each section verbatim, and follows each with
an adjudication stub:

```sh
fencewalk draft walk.db --run 1
```

```text
# Adjudication draft — Reference case — Marigold Community Food Bank perimeter audit

- Run: 1
- Packet hash: <64 hex characters>
- Model: Example Model 1
- Run date: 2026-11-26
```

The draft then carries the four sections in order — Coverage map,
Attack chains, Fix list, Verify-next list — each followed by the
stub. The sample file's own heading and introduction land in a
Preamble section at the top of the draft; the four deliverable
sections follow it.

```text
> **Adjudication**
> Decision: (accept / correct / reject)
> Correction or note:
```

## Stage 4 — adjudication

Decide each section against the inventory. The sample's coverage
map is mostly a second opinion on scores the fixture already
holds — R-1.1 Partial and R-2.1 Unknown agree with the fixture —
but its R-3.2 reading is wrong: it says Not applicable because
there is no client portal. R-3.2 is not only about a client
portal: the scheduling app shows every volunteer the full roster
with mobile numbers (D3), and the sample's own chain D names R-3.2
as its control. That section is a `correct`, and the note is the
correction:

```sh
fencewalk adjudicate walk.db --run 1 --section coverage --decision correct --note "R-3.2 reaches more than a client portal: the scheduling app shows every volunteer the full roster with mobile numbers, and the run's own chain D leans on R-3.2."
```

```text
recorded adjudication event 1 (run 1, coverage, correct)
```

The other three sections stand as the sample wrote them:

```sh
fencewalk adjudicate walk.db --run 1 --section chains --decision accept
fencewalk adjudicate walk.db --run 1 --section fixes --decision accept
fencewalk adjudicate walk.db --run 1 --section verify-next --decision accept
```

```text
recorded adjudication event 2 (run 1, chains, accept)
recorded adjudication event 3 (run 1, fixes, accept)
recorded adjudication event 4 (run 1, verify-next, accept)
```

A decision never applies anything by itself. Check the standings:

```sh
fencewalk adjudications walk.db --run 1
```

```text
coverage: correct (2026-11-26, operator)
  note: R-3.2 reaches more than a client portal: the scheduling app shows every volunteer the full roster with mobile numbers, and the run's own chain D leans on R-3.2.
chains: accept (2026-11-26, operator)
fixes: accept (2026-11-26, operator)
verify-next: accept (2026-11-26, operator)
Current standings:
coverage: correct
chains: accept
fixes: accept
verify-next: accept
```

Decisions are append-only events: adjudicating a section again
adds a new event, and the section's standing is its latest.
Accepting the sample changes no score — the fixture arrives
already scored, so this run is a second opinion on the same
rubric.

### A second pass that attacks the scores

The packet in Stage 3 asks for scores blind. The adversarial
posture asks the opposite question: given the scores that stand,
where are they wrong? Assemble it:

```sh
fencewalk packet walk.db --posture adversarial --out adversarial-packet.md
```

```text
packet written to adversarial-packet.md
byte count: 26715
sha256: <64 hex characters>
posture: adversarial
```

The run-configuration block names the posture, and between the
brief and the inventory sits a standing-coverage section: each of
the 20 scored items with its status, reasoning, N/A reason, and
cited entries with their labels. The brief asks, item by item, for
the strongest case that the status is wrong — evidence too thin
for it, reasoning that says more than the cited entries show,
citations that do not support it — and for the status the evidence
does support, or one line saying the score holds. Run it the way
you ran the Stage 3 packet, then `ingest` the output against this
packet's hash; `draft` and `adjudicate` work on it exactly as
above. The packet record notes the posture, so a standard run and
an adversarial one stay distinguishable. This walkthrough carries
no sample adversarial output, so it moves on.

### Calibration: how the runs compare with the record

Once runs have been adjudicated, `calibration` reads them back as
a prior for the next pass: for every run with a coverage
decision, each proposed status against the item's standing
status today.

```sh
fencewalk calibration walk.db
```

The header counts the population; the tables follow. With one
adjudicated run — the sample — the run-level and overall lines
read:

```text
- Runs qualifying: 1
- 0 runs not adjudicated for coverage — excluded
- 0 rows not readable — excluded
```

```text
| Run | Model | Run date | Posture | Compared | Agreement |
|---|---|---|---|---|---|
| 1 | Example Model 1 | 2026-11-26 | standard | 3 | 66.7% |
```

```text
| Compared | Agree | Model optimistic | Model pessimistic | N/A-involved | Standing unscored | Agreement |
|---|---|---|---|---|---|---|
| 3 | 2 | 0 | 0 | 1 | 0 | 66.7% |
```

R-1.1 and R-2.1 agree with the standing scores; the sample's
R-3.2 Not applicable, which you corrected above, is n/a-involved
against the standing Partial. The adversarial packet you
assembled has no ingested run, so its posture row reads zero. The
report closes with a note on how to read it: standing scores are
as of today, so a score changed since adjudication counts exactly
as an overturn does. Calibration only reads; the database is
unchanged.

## Stage 5 — fix tracking

Apply the adjudicated deliverables by hand, one command each.
The chain first — the sample's chain D, with its four steps in
the fixture's phase convention:

```sh
fencewalk add-chain walk.db --key D --name "Donor list exported through a staff donor-management login" --control "two-step sign-in on every donor-management account, with an alert on bulk exports" --control-status unknown --control-rubric R-3.2 --step "Reconnaissance: Staff names and work addresses are printed on appeal letters, and the donor-management service's sign-in page is public (D1)." --step "Initial access: One of the six staff passwords is phished or reused from another site's breach. This depends on an UNKNOWN: whether the service asks for a second factor at all (D2, H8)." --step "Privilege escalation: None needed if the account can run exports, which no record limits to the development director." --step "Collection-exfiltration: All 4,200 donor records, with home addresses and gift history, leave in one export. Whether any alert fires on a bulk export is UNKNOWN (D2)."
```

```text
added chain D (4 steps)
```

A step can also name the rubric item it exercises. Step 4 of
chain D only works while a full export of the donor list raises
no alert, which is R-3.2's ground. Name it on the chain you just
recorded (or name items as the chain is created, with
`--step-item 4=R-3.2` on `add-chain`):

```sh
fencewalk set-step-item walk.db --chain D --step 4 --item R-3.2
```

```text
chain D step 4: item R-3.2 (flash-20261113-001) (was none)
```

`--clear` removes a step's reference. Now the chain can be
computed. `chains` lists every chain with its steps, marks each
step that names an item with that item's standing status, and
derives the chain's exposure from those marks:

```sh
fencewalk chains walk.db
```

```text
Chain D: Donor list exported through a staff donor-management login
  Earliest breaking control: two-step sign-in on every donor-management account, with an alert on bulk exports (R-3.2, flash-20261113-001) Status: unknown.
  1. Reconnaissance: Staff names and work addresses are printed on appeal letters, and the donor-management service's sign-in page is public (D1).
  2. Initial access: One of the six staff passwords is phished or reused from another site's breach. This depends on an UNKNOWN: whether the service asks for a second factor at all (D2, H8).
  3. Privilege escalation: None needed if the account can run exports, which no record limits to the development director.
  4. Collection-exfiltration: All 4,200 donor records, with home addresses and gift history, leave in one export. Whether any alert fires on a bulk export is UNKNOWN (D2).
     item R-3.2 (flash-20261113-001) — Partial
  Exposure: contested at step 4, where R-3.2 (flash-20261113-001) is Partial; no annotated step is Covered. Derived from 1 of 4 steps (the one that names an item); the other steps are not judged.
  Related fixes: F-13 (proposed), F-15 (proposed)
```

(Chains A, B and C come first; their steps name no items yet, so
each says `Exposure: not computed` — never open, never safe.) A
chain is **interrupted** at its earliest step whose item is
Covered, **contested** when none is Covered but one is Partial or
Unknown, and **open** when every annotated step is Gap, Not
applicable, or unscored. Steps that name no item are shown
unmarked and not judged. Nothing is stored: rescore R-3.2 and the
next render re-derives the chain. The report's Attack chains
section gains the same derivation as one line under chain D's
control line, and changes nowhere else.

Then the two fixes. The fixture already holds F-1 through F-16,
so the sample's fixes take the next IDs:

```sh
fencewalk add-fix walk.db --id F-17 --action "Turn on two-step sign-in for every donor-management account, and remove the accounts of staff who have left." --effort "Minutes" --breaks D --rubric R-1.6
fencewalk add-fix walk.db --id F-18 --action "Limit full donor exports to the development director's account, and read the service's export history back to October 1." --effort "An hour" --breaks D --rubric R-3.2
```

```text
added fix F-17 (proposed)
added fix F-18 (proposed)
```

A fix is created `proposed`. F-18 maps R-3.2, so chain D's
related fixes now read F-13, F-15 and F-18. Then the two
verify-next items, which take the next sequence numbers, 11 and
12:

```sh
fencewalk add-verify-next walk.db --unknown "Whether the donor-management service's export history shows any full export since October 1." --why "It decides whether Chain D has already run or is still ahead." --check "The service's activity log, filtered to exports."
fencewalk add-verify-next walk.db --unknown "Which of the six donor-management accounts belong to people who still work at the food bank." --why "Every account left behind is another way into Chain D at step two." --check "Compare the service's user list with the current staff list."
```

```text
added verify-next item 11
added verify-next item 12
```

Move one fix to done. `set-fix-status` is the only path that
moves a fix, and it refuses a same-status no-op. On this
fictional fixture the transition is a demonstration of the
command, not a claim that the work was done — in a real
engagement you move a fix only when the work is actually done.

```sh
fencewalk set-fix-status walk.db F-17 done
```

```text
F-17 status set to done
```

To work one fix by hand, render its packet:

```sh
fencewalk fix-packet walk.db F-17
```

The packet carries F-17's action, its status history (proposed,
then done, each with its date and actor), and its one mapped item,
R-1.6, with the item's full rubric text, its current coverage
status and reasoning, and the cited entries with their labels.
Its Verify by rescore section lists R-1.6, which is not Covered:
moving the fix to done changed no score, and the rescore is
yours to make once the work is checked. Unlike `packet`, which
records the packet it assembles, `fix-packet` is a view: it
writes nothing to the database and records no run.

Now render the final report. The posture summary tells the
story of the whole loop:

```sh
fencewalk report walk.db
```

```text
## Posture summary

- Inventory: 52 entries (VERIFIED 16, ON RECORD 19, UNKNOWN 17)
- Coverage: Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows
- Attack chains: 4
- Fixes: 18 (proposed 14, approved 1, done 2, deferred 1)
- Verify-next items: 12
```

The inventory moved by one (E5 resolved), the chains by one
(D applied), the fixes by two (F-17, F-18 — F-17 done, and F-1
was already done in the fixture), the verify-next items by two
(11, 12). The coverage tallies are unchanged: accepting the
sample changed no score. And the report now ends with an
Adjudication section, which appears only when at least one
decision exists:

```text
## Adjudication

### Run 1 — Example Model 1 (2026-11-26)

- Packet hash: <64 hex characters>
- Coverage: correct (2026-11-26, operator) — note: R-3.2 reaches more than a client portal: the scheduling app shows every volunteer the full roster with mobile numbers, and the run's own chain D leans on R-3.2.
- Chains: accept (2026-11-26, operator)
- Fixes: accept (2026-11-26, operator)
- Verify-next: accept (2026-11-26, operator)
```

Render the same report as a PDF, for filing or handing to a
client:

```sh
fencewalk pdf walk.db --out walk.pdf
```

```text
pdf written to walk.pdf
```

The PDF is 6 pages, US Letter, and byte-identical if you render
it again from the same database — it carries no timestamps, and
its `/ID` is the SHA-256 of the gathered report data.

## Next — a real engagement

The fixture taught the loop; a real engagement starts empty:

```sh
fencewalk new eng.db --name "Example audit" --subject "Example firm" --method-order verify-first --date 2026-11-26
fencewalk import-inventory eng.db inventory.md
fencewalk load-pack eng.db flash-20261113-001
```

`new` creates the database and refuses to overwrite an existing
file. `import-inventory` reads a bundle-format Markdown inventory
into an empty inventory — multi-label bullets are skipped and
listed for manual entry, unlabeled bullets import as UNKNOWN, and
a VERIFIED checked date is read from the same sentence as its
marker. `load-pack` validates the whole pack file before it
inserts anything. From there the loop is the one you just ran:
checklist, packet, ingest, draft, adjudicate, apply, track.

The web interface serves one engagement database locally:

```sh
fencewalk serve walk.db
```

It binds `127.0.0.1:8090` by default. It has no authentication:
binding any other host prints a plain no-auth warning at startup.
A request whose Host header does not name the server (its bind
address or a loopback name, on its port) is refused with 403, a
form submission whose Origin host does not match the server's
Host is refused with 403, and every form carries a per-process
token that a submission must present. The pages are the same store
and the same computed counts as the CLI, rendered as HTML, with
no JavaScript.

## Keep the engagement in a local registry

Register the walkthrough database so you can find it again:

```sh
fencewalk register walk.db
fencewalk engagements
```

Registration prints the fixture's subject label and stores only
the canonical absolute path and registration date in
`~/.fencewalk/registry.json`. The listing reads the database's
current subject, name, created date, default pack, loaded pack
count, inventory count, and scored count for the default pack.
Neither command changes the database, including an older database
without a primary pack column.

For a separate scratch registry, pass `--registry ./registry.json`
to each command, or set `FENCEWALK_REGISTRY`; the flag wins over
the environment variable. Listing alone never creates a registry.
Missing databases list as `MISSING` with their paths and no counts.
An invalid registry file is an error and stays untouched.

Remove the listing when you finish the walkthrough:

```sh
fencewalk unregister walk.db
```

This removes only the registry entry; the database stays in place.
It also works after the database has been removed. Registering a
path twice or unregistering an unregistered path is refused.
`serve` continues to use a database path directly.

## See what a re-audit changed

A re-audit rescores items, sets labels, and moves fixes in the same
database. Copy the database first; afterwards, diff the copy against
the current one:

```sh
cp walk.db walk-before.db
fencewalk set-fix-status walk.db F-3 approved
fencewalk diff walk-before.db walk.db
```

The drift report lists F-3 under Fix changes (WAS proposed, NOW
approved, with the newer side's status date) and reads "No changes."
under Coverage changes and Inventory changes, with the unchanged
counts beneath each. Neither database is written. Two limits are
deliberate: the report compares statuses and labels, not text, so a
rescore that rewrites the reasoning but keeps the status counts as
unchanged; and it does not compare chains or verify-next items.
`diff` refuses two different engagements, and a `--pack` that is
not loaded in both databases.

For everything the walkthrough did not show, the README's
[command reference](../README.md#command-reference) lists every
command grouped by stage. If you are publishing a release rather
than using the tool, `RELEASING.md` is the checklist — for
publishers only.
