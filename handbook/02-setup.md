# 2 Setup

Tested with EasyEDA Pro 3.2.206 on Linux (Ubuntu), easyeda-mcp-pro 1.4.0, Node 24, Python 3.11–3.14, ngspice 45,
Freerouting 2.4.1, Claude Code 2.1.3xx. Windows and macOS should work for everything except the bundled Freerouting
download (set `FREEROUTING_JAR`) – untested.

## 2.1 What talks to what

```text
Claude Code ──stdio──► easyeda-mcp-pro ◄──WebSocket 127.0.0.1:49620──► bridge extension in EasyEDA Pro
 (plugin manifest)     (edakit/easyeda/mcp-server.sh)                    (menu "MCP Bridge")
edakit ──────stdio──► easyeda-mcp-pro (its own instance, the same bridge connection)
```

EasyEDA Pro has no command line and no HTTP API. It can be automated only through its **extension API**, which
exists inside the running editor. [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro) brings an
extension that connects to a local MCP server; the server exposes 115 tools plus a controlled generic call into the
extension API. edakit uses the same server.

## 2.2 Install

1. **EasyEDA Pro** (desktop, not the web version): from easyeda.com. Create or open your project once.
2. **Node 24** (easyeda-mcp-pro 1.4.0 requires it): `nvm install 24`. The launcher sources nvm itself when started
   from a desktop client without it in PATH.
3. **uv** (runs edakit with its dependencies): <https://docs.astral.sh/uv/>.
4. **ngspice** (stage E): `sudo apt install ngspice` (or your package manager).
   **pdftotext** (optional, poppler-utils): `edakit part fetch` checks with it whether a datasheet has a text layer
   and names its part number (4.3).
5. **Freerouting**: nothing to do on Linux x64 – `edakit route` downloads the pinned release (with its own Java)
   to `~/.local/share/freerouting/` and checks its SHA-256. Elsewhere: download `freerouting-2.4.1.jar`, install
   Java 21+, set `FREEROUTING_JAR`. (Java 17 is too old for Freerouting 2.x.)

## 2.3 Claude Code: the plugin

```text
/plugin marketplace add tgd1975/edakit
/plugin install edakit@edakit
```

In the VS Code extension, which has no `/plugin`: `claude plugin marketplace add tgd1975/edakit` and
`claude plugin install edakit@edakit` in a terminal – with only the extension installed, `claude` is
`~/.vscode/extensions/anthropic.claude-code-<version>-linux-x64/resources/native-binary/claude`. How to update:
README, Install.

This installs the skills (`/edakit:start`, `/edakit:hardware-change`, …), the agents, the MCP server `easyeda`
(tools `mcp__plugin_edakit_easyeda__*`), the EasyEDA claim hook, the session hook that brings the working agreements
(11.4) into every session of an edakit project, and the command `edakit` on the Bash PATH. Confirm the MCP server when
Claude Code asks (or `/mcp` → easyeda).

To give every session in a project the plugin automatically, put this into the project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "edakit": { "source": { "source": "github", "repo": "tgd1975/edakit" } }
  },
  "enabledPlugins": { "edakit@edakit": true }
}
```

Without Claude Code (CI, a terminal): `uvx --from git+https://github.com/tgd1975/edakit edakit <command>`,
or from a clone `uv run --project /path/to/edakit edakit <command>`.

## 2.4 The MCP server

`edakit/easyeda/mcp-server.sh` installs easyeda-mcp-pro **pinned** to 1.4.0 into
`~/.easyeda-mcp-pro/runtime/1.4.0` (once) and starts `node` directly, with safe defaults:

| Setting | Value | Why |
|---|---|---|
| `TOOL_PROFILE` | `full` | schematic/PCB write tools and `easyeda_api_call` (writes need `confirmWrite: true`) |
| `JLCPCB_MODE`, `JLCPCB_ENABLE_ORDERING` | `disabled`, `false` | nothing can be ordered from Claude – orders are placed by a human |
| `BRIDGE_RAW_EXEC_ENABLED` | `false` | no arbitrary JavaScript in the editor |
| `ARTIFACT_DIR` | `$PWD/build/easyeda-mcp` | exports land in the project, not in the home directory |
| `BRIDGE_TIMEOUT_MS` | `120000` | DRC and pour fills of a large board take longer than the default 15 s |

**Pinned, not npx:** the tool set and the extension must match, and npx does not pass SIGTERM on – an orphaned server
then blocks the bridge port. Update deliberately: raise `EASYEDA_MCP_VERSION`, rebuild the patched extension (2.5),
re-import it, restart EasyEDA.

The bridge listens on 127.0.0.1 only. The only online calls are read-only part lookups (LCSC product data, JLCPCB's
public assembly catalogue) – only part numbers leave the machine.

## 2.5 The bridge extension, patched

The original extension cuts every API answer after 5 levels – DRC details are then unreadable – and cannot export a
schematic as PDF. Build the patched one:

```bash
bash <plugin or clone>/edakit/easyeda/bridge-extension-patch.sh      # -> ./easyeda-bridge-extension.eext
```

The script takes the extension from the pinned server, raises the depth to 12, adds the schematic PDF path, checks the
bundle still parses, and renames it "MCP Pro Bridge (depth 12, schematic PDF)". If the extension changed upstream it
stops instead of patching blindly.

Import in EasyEDA: *Settings → Extensions → Extension Manager → Import*. It asks for the permission "External
Interactions" itself. Then the menu **MCP Bridge** appears; choose **Enable Auto-Connect**.

Re-importing (update, other depth): EasyEDA does not take an import over an installed copy with the same UUID and
version. **Uninstall the old one, import, restart EasyEDA**; until the restart the old copy keeps running. After that
restart the menu sometimes is missing, but Auto-Connect stays on and connects. Check: `edakit doctor` says "patched
extension" – it asks `DMT_Project.getCurrentProjectInfo`, which shows the pages written out instead of `[MaxDepth]` –
and "bridge extension 1.4.0 = server 1.4.0". It probes the depth only while EasyEDA is free or claimed by you; the
version and registry lines come from `easyeda_health_check`, which needs no claim. The patched build keeps the UUID
and version of the original, so neither EasyEDA's extension manager nor the version tells the two apart – the depth
does.

## 2.6 EasyEDA without background throttling

Chromium throttles timers of covered windows, and EasyEDA computes DRC, pour fills and exports in many small timer
steps. With VS Code covering EasyEDA, the DRC of a 120-part board took longer than 120 s and failed; unthrottled it
takes 1–4 s. Make the desktop launcher start it unthrottled (Linux):

```bash
sed 's|^Exec=.*|Exec=/opt/apps/easyeda-pro/easyeda-pro %f --no-sandbox --gtk-version=3 --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows|' \
  /usr/share/applications/easyeda-pro.desktop > ~/.local/share/applications/easyeda-pro.desktop
```

From a shell inside VS Code or Claude Code start it only with `env -u ELECTRON_RUN_AS_NODE setsid /opt/apps/easyeda-pro/
easyeda-pro --no-sandbox --gtk-version=3 --disable-background-timer-throttling --disable-renderer-backgrounding
--disable-backgrounding-occluded-windows` – VS Code's shells carry `ELECTRON_RUN_AS_NODE`, and EasyEDA then behaves like
Node. Check: `edakit doctor` ("EasyEDA unthrottled").

## 2.7 A project

```bash
cd my-project
/edakit:new-project my-board          # in Claude Code – or copy the example's files and adapt
edakit doctor                         # tool chain ready?
edakit check && edakit sim            # offline, seconds
```

The skill sets the project up from an interview, not from the example's defaults. It asks for the boards – one or
several, a bought board on a cable (4.5), variants –, who assembles, the order, a budget, the purpose, the
requirements, firmware that follows the graph, documents that quote values, and the project's own scripts and agents.
Each answer sets its keys; the skill proposes every file and key with its reason and writes only after your OK. In
Claude Code the interview is a form with options – up to four questions at a time, your own words for the rest –,
elsewhere one decision round in text. The purpose – private, a gift or for sale – decides how deep the regulatory
review M-6 goes (chapter 15); the review is support, not legal advice: nothing in it is legally guaranteed, and it
claims no correctness.

**Moving a project to edakit.** A repository without edakit.toml but with hardware files, scripts or agents of its
own – a netlist, parts, a board, gate runs, `.claude/agents/` – takes the same skill. First the agent
`project-surveyor` makes the inventory, beside the agent `requirements-engineer`: per place – hardware data, the
EasyEDA project and released runs, scripts, agents, skills, documents with values, decisions, hooks and CI – what it
found and where, the proposal (a key, an entry of `[scripts]` or `[agents]`, a file) and its reason, the
contradictions between the project's documents and what it could not read. Its proposals are the interview's answers
to confirm. The project's files stay where they lie and edakit.toml names them; the project's own skills are listed
with their edakit counterpart and what they do beyond it – keeping or deleting each is your decision, the setup
deletes none.

Then open the EasyEDA project once (edakit remembers its UUID and reopens it after an EasyEDA restart) and follow
chapters 6–8. Daily: start EasyEDA → open the project → work.

## 2.8 Licences of the parts you combine

edakit itself is MIT licensed ([LICENSE](../LICENSE)). It uses, without bundling them: **easyeda-mcp-pro** (PolyForm Noncommercial
1.0.0 – fine for private projects; check its licence before commercial use), **EasyEDA Pro** (proprietary, free),
**Freerouting** (GPL-3.0, downloaded at first use), **ngspice** (BSD).
