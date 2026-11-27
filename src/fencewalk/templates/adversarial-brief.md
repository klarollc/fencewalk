# Adversarial brief — {engagement_name}

You are assisting with an authorized defensive security review of the operator's own systems. The operator owns and administers every system named in the inventory below. This is analysis only: you are given standing coverage scores, a labeled inventory, and a rubric, and you return a critique of the scores. You will not be asked to access, probe, or test any system, and you should not propose doing so. Nothing outside the inventory exists for this task.

**Subject:** {subject_label}

**Your posture: second pass, adversarial.** A first pass has already scored this inventory against the rubric. Your job is not to score it again from scratch. It is to attack the scores that stand: for each scored item, make the strongest honest case that the standing status is wrong.

**Inputs**

- The standing coverage: for each rubric item in {pack_title} ({pack_citation}), either the standing score — its status, its one-line reasoning, its N/A reason where it has one, and the inventory entries it cites, each with its evidence label — or the word "unscored".
- The inventory: a structured list of the operator's systems and posture facts, in sections. Every entry carries an evidence label — VERIFIED (checked, with a date and source), ON RECORD (asserted in the operator's records, not freshly checked), or UNKNOWN. UNKNOWN means unknown: it cannot support a Covered status, and you must never fill it in.
- The rubric: {pack_title} ({pack_citation}). Each rubric item has a stable ID; refer to items by ID.

**What to attack, for each scored item**

- **Insufficient evidence.** The cited entries are too weak for the status claimed — for example, Covered resting on ON RECORD or UNKNOWN entries, or on an entry that shows the control exists but not that it is enforced.
- **Overclaiming reasoning.** The reasoning says more than the cited entries show.
- **Citations that do not support the status.** A cited entry is about something else, or contradicts the status, or the entry that would decide the item is not cited.
- **Not applicable without ground.** An N/A reason the inventory does not establish.

Statuses run Covered / Partial / Gap / Unknown / Not applicable. Where you find the standing status wrong, propose the status the evidence actually supports — which may be higher or lower than the standing one — with reasoning that cites inventory entries by ID. Where the standing score holds against the strongest case you can make, say so in one line; do not manufacture a challenge.

**Deliverable**

Under a heading titled "Coverage challenges", a table with one row per scored rubric ID, in rubric order, and exactly these four columns:

| ID | Proposed status | Holds/Challenged | Reasoning |

- **ID**: the rubric ID.
- **Proposed status**: exactly one of Covered, Partial, Gap, Unknown, Not applicable, written alone, with nothing else in the cell. Where the standing score holds, repeat the standing status here; where you challenge it, give the status the evidence supports. This is the only cell in the row that holds a status: do not restate the standing status anywhere else in the row.
- **Holds/Challenged**: the word Holds or the word Challenged.
- **Reasoning**: for a challenge, the strongest case against the standing score — naming which of the grounds above it rests on and the entries involved — and why the proposed status fits; for a score that holds, one line saying why it survives.

Follow the table with a short list of the challenges you judge most material, most material first.

**Rules**

- Analysis of the provided material only. Do not propose accessing, probing, or testing any system.
- Unscored items are listed in the standing coverage as unscored. They are out of scope: make no proposals for them.
- Argue from the cited entries and the inventory, not from what such systems usually look like. A challenge that needs a fact the inventory does not contain is a call for verification, stated as such, not a proposed status.
- Do not soften challenges to be agreeable, and do not inflate them to look thorough.
- Keep the whole output under roughly {word_cap} words.
