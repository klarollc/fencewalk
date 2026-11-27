# Google-workspace fixture

A public demo dataset for Fencewalk's CISA SCuBA Google Workspace pack
(`scuba-gws-v1.1.0`): a complete engagement (inventory, rubric coverage,
attack chains, fixes, verify-next) for a fictional firm's Google Workspace
tenant. It is the fifth bundled fixture. Like `github-org` it composes a
second pack: the DNS and registrar pack is loaded beside the GWS pack, so
chain B's control and fix F-2 cite `DNS-EM-04` there.

## The fiction

Larkspur Advisory LLC (`larkspur.example`) is an eleven-person advisory
firm that has run on Google Workspace **Business Standard** since 2021.
The founder is the one super admin; the office manager holds a limited
admin role. The basics were turned on at setup and never revisited. The
operator ran CISA's ScubaGoggles v1.1.0 against the tenant for this audit;
its results are recorded ON RECORD (entries B1–B4, C1, D1, E1), and the
console and DNS reads that confirm them are VERIFIED. Everything here is
invented; see `SCRUB.md`.

The edition matters. The baselines assume Enterprise Plus. Five policies
govern features Google's edition documentation puts outside Business
Standard (Context-Aware Access, the data processing region, multi-party
approval, and DLP twice); they score Not applicable with the edition named.
One more, GWS.GMAIL.4.3v1, scores Not applicable because its literal
requirement (aggregate reports to a U.S. federal address) is a federal
obligation. Five more are conditional and their condition does not hold
here (no SSO profile; external sharing and receiving allowed; Calendar
Interop off); they score Not applicable with the unmet condition named.

## Render it

Two packs are loaded. Loading records the GWS pack (`pack_file`) as the
engagement's primary pack, so `report`, `packet` and `pdf` render it by
default, although the DNS pack sorts first. `--pack scuba-gws-v1.1.0`
names it explicitly and renders the same bytes:

```sh
fencewalk load-fixture google-workspace gws.db
fencewalk report gws.db
fencewalk packet gws.db --date 2026-11-18 --out gws-packet.md
fencewalk pdf gws.db --out gws.pdf
```

## Files

- `engagement.json` — name, subject label, created date (2026-11-18),
  method order `verify-first`, `pack_file` (the GWS pack) and
  `extra_pack_files` (the DNS pack).
- `inventory.json` — 20 entries in sections A–F (A tenant, accounts, admin
  roles and audit log; B ScubaGoggles Common Controls results and API
  controls; C Gmail and mail authentication; D Drive and Docs; E Chat, Meet,
  Calendar, Groups and Sites; F how the firm moves money).
  `docs/google-workspace-evidence.md` names the read behind each entry.
- `coverage.json` — one score per GWS pack item (124), each citing the
  entries that ground it.
- `chains.json` — A, credential phishing to payment diversion (control
  `GWS.COMMONCONTROLS.1.1v1`); B, self-spoof business email compromise
  (control `DNS-EM-04`, `control_pack` `dns-registrar-security-1.0`);
  C, link sharing exposure (control `GWS.DRIVEDOCS.1.5v1`). All three
  controls are Gap.
- `fixes.json` — F-1 through F-12, all `proposed`, actor `operator`, dated
  2026-11-18. F-2 cites `DNS-EM-04` and `DNS-EM-05` with `rubric_pack_id`
  `dns-registrar-security-1.0`, and states how its quarantine-first path
  differs from GWS.GMAIL.4.2v1.
- `verify_next.json` — five items: the open edition question for
  GWS.COMMONCONTROLS.14.1v1, and the four UNKNOWN entries (A4, B5, D3, E2).
- `EXPECTED-REPORT.md` — the report rendered by
  `fencewalk report <db> --out ...` (or with `--pack scuba-gws-v1.1.0`,
  the same bytes). Chain B's
  control and F-2's citations carry the `(dns-registrar-security-1.0)`
  annotation.

## Acceptance numbers

Loading this fixture and rendering the report reproduces: 124 coverage rows (Covered 45, Partial 4,
Unknown 4, Not applicable 11, Gap 60), 3 chains, 12 fixes (all proposed),
5 verify-next items, 20 inventory entries (VERIFIED 6, ON RECORD 10,
UNKNOWN 4).
