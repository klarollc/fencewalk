# Scrub audit note — dns-registrar fixture

Like `github-org`, this fixture has no source dataset: it is written as
fiction from the start, so there is nothing to substitute away. This note
records the classes of identifier the fiction uses and what was kept out.
The scrub is machine-checked: `tests/test_fixture_dns_registrar.py` greps
every file in this directory for GUID, e-mail, IPv4, IPv6, phone and
real-hostname-shaped strings and fails on any match outside the fictional
`.example` domains.

## Identifier classes used

1. **Firm and domains.** Wrenfield Advisory LLC at `wrenfield.example`,
   with `wrenfieldgroup.example` (parked) and the two legacy domains
   `wrenfield-advisory.example` and `wrenfieldllc.example`, all under the
   reserved `.example` top-level domain. Subdomains (`help.`, `projects.`,
   `dev.`) are under `wrenfield.example`.
2. **Vendors.** The registrar, the DNS provider, the mail platform, the
   invoicing tool, the marketing platform, the helpdesk service and the
   former web vendor are named by role only. No real provider is named as
   the firm's vendor, and no real nameserver, mail server or CNAME target
   hostname appears.
3. **People.** Roles only: the office manager, the managing partner, the
   contractor, a former partner, a departed staff member. No name and no
   e-mail address of any person is carried.
4. **DNS records.** Records are described in prose (policy values, tags,
   counts, key sizes). No record value that could identify a real service
   (an SPF include target, a DKIM public key, a DS digest, a TLSA hash)
   appears.
5. **Network identifiers.** No IP address, CIDR range, autonomous system
   number or phone number appears.
6. **Dates.** The engagement date, 2026-11-20, is the VERIFIED entries'
   checked date and the fixes' status date. Expiry dates (2027-03-18,
   2027-06-02) and year-level dates in entry bodies are part of the
   fiction.
7. **Sources.** RFC numbers, CISA BOD 18-01, NCSC and NIST SP 800-81 are
   the pack's public sources, not the firm's vendors, and appear by name.

## Kept out

- No fact, count, name or wording from any real engagement.
- No CIS Benchmark content: every rubric item the fixture scores comes
  from the DNS pack.
- No output of any real DNS query, registrar or DNS provider console:
  the inventory bodies state what such reads showed, in prose;
  `docs/dns-registrar-evidence.md` names the reads an operator would run.
