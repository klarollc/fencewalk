# Model run output — Marigold Community Food Bank perimeter audit (sample)

Sample output for the slice-4 tests: fictional, written against the
Marigold reference case in the shape a model returns after running
the packet. One bounded pass, analysis only.

## 1. Coverage map

| Rubric ID | Entries | Status | Reasoning |
|---|---|---|---|
| R-1.2 | E1, E4 | Gap | The NAS's web admin login answers from the internet through a forwarded port, behind one password the three shift leads share. |
| R-2.6 | E7 | Not applicable | The food bank runs no certificate authority; laptops sign in with Microsoft 365 accounts. N/A reason: no certificate service of that kind exists in the inventory. |
| R-3.3 | C8 | Covered | A missing page, a malformed search and a broken form submission all returned the host's plain error page. |
| R-4.1 | F4, F5 | Unknown | The 180-day audit retention comes from the licence documentation; no one has run a search to see that records exist. |

## 2. Attack chains

### Chain A: the warehouse camera's cloud viewer

1. Reconnaissance: the camera's maker runs a public sign-in page for its cloud viewer.
2. Initial access: the viewer account, registered to the warehouse lead's personal email, is taken over through that email (whether the viewer asks for a second factor is UNKNOWN, entry E6).
3. Privilege escalation: none is needed; the viewer account sees every stream.
4. Collection: live and recorded views of the warehouse and the pantry window, including the households who come to it.

Earliest breaking control: a camera that records to the NAS only, with no cloud viewer. The inventory shows this control absent.

### Chain B: the NAS through the forwarded port

1. Reconnaissance: an internet scan finds the NAS login page on the warehouse's public address.
2. Initial access: the shared admin password is guessed or comes from a shift lead's phone (the firmware's age is UNKNOWN, entry E3).
3. Privilege escalation: the shared account is the NAS administrator.
4. Impact: the shares, the client-intake spreadsheet among them, are encrypted for ransom.

Earliest breaking control: the NAS login page closed to the internet. The inventory shows this control absent.

## 3. Fix list

| ID | Rubric | Action | Effort | Breaks |
|---|---|---|---|---|
| F-1 | R-1.2 | Remove the router's port forward to the NAS and confirm from outside that the login page no longer answers. | Minutes | B |
| F-2 | R-1.1 | Add the camera's cloud viewer to the perimeter list and move its account to a food-bank address. | Minutes | A |
| F-3 | R-4.1 | Run one audit search for this month's activity and record whether events come back. | Minutes | None |

## 4. Verify-next list

1. **Unknown:** whether the camera's cloud viewer asks for a second factor. **Why it changes the picture:** chain A stands or falls on it. **Cheapest check:** the viewer account's security page, read once and recorded.
2. **Unknown:** the NAS firmware version. **Why it changes the picture:** known flaws in old firmware make chain B's second step easier. **Cheapest check:** the NAS admin page's firmware screen.
3. **Unknown:** whether the audit log holds any events at all. **Why it changes the picture:** every investigation depends on records that may not exist. **Cheapest check:** one audit search for donations@ over the last 30 days.
