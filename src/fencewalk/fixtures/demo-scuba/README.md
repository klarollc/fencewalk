# Demo-scuba fixture

A public demo dataset for Fencewalk: a complete engagement (inventory,
rubric coverage, attack chains, fixes, verify-next) for a fictional firm,
derived from the sample reports that ship with CISA's ScubaGear v2.0.0.
It lets a new user run a realistic engagement end to end without
inventing data. The bundled reference case (`reference-case`, the
FLASH-scored Marigold engagement, wholly fictional) is unchanged; this is
a second fixture beside it.

## Source

- ScubaGear, `https://github.com/cisagov/ScubaGear.git`, tag `v2.0.0`
  (tag SHA `6e5a1a421b36c5a1fb3fd983b8c4bcd5b7a6c61d`). Licence:
  **CC0 1.0 Universal**, per the tag's `LICENSE` file.
- Inputs, all under `PowerShell/ScubaGear/Sample-Reports/` in the tag:
  `ScubaResults.csv` (the coverage source of record), `ActionPlan.csv`
  (the fixes), `ProviderSettingsExport.json` (the inventory, aggregate
  shapes only), and `RegoOutput.json` and the full results JSON
  (corroboration only). No sample-report file is copied into this
  repository, in whole or in part. The per-product HTML reports, debug
  logs, images and `RiskyApps.csv` were not used.
- The sample run is dated 2026-10-15; the engagement carries that date.

Every concrete identifier in the sample reports was replaced with one
obviously fictional tenant, Tidewater Advisory LLC at
`tidewateradvisory.example`. See `SCRUB.md`.

## Derivation

- **Coverage** (`coverage.json`): one score per row of `ScubaResults.csv`,
  109 rows for the 109 items of the bundled SCuBA pack
  (`scuba-m365-v2.0.0`). Result maps to status as Pass → Covered,
  Fail → Gap, Warning → Partial, N/A → Not applicable. `reasoning` is the
  row's Details field with HTML removed and whitespace collapsed, kept
  whole, with the scrub substitutions applied; for the N/A rows the same
  text is the `na_reason`. Unknown is 0 because a ScubaGear run
  determines every item it evaluates.
- **Inventory** (`inventory.json`): 30 entries in sections A–H (A Entra
  ID, B Exchange Online, C SharePoint and OneDrive, D Teams, E Power
  Platform, F Power BI, G Security Suite, H run configuration and
  standing unknowns). Each entry states an aggregate shape of the sample
  tenant (counts, settings, policy shapes) and names its source. Results
  read off the run are VERIFIED with the run date; run-configuration
  facts are ON RECORD; checks the tool cannot make are UNKNOWN.
- **Chains** (`chains.json`): four chains from the failing posture:
  A, takeover of a privileged administrator (Entra); B, illicit consent
  through a third-party application; C, anonymous links into SharePoint
  content; D, data movement through unrestricted Power Platform
  connectors. Each control rubric is a SCuBA pack item.
- **Fixes** (`fixes.json`): F-1 through F-15, one per Fail row, each
  citing its single rubric item. The action is the `ActionPlan.csv`
  finding rewritten as an imperative. All 15 are `proposed`, dated
  2026-10-15, actor `operator`: nothing was remediated in the sample
  tenant, and the fixture claims no remediation.
- **Verify-next** (`verify_next.json`): five items, one per product that
  carries Warning rows (Entra ID, Exchange Online, Power BI, Power
  Platform, Security Suite), each naming its Warning IDs.
- **Engagement** (`engagement.json`): method order `verify-first` (the
  scores are read off a tool run that verified the posture before
  anything was recorded); `pack_file` names the bundled SCuBA pack.
- `EXPECTED-REPORT.md` is the report rendered from this fixture by
  `fencewalk report <db> --out ...`.

## Load it

```sh
fencewalk load-fixture demo-scuba demo.db
fencewalk report demo.db
fencewalk packet demo.db --date 2026-10-15 --out demo-packet.md
fencewalk pdf demo.db --out demo.pdf
```

## Acceptance numbers

Loading this fixture and rendering the report reproduces: 109 coverage
rows (Covered 72, Partial 14, Unknown 0, Not applicable 8, Gap 15),
4 chains, 15 fixes (all proposed), 5 verify-next items, 30 inventory
entries (VERIFIED 23, ON RECORD 2, UNKNOWN 5).
