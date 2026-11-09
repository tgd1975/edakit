minor
- **When updating:** easyeda-mcp-pro is pinned to 1.11.0 (was 1.8.0), and server and bridge extension must have the
  same version. Copy the extension out of the pinned server (`bash <plugin>/edakit/easyeda/mcp-server.sh extension
  --copy .`), in EasyEDA uninstall the old "MCP Pro Bridge", import the new one, allow "External Interaction", restart
  EasyEDA, then end every running `easyeda-mcp-pro` server (`pgrep -af easyeda-mcp-pro`; Claude Code's restarts with
  `/mcp`). `edakit doctor` then shows "bridge extension 1.11.0 = server 1.11.0" (handbook 2.4, 2.5).
- `schematic check` and stage S close only their own schematic's tabs before they read; the other schematics stay
  open. easyeda-mcp-pro 1.9.0 reads the nets of the focused page only (M-11, our #865), so a net flag of another open
  schematic no longer puts a pin on a second net (#117). Another schematic with unsaved changes is no longer a
  finding `saved`.
- edakit sends the open project's UUID as `projectId` to easyeda-mcp-pro's tools instead of `"current"`, which its
  schematic and PCB reads refuse since 1.9.0 (`current-project-uuid-mismatch`).
