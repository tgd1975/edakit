# Ordering at JLCPCB through its interfaces

Status 2026-10-30: proposal; the path is decided (Claude in Chrome, up to "Save to Cart", below). Nothing is built, and no call has been
made live. The findings come from JLCPCB's help
article on its online API, search summaries of the developer portal (api.jlcpcb.com, behind a login), the code of
open-source clients of the official API and of the web shop, and EasyEDA Pro's documentation. jlcpcb.com and
api.jlcpcb.com were not reachable from the session that wrote this, so every endpoint below is marked as **verified**
(in a JLCPCB source or in code that calls it) or **reported** (one secondary source), and step 0 checks them.

## Why

Today the owner does the order (handbook 8.4): uploading `gerber_<b>.zip`, `bom_<b>.csv` and `cpl_<b>.csv`, typing the
form from `fab/<board>/order.md`, reading the quote, M-2 in the assembly preview, paying. edakit prepares all of it.
The typing is still by hand, and so is reading what the order really costs. Three things go wrong there:

1. **Form by hand.** The reference cart still said "Remove Mark" although the board had the placeholder; the remark
   was wrong three times (8.4). F-6 checks `[order]` against the files, but nothing checks the form against `[order]`.
2. **Upload of the wrong run.** `edakit release verify` has to be run by hand right before the upload.
3. **Real cost not fed back.** `edakit cost` estimates within about 1 $ of the cart, but the fee table
   (`edakit/fees/jlcpcb.json`) is updated by hand from carts and help pages, and `[cost] pcb_price` is typed in.

**Goal:** from a released run, the files are uploaded, every form field is set from `order.md`, the quote is read
(PCB, assembly fees, parts, shipping) and compared with `edakit cost`, and after the order the real cost is read and
kept with the run – each checked by edakit against the release. **Not a goal:** ordering and paying. The skill ends
with the board in the cart; the order is placed and paid by the owner, after M-2 – a human
sign-off that no agent gives (handbook 10, `signs`).

## What JLCPCB offers

### The official Open API

| Item | Finding | Basis |
| --- | --- | --- |
| Portal, docs | api.jlcpcb.com (login), signature spec at `/docs/api-request-signature` | verified |
| Host of the calls | `https://open.jlcpcb.com`, all `POST /overseas/openapi/…` | verified (several clients that call it live) |
| Access | two tiers: pricing, and ordering (upload, pricing, PCB and stencil orders, tracking). Ordering is for "partner companies" with "a certain monthly order volume"; "not all applications will be approved" | verified (help article "JLCPCB Online API available now") |
| Business types | per app, applied for one by one (PCB, Components, 3D printing), each approved by JLCPCB | reported |
| Auth | AppID, AccessKey, SecretKey; HMAC-SHA256 over `METHOD\nURI\nTIMESTAMP\nNONCE\nBODY\n`; header `Authorization: <scheme> appid=…,accesskey=…,timestamp=…,nonce=…,signature=…`; uploads with `Content-MD5` | verified in code; scheme (`JOP` or `JOP-HMAC-SHA256`) and signature encoding (Base64 or hex) differ between clients – reported per API |
| SDK | Java only, from the console | verified |
| Rate limits | 429 documented, no number; IP whitelist possible | reported |

Endpoints (from five independent clients):

| Endpoint | Does | Note |
| --- | --- | --- |
| `pcb/uploadGerber` | multipart `meta` + `file` → `fileKey` | |
| `pcb/audit/get` | JLCPCB's pre-review (DFM) of the upload | |
| `pcb/calculate` | quote: `orderType` (1 PCB, 2 PCB + stencil, 3 stencil), `pcbParam`, `fileKey`, country, postcode, shipping method, delivery date → PCB cost, shipping, lead time | |
| `pcb/create` | places the order (addresses, `pcbParam`) | in the SDK, nobody has called it live |
| `pcb/order/detail` | order by `batchNum`: costs, address, tracking | |
| `pcb/wip/get` | production progress | |
| `component/getComponentDetailByCode` | up to 1000 LCSC numbers at once | replaces the per-part search of `edakit stock` |
| `component/getComponentInfos`, `getComponentLibraryList`, `getPrivateComponentLibrary` | catalogue, private library | |

`pcbParam` (`PcbOrderCraftData`) has at least `layer`, `width`, `length`, `cuprumThickness`. The fields for thickness,
mask colour, silkscreen, finish, mark and remark are not yet seen (step 0).

**There is no assembly.** Every "SMT" of the official API is the SMD stencil; `calculate` takes only orderType 1–3.
No BOM, no CPL, no Economic or Standard PCBA, no assembly side, no tooling holes, no assembly fees, no part prices
(reported by one client that lists the whole surface; it agrees with the help article, which names PCB and stencil
orders only). edakit's boards are assembled, so the official API covers a part of the order.

### The web shop's own calls

| Call | Does | Auth | Basis |
| --- | --- | --- | --- |
| `jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList` | catalogue search | none (403 when too fast) | verified – edakit uses it (`release/fab.py` `JLC_SEARCH`) |
| `cart.jlcpcb.com/api/overseas-core-platform/file/uploadGerber` | Gerber upload → `fileId` | none | verified in code (overprint) |
| `cart.jlcpcb.com/quote/?homeUploadNum=<fileId>` | opens the quote form with that upload | browser | verified in code |
| `…/overseas-pcb-order/v1/smtOrder/getSmtOrderDetail` | an assembly order with its costs | session | verified in code (KiCad-Lib) |
| `…/overseas-core-platform/orderCenter/invoiceOrder` | invoices | session | verified in code |

Logged-in calls need the session cookie (`JLCPCB_SESSION_ID`, httpOnly), the header `x-xsrf-token` (cookie
`XSRF-TOKEN`, about 30 min) and a header `secretkey` from `/api/overseas-core-platform/secret/update` (about 30 min).
For pricing a PCBA, for BOM and CPL upload and for the cart no public code was found – that would be reverse
engineering in the browser's DevTools, and it breaks when the shop changes.

### EasyEDA Pro

`eda.pcb_ManufactureData.placePcbOrder(interactive, ignoreWarning)` builds the Gerber on EasyEDA's server and opens
JLCPCB's order page. Its parameters have no effect, and it returns nothing about the order (reported). It would upload
EasyEDA's export, not the run the gate checked – edakit does not use it.

### What follows

The official API covers the PCB but not the assembly, and the shop has no interface for BOM, CPL, the assembly form or
its price. EasyEDA's order button sends EasyEDA's own export, not the gate's files (its BOM is edakit's from the
graph, `release/fab.py` `bom_rows`; its CPL is converted and checked by F-3). Every complete automation therefore
works the shop's web pages. The user decided on 2026-10-30: **Claude works the pages in the owner's browser (Claude in
Chrome); edakit prepares the order and checks what Claude brings back.** A fixed browser script (Playwright with
selectors) and the session calls are not built: both break with every change of the shop, and the session calls need
copied cookies.

## Design

Two halves with a file between them. edakit is deterministic and knows the release; Claude reads and fills pages that
change. Nothing Claude reads counts until edakit has checked it.

```text
 edakit jlc prepare ──► order_job.json ──► skill jlc-order (Claude in Chrome) ──► quote.json + page text
 (verify, M-6, form)      (one board)       upload, fill, read back, quote           │
                                                                                     ▼
                                                     edakit jlc check (J-1 to J-6: form = job, BOM, quote, files)
                                                                                     ▼
                                                     agent regulatory-reviewer on the order ──► jlc/regulatory.md
                                                                                     ▼
                                                     J-7, then Save to Cart – nothing further
 owner: M-2, order, pay ──► skill jlc-order: order page ──► actual.json + page text ──► edakit jlc actual
                                                                       (actual vs quote vs cost, fee table)
```

All files of an order live next to the upload files of the released run, `<run>/fab/<board>/jlc/`, so a quote and
a real cost belong to one fab hash.

### 1. The form as data

`order_sheet.py` already computes every field of the form; today it prints them as Markdown. `order_sheet.form(…)`
returns them as one list of fields, and `order.md` is printed from it – same output as today. A field is
`{name, value, section}` with JLCPCB's label (`"Mark on PCB"`, `"PCB Color"`, `"PCBA Type"`, …) and the value as the
form shows it (`"Order Number (Specify Position)"`, `"Green"`, `"Economic"`):

| From | Field (section) |
| --- | --- |
| layers of the run, Gerber outline | Layers, Dimensions (PCB) |
| `[project] quantity` | PCB Qty (PCB) |
| `thickness_mm`, `[order] mask`, `silkscreen`, `finish`, `mark`, `remark` | PCB Thickness, PCB Color, Silkscreen, Surface Finish, Mark on PCB, Remark (PCB) |
| `[release] assembly.pcba`, sides | PCBA Type, Assembly Side (PCBA) |
| `[tooling]` | Tooling holes: Added by Customer (PCBA) |
| `[project] quantity` | PCBA Qty (PCBA) |
| stock snapshot, MSL ≥ 5 | Bake Components (PCBA) |

Fields that `order.md` does not set today (copper weight, via covering, delivery format) get their value from
`[order]` once a project sets them, else the form's default, named as such – the skill sets every field of the job
and leaves none at a default it was not given.

### 2. `edakit jlc prepare [--board B]`

1. Takes the current release (`edakit release current`); a board not in it, or no release, stops.
2. `release verify` on the three upload files of the board (the same function); a mismatch stops.
3. M-6 is signed for the circuit hash of that run – the release gate demands it, `prepare` checks it once more, since
   the order is placed against the run and not against the working tree; otherwise it stops.
4. Writes `jlc/order_job.json`: run, fab hash, circuit hash, `purpose` of the graph, board, the absolute paths of `gerber_<b>.zip`, `bom_<b>.csv`,
   `cpl_<b>.csv`, the fields of 1., the expected BOM (LCSC number → designators, from `bom_<b>.csv`), the estimate of
   `edakit cost` for the board (total and lines), the `compliance` of each BOM part from its parts entry, and the
   SHA-256 of each upload file.
5. Prints the job as the skill reads it.

### 3. Skill `jlc-order`

A skill of the plugin, run by Claude with the Claude in Chrome tools in a tab of the owner's browser, logged in by the
owner. It reads `order_job.json` and nothing else of the project.

1. **Quote page.** Open jlcpcb.com's quote form in a new tab. Upload `gerber_<b>.zip` from the job's path.
2. **PCB fields.** Set each field of section PCB. After each, read the page and note what it shows.
3. **PCBA.** Switch on assembly, set the fields of section PCBA, upload `bom_<b>.csv` and `cpl_<b>.csv`.
4. **BOM tool.** Read the matched parts: LCSC number and designators per line, and every line JLCPCB marks
   (not matched, out of stock, replaced, "Standard Only").
5. **Quote.** Read every price line JLCPCB shows (PCB, each assembly fee, parts, shipping, total, currency) and the
   lead time.
6. **Check.** Write `jlc/quote.json` (fields as read, BOM as read, price lines) and `jlc/quote_page.txt` (the page
   text of the form, the BOM tool and the quote, as read). Run `edakit jlc check`. A failed J-1 to J-6 stops here.
7. **Regulatory review.** Start the agent regulatory-reviewer on the order (5.) and write its result, unchanged, to
   `jlc/regulatory.md`. Run `edakit jlc check` again for J-7.
8. **Cart.** Only when J-1 to J-7 passed: press "Save to Cart", read the cart line back (board, quantity, price) into
   `quote.json`, and stop. Otherwise stop on the form, nothing in the cart, and name the findings. Tell the owner the
   result and that M-2 in the assembly preview, ordering and paying are theirs.

**Never** (user's decision 2026-10-30): the skill does not press "Order", "Buy", "Checkout", "Pay", "Submit order" or
any button that places or pays an order, does not enter or confirm an address, a payment method or a coupon, and does
not change or delete what is already in the cart. When the next step of a page would be one of these, it stops.

Rules of the skill: one field at a time, read back after each; a field it cannot find, or a value the form does not
offer, stops with the field's name – no guessing, no nearby option; a dialog the job does not explain (DFM warning,
part replacement) is reported, not answered.

### 4. `edakit jlc check`

What Claude brought is checked against the job and against the page text:

- **J-1 form = job:** every field of the job read back with its value (case and blanks ignored); a missing or other
  value fails with the field's name. This is the check that would have caught "Remove Mark".
- **J-2 BOM = release:** the BOM tool's lines are those of `bom_<b>.csv` – same LCSC numbers, same designators; a line
  JLCPCB marked or replaced fails.
- **J-3 quote vs estimate:** each price line against `edakit cost`'s line, the total against `[cost] budget`; a
  difference above `[jlc] tolerance` warns with both values.
- **J-4 read, not made up:** every value of `quote.json` occurs in `quote_page.txt`. It does not prove the page, but a
  value Claude did not read from it fails.
- **J-5 same files:** the SHA-256 of the upload files is still that of the job and of the manifest.
- **J-6 order and purpose:** what a program can decide of 5. – a finish with lead (`HASL(with lead)` as the form
  reads back) fails for `gift` and `sale` and warns for `private`; a part in the BOM tool without `compliance.rohs`
  in its parts entry fails for `sale` and warns otherwise; the PCBA quantity is `[project] quantity`.
- **J-7 regulatory review of this order:** `jlc/regulatory.md` exists, names the SHA-256 of `order_job.json` and
  `quote.json` as they are now, and ends with "Order: OK"; a finding **block** fails, an **important** one fails
  until the owner has accepted it as a numbered decision in the decision log (as for M-6, handbook 15.4).

The result goes to `jlc/check.md`, and the PCB line of the quote becomes `[cost] pcb_price` for this fab hash
(`edakit cost` takes it as long as the hash is the same).

### 5. The regulatory review of the order

M-6 reviews the circuit: graph with its purpose, parts database, requirements (scope `circuit`, handbook 15.4). The
order adds what M-6 never saw, and what may change between the release and the cart:

| What | Why it matters | Where it comes from |
| --- | --- | --- |
| the parts JLCPCB actually places – a line matched to another number, a part it replaces or sources elsewhere | another part, another RoHS status and SVHC statement (REACH Art. 33 for `gift` and `sale`) | BOM tool, `quote.json` |
| the surface finish and the other settings of `[order]` | they are in the layout and fab hash, not in the circuit hash; lead HASL is lead in the product (RoHS; lead is an SVHC) | form as read back |
| the quantity against `purpose` | 50 boards for `private` asks whether the purpose is still true – a new purpose is a new M-6 | job, cart |
| the import | for `sale`, ordering from China makes the owner the manufacturer or importer of the boards – name and address on the product, the technical file, registrations before the first sale (handbook 15.2) | `purpose`, shipping country |
| items in the order that bring duties of their own – a cell, a power supply in the BOM | batteries regulation, the supply's own conformity, transport of lithium cells | BOM tool |
| the order's own declarations, if JLCPCB's form asks for any (customs description and value) | what the shipment is declared as; not checked whether the form asks (step 0) | form as read |

The agent regulatory-reviewer gets a section "At the order": it reads `order_job.json`, `quote.json`,
`quote_page.txt`, `jlc/check.md` and the M-6 result for the run's circuit hash, and looks only at the difference –
what the order adds or changes against what M-6 signed. It changes no file, as for M-6; its result, which the skill
writes to `jlc/regulatory.md`, has numbered findings graded as for M-6 (block, important, note, each with rule and
source), the SHA-256 of the job and the quote it reviewed, and the last line "Order: OK" or "Order: not OK". A
difference that changes the circuit – another part, another purpose – is not settled at the order: it is a finding
**block** ("new M-6 needed"), and the order waits for a new release.

It is no sign-off in `signoff.json` – the release and its hashes stay as they are – but J-7 makes the cart wait for
it, and a new quote (another price, another BOM match) needs a new review, because its hash changes.

### 6. Real cost: `edakit jlc actual`

After the owner has paid, the skill opens the order in the order history and writes `jlc/actual.json` and
`jlc/actual_page.txt` as in 3.5–3.6, plus the order number. Alternatively the owner saves the order page or the
invoice (HTML or PDF) and passes it with `--from FILE`; then Claude reads that file instead of the tab.
`edakit jlc actual` checks J-4 on it, prints estimate, quote and actual line by line with the difference, and with
`--fees` writes a proposal for `edakit/fees/jlcpcb.json`: each changed value with the order as its `source` and the
order's date. The proposal is reviewed and committed like any other change of the table. The gate protocol of the run
lists the three totals once `actual.json` exists.

### 7. Configuration

```toml
[jlc]
country = "DE"         # shipping, as the form names it
shipping = "DHL Express"
tolerance = 0.10       # $ per price line before J-3 warns
```

No credentials anywhere: the owner is logged in in their browser, edakit never sees the account. `quote.json` and
`actual.json` hold prices and the order number, no address.

### 8. The official API later

If JLCPCB grants API access, `edakit jlc quote --api` uploads the Gerber (`pcb/uploadGerber`), runs its pre-review
(`pcb/audit/get`) and prices the PCB (`pcb/calculate`) without a browser, and `edakit stock` reads all parts in one
call (`component/getComponentDetailByCode`). The assembly still goes through the skill. Keys from `JLCPCB_APP_ID`,
`JLCPCB_ACCESS_KEY`, `JLCPCB_SECRET_KEY` or the keyring. The user asks JLCPCB for API access and for an assembly
interface for partners in parallel.

### 9. What stays

- **The regulatory review sees every order.** No cart without J-7 on the current job and quote; M-6 is not replaced
  by it, only completed for what the order adds.
- **Ordering and paying are the owner's, and so is M-2.** The skill ends with "Save to Cart"; no command, skill or
  API path places or pays an order – `pcb/create` is never called.
- **No key, no change.** Without `[jlc]` and without an `order_job.json`, nothing runs; the gate result, the hashes and
  the sign-offs do not change. Everything under `jlc/` is output of an order, not input of a hash.
- **Tests without the network.** `prepare`, `check` and `actual` are tested on recorded `quote.json`, page texts and
  a saved invoice. The skill is tried live only on the owner's request, up to the cart, nothing ordered.
- **Where it runs.** Claude in Chrome needs the owner's Chrome with the extension – on the owner's machine, or a cloud
  session linked to it. Without it the skill prints the job as a checklist and `edakit jlc check` checks a
  `quote.json` the owner fills by hand.

## Order of work

| Step | What | Needs |
| --- | --- | --- |
| 0 | Probe in the owner's browser, nothing ordered: can Claude in Chrome put a local file into the upload fields (Gerber, BOM, CPL)? Do the form's fields read back as text? Record the page texts of one quote and one past order as test data. Read JLCPCB's terms on automated use | owner's Chrome with Claude in Chrome |
| 1 | `order_sheet.form`: the form as fields, `order.md` printed from it – no change of output | – |
| 2 | `edakit jlc actual --from FILE` on a saved order page or invoice; three columns; fee table proposal | step 1, a saved page from step 0 |
| 3 | `edakit jlc prepare` and `edakit jlc check` (J-1 to J-7) on recorded data | step 1 |
| 3b | Agent regulatory-reviewer: section "At the order", `jlc/regulatory.md`; tried on recorded data with a replaced part and lead HASL | step 3 |
| 4 | Skill `jlc-order`, live up to the cart | steps 0, 3, 3b |
| 5 | Official API (8.), if granted | JLCPCB |

If step 0 shows that the extension cannot upload a local file, the owner drops the three files into the upload fields
when the skill asks for them, and the skill carries on from there; everything else stays.

## Open decisions

1. **Terms of use:** read in step 0. If JLCPCB forbids automated use of the shop, the skill only reads (fields,
   BOM tool, quote) after the owner has filled the form, and J-1 to J-7 still check it.
2. **Fee table:** real cost as a proposal to review (as above), or committed automatically from the owner's own
   orders?

## Sources

- JLCPCB, "JLCPCB Online API available now": https://jlcpcb.com/help/article/jlcpcb-online-api-available-now
- JLCPCB API portal: https://api.jlcpcb.com/docs/start, https://api.jlcpcb.com/docs/api-request-signature
- Clients of the official API: i2cjak/jlcpcb_api, shpaw415/community_jlcpcb_api_client, holla2040/hendley
  (`docs/api-reference.md`), NeilHanlon/swamp-jlcpcb, Eyalm321/jlcpcb-mcp, rjwalters/kicad-tools
- Web shop calls: Bouni/kicad-jlcpcb-tools (`common/jlcapi.py`), yaqwsx/jlcparts, Dirdmaster/overprint
  (`apps/web/server/utils/jlcUpload.ts`), mszkowalik/KiCad-Lib (`docs/jlcpcb-web-api.md`)
- EasyEDA Pro: https://prodocs.easyeda.com/en/pcb/order-order-pcb, easyeda/easyeda-api-skill
  (`references/classes/PCB_ManufactureData.md`)
