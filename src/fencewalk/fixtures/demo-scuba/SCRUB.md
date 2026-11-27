# Scrub audit note — demo-scuba fixture

The fixture in this directory is derived from the sample reports published
with ScubaGear v2.0.0 (CC0 1.0 Universal). Those reports are not clean: they
carry a real tenant's identifiers. None of them enters this repository. This
note lists every substitution class applied and the identifier load
measured in the inputs, so a reviewer can audit the scrub against the
public tag. Unlike the reference fixture, this scrub is also machine-checked:
`tests/test_fixture_demo_scuba.py` greps every file in this directory for
GUID, e-mail and IPv4 patterns and fails on any match outside the fictional
tenant.

## Measured identifier load in the inputs

Distinct values per file, counted on the pinned tag. The naive e-mail
pattern also matches OData type annotations (a property name, an at-sign,
then `odata.type`), so e-mail-shaped strings are split into OData artifacts and real addresses.

| file | GUIDs | e-mail-shaped | of which OData | real addresses | IPv4-shaped |
|---|---|---|---|---|---|
| ScubaResults.csv | 0 | 1 | 0 | 1 | 0 |
| ActionPlan.csv | 0 | 0 | 0 | 0 | 0 |
| RegoOutput.json | 29 | 63 | 60 | 3 | 5 |
| ProviderSettingsExport.json | 650 | 244 | 236 | 8 | 11 |
| results JSON (full document) | 650 | 243 | 236 | 7 | 11 |

The real addresses are placeholder accounts at `example.com`, plus one
government address (below). Every IPv4-shaped string is a version
number (for example an Exchange object version or an alert-policy
`-V1.0.0.x` suffix), not a network address. The count depends on the
pattern: one that skips the `-V` suffixes counts fewer.

## Substitution classes

1. **Tenant identity.** The sample tenant's display name, its initial
   Microsoft-assigned tenant domain, the tenant ID and the report UUID → one
   fictional firm, Tidewater Advisory LLC, at `tidewateradvisory.example`.
   The initial domain appears in one CSV Details field (MS.EXO.3.1v1) and is
   mapped onto `tidewateradvisory.example`. The tenant ID, report UUID and
   display name are dropped, not mapped.
2. **People.** The two Global Administrator display names in the
   MS.AAD.7.1v1 Details field → role labels ("the principal, the second
   global administrator"). No other person name is carried; the
   privileged-user records contribute counts and role names only.
3. **E-mail addresses.** The tenant's technical notification address (an
   `example.com` placeholder) → `admin@tidewateradvisory.example`. The
   DMARC aggregate-report address → `reports@dmarc.tidewateradvisory.example`.
   The one address in `ScubaResults.csv`, CISA's DMARC reporting address in
   the `dmarc.cyber.dhs.gov` domain, is a real government address, not a
   tenant UPN; it is not reproduced here. It sits in the MS.EXO.4.3v1
   Requirement column, not in Details, so it never reaches the fixture. The
   fixture's DMARC entry (B2) records the fictional address in its place. No
   UPN of any account is carried.
4. **Phone number.** The tenant record's placeholder business phone → the
   fictional (555) 010-0177. The reference fixture uses 0142.
5. **GUIDs.** Every GUID is dropped: tenant ID, report UUID, service-plan
   IDs, object, policy, group and application IDs. The fixture contains no
   GUID.
6. **IP addresses.** None exist in the inputs (see above), and none are
   written.
7. **Timestamps.** Only the sample run date, 2026-10-15, is carried. It is
   the engagement date, the VERIFIED entries' checked date and the fixes'
   status date. Assignment, sync and creation timestamps are dropped.
8. **Policy and object names.** Conditional Access policies, roles, licences
   and settings are described by shape (counts, states, exclusion counts,
   setting values), not by tenant-chosen object names. Microsoft product,
   role and licence names are third-party product names and are kept.

## Preserved exactly

- The 109 results, one per SCuBA item, and every result → status mapping.
- Each CSV Details field, cleaned of markup but otherwise whole, with only
  the substitutions above.
- Counts measured from the export (users, privileged users and roles,
  policies, environments, settings).

## Not carried

The per-product HTML and JSON reports, `BaselineReports.html`, debug logs,
images and `RiskyApps.csv` are not inputs and nothing from them is in this
directory.
