# Engagement report — DNS and registrar case — Wrenfield Advisory perimeter audit

- Subject: Wrenfield Advisory LLC (fictional demo firm)
- Engagement created: 2026-11-20
- Method order: verify-first
- Rubric pack: DNS and Registrar — Domain Security Expected State (curated) (Curated from the IETF RFCs named in docs/dns-registrar-evidence.md, CISA BOD 18-01, and NCSC guidance (Open Government Licence v3.0), retrieved 2026-11-24. Items are selected and reworded for a small organization.)

## Posture summary

- Inventory: 25 entries (VERIFIED 15, ON RECORD 5, UNKNOWN 5)
- Coverage: Covered 3 · Partial 5 · Unknown 2 · Not applicable 0 · Gap 18 — 28 rows
- Attack chains: 3
- Fixes: 10 (proposed 10, approved 0, done 0, deferred 0)
- Verify-next items: 5

## Coverage

Tallies: Covered 3 · Partial 5 · Unknown 2 · Not applicable 0 · Gap 18 — 28 rows

| Item | Group | Status | Reasoning | Cited entries |
|---|---|---|---|---|
| DNS-EM-01 | Email authentication | Partial | One SPF record within the lookup limit, but it still names a marketing platform the firm stopped using in 2024. | D1, D2, D3 |
| DNS-EM-02 | Email authentication | Gap | The SPF record ends in a soft fail (~all), with no dated step toward -all. | D1 |
| DNS-EM-03 | Email authentication | Partial | The mail platform signs with 2048-bit keys; the invoicing tool sends unsigned. | D4 |
| DNS-EM-04 | Email authentication | Gap | DMARC has been at p=none since 2023, with no dated step toward enforcement. | D5 |
| DNS-EM-05 | Email authentication | Gap | Aggregate reports go to a mailbox nobody reads; the unread reports go back to 2023. | D5 |
| DNS-EM-06 | Email authentication | Gap | Neither the sp nor the np tag is published. | D5 |
| DNS-EM-07 | Email authentication | Gap | The parked domain sends no mail and publishes no SPF and no DMARC record. | D6 |
| DNS-EM-08 | Email authentication | Gap | The sender mapping has never been re-checked: the SPF record still includes the marketing platform dropped in 2024. | D1, D2 |
| DNS-NS-01 | Nameserver resilience | Gap | Two nameservers, but both sit in the DNS provider's single network. | C1 |
| DNS-NS-02 | Nameserver resilience | Unknown | Whether either nameserver refuses an outside zone transfer has never been tested. | C2 |
| DNS-NS-03 | Nameserver resilience | Gap | No copy of either zone's records is kept outside the DNS provider. | B5 |
| DNS-REG-01 | Registrar account and domains | Partial | Multi-factor authentication is on, but the recovery email is a departed staff member's personal address, which the firm does not control. | A1 |
| DNS-REG-02 | Registrar account and domains | Covered | Transfer lock is on for both domains at the registrar. | A2 |
| DNS-REG-03 | Registrar account and domains | Gap | The registry offers registry lock and it is not enabled on either domain. | A2 |
| DNS-REG-04 | Registrar account and domains | Gap | Auto-renew is off on both domains; the main domain expires in about four months. | A2 |
| DNS-REG-05 | Registrar account and domains | Partial | The two main domains are listed with owner and purpose, but a second registrar account holds two domains that appear on no list. | A3, A4 |
| DNS-SUB-01 | Subdomain hygiene | Gap | No subdomain inventory exists. | F1 |
| DNS-SUB-02 | Subdomain hygiene | Gap | help.wrenfield.example still points at the helpdesk service the firm left in 2024. | F2 |
| DNS-SUB-03 | Subdomain hygiene | Gap | projects.wrenfield.example is delegated to a former web vendor's nameservers, unchanged and unreviewed since 2022; who operates them now is unknown. | F3, F4 |
| DNS-SUB-04 | Subdomain hygiene | Partial | One wildcard exists; its reason is only half remembered and nothing records it. | F5, F6 |
| DNS-TLS-01 | Mail transport and certificate issuance | Gap | No MTA-STS record or policy is published. | E1 |
| DNS-TLS-02 | Mail transport and certificate issuance | Gap | No TLS-RPT record is published. | E1 |
| DNS-TLS-03 | Mail transport and certificate issuance | Gap | No CAA record is published, so any certificate authority may issue for the domains. | E1 |
| DNS-TLS-04 | Mail transport and certificate issuance | Unknown | Whether the mail platform supports DANE has never been checked. | E2 |
| DNS-ZONE-01 | Zone integrity | Covered | Two-step verification is on for both logins, and only the two administrators who manage the zones have access. | B1 |
| DNS-ZONE-02 | Zone integrity | Gap | DNSSEC was never enabled: no DNSKEY records and no DS records. | B2 |
| DNS-ZONE-03 | Zone integrity | Gap | The provider logs zone changes, but nobody reviews the log. | B3, B4 |
| DNS-ZONE-04 | Zone integrity | Covered | The parent's nameserver records match the zone's own and both nameservers answer authoritatively. | C1 |

## Attack chains

### Chain A: Spoofed invoice

1. **Reconnaissance.** The firm bills clients by email from its own domain (D4); a client and an invoice cycle are easy to learn.
2. **Initial access.** An attacker sends a payment-change email as the firm to a client. The SPF record ends in a soft fail and DMARC is at p=none (DNS-EM-02, DNS-EM-04; D1, D5), so receivers apply no enforcement and the message delivers as genuine.
3. **Impact.** The client pays the next invoice to the attacker's account.

Earliest breaking control: a DMARC enforcement policy in force (p=quarantine, then p=reject once the aggregate reports allow) (DNS-EM-04) Status: Gap.

### Chain B: Subdomain takeover

1. **Reconnaissance.** help.wrenfield.example still points at the helpdesk service the firm left in 2024, which answers that no site is configured for the name (DNS-SUB-02; F2).
2. **Initial access.** An attacker opens an account at the helpdesk service and claims that name, so the firm's own subdomain serves the attacker's page.
3. **Collection/exfiltration.** A credential-harvesting page answers on a subdomain of the firm's real domain, and clients and staff trust the name.

Earliest breaking control: dangling records to deprovisioned services removed (DNS-SUB-02) Status: Gap.

### Chain C: Registrar social engineering

1. **Initial access.** An attacker calls the registrar's support desk posing as the firm. The account's recovery contact is a departed staff member's personal mailbox (DNS-REG-01; A1), so the firm sees none of the support desk's notices.
2. **Impact.** The support desk changes the domain's nameservers. With no registry lock (DNS-REG-03; A2) nothing holds the change until a lock is removed, and it takes effect.
3. **Collection/exfiltration.** The attacker's zone points the domain's mail at the attacker, and the firm's mail is rerouted for a weekend before anyone notices.

Earliest breaking control: registry lock, so the domain cannot be changed until the lock is removed (DNS-REG-03) Status: Gap.

## Fixes

| ID | Action | Rubric | Effort | Breaks | Status |
|---|---|---|---|---|---|
| F-1 | Move DMARC from p=none to p=quarantine now, and route aggregate reports to a mailbox someone reads; read the reports for at least a month, then move to p=reject if they show no mailing-list or forwarding breakage. | DNS-EM-04, DNS-EM-05 | An hour, then a month of report reading | A | proposed |
| F-2 | Remove the marketing platform's include from the SPF record and, once the aggregate reports show every remaining sender passing, change ~all to -all. | DNS-EM-01, DNS-EM-02, DNS-EM-08 | An hour, after the reports are read | A | proposed |
| F-3 | Turn on DKIM signing for the invoicing tool with a 2048-bit key and publish its selector. | DNS-EM-03 | An hour | A | proposed |
| F-4 | Delete the help.wrenfield.example CNAME. | DNS-SUB-02 | Minutes | B | proposed |
| F-5 | Replace the registrar account's recovery email with a firm-controlled address, then ask the registrar to enable registry lock on wrenfield.example. | DNS-REG-01, DNS-REG-03 | An hour, plus the registry's lock fee | C | proposed |
| F-6 | Turn on auto-renew for both domains at the registrar. | DNS-REG-04 | Minutes | None (prevents expiry) | proposed |
| F-7 | Publish a null SPF record (v=spf1 -all) and a DMARC record at p=reject for wrenfieldgroup.example. | DNS-EM-07 | Minutes | None (parked domain) | proposed |
| F-8 | Enable DNSSEC for both zones at the DNS provider and publish the DS records at the registrar. | DNS-ZONE-02 | An hour | None (zone integrity) | proposed |
| F-9 | Add the second registrar account's domains to the domain list with an owner and purpose, and decide whether to keep, transfer or let each lapse. | DNS-REG-05 | Half a day | None (inventory) | proposed |
| F-10 | Remove the projects.wrenfield.example delegation, or re-own it with a named owner and a quarterly review. | DNS-SUB-03 | An hour | None (delegation) | proposed |

## Verify next

1. **Unknown:** Whether either nameserver answers a zone transfer request from an outside address (C2). **Why it changes the picture:** An open transfer hands anyone the zone's full record list, including names not otherwise published; DNS-NS-02 stays Unknown until it is tested. **Cheapest check:** From a network outside the firm, request a zone transfer from each nameserver (dig AXFR wrenfield.example at each one); a refusal settles it.
2. **Unknown:** Whether the hosted mail platform supports DANE for inbound mail (E2). **Why it changes the picture:** DNS-TLS-04 applies only where the platform supports DANE; until that is known it stays Unknown. **Cheapest check:** The mail platform's documentation on DANE, or a TLSA query for its published mail server names.
3. **Unknown:** The full contents of the second registrar account (A4). **Why it changes the picture:** Domains in nobody's inventory expire or get hijacked unnoticed; DNS-REG-05 cannot be settled from the active list alone. **Cheapest check:** Sign in to the second account and read every domain's state, including expired and redemption, and its recovery contacts.
4. **Unknown:** Whether the marketing platform still sends anything using the domain (D3). **Why it changes the picture:** If it still sends, removing its SPF include (F-2) breaks that mail; if it does not, the include only authorizes a service nobody controls. **Cheapest check:** Read the last month of DMARC aggregate reports for the marketing platform's sending sources.
5. **Unknown:** Who operates the delegated nameservers for projects.wrenfield.example today (F4). **Why it changes the picture:** If the former vendor no longer runs them, whoever does controls a subdomain of the firm's domain, the same exposure as Chain B by another route. **Cheapest check:** Look up who holds the nameservers' domain and addresses, and ask the former vendor whether it still runs them.
