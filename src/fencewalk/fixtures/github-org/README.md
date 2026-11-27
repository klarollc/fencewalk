# GitHub-org fixture

A public demo dataset for Fencewalk's GitHub organization security pack
(`github-org-security-1.0`): a complete engagement (inventory, rubric
coverage, attack chains, fixes, verify-next) for a fictional firm's GitHub
organization. It is the third bundled fixture, beside `reference-case`
(FLASH) and `demo-scuba` (SCuBA), and it carries the first **cross-pack
chain**: chain A's earliest breaking control is an item in the SCuBA pack,
and so is fix F-9's citation.

## The fiction

Alder Creek Advisory LLC (`aldercreek.example`) is a small advisory firm
with one GitHub organization, `aldercreek-advisory`, on the GitHub **Team**
plan: 12 members, 4 outside collaborators, 11 repositories (generic names:
`client-portal`, `billing-tools`, `field-notes`, `brand-assets`). Its two
owners also sign in to the firm's Microsoft 365 tenant with the same
identities, and the firm's own Microsoft 365 review (recorded ON RECORD in
entry H1, not re-tested) has phishing-resistant MFA not yet enforced for the
highly privileged roles. Everything here is invented; see `SCRUB.md`.

The plan matters. On Team, SAML single sign-on, IP allow lists and
restricted email notifications are not offered (GitHub Docs: each requires
GitHub Enterprise Cloud), so GH-ID-03, GH-ID-04 and GH-ID-05 are Not
applicable, each with that reason. Whether the plan should change is
verify-next item 1.

## Files

- `engagement.json` — name, subject label, created date (2026-11-21),
  method order `verify-first`, `pack_file` (the GitHub pack), and
  `extra_pack_files`: the SCuBA pack, loaded beside it so chain A and F-9
  can cite `MS.AAD.3.6v1`.
- `inventory.json` — 24 entries in sections A–H (A organization, owners and
  authentication; B membership and collaborators; C programmatic access;
  D GitHub Actions; E code security; F webhooks; G audit; H the linked
  Microsoft 365 tenant). Settings read on the organization's own pages are
  VERIFIED with the engagement date; what the owners state is ON RECORD;
  what nobody has checked is UNKNOWN. `docs/github-org-evidence.md` names
  the read behind each entry.
- `coverage.json` — one score per pack item (34), each citing the entries
  that ground it. The three Not-applicable rows carry the plan reason as
  their `na_reason`.
- `chains.json` — A, organization takeover through an owner's Microsoft 365
  account (control `MS.AAD.3.6v1`, `control_pack` `scuba-m365-v2.0.0`);
  B, malicious workflow through a public repository (control `GH-ACT-02`);
  C, persistence through a dormant collaborator and a stale webhook (control
  `GH-MEM-03`). All three controls are Gap.
- `fixes.json` — F-1 through F-9, all `proposed`, actor `operator`, dated
  2026-11-21. F-9 cites `MS.AAD.3.6v1` with `rubric_pack_id`
  `scuba-m365-v2.0.0`.
- `verify_next.json` — five items, one per open question: the plan, the
  installed apps still in use, the stale webhook's endpoint, the second
  owner's two-factor methods, and the classic tokens. Four match the
  UNKNOWN entries (A5, C3, C4, F3); the first rests on A1 and A6.
- `EXPECTED-REPORT.md` — the report rendered from this fixture by
  `fencewalk report <db> --out ...`. It renders the GitHub pack (the
  engagement's primary pack); chain A's control and F-9's citation
  carry the `(scuba-m365-v2.0.0)` annotation.

## Load it

```sh
fencewalk load-fixture github-org gh.db
fencewalk report gh.db
fencewalk packet gh.db --date 2026-11-21 --out gh-packet.md
fencewalk pdf gh.db --out gh.pdf
```

## Acceptance numbers

Loading this fixture and rendering the report reproduces: 34 coverage rows
(Covered 5, Partial 3, Unknown 2, Not applicable 3, Gap 21), 3 chains,
9 fixes (all proposed), 5 verify-next items, 24 inventory entries
(VERIFIED 17, ON RECORD 3, UNKNOWN 4).
