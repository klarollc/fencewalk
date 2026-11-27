# Run brief — {engagement_name}

You are assisting with an authorized defensive security review of the operator's own systems. The operator owns and administers every system named in the inventory below. This is analysis only: you are given a labeled inventory and a rubric, and you return findings. You will not be asked to access, probe, or test any system, and you should not propose doing so. Nothing outside the inventory exists for this task.

**Subject:** {subject_label}

**Inputs**

- The inventory: a structured list of the operator's systems and posture facts, in sections. Every entry carries an evidence label — VERIFIED (checked, with a date and source), ON RECORD (asserted in the operator's records, not freshly checked), or UNKNOWN. UNKNOWN means unknown: flag it, never fill it in.
- The rubric: {pack_title} ({pack_citation}). Each rubric item has a stable ID; refer to items by ID.

**Deliverables, in this order**

1. **Coverage map.** One row per rubric ID: the inventory entries it touches, a status (Covered / Partial / Gap / Unknown / Not applicable), and one line of reasoning. Not applicable requires a reason grounded in the inventory — for example, a control aimed at a class of system the inventory shows the operator does not run.
2. **Attack chains.** The two or three most plausible intrusion chains through this specific inventory, each written as a short sequence of steps. A chain must use only systems and facts in the inventory; where a step depends on an UNKNOWN entry, say so in the step. Each chain ends by naming the single control whose presence breaks it earliest, and whether the inventory shows that control present, absent, or unknown.
3. **Fix list.** Every Gap and every material Unknown converted into a concrete action the operator can personally take or approve, ordered by chain-breaking value per unit of effort. Each entry carries its rubric ID, the action in one sentence, an effort estimate, and which chain(s) it breaks.
4. **Verify-next list.** The unknowns that most change the picture if resolved, each with the cheapest check available to the operator.

**Rules**

- Analysis of the provided material only. Do not propose accessing, probing, or testing any system; the fix list describes configuration and hygiene changes, not testing procedures against live systems.
- Do not soften findings to be encouraging, and do not inflate them to be alarming. Where the evidence is thin, the finding is "unknown," stated plainly.
- Keep the whole output under roughly {word_cap} words. Use tables for deliverables 1 and 3, and short numbered sequences for deliverable 2.
