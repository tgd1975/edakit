---
name: decision-round
description: Present a review or open questions as numbered findings, read the user's short answers ("ad 1 ack, ad 2 …") and turn them into numbered decisions in the project's decision log, then implement them. Use for "review", "what is open", before larger changes with several judgement calls, and whenever the user answers with "ad 1 … ad 2 …".
argument-hint: "<topic, e.g. schematic, layout, enclosure>"
---

# Decision round

Topic: $ARGUMENTS. Why this format works: `${CLAUDE_PLUGIN_ROOT}/handbook/11-working-with-claude.md`.

## 1. Present

- Look closely before asking. For hardware an independent second opinion comes from the agent electrical-reviewer
  (circuit) or pcb-reviewer (layout).
- A **numbered list**, per item: the **finding** in one sentence (what, where, with designator: R41, GP22, D-25),
  the **consequence** if nothing is done, the **proposal** with the recommendation first; for real alternatives a/b
  with half a sentence of trade-off each. Check that a proposal fits (datasheet dimensions, board geometry) before
  presenting it.
- Sorted by weight. Real risks only: how likely, what it costs ("rare, then 5 min with a soldering iron"). A deviation
  from a datasheet recommendation without a realistic consequence is no finding; things nobody can influence get one
  line at most.
- What Claude can decide itself (no effect on cost, looks or operation) is not asked but listed at the end as
  "decided: …". No more than about 10 items – rather two rounds.
- **Check candidates** of a review (findings a rule could find again) are one item: "make it a check in edakit?" –
  with what the check would test. Whether something becomes edakit knowledge is the user's decision; nothing is
  filed anywhere by itself – a proposal to edakit goes out only when the user asks for it (skill propose-rule).

## 2. Read the answers

| Answer | Meaning |
|---|---|
| `ack`, `yes`, `ok`, `do it` | implement the proposal |
| `don't care`, `you decide` | Claude decides, gives a short reason, documents it |
| `no idea what this is about` | explain the item again without jargon, do not implement |
| counter-question ("didn't we want …?") | answer first, then propose again; do not implement silently |
| `… is a must` | hard requirement: keep searching instead of switching |
| no comment on an item | leave it open and say so in the report |

## 3. Document

Every decision gets a **number** in the project's decision log (D-… design, E-… part choice, or the project's scheme):
decision, reason (in the user's words where possible), date, alternatives. Cite the number in the graph or the code
where it applies. Update the list of open items.

An accepted candidate is a decision like any other, written so that it can be built later without this
conversation: what the check would test, the finding that showed it (designator, numbers), the evidence or source,
and `edakit: open`. When the user asks, the skill propose-rule sends it to the edakit repository as an issue
(`edakit: #12`); its triage builds it, rejects it or asks back, and the decision then gets the check's ID
(`edakit: REQ.function`) or `edakit: rejected (#12)`.

## 4. Implement and report

Implement through the matching skill (hardware-change, pcb-round, release). Report one line per number:
implemented (D-…) / decided by Claude: … / open, because …
