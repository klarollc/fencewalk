# Engagement report — Reference case — Marigold Community Food Bank perimeter audit

- Subject: Marigold Community Food Bank (fictional reference firm)
- Engagement created: 2026-11-05
- Method order: verify-first
- Rubric pack: ARTEX mitigations rubric (FBI FLASH-20261113-001, "Threat Overview of ARTEX Autonomous Penetration Testing Framework," Nov 13, 2026, TLP:CLEAR)

## Posture summary

- Inventory: 52 entries (VERIFIED 15, ON RECORD 19, UNKNOWN 18)
- Coverage: Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows
- Attack chains: 3
- Fixes: 16 (proposed 13, approved 1, done 1, deferred 1)
- Verify-next items: 10

## Coverage

Tallies: Covered 3 · Partial 8 · Unknown 5 · Not applicable 2 · Gap 2 — 20 rows

| Item | Group | Status | Reasoning | Cited entries |
|---|---|---|---|---|
| R-1.1 | Group 1 — Reduce external attack surface | Partial | The website, hosted checkout, donor-management service and scheduling app are known, but the NAS login page (E1) and the camera's cloud viewer (E6) were on no list until this audit, and whether the router's admin page is exposed is UNKNOWN. | C1, C5, D1, D3, E1, E5, E6 |
| R-1.2 | Group 1 — Reduce external attack surface | Gap | The NAS's web admin login answers from the internet through a port forward (E1, VERIFIED Nov 3), behind one admin password shared by three shift leads (E4), on firmware of unknown age (E3). | E1, E3, E4 |
| R-1.3 | Group 1 — Reduce external attack surface | Partial | Nothing is deployed from a repository, so the publishing paths are the CMS admin page and SFTP (C1); the SFTP login is one shared password unchanged since the 2023 agency handover (C2), and two agency admin accounts remain in the CMS (C3) with two-step sign-in UNKNOWN (C4). | C1, C2, C3, C4 |
| R-1.4 | Group 1 — Reduce external attack surface | Not applicable | Marigold deploys no application of its own; the website is a hosted CMS edited in place. N/A reason: No deployed application exists for a package model to protect: the site is a managed CMS on the host's platform, edited through its admin page. | — |
| R-1.5 | Group 1 — Reduce external attack surface | Gap | No rule governs what gets exposed: the NAS forward was opened by a volunteer in 2024 with no recorded approval (E2), and no one re-checked it until this audit (E1). | E1, E2 |
| R-1.6 | Group 1 — Reduce external attack surface | Partial | Mail and files sit behind Microsoft 365 sign-in with security defaults (A3), but the NAS, which holds the client-intake and inventory spreadsheets (F1), is reached through a raw port forward rather than any access gateway, and other routes in from home are UNKNOWN (E8). | A3, E1, E8, F1 |
| R-2.1 | Group 2 — Harden identity and access | Unknown | Three connected apps are known by name (A7); their permissions, who consented, and whether staff can consent to new apps alone are not on record (A8). | A7, A8 |
| R-2.2 | Group 2 — Harden identity and access | Partial | The default alert policies are on (A10), so admin and app changes do raise an email, but it is filed into a rarely opened folder in one inbox; nothing watches app credentials or app-only activity. | A10 |
| R-2.3 | Group 2 — Harden identity and access | Unknown | The managed IT provider that ran the tenant until June 2025 never wrote down what it connected (A9), so whether any of the advisory's affected applications were ever authorized here cannot be said from the record. | A9 |
| R-2.4 | Group 2 — Harden identity and access | Unknown | No one has looked at service-principal sign-ins; the only sign-in activity reviewed is the user-side failures against donations@ (A6). | A6 |
| R-2.5 | Group 2 — Harden identity and access | Partial | Admin role assignments were read on Nov 4 (A2, VERIFIED): two global admins and nothing else. App credentials, owners, consent grants, authentication-method changes and group changes were not reviewed (A8). | A2, A8 |
| R-2.6 | Group 2 — Harden identity and access | Not applicable | Marigold runs no certificate authority and no Windows Server; laptops sign in with Microsoft 365 accounts and the NAS keeps its own local accounts. N/A reason: Nothing in the inventory issues certificates or runs a directory on premises: identity is Microsoft 365 only. | — |
| R-3.1 | Group 3 — Strengthen application protections | Covered | The one high-impact business function exposed, taking donations, runs on the processor's hosted checkout with card-testing protection and attempt limits (C5), volume alerts to the finance lead, and a second approver on payout changes (C6), all VERIFIED Nov 4. | C5, C6 |
| R-3.2 | Group 3 — Strengthen application protections | Partial | There is no client portal (D5), but the scheduling app shows every volunteer the whole roster with mobile numbers (D3, VERIFIED Nov 2), and the role-based field limits it offers were never set (D4). | D3, D4, D5 |
| R-3.3 | Group 3 — Strengthen application protections | Covered | Missing pages, a malformed search and a broken form submission all returned the host's plain error page, with no versions, paths or database text (C8, VERIFIED Nov 4). | C1, C8 |
| R-3.4 | Group 3 — Strengthen application protections | Partial | There is no code or pipeline to scan (C1), but the processor's secret key sits in the plugin settings unrotated since 2023 (C7), and the shared SFTP password (C2) is a credential in the same position. | C1, C2, C7 |
| R-4.1 | Group 4 — Preserve evidence and respond | Partial | Purview audit is on record as on, with 180 days' retention (F4), but that was taken from the licence documentation and not checked in the tenant; there is no SIEM and nothing is kept outside the tenant (F5). | F4, F5 |
| R-4.2 | Group 4 — Preserve evidence and respond | Unknown | No review back to Oct 1 has happened. Until the former provider says what it connected (A9) there is nothing named to search for, and the donations@ failures (A6) are the only activity anyone has looked at. | A6, A9 |
| R-4.3 | Group 4 — Preserve evidence and respond | Covered | The board-approved incident sheet (G1, VERIFIED Nov 5) names the volunteer IT lead as responder and the operations manager as decision-maker, and both hold Global Administrator (A2). | A2, G1 |
| R-4.4 | Group 4 — Preserve evidence and respond | Unknown | Whether any affected application connection exists turns on the former provider's answer (A9), which has not yet been asked for. | A9 |

## Attack chains

### Chain A: Warehouse NAS through the forwarded port

1. **Reconnaissance.** A routine internet scan of the warehouse's public address finds the NAS's web admin login page answering on the forwarded port.
2. **Initial access.** The attacker tries the maker's known flaws and common passwords against it. One admin password is shared by three shift leads, and the firmware's age is UNKNOWN, so neither defence can be counted on.
3. **Privilege escalation.** None is needed: the shared account is the NAS's administrator, with every share, the camera recordings and the backup settings.
4. **Impact.** The shares are encrypted for ransom, the client-intake spreadsheet among them. The nightly sync mirrors the encrypted files to the cloud-backup service, and how many earlier versions it keeps is UNKNOWN.

Earliest breaking control: the NAS admin page closed to the internet and reachable from the warehouse network only (R-1.2) Status: Gap.

### Chain B: Donate button redirected through the website's shared publishing login

1. **Reconnaissance.** The page source names the CMS and its donation plugin, and the host's SFTP service answers on the site's address.
2. **Initial access.** The shared SFTP password, unchanged since the design agency handed over in 2023, or one of the agency's two leftover CMS admin accounts is used. Whether any CMS admin has two-step sign-in is UNKNOWN.
3. **Privilege escalation.** CMS admin access includes the processor plugin's settings page, where its secret API key is stored.
4. **Collection/exfiltration.** During the holiday drive the donate button is pointed at a look-alike checkout page that keeps card numbers, and the stolen key reads past donation records at the processor.

Earliest breaking control: per-person publishing access: the shared SFTP password retired and the agency's CMS admin accounts removed (R-1.3) Status: Partial.

### Chain C: Donor mail taken over through the shared donations mailbox

1. **Reconnaissance.** The scheduling app's roster gives any volunteer account the names and mobile numbers of the people who triage donor email, and donations@ is printed on every appeal letter.
2. **Initial access.** The donations@ password, shared by three volunteers on personal phones and not changed when volunteers leave, is phished by text or guessed; failed attempts from abroad are already in its sign-in list. Whether it has a second factor registered is UNKNOWN.
3. **Persistence.** A forwarding rule copies incoming donor mail to an outside address. The alert it raises is filed into a folder that is rarely opened.
4. **Impact.** Mail from donations@, inside the food bank's own threads, asks recurring donors to re-enter their card details on a fake page.

Earliest breaking control: sign-in blocked on the shared mailboxes, with volunteers reading donations@ through delegated access from accounts of their own Status: Gap.

## Fixes

| ID | Action | Rubric | Effort | Breaks | Status |
|---|---|---|---|---|---|
| F-1 | Print the board-approved incident sheet for the office and warehouse walls, and save a copy where both admins can reach it offline. | R-4.3 | Minutes | None (response) | done |
| F-2 | Remove the warehouse router's port forward to the NAS, and confirm from a phone off the warehouse network that the login page no longer answers. | R-1.2, R-1.5 | Minutes | A | approved |
| F-3 | Update the NAS firmware, turn on its automatic security updates, and give each shift lead a named account in place of the shared admin password. | R-1.2 | An hour | A | proposed |
| F-4 | Turn on NAS snapshots and set the cloud-backup service to keep at least 30 days of earlier versions, so an encrypted sync can be rolled back. | — | An hour | A (step 4) | proposed |
| F-5 | Change the hosting account's SFTP password, then turn SFTP off; the web volunteer turns it on for a session when a file change is needed. | R-1.3 | Minutes | B | proposed |
| F-6 | Delete the design agency's two CMS admin accounts and require two-step sign-in for the three that remain. | R-1.3 | Minutes | B | proposed |
| F-7 | Roll the processor's secret API key, replace it with a restricted key that can only create checkout sessions, and note the rotation date in the web volunteer's records. | R-3.4 | Minutes | B | proposed |
| F-8 | Block sign-in on donations@ and info@, and give the triage volunteers delegated access through accounts of their own. | — | An hour | C | proposed |
| F-9 | Remove the e-signature add-in if the grant agreement is closed, and turn on the admin consent request flow so the operations manager approves any new app. | R-2.1 | Minutes | None (app exposure) | proposed |
| F-10 | Write to the former managed IT provider asking which tools, integrations and accounts it connected to the tenant, and when each was removed; file the reply. | R-2.3, R-4.4 | Minutes, then a wait | None (evidence) | proposed |
| F-11 | Search the tenant's audit log from Oct 1 for new inbox rules, forwarding and app consents touching donations@ and info@, plus anything the former provider names. | R-4.2 | An hour | C | proposed |
| F-12 | Run one Purview audit search for this month's donations@ activity to prove audit is recording, and write the retention period into the operations manager's records. | R-4.1 | Minutes | None (evidence) | proposed |
| F-13 | Limit the scheduling app's roster so volunteers see first names and shifts only; mobile numbers go to shift leads and the volunteer coordinator. | R-3.2 | Minutes | C | proposed |
| F-14 | Send the tenant's alert emails to a security@ list read by both admins, and remove the mail rule that files them away. | R-2.2 | Minutes | C | proposed |
| F-15 | Ask the donor-management vendor what export limits and bulk-export alerts it offers, and turn on whatever it has for the development director. | R-3.2 | Minutes | None (donor data) | proposed |
| F-16 | Replace the warehouse camera with one that records to the NAS only and has no cloud viewer. | R-1.1 | A morning, plus purchase | None (reduces exposure) | deferred |

## Verify next

1. **Unknown:** NAS firmware version, and whether its admin page has seen logins from outside. **Why it changes the picture:** Decides whether Chain A has already happened or is still ahead. **Cheapest check:** NAS admin page -> System -> Firmware update; the NAS's connection log filtered to addresses outside the warehouse.
2. **Unknown:** Whether the warehouse router's own admin page answers from the internet. **Why it changes the picture:** A second exposed admin page would put the router itself in Chain A. **Cheapest check:** Router admin -> Administration -> Remote management; then the router's public address from a phone off the warehouse network.
3. **Unknown:** App permissions and the user consent setting. **Why it changes the picture:** Decides how far a single staff click can extend app access to mail and files. **Cheapest check:** Entra admin center -> Enterprise applications -> each app's Permissions tab; Consent and permissions -> User consent settings.
4. **Unknown:** What the former managed IT provider connected to the tenant. **Why it changes the picture:** The only route to an answer on R-2.3, R-4.2 and R-4.4. **Cheapest check:** A written request to the former provider; meanwhile Enterprise applications sorted by created date, looking before June 2025.
5. **Unknown:** Second-factor registration across staff accounts. **Why it changes the picture:** Security defaults protect only accounts that have registered. **Cheapest check:** Entra admin center -> Authentication methods -> User registration details.
6. **Unknown:** Who knows the donations@ password. **Why it changes the picture:** Sets how many people, past and present, can open Chain C. **Cheapest check:** Ask the three triage volunteers and the volunteer coordinator; compare against the roster of volunteers who have left.
7. **Unknown:** Two-step sign-in on the CMS administrator accounts. **Why it changes the picture:** Decides whether Chain B's account route is open. **Cheapest check:** CMS admin -> Users -> filter Administrator; each account's security settings.
8. **Unknown:** Version history kept by the cloud-backup service. **Why it changes the picture:** Decides whether Chain A's impact can be rolled back. **Cheapest check:** Cloud-backup service web console -> version history on one NAS file changed last week.
9. **Unknown:** Whether Purview audit is actually recording. **Why it changes the picture:** The 180-day figure is from documentation, not the tenant. **Cheapest check:** Purview portal -> Audit -> search the last 30 days for donations@.
10. **Unknown:** Sign-in protection and export alerts on the donor-management service. **Why it changes the picture:** 4,200 donor records sit behind a login no one has checked. **Cheapest check:** Donor-management service admin settings -> Security, and its notification settings for exports.
