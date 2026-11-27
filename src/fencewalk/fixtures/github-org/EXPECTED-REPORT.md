# Engagement report — GitHub organization case — Alder Creek Advisory perimeter audit

- Subject: Alder Creek Advisory LLC (fictional demo firm)
- Engagement created: 2026-11-21
- Method order: verify-first
- Rubric pack: GitHub — Organization Security Expected State (curated) (Curated from GitHub Docs (github/docs @ bd60abd2de5c9285e34ce3ea794274e973b0633e, retrieved 2026-11-24), © GitHub, Inc., licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Items are selected and reworded for a small organization. No CIS Benchmark content is used.)

## Posture summary

- Inventory: 24 entries (VERIFIED 17, ON RECORD 3, UNKNOWN 4)
- Coverage: Covered 5 · Partial 3 · Unknown 2 · Not applicable 3 · Gap 21 — 34 rows
- Attack chains: 3
- Fixes: 9 (proposed 9, approved 0, done 0, deferred 0)
- Verify-next items: 5

## Coverage

Tallies: Covered 5 · Partial 3 · Unknown 2 · Not applicable 3 · Gap 21 — 34 rows

| Item | Group | Status | Reasoning | Cited entries |
|---|---|---|---|---|
| GH-ACT-01 | GitHub Actions | Gap | All actions and reusable workflows are allowed. | D1 |
| GH-ACT-02 | GitHub Actions | Gap | Default GITHUB_TOKEN permissions are read and write. | D1 |
| GH-ACT-03 | GitHub Actions | Gap | Approval is required only for first-time contributors, and the pull_request_target workflow in field-notes runs regardless of approval settings. | D1, D3 |
| GH-ACT-04 | GitHub Actions | Covered | Retention is 90 days, the default. | D1 |
| GH-ACT-05 | GitHub Actions | Covered | No self-hosted runners are registered, so none serves a public repository. | D1 |
| GH-ACT-06 | GitHub Actions | Gap | Two of six organization secrets are available to all repositories, public ones included, with no accepted-exposure record. | D2 |
| GH-AUD-01 | Audit | Gap | The audit log has not been reviewed since the organization was created. | G2 |
| GH-AUD-02 | Audit | Gap | IP addresses are not displayed, and token-performed events cannot be identified on the Team plan. | G1 |
| GH-AUD-03 | Audit | Gap | No audit log export has been taken. | G1 |
| GH-CODE-01 | Code security defaults | Partial | Secret scanning is on for public repositories only. | E1 |
| GH-CODE-02 | Code security defaults | Gap | Push protection is off. | E1 |
| GH-CODE-03 | Code security defaults | Partial | Dependabot alerts are on; security updates are off. | E1 |
| GH-CODE-04 | Code security defaults | Gap | No organization ruleset exists. | E1 |
| GH-CODE-05 | Code security defaults | Gap | Private vulnerability reporting is not enabled on either public repository. | E1 |
| GH-CODE-06 | Code security defaults | Covered | Forking of private repositories is not allowed. | B2 |
| GH-ID-01 | Identity and access | Gap | Two-factor authentication is not required; 3 members and 2 outside collaborators have none enabled. | A3 |
| GH-ID-02 | Identity and access | Gap | One owner uses a passkey; the other reports a TOTP app and no phishing-resistant method was seen. Both owners' identities are shared with a tenant where phishing-resistant MFA is not enforced. | A4, A5, H1 |
| GH-ID-03 | Identity and access | Not applicable | SAML single sign-on requires GitHub Enterprise Cloud; the organization is on the Team plan. N/A reason: SAML single sign-on requires GitHub Enterprise Cloud; the organization is on the Team plan. | A1, A6 |
| GH-ID-04 | Identity and access | Not applicable | IP allow lists require GitHub Enterprise Cloud; the organization is on the Team plan. N/A reason: IP allow lists require GitHub Enterprise Cloud; the organization is on the Team plan. | A1, A6 |
| GH-ID-05 | Identity and access | Not applicable | Restricted email notifications require GitHub Enterprise Cloud; the organization is on the Team plan. N/A reason: Restricted email notifications require GitHub Enterprise Cloud; the organization is on the Team plan. | A1, A6 |
| GH-MEM-01 | Membership and ownership | Gap | Base permissions are Write, so every member can push to every repository. | B1 |
| GH-MEM-02 | Membership and ownership | Gap | Members can create both public and private repositories. | B2 |
| GH-MEM-03 | Membership and ownership | Gap | Repository administrators may invite outside collaborators (the owner-only restriction is not offered on Team), and no access review is on record: the former vendor's staff member kept write access after the engagement ended. | B3 |
| GH-MEM-04 | Membership and ownership | Covered | Two owners, each a named staff member. | A2 |
| GH-MEM-05 | Membership and ownership | Covered | Pages creation is disallowed for members and no site is published. | B2 |
| GH-TOK-01 | Programmatic access | Gap | OAuth app access restrictions are not set up, so any OAuth app a member authorizes can reach organization resources. | C1 |
| GH-TOK-02 | Programmatic access | Gap | Repository administrators may install GitHub Apps, and app access requests are open to members and outside collaborators. | C1 |
| GH-TOK-03 | Programmatic access | Gap | Fine-grained tokens reach the organization without approval. | C2 |
| GH-TOK-04 | Programmatic access | Unknown | Fine-grained tokens are listed (one unused since May 2026), but the two known classic tokens cannot be seen from the organization; whether they still reach it is unknown. | C2, C3 |
| GH-TOK-05 | Programmatic access | Gap | Two deploy keys on client-portal, one read-write, with no owner or review date. | C5 |
| GH-TOK-06 | Programmatic access | Unknown | Three apps are installed and two have known owners; the chat app has no owner on record and whether it is still used is unknown, so whether it should be uninstalled is open. | C1, C4 |
| GH-WH-01 | Webhooks | Partial | Two of three webhooks have a known purpose and owner; the ci-old webhook's endpoint has no known operator. | F1, F2, F3 |
| GH-WH-02 | Webhooks | Gap | The billing-tools intake webhook has no secret set. | F1 |
| GH-WH-03 | Webhooks | Gap | The ci-old webhook still delivers to a decommissioned server's name, and its endpoint is not one the firm operates. | F1, F2 |

## Attack chains

### Chain A: Organization takeover through an owner's Microsoft 365 account

1. **Initial access.** An adversary-in-the-middle phishing page relays an owner's Microsoft 365 sign-in: the tenant does not enforce phishing-resistant MFA (MS.AAD.3.1v1), not even for the highly privileged roles both owners hold (H1).
2. **Privilege escalation.** The same identity holds GitHub ownership. The owner who reports a TOTP app has no phishing-resistant method on record (GH-ID-02; A5), and a TOTP code can be relayed by the same kit; password reset mail for the account lands in the already-captured tenant mailbox (H1).
3. **Persistence.** As owner, the adversary authorizes an approved-looking OAuth app or creates a fine-grained token: OAuth app access restrictions are off and fine-grained tokens need no approval (GH-TOK-01, GH-TOK-03; C1, C2), so the grant survives a password reset.

Earliest breaking control: phishing-resistant MFA required for the highly privileged roles (in the tenant) (MS.AAD.3.6v1 (scuba-m365-v2.0.0)) Status: Gap.

### Chain B: Malicious workflow through a public repository

1. **Initial access.** Anyone can fork field-notes and open a pull request; its pull_request_target workflow checks out and builds the pull request's head, and runs regardless of approval settings (D3; GH-ACT-03).
2. **Privilege escalation.** The workflow runs in the base repository's context with a GITHUB_TOKEN that defaults to read and write (GH-ACT-02; D1).
3. **Collection/exfiltration.** The deployment credential among the organization secrets is available to all repositories, field-notes included (GH-ACT-06; D2), so the build script can read it and send it out.

Earliest breaking control: default GITHUB_TOKEN permissions set to read-only (GH-ACT-02) Status: Gap.

### Chain C: Persistence through a dormant collaborator and a stale webhook

1. **Initial access.** The former vendor's staff member keeps write access to client-portal with no two-factor authentication (B3; GH-ID-01), so that one password opens a client repository.
2. **Persistence.** No collaborator review is on record (GH-MEM-03), so the access was never removed when the engagement ended.
3. **Collection/exfiltration.** Separately, the ci-old webhook still sends organization event payloads to a decommissioned server's name, which has answered with success since October 2026 (F1, F2); whoever operates it now receives them (F3; GH-WH-03).

Earliest breaking control: outside collaborators' access reviewed at least quarterly, with only owners inviting (GH-MEM-03) Status: Gap.

## Fixes

| ID | Action | Rubric | Effort | Breaks | Status |
|---|---|---|---|---|---|
| F-1 | Require two-factor authentication for the organization, after notifying the 3 members and 2 outside collaborators without it; outside collaborators who have not enabled it are removed. | GH-ID-01 | An hour, after a week's notice | C | proposed |
| F-2 | Register passkeys or security keys for both owners and remove any SMS method; keep TOTP only as a backup. | GH-ID-02 | An hour | A | proposed |
| F-3 | Set base permissions for members to None and grant repository access through teams. | GH-MEM-01 | Half a day | None (least privilege) | proposed |
| F-4 | Turn off repository creation for members, so only owners create repositories. | GH-MEM-02 | Minutes | None (prevents exposure) | proposed |
| F-5 | Remove the former vendor's staff member from client-portal, then review outside collaborators' access every quarter and record each review. | GH-MEM-03 | An hour, then quarterly | C | proposed |
| F-6 | Set up OAuth app access restrictions and approve only the OAuth apps the firm uses. | GH-TOK-01 | An hour | A (step 3) | proposed |
| F-7 | Require owner approval for fine-grained personal access tokens. | GH-TOK-03 | Minutes | A (step 3) | proposed |
| F-8 | Set the organization's default GITHUB_TOKEN permissions to read-only, and grant write per workflow where a job needs it. | GH-ACT-02 | An hour, with workflow review | B | proposed |
| F-9 | Enforce phishing-resistant MFA for the owners' tenant accounts: require the phishing-resistant authentication strength for the highly privileged roles in Conditional Access. | MS.AAD.3.6v1 (scuba-m365-v2.0.0) | An hour, after passkey registration | A | proposed |

## Verify next

1. **Unknown:** Whether the firm's exposure justifies moving to GitHub Enterprise Cloud, which SAML single sign-on and IP allow lists require. **Why it changes the picture:** GH-ID-03 and GH-ID-04 are Not applicable on the Team plan (A1, A6), and so are restricted email notifications, the owner-only invite restriction in GH-MEM-03 and token attribution in GH-AUD-02; whether those are worth a plan change is a business decision, not a setting. **Cheapest check:** The plan comparison against the two Not-applicable items (GH-ID-03, GH-ID-04), read against the firm's client commitments.
2. **Unknown:** Whether the chat notification app and the CI service installation are still used, and who owns the chat app (C4). **Why it changes the picture:** An app nobody owns is uninstalled under GH-TOK-06; until use and ownership are known that item stays Unknown. **Cheapest check:** Organization settings -> GitHub Apps -> each app's Configure page, then ask the staff who use chat notifications and CI.
3. **Unknown:** Who operates the endpoint at ci-old.aldercreek.example now (F3). **Why it changes the picture:** If the name now resolves to someone else's server, organization event payloads have been going to a third party since October 2026, and Chain C's last step is live. **Cheapest check:** Resolve the name and look up who holds the address it points to; then remove the DNS record and delete the webhook.
4. **Unknown:** Which two-factor methods are registered on the second owner's account (A5). **Why it changes the picture:** If an SMS method or no passkey is registered, Chain A's second step needs only a relayed code; a registered security key would narrow it to the TOTP fallback. **Cheapest check:** The owner opens Settings -> Password and authentication on their own account and lists the registered methods.
5. **Unknown:** Whether the two known classic personal access tokens still reach the organization (C3). **Why it changes the picture:** A classic token carries its holder's access without appearing on the organization's token pages: the vendor staff member's token works for as long as F-5 is not done, and the deploy script's token has never been reviewed. GH-TOK-04 stays Unknown until both are settled. **Cheapest check:** Theo Marsh checks Settings -> Developer settings -> Personal access tokens (classic) for the deploy token's scopes and last use; the former vendor is asked to revoke its staff member's token.
