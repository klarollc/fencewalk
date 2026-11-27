# Scrub audit note — github-org fixture

Like `reference-case` (an invented case, written as fiction from the
start) and unlike `demo-scuba` (derived from ScubaGear's published sample
reports), this fixture has no source dataset. It is written as fiction from
the start, so there is nothing to substitute away; this note records the
classes of identifier the fiction uses, and what was kept out. The scrub is
machine-checked: `tests/test_fixture_github_org.py` greps every file in
this directory for GUID, e-mail, IPv4, phone and token-shaped strings and
fails on any match outside the fictional domain.

## Identifier classes used

1. **Firm and domain.** Alder Creek Advisory LLC at `aldercreek.example`
   (the reserved `.example` top-level domain). The one hostname,
   `ci-old.aldercreek.example`, is under that domain.
2. **GitHub organization and repositories.** The organization login
   `aldercreek-advisory` and the repository names `client-portal`,
   `billing-tools`, `field-notes` and `brand-assets` are generic and
   invented; no repository of a real project is named.
3. **People.** Two owners, Dana Whitcomb and Theo Marsh, are invented
   names. Every other person is a role ("a staff member of a former IT
   vendor", "a former staff member"). No GitHub username of any person is
   carried.
4. **Third-party services.** The installed apps and webhook receivers are
   described by kind ("a CI service", "a chat notification app"), not by
   product name.
5. **Secrets and tokens.** Secrets are described by purpose ("a deployment
   credential", "a notification endpoint"); no secret name, token, key,
   fingerprint or webhook secret value appears.
6. **Network identifiers.** No IP address, CIDR range or phone number
   appears.
7. **Dates.** The engagement date, 2026-11-21, is the VERIFIED entries'
   checked date and the fixes' status date. Month-level dates in entry
   bodies (March, April, May and October 2026) are part of the fiction.
8. **Microsoft 365 references.** The SCuBA item IDs (`MS.AAD.3.1v1`,
   `MS.AAD.3.6v1`) are public baseline identifiers from the bundled SCuBA
   pack, not tenant data. No tenant ID, tenant domain or UPN is carried.

## Kept out

- No fact, count, name or wording from any real engagement. The fixture
  shares only a common shape with real small-firm GitHub reviews: an
  organization without a two-factor requirement as the headline gap.
- No CIS Benchmark content: every rubric item the fixture scores comes
  from the GitHub pack, which is curated from GitHub Docs.
- No output of any real `gh` or REST read: the inventory bodies state
  settings in prose; `docs/github-org-evidence.md` names the reads an
  operator would run.
