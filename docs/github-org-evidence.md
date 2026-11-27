# Gathering evidence for the GitHub organization pack

How an operator gathers the evidence that `github-org-security-1.0` is
scored against, for their own organization. Fencewalk adds no importer and
no network code for this: you run read-only reads with your own
authenticated `gh` CLI, or read the organization's settings pages, and
record what you see as inventory entries and scores through the existing
CLI or web paths (`add-entry`, `score`).

## Rules

- **Read-only.** Every read below is a GET or a page view. Nothing is
  written back to GitHub.
- **Your own authentication.** Run `gh auth login` yourself; the
  credential lives in `gh`, never in Fencewalk. Most organization settings
  reads need an organization owner's session.
- **No token in Fencewalk.** Never paste a token, a secret value or a
  webhook secret into an inventory entry. Record settings and counts in
  prose, as the bundled `github-org` fixture does.
- `ORG` below is your organization's login; `REPO` a repository in it.

Each read is marked **API** (a `gh api` path; the REST API's GET
endpoint), **gh** (another read-only `gh` command), or **Settings page**
(no REST route on a Team-plan organization: read the named page). The
endpoints were checked against the REST API description in the GitHub Docs
tree at `github/docs` @ `bd60abd2de5c9285e34ce3ea794274e973b0633e`
(`src/rest/data/fpt-2022-11-28/`); settings pages against the same tree's
`content/organizations/` articles.

## 1. Identity and access (GH-ID-01 – GH-ID-05)

1. **API** `gh api /orgs/ORG` — `plan.name` (the plan: Free, Team or
   Enterprise Cloud) and `two_factor_requirement_enabled`.
2. **API** `gh api "/orgs/ORG/members?filter=2fa_disabled" --paginate` and
   `gh api "/orgs/ORG/outside_collaborators?filter=2fa_disabled" --paginate`
   — who has no two-factor authentication. `filter=2fa_insecure` lists
   those using an insecure method such as SMS.
3. **API** `gh api "/orgs/ORG/members?role=admin" --paginate` — the
   owners, whose methods the next read checks.
4. **Settings page** — each owner's own **Settings → Password and
   authentication** page, viewed with that owner: the registered two-factor
   methods (passkey, security key, authenticator app, SMS). No API reads
   another user's methods.
5. **Plan check** (SAML, IP allow list, restricted email notifications) —
   on an organization not on GitHub Enterprise Cloud these are not
   settings reads: read 1's `plan.name` decides them. SAML single sign-on,
   IP allow lists and restricted email notifications each require
   GitHub Enterprise Cloud, so on Free or Team record the plan and score
   GH-ID-03, GH-ID-04 and GH-ID-05 Not applicable with that reason. On
   Enterprise Cloud, read **Settings → Authentication security** (SAML
   single sign-on, IP allow list) and **Settings → Verified and approved
   domains** (restricted email notifications).

## 2. Membership and ownership (GH-MEM-01 – GH-MEM-05)

1. **API** `gh api /orgs/ORG` — `default_repository_permission` (base
   permissions), `members_can_create_public_repositories`,
   `members_can_create_private_repositories`,
   `members_can_create_public_pages`, `members_can_create_private_pages`,
   `members_can_fork_private_repositories`.
2. **API** `gh api /orgs/ORG/outside_collaborators --paginate`, then per
   repository `gh api "/repos/ORG/REPO/collaborators?affiliation=outside"`
   — who the outside collaborators are and where they have access.
3. **Settings page** — **Settings → Member privileges → Repository outside
   collaborators**: whether repository administrators may invite outside
   collaborators. (The owner-only restriction exists only on Enterprise
   Cloud.) No collaborator access review is visible anywhere in GitHub:
   ask for the review record.
4. **API** read 3 of group 1 (`role=admin`) — the owner count.

## 3. Programmatic access (GH-TOK-01 – GH-TOK-06)

1. **Settings page** — **Settings → Third-party access → OAuth app
   policy**: whether OAuth app access restrictions are set up, and which
   apps are approved.
2. **Settings page** — **Settings → Member privileges**, under "App access
   requests" and "GitHub Apps": who may request apps, and whether
   repository administrators may install GitHub Apps.
3. **API** `gh api /orgs/ORG/installations --paginate` — the installed
   GitHub Apps, each with its repository selection. Who owns each app
   internally is a question for the people, not the API.
4. **Settings page** — **Settings → Personal access tokens → Settings**:
   whether fine-grained tokens need approval and whether classic tokens
   are allowed.
5. **API** `gh api /orgs/ORG/personal-access-tokens --paginate` and
   `gh api /orgs/ORG/personal-access-token-requests --paginate` — the
   fine-grained tokens with access (including last use) and pending
   requests. Classic tokens are not listed for an organization without
   SAML single sign-on: ask their holders.
6. **API** per repository `gh api /repos/ORG/REPO/keys` — deploy keys,
   with read-only flag and creation date. `gh api /orgs/ORG` field
   `deploy_keys_enabled_for_repositories` is the organization policy where
   the plan offers it.

## 4. GitHub Actions (GH-ACT-01 – GH-ACT-06)

1. **API** `gh api /orgs/ORG/actions/permissions` and
   `gh api /orgs/ORG/actions/permissions/selected-actions` — which actions
   and reusable workflows are allowed.
2. **API** `gh api /orgs/ORG/actions/permissions/workflow` —
   `default_workflow_permissions` (read or write) and
   `can_approve_pull_request_reviews`.
3. **API** `gh api /orgs/ORG/actions/permissions/fork-pr-contributor-approval`
   — `approval_policy` for fork pull request workflows.
4. **API** `gh api /orgs/ORG/actions/permissions/artifact-and-log-retention`
   — the retention period.
5. **API** `gh api /orgs/ORG/actions/permissions/self-hosted-runners`,
   `gh api /orgs/ORG/actions/runners` and
   `gh api /orgs/ORG/actions/runner-groups` (then
   `.../runner-groups/{id}/repositories` per group) — runners, groups and
   which repositories each group serves.
6. **API** `gh api /orgs/ORG/actions/secrets --paginate` — secret names
   and `visibility` (`all`, `private`, `selected`); never values.
7. **gh** `gh workflow list -R ORG/REPO` and
   `gh api /repos/ORG/REPO/contents/.github/workflows` — the workflows in
   each public repository, read for `pull_request_target` triggers.

## 5. Code security defaults (GH-CODE-01 – GH-CODE-06)

1. **API** `gh api /orgs/ORG/code-security/configurations` and
   `gh api /orgs/ORG/code-security/configurations/defaults` — the security
   configurations and which one is the default for new repositories:
   secret scanning, push protection, Dependabot alerts and security updates,
   private vulnerability reporting.
2. **API** `gh api /orgs/ORG/rulesets` (then `/orgs/ORG/rulesets/{id}`) —
   organization rulesets and their rules.
3. **API** per public repository
   `gh api /repos/ORG/REPO/private-vulnerability-reporting` — whether
   private vulnerability reporting is enabled.
4. **API** group 2 read 1 — `members_can_fork_private_repositories`.

## 6. Webhooks (GH-WH-01 – GH-WH-03)

1. **API** `gh api /orgs/ORG/hooks` — each organization webhook: URL,
   events, `active`, and `config.insecure_ssl` (`"0"` means SSL
   verification is on). `config.secret` reads `********` when a secret is
   set and is absent when none is.
2. **API** `gh api /orgs/ORG/hooks/{hook_id}/deliveries` — recent
   deliveries and their response codes, for failing or unexpectedly
   succeeding endpoints.
3. Who operates each endpoint, and each webhook's purpose and owner, are
   not in GitHub: resolve the endpoint's host name and ask.

## 7. Audit (GH-AUD-01 – GH-AUD-03)

1. **Settings page** — **Settings → Archive → Logs → Audit log**: the
   events of the last 180 days, and **Export** (JSON or CSV) for retention
   beyond it. The REST audit log endpoint for organizations is an
   Enterprise Cloud feature; it is not in the API description for other
   plans.
2. **Settings page** — the same **Audit log** page, **Settings** tab,
   "Disclose actor IP addresses in audit logs" (public preview).
   Identifying events performed by an access token is an Enterprise Cloud
   feature.
3. Whether the log is reviewed, and whether exports are kept, is a
   question for the owners: ask for the record.

## Reads to inventory entries

The `github-org` fixture's entries, with the reads that ground them:

| Entry | Grounded by |
|---|---|
| A1 | Group 1 read 1 (`plan.name`); `gh api /orgs/ORG/members`, `/outside_collaborators`, `gh repo list ORG` |
| A2 | Group 1 read 3 |
| A3 | Group 1 reads 1–2 |
| A4, A5 | Group 1 read 4 (A5 is UNKNOWN because that read was not made) |
| A6 | Group 1 read 5 (plan check) |
| B1, B2 | Group 2 read 1; each public repository's Pages settings page |
| B3 | Group 2 reads 2–3 |
| C1 | Group 3 reads 1–3 |
| C2 | Group 3 reads 4–5 |
| C3 | Group 3 read 5's limit: classic tokens are not listed; ask holders |
| C4 | Group 3 read 3, plus asking the staff (UNKNOWN until asked) |
| C5 | Group 3 read 6 |
| D1 | Group 4 reads 1–5 |
| D2 | Group 4 read 6 |
| D3 | Group 4 read 7 |
| E1 | Group 5 reads 1–3 |
| F1 | Group 6 reads 1–2 |
| F2, F3 | Group 6 read 3 (F2 is what the owners said; F3 is UNKNOWN until checked) |
| G1 | Group 7 reads 1–2 |
| G2 | Group 7 read 3 |
| H1 | Not a GitHub read: the firm's own Microsoft 365 review, recorded ON RECORD |

## Reads not confirmed

- Settings page names and menu paths (for example **Settings → Archive →
  Logs → Audit log**, **Third-party access**) follow the pinned docs'
  wording; GitHub renames menus, so read the page by its heading if the
  path has moved.
- The `plan` object in `GET /orgs/ORG` is returned only to organization
  owners; with a member's session it is absent and the plan must be read
  on **Settings → Billing and plans**.
- `members_can_create_public_repositories` and the related member
  privilege fields are listed in the REST description, but whether every
  one is populated on every plan was not confirmed against a live
  organization; where a field is missing, read **Settings → Member
  privileges**.
