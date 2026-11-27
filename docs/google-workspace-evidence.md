# Gathering evidence for the Google Workspace pack

How an operator gathers the evidence that `scuba-gws-v1.1.0` is scored
against, for their own organization's Google Workspace tenant. Fencewalk
adds no importer and no network code for this: you run CISA's ScubaGoggles
against your own tenant, read the Admin console, and run DNS queries, then
record what you see as inventory entries and scores through the existing
CLI or web paths (`add-entry`, `score`).

## Rules

- **Read-only.** Nothing below changes a setting. ScubaGoggles reads the
  tenant's configuration and writes its report to your machine.
- **Your own admin credentials.** ScubaGoggles needs a Super Admin
  session (its prerequisites page says so); run it yourself, or with the
  tenant's super admin, from your own machine. The Admin console reads
  need an admin role that can see the page.
- **Nothing secret in Fencewalk.** Never record a password, OAuth token,
  service-account key, client secret or recovery code in an inventory
  entry. Record settings and counts in prose, as the bundled
  `google-workspace` fixture does. Keep ScubaGoggles' report files
  outside the engagement database.
- `DOMAIN` below is the tenant's primary domain.

Each read is marked **ScubaGoggles** (CISA's assessment tool, the primary
route for configuration items), **Admin console** (a settings or report
page, named by what it shows; Google moves and renames these pages), or
**DNS query** (for the mail-authentication items; the queries themselves
are in `docs/dns-registrar-evidence.md`, group 4).

## Sources

- The pack's items: CISA SCuBA Google Workspace baselines as published
  with ScubaGoggles v1.1.0
  (https://github.com/cisagov/ScubaGoggles/releases/tag/v1.1.0, tag commit
  `08a08ce145178582284d81ab1f3625987f3ad66b`), CC0 1.0 Universal. Three
  baselines in that release are not included: Classroom (an
  education-sector product), Gemini and Assured Controls (separately
  purchased add-ons).
- The edition determinations (which items are Not applicable on an edition
  below Enterprise Plus), never the item text: Google Workspace's edition
  and feature-availability documentation, retrieved 2026-11-24 —
  - Context-Aware Access: https://support.google.com/a/answer/9275380
  - Exporting logs to BigQuery: https://support.google.com/a/answer/9079364
  - Data regions (storage, and the data processing setting):
    https://support.google.com/a/answer/7630496
  - Multi-party approval: https://support.google.com/a/answer/13790448
  - Gmail security sandbox: https://support.google.com/a/answer/7676854
  - DLP for Drive: https://support.google.com/a/answer/9655387
  - The plan comparison: https://workspace.google.com/pricing.html

## Editions

Every baseline file says it assumes Enterprise Plus. On a lower edition,
some settings do not exist. Score such an item **Not applicable** only
when the baseline's own text, or Google's edition documentation above,
puts the feature outside the tenant's edition, and name the edition in the
reason. Read the tenant's edition on the Admin console's billing page
(group 1, read 1) and record it as an inventory entry: every edition-gated
row cites it. Where the documentation leaves the question open, score the
setting as observed and put the question on the verify-next list.

A second Not-applicable class covers items whose literal requirement is a
U.S. federal obligation (for example GWS.GMAIL.4.3v1, which directs DMARC
aggregate reports to a federal address); name the obligation in the
reason. A third covers conditional policies whose own condition does not
hold in the tenant (for example a post-SSO verification policy where no
SSO profile is configured); name the unmet condition in the reason, and
score the setting the condition depends on in its own row.

## 1. Common Controls (GWS.COMMONCONTROLS.*)

1. **Admin console** — billing (subscriptions) and account settings: the
   edition, the user count and the primary domain.
2. **Admin console** — the 2-Step Verification settings page and the
   users list's enrollment column: whether 2SV is enforced, and each
   user's method.
3. **Admin console** — admin roles and each role's assigned admins: how
   many super admins, and which accounts hold any admin role.
4. **ScubaGoggles** — `scubagoggles gws -b commoncontrols -o <dir>`:
   results for every Common Controls policy (authentication, sessions,
   passwords, recovery, Advanced Protection, API controls, Marketplace,
   Takeout, alert rules, data regions, additional services, multi-party
   approval, DLP). Record the run (version, date, who ran it) as its own
   ON RECORD entry and summarize its results by section.
5. **Admin console** — Security > API controls > Domain-wide delegation:
   every client holding domain-wide delegation, and its scopes. Who owns
   each client is a question for the people.
6. **Admin console** — the Reporting audit and investigation pages: which
   logs are searchable and for how long; whether any export or SIEM feed
   exists. Whether anyone reviews them is a question for the people.

## 2. Gmail (GWS.GMAIL.*)

1. **ScubaGoggles** — `scubagoggles gws -b gmail -o <dir>`: results for
   every Gmail policy (delegation, attachment, link and spoofing
   protections, uploads, POP and IMAP, Sync, forwarding, gateways,
   warnings, allowlists, pre-delivery scanning, sandbox, comprehensive
   mail storage, spam bypass).
2. **DNS query** — SPF, DKIM and DMARC for `DOMAIN`, as in
   `docs/dns-registrar-evidence.md` group 4: the SPF record's final
   mechanism, the DKIM selector's key, the DMARC `p`, `sp`, `np`, `rua`
   and `ruf` tags. ScubaGoggles reads the same records.
3. **Admin console** — Apps > Gmail > Authenticate email: whether Gmail
   is signing with DKIM for each domain.
4. Whether anyone reads the DMARC report mailbox is a question for the
   people.

## 3. Drive and Docs (GWS.DRIVEDOCS.*)

1. **ScubaGoggles** — `scubagoggles gws -b drive -o <dir>`: results for
   every Drive and Docs policy (external sharing, receiving, warnings,
   link sharing, access checking, shared drives, default access, SDK,
   Drive for desktop).
2. **Admin console** — the Drive log events report: items shared
   "anyone with the link", and which of them are client folders.
3. Where ScubaGoggles reports a policy as a manual check (for example
   ransomware monitoring for Drive for desktop), read the Drive and Docs
   settings page in the Admin console.

## 4. Google Chat, Meet, Calendar, Groups and Sites

1. **ScubaGoggles** — `scubagoggles gws -b chat meet calendar groups
   sites -o <dir>`: results for every policy in those baselines.
2. **Admin console** — where ScubaGoggles reports a manual check (for
   example the Meet meeting-notes settings), read that product's settings
   page.

## 5. Context outside the tenant

How the firm moves money (who acts on emailed payment instructions, and
whether anyone calls back) is a question for the people. It grounds the
chains' impact steps, not any rubric item.

## Reads to inventory entries

The `google-workspace` fixture's entries, with the reads that ground them:

| Entry | Grounded by |
|---|---|
| A1 | Group 1 read 1 |
| A2 | Group 1 read 2 |
| A3 | Group 1 read 3 |
| A4 | Not readable by the operator: the account holder's own security page (UNKNOWN) |
| A5 | Group 1 read 6 |
| A6 | Group 1 read 6, the people part (ON RECORD) |
| B1 | Group 1 read 4, the run itself (ON RECORD) |
| B2, B3, B4 | Group 1 read 4, by section (ON RECORD) |
| B5 | Group 1 read 5; owner not yet identified (UNKNOWN) |
| C1 | Group 2 read 1 (ON RECORD) |
| C2 | Group 2 reads 2–3 |
| C3 | Group 2 read 4 (ON RECORD) |
| D1 | Group 3 read 1 (ON RECORD) |
| D2 | Group 3 read 2 |
| D3 | Group 3 read 3, not yet made (UNKNOWN) |
| E1 | Group 4 read 1 (ON RECORD) |
| E2 | Group 4 read 2, not yet made (UNKNOWN) |
| F1 | Group 5 (ON RECORD) |

## Reads not confirmed

- Admin console pages are named here by what they show. Google renames
  and moves them; the paths given (Security > API controls > Domain-wide
  delegation, Apps > Gmail > Authenticate email) follow Google's Admin
  Help wording at the time of writing and were not checked against a live
  console.
- The ScubaGoggles command lines follow the tool's own usage
  documentation at v1.1.0 (`scubagoggles gws`, `-b` for baselines, `-o`
  for the output directory); none was run for this document.
- ScubaGoggles' interactive OAuth consent includes two scopes that are not
  `.readonly` (`apps.licensing`, `apps.groups.settings`), per its
  prerequisites page. The tool reads; whether either grant allows more
  than reading was not tested.
- Whether a SIEM route other than BigQuery export (for example the
  Reports API) is available on Business Standard was not settled from
  Google's documentation; the fixture leaves it as verify-next item 1.
