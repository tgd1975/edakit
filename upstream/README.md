# Upstream: what edakit needs from EasyEDA Pro and easyeda-mcp-pro

edakit drives EasyEDA Pro through [easyeda-mcp-pro](https://github.com/oaslananka/easyeda-mcp-pro). Whatever edakit
has to click, patch or work around because one of the two lacks something or gets it wrong is a requirement here –
E-… for EasyEDA Pro, M-… for easyeda-mcp-pro – and stays here until upstream has released the fix and edakit has
dropped its workaround. How each behaves today is in [handbook 9](../handbook/09-easyeda-api.md); this list says what
we want instead and where it stands. Nothing here is posted without the owner's word.

## The owner's rules (2026-11-01)

1. **No click because of the API.** The owner never has to press anything in EasyEDA Pro because its API gets
   something wrong or leaves it out. Every click edakit still asks for has its requirement below, reported at
   EasyEDA, until the API takes it over.
2. **No self-extended MCP server.** edakit patches easyeda-mcp-pro no further: what it needs goes upstream as an issue
   and a pull request from the fork [tgd1975/easyeda-mcp-pro](https://github.com/tgd1975/easyeda-mcp-pro). The two
   patches of today – `edakit/easyeda/odb-tool-patch.mjs` and `edakit/easyeda/bridge-extension-patch.sh` – stay as
   they are until the release that brings M-2 to M-4, and go with it; no new patch comes.
3. **The latest state first.** Before a requirement is reported, a branch is built or a workaround is changed, the
   check below runs. A requirement upstream has met already is not reported but taken up: the pin raised, the
   workaround removed.

## The latest state

1. easyeda-mcp-pro: in the clone `../easyeda-mcp-pro` `git fetch upstream`; the newest release
   (`npm view easyeda-mcp-pro version`) against the pin `EASYEDA_MCP_VERSION` in `edakit/easyeda/mcp-server.sh`, its
   `CHANGELOG.md` since the pin, and the source on `upstream/main` where the fix would sit. Issues and pull requests,
   open and closed: `gh search issues --repo oaslananka/easyeda-mcp-pro "<topic>"`.
2. EasyEDA Pro: the newest version on its [update record](https://pro.easyeda.com/page/update-record) against the
   installed one (`ls /opt/apps/easyeda-pro/resources/app/assets/pro-versions`), the issues of
   [easyeda/easyeda-api-sdk](https://github.com/easyeda/easyeda-api-sdk/issues), open and closed – mostly in Chinese;
   EasyEDA's first answer is "update to the latest version" –, and the API types
   (`npm view @jlceda/pro-api-types version`). An E-… is checked live on the newest version before it is reported.
3. The fork's branches rebased onto `upstream/main`, their tests green.
4. The column "Checked" takes the version checked against.

**Last check, 2026-11-01:**

- easyeda-mcp-pro 1.6.0 (2026-10-28) is the newest; edakit pins 1.4.0. Nothing from 1.4.0 to 1.6.0 meets M-1 to M-4
  – on `upstream/main` the return depth is still 5, the PDF export still calls the PCB's function first, there is no
  ODB++, `src/bridge/manager.ts` is untouched – and no issue or pull request there covers them. Since 1.5.1 the
  server refuses writes from a bridge extension of another version: raising the pin takes the extension of the same
  version, imported anew (E-4). The anchors of both patches are still in 1.6.0.
- The fork's three branches rebased onto 1.6.0 (`e52d862`); their tests in the table of the branches below.
- EasyEDA Pro 3.2.209 (2026-10-21) is the newest; 3.2.206 is installed. 3.2.209's notes name no change of the API.
  At easyeda-api-sdk five of ours are reported already, by others: #33, #34, #36, #38, #39 (in the tables).
- EasyEDA has published an AI skill with a WebSocket bridge of its own,
  [easyeda/easyeda-api-skill](https://github.com/easyeda/easyeda-api-skill) – not examined.

## EasyEDA Pro – its extension API

Reported at [easyeda/easyeda-api-sdk](https://github.com/easyeda/easyeda-api-sdk/issues): to a known issue our case
as a comment, otherwise an issue of its own. Nothing of ours is reported yet.

### The clicks

| # | Requirement | The click today | Handbook | Upstream | Checked |
|---|---|---|---|---|---|
| E-1 | `DMT_Project.createProject` creates a project in the local desktop client – its local server wants a folder `path` the API cannot pass | *File → New → Project*, once per project | 9.2 Creating projects | new; the [draft](issue-4-create-project.md) is written for easyeda-mcp-pro – rewrite it for EasyEDA, M-5 keeps the server's part | 3.2.206 |
| E-2 | Import Changes without the dialog: `PCB_Document.importChanges(uuid, true)` honours `force`; the DRC drops "Netlist Error – Import Changes" once schematic and PCB agree; a call says whether an import is pending and what differs | *Design → Import Changes* after parts were placed in the schematic | 9.4 The one click left, Netlist → PCB | #39 (open: a false Netlist Error from `netlistComparison` with the PCB's UUID) and #33 (open: pad numbers null until a reload, the Netlist Error without details; EasyEDA: fixed in a newer 3.2) – our case as a comment | 3.2.206 |
| E-3 | Calls address a document by its UUID, whichever tab is active: the PCB answers `PCB_Drc.check`, `getDsnFile` and the exports without its tab counting as active; schematic reads and writes act on the page named | edakit switches to the start page and back; when that fails, "click the PCB tab once" | 9.2 Active tab, PCB tab "active" | new | 3.2.206 |
| E-4 | Install and update an extension without the GUI – a command-line option, a folder the client reads, or an API call | for every bridge extension: uninstall, import, allow "External interaction", restart – since easyeda-mcp-pro 1.5.1 at every update of the server | 2.5 | new | 3.2.206 |

### Defects edakit works around

| # | Requirement | edakit's workaround | Handbook | Upstream | Checked |
|---|---|---|---|---|---|
| E-5 | `SCH_PrimitiveText.delete` and `.modify` are saved | deletes texts through `SCH_PrimitiveCircle.delete` | 9.3 Texts | #36 (open) | 3.2.206 |
| E-6 | `PCB_Document.clearRouting` ends without a dialog | deletes lines and vias by id and counts again | 9.4 Deleting tracks | #38 (open) | 3.2.206 |
| E-7 | The DRC is right after API writes without save, close and reopen | saves, closes and reopens before every DRC | 9.4 DRC after API changes | related: #34 (EasyEDA: fixed in the current version) – check on 3.2.209 | 3.2.206 |
| E-8 | `modifySchematicName(uuid, …)` renames the schematic passed; `getAllSchematicsInfo` returns current names and lists a document as soon as it exists | activates, renames, reads every name back, checks the panels | 9.3 Renaming, Reading names | new | 3.2.206 |
| E-9 | Local projects: `getAllProjectsUuid` lists them; `modifyProjectDescription` and `modifyProjectFriendlyName` work | reads EasyEDA's `config.json` and the `.eprj2` files | 9.2 Local projects | new | 3.2.206 |
| E-10 | Deleting a part or a net flag deletes its attribute texts | deletes them by their parent id | 9.3 Orphan attributes | new | 3.2.206 |
| E-11 | Footprints: a placed part takes its edited footprint without being deleted and placed anew; a device made by `LIB_Device.create` or `copy` can be placed in the local client; `SCH_PrimitivePin.modify` is saved | `edakit part build` rebuilds the copy of a system part, the parts are placed anew | 9.4 Footprints in the project | new | 3.2.206 |
| E-12 | A placed part's footprint geometry is readable without turning or moving the part | turns it to 0° on TOP, reads, turns it back | 9.4 Footprint geometry | new | 3.2.206 |
| E-13 | Pours: a `$complexPolygon` with holes is filled as drawn; filling works while a non-plated pad without part – a tooling hole – is on the board | takes tooling holes out before filling and puts them back; the pours keep a notch around them | 9.4 Pours, Free pads | new – whether the failing fill is EasyEDA's or `easyeda_pcb_rebuild_copper`'s is not found yet | 3.2.206, 1.4.0 |
| E-14 | `PCB_Document.autoLayout` places on both sides | parts on the bottom are placed by the plan (`[place]`) | 9.4 Auto-layout | new | 3.2.206 |
| E-15 | `addIntoBom: false` works when a library part is created | creates the part, then modifies it | 9.3 `batch_write` | new – whether the "Invalid device" is EasyEDA's or `easyeda_schematic_batch_write`'s is not found yet | 3.2.206, 1.4.0 |
| E-16 | ODB++: `getOpenDatabaseDoublePlusFile` out of BETA, honours `unit`, takes a file name | packs EasyEDA's tgz, removes the file `undefined` | 9.1 ODB++ | new | 3.2.206 |

E-2 (the query whether an import is pending), E-3 (writing by document id) and E-11 to E-15 come from the analysis
of the project histories that pytree-27 left in the owner's TODO list.

## easyeda-mcp-pro

An issue first, then the fork's branch and its pull request with "Fixes #<issue>"; the issue drafts follow the
repository's issue forms field by field, the pull request drafts its template. On the first substantial pull request
the maintainer asks once for the comment "I agree to the Contributor Permission v1 in CONTRIBUTOR-LICENSING.md" from
the account that opened it – a consent in the owner's name, given by the owner.

| # | Requirement | Local workaround – goes with the release | Upstream | Fork branch | Checked |
|---|---|---|---|---|---|
| M-1 | The stale sweep honours each request's own timeout | `BRIDGE_TIMEOUT_MS=120000` for every server – a setting, no patch | [issue](issue-1-stale-sweep.md), [pull request](pr-1-stale-sweep.md) | `fix/stale-sweep-per-request-timeout` | 1.6.0 |
| M-2 | `easyeda_export_pdf` with `what: "schematic"` exports the schematic | `bridge-extension-patch.sh` | [issue](issue-2-schematic-pdf.md), [pull request](pr-2-schematic-pdf.md); #527 (closed) only stopped the false success | `fix/schematic-pdf-export` | 1.6.0 |
| M-3 | `easyeda_api_call` returns deeper results (`maxDepth`) – DRC details and the rule set lie 9 levels deep | `bridge-extension-patch.sh` (depth 12) | [issue](issue-3-api-call-depth.md), [pull request](pr-3-api-call-depth.md) | `feat/api-call-max-depth` | 1.6.0 |
| M-4 | ODB++ export as a tool | `odb-tool-patch.mjs` and `bridge-extension-patch.sh` | [issue](issue-5-odb-export.md), [pull request](pr-4-odb-export.md) | `feat/odb-export` – not built | 1.6.0 |
| M-5 | `easyeda_api_call` reports a create call that returns null as a failure | checks the open project's name before every run | [issue](issue-4-create-project.md), its server part | – | 1.4.0 |
| M-6 | The schematic read tools and the BOM read a page by its UUID without switching the owner's tab; the BOM of a board-linked schematic lists each part once | focuses page after page, merges, removes the duplicates, checks the focus after each read | #526 (closed into the design draft #539, built later) – our case as a comment there | – | 1.6.0 |
| M-7 | The pick-and-place export returns csv when csv is asked: the bridge passes the project id as the file name and no type to `getPickAndPlaceFile(fileName, fileType, unit)`, so EasyEDA answers with its default xlsx | reads the xlsx | new | – | 1.6.0 |
| M-8 | The bridge connects by itself, also after a crash of EasyEDA, and shows its menu | the skill start asks for *MCP Bridge → Connect*, or restarts EasyEDA | report only if the original extension does it too – the patched one sometimes shows no menu | – | 1.4.0 |

Fork branches in the clone `../easyeda-mcp-pro`, rebased onto 1.6.0 on 2026-11-01, not pushed yet:

| Branch | Commit | Tests on 1.6.0 |
|---|---|---|
| `fix/stale-sweep-per-request-timeout` | `fix(bridge): stale sweep honours each request's own timeout` | its test file 69 green, extension 568 green, `pnpm verify:fast` green |
| `fix/schematic-pdf-export` | `fix(export): schematic PDF through SCH_ManufactureData.getExportDocumentFile` | extension 569 green, `pnpm verify:fast` green; the whole server suite as on `upstream/main`: green but for the test that expects no ngspice (installed here) |
| `feat/api-call-max-depth` | `feat(api): optional maxDepth for easyeda_api_call results` | its test files 59 green, extension 571 green, `pnpm verify:fast` green |

## The component library (EasyEDA / LCSC)

Errors in the library data `edakit part import` reads go to EasyEDA's component library, not to easyeda-mcp-pro.

| # | Topic | Local workaround | Report |
|---|---|---|---|
| 6 | Six symbols differ from their datasheets – a pin number given twice (WS2812B-V5/W, Pico 2, DRV8825), names swapped (XC6206, Pico 2's debug pins), a pad without a pin (DRV8825's PowerPAD, AQY212GS), the LED's pins of a 6N138 named "2" and "NC" | STRUCT.entry compares the cached symbol with the entry and the footprint; the library entries say where they follow the datasheet (`symbol_differs`, handbook 4.4) | [report draft](issue-6-easyeda-symbols.md) – not sent |
