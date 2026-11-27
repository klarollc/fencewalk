# Scrub audit note — google-workspace fixture

Like `github-org` and `dns-registrar`, this fixture has no source dataset:
it is fiction from the start, so there is nothing to substitute away. This
note records the classes of identifier the fiction uses and what was kept
out. The scrub is machine-checked: `tests/test_fixture_google_workspace.py`
greps every file in this directory for GUID, e-mail, IPv4, phone, OAuth
client-ID and real-hostname-shaped strings and fails on any match outside
the fictional `.example` domain.

## Identifier classes used

1. **Firm and domain.** Larkspur Advisory LLC at `larkspur.example`, under
   the reserved `.example` top-level domain.
2. **People.** Roles only: the founder, the office manager, the
   bookkeeper, eight staff. No name, username or e-mail address of any
   person is carried.
3. **Vendors and apps.** The domain-wide delegation client, the SIEM the
   firm does not have, and any third-party app are described by role. No
   client ID, service account, project ID or app name appears.
4. **Google product and setting names.** Google Workspace, Gmail, Drive,
   Meet and the Admin console's setting names are the product's own names,
   kept so the entries read against the baseline.
5. **CISA references.** Policy IDs (`GWS.*`) and the ScubaGoggles release
   are the pack's public source. The federal reporting address named in
   GWS.GMAIL.4.3v1 appears only in the pack file, never in this
   directory.
6. **Network identifiers.** No IP address, CIDR range or phone number
   appears.
7. **Dates.** The engagement date, 2026-11-18, is the ScubaGoggles run
   date, the VERIFIED entries' checked date and the fixes' status date.
   The year 2021 (when the firm moved to Google Workspace) is part of the
   fiction.

## Kept out

- No fact, count, name or wording from any real engagement or tenant.
- No ScubaGoggles output: the B, C, D and E entries state what such a run
  reported, in prose; no report file is included.
- No Google Admin Help text: Google's edition documentation decided which
  rows are Not applicable and is cited in `docs/google-workspace-evidence.md`;
  none of it is copied.
- No CIS Benchmark content.
