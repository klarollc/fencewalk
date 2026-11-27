# DNS-registrar fixture

A public demo dataset for Fencewalk's DNS and registrar pack
(`dns-registrar-security-1.0`): a complete engagement (inventory, rubric
coverage, attack chains, fixes, verify-next) for a fictional firm's
domains, DNS and mail authentication. It is the fourth bundled fixture,
beside `reference-case` (FLASH), `demo-scuba` (SCuBA) and `github-org`
(GitHub). It is deliberately single-pack: every citation is to the DNS
pack, and `engagement.json` names no extra packs.

## The fiction

Wrenfield Advisory LLC is a nine-person advisory firm. Its domains,
`wrenfield.example` (the main domain) and `wrenfieldgroup.example`
(parked), were registered in 2019 at one registrar; DNS is hosted at a
separate DNS provider; mail runs on a mainstream hosted platform. Nobody
owns DNS as a job: the office manager set it up with a contractor in 2021
and it has drifted. During the audit a second registrar account turned
up, holding two legacy domains nobody had listed. The registrar, the DNS
provider and the mail, invoicing, marketing and helpdesk services are
named by role only. Everything here is invented; see `SCRUB.md`.

## Files

- `engagement.json` — name, subject label, created date (2026-11-20),
  method order `verify-first`, and `pack_file` (the DNS pack). No
  `extra_pack_files`.
- `inventory.json` — 25 entries in sections A–F (A registrar; B DNS
  provider; C delegation and nameservers; D email authentication; E mail
  transport and certificate issuance; F subdomains). Console reads and
  live DNS reads are VERIFIED with the engagement date; what the office
  manager or the contractor states is ON RECORD; what nobody has checked
  is UNKNOWN. `docs/dns-registrar-evidence.md` names the read behind each
  entry.
- `coverage.json` — one score per pack item (28), each citing the entries
  that ground it.
- `chains.json` — A, spoofed invoice (control `DNS-EM-04`); B, subdomain
  takeover through the dangling helpdesk CNAME (control `DNS-SUB-02`);
  C, registrar social engineering (control `DNS-REG-03`). All three
  controls are Gap.
- `fixes.json` — F-1 through F-10, all `proposed`, actor `operator`,
  dated 2026-11-20. F-1 is the DMARC enforcement path RFC 9989 §7.4
  sets out for a domain with general users: quarantine now, a month of
  aggregate reports, then reject only if the reports show no mailing-list
  or forwarding breakage.
- `verify_next.json` — five items, one per UNKNOWN entry (A4, C2, D3, E2,
  F4): the zone transfer test, DANE support, the second registrar
  account, the marketing platform, and the delegated subdomain.
- `EXPECTED-REPORT.md` — the report rendered from this fixture by
  `fencewalk report <db> --out ...`.

## Load it

```sh
fencewalk load-fixture dns-registrar dns.db
fencewalk report dns.db
fencewalk packet dns.db --date 2026-11-20 --out dns-packet.md
fencewalk pdf dns.db --out dns.pdf
```

## Acceptance numbers

Loading this fixture and rendering the report reproduces: 28 coverage rows
(Covered 3, Partial 5, Unknown 2, Not applicable 0, Gap 18), 3 chains,
10 fixes (all proposed), 5 verify-next items, 25 inventory entries
(VERIFIED 15, ON RECORD 5, UNKNOWN 5).
