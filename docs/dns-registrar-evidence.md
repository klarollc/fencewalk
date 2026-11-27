# Gathering evidence for the DNS and registrar pack

How an operator gathers the evidence that `dns-registrar-security-1.0` is
scored against, for their own organization. Fencewalk adds no importer and
no network code for this: you run read-only DNS queries yourself and read
your own registrar and DNS provider consoles, then record what you see as
inventory entries and scores through the existing CLI or web paths
(`add-entry`, `score`).

## Rules

- **Read-only.** Every read below is a DNS query, an HTTPS GET or a
  console page view. Nothing is changed at the registrar, at the DNS
  provider, or in any zone.
- **Your own accounts.** Console reads use the organization's own
  registrar and DNS provider logins, made by or with their holders.
- **Nothing secret in Fencewalk.** Never record a password, recovery code,
  API token, TSIG key, DNSSEC private key or zone-file secret in an
  inventory entry. Record settings, states and counts in prose, as the
  bundled `dns-registrar` fixture does.
- `DOMAIN` below is one of your domains; `NS1` / `NS2` its nameservers.

Each read is marked **DNS query** (a `dig` read anyone can run; any
DNS-over-HTTPS resolver's JSON interface answers the same questions),
**Registrar console**, or **DNS provider console**. Console page names
differ between providers: read the page by what it controls, not by the
menu path.

## Sources

The pack's items are selected and reworded from these sources for a small
organization:

- IETF RFCs: RFC 7208 (SPF); RFC 6376 (DKIM) and RFC 8301 (DKIM key
  sizes); RFC 9989 (DMARC; obsoletes RFC 7489), RFC 9990 (DMARC aggregate
  reporting) and RFC 9991 (DMARC failure reporting); RFC 8617 (ARC);
  RFC 8461 (MTA-STS) and RFC 8460 (SMTP TLS reporting); RFC 8659 (CAA);
  RFC 6698 and RFC 7671 (DANE); RFC 4033, 4034, 4035 and RFC 9364
  (DNSSEC); RFC 2182 (secondary DNS); RFC 1912 (common DNS errors,
  including lame delegation and §2.7 on wildcard records).
- NIST SP 800-81 Rev. 3, *Secure Domain Name System (DNS) Deployment
  Guide* (March 2026), §3.1 and §3.1.1 (zone transfer restriction). US
  government work, public domain.
- CISA Binding Operational Directive 18-01 (email authentication; US
  government work, public domain).
- NCSC, "Managing public domain names" and "Email security and
  anti-spoofing", retrieved 2026-11-24. Contains public sector
  information licensed under the Open Government Licence v3.0
  (https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
- ICANN, EPP status codes (clientTransferProhibited and the registry
  lock statuses), retrieved 2026-11-24.

## 1. Registrar account and domains (DNS-REG-01 – DNS-REG-05)

1. **Registrar console** — account security page: whether
   multi-factor authentication is on for every login, and which recovery
   email and phone the account carries (record whose they are, not the
   values).
2. **Registrar console** — each domain's settings: transfer lock,
   whether the registry offers registry lock and whether it is on,
   auto-renew, expiry date, and the payment method's validity.
3. **DNS query** (RDAP) — `whois DOMAIN`, or the registry's RDAP record
   for the domain: the EPP status codes (`clientTransferProhibited`; the
   `server*Prohibited` codes when registry lock is on) and the expiry
   date, as the registry sees them.
4. **Registrar console** — the account's full domain list, at every
   registrar account the organization holds; compare against the
   organization's own domain list. Accounts nobody listed are found by
   asking and by searching the shared password manager, not by a query.

## 2. Zone integrity (DNS-ZONE-01 – DNS-ZONE-04)

1. **DNS provider console** — users and security pages: who has access,
   and whether two-step verification is on for each login.
2. **DNS query** — `dig +dnssec DNSKEY DOMAIN` and `dig DS DOMAIN`: does
   the zone publish DNSKEY records, and does the parent hold DS records
   that match them. **DNS provider console** — the DNSSEC settings page,
   for the provider's view.
3. **DNS provider console** — the activity or audit log: whether zone
   changes are logged, by whom, and when the last changes were. Whether
   anyone reviews it is a question for the people.
4. **DNS query** — `dig NS DOMAIN` at the parent (`dig +trace NS DOMAIN`)
   and `dig NS DOMAIN @NS1` / `@NS2`: the parent's and the zone's own
   nameserver sets match; `dig SOA DOMAIN @NS1` / `@NS2` with `+norec`:
   each answers authoritatively (the `aa` flag) with the same serial. A
   server that does not answer authoritatively is a lame delegation.

## 3. Nameserver resilience (DNS-NS-01 – DNS-NS-03)

1. **DNS query** — `dig A NS1` / `dig AAAA NS1` (and for NS2), then look
   up the routing origin of each address: are the nameservers on separate
   networks, or all in one provider's network.
2. **DNS query** — from a network outside the organization,
   `dig AXFR DOMAIN @NS1` and `@NS2`: a refusal (`Transfer failed`) is the
   expected answer. This is a read request; it changes nothing, but the
   provider may log it, so run it against your own domains only.
3. **DNS provider console** — the zone export function, and the
   organization's own repository or file store: is a current copy of the
   records kept outside the provider. Whether one exists is a question for
   the people.

## 4. Email authentication (DNS-EM-01 – DNS-EM-08)

1. **DNS query** — `dig TXT DOMAIN`: exactly one `v=spf1` record; its
   mechanisms and its final `-all` or `~all`. Follow each `include:` and
   count the lookups (RFC 7208 limits them to 10).
2. **DNS query** — `dig TXT SELECTOR._domainkey.DOMAIN` for each DKIM
   selector the sending services use: the key type and size. Selectors are
   not discoverable by query; take them from each service's settings or
   from the `DKIM-Signature` header (`s=`) of a message it sent.
3. **DNS query** — `dig TXT _dmarc.DOMAIN`: the `p`, `sp` and `np` tags
   and the `rua` reporting address.
4. **DNS query** — the same reads for each domain that sends no mail: a
   null SPF record (`v=spf1 -all`) and a DMARC record at `p=reject`;
   `dig MX DOMAIN` confirms it accepts no mail.
5. The aggregate report mailbox (the `rua` address): whether anyone reads
   it, and which senders the reports show as misaligned. This is the
   organization's own mailbox, read with its holder.
6. The mapping from each SPF include and DKIM selector to a service still
   in use is a question for the people, checked against reads 1 and 2.

## 5. Mail transport and certificate issuance (DNS-TLS-01 – DNS-TLS-04)

1. **DNS query** — `dig TXT _mta-sts.DOMAIN`, then an HTTPS GET of
   `https://mta-sts.DOMAIN/.well-known/mta-sts.txt`: the policy's `mode`
   (`enforce`, `testing` or `none`).
2. **DNS query** — `dig TXT _smtp._tls.DOMAIN`: the TLS-RPT `rua`
   address. Whether anyone reads it is a question for the people.
3. **DNS query** — `dig CAA DOMAIN`: the `issue` and `issuewild`
   authorities.
4. **DNS query** — `dig MX DOMAIN`, then `dig TLSA _25._tcp.MX-HOST` for
   each mail server: TLSA records where the mail platform supports DANE.
   Whether the platform supports DANE is in its documentation.

## 6. Subdomain hygiene (DNS-SUB-01 – DNS-SUB-04)

1. **DNS provider console** — the zone's full record list: every
   subdomain, what it points at, and every wildcard. Compare against the
   organization's own subdomain list, if one exists.
2. **DNS query** — `dig CNAME NAME.DOMAIN` for each alias, then an HTTPS
   GET of the name: a target service answering that no site is configured
   marks a dangling record.
3. **DNS query** — `dig NS NAME.DOMAIN` for each delegated subdomain, then
   `dig SOA NAME.DOMAIN @each-delegated-server`: who answers for it. Who
   operates those servers now is a question for the people and the
   former vendor.
4. **DNS query** — `dig A random-label.NAME.DOMAIN` for two random labels:
   matching answers confirm a wildcard. Its reason is a question for the
   people.

## Reads to inventory entries

The `dns-registrar` fixture's entries, with the reads that ground them:

| Entry | Grounded by |
|---|---|
| A1 | Group 1 read 1 |
| A2 | Group 1 reads 2–3 |
| A3 | Group 1 read 4 (and the office manager's domain list) |
| A4 | Group 1 read 4's limit: only the second account's active list was viewed (UNKNOWN) |
| B1 | Group 2 read 1 |
| B2 | Group 2 read 2 |
| B3 | Group 2 read 3 |
| B4 | Group 2 read 3, the people part (ON RECORD) |
| B5 | Group 3 read 3 (ON RECORD) |
| C1 | Group 2 read 4; group 3 read 1 |
| C2 | Group 3 read 2, not yet run (UNKNOWN) |
| D1 | Group 4 read 1 |
| D2 | Group 4 read 6 (ON RECORD) |
| D3 | Group 4 read 5, not yet run (UNKNOWN) |
| D4 | Group 4 read 2 |
| D5 | Group 4 reads 3 and 5 |
| D6 | Group 4 read 4 |
| E1 | Group 5 reads 1–3 |
| E2 | Group 5 read 4, the platform part, not yet checked (UNKNOWN) |
| F1 | Group 6 read 1, the people part (ON RECORD) |
| F2 | Group 6 read 2 |
| F3 | Group 6 read 3 |
| F4 | Group 6 read 3, the people part, not yet asked (UNKNOWN) |
| F5 | Group 6 read 4 |
| F6 | Group 6 read 4, the people part (ON RECORD) |

## Reads not confirmed

- Registrar and DNS provider console pages are named here by what they
  control, not by menu path: every provider names and arranges them
  differently, and none was checked against a live console.
- Whether a registrar's or registry's RDAP record shows registry lock
  depends on the registry: the `server*Prohibited` status codes appear
  only where the registry implements the lock with them.
- The AXFR read is a query, but some providers flag repeated transfer
  attempts; it was not run against a live provider for this document.
- The routing-origin lookup in group 3 read 1 depends on a public routing
  data service of the operator's choosing; none is named or was checked.
- DKIM selectors cannot be listed from DNS (group 4 read 2): an
  unconfirmed sender may have a selector this method does not find.
