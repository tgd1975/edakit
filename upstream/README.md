# Upstream contributions to easyeda-mcp-pro

edakit runs on [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro). What we had to patch or work around
locally goes upstream as an issue first and a small pull request from the fork
[tgd1975/easyeda-mcp-pro](https://github.com/tgd1975/easyeda-mcp-pro). Once a fix is released, the matching workaround
here is removed and the pinned version in `edakit/easyeda/mcp-server.sh` is raised.

| # | Topic | Local workaround | Upstream |
|---|---|---|---|
| 1 | Stale sweep cancels requests that have a longer timeout of their own | `BRIDGE_TIMEOUT_MS=120000` for every server | [issue draft](issue-1-stale-sweep.md), branch `fix/stale-sweep-per-request-timeout` |
| 2 | `easyeda_export_pdf` with `what: "schematic"` calls the PCB export | `bridge-extension-patch.sh` | [issue draft](issue-2-schematic-pdf.md), branch `fix/schematic-pdf-export` |
| 3 | `easyeda_api_call` results cut after 5 levels (`[MaxDepth]`) | `bridge-extension-patch.sh` (depth 12) | [issue draft](issue-3-api-call-depth.md), branch `feat/api-call-max-depth` |
| 4 | `DMT_Project.createProject` returns null in the local desktop client | project created by hand | [issue draft](issue-4-create-project.md) |
| 5 | No ODB++ export (`PCB_ManufactureData.getOpenDatabaseDoublePlusFile`) – AISLER assembles from ODB++ | `odb-tool-patch.mjs` (the tool, patched in by `mcp-server.sh`) and `bridge-extension-patch.sh` (the handler) | [issue draft](issue-5-odb-export.md), [PR draft](pr-4-odb-export.md) – branch not built yet |

The issue drafts follow the repository's issue forms field by field; the PR drafts ([1](pr-1-stale-sweep.md), [2](pr-2-schematic-pdf.md), [3](pr-3-api-call-depth.md)) follow its pull request template.

Status (2026-10-25): issue texts drafted, not posted. The three branches are committed in the local clone of the fork
(`../easyeda-mcp-pro`) on top of upstream `main` (1.5.4), not pushed yet:

| Branch | Commit | Tests |
|---|---|---|
| `fix/stale-sweep-per-request-timeout` | `fix(bridge): stale sweep honours each request's own timeout` | new regression test red without the fix, green with it; `pnpm verify:fast` green |
| `fix/schematic-pdf-export` | `fix(export): schematic PDF through SCH_ManufactureData.getExportDocumentFile` | 569 extension tests green; `verify:fast` green |
| `feat/api-call-max-depth` | `feat(api): optional maxDepth for easyeda_api_call results` | 571 extension tests, server suite green except one test that also fails on upstream `main` here (ngspice installed); `verify:fast` green |

Order: post the issue, then push the branch and open the PR with "Fixes #<issue>". On the first substantial PR the
maintainer asks once for the comment "I agree to the Contributor Permission v1 in CONTRIBUTOR-LICENSING.md" from the
account that opened it.

## The component library (EasyEDA / LCSC)

Errors in the library data `edakit part import` reads go to EasyEDA's component library, not to easyeda-mcp-pro.

| # | Topic | Local workaround | Report |
|---|---|---|---|
| 6 | Six symbols differ from their datasheets – a pin number given twice (WS2812B-V5/W, Pico 2, DRV8825), names swapped (XC6206, Pico 2's debug pins), a pad without a pin (DRV8825's PowerPAD, AQY212GS), the LED's pins of a 6N138 named "2" and "NC" | STRUCT.entry compares the cached symbol with the entry and the footprint; the library entries say where they follow the datasheet (`symbol_differs`, handbook 4.4) | [report draft](issue-6-easyeda-symbols.md) – not sent |
