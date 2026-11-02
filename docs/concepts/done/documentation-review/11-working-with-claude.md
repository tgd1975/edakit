# Documentation review: handbook/11-working-with-claude.md (step D.5)

**Status:** condensed on branch claude/amazing-newton-ygty8a, not committed; open for the owner's review. Section 11.4
is unchanged to the character, as are all headings and the name cells of table 11.1. Every statement kept; the
chapter gave about a tenth fewer words, not a third (why below).

## Measures

| | before | after |
| --- | --- | --- |
| lines | 247 | 240 |
| own words (outside 11.4, the table and code) | 1335 | 1200 |
| mean sentence (words) | 24.7 | 23.1 |
| paragraphs over 120 words | 0 | 0 |
| sections over 80 lines without a subheading | 1 (11.4, 114 lines) | 1 (11.4, 114 lines) |
| "the user" / "the reference project" in own sentences | 14 | 0 |
| bare references, dates | 0 | 0 |

`tests/test_style.py`: `words:handbook/11-working-with-claude.md` now XPASS(strict) – the chapter meets the rule and
can leave `RED["words"]`. `sections:handbook/11-working-with-claude.md` stays red: the only long section is 11.4
itself, and a `###` there would change the section the hook parses.

Why no third fewer: about half of the chapter's text is section 11.4 and table 11.1, which stay. Of the rest, 11.2,
11.4 and 11.6 are named by the automation and 11.3 by chapters 8 and 12; what remains there is lists of statements –
the library lookups and their tool names, the yield rules, the commands that print step lines, the template's sections,
the triage checks, the build steps. What could go was the history, the examples and a few asides; the new first
paragraph took back about 40 words.

## Places that name the chapter

- `skills/start/SKILL.md:39` – handbook 11.2 (library lookups pass without a claim).
- `skills/requirements/SKILL.md:113`, `edakit/config.py:259`, `edakit/scripts.py:1475`, `edakit/agreements.py:1` –
  handbook 11.4 (unchanged).
- `edakit/proposal.py:8`, `.claude/skills/triage-feature/SKILL.md:9` – handbook 11.6.
- `skills/propose-feature/SKILL.md:9` opens the file for "the whole loop" (11.6); `skills/decision-round/SKILL.md:9`
  opens it for why the format works (agreement 5 in 11.4, unchanged).
- Tests: `tests/test_plugin.py` (the table of 11.1), `tests/test_agreements.py` (11.4), `tests/test_style.py`.
- Other chapters: 11.2 from 8 and 10 and 17, 11.3 from 8, 10 and 12 (step lines, `pgrep -f`), 11.4 from 2, 3, 8 and
  10, 11.6 from 14 and the README; the glossary links 11.1, 11.2, 11.4, 11.6. All anchors stay.

## Per section

- **H1** – new first paragraph (for whom, what after). "Both came out of a week of daily use" went to the history; the
  statement that the agreements weigh as much as the scripts stays.
- **11.1** – table: the name cells and rows unchanged; in five Use cells "the user" became "you" (new-project,
  requirements, own-part) and "the owner's browser" became "your browser" (cart). The paragraph on project rules made
  shorter. The paragraph on project agents: the example "the reference project's elektrotechniker for M-1, pcb-pruefer
  for M-5 and its round reviews" went to the history (8.6 has the same example in full); "as for each script of the
  project" dropped, since 11.4 owns the line per script; cross-references now name their subject ("project scripts
  and agents, 8.6", "the session start, 11.4").
- **11.2** (named by `skills/start`) – no statement left: one EasyEDA per machine, tab switching, the claim with its
  15 minutes, the library lookups with both tool paths, `READ_ONLY_TOOLS`/`READ_ONLY_API` and the evidence rule, the
  refusal, the yield rules, release while waiting for a click, the state file. Moved to the history: the four
  anecdotes (20-minute run lost, 38-minute wait, 93-minute wait, 49-minute hold) and "The reference project used …".
  The example list of sessions ("one routes, one writes docs, one researches a part") was cut. The git paragraph now
  describes the coordination tool as a recommendation without the reference project.
- **11.3** – wording only: the command list folded into the sentence with the example line, two short sentences
  merged. Every command and the snap/`uv` note stay.
- **11.4** – untouched.
- **11.5** – "so a new project does not meet them again the hard way" became "so a new project starts with them" (the
  original sentence in the history); "Each quirk in chapter 9" became "Each EasyEDA quirk (chapter 9)".
- **11.6** (named by `edakit/proposal.py`, `triage-feature`, opened by `propose-feature`) – every statement of the five
  steps stays, with the template's sections, the triage's checks and results, the build order, `features/proposals`,
  `edakit: #14 built`. Reworded: step 2's last sentence ("The issue is public: you see it before it goes out, a
  private project's code is quoted only with your OK, and it is sealed like a rule proposal"); step 5 "before the user
  merges" became "before the merge" (see Assumptions); the second "(14.4)" in step 3 dropped, the intro links 14.4
  by name. "Why it exists: the project edakit came from went on growing …" went to the history.

## To the history file

`/tmp/claude-0/-home-user-edakit/82157d39-3f55-5034-b81b-e1cbfc4ad998/scratchpad/history/11.md`: the opening's "week
of daily use", the 11.1 example of the reference project's agents, the 11.2 anecdotes and the reference project's
git tool, the 11.5 "hard way" sentence, the 11.6 "Why it exists" paragraph. It also notes that the stories inside
11.4 (items 5, 15–25) are history by the style guide but stay, as 11.4 is the hook's.

## Findings

- **Lock state path** (11.2): the chapter names `~/.local/state/edakit/easyeda-lock.json`; `edakit/lock.py` uses
  `$XDG_STATE_HOME/edakit/easyeda-lock.json` with `~/.local/state` as the default, and `EDAKIT_LOCK_FILE` overrides
  it. The chapter gives the default only. Not changed.
- **11.5, "Facts that are in the repository … belong in the repository"**: reads as a tautology; probably meant "facts
  about the project" (decisions, checks, API behaviour belong in the repository, not in memory). Kept as written.
- **Section 11.4 against the style guide**: it holds "the user" and "the reference project" in its own sentences,
  dated stories in items 5 and 15–25, and is 114 lines without a subheading – `RED["sections"]` for this chapter can
  only go once 11.4 changes. `tests/test_style.py` exempts 11.4 from the word rules (`QUOTED`) but not from the
  section-length rule. Either the agreements get shorter items (the owner's decision, as they are the agreements), or
  `long_sections` exempts 11.4 too. Not changed.
- **Table 11.1 cells**: the long Use cells (new-project, requirements, cart, requirements-engineer, project-surveyor)
  are paragraphs, and the cells use bare forms like "(2.7)", "(chapter 14.4)", "(chapter 4.2)" – the latter
  inconsistent with "section 14.4". Left, since `tests/test_plugin.py` reads the table and the brief asked to keep
  the cells.

## Assumptions

1. Table 11.1: only "the user"/"the owner" replaced in the Use cells; no cell shortened or split, as the test reads the
   table and the brief said to keep the cells.
2. 11.1: the example agents of the reference project dropped instead of rephrased as "a real project's …" – 8.6 shows
   the same agents in full; one example in this chapter (the 11.4 code block) stays.
3. 11.1: "as for each script of the project" dropped as a statement owned by 11.4.
4. 11.2: "in the reference project a 20-minute routing run was lost that way" generalised to "a run in progress is
   lost" – the statement (a run is lost) kept, the story moved.
5. 11.2: the four anecdotes in parentheses treated as history, though 11.2 is named by `skills/start`; they carry no
   rule, only the reason for one.
6. 11.2: the git paragraph keeps the description of a coordination tool (commit lock, active branch, log book,
   PreToolUse hook) as advice, without saying a real project used one.
7. 11.2: "release EasyEDA while waiting" – the reason (a session held it 49 minutes for a click) moved to history.
8. 11.6: "edakit's repository owner" kept for the role in the proposals pipeline; "the owner" in the sense of the
   reader left the chapter.
9. 11.6 step 5: "before the user merges" became "before the merge" – the original is ambiguous about who merges;
   by CLAUDE.md the owner merges the pull request. Passive keeps it true either way.
10. 11.6: the "Why it exists" paragraph (the private project's 0 Ω bridges, star LED, pour-only nets) treated as the
    story of the private project and moved; the reason for the loop stays in the intro ("edakit and the project drift
    apart").
11. 11.5: "the hard way" replaced by "starts with them", which keeps the consequence (a new project has the agreements
    from the start).
12. The first paragraph names three things the reader can do after the chapter, not every section; the feature loop
    is left to its heading.
