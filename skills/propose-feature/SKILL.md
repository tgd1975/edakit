---
name: propose-feature
description: Propose a feature edakit lacks – something a project had to build itself or work around (a false finding, a crash, a part of the circuit the simulation leaves out, a routing, pour or silkscreen capability, a missing test) – as an issue in the edakit repository, sealed with its SHA-256, and bring the outcome back into the project. Use when the user asks to send gaps to edakit ("propose the gaps to edakit", "make an edakit feature issue of it", "what became of #14"). Only on the user's request.
argument-hint: "<the gap or the project decision that lists it – or an issue number to follow up>"
---

# Propose a feature to edakit

Wanted: $ARGUMENTS. The whole loop: `${CLAUDE_PLUGIN_ROOT}/handbook/11-working-with-claude.md` (11.6); seal, Action
and who may propose are the same as for rules (14.4).

A feature proposal is an issue in `tgd1975/edakit`. The Action proposals there triages it – accepted and built into
the one open pull request of feature proposals, rejected with the reason, or a question back – and works only on
proposals of the repository owner. A check, a hint, a block or a part fact is not a feature: that is
`/edakit:propose-rule`.

## 1. Write it

1. Start from the project's decision that names the gap. Without one, write it first (skill decision-round,
   section 3): what edakit should learn is the user's decision.
2. **Already there or proposed?** `edakit --help`, `${CLAUDE_PLUGIN_ROOT}/handbook/10-reference.md`,
   `gh issue list --repo tgd1975/edakit --label feature-proposal --state all --search "<words>"`. If so, tell the user
   instead of proposing it again.
3. **One capability per proposal.** "Pours" is too much; "several nets share one pour layer" is one. A gap with three
   causes is three proposals.
4. **Show the gap now:** run the command in the project and keep its output or numbers. A gap that cannot be shown
   with a command (a step done by hand) is described with what the project does instead.
5. `edakit proposal template --feature` into a file in the scratchpad, filled in, in English:
   - **title:** a few words, what edakit can do afterwards ("zero-ohm bridges join their nets")
   - **Capability:** what edakit should do – for any board with this pattern, not in this project's words
   - **Gap:** the command and what it says today, with designators, nets and numbers
   - **Reference:** how the project does it today – file, function, commit – and the method in words. The issue is
     public: quote the project's code only with the user's OK; names, parts and numbers are fine
   - **Interface:** keys in edakit.toml, fields in graph or parts entries, options – each with the default that leaves
     existing projects as they are; "none" if only the behaviour changes
   - **Test:** how a test shows it without EasyEDA (the Action has none): what is built into the example
     (`tests/fixtures/led-bar`), what edakit reports before and after; for a step in EasyEDA, the part that can be
     tested offline (the board file, the DSN, the plan, the Gerber files)
   - **Origin:** the project (`owner/repo` on GitHub, or its name and "private"), the decision and its file, the
     commit

## 2. Show, seal, send

The issue is public. Show the user every text and point out what comes from the project; send only with the user's
OK. Several gaps go out one by one – each is its own issue and its own triage.

```bash
edakit proposal seal draft.md --out body.md
gh issue create --repo tgd1975/edakit --title "Feature proposal: <title>" --body-file body.md
```

The decision gets the issue: `edakit: #14` with its link. Commit in the project as it does.

## 3. Follow up

`gh issue view 14 --repo tgd1975/edakit --comments` – every triage comment starts with its result:

| Result | In the project |
|---|---|
| **Question** | show the questions; answer with the user's words (`gh issue comment 14 --repo tgd1975/edakit --body …`), or change the proposal: edit the draft, seal it again, `gh issue edit 14 --repo tgd1975/edakit --body-file body.md`. Never edit the body by hand – the checksum fails then, on purpose |
| **Accepted** – built in #20 | a private project could not be run by the Action: run the gap command against the branch (`uvx --from git+https://github.com/tgd1975/edakit@features/proposals edakit …`) and put the result as a comment on #20 – that is the check before the user merges. After the merge and the plugin update: the gap command once more, the decision gets `edakit: #14 built`, the project's own workaround goes |
| **Rejected** | the decision gets `edakit: rejected (#14)` and the reason in one line; the workaround stays in the project |
