# 11 Working with Claude Code

The toolkit is half code, half agreements about how Claude works. Both came out of a week of daily use; the
agreements are as important as the scripts.

## 11.1 What the plugin brings

| Component | Name | Use |
|---|---|---|
| skill | `/edakit:start` | EasyEDA ready, long runs, GUI clicks, crash recovery – before any EasyEDA work |
| skill | `/edakit:new-project` | set up edakit in a repository |
| skill | `/edakit:circuit-design` | from requirements to a graph: blocks, parts, computed values, checks, hints, simulation (chapter 14) |
| skill | `/edakit:hardware-change` | a change from graph to PCB and docs |
| skill | `/edakit:part-search` | find a part at the project's distributors, create and sign its parts entry |
| skill | `/edakit:own-part` | the parts entry of a part nobody sells and no edakit project describes – own board, from the bin, made by hand – from the user's documents and measurement (4.5) |
| skill | `/edakit:pcb-round` | one layout round |
| skill | `/edakit:release` | the gate, sign-offs, order checklist |
| skill | `/edakit:decision-round` | numbered findings, short answers, numbered decisions |
| skill | `/edakit:propose-rule` | a check, hint, block or part fact as a sealed issue to the edakit repository, and its outcome back into the decision (chapter 14.4) |
| skill | `/edakit:propose-feature` | a feature edakit lacks and a project had to build or work around, as a sealed issue to the edakit repository, and its outcome back into the project (11.6) |
| agent | `edakit:part-selector` | finds a part at the project's distributors (a profile each) and writes its parts entry, in its own context (chapter 4.2) |
| agent | `edakit:easyeda-operator` | runs one long EasyEDA step and returns only the result – keeps the main conversation clean |
| agent | `edakit:electrical-reviewer` | independent circuit review; its result is the sign-off M-1 |
| agent | `edakit:regulatory-reviewer` | circuit and parts against EU law for the board's purpose; its result is the sign-off M-6 (chapter 15) |
| agent | `edakit:pcb-reviewer` | independent layout review (read-only EasyEDA tools); its result is the sign-off M-5 |
| MCP | `easyeda` | easyeda-mcp-pro, pinned, safe defaults |
| hook | PreToolUse on the easyeda tools | claims EasyEDA for the session, refuses when another session holds it |
| hook | SessionStart | in an edakit project: the working agreements of 11.4, one line each, into the session's context |
| bin | `edakit` | the command line on the Bash PATH |

Skills trigger on their description; you can also call them by name. Put project-specific rules (what the user wants
from the layout, which parts must stay hand-soldered, decision numbering) into the project's own CLAUDE.md or skills –
the plugin's skills stay generic.

## 11.2 Parallel sessions share one EasyEDA

Several Claude sessions working at the same time is normal (one routes, one writes docs, one researches a part). But
there is one EasyEDA per machine, and every script and most MCP tools switch its active tab. A second session's run
pulls the tab away: in the reference project a 20-minute routing run was lost that way, and writes can land in the
wrong document.

So EasyEDA is **claimed per session** (`edakit lock`), independent of anything git does:

- The first EasyEDA access claims automatically (the hook for MCP tools, every edakit command for scripts); every
  access renews it; it expires after 15 minutes without access. Tools that only ask about the connection are free.
- **Library lookups pass the claim:** the device search (`easyeda_schematic_search_device`) and the device reads
  through `easyeda_api_call` (paths beginning `LIB_Device.search` or `LIB_Device.get`) leave the open document and tab
  as they are, so they neither take nor renew a claim – a part search runs while another session routes, and it does
  not block EasyEDA for 15 minutes afterwards. The list is data in `edakit/lock.py` (`READ_ONLY_TOOLS`,
  `READ_ONLY_API`); an entry joins only with the evidence that the call leaves the active document as it was. (A part
  lookup once waited 38 minutes behind a layout session.)
- Another session is refused with who holds EasyEDA and since when. It waits, or asks the holder (ListAgents →
  SendMessage).
- **Letting a short run in:** a run under 5 minutes on another document need not wait behind a long one. The holder,
  between two of its own runs and with nothing unsaved it might discard, runs `edakit lock yield <session>`. When the
  guest releases – or its claim expires – EasyEDA goes **back to the holder**, not free, so a third session cannot
  snatch the gap. (A 7-minute change once waited 93 minutes before this existed.)
- **Waiting for the user's click holds nothing:** release EasyEDA while waiting (a session once held it for 49 minutes
  for a click the user did not know about, running a DRC every minute).

The state lives in `~/.local/state/edakit/easyeda-lock.json` – machine-wide, because EasyEDA is machine-wide.

The same thinking applies to git when several sessions share one working tree: one branch switch moves everyone, a
`git add -A` takes other sessions' files. The reference project used a small coordination tool with a commit lock, an
active branch and a log book, enforced by a PreToolUse hook on git commands. That tool is not part of edakit (it is not
EDA-specific), but if you run parallel sessions in one repository, build or adopt something like it.

## 11.3 Long runs

- Say up front how long it will take and which step is the longest; show progress (step n/m, minutes).
- Start long runs in the background; wait for the notification or watch the log. **Never wait with `pgrep -f`** on a
  pattern in the same command line – it finds its own shell and never ends. Write an end line and the PID, wait for
  either.
- Do not filter the output of a long run down to a few lines – a silent abort is then invisible.
- `uv` installed as a snap cannot write to files Claude Code hands it as stdout: `… 2>&1 | cat`.

## 11.4 Working agreements that proved themselves

Every session in an edakit project starts with this list: the plugin's SessionStart hook (`edakit/agreements.py`)
finds the project's edakit.toml and adds one line per agreement – its number and bold title, read from this
section – with the path of this chapter. A new agreement needs nothing but its numbered item with a bold title here.
`[project] agreements = false` in edakit.toml turns it off; outside an edakit project the hook adds nothing.

1. **Everything in EasyEDA is generated, so it may be deleted.** Claude deletes tracks, pours, parts, schematics and
   regenerates them without asking for permission or proposing a backup.
2. **Fix the tooling instead of asking for clicks.** When automation keeps failing, find the cause (the EasyEDA editor
   bundle, the MCP server source), adapt the scripts, the server configuration, EasyEDA's start options; restarting
   EasyEDA is fine (save first, announce it to other sessions).
3. **A dialog the user must handle is a plain OK.** Prepare everything so that OK is right; never ask them to read,
   copy or judge a dialog's content. Ask when they are there, and only then say "click now".
4. **An agent's check is the sign-off.** If an independent agent checked it, it is either OK (signed, `done_by` = the
   agent) or not OK (fixed and checked again). No checklists for the user to re-check what an agent can check. Only
   real decisions go to the user: accepting a warning, looks and operation, money.
5. **Open questions go to the user in decision rounds.** Numbered findings with consequence and a recommended
   proposal; the user answers "ad 1 ack, ad 2 b, ad 3 you decide"; every answer becomes a numbered decision with
   reason and date (decision-round skill).
6. **Realistic risks: how likely, what it costs.** Per risk, and the review agents per finding too. Delivery delays
   and stock problems are force majeure – one line. A deviation from a datasheet recommendation without a realistic
   consequence is not a finding.
7. **Check that a proposal fits before proposing it.** Dimensions from the datasheet of the exact part (including
   solder tabs) against the board geometry; electrical specs of the exact part, not of a similar one.
8. **Robust, not fitted to today's layout.** Mechanical parts derived from the layout (enclosures, stands) get
   uniform clearances over areas and contact only where needed – not pockets fitted to today's pins.
9. **Name stages and checks with words.** "Stage L (board)", "L-9 (hole fits the lead)" – nobody remembers letters.
10. **Cost matters, effort is no argument.** A cheaper part is worth a gate run; a gate run is routine, not a cost.
11. **Requests to the user stand apart at the end of a message**, not hidden in a paragraph.
12. **Circuit, layout and review are separate roles** (chapter 14.1). The circuit designer (skill circuit-design)
    hands over in writing, the PCB designer works from that in a session of its own (skill pcb-round), and the agents
    electrical-reviewer and pcb-reviewer review in theirs. A design reviewed by its designer has not been reviewed.
13. **A finding a rule could have found can become a check.** Reviewers mark such findings as check candidates; the
    user decides, nothing is filed by itself; an accepted candidate is a decision in the project's log, goes to the
    edakit repository as a proposal when the user asks (skill propose-rule), and is triaged and built there (skills
    triage-rule and add-rule, chapter 14.4). Rules come from the catalog and the
    datasheets – a rule from memory is said to be one and reported as a candidate.
14. **What a project had to build itself goes back as a feature proposal**, not as a quiet copy in edakit and not as
    a lasting workaround in the project (11.6).
15. **Time-box a failing tool.** When a tool keeps failing, read its documented limits and try the alternative before
    writing repair tooling around it – fixing the tooling (2) starts there. In the reference project about a day and
    1000 lines of repair code went into EasyEDA's autorouter, whose documented behaviour is all or nothing; Freerouting
    then routed the same board in 1.5 minutes with DRC 0.
16. **Reported means read back.** A change written to the EDA is reported or documented only after save, reload and
    read-back – best from the exported files. A fix of hole sizes and slots was reported, and written into the parts
    database and a decision, while EasyEDA had reverted it; the documents were wrong for about 1.5 hours.
17. **Tool and UI facts only from verified output.** Commands, API names, menu entries and options in documents or
    instructions come from the tool itself – the API inventory, the extension's manifest, the editor's bundle –
    never from memory; look for the EDA's own API before building a fallback around it. About 600 lines of invented
    automation docs (commands, a package, API calls that do not exist) and mock scripts with invented part numbers
    took about an hour to clean up; a raster PDF stitched from 36 screenshots was presented as the only option while
    the API had a vector export (35 minutes).
18. **Probes on a throwaway document.** Tests and probes run on a scratch document, never on a generated document the
    project uses; probe documents and library objects without a device are removed when done. A test run overwrote
    the real 113-part schematic; later, leftover probe schematics and a footprint copy without a device put a dialog in
    front of the user whose wrong answer would have changed the footprint of the main module in the order data.
19. **A principle the user has set stays set.** State the effort once, plainly; do not reopen a decided principle
    with effort arguments. After the user had set "nothing on the visible side but the LEDs", moving the tracks was
    answered with "a day of work with risk" and two more questions about alternatives – two extra decision rounds.
20. **Fix defects in your own choices.** A failing check on a part, footprint or value Claude chose is fixed and
    reported, not put to the user as "may I swap?"; only real trade-offs go to the user (4). On a second project
    Claude asked the user to approve swapping a footprint it had chosen itself, after the hole check failed on it.
21. **Say honestly how far the automation goes.** Documents and READMEs name the steps that were done or fixed by hand
    and the ones never run live. A README claimed that nothing in the EDA project was drawn by hand while much had been
    developed by hand around it; it had to be rewritten.
22. **Prefer what the project already does.** Among options, recommend the mechanism the project already uses (a plug
    and a cable, screws) over a new one (spring contacts, docking); if a new one is the only way, say that it is new
    and what must be tested. Spring-contact docking was recommended where a plug and a cable like the existing ones
    did the job, and rejected as a mechanism the project never had.
23. **Take a stated rule literally, keep a new feature on its own.** Do not tie it to existing mappings or build on an
    optional aside. A progress display stated as "from bottom left to top right" was mapped onto an unrelated existing
    order of the LEDs, followed by the question whether to rearrange other content to fit it.
24. **A declared phase limits what changes.** While the user calls the work a concept phase, every request changes the
    concept documents only – not graph, board files or firmware – until an explicit go. In a concept phase, requests
    about a 3D-printed part were taken as orders to change it; the phase had to be restated three times.
25. **Project documents stay in the repository.** Reports and documentation are files in the repository; nothing is
    published to an outside service unless the user asks. A documentation request once ended as a page hosted outside
    the repository.

## 11.5 Memory and project knowledge

The agreements of 11.4 reach every session through the plugin, so a new project does not meet them again the hard
way. Claude Code's memory (per project) and the project's CLAUDE.md are the place for the preferences of one project
that are not in the code. Facts
that are in the repository (decisions, checks, API behaviour) belong in the repository – the decision log, the
handbook, comments next to the code they explain. Each quirk in chapter 9 is also written as a comment where edakit
works around it, so the next person does not "simplify" the workaround away.

## 11.6 When edakit falls short: feature proposals

A project finds what edakit cannot do yet: a false finding (a 0 Ω bridge that the checks do not see through), a crash,
a part of the circuit the simulation leaves out, a routing or pour capability, a silkscreen it cannot place, a check
without a test. The project then builds it itself or works around it – and edakit and the project drift apart. The
loop below brings such a gap back, the same way as a rule (14.4), with its own text and its own triage:

1. **Decision in the project.** Which gaps go to edakit is the user's decision, in the project's log.
2. **Proposal.** The skill `propose-feature` writes one issue per capability from `edakit proposal template --feature`:
   Capability (what edakit should do, for any board), Gap (the command and what it says today), Reference (how the
   project does it: file, function, commit, the method in words), Interface (keys in edakit.toml or a board or schematic
   file, fields, options – each with the default that leaves existing projects as they are), Test (how a test shows it
   without EasyEDA), Origin. Shown to the user before it goes out – the issue is public, a private project's code is not
   quoted without the user's OK – and sealed like a rule proposal.
3. **Triage.** The Action `proposals` reads the section Kind and runs the skill `triage-feature`: correctly made, a
   feature and not a rule, new, the gap real at this commit, general rather than one project's taste, fitting (project
   data in the project's files, not in the code), testable without EasyEDA, one capability, clear enough. Result as for
   rules: **Accepted**, **Rejected** with a reason a person can check, or **Question**.
4. **Build.** The skill `add-feature`: the gap red in a test first, then the interface with its default, the code –
   whatever needs EasyEDA a thin call around a function that is tested –, the example and the projects at hand
   unchanged, the handbook. One commit per proposal, all of them in one open pull request from `features/proposals`.
5. **Back in the project.** The Action cannot clone a private project; the pull request gives the commands that show
   the gap closed there, and the project runs them against the branch before the user merges. After the merge the
   project's workaround goes and the decision gets `edakit: #14 built`.

Why it exists: the project edakit came from went on growing after the extraction (0 Ω bridges, a common-anode star
LED, pour-only nets). Before it can use edakit, those have to come back – one proposal each.

