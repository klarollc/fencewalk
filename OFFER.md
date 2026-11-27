# Fencewalk

A local-first perimeter audit for small organizations.

## What it is

Fencewalk runs one repeatable method for auditing a small organization's
perimeter: build a structured, evidence-labeled inventory; score it against
a sourced rubric; run a bounded model pass; adjudicate the model's output
against the evidence; and track the fixes to done.

It is not a scanner. Evidence enters through the operator — console reads,
exports, captures — and the tool's value is the evidence discipline. Every
inventory entry carries a label: VERIFIED (checked, with date and source),
ON RECORD (asserted in the operator's records, not freshly checked), or
UNKNOWN. UNKNOWN is a first-class value that nothing silently upgrades.

## What it does — five stages, one loop

1. **Intake.** Build the inventory in sections, every entry evidence-labeled.
2. **Verification.** A checklist generated from the UNKNOWN entries; resolved
   unknowns return as VERIFIED with dates.
3. **Model pass.** A single self-contained packet the operator runs in their
   own model session — or through `run-model`, which calls the operator's
   own model provider with the operator's own key. Either way, the output
   enters the record only through adjudication. The packet can also be
   assembled in an adversarial posture: a second pass briefed to refute
   the standing scores, not repeat them.
4. **Adjudication.** Review the returned output against the inventory —
   accept, correct, or reject, with corrections preserved verbatim.
5. **Fix tracking.** Each fix carries a rubric citation, an effort estimate,
   the chain it breaks, and a status that changes only on the operator's
   explicit action. A chain whose steps name the items they exercise gets
   a computed exposure, derived from the standing scores at render time.

The loop also keeps score of itself. A **calibration** report compares
every adjudicated model proposal with the standing record — by group,
posture, and run — so the operator can see where the model runs
optimistic and where it runs pessimistic. **Probes** record behavioral
checks, the operator doing the thing a control claims to govern, against
the items they test; the Covered and Partial items with no probe on
record are listed by name.

## Who it's for

Small organizations — nonprofits, small firms — with a perimeter spread
across Microsoft 365 or Google Workspace, GitHub, and their own domains,
and no security team. Operators who want a defensible record of
what was checked, what is unknown, and what is fixed. The method is free
and open source (MIT), so anyone can run it themselves.

## How to run it

Python 3.11 or later, standard library only, zero dependencies. From the
repo root:

```sh
# Start an engagement from the included reference fixture
PYTHONPATH=src python -m fencewalk load-fixture reference-case /tmp/reference.db

# Or start your own: new, import-inventory, load-pack, checklist,
# packet, ingest, draft, adjudicate, report
PYTHONPATH=src python -m fencewalk serve /tmp/eng.db   # http://127.0.0.1:8090
```

The web interface is the same store and the same computed counts as the
CLI, in the browser — read-only pages, verification writes, and the model
pass with adjudication.

## Two ways in

- **Run it yourself.** Free, MIT-licensed — github.com/klarollc/fencewalk
- **Have Klaro run it.** Klaro Impact Consulting runs the engagement for
  you: inventory, verification, model pass, adjudication, fix tracking,
  and a filed report. Book a call:
  https://bookings.cloud.microsoft/book/Klaro@klaroimpactconsulting.com/

## Provenance

Built from the ARTEX advisory method (FBI FLASH-20261113-001); the rubric
pack ships with the tool, and the reference case is included. First real
engagement: Klaro's own perimeter, November 2026 — 46 entries, 20 rubric
items scored, 21 fixes tracked.

Fencewalk reports findings; it does not guarantee security. A clean report
is evidence about the checks that ran, not proof that nothing is wrong.
