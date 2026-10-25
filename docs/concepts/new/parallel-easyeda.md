# Parallel EasyEDA instances

Status 2026-10-25: proposal. Nothing is built, and nothing has been tried live. The findings come from reading the code
of easyeda-mcp-pro 1.4.0 (`dist/bridge/manager.js`, `dist/bridge/listener-ownership.js`), the bridge extension it ships
(`dist/index.js`) and EasyEDA Pro 3.2.206 (`resources/app/app.js`).

## Why

There is one EasyEDA per machine, and the claim makes sessions take turns
([handbook 11.2](../../../handbook/11-working-with-claude.md#112-parallel-sessions-share-one-easyeda)). Within one
project that is right. Two projects on one machine, for example the reference project and the Christmas bell, wait for
each other although they never touch the same document. A project with its own claim (the reference project's git
coordination tool, state in `<git-dir>/claude-sync.json`) does not even see edakit's claim
(`~/.local/state/edakit/easyeda-lock.json`), so the two can pull tabs away from each other today.

**Goal:** one EasyEDA instance per project. Each instance has its own bridge port, MCP server and claim, so sessions on
different projects do not wait for each other. **Not a goal:** two instances on the same project. The project file
(`.eprj2`) is one SQLite database, and work inside one project stays serialised by the claim.

## Why it does not work today

| # | Layer | Behaviour |
| --- | --- | --- |
| 1 | MCP server | The first server becomes the owner: it creates the lock directory `bridge-listener.lock` in `DATA_DIR` (default `~/.easyeda-mcp-pro`) and listens on the first free port of `BRIDGE_PORT_SCAN` (49620–49629). Every later server becomes a follower and sends its calls through the owner, so every server on the machine reaches the same EasyEDA. |
| 2 | MCP server | The owner holds exactly one EasyEDA connection. A second EasyEDA that connects replaces the first ("replacing existing bridge client connection"). |
| 3 | Extension | Scans 49620–49629 and always tries 49620 first. The port it prefers is kept only in memory and starts at 49620, and after a dropped connection it reconnects by itself. Two EasyEDA instances would both land on 49620 and keep replacing each other. |
| 4 | Extension | `BRIDGE_TOKEN` on the server could reject the wrong extension, but the extension's `BRIDGE_SESSION_TOKEN` is fixed at build time, so each instance would need its own build anyway. |
| 5 | EasyEDA | Allows one instance only (`requestSingleInstanceLock`). It sets its data directory itself to `$HOME/.config/EasyEDA-Pro/…` (`app.setPath`), so `--user-data-dir` does not help. A second start just opens another window in the running instance. |
| 6 | EasyEDA | Several windows of one instance do not help either: the API acts on the focused tab. |

## Design

An instance is a name plus four things: an EasyEDA home, a bridge port, an MCP `DATA_DIR` and a claim file. The
instance `default` keeps today's values (49620, `~/.easyeda-mcp-pro`, `~/.config/EasyEDA-Pro`,
`easyeda-lock.json`), so a setup with one instance does not change.

1. **EasyEDA:** each further instance runs with its own `HOME`, e.g. `~/.local/share/edakit/instances/<name>/home`,
   started like in [handbook 2.6](../../../handbook/02-setup.md#26-easyeda-without-background-throttling) with
   `HOME=…` added. Set it up once, as in 2.2 and 2.5: activation, import of the extension, then create or import the
   project there. A project lives in exactly one instance.
2. **Extension with a fixed port, in every instance, the default one included:**
   `BRIDGE_PORT=49621 bridge-extension-patch.sh` sets `BRIDGE_PORT` and `PORT_SCAN_COUNT = 1` in the bundle and adds
   the port to the display name. Without this, an extension whose own server is not running scans on and takes over
   another instance's server.
3. **MCP server:** `mcp-server.sh` resolves the instance from `EDAKIT_INSTANCE`, then from `edakit.toml` in the
   working directory, and otherwise uses `default`. For an instance other than `default` it sets
   `DATA_DIR=~/.easyeda-mcp-pro/instances/<name>` (own owner lock) and `BRIDGE_PORT_SCAN=<port>` (one port, so it
   never takes another instance's port). There is still one MCP entry in the plugin, and the tool names stay
   `mcp__plugin_edakit_easyeda__*`. One session works with one instance; switching means reconnecting with `/mcp`.
4. **Configuration:** `[easyeda] instance = "bell"` and `port = 49621` in `edakit.toml`. `edakit` commands pass both
   to `mcp-server.sh`.
5. **Claim:** one state file per instance (`easyeda-lock-<name>.json`). The hook finds the instance from the `cwd` in
   the hook JSON. `edakit lock` shows the instance it means.
6. **Doctor:** for each configured instance, `edakit doctor` shows the port, the owner PID, whether EasyEDA is connected
   and which project is open. It warns when more than one instance is configured but an extension still scans
   (`PORT_SCAN_COUNT` 10), and when two instances share a port.

## What stays

- **Memory:** every instance is a full Electron application. On the reference machine (14 GB) about 3 GB were left
  with one instance and the IDE running, and a single EasyEDA has already died of V8 out-of-memory during long runs.
  Two large boards at once will be tight; measure before building.
- **Small gain on one project:** checks, simulation, Freerouting and the Gerber analysis already run without EasyEDA.
  Only the EasyEDA steps of *different* projects become parallel.
- **Upstream would be the better place:** a port that can be set in the extension at run time (setting or menu)
  instead of a build constant, and a server that rejects a second client instead of silently replacing the first.
  Both are candidates for [upstream/](../../../upstream/README.md).

## Steps

Each step is checked before the next one starts.

1. **Without code:** start a second EasyEDA with its own `HOME`. Does it start next to the first one (step 5 of the
   table)? Do activation, fonts and the extension import work? Measure memory with two boards open.
2. **By hand:** build an extension with a fixed port, then start a second server with `DATA_DIR` and `BRIDGE_PORT_SCAN`.
   `DMT_Project.getCurrentProjectInfo` returns a different project on each server, and after 10 minutes neither log
   contains "replacing existing bridge client connection".
3. **Code:** instance resolution in `mcp-server.sh`, the port in `bridge-extension-patch.sh`, the configuration key,
   claim per instance, doctor; handbook 2.4–2.6 and 11.2.
4. **Negative tests** in `tests/`: an extension that still scans while two instances are configured, two instances on
   one port, a project without an instance while the `default` instance holds another project.

## Open questions

- Does EasyEDA Pro run cleanly under another `HOME` (activation file, login, GTK settings)? Step 1 answers it.
- Does Claude Code start a plugin's MCP server in the project directory? If not, the instance comes from `env` in the
  project's `.claude/settings.json` (`EDAKIT_INSTANCE`).
- Is it worth the effort? Only if two projects are worked on with EasyEDA at the same time regularly.
