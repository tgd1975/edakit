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
| skill | `/edakit:part-search` | find a part, create and sign its parts entry |
| skill | `/edakit:pcb-round` | one layout round |
| skill | `/edakit:release` | the gate, sign-offs, order checklist |
| skill | `/edakit:decision-round` | numbered findings, short answers, numbered decisions |
| agent | `edakit:easyeda-operator` | runs one long EasyEDA step and returns only the result – keeps the main conversation clean |
| agent | `edakit:electrical-reviewer` | independent circuit review; its result is the sign-off M-1 |
| agent | `edakit:pcb-reviewer` | independent layout review (read-only EasyEDA tools); its result is the sign-off M-5 |
| MCP | `easyeda` | easyeda-mcp-pro, pinned, safe defaults |
| hook | PreToolUse on the easyeda tools | claims EasyEDA for the session, refuses when another session holds it |
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
5. **Decision rounds:** numbered findings with consequence and a recommended proposal; the user answers "ad 1 ack,
   ad 2 b, ad 3 you decide"; every answer becomes a numbered decision with reason and date (decision-round skill).
6. **Realistic risks.** Per risk: how likely, what it costs. Delivery delays and stock problems are force majeure –
   one line. A deviation from a datasheet recommendation without a realistic consequence is not a finding.
7. **Check that a proposal fits before proposing it.** Dimensions from the datasheet of the exact part (including
   solder tabs) against the board geometry; electrical specs of the exact part, not of a similar one.
8. **Robust, not fitted.** Mechanical parts derived from the layout (enclosures, stands) get uniform clearances over
   areas and contact only where needed – not pockets fitted to today's pins.
9. **Name stages and checks with words.** "Stage L (board)", "L-9 (hole fits the lead)" – nobody remembers letters.
10. **Cost matters, effort is no argument.** A cheaper part is worth a gate run; a gate run is routine, not a cost.
11. **Requests to the user stand apart** at the end of a message, not hidden in a paragraph.
12. **Design and review are two roles.** The main session designs (skill circuit-design), the agent
    electrical-reviewer reviews in its own session. A design reviewed by its designer has not been reviewed.
13. **A finding a rule could have found can become a check.** Reviewers mark such findings as check candidates; the
    user decides, nothing is filed by itself; an accepted candidate is a decision in the project's log and is built
    in the edakit repository when the user asks (skill add-rule, chapter 14.4). Rules come from the catalog and the
    datasheets – a rule from memory is said to be one and reported as a candidate.

## 11.5 Memory and project knowledge

Claude Code's memory (per project) is the place for preferences like the ones above that are not in the code. Facts
that are in the repository (decisions, checks, API behaviour) belong in the repository – the decision log, the
handbook, comments next to the code they explain. Each quirk in chapter 9 is also written as a comment where edakit
works around it, so the next person does not "simplify" the workaround away.
