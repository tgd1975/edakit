---
name: propose-rule
description: Propose a check, a design hint, a building block, a part fact or the retirement of a check to edakit – as an issue in the edakit repository, sealed with its SHA-256, usually from a project decision with `edakit: open` – and bring the outcome back into that decision. Use when the user asks to send something to edakit ("propose D-17 to edakit", "make an edakit issue of it", "what became of #12"). Only on the user's request.
argument-hint: "<decision, e.g. D-17 – or an issue number to follow up>"
---

# Propose a rule to edakit

Wanted: $ARGUMENTS. The whole loop: `${CLAUDE_PLUGIN_ROOT}/handbook/14-design.md` (14.4).

A proposal is an issue in `tgd1975/edakit`. The Action rule-proposals there triages it – accepted and built into the
one open pull request of rule proposals, rejected with the reason, or a question back – and works only on proposals
of the repository owner. The checksum shows that the text is the one sealed here.

## 1. Write it

1. Start from the decision in the project's log (`edakit: open`). Without one, write it first (skill decision-round,
   section 3): what becomes edakit knowledge is the user's decision.
2. Already there or proposed? `edakit rules`, `edakit block list`,
   `gh issue list --repo tgd1975/edakit --label rule-proposal --state all --search "<words>"`. If so, tell the user
   instead of proposing it again.
3. `edakit proposal template` into a file in the scratchpad, filled in, in English:
   - **title:** a few words, like the title of a check ("hole fits the lead")
   - **Kind:** `check` (a program decides it), `hint` (needs judgement), `block`, `part` (a fact from one part's
     datasheet), `retire`
   - **Rule, Why, Fix:** as they would stand in the rule catalog
   - **Finding:** designator or net, the numbers, the state (circuit hash or commit)
   - **Sources:** every source opened and read in this session – document number, revision, section. A rule from
     memory is said to be one; the triage asks for the source then.
   - **Origin:** the project (`owner/repo` on GitHub, or its name), the decision and its file, the commit

## 2. Show, seal, send

The issue is public. Show the user the whole text and point out what comes from the project (names, parts, numbers);
send it only with the user's OK.

```bash
edakit proposal seal draft.md --out body.md
gh issue create --repo tgd1975/edakit --title "Rule proposal: <title>" --body-file body.md
```

The decision gets the issue: `edakit: #12` with its link. Commit in the project as it does.

## 3. Follow up

`gh issue view 12 --repo tgd1975/edakit --comments` – every triage comment starts with its result:

| Result | In the project |
|---|---|
| **Question** | show the questions; answer with the user's words (`gh issue comment 12 --repo tgd1975/edakit --body …`), or change the proposal: edit the draft, seal it again, `gh issue edit 12 --repo tgd1975/edakit --body-file body.md`. Never edit the body by hand – the checksum fails then, on purpose |
| **Accepted** – G-15 in #20 | after the pull request is merged and the plugin is updated: the decision gets `edakit: G-15`, then `edakit check` in the project |
| **Rejected** | the decision gets `edakit: rejected (#12)` and the reason in one line |
