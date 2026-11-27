# Illustrative sample model output

This file is ILLUSTRATIVE. It is an example of the shape a model
run's output takes, written to demonstrate the walkthrough. It is
not a real model run, and nothing in it is evidence about
Marigold Community Food Bank, which is itself fictional. It
references real fixture rubric items (R-1.1, R-1.6, R-2.1, R-3.2)
and real fixture entries (A7, A8, C1, D1, D2, D5, E1, E6, H8) so
the walkthrough's apply commands are coherent.

# Coverage map

| Item | Status | Reasoning | Cited entries |
|---|---|---|---|
| R-1.1 | Partial | The website, the hosted checkout and the donor-management service are on the list, but the NAS login page and the camera's cloud viewer were found only by this audit. | C1, D1, E1, E6 |
| R-2.1 | Unknown | The three connected apps are named, but no one has read what each may do or who agreed to it. | A7, A8 |
| R-3.2 | Not applicable | There is no client portal: households are signed in on paper at the pantry window. | D5 |

# Attack chains

## Chain D: Donor list exported through a staff donor-management login

1. Reconnaissance: Staff names and work addresses are printed on appeal letters, and the donor-management service's sign-in page is public (D1).
2. Initial access: One of the six staff passwords is phished or reused from another site's breach. This depends on an UNKNOWN: whether the service asks for a second factor at all (D2, H8).
3. Privilege escalation: None needed if the account can run exports, which no record limits to the development director.
4. Collection-exfiltration: All 4,200 donor records, with home addresses and gift history, leave in one export. Whether any alert fires on a bulk export is UNKNOWN (D2).

Earliest breaking control: two-step sign-in on every donor-management account, with an alert on bulk exports. Status: unknown. Rubric: R-3.2.

# Fix list

- F-17: Turn on two-step sign-in for every donor-management account, and remove the accounts of staff who have left. Rubric: R-1.6. Effort: Minutes. Breaks: D.
- F-18: Limit full donor exports to the development director's account, and read the service's export history back to October 1. Rubric: R-3.2. Effort: An hour. Breaks: D.

# Verify-next list

1. Unknown: Whether the donor-management service's export history shows any full export since October 1. Why it changes the picture: It decides whether Chain D has already run or is still ahead. Cheapest check: The service's activity log, filtered to exports.
2. Unknown: Which of the six donor-management accounts belong to people who still work at the food bank. Why it changes the picture: Every account left behind is another way into Chain D at step two. Cheapest check: Compare the service's user list with the current staff list.
