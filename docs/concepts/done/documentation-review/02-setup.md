# Documentation review: handbook/02-setup.md (step D.5)

**Status:** condensed on branch claude/amazing-newton-ygty8a, not committed; open for the owner's review. Every
statement kept; the chapter did not give a third fewer words without losing statements.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 195 | 215 |
| own words | 1552 | 1562 |
| mean sentence (words) | 19.9 | 19.0 |
| paragraphs over 120 words | 2 (220, 142) | 0 |
| sections over 80 lines without a subheading | 0 | 0 |
| bare references, words from inside, dates | 0 | 0 |

`tests/test_style.py`: `paragraphs:handbook/02-setup.md` now XPASS(strict) – the chapter meets the paragraph rule and
can leave `RED["paragraphs"]`. The other rules were met before and still are.

Why no third fewer: the whole chapter is read by the automation. `skills/start/SKILL.md` opens it by path for
"background and every API quirk"; `edakit/config.py:943`, `edakit/doctor.py:221,226` point at it; "handbook 2" is
named in `edakit/doctor.py:168` and `edakit/toolchain/kicad/cli.py:50`; 2.5 in `edakit/doctor.py:34,171,188`,
`edakit/export.py:14`, `edakit/release/fab.py:255,266`, `edakit/catalog/codes.toml:763`, `skills/start/SKILL.md:19`;
2.3 in `README.md:69`; and the other chapters name 2.2, 2.3, 2.4, 2.5, 2.6 and 2.7. The text was already dense – few
asides, no repetition inside a section, mean sentence under 20 words –, so what could go without a statement going
was a handful of words; the new first paragraph and the subjects added to cross-references took them back.

## Per section

- **H1 and its first paragraph** – new first paragraph: for whom, what works after the chapter. The tested-versions
  paragraph unchanged (tool versions are statements the setup relies on).
- **2.1 What talks to what** – diagram unchanged; three sentences on the extension API made two. No statement left.
- **2.2 Install** (named in 16, 18) – item 2 reordered into one sentence with the condition first; item 4 gives
  `edakit part fetch` its subject "(datasheets, 4.6)"; item 5 moves "Java 17 is too old" into the Java parenthesis;
  the KiCad paragraph splits the doctor clause into a sentence of its own, "(the KiCad setup, 16.2)". No statement left.
- **2.3 Claude Code: the plugin** (named in `README.md:69` with its anchor, 10.5, 14) – the VS Code paragraph split
  into three sentences; "This installs …" became two sentences, the session hook in a sentence of its own, every item
  kept. The bold paragraph title "**Versions.**" became `### Versions`, its three paragraphs kept, the pin paragraph
  made one sentence of two places. Anchor `#23-claude-code-the-plugin` unchanged.
- **2.4 The MCP server** (named in 8) – unchanged except "(AISLER; ordering, 8.4; SYNC.odb)" and a colon for the
  en dash before "only part numbers leave the machine".
- **2.5 The bridge extension, patched** (named by doctor, export, fab, codes.toml, the start skill, 12, 8,
  `upstream/README.md` E-4) – the long sentence on what the script does split in two; the re-import paragraph split
  into the re-import and the check, every statement, both doctor strings and the claim condition kept verbatim.
- **2.6 EasyEDA without background throttling** (named in 12, the start skill "the desktop launcher", doctor) – the
  inline `env -u ELECTRON_RUN_AS_NODE …` command became a code block. In the original the code span broke across a line
  inside the path (`/opt/apps/easyeda-pro/` ⏎ `easyeda-pro`), which renders as a space in the path – formatting, the
  command unchanged.
- **2.7 A project** (named in 3, 11.1, 14, 15) – the 220-word paragraph split into three: the interview's questions;
  how it writes (answers, OK, form or decision round); the graph and the pre-commit hook; the purpose sentence with
  M-6 and the not-legal-advice wording kept verbatim (CLAUDE.md, the same three phrases `tests/test_plugin.py` holds
  in the skill). "**Moving a project to edakit.**" became `### Moving a project to edakit`, its paragraph split in two;
  the last paragraph got `### The EasyEDA project` and "Then" became "After the skill". Subjects added: "(own parts,
  4.5)", "(the graph's format, 3.1)", "(editor state, 9.2)"; `style` moved before its three options.
- **2.8 Licences** – unchanged (`upstream/README.md:116` names it).

Nothing went to the history file (`history/02.md` says what was considered and kept).

## Findings

Not changed by this step:

1. **`BRIDGE_TIMEOUT_MS` must be equal in every server.** `edakit/easyeda/mcp-server.sh` says the server holding the
   bridge port drops pending requests after its own timeout, so every server needs the same value, and
   `edakit/doctor.py` warns when they differ. 2.4 gives only the value and the reason for 120 s. Adding the sentence
   would be a new statement – the owner's call.
2. **"External Interactions" against "External interaction".** 2.5 writes the permission as "External Interactions",
   `upstream/README.md` E-4 as "External interaction". One of them is not EasyEDA's label; check it in EasyEDA.
3. **"115 tools" in 2.1** cannot be checked from the repository (the server is not installed here); a count that drifts
   with the pinned version – worth a look at the next update of `EASYEDA_MCP_VERSION`.
4. **The throttling measurement is in two places**: 2.6 and the Throttling row of the editor state (9.2,
   `handbook/09-easyeda-api.md:38`) say the same 120-part, 120 s, 1–4 s. "Every statement once" would keep one and
   link from the other; both are read (the start skill opens 02, chapter 9 is the API reference), so both stay for
   now.

## Assumptions

1. The third fewer words is not reached; statements won, for the reason above.
2. Tool versions, "Since 1.5.1" and the "Tested with" line stay as statements, not history.
3. The 120-part DRC measurement in 2.6 stays: undated, names no project, and the launcher flags and the 120 s timeout
   rest on it.
4. Three `###` headings added (Versions; Moving a project to edakit; The EasyEDA project). They add anchors and remove
   none; no link names the bold paragraph titles they replace.
5. Cross-references already preceded by their subject were left as they are: "the working agreements (11.4)", "the
   project's own scripts and agents (8.6)", "the patched extension (2.5)", "(`style`, 6.5)", "(chapter 15)", "(chapter
   16)".
6. The new first paragraph says "the tool chain runs" rather than listing EasyEDA, server, bridge and plugin – the KiCad
   tool chain needs none of them.
7. "How to update: README, Install." became "the README, section Install" – the same pointer.
8. The 2.6 inline command turned into a code block, changing the reading (copyable) but not the command.
