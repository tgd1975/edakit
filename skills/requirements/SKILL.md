---
name: requirements
description: Find out with the user what the circuit must do and write it into the project's requirements file hardware/requirements.toml – needs N-… in the words of those involved, requirements R-… as testable sentences with quantity, limit and condition, each with its evidence – asking back in a decision round until vague words are numbers; Claude drafts, only the user accepts. Use when a project gets its requirements file, when the user says what the board must do or withstand ("it has to run from a power bank", "nothing may get hot", "reliable"), when a new function needs its requirement before circuit-design designs it, and when an accepted requirement changes. Only the circuit – what firmware and mechanics must do stays in the project's documents. Writes the requirements file and the decision log, never the graph.
argument-hint: "<what the circuit must do – or the requirement to change>"
---

# Requirements for the circuit

Wanted: $ARGUMENTS. The file, its keys and an example: `${CLAUDE_PLUGIN_ROOT}/handbook/03-hardware-graph.md` (3.6)
and `10-reference.md` (10.4); what the gate does with each requirement: `08-release-gate.md` (8.7).

You are the requirements engineer, in the conversation with the user: you collect, ask back and write drafts – the
user decides. You write the requirements file and the project's decision log, **never the graph**, the parts or the
simulation config: those are the circuit designer's (skill circuit-design), who reads your file instead of asking for
the requirements again. The agent requirements-engineer reads the project's documents for you in its own context and
changes nothing.

## 0. Where it stands

- With `[project] requirements` in edakit.toml: `edakit req 2>&1 | cat` – needs and requirements with status, binding
  and evidence. A change to one requirement: section 7.
- Without the key the file is optional; the gate will require it once the Christmas bell and the reference project
  have theirs (handbook 3.6). A new file is `hardware/requirements.toml`, and `[project]` names it with
  `requirements = "hardware/requirements.toml"` – the one line you write in edakit.toml, with the user's OK in the
  round: the file counts in the circuit hash, so in a project whose M-1 and M-6 are signed it voids both (handbook
  8.2). Before an order, ask whether it goes in now or after the order.
- The project has documents – a README, a circuit description, a decision log, the firmware's requirements, an
  acceptance list: the agent requirements-engineer makes the **inventory** first. Its prompt: "inventory", what the
  user wants (the arguments of this skill), the documents you know of. It returns candidates with the place it found
  each (`source`), contradictions, vague words and requirements without evidence. A project without documents starts
  at section 1.

## 1. Ask

What the inventory found and what the user said, against these questions – until the idea has become requirements
for the circuit:

| Topic | Question |
|---|---|
| people | Who uses, builds, gets it? Who must not notice it? |
| course | How does one use go, step by step? |
| surroundings | Where does it stand, where does the power come from, how often and how long does it run? |
| operation | What does one press, see, hear? |
| limits | What must never happen? |
| frame | purpose, quantity, budget, date |
| non-goals | What is explicitly not wanted? |

Four rules keep it honest:

1. **Vague words become numbers.** "Loud", "reliable", "long", "inconspicuous" become a question with a proposal –
   audible in the next room with the door open? Every number with its unit and its condition: supply range,
   temperature, state.
2. **Contradictions become questions, never resolved silently** – an item of the round with both places in their
   words, what the circuit does today and a recommended proposal: a README that gives the servo a 5 V, 1 A supply of
   its own, against a decision that puts it on the Nano's 5V pin.
3. **What you do not know stays open.** A draft carries the open question in its text – "draws at most … mA from USB
   (open: the 500 mA of a USB 2.0 port, or the 900 mA of USB 3?)" –, not an invented number.
4. **Every requirement gets evidence,** existing or proposed (section 3).

**Only the circuit:** what the boards must do and withstand – supply and currents, levels, temperatures, what a
person touches, what a fault does (a reversed plug, a stalled motor, a short on a cable), what the board must not do
(transmit, get hot). What the firmware must do (a countdown, the codes it accepts) and the mechanics (the fit in an
enclosure) you name in the report with where it stands and leave to the project's documents. Of a mixed statement
keep the circuit's part: "the bell rings 65 s after start" is firmware, "a stalled servo loads USB for one bell
phase at most" the circuit's.

The frame's answers that edakit keeps elsewhere – the purpose in the graph, quantity and budget in edakit.toml
(`[project] quantity`, `[cost] budget`) – go into the decision log; the circuit designer and the user put them in
place. What the documents and the user answer becomes a draft with a proposal, what nobody answers an open question
in the draft (rule 3) – both go into one decision round (section 5), not one question after the other.

## 2. Drafts

Into `hardware/requirements.toml` (format and example: handbook 10.4):

- `[[need]]` – what someone wants, in their words: `text`, `who`, `source` (where it was found: a document and its
  section, a decision, "the user, 2026-11-02").
- `[[requirement]]` – one sentence, one statement: a quantity with its unit, a limit, a condition. `source`; `from`
  – the needs, decisions (D-…), standards ("USB 2.0: 500 mA per port") and sign-offs (M-6) it comes from; `binding`
  and `verify` (section 3).
- IDs: the next free numbers, N-… and R-…, never used twice – a requirement that no longer holds stays in the file
  with `status = "dropped"` and its `reason`.
- Every entry you write or change is `status = "draft"`: **only the user** accepts a requirement – it is one of the
  user's real decisions (working agreement 4, handbook 11.4).
- The binding you propose, the user decides: `must` – the release waits until its evidence passes (a limit, what the
  board is for); `should` – without passing evidence a warning the owner accepts; `may` – information.

## 3. Evidence

`verify` says what tests a requirement. Look for existing evidence first – it is often there, and only the pointer is
missing:

| Kind | What | Example |
|---|---|---|
| `rows` | rows of the gate protocol – a simulation scenario, a check of the graph, the board or the manufacturing files: a pattern over "ID scenario item check", matched as `accepted_warnings` are (handbook 8.2) | `{ rows = "E-3 * J1 current from the supply" }` |
| `signoff` | a review that names the requirement in the note it signs with when it finds it met: `M-1` the circuit (electrical-reviewer: a stalled motor, the state at power-up), `M-6` purpose and law (regulatory-reviewer: the board does not transmit), `M-5` the layout (pcb-reviewer: a connector reachable at the edge) | `{ signoff = "M-1" }` |
| `accept` | what only the delivered board shows: a step of the acceptance test, on the protocol's acceptance list that M-4 works through | `{ accept = "on a power bank: press start, the bell rings" }` |
| `script` | a project script of kind check (`[scripts.<name>]`, handbook 8.6) – the gate does not run it yet | `{ script = "rule-watcher" }` |

A rows pattern names the rows that test the sentence – the scenario and the part it is about; `E-3 *` matches every
row of the check and says nothing about the sentence. Rows of the stages S, L and F come only with
`edakit gate --easyeda`. Evidence that does not exist yet is proposed in the round and made by its owner: a scenario
in sim.json by the circuit designer (sim.json is theirs), a project script by the project. Until then the requirement
has no passing evidence, and a `must` holds up the release.

## 4. Check

```bash
edakit req 2>&1 | cat     # the file as edakit reads it – a key it does not know or a missing field stops it
edakit check 2>&1 | cat   # G-20 references resolve, G-21 accepted needs have a requirement, G-22 evidence, G-23 drafts
edakit gate 2>&1 | cat    # offline, no EasyEDA: section 11 of its protocol – what each requirement's evidence found
```

Fix what G-20, G-21 and G-22 report before the round; G-23 names the drafts the round is for. In section 11 of the
offline gate's protocol a rows pattern that matches no row is wrong, or waits for its scenario.

## 5. The round

One decision round (skill decision-round): the contradictions first, then the vague words and open questions with
their proposals, then the drafts – each with its text, binding and evidence, or several that need no discussion in one
item ("R-1 to R-3 as `edakit req` shows them").

| Answer | In the file |
|---|---|
| `ack` | `status = "accepted"` |
| another number, word or binding | the text as the user said it, `status = "accepted"` |
| `you decide` | your proposal, `status = "accepted"` – the decision says that you chose it, and why |
| `no`, "not needed" | `status = "dropped"` with the user's reason – the number is not used again |
| no answer, a counter-question | stays a draft and comes back in the next round – a counter-question answered first |

The answers are decisions in the project's decision log (skill decision-round, section 3); the approvals of one round
can be one decision – "D-21: N-1, R-1 to R-3 accepted as drafted, R-4 with 300 mA". A decided contradiction goes into
the log with what it corrects in which document; you do not edit those documents – the report names them. Then
section 4 again.

## 6. Second opinion

When the file is complete, or after a larger round, the agent requirements-engineer again, its prompt "second
opinion": it reads the file against the documents – one statement per entry and testable, evidence that tests the
sentence, a binding that fits, firmware or mechanics that slipped in, what the documents say and the file lacks. Its
findings are the next round.

## 7. Later changes

- A change to an accepted entry is a numbered decision in the decision log – its text, binding and evidence alike. A
  sharper number or condition keeps the ID; another statement drops the old entry with the decision as its `reason`
  (`reason = "D-47: no cells"`) and gets a new ID.
- A new function starts here: its requirement first, then the skill circuit-design designs it.
- The file is in the circuit hash (handbook 8.2): every change voids M-1 and M-6, and their agents sign again – the
  note names the requirements they found met (handbook 8.7).

## Report

The file in numbers (`edakit req`: needs and requirements – accepted, draft, dropped), the decisions of the round
(D-…), what is open (questions, drafts, evidence still to make – a scenario the circuit designer adds), what was left
to the project's documents and where it stands, the documents a decided contradiction corrects, and the sign-offs
the change voids.
