#!/usr/bin/env bash
# Starts easyeda-mcp-pro in a pinned version – for Claude Code (plugin .mcp.json or a project .mcp.json) and for the
# edakit scripts, which start their own server instance. Arguments are passed through:
#   mcp-server.sh                    -> MCP server (stdio)
#   mcp-server.sh doctor             -> check environment and bridge
#   mcp-server.sh extension --copy . -> copy the bridge extension (.eext) here
#
# IMPORTANT: in server mode stdout speaks the MCP protocol. Never print anything to stdout.
set -euo pipefail

EASYEDA_MCP_VERSION="${EASYEDA_MCP_VERSION:-1.4.0}"
RUNTIME_DIR="${EASYEDA_MCP_RUNTIME_DIR:-$HOME/.easyeda-mcp-pro/runtime/$EASYEDA_MCP_VERSION}"
ENTRY="$RUNTIME_DIR/node_modules/easyeda-mcp-pro/dist/index.js"

# Clients started from a desktop launcher often lack nvm in PATH.
if ! command -v node >/dev/null 2>&1 && [ -s "$HOME/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1
fi

node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [ "$node_major" != "24" ]; then
  echo "easyeda-mcp-pro $EASYEDA_MCP_VERSION needs Node 24.x (found: $(node -v 2>/dev/null || echo none))" >&2
  exit 1
fi

# Install once, pinned. Not through npx: npx does not pass SIGTERM on to the server, which then lingers as an
# orphan and keeps the bridge port 49620 busy.
if [ ! -f "$ENTRY" ]; then
  echo "Installing easyeda-mcp-pro@$EASYEDA_MCP_VERSION to $RUNTIME_DIR ..." >&2
  npm install --prefix "$RUNTIME_DIR" --no-save --no-audit --no-fund "easyeda-mcp-pro@$EASYEDA_MCP_VERSION" >&2
fi

# ODB++ for a maker that assembles from it (edakit handbook 8.4, SYNC.odb): the tool easyeda_export_odb, patched into the
# installed server – once; a patched server is left as it is. Its messages go to stderr.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
node "$HERE/odb-tool-patch.mjs" "$RUNTIME_DIR/node_modules/easyeda-mcp-pro/dist/tools/L1_export.js" >&2 ||
  echo "easyeda_export_odb not patched in – the server runs without the ODB++ export" >&2

# Profile "full": schematic/PCB write tools plus the controlled easyeda_api_call (writes need confirmWrite=true).
export TOOL_PROFILE="${TOOL_PROFILE:-full}"
# Ordering hard off – orders are placed by a human in the browser.
export JLCPCB_MODE="${JLCPCB_MODE:-disabled}"
export JLCPCB_ENABLE_ORDERING=false
# No raw JavaScript in the editor.
export BRIDGE_RAW_EXEC_ENABLED=false
# Exports (Gerber, BOM, PDF, ...) go to the project instead of ~/.easyeda-mcp-pro. edakit sets its own per run.
export ARTIFACT_DIR="${ARTIFACT_DIR:-$PWD/build/easyeda-mcp}"
export LOG_LEVEL="${LOG_LEVEL:-warn}"
# Bridge calls may take 120 s instead of 15 s: DRC and copper pours of a large board need longer. The server that holds
# the bridge port drops pending requests after ITS timeout ("stale sweep") – also requests another server (e.g. a
# script's) passes through with a longer timeout. So every server needs the same value (checked with 1.4.0).
export BRIDGE_TIMEOUT_MS="${BRIDGE_TIMEOUT_MS:-120000}"

exec node "$ENTRY" "$@"
