# Marigold Community Food Bank perimeter inventory — sample for the import tests

Compiled for the Fencewalk import tests. Status labels: **VERIFIED** = checked against a live source on the date given. **ON RECORD** = asserted in the operator's records, not freshly checked. **UNKNOWN** = not on record; the import must flag these, never assume them.

## A. Identity and mail

- Mail, calendars and files run on Microsoft 365 Business Standard. VERIFIED Nov 4, 2026.
- Two accounts hold the Global Administrator role. ON RECORD.
- Second-factor registration across staff accounts: **UNKNOWN.** The registration report has not been read.
- The donations@ sign-in log was read by the volunteer IT lead and the result was **reported as failures only**. VERIFIED as performed, Nov 4, 2026.
- NAS snapshot restore test result: VERIFIED.
- The camera's cloud viewer account belongs to the warehouse lead. It is excluded from all review activity.
- Security defaults are on for the tenant. ON RECORD. A new-browser sign-in asked for a second factor. VERIFIED Nov 4, 2026. Coverage of the shared mailboxes: **UNKNOWN.**

## B. Domain and DNS

- DNS for marigoldfoodbank.example is served by the website host. VERIFIED Nov 3, 2026.
- SPF lists Microsoft 365 and the donor-management service. ON RECORD from the Nov 3 check.

## H. Standing unknowns

1. Second-factor registration across staff accounts.
2. Whether the donations@ sign-in log has ever been read. **RESOLVED Nov 4, 2026:** the volunteer IT lead read it; failures only, no successful sign-in from abroad.
