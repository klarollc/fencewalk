# Reference-case fixture

The golden reference case for Fencewalk acceptance: a complete engagement
(inventory, rubric coverage, attack chains, fixes, verify-next) stored as
data files, from which the fixture loader builds an engagement database and
the report renderer reproduces the adjudicated record.

**This case is fictional.** Marigold Community Food Bank was invented for
Fencewalk and has no real-world counterpart: the town, the people, the
domains (all under `.example`), and every fact in these files are made up,
and none of it is derived from any real engagement. See `PROVENANCE.md` for
the fixture's history.

The invented firm: a small nonprofit food bank with fourteen staff and about
sixty volunteers, a Microsoft 365 Business Standard tenant, a hosted website
taking donations through a payment processor's hosted checkout, a
donor-management service, a volunteer-scheduling app, and a small warehouse
(a NAS, label printers, one camera), with volunteers and drivers on their own
phones.

## Files

- `engagement.json` — engagement name, subject label, created date, method
  order (`verify-first`), and `pack_file`, the rubric pack this engagement
  scores against (the FLASH pack, resolved relative to this directory).
- `inventory.json` — inventory entries: `entry_id` (section letter + number),
  `section` (A–H), `body`, `label` (VERIFIED / ON RECORD / UNKNOWN),
  `source`, and `checked_date` (set for VERIFIED entries). Sections: A
  identity and mail, B domain and DNS, C public website and donations, D
  donor and volunteer services, E warehouse and office network and devices,
  F data and backups, G people and response, H the standing unknowns (H1–H8).
- `coverage.json` — one score per rubric item: `status`, `reasoning`,
  `cited_entry_ids`, and `na_reason` for the Not applicable rows. The two
  N/A rows cite no entries and rest on their written reasons.
- `chains.json` — the three attack chains: ordered steps with phases,
  earliest-breaking control, its rubric ID where one fits (chain C's control
  has none), and its status. No step names a rubric item; the tests annotate
  steps at runtime.
- `fixes.json` — fixes F-1 through F-16: action, rubric citations (F-4 and
  F-8 have none: backup versioning and shared-mailbox sign-in fall outside
  the FLASH rubric), effort, chains broken, and status with date and actor.
  F-1 is `done`, F-2 `approved`, F-16 `deferred`, the rest `proposed`, all
  as of 2026-11-05 (actor `operator`).
- `verify_next.json` — the 10 verify-next items: the unknown, why it changes
  the picture, and the cheapest check.
- `EXPECTED-REPORT.md` — the report rendered from this fixture by the
  documented command; its tallies are the acceptance numbers (see the
  acceptance test in `tests/`).

## Acceptance numbers

Loading this fixture and rendering the report reproduces: 52 inventory
entries (VERIFIED 15, ON RECORD 19, UNKNOWN 18), 20 coverage rows (Covered 3,
Partial 8, Unknown 5, Not applicable 2, Gap 2), 3 chains, 16 fixes (proposed
13, approved 1, done 1, deferred 1), 10 verify-next items.
