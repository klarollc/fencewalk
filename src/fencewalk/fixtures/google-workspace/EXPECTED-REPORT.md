# Engagement report — Google Workspace case — Larkspur Advisory perimeter audit

- Subject: Larkspur Advisory LLC (fictional demo firm)
- Engagement created: 2026-11-18
- Method order: verify-first
- Rubric pack: CISA SCuBA Google Workspace Secure Configuration Baselines (ScubaGoggles v1.1.0) (CISA Secure Cloud Business Applications (SCuBA) Google Workspace baselines, as published with ScubaGoggles v1.1.0 (released Oct 22, 2026; https://github.com/cisagov/ScubaGoggles/releases/tag/v1.1.0), CC0 1.0 Universal. Three baselines are not included: Classroom (an education-sector product), Gemini and Assured Controls (separately purchased add-ons).)

## Posture summary

- Inventory: 20 entries (VERIFIED 6, ON RECORD 10, UNKNOWN 4)
- Coverage: Covered 45 · Partial 4 · Unknown 4 · Not applicable 11 · Gap 60 — 124 rows
- Attack chains: 3
- Fixes: 12 (proposed 12, approved 0, done 0, deferred 0)
- Verify-next items: 5

## Coverage

Tallies: Covered 45 · Partial 4 · Unknown 4 · Not applicable 11 · Gap 60 — 124 rows

| Item | Group | Status | Reasoning | Cited entries |
|---|---|---|---|---|
| GWS.CALENDAR.1.1v1 | Google Calendar | Covered | Primary calendars share free/busy only outside the organization. | E1 |
| GWS.CALENDAR.1.2v1 | Google Calendar | Gap | Secondary calendars share all event details outside the organization. | E1 |
| GWS.CALENDAR.2.1v1 | Google Calendar | Covered | External invitation warnings are on. | E1 |
| GWS.CALENDAR.3.1v1 | Google Calendar | Covered | Calendar Interop is off. | E1 |
| GWS.CALENDAR.3.2v1 | Google Calendar | Not applicable | The policy applies where Calendar Interop is used; Calendar Interop is off, so its condition is unmet. N/A reason: The policy applies where Calendar Interop is used; Calendar Interop is off, so its condition is unmet. | E1 |
| GWS.CALENDAR.4.1v1 | Google Calendar | Gap | Appointment schedules with payments are on. | E1 |
| GWS.CHAT.1.1v1 | Google Chat | Covered | Chat history is on. | E1 |
| GWS.CHAT.1.2v1 | Google Chat | Gap | Users may change their history setting. | E1 |
| GWS.CHAT.2.1v1 | Google Chat | Gap | External file sharing in Chat is on. | E1 |
| GWS.CHAT.3.1v1 | Google Chat | Covered | Space history is on. | E1 |
| GWS.CHAT.4.1v1 | Google Chat | Gap | External chat is open to all domains. | E1 |
| GWS.CHAT.5.1v1 | Google Chat | Covered | Content reporting is on for all conversation types. | E1 |
| GWS.CHAT.5.2v1 | Google Chat | Covered | Every reporting category is selected. | E1 |
| GWS.COMMONCONTROLS.1.1v1 | Common Controls | Gap | 2-Step Verification is not enforced, so phishing-resistant MFA is not required; only the founder uses a security key. | A2, B2 |
| GWS.COMMONCONTROLS.1.2v1 | Common Controls | Gap | No MFA method is enforced for all users. | A2, B2 |
| GWS.COMMONCONTROLS.1.3v1 | Common Controls | Gap | Two staff use SMS codes. | A2 |
| GWS.COMMONCONTROLS.1.4v1 | Common Controls | Gap | No new-user enrollment period is set. | B2 |
| GWS.COMMONCONTROLS.1.5v1 | Common Controls | Gap | Users may trust their device. | B2 |
| GWS.COMMONCONTROLS.10.1v1 | Common Controls | Gap | API controls are not configured; third-party apps are unrestricted. | B4, B5 |
| GWS.COMMONCONTROLS.10.2v1 | Common Controls | Gap | Users may consent to low-risk scopes. | B4 |
| GWS.COMMONCONTROLS.10.3v1 | Common Controls | Gap | Internal apps are trusted. | B4 |
| GWS.COMMONCONTROLS.10.4v1 | Common Controls | Gap | Unconfigured third-party apps are allowed. | B4 |
| GWS.COMMONCONTROLS.10.5v1 | Common Controls | Covered | Less secure apps are blocked. | B4 |
| GWS.COMMONCONTROLS.11.1v1 | Common Controls | Gap | Any Marketplace app may be installed. | B4 |
| GWS.COMMONCONTROLS.12.1v1 | Common Controls | Gap | Takeout is on. | B4 |
| GWS.COMMONCONTROLS.13.1v1 | Common Controls | Partial | System-defined alert rules are on at their defaults, several without email notification. | B4 |
| GWS.COMMONCONTROLS.14.1v1 | Common Controls | Gap | No log is sent to a SIEM; the firm has none. Whether the Business Standard edition supports a suitable export route is open (verify-next 1). | A5 |
| GWS.COMMONCONTROLS.14.2v1 | Common Controls | Partial | Audit logs are searchable for about six months; nothing is retained beyond that. | A5 |
| GWS.COMMONCONTROLS.15.1v1 | Common Controls | Gap | The data region is set to no preference. | B4 |
| GWS.COMMONCONTROLS.15.2v1 | Common Controls | Not applicable | Choosing the data processing region requires Enterprise Plus, Frontline Plus or Enterprise Essentials Plus (Google's edition documentation); the firm is on Business Standard. N/A reason: Choosing the data processing region requires Enterprise Plus, Frontline Plus or Enterprise Essentials Plus (Google's edition documentation); the firm is on Business Standard. | A1 |
| GWS.COMMONCONTROLS.16.1v1 | Common Controls | Gap | Services without an individual control are on. | B4 |
| GWS.COMMONCONTROLS.16.2v1 | Common Controls | Covered | Early access apps are off. | B4 |
| GWS.COMMONCONTROLS.16.3v1 | Common Controls | Gap | Looker Studio sharing outside the organization is on. | B4 |
| GWS.COMMONCONTROLS.16.4v1 | Common Controls | Gap | Pinpoint is on. | B4 |
| GWS.COMMONCONTROLS.17.1v1 | Common Controls | Not applicable | Multi-party approval requires an Enterprise or Education edition or Enterprise Essentials Plus (Google's edition documentation); the firm is on Business Standard. N/A reason: Multi-party approval requires an Enterprise or Education edition or Enterprise Essentials Plus (Google's edition documentation); the firm is on Business Standard. | A1 |
| GWS.COMMONCONTROLS.18.1v1 | Common Controls | Not applicable | DLP requires an Enterprise, Frontline or Education edition or Enterprise Essentials Plus, as the baseline's DLP section and Google's edition documentation state; the firm is on Business Standard. N/A reason: DLP requires an Enterprise, Frontline or Education edition or Enterprise Essentials Plus, as the baseline's DLP section and Google's edition documentation state; the firm is on Business Standard. | A1 |
| GWS.COMMONCONTROLS.18.2v1 | Common Controls | Not applicable | DLP requires an Enterprise, Frontline or Education edition or Enterprise Essentials Plus, as the baseline's DLP section and Google's edition documentation state; the firm is on Business Standard. N/A reason: DLP requires an Enterprise, Frontline or Education edition or Enterprise Essentials Plus, as the baseline's DLP section and Google's edition documentation state; the firm is on Business Standard. | A1 |
| GWS.COMMONCONTROLS.2.1v1 | Common Controls | Not applicable | Context-Aware Access requires an Enterprise, Frontline or Education edition or Cloud Identity Premium (Google's edition documentation); the firm is on Business Standard. N/A reason: Context-Aware Access requires an Enterprise, Frontline or Education edition or Cloud Identity Premium (Google's edition documentation); the firm is on Business Standard. | A1 |
| GWS.COMMONCONTROLS.3.1v1 | Common Controls | Not applicable | The policy applies to sign-ins through the organization's SSO profile; no SSO profile is configured, so its condition is unmet. N/A reason: The policy applies to sign-ins through the organization's SSO profile; no SSO profile is configured, so its condition is unmet. | B2 |
| GWS.COMMONCONTROLS.3.2v1 | Common Controls | Not applicable | The policy applies to sign-ins through other SSO profiles; no SSO profile is configured, so its condition is unmet. N/A reason: The policy applies to sign-ins through other SSO profiles; no SSO profile is configured, so its condition is unmet. | B2 |
| GWS.COMMONCONTROLS.4.1v1 | Common Controls | Gap | Web sessions last 14 days. | B2 |
| GWS.COMMONCONTROLS.5.1v1 | Common Controls | Covered | Password strength is enforced. | B3 |
| GWS.COMMONCONTROLS.5.2v1 | Common Controls | Gap | Minimum password length is 8. | B3 |
| GWS.COMMONCONTROLS.5.3v1 | Common Controls | Gap | Minimum password length is 8. | B3 |
| GWS.COMMONCONTROLS.5.4v1 | Common Controls | Gap | The password policy is not enforced at next sign-in. | B3 |
| GWS.COMMONCONTROLS.5.5v1 | Common Controls | Gap | Password reuse is allowed. | B3 |
| GWS.COMMONCONTROLS.5.6v1 | Common Controls | Covered | Passwords do not expire. | B3 |
| GWS.COMMONCONTROLS.6.1v1 | Common Controls | Covered | Admin accounts are Google accounts with no external identity provider. | B3 |
| GWS.COMMONCONTROLS.6.2v1 | Common Controls | Gap | One super admin, not the minimum of two. | A3 |
| GWS.COMMONCONTROLS.7.1v1 | Common Controls | Gap | Account conflict management is not configured. | B3 |
| GWS.COMMONCONTROLS.8.1v1 | Common Controls | Gap | Super admin self-recovery is on. | A4, B3 |
| GWS.COMMONCONTROLS.8.2v1 | Common Controls | Covered | User self-recovery is off. | B3 |
| GWS.COMMONCONTROLS.8.3v1 | Common Controls | Gap | Users may add recovery information. | B3 |
| GWS.COMMONCONTROLS.9.1v1 | Common Controls | Gap | The super admin is not enrolled in the Advanced Protection Program. | B3 |
| GWS.COMMONCONTROLS.9.2v1 | Common Controls | Gap | No account is enrolled in the Advanced Protection Program. | B3 |
| GWS.DRIVEDOCS.1.10v1 | Drive and Docs | Not applicable | The policy applies when external sharing is not allowed; external sharing is allowed, so its condition is unmet (the sharing gap is scored on GWS.DRIVEDOCS.1.1v1). N/A reason: The policy applies when external sharing is not allowed; external sharing is allowed, so its condition is unmet (the sharing gap is scored on GWS.DRIVEDOCS.1.1v1). | D1 |
| GWS.DRIVEDOCS.1.11v1 | Drive and Docs | Not applicable | The policy applies when receiving external files is not allowed; receiving is allowed, so its condition is unmet (the receiving gap is scored on GWS.DRIVEDOCS.1.2v1). N/A reason: The policy applies when receiving external files is not allowed; receiving is allowed, so its condition is unmet (the receiving gap is scored on GWS.DRIVEDOCS.1.2v1). | D1 |
| GWS.DRIVEDOCS.1.1v1 | Drive and Docs | Gap | Sharing outside the organization is allowed with no allowlist. | D1 |
| GWS.DRIVEDOCS.1.2v1 | Drive and Docs | Gap | Receiving files from outside is allowed. | D1 |
| GWS.DRIVEDOCS.1.3v1 | Drive and Docs | Covered | Warnings are shown when sharing outside the organization. | D1 |
| GWS.DRIVEDOCS.1.4v1 | Drive and Docs | Gap | Sharing with people who have no Google account is allowed. | D1 |
| GWS.DRIVEDOCS.1.5v1 | Drive and Docs | Gap | "Anyone with the link" is allowed and in use on six client folders. | D1, D2 |
| GWS.DRIVEDOCS.1.6v1 | Drive and Docs | Gap | Access checking allows public targets, not recipients only. | D1 |
| GWS.DRIVEDOCS.1.7v1 | Drive and Docs | Gap | Content may be moved to other organizations' shared drives. | D1 |
| GWS.DRIVEDOCS.1.8v1 | Drive and Docs | Covered | New items are private to their owner. | D1 |
| GWS.DRIVEDOCS.1.9v1 | Drive and Docs | Covered | Out-of-domain file warnings are on. | D1 |
| GWS.DRIVEDOCS.2.1v1 | Drive and Docs | Gap | Shared drive managers may override creation settings. | D1 |
| GWS.DRIVEDOCS.2.2v1 | Drive and Docs | Covered | Non-members may be added to files. | D1 |
| GWS.DRIVEDOCS.3.1v1 | Drive and Docs | Covered | The Drive file security update is applied. | D1 |
| GWS.DRIVEDOCS.4.1v1 | Drive and Docs | Gap | Drive SDK access is on. | D1 |
| GWS.DRIVEDOCS.5.1v1 | Drive and Docs | Gap | Drive for desktop is allowed on any device. | D1 |
| GWS.DRIVEDOCS.5.2v1 | Drive and Docs | Unknown | Whether ransomware monitoring is on was not checked. | D3 |
| GWS.GMAIL.1.1v1 | Gmail | Gap | Mail delegation is on. | C1 |
| GWS.GMAIL.10.1v1 | Gmail | Gap | Workspace Sync is on. | C1 |
| GWS.GMAIL.11.1v1 | Gmail | Covered | Automatic forwarding is off. | C1 |
| GWS.GMAIL.12.1v1 | Gmail | Covered | Per-user outbound gateways are off. | C1 |
| GWS.GMAIL.13.1v1 | Gmail | Covered | External reply warnings are on. | C1 |
| GWS.GMAIL.14.1v1 | Gmail | Covered | No email allowlist is set. | C1 |
| GWS.GMAIL.15.1v1 | Gmail | Covered | Enhanced pre-delivery scanning is on. | C1 |
| GWS.GMAIL.16.1v1 | Gmail | Gap | The security sandbox, available on Business Standard, is off. | C1 |
| GWS.GMAIL.17.1v1 | Gmail | Gap | Comprehensive mail storage is off. | C1 |
| GWS.GMAIL.18.1v1 | Gmail | Covered | No domain is on a spam-bypass list. | C1 |
| GWS.GMAIL.18.2v1 | Gmail | Covered | No domain is on a list that bypasses spam filters and hides warnings. | C1 |
| GWS.GMAIL.18.3v1 | Gmail | Covered | Bypassing spam filters and hiding warnings is not enabled. | C1 |
| GWS.GMAIL.2.1v1 | Gmail | Covered | Gmail signs outbound mail with DKIM and the key is published. | C2 |
| GWS.GMAIL.3.1v1 | Gmail | Partial | One SPF record, ending in a soft fail rather than failing non-approved senders. | C2 |
| GWS.GMAIL.4.1v1 | Gmail | Covered | A DMARC record is published for larkspur.example, the tenant's only domain. | A1, C2 |
| GWS.GMAIL.4.2v1 | Gmail | Gap | DMARC is at p=none. | C2 |
| GWS.GMAIL.4.3v1 | Gmail | Not applicable | The baseline directs aggregate reports to a U.S. federal address, an obligation of federal agencies; the firm's reports go to its own mailbox. N/A reason: The baseline directs aggregate reports to a U.S. federal address, an obligation of federal agencies; the firm's reports go to its own mailbox. | C2 |
| GWS.GMAIL.4.4v1 | Gmail | Partial | Aggregate reports go to the firm's own mailbox, which nobody reads; no failure-report contact is set. | C2, C3 |
| GWS.GMAIL.5.1v1 | Gmail | Covered | Protection against encrypted attachments from untrusted senders is on. | C1 |
| GWS.GMAIL.5.2v1 | Gmail | Covered | Protection against attachments with scripts is on. | C1 |
| GWS.GMAIL.5.3v1 | Gmail | Covered | Protection against anomalous attachment types is on. | C1 |
| GWS.GMAIL.5.4v1 | Gmail | Covered | Future recommended attachment settings are on. | C1 |
| GWS.GMAIL.5.5v1 | Gmail | Gap | Flagged attachments are kept in the inbox with a warning. | C1 |
| GWS.GMAIL.6.1v1 | Gmail | Covered | Shortened-URL scanning is on. | C1 |
| GWS.GMAIL.6.2v1 | Gmail | Covered | Linked-image scanning is on. | C1 |
| GWS.GMAIL.6.3v1 | Gmail | Gap | The warning prompt for links to untrusted domains is off. | C1 |
| GWS.GMAIL.6.4v1 | Gmail | Covered | Future recommended link settings are on. | C1 |
| GWS.GMAIL.7.1v1 | Gmail | Covered | Protection against similar domain names is on. | C1 |
| GWS.GMAIL.7.2v1 | Gmail | Covered | Protection against spoofing of employee names is on. | C1 |
| GWS.GMAIL.7.3v1 | Gmail | Gap | Protection against inbound mail spoofing the firm's own domain is off. | C1 |
| GWS.GMAIL.7.4v1 | Gmail | Gap | Protection against any unauthenticated mail is off. | C1 |
| GWS.GMAIL.7.5v1 | Gmail | Covered | Protection for Groups against inbound domain spoofing is on. | C1 |
| GWS.GMAIL.7.6v1 | Gmail | Gap | Flagged spoofing mail is kept in the inbox. | C1 |
| GWS.GMAIL.7.7v1 | Gmail | Covered | Future recommended spoofing settings are on. | C1 |
| GWS.GMAIL.8.1v1 | Gmail | Gap | User email uploads are on. | C1 |
| GWS.GMAIL.9.1v1 | Gmail | Gap | POP and IMAP access are on. | C1 |
| GWS.GROUPS.1.1v1 | Google Groups | Covered | Access from outside the organization is off unless granted. | E1 |
| GWS.GROUPS.1.2v1 | Google Groups | Gap | Owners may add external members. | E1 |
| GWS.GROUPS.1.3v1 | Google Groups | Gap | Owners may let non-members post. | E1 |
| GWS.GROUPS.2.1v1 | Google Groups | Gap | Any user may create groups. | E1 |
| GWS.GROUPS.3.1v1 | Google Groups | Covered | Conversations are viewable by all group members. | E1 |
| GWS.GROUPS.4.1v1 | Google Groups | Gap | Groups may be hidden from the directory. | E1 |
| GWS.MEET.1.1v1 | Google Meet | Covered | Uninvited external users must ask to join. | E1 |
| GWS.MEET.2.1v1 | Google Meet | Gap | Meetings created by users outside any organization may be joined. | E1 |
| GWS.MEET.3.1v1 | Google Meet | Covered | Host management is on. | E1 |
| GWS.MEET.4.1v1 | Google Meet | Gap | The external-participant warning is off. | E1 |
| GWS.MEET.5.1v1 | Google Meet | Covered | Automatic recordings are off. | E1 |
| GWS.MEET.5.2v1 | Google Meet | Covered | Automatic transcripts are off. | E1 |
| GWS.MEET.6.1v1 | Google Meet | Unknown | The meeting-notes override setting was not checked. | E2 |
| GWS.MEET.6.2v1 | Google Meet | Unknown | The default sharing level for AI notes was not checked. | E2 |
| GWS.MEET.6.3v1 | Google Meet | Unknown | The screenshots-in-notes setting was not checked. | E2 |
| GWS.SITES.1.1v1 | Google Sites | Gap | Sites is on for all users. | E1 |

## Attack chains

### Chain A: Credential phishing to payment diversion

1. **Initial access.** An adversary-in-the-middle phishing page relays the password and SMS code of one of the two staff who use SMS: 2-Step Verification is not enforced and phishing-resistant MFA is not required (GWS.COMMONCONTROLS.1.1v1, GWS.COMMONCONTROLS.1.3v1; A2).
2. **Persistence.** The stolen session lasts 14 days (GWS.COMMONCONTROLS.4.1v1; B2). Automatic forwarding is off, so the attacker reads in place and adds a filter that archives the client's replies, hiding the thread.
3. **Impact.** The attacker alters a payment instruction in a live client thread, and the client pays the attacker's account (F1).

Earliest breaking control: phishing-resistant MFA required for all users (GWS.COMMONCONTROLS.1.1v1) Status: Gap.

### Chain B: Self-spoof business email compromise

1. **Initial access.** An attacker sends mail to the bookkeeper from an outside server using the founder's own address. DMARC is at p=none (GWS.GMAIL.4.2v1; C2), so receivers apply no enforcement.
2. **Privilege escalation.** Gmail's protection against inbound mail spoofing the firm's own domain is off (GWS.GMAIL.7.3v1; C1), so the message arrives as ordinary internal mail.
3. **Impact.** The bookkeeper changes a supplier's payment details on the instruction, with no call-back step (F1).

Earliest breaking control: a DMARC enforcement policy in force for the domain (DNS-EM-04 (dns-registrar-security-1.0)) Status: Gap.

### Chain C: Link sharing exposure

1. **Initial access.** Six client folders are shared "anyone with the link" (GWS.DRIVEDOCS.1.5v1; D2), and sharing outside the organization has no allowlist (GWS.DRIVEDOCS.1.1v1; D1).
2. **Collection/exfiltration.** A client forwards a folder link beyond the client's own staff; whoever holds the link opens the folder without signing in.
3. **Impact.** The folder's contents surface months later outside both firms, with no record of who opened them.

Earliest breaking control: "anyone with the link" disabled where external sharing is allowed (GWS.DRIVEDOCS.1.5v1) Status: Gap.

## Fixes

| ID | Action | Rubric | Effort | Breaks | Status |
|---|---|---|---|---|---|
| F-1 | Enforce 2-Step Verification for all users with security keys or passkeys, the office manager's admin account first; remove the two SMS enrolments. | GWS.COMMONCONTROLS.1.1v1, GWS.COMMONCONTROLS.1.2v1, GWS.COMMONCONTROLS.1.3v1 | A week, staged | A | proposed |
| F-2 | Move DMARC from p=none to p=quarantine now and have someone read the aggregate reports for at least a month, then move to p=reject if they show no mailing-list or forwarding breakage. This follows RFC 9989's quarantine-first path for a domain with general users; GWS.GMAIL.4.2v1, written for federal tenants, asks for p=reject outright. | DNS-EM-04 (dns-registrar-security-1.0), DNS-EM-05 (dns-registrar-security-1.0) | An hour, then a month of report reading | B | proposed |
| F-3 | Turn on Gmail's protections against inbound mail spoofing the firm's domain and against any unauthenticated mail, and send flagged mail to spam rather than the inbox. | GWS.GMAIL.7.3v1, GWS.GMAIL.7.4v1, GWS.GMAIL.7.6v1 | Minutes | B | proposed |
| F-4 | Turn off "anyone with the link" sharing and re-share the six client folders with named client accounts. | GWS.DRIVEDOCS.1.5v1 | Half a day | C | proposed |
| F-5 | Restrict sharing outside the organization to an allowlist of client domains. | GWS.DRIVEDOCS.1.1v1 | An hour, after listing client domains | C | proposed |
| F-6 | Add a second super admin with a security key, held by a named person other than the founder. | GWS.COMMONCONTROLS.6.2v1 | An hour | None (admin resilience) | proposed |
| F-7 | Set web sessions to 12 hours. | GWS.COMMONCONTROLS.4.1v1 | Minutes | A (step 2) | proposed |
| F-8 | Raise the minimum password length to 12 (16 where possible), enforce the policy at next sign-in, and block reuse. | GWS.COMMONCONTROLS.5.2v1, GWS.COMMONCONTROLS.5.4v1, GWS.COMMONCONTROLS.5.5v1 | Minutes | None (password policy) | proposed |
| F-9 | Configure API controls: restrict third-party apps to an approved list and block unconfigured third-party apps. | GWS.COMMONCONTROLS.10.1v1, GWS.COMMONCONTROLS.10.4v1 | Half a day | None (app access) | proposed |
| F-10 | Turn off super admin self-recovery. | GWS.COMMONCONTROLS.8.1v1 | Minutes | None (recovery) | proposed |
| F-11 | Turn off POP and IMAP access. | GWS.GMAIL.9.1v1 | Minutes, after checking for desktop clients | None (legacy access) | proposed |
| F-12 | Turn on the Gmail security sandbox. | GWS.GMAIL.16.1v1 | Minutes | None (attachment scanning) | proposed |

## Verify next

1. **Unknown:** Whether GWS.COMMONCONTROLS.14.1v1 can be met on the Business Standard edition (A1, A5). **Why it changes the picture:** Google's edition documentation puts BigQuery log export outside Business Standard, but the baseline accepts any route that delivers the critical logs to a SIEM; until a route is chosen, GWS.COMMONCONTROLS.14.1v1 is a Gap with an open edition question. **Cheapest check:** Google's documentation for the Reports API and the audit log export options on Business Standard, read against whatever SIEM or log service the firm would use.
2. **Unknown:** Whether Drive for desktop's ransomware monitoring is on (D3). **Why it changes the picture:** GWS.DRIVEDOCS.5.2v1 stays Unknown until the setting is read. **Cheapest check:** The Admin console's Drive and Docs settings for Drive for desktop, read by the founder.
3. **Unknown:** The Meet settings for AI-generated meeting notes (E2). **Why it changes the picture:** GWS.MEET.6.1v1, GWS.MEET.6.2v1 and GWS.MEET.6.3v1 stay Unknown until the settings are read. **Cheapest check:** The Admin console's Google Meet settings, the meeting-notes section, read by the founder.
4. **Unknown:** Whether the founder's personal email account is still a recovery address on the super admin account (A4). **Why it changes the picture:** With super admin self-recovery on, a recovery address outside the firm is a second door to the tenant's only super admin account. **Cheapest check:** The founder opens their own Google account's security page and reads the recovery email and phone.
5. **Unknown:** Which app or vendor holds the domain-wide delegation grant (B5). **Why it changes the picture:** A domain-wide delegation client with Gmail and Drive scopes can read any user's mail and files without their sign-in; GWS.COMMONCONTROLS.10.1v1 cannot be fixed safely until it is identified. **Cheapest check:** Match the client ID against the firm's installed apps and service accounts, and ask the founder and the office manager which vendor set it up.
