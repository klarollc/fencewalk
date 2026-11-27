# Engagement report — Demo case — Tidewater Advisory perimeter audit

- Subject: Tidewater Advisory LLC (fictional demo firm)
- Engagement created: 2026-10-15
- Method order: verify-first
- Rubric pack: CISA SCuBA M365 Secure Configuration Baselines (ScubaGear v2.0.0) (CISA Secure Cloud Business Applications (SCuBA) Microsoft 365 baselines, as published with ScubaGear v2.0.0 (released Oct 22, 2026; https://github.com/cisagov/ScubaGear/releases/tag/v2.0.0), CC0 1.0 Universal)

## Posture summary

- Inventory: 30 entries (VERIFIED 23, ON RECORD 2, UNKNOWN 5)
- Coverage: Covered 72 · Partial 14 · Unknown 0 · Not applicable 8 · Gap 15 — 109 rows
- Attack chains: 4
- Fixes: 15 (proposed 15, approved 0, done 0, deferred 0)
- Verify-next items: 5

## Coverage

Tallies: Covered 72 · Partial 14 · Unknown 0 · Not applicable 8 · Gap 15 — 109 rows

| Item | Group | Status | Reasoning | Cited entries |
|---|---|---|---|---|
| MS.AAD.1.1v1 | Microsoft Entra ID | Gap | 0 conditional access policy(s) found that meet(s) all requirements. Near miss: MS.AAD.1.1v1 Legacy authentication SHALL be blocked would pass if the config file is updated to include: user exclusions. Run the Start-SCuBAConfigAnalyzer cmdlet, https://github.com/cisagov/ScubaGear/blob/main/docs/configuration/scubaconfiganalyzer.md and import your ScubaResults JSON file to determine which specific exclusions to add to the configuration file. | A5, H6 |
| MS.AAD.2.1v1 | Microsoft Entra ID | Covered | 1 conditional access policy(s) found that meet(s) all requirements: MS.AAD.2.1v1 Users detected as high risk SHALL be blocked. | A5 |
| MS.AAD.2.2v1 | Microsoft Entra ID | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/aad.md#msaad22v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/aad.md#msaad22v1 for instructions on manual check | A5, H3 |
| MS.AAD.2.3v1 | Microsoft Entra ID | Covered | 1 conditional access policy(s) found that meet(s) all requirements: MS.AAD.2.3v1 Sign-ins detected as high risk SHALL be blocked. | A2, A5 |
| MS.AAD.3.1v1 | Microsoft Entra ID | Gap | 0 conditional access policy(s) found that meet(s) all requirements. | A5, A9 |
| MS.AAD.3.2v2 | Microsoft Entra ID | Covered | 1 conditional access policy(s) found that meet(s) all requirements: MS.AAD.3.2v1 If phishing-resistant MFA has not been enforced, an alternative MFA method SHALL be enforced for all users. | A5 |
| MS.AAD.3.3v2 | Microsoft Entra ID | Covered | Requirement met | A9 |
| MS.AAD.3.4v1 | Microsoft Entra ID | Covered | Requirement met | A9 |
| MS.AAD.3.5v2 | Microsoft Entra ID | Covered | Requirement met | A9 |
| MS.AAD.3.6v1 | Microsoft Entra ID | Gap | 0 conditional access policy(s) found that meet(s) all requirements. | A5, A9 |
| MS.AAD.3.7v1 | Microsoft Entra ID | Partial | 0 conditional access policy(s) found that meet(s) all requirements. | A5 |
| MS.AAD.3.8v1 | Microsoft Entra ID | Partial | 0 conditional access policy(s) found that meet(s) all requirements. | A5 |
| MS.AAD.3.9v1 | Microsoft Entra ID | Partial | 0 conditional access policy(s) found that meet(s) all requirements. Near miss: MS.AAD.3.9v1 Device code authentication SHOULD be blocked would pass if the config file is updated to include: user exclusions, group exclusions. Run the Start-SCuBAConfigAnalyzer cmdlet, https://github.com/cisagov/ScubaGear/blob/main/docs/configuration/scubaconfiganalyzer.md and import your ScubaResults JSON file to determine which specific exclusions to add to the configuration file. | A5, H6 |
| MS.AAD.4.1v1 | Microsoft Entra ID | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/aad.md#msaad41v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/aad.md#msaad41v1 for instructions on manual check | G3, H3 |
| MS.AAD.5.1v1 | Microsoft Entra ID | Gap | 1 authorization policies found that allow non-admin users to register third-party applications: authorizationPolicy | A10, A7 |
| MS.AAD.5.2v1 | Microsoft Entra ID | Gap | 1 authorization policies found that allow non-admin users to consent to third-party applications with risky delegated permission classifications: authorizationPolicy | A10, A7 |
| MS.AAD.5.3v1 | Microsoft Entra ID | Covered | Requirement met | A10, A7 |
| MS.AAD.5.5v1 | Microsoft Entra ID | Covered | Requirement met | A10, A7 |
| MS.AAD.5.6v1 | Microsoft Entra ID | Covered | Requirement met | A10, A7 |
| MS.AAD.5.7v1 | Microsoft Entra ID | Covered | Requirement met | A10, A7 |
| MS.AAD.6.1v1 | Microsoft Entra ID | Gap | Requirement not met | H7 |
| MS.AAD.7.1v1 | Microsoft Entra ID | Covered | 2 global admin(s) found: the principal, the second global administrator | A3 |
| MS.AAD.7.2v1 | Microsoft Entra ID | Gap | Requirement not met: Least Privilege Score = 2 (should be 1 or less) Calculated by 2 global admins / 1 privileged users without global admin role | A3 |
| MS.AAD.7.3v1 | Microsoft Entra ID | Covered | 0 admin(s) that are not cloud-only found | A1, A3 |
| MS.AAD.7.4v1 | Microsoft Entra ID | Gap | 6 role(s) that contain users with permanent active assignment: Application Administrator, Cloud Application Administrator, Exchange Administrator, Global Administrator, SharePoint Administrator, User Administrator | A3, A6 |
| MS.AAD.7.5v1 | Microsoft Entra ID | Gap | 4 role(s) assigned to users outside of PIM: Exchange Administrator, Global Administrator, SharePoint Administrator, User Administrator | A3, A6 |
| MS.AAD.7.6v1 | Microsoft Entra ID | Gap | 1 role(s) or group(s) allowing activation without approval found: Global Administrator(Directory Role) | A3, A6 |
| MS.AAD.7.7v1 | Microsoft Entra ID | Gap | 6 role(s) or group(s) without notification e-mail configured for role assignments found: Cloud Application Administrator(Directory Role), Exchange Administrator(Directory Role), Global Administrator(Directory Role), Hybrid Identity Administrator(Directory Role), Privileged Role Administrator(Directory Role), SharePoint Administrator(Directory Role) | A3, A6 |
| MS.AAD.7.8v1 | Microsoft Entra ID | Covered | 0 role(s) or group(s) without notification e-mail configured for Global Administrator activations found | A3, A6 |
| MS.AAD.7.9v1 | Microsoft Entra ID | Partial | 5 role(s) or group(s) without notification e-mail configured for role activations found: Cloud Application Administrator(Directory Role), Exchange Administrator(Directory Role), Hybrid Identity Administrator(Directory Role), Privileged Role Administrator(Directory Role), SharePoint Administrator(Directory Role) | A3, A6 |
| MS.AAD.8.1v1 | Microsoft Entra ID | Covered | Permission level set to "Limited access" (authorizationPolicy) | A8 |
| MS.AAD.8.2v1 | Microsoft Entra ID | Partial | Permission level set to "adminsGuestInvitersAndAllMembers" (authorizationPolicy) | A8 |
| MS.AAD.8.3v1 | Microsoft Entra ID | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/aad.md#msaad83v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/aad.md#msaad83v1 for instructions on manual check | A8, H3 |
| MS.AAD.9.1v1 | Microsoft Entra ID | Gap | 0 conditional access policy(s) found that meet(s) all requirements. | A2, A5 |
| MS.EXO.1.1v2 | Exchange Online | Covered | No domains allow automatic forwarding. | B3 |
| MS.EXO.13.1v1 | Exchange Online | Covered | Requirement met | B4 |
| MS.EXO.2.2v3 | Exchange Online | Covered | Requirement met. View DNS logs, #dns-logs for more details. | B1 |
| MS.EXO.3.1v1 | Exchange Online | Partial | 1 agency domain(s) found in violation: tidewateradvisory.example. View DNS logs, #dns-logs for more details. | B1 |
| MS.EXO.4.1v1 | Exchange Online | Covered | Requirement met. View DNS logs, #dns-logs for more details. | B2 |
| MS.EXO.4.2v1 | Exchange Online | Covered | Requirement met. View DNS logs, #dns-logs for more details. | B2 |
| MS.EXO.4.3v1 | Exchange Online | Covered | Requirement met. View DNS logs, #dns-logs for more details. | B2 |
| MS.EXO.4.4v1 | Exchange Online | Covered | Requirement met. View DNS logs, #dns-logs for more details. | B2 |
| MS.EXO.5.1v1 | Exchange Online | Covered | Requirement met | B4 |
| MS.EXO.6.1v1 | Exchange Online | Covered | Requirement met | B4 |
| MS.EXO.6.2v1 | Exchange Online | Covered | Requirement met | B4 |
| MS.EXO.7.1v1 | Exchange Online | Covered | Requirement met | B4 |
| MS.POWERBI.1.1v1 | Power BI | Covered | Requirement met | F1 |
| MS.POWERBI.2.1v1 | Power BI | Covered | Requirement met | F1 |
| MS.POWERBI.3.1v1 | Power BI | Partial | Requirement not met | F1 |
| MS.POWERBI.4.1v1 | Power BI | Covered | Requirement met | F1 |
| MS.POWERBI.4.2v1 | Power BI | Covered | Requirement met | F1 |
| MS.POWERBI.5.1v1 | Power BI | Partial | Requirement not met | F1 |
| MS.POWERBI.6.1v1 | Power BI | Partial | Requirement not met | F1 |
| MS.POWERBI.7.1v1 | Power BI | Covered | Requirement met | F1 |
| MS.POWERPLATFORM.1.1v1 | Power Platform | Covered | Requirement met | E1 |
| MS.POWERPLATFORM.1.2v1 | Power Platform | Covered | Requirement met | E1 |
| MS.POWERPLATFORM.2.1v1 | Power Platform | Gap | No policy found that applies to default environment | E2 |
| MS.POWERPLATFORM.2.2v1 | Power Platform | Partial | No DLP policies found | E2 |
| MS.POWERPLATFORM.3.1v1 | Power Platform | Covered | Requirement met | E1 |
| MS.POWERPLATFORM.3.2v1 | Power Platform | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/powerplatform.md#mspowerplatform32v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/powerplatform.md#mspowerplatform32v1 for instructions on manual check | E1, H4 |
| MS.POWERPLATFORM.4.1v1 | Power Platform | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/powerplatform.md#mspowerplatform41v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/powerplatform.md#mspowerplatform41v1 for instructions on manual check | H4 |
| MS.POWERPLATFORM.5.1v1 | Power Platform | Covered | Requirement met | E1 |
| MS.POWERPLATFORM.6.1v1 | Power Platform | Covered | Requirement met | E1 |
| MS.SECURITYSUITE.1.1v1 | Security Suite | Covered | Requirement met. The highest priority anti-malware policy that applies to all users is: Standard Preset. | G1 |
| MS.SECURITYSUITE.1.2v1 | Security Suite | Covered | Requirement met. The highest priority anti-malware policy that applies to all users is: Standard Preset. | G1 |
| MS.SECURITYSUITE.1.3v1 | Security Suite | Covered | Requirement met. The highest priority safe attachments policy that applies to all users is: Standard Preset. | G1 |
| MS.SECURITYSUITE.1.4v1 | Security Suite | Partial | Requirement not met | G1 |
| MS.SECURITYSUITE.2.1v1 | Security Suite | Partial | No users defined as sensitive users in the ScubaGear config file. | G1, H2 |
| MS.SECURITYSUITE.2.2v1 | Security Suite | Covered | Requirement met | G1, H2 |
| MS.SECURITYSUITE.2.3v1 | Security Suite | Partial | No partner domains defined in the ScubaGear config file. | G1, H2 |
| MS.SECURITYSUITE.2.4v1 | Security Suite | Covered | Requirement met | G1, H2 |
| MS.SECURITYSUITE.3.1v1 | Security Suite | Covered | Requirement met | G2 |
| MS.SECURITYSUITE.3.2v1 | Security Suite | Partial | DLP custom policy applied to the following locations: Devices. Custom policy protecting sensitive info types NOT applied to: Exchange, OneDrive, SharePoint, Teams. Teams location requires DLP for Teams included in E5/G5 licenses. For full policy details, see the ActualValue field in the results file: ./RegoOutput.json | G2 |
| MS.SECURITYSUITE.3.3v1 | Security Suite | Covered | Requirement met | G2 |
| MS.SECURITYSUITE.3.4v1 | Security Suite | Covered | Requirement met | G2 |
| MS.SECURITYSUITE.3.5v1 | Security Suite | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/securitysuite.md#mssecuritysuite35v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/securitysuite.md#mssecuritysuite35v1 for instructions on manual check | G2, H5 |
| MS.SECURITYSUITE.4.1v1 | Security Suite | Covered | Requirement met | G3 |
| MS.SECURITYSUITE.4.2v1 | Security Suite | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/securitysuite.md#mssecuritysuite42v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/securitysuite.md#mssecuritysuite42v1 for instructions on manual check | G3, H5 |
| MS.SECURITYSUITE.5.1v1 | Security Suite | Covered | Requirement met | G3 |
| MS.SECURITYSUITE.5.2v1 | Security Suite | Not applicable | This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/securitysuite.md#mssecuritysuite52v1 for instructions on manual check N/A reason: This product does not currently have the capability to check compliance for this policy. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/securitysuite.md#mssecuritysuite52v1 for instructions on manual check | G3, H5 |
| MS.SECURITYSUITE.6.1v1 | Security Suite | Covered | Requirement met. Standard preset is active and compliant (Strict not active or non-compliant). Custom and Default policies not evaluated | G1 |
| MS.SECURITYSUITE.6.2v1 | Security Suite | Covered | Requirement met. Standard preset is active and compliant (Strict not active or non-compliant). Custom and Default policies not evaluated | G1 |
| MS.SECURITYSUITE.7.1v1 | Security Suite | Covered | URL comparison with a block-list is enabled via the standard or strict preset security policies. | G1 |
| MS.SECURITYSUITE.7.2v1 | Security Suite | Covered | Direct download links are scanned for malware via the standard or strict preset security policies. | G1 |
| MS.SECURITYSUITE.7.3v1 | Security Suite | Covered | User click tracking is enabled via the standard or strict preset security policies. | G1 |
| MS.SECURITYSUITE.8.1v1 | Security Suite | Covered | Requirement met | G1 |
| MS.SECURITYSUITE.8.2v1 | Security Suite | Covered | Requirement met | G1 |
| MS.SHAREPOINT.1.1v1 | SharePoint Online and OneDrive | Gap | Requirement not met | C1 |
| MS.SHAREPOINT.1.2v1 | SharePoint Online and OneDrive | Covered | Requirement met | C1 |
| MS.SHAREPOINT.1.3v1 | SharePoint Online and OneDrive | Covered | Requirement met: Note that we currently only check for approved external domains. Approved security groups are currently not being checked, see the baseline policy for instructions on a manual check. | C1 |
| MS.SHAREPOINT.2.1v1 | SharePoint Online and OneDrive | Covered | Requirement met | C2 |
| MS.SHAREPOINT.2.2v1 | SharePoint Online and OneDrive | Covered | Requirement met | C2 |
| MS.SHAREPOINT.3.1v1 | SharePoint Online and OneDrive | Covered | Requirement met | C2 |
| MS.SHAREPOINT.3.2v1 | SharePoint Online and OneDrive | Gap | Requirement not met: folders are not limited to view for Anyone | C2 |
| MS.SHAREPOINT.3.3v2 | SharePoint Online and OneDrive | Covered | Requirement met | C2 |
| MS.TEAMS.1.1v1 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.1.2v2 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.1.3v1 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.1.4v1 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.1.5v1 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.1.6v1 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.1.7v2 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.2.1v2 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.2.2v2 | Teams | Covered | This policy is not applicable to GCC, GCC High, or DOD environments. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/teams.md#msteams22v2 for more info | D1, H1 |
| MS.TEAMS.2.3v2 | Teams | Covered | This policy is not applicable to GCC, GCC High, or DOD environments. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/teams.md#msteams23v2 for more info | D1, H1 |
| MS.TEAMS.4.1v1 | Teams | Covered | This policy is not applicable to GCC, GCC High, or DOD environments. See Secure Configuration Baseline policy, https://github.com/cisagov/ScubaGear/blob/v2.0.0/PowerShell/ScubaGear/baselines/teams.md#msteams41v1 for more info | D1, H1 |
| MS.TEAMS.5.1v2 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.5.2v2 | Teams | Covered | Requirement met | D1 |
| MS.TEAMS.5.3v2 | Teams | Covered | Requirement met | D1 |

## Attack chains

### Chain A: Takeover of a privileged administrator

1. **Reconnaissance.** The tenant's domain and its Microsoft 365 sign-in page are public; two of the three privileged users are Global Administrators, so any one of them is a full-tenant target.
2. **Initial access.** An adversary-in-the-middle phishing page relays an administrator's sign-in: MFA is enforced by authentication strength, but not the phishing-resistant strength, for all users or for privileged roles (MS.AAD.3.1v1, MS.AAD.3.6v1). Alternative routes run through the account excluded from the legacy-authentication block (MS.AAD.1.1v1) or the exclusions on the device-code block (MS.AAD.3.9v1); whose accounts those are is UNKNOWN (H6).
3. **Privilege escalation.** None is needed: six highly privileged roles carry permanent active assignments, four are assigned outside PIM, and Global Administrator activation needs no approval (MS.AAD.7.4v1, MS.AAD.7.5v1, MS.AAD.7.6v1); Global Administrator is used where finer-grained roles would do (MS.AAD.7.2v1).
4. **Persistence.** New role assignments go unannounced: six roles send no assignment notification and five send none on activation (MS.AAD.7.7v1, MS.AAD.7.9v1), so an added administrator or application credential can stand unseen.

Earliest breaking control: phishing-resistant MFA required for the highly privileged roles (MS.AAD.3.6v1) Status: Gap.

### Chain B: Illicit consent through a third-party application

1. **Initial access.** A user is lured to consent to an attacker's multi-tenant application, which the authorization policy allows even for risky delegated permissions (MS.AAD.5.2v1); any user may also register applications (MS.AAD.5.1v1).
2. **Persistence.** The grant outlives a password reset and sits among the 10 applications and 1 third-party service principal the scan already flags as holding risky permissions (A10).
3. **Collection/exfiltration.** Mail and files are read through Microsoft Graph as the application, activity that sign-in protections do not cover.

Earliest breaking control: user consent to applications restricted, with requests routed to the admin consent workflow (MS.AAD.5.2v1) Status: Gap.

### Chain C: Anonymous links into SharePoint content

1. **Initial access.** SharePoint external sharing is set to Anyone (MS.SHAREPOINT.1.1v1), so a forwarded or leaked link opens content without sign-in.
2. **Privilege escalation.** Anyone links on folders allow edit, not view only (MS.SHAREPOINT.3.2v1): the holder of a folder link can add or replace files for the 30 days the link lives.
3. **Execution.** A planted file reaches staff from a trusted site; Safe Attachments does not scan SharePoint, OneDrive or Teams files (MS.SECURITYSUITE.1.4v1).

Earliest breaking control: SharePoint external sharing limited to existing guests or to people in the organization (MS.SHAREPOINT.1.1v1) Status: Gap.

### Chain D: Data movement through unrestricted Power Platform connectors

1. **Initial access.** Any signed-in user, or an attacker holding one user's session from Chain A or B, can build a flow in the default environment.
2. **Collection/exfiltration.** With no DLP policy in the default environment (MS.POWERPLATFORM.2.1v1) or the other environment (MS.POWERPLATFORM.2.2v1), the flow can join a business connector to any non-business connector and copy data out; Purview DLP covers Devices only, not SharePoint, OneDrive or Exchange (MS.SECURITYSUITE.3.2v1).

Earliest breaking control: a DLP policy restricting connector access in the default Power Platform environment (MS.POWERPLATFORM.2.1v1) Status: Gap.

## Fixes

| ID | Action | Rubric | Effort | Breaks | Status |
|---|---|---|---|---|---|
| F-1 | Remove the user exclusion from the legacy-authentication block policy, or record the excluded account as a documented emergency-access exclusion in the ScubaGear configuration, so legacy authentication is blocked for every account. | MS.AAD.1.1v1 | An hour | A | proposed |
| F-2 | Register passkeys for every user and switch the all-user Conditional Access policy to the phishing-resistant MFA authentication strength, in report-only mode first. | MS.AAD.3.1v1 | Days, staged | A | proposed |
| F-3 | Require the phishing-resistant MFA authentication strength for the highly privileged roles in Conditional Access, ahead of the all-user rollout. | MS.AAD.3.6v1 | An hour | A | proposed |
| F-4 | Set "Users can register applications" to No, so only administrators register applications. | MS.AAD.5.1v1 | Minutes | B | proposed |
| F-5 | Restrict user consent so users cannot consent to third-party applications, and send requests through the admin consent workflow that is already configured. | MS.AAD.5.2v1 | Minutes | B | proposed |
| F-6 | Find the domain whose password policy failed the check and set its user passwords to never expire. | MS.AAD.6.1v1 | Minutes | None (password hygiene) | proposed |
| F-7 | Move privileged tasks off Global Administrator onto finer-grained roles, so privileged users without Global Administrator at least equal the two Global Administrators the baseline's minimum requires. | MS.AAD.7.2v1 | An hour | A | proposed |
| F-8 | Convert the permanent active assignments in the six highly privileged roles to PIM-eligible assignments. | MS.AAD.7.4v1 | An hour | A | proposed |
| F-9 | Re-provision the four roles assigned outside PIM through PIM, and remove the direct assignments. | MS.AAD.7.5v1 | An hour | A | proposed |
| F-10 | Require approval to activate Global Administrator in the PIM role settings, with an approver other than the requester. | MS.AAD.7.6v1 | Minutes | A | proposed |
| F-11 | Turn on assignment notification e-mail for the six highly privileged roles the run names, sent to a monitored address. | MS.AAD.7.7v1 | Minutes each | A | proposed |
| F-12 | Confirm the licence the risky-agent policy needs (Entra ID P2 plus Microsoft Agent 365 or Microsoft 365 E7), then add a Conditional Access policy that blocks risky AI agents. | MS.AAD.9.1v1 | An hour | None (agent sign-ins) | proposed |
| F-13 | Create a DLP policy for the default Power Platform environment that keeps business connectors apart from non-business connectors and blocks the connectors the firm does not use. | MS.POWERPLATFORM.2.1v1 | An hour | D | proposed |
| F-14 | Lower SharePoint external sharing from Anyone to Existing guests, or to Only people in your organization. | MS.SHAREPOINT.1.1v1 | Minutes | C | proposed |
| F-15 | Set the allowable permission for Anyone links on folders to View. | MS.SHAREPOINT.3.2v1 | Minutes | C | proposed |

## Verify next

1. **Unknown:** Whether the five Entra SHOULD warnings are accepted risk or open work: managed devices for sign-in and for MFA registration (MS.AAD.3.7v1, MS.AAD.3.8v1), the device-code block and its exclusions (MS.AAD.3.9v1), activation alerts for five highly privileged roles (MS.AAD.7.9v1), and who may invite guests (MS.AAD.8.2v1). **Why it changes the picture:** A SHOULD shortfall needs a recorded decision, not just a result; the device-code exclusions decide whether Chain A has a second door, and managed-device policies need an Intune licence the run does not show. **Cheapest check:** Entra admin center -> Protection -> Conditional Access (the device-code policy's exclusions); Identity governance -> Privileged Identity Management -> Microsoft Entra roles -> Settings (activation notifications); External Identities -> External collaboration settings (guest invite restrictions).
2. **Unknown:** Why DKIM is not enabled on tidewateradvisory.example (MS.EXO.3.1v1). **Why it changes the picture:** Unsigned mail from the default domain weakens DMARC alignment for that domain; turning DKIM on is cheap once the reason is known. **Cheapest check:** Microsoft Defender portal -> Email & collaboration -> Policies & rules -> Threat policies -> Email authentication settings -> DKIM.
3. **Unknown:** Whether Power BI needs external-user invitations, ResourceKey authentication, and R and Python visuals (MS.POWERBI.3.1v1, MS.POWERBI.5.1v1, MS.POWERBI.6.1v1). **Why it changes the picture:** Each is allowed by the baseline only where a mission need is stated; the run cannot see the need, only the setting. **Cheapest check:** Power BI admin portal -> Tenant settings: "Invite external users to your organization", "Block ResourceKey Authentication", "Interact with and share R and Python visuals".
4. **Unknown:** What the non-default Power Platform environment is for, and whether it needs its own DLP policy (MS.POWERPLATFORM.2.2v1). **Why it changes the picture:** The default-environment fix (F-13) does not cover it; a second environment with no DLP policy keeps Chain D open there. **Cheapest check:** Power Platform admin center -> Environments (purpose and owner), then Policies -> Data policies.
5. **Unknown:** The four Security Suite warnings: Safe Attachments for SharePoint, OneDrive and Teams (MS.SECURITYSUITE.1.4v1), impersonation protection for sensitive users and partner domains (MS.SECURITYSUITE.2.1v1, MS.SECURITYSUITE.2.3v1), and DLP locations beyond Devices (MS.SECURITYSUITE.3.2v1). **Why it changes the picture:** Two of them read as warnings only because the run configuration lists no sensitive users or partner domains (H2), so the human look decides whether they are gaps; 1.4 and 3.2 bear on Chains C and D. **Cheapest check:** Defender portal -> Threat policies -> Safe Attachments -> Global settings; Anti-phishing -> the policy's impersonation lists; Microsoft Purview -> Data loss prevention -> Policies -> locations.
