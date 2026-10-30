# Ordering at the manufacturer

Status 2026-10-30: proposal; the path is decided (Claude in Chrome, up to the cart; JLCPCB, Eurocircuits and AISLER;
ODB++ from EasyEDA Pro – "What follows"). Nothing is built, and no call has been made live. The findings come from
JLCPCB's help article on its online API, search summaries of the developer portal (api.jlcpcb.com, behind a login),
the code of open-source clients of the official API and of the web shop, search results on the European makers, and
EasyEDA Pro's documentation and extension API. The makers' sites were not reachable from the session that wrote this,
so every finding is marked as **verified** (in a source or in code that calls it) or **reported** (one secondary
source), and step 0 checks them.

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

## European manufacturers

The user wants a choice beside JLCPCB (2026-10-30). Checked: European makers that assemble small runs (1–100
boards). The sites could not be opened from the session; the findings come from search results with their URLs, and
step 0 checks them on the sites.

| | Eurocircuits (BE) | AISLER (NL/DE) | Beta LAYOUT / PCB-POOL (DE) |
| --- | --- | --- | --- |
| Assembly | PCB Proto: 1–5 boards, 2 or 4 layers, about 6 working days; larger runs 10 or 12 days | "Amazing Assembly", about 6 working days | yes, with its own parts stock |
| Parts | Eurocircuits buys them; what it cannot source, the customer supplies | AISLER buys at Mouser, Digi-Key, Farnell, LCSC, TME and others; customer parts on request | own stock first, then distributors ("MAGIC-BOM") |
| Files for assembly | Gerber, BOM (CSV or Excel, **MPN** required, designators), pick-and-place | **no assembly from Gerber**: ODB++ or native design files | Gerber X2 or native files |
| Interface | none published; quote, cart and orders only in the browser account | none published; push plugins for KiCad and DipTrace, upload keys per request (third-party report) | `api.beta-layout.com` answers, no documentation (third-party report) |
| RoHS, REACH | not found, on request (assumed) | signed RoHS declaration (2026-02-25) and REACH statement published | not found |

Ruled out: Multi-CB (an order API, but bare boards only), Würth WEdirekt and LeitOn (no online assembly).

**What a maker in the EU changes.** Bought inside the EU there is no customs clearance and no import VAT, and the buyer
is not the importer of the boards; the maker carries its own duties for what it supplies (general EU law, not read on
the makers' pages). Parts the owner supplies from outside the EU are imported by the owner.

**What edakit lacks for them.**

- **MPN in the BOM.** Eurocircuits matches by manufacturer part number, not by LCSC number. The parts entries hold
  `mpn` and `manufacturer` (P-4 compares the MPN with JLCPCB's already); a BOM for Eurocircuits takes them as columns.
- **ODB++ for AISLER.** No open-source tool turns Gerber, BOM and pick-and-place into ODB++ (GitHub search: no such
  converter; gerbonara, pygerber and pcb-tools write no ODB++; OdbDesign and ODBPy only read). KiCad 9 and Horizon
  EDA write ODB++, but only from their own boards. EasyEDA Pro exports it itself ("ODB++ v8.0", File > Export >
  ODB++), and its extension API has the call:
  `PCB_ManufactureData.getOpenDatabaseDoublePlusFile(fileName?, unit?, otherData?, layers?, objects?)` (BETA) →
  `File`, with drill holes, drill table and flying probe file as `otherData`. The bridge of easyeda-mcp-pro 1.4.0 does
  not call it (its bundle calls `getGerberFile`, `getPickAndPlaceFile`, `getNetlistFile`, `getPdfFile`,
  `getDsnFile`, `getManufactureData`); edakit's bridge patch can add it as it added the schematic PDF. Whether the
  export holds the component layers (`comp_+_top`, packages, pins, part numbers) the documentation does not say –
  step 0b. AISLER has a guide "Export ODB++ from EasyEDA", which points to yes.

### Terms of use (state 2026-10-30)

Searched, not read: the documents were not reachable from the session (network policy), so what follows are search
snippets; step 0 reads the documents themselves. Not legal advice.

| Maker | Documents | On automated use | Assessment |
| --- | --- | --- | --- |
| JLCPCB | Terms & Conditions https://jlcpcb.com/help/article/terms-&-conditions (JiaLiChuang (HongKong) Co., Limited), API notice; parts sales contract under Hong Kong law | no clause found; the sister company EasyEDA forbids "any robot, spider, scraper, crawler, script or other automated means" unless authorised in writing (second-hand, an issue of rjwalters/kicad-tools); automation is meant to go through the gated API | not settled; the highest risk of the three |
| Eurocircuits | Terms of Use https://www.eurocircuits.com/termofuse/, Terms of Sales (revision 2025-12-01), Belgian law likely | the tools "are free to use by anyone who wants to use them in a fair way"; to avoid unfair use it may "limit the number of calculations that can be added to the shopping basket" | not addressed; fair use for ordering, which an order of one's own design is |
| AISLER | Terms and Conditions https://aisler.net/en-US/terms, Dutch law | none found in the shop terms; the forum's terms (Discourse template) forbid "a web crawler, browser add-on, or other program that is not a web browser" – for the forum only | not addressed for the shop |

What speaks for the use: the owner's own account and own designs, one order at a time at a human pace, no catalogue
data collected, nothing ordered or paid. What speaks against it: a literal "any automated means" clause would still
cover a browser extension. If step 0 finds such a clause, open decision 1 applies – the skill only reads after the
owner has filled the form – or the maker is asked for written consent.

## What follows

The official API covers the PCB but not the assembly, and the shop has no interface for BOM, CPL, the assembly form or
its price. EasyEDA's order button sends EasyEDA's own export, not the gate's files (its BOM is edakit's from the
graph, `release/fab.py` `bom_rows`; its CPL is converted and checked by F-3). The European makers publish no
interface either. Every complete automation therefore works the shop's web pages. The user decided on 2026-10-30:

1. **Claude works the pages in the owner's browser (Claude in Chrome); edakit prepares the order and checks what Claude
   brings back.** A fixed browser script (Playwright with selectors) and session calls are not built: both break with
   every change of a shop, and session calls need copied cookies.
2. **Up to "Save to Cart", never further.**
3. **The regulatory reviewer looks at every order.**
4. **A choice of maker:** JLCPCB, Eurocircuits, AISLER – one interface, a profile per maker.
5. **ODB++ from EasyEDA Pro through the patched bridge**, checked by the gate against the released files.

## Design

Two halves with a file between them. edakit is deterministic and knows the release; Claude reads and fills pages that
change. Nothing Claude reads counts until edakit has checked it.

```text
 edakit cart prepare ──► job.json ──► skill cart (Claude in Chrome) ──► quote.json + page text
 (verify, M-6, form,      (board,       upload, fill, read back, quote         │
  maker's files)           maker)                                              ▼
                                         edakit cart check (K-1 to K-6: form = job, BOM, quote, files, purpose)
                                                                               ▼
                                         agent regulatory-reviewer on the order ──► regulatory.md
                                                                               ▼
                                         K-7, then the maker's cart button – nothing further
 owner: M-2, order, pay ──► skill cart: order page ──► actual.json + page text ──► edakit cart actual
                                                                (actual vs quote vs cost, fee table)
```

All files of an order live next to the upload files of the released run, `<run>/fab/<board>/cart/<maker>/`, so a
quote and a real cost belong to one fab hash and one maker.

### 1. The maker's profile

One data file per maker, `edakit/makers/<maker>.toml`, shipped with edakit; a project may name its own in `[cart]`.
It holds no code:

| Key | Holds | JLCPCB | Eurocircuits | AISLER |
| --- | --- | --- | --- | --- |
| `start` | the page the skill opens | quote form | PCB Proto calculator | project upload |
| `files` | what is uploaded | Gerber, BOM, CPL | Gerber, BOM with MPN, CPL | ODB++ |
| `bom` | BOM columns and the key parts are matched by | Comment, Designator, Footprint, LCSC Part # – LCSC | Designator, Quantity, Manufacturer, MPN, Comment – MPN | – (in the ODB++) |
| `fields` | label of each form field and the form's word for each value of `[order]` | "Mark on PCB": `specify` → "Order Number (Specify Position)" | step 0 | step 0 |
| `cart` | the one button the skill may press | "Save to Cart" | step 0 ("add to basket") | step 0 |
| `never` | buttons and fields it must not touch | Order, Buy, Checkout, Pay, Submit order; address, payment, coupon | the same in the maker's words | the same |
| `country`, `currency` | where the maker ships from, its currency | CN, USD | BE, EUR | DE/NL, EUR |
| `fees` | the fee table `edakit cost` prices with | `edakit/fees/jlcpcb.json` | none yet | none yet |

`fields` and `cart` are what the skill looks for, and the words step 0 records on each site; when a site changes, the
profile changes – a line of text, reviewed like any other.

### 2. The form as data

`order_sheet.py` already computes every field of the form; today it prints them as Markdown. `order_sheet.form(…)`
returns them as one list of fields in edakit's words – `{name, value, section}` – and `order.md` is printed from it,
same output as today. The profile maps each to the maker's label and value:

| From | Field (section) |
| --- | --- |
| layers of the run, Gerber outline | layers, dimensions (PCB) |
| `[project] quantity` | quantity (PCB) |
| `thickness_mm`, `[order] mask`, `silkscreen`, `finish`, `mark`, `remark` | thickness, mask colour, silkscreen colour, finish, mark, remark (PCB) |
| `[release] assembly.pcba`, sides | assembly class, assembly side (PCBA) |
| `[tooling]` | tooling holes by the customer (PCBA) |
| `[project] quantity` | assembled quantity (PCBA) |
| stock snapshot, MSL ≥ 5 | bake (PCBA) |

A field the maker does not have (JLCPCB's Economic or Standard at Eurocircuits, the order-number mark in Europe) is
`null` in its profile and left out; a field of the job the profile cannot map stops `prepare` with its name. Fields
`order.md` does not set today (copper weight, via covering) get their value from `[order]` once a project sets them,
else the form's default, named as such – the skill sets every field of the job and none it was not given.

### 3. The maker's files from the gate

The gate writes the files of every maker in `[cart] makers` into the run, next to the ones it writes today, and
`release verify` and the manifest cover them:

- **BOM with MPN** (`bom_<b>_mpn.csv`, when a maker's `bom` asks for it): the rows of F-1 with `manufacturer` and `mpn`
  of the parts entry. **F-7** fails a BOM part whose entry has no `mpn` or `manufacturer`.
- **ODB++** (`odb_<b>.zip`, when a maker's `files` asks for it): `edakit gate --easyeda` exports it with the Gerber,
  through the patched bridge (`getOpenDatabaseDoublePlusFile`, millimetres, plated and non-plated holes), and
  `edakit export` too. **F-8** checks it against the released files, without trusting EasyEDA:
  - every copper, mask and silkscreen layer of the ODB++, rasterised as L-2 does (`gerber.RES`), XOR the Gerber layer
    of the same run: no spot above `SPOT_MM2`;
  - the drill holes = the drill files (position to 1 µm, diameter, plated or not);
  - the profile = the Gerber outline;
  - the components (`comp_+_top`, `comp_+_bot`): every BOM part exactly once, position, rotation and side as in the
    CPL, part number as in the BOM – and no part with `bom: false` among them unless the maker is told to leave it;
  - the nets of the pads as in the graph, as `gerber.py` already maps pads to nets.
  F-8 needs a small ODB++ reader in edakit (`edakit/odb.py`: matrix, features with the standard symbols, surfaces,
  drill, components); reading is far smaller than writing, and it is tested on the export of step 0b.

The fab hash does not change with them: F-8 holds the ODB++ to the Gerber and CPL that are in the hash, and the BOM
with MPN adds nothing the manufacturer builds from beyond the parts entries already in scope `circuit`. A project
without `[cart]` gets no new file and no new check.

### 4. `edakit cart prepare [--board B] [--maker M]`

1. Takes the current release (`edakit release current`); a board not in it, or no release, stops.
2. `release verify` on the maker's upload files of the board (the same function); a mismatch stops.
3. M-6 is signed for the circuit hash of that run – the release gate demands it, `prepare` checks it once more, since
   the order is placed against the run and not against the working tree; otherwise it stops.
4. Writes `cart/<maker>/job.json`: run, fab hash, circuit hash, `purpose` of the graph, board, maker and its profile,
   the absolute paths and SHA-256 of the upload files, the fields of 2. in the maker's words, the expected BOM (LCSC
   number or MPN → designators), the estimate of `edakit cost` for the board when the maker has a fee table, and the
   `compliance` of each BOM part from its parts entry.
5. Prints the job as the skill reads it.

`--maker` defaults to `[cart] maker`.

### 5. Skill `cart`

A skill of the plugin, run by Claude with the Claude in Chrome tools in a tab of the owner's browser, logged in by the
owner. It reads `job.json` and nothing else of the project.

1. **Start.** Open the profile's `start` page in a new tab. Upload the job's files.
2. **Board fields.** Set each field of section PCB. After each, read the page and note what it shows.
3. **Assembly.** Switch on assembly, set the fields of section PCBA, upload BOM and pick-and-place where the maker
   takes them separately.
4. **Parts.** Read the maker's matching: part number and designators per line, and every line it marks (not matched,
   out of stock, replaced, another manufacturer, "Standard Only").
5. **Quote.** Read every price line the maker shows (board, each assembly fee, parts, shipping, total, currency) and
   the lead time.
6. **Check.** Write `quote.json` (fields as read, parts as read, price lines) and `quote_page.txt` (the page text of
   the form, the matching and the quote, as read). Run `edakit cart check`. A failed K-1 to K-6 stops here.
7. **Regulatory review.** Start the agent regulatory-reviewer on the order (7.) and write its result, unchanged, to
   `regulatory.md`. Run `edakit cart check` again for K-7.
8. **Cart.** Only when K-1 to K-7 passed: press the profile's `cart` button, read the cart line back (board,
   quantity, price) into `quote.json`, and stop. Otherwise stop on the form, nothing in the cart, and name the
   findings. Tell the owner the result and that M-2 at the maker, ordering and paying are theirs.

**Never** (user's decision 2026-10-30): the skill does not press "Order", "Buy", "Checkout", "Pay", "Submit order",
the profile's `never` or any button that places or pays an order, does not enter or confirm an address, a payment
method or a coupon, and does not change or delete what is already in the cart. When the next step of a page would be
one of these, it stops.

Rules of the skill: one field at a time, read back after each; a field it cannot find, or a value the form does not
offer, stops with the field's name – no guessing, no nearby option; a dialog the job does not explain (DFM warning,
part replacement) is reported, not answered.

### 6. `edakit cart check`

What Claude brought is checked against the job and against the page text:

- **K-1 form = job:** every field of the job read back with its value (case and blanks ignored); a missing or other
  value fails with the field's name. This is the check that would have caught "Remove Mark".
- **K-2 parts = release:** the maker's lines are those of the job's BOM – same part numbers, same designators; a line
  the maker marked, replaced or matched to another manufacturer fails.
- **K-3 quote vs estimate:** each price line against `edakit cost`'s line, the total against `[cost] budget`; a
  difference above `[cart] tolerance` warns with both values. A maker without a fee table: the total against the
  budget only.
- **K-4 read, not made up:** every value of `quote.json` occurs in `quote_page.txt`. It does not prove the page, but a
  value Claude did not read from it fails.
- **K-5 same files:** the SHA-256 of the upload files is still that of the job and of the manifest.
- **K-6 order and purpose:** what a program can decide of 7. – a finish with lead fails for `gift` and `sale` and
  warns for `private`; a part in the maker's matching without `compliance.rohs` in its parts entry fails for `sale`
  and warns otherwise; the assembled quantity is `[project] quantity`.
- **K-7 regulatory review of this order:** `regulatory.md` exists, names the SHA-256 of `job.json` and `quote.json`
  as they are now, and ends with "Order: OK"; a finding **block** fails, an **important** one fails until the owner
  has accepted it as a numbered decision in the decision log (as for M-6, handbook 15.4).

The result goes to `check.md`. With JLCPCB the board line of the quote becomes `[cost] pcb_price` for this fab hash
(`edakit cost` takes it as long as the hash is the same).

### 7. The regulatory review of the order

M-6 reviews the circuit: graph with its purpose, parts database, requirements (scope `circuit`, handbook 15.4). The
order adds what M-6 never saw, and what may change between the release and the cart:

| What | Why it matters | Where it comes from |
| --- | --- | --- |
| the parts the maker actually places – matched to another number or manufacturer, replaced, sourced elsewhere | another part, another RoHS status and SVHC statement (REACH Art. 33 for `gift` and `sale`) | the maker's matching, `quote.json` |
| the surface finish and the other settings of `[order]` | in the layout and fab hash, not in the circuit hash; lead HASL is lead in the product (RoHS; lead is an SVHC) | form as read back |
| the quantity against `purpose` | 50 boards for `private` asks whether the purpose is still true – a new purpose is a new M-6 | job, cart |
| where the maker sits | outside the EU (JLCPCB) and `sale`: the owner is the manufacturer or importer of the boards – name and address on the product, technical file, registrations before the first sale (handbook 15.2); inside the EU no import, the maker's declarations (AISLER's RoHS and REACH) are input | profile `country`, `purpose` |
| parts the owner supplies to the maker | imported by the owner when bought outside the EU | job |
| items that bring duties of their own – a cell, a power supply in the BOM | batteries regulation, the supply's own conformity, transport of lithium cells | the maker's matching |
| the order's own declarations, if the form asks for any (customs description and value) | what the shipment is declared as; whether a form asks is not known (step 0) | form as read |

The agent regulatory-reviewer gets a section "At the order": it reads `job.json`, `quote.json`, `quote_page.txt`,
`check.md` and the M-6 result for the run's circuit hash, and looks only at the difference – what the order adds or
changes against what M-6 signed. It changes no file, as for M-6; its result, which the skill writes to
`regulatory.md`, has numbered findings graded as for M-6 (block, important, note, each with rule and source), the
SHA-256 of the job and the quote it reviewed, and the last line "Order: OK" or "Order: not OK". A difference that
changes the circuit – another part, another purpose – is not settled at the order: it is a finding **block** ("new
M-6 needed"), and the order waits for a new release.

It is no sign-off in `signoff.json` – the release and its hashes stay as they are – but K-7 makes the cart wait for
it, and a new quote (another price, another match) needs a new review, because its hash changes.

### 8. Real cost: `edakit cart actual`

After the owner has paid, the skill opens the order in the maker's order history and writes `actual.json` and
`actual_page.txt` as in 5.5–5.6, plus the order number. Alternatively the owner saves the order page or the invoice
(HTML or PDF) and passes it with `--from FILE`; then Claude reads that file instead of the tab. `edakit cart actual`
checks K-4 on it, prints estimate, quote and actual line by line with the difference, and with `--fees` writes a
proposal for the maker's fee table: each changed value with the order as its `source` and the order's date. For a
maker without a table the first order starts one – its lines, dated, as `edakit/fees/<maker>.json`; `edakit cost`
prices with it once its model for that maker exists (the fee model of `cost.py` is JLCPCB's: Economic, Standard,
feeders, joints). Every proposal is reviewed and committed like any other change of a table. The gate protocol of the
run lists the three totals once `actual.json` exists.

### 9. Configuration

```toml
[cart]
maker = "jlcpcb"                     # the default of --maker
makers = ["jlcpcb", "eurocircuits"]  # the makers whose files the gate writes (3.); default [maker]
country = "DE"                       # shipping, as the forms name it
shipping = { jlcpcb = "DHL Express" }
tolerance = 0.10                     # per price line, in the maker's currency, before K-3 warns
```

No credentials anywhere: the owner is logged in in their browser, edakit never sees an account. `quote.json` and
`actual.json` hold prices and the order number, no address.

### 10. Interfaces later

- **JLCPCB's official API**, if granted: `edakit cart quote --api` uploads the Gerber (`pcb/uploadGerber`), runs its
  pre-review (`pcb/audit/get`) and prices the board (`pcb/calculate`) without a browser, and `edakit stock` reads all
  parts in one call (`component/getComponentDetailByCode`). The assembly still goes through the skill. Keys from
  `JLCPCB_APP_ID`, `JLCPCB_ACCESS_KEY`, `JLCPCB_SECRET_KEY` or the keyring.
- **AISLER's upload keys and Beta LAYOUT's API**, if they give them: the upload of the ODB++ without a browser.
- The user asks JLCPCB (API access, an assembly interface for partners), AISLER (upload key, ODB++ from EasyEDA for
  assembly) and Beta LAYOUT (API) in parallel to steps 1 to 3.

### 11. What stays

- **The regulatory review sees every order.** No cart without K-7 on the current job and quote; M-6 is not replaced
  by it, only completed for what the order adds.
- **Ordering and paying are the owner's, and so is M-2.** The skill ends with the maker's cart button; no command,
  skill or API path places or pays an order – `pcb/create` is never called.
- **No key, no change.** Without `[cart]` nothing runs, the gate writes no new file, and the gate result, the hashes
  and the sign-offs do not change. Everything under `cart/` is output of an order, not input of a hash.
- **Stock.** P-4 and `edakit stock` ask JLCPCB's catalogue; for another maker the stock is what its matching shows,
  checked by K-2.
- **Tests without the network.** `prepare`, `check`, `actual`, F-7 and F-8 are tested on recorded data: page texts,
  a saved invoice, the ODB++ of step 0b. The skill is tried live only on the owner's request, up to the cart, nothing
  ordered.
- **Where it runs.** Claude in Chrome needs the owner's Chrome with the extension – on the owner's machine, or a cloud
  session linked to it. Without it the skill prints the job as a checklist and `edakit cart check` checks a
  `quote.json` the owner fills by hand.

## Order of work

| Step | What | Needs |
| --- | --- | --- |
| 0 | Probe per maker in the owner's browser, nothing ordered: can Claude in Chrome put a local file into the upload fields? Do the fields read back as text? The labels, values and cart button for the profile; the page texts of one quote and one past order as test data. Read each maker's terms on automated use | owner's Chrome with Claude in Chrome |
| 0b | ODB++ export of a throwaway board under the EasyEDA claim (working agreement 18): through the bridge with a patched call, and by hand (File > Export > ODB++) for comparison. Does it hold `comp_+_top`/`comp_+_bot` with packages, pins and part numbers? | EasyEDA |
| 1 | `order_sheet.form`: the form as fields, `order.md` printed from it – no change of output | – |
| 2 | Maker profiles: `jlcpcb.toml` from today's knowledge, `eurocircuits.toml` and `aisler.toml` from step 0 | step 0 |
| 3 | `edakit cart actual --from FILE` on a saved order page or invoice; three columns; fee table proposal | steps 1, 2 |
| 4 | `edakit cart prepare` and `edakit cart check` (K-1 to K-7) on recorded data | steps 1, 2 |
| 4b | Agent regulatory-reviewer: section "At the order", `regulatory.md`; tried on recorded data with a replaced part, lead HASL, and a maker inside and outside the EU | step 4 |
| 5 | Skill `cart`, live up to the cart at JLCPCB | steps 0, 4, 4b |
| 6 | BOM with MPN and F-7; Eurocircuits live up to the basket | step 5 |
| 7 | Bridge patch for `getOpenDatabaseDoublePlusFile` (and the upstream issue, as for the schematic PDF), `edakit/odb.py`, F-8; AISLER live up to the cart | steps 0b, 5 |
| 8 | Interfaces of 10., where granted | the makers |

If step 0 shows that the extension cannot upload a local file, the owner drops the files into the upload fields
when the skill asks for them, and the skill carries on from there; everything else stays. If step 0b shows that
EasyEDA's ODB++ has no component layers, AISLER waits: then the choice is KiCad 9 as a converter (import of the
EasyEDA Pro project, `kicad-cli pcb export odb`, F-8 on its result) or none – a decision of its own.

## Open decisions

1. **Terms of use:** searched (above), read in step 0, per maker. Where a maker forbids automated use of its shop,
   the skill only reads (fields, matching, quote) after the owner has filled the form, and K-1 to K-7 still check it –
   or the owner asks the maker for written consent (JLCPCB first).
2. **Fee tables:** real cost as a proposal to review (as above), or committed automatically from the owner's own
   orders?
3. **Default maker** in new projects (`edakit new`): JLCPCB as today, or a maker in the EU?

## Sources

- JLCPCB, "JLCPCB Online API available now": https://jlcpcb.com/help/article/jlcpcb-online-api-available-now
- JLCPCB API portal: https://api.jlcpcb.com/docs/start, https://api.jlcpcb.com/docs/api-request-signature
- Clients of the official API: i2cjak/jlcpcb_api, shpaw415/community_jlcpcb_api_client, holla2040/hendley
  (`docs/api-reference.md`), NeilHanlon/swamp-jlcpcb, Eyalm321/jlcpcb-mcp, rjwalters/kicad-tools
- Web shop calls: Bouni/kicad-jlcpcb-tools (`common/jlcapi.py`), yaqwsx/jlcparts, Dirdmaster/overprint
  (`apps/web/server/utils/jlcUpload.ts`), mszkowalik/KiCad-Lib (`docs/jlcpcb-web-api.md`)
- EasyEDA Pro: https://prodocs.easyeda.com/en/pcb/order-order-pcb, https://prodocs.easyeda.com/en/pcb/export-odb-plus-plus,
  easyeda/easyeda-api-skill (`references/classes/PCB_ManufactureData.md`: `getOpenDatabaseDoublePlusFile`)
- Eurocircuits: https://www.eurocircuits.com/pcb-assembly-proto/, BOM requirements https://www.eurocircuits.com/?p=9450
- AISLER: https://aisler.net/en/products/assembly, https://aisler.net/en/products/supply, design tool support matrix
  https://community.aisler.net/t/pcb-design-tool-support-matrix/103, ODB++ https://community.aisler.net/t/introducing-odb-support/2459,
  EasyEDA guide https://community.aisler.net/t/export-odb-from-easyeda/3601, compliance
  https://community.aisler.net/t/clean-and-clear-compliance-rohs-reach-made-in-europe-documentation/85
- Beta LAYOUT: https://eu.beta-layout.com/pcb/assembly/; Multi-CB:
  https://www.multi-circuit-boards.eu/en/ems-provider-electronics-manufacturing.html
- ODB++ writers: KiCad 9 (`kicad-cli pcb export odb`), Horizon EDA 2.3+; readers: nam20485/OdbDesign, ulikoehler/ODBPy
