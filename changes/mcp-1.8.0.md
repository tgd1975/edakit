minor
- **When updating:** easyeda-mcp-pro is pinned to 1.8.0 (was 1.6.0), and server and bridge extension must have the
  same version. Copy the extension out of the pinned server (`bash <plugin>/edakit/easyeda/mcp-server.sh extension
  --copy .`), in EasyEDA uninstall the old "MCP Pro Bridge" – also the patched one named "MCP Pro Bridge (depth 12,
  schematic PDF, ODB++)" –, import the new one, allow "External Interactions", restart EasyEDA, then end every running
  `easyeda-mcp-pro` server (`pgrep -af easyeda-mcp-pro`; Claude Code's restarts with `/mcp`). `edakit doctor` then
  shows "bridge extension 1.8.0 = server 1.8.0" and "return depth: answers deeper …" (handbook 2.4, 2.5).
- edakit's two patches of easyeda-mcp-pro are gone (`bridge-extension-patch.sh`, `odb-tool-patch.mjs`): 1.7.0 brings
  their fixes – `maxDepth` for `easyeda_api_call` (edakit asks 12 levels), the schematic PDF, `easyeda_export_odb` (in
  edakit's own servers, profile `experimental`). The pick-and-place export comes as csv (`cpl_easyeda.csv`, an xlsx of
  an older extension read as well), hand-soldered parts leave the BOM on create, and a net's pours fill in one call
  (upstream M-1 to M-10, TD-26, TD-84). easyeda-mcp-pro is MIT licensed since 1.7.0.
