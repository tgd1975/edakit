# Ordering at JLCPCB through its interfaces

Status 2026-10-30: proposal. Nothing is built, and no call has been made live. The findings come from JLCPCB's help
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

**Goal:** from a released run, edakit uploads the files, sets every form field from `order.md`, reads the quote
(PCB, assembly fees, parts, shipping) back, compares it with `edakit cost`, and after the order reads the real cost
and keeps it with the run. **Not a goal:** paying. The order is placed and paid by the owner, after M-2 – a human
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

## Design

One module `edakit/jlc.py`, one command `edakit jlc`, three paths behind one interface. Each path reads the released
run (`<run>/fab/<board>/`: the upload files, `order.md`, `order.json`) and writes what it got into
the same folder, so a quote and a real cost belong to one fab hash.

```text
 release run ──► verify ──► upload ──► form ──► quote ──► (owner: M-2, pay) ──► actual cost
 (gate)          hash      Gerber,    order.json          quote.json                actual.json
                           BOM, CPL   → fields            vs edakit cost            vs quote, → fee table
```

### 1. The form as data: `jlc_form`

`order_sheet.py` already computes every field of the form; today it writes them as Markdown. `order_sheet.form(…)`
returns them as one dict, and `order.md` is printed from it, so the Markdown and every path below use the same values.
`jlc.py` maps the dict to each path's names:

| `[order]`, `[release]`, board file | form field | `pcbParam` (official) |
| --- | --- | --- |
| layers of the run, outline size | Layers, Dimensions | `layer`, `width`, `length` |
| `quantity` | PCB Qty | step 0 |
| `thickness_mm` | PCB Thickness | step 0 |
| `mask`, `silkscreen` | PCB Color, Silkscreen | step 0 |
| `finish` | Surface Finish | step 0 |
| `mark` | Mark on PCB | step 0 |
| `remark` | Remark | step 0 |
| copper weight (fee table `pcb.spec`) | Outer Copper Weight | `cuprumThickness` |
| `[release] assembly.pcba`, sides | PCBA Type, Assembly Side | – (no PCBA) |
| `[tooling]` | Tooling holes "Added by Customer" | – |
| bake from the stock snapshot | Bake Components | – |

A field the path cannot set is listed as "to set by hand" in the output – never left silently at the shop's default.

### 2. Paths

**A. Official API, PCB (`edakit jlc quote --api`).** For a board with `bought = true` or `bom = false` on every part,
and for the PCB share of every board:

1. `edakit release verify` on the files (the same function, not a subprocess); a mismatch stops.
2. `pcb/uploadGerber` → `fileKey`; `pcb/audit/get` – its findings next to the gate's waivers (8.4: "so nobody panics").
3. `pcb/calculate` with `pcbParam` from the form, `[jlc] country`, `postcode`, `shipping`.
4. `quote.json`: request, answer, fab hash, date. `edakit cost` takes its PCB price instead of the fee table's – an
   automatic `[cost] pcb_price`, valid as long as the fab hash is the same.

`pcb/create` is not called. A later step may add it behind `--order` for PCB-only boards, after the owner decides
(open decision 3); it would still stop before payment if the API allows that.

**B. Hand-off for PCBA (`edakit jlc cart`).** No interface exists, so edakit drives the owner's own browser:

1. verify as in A.
2. Playwright with a persistent profile under `~/.local/state/edakit/jlc-browser/` – the owner logs in there once, by
   hand; edakit never sees the password and stores no cookie in the project.
3. Upload Gerber, set every field of the form, upload BOM and CPL, confirm the part matching, stop at the assembly
   preview. Each field is read back after setting it and compared with the form; a difference stops with the field's
   name. This closes the "Remove Mark" kind of error.
4. Read the quote off the page – PCB, each assembly fee, parts, shipping, total – into `quote.json`, and the BOM tool's
   unmatched or changed parts into the same file.
5. Leave the browser open at the preview. M-2 and paying stay with the owner.

Selectors live in one table in `jlc.py` with the date they were last seen to work; `edakit doctor` runs a dry probe
(open the quote page, find each selector, upload nothing). When the shop changes, the path fails with the field that
was not found, and the owner orders as today.

**C. Session calls (not proposed).** The logged-in endpoints with cookie, XSRF and `secretkey` would avoid the browser,
but there is no public code for pricing or the cart, the tokens last 30 minutes, and an account automated with copied
cookies risks being blocked. Only `getSmtOrderDetail` is of use, for the real cost – and B can read the same from the
order page.

### 3. Real cost: `edakit jlc actual`

After the order (`--order <number>`, or found by the run's `fileKey`/`fileId`):

- PCB-only order: `pcb/order/detail` (official).
- PCBA order: the order page in the browser profile of B (assembly fees, parts, shipping, coupon as JLCPCB itemises
  them).

It writes `actual.json` next to `quote.json` and prints three columns: `edakit cost`, quote, actual, line by line,
with the difference. Lines whose estimate was off by more than `[jlc] tolerance` (default 0.10 $) are named. With
`--fees` it writes a proposal for `edakit/fees/jlcpcb.json`: each changed value with the order as its `source` and
the order's date – reviewed and committed like any other change of the table. The gate protocol of the run lists the
three totals once `actual.json` exists.

### 4. Configuration and secrets

```toml
[jlc]
path = "browser"            # "api" (PCB only), "browser", or "none" (default: edakit jlc does nothing)
country = "DE"
postcode = "…"
shipping = "DHL"            # the shop's name of the method
tolerance = 0.10            # $ per line before actual names it
```

API keys come from `JLCPCB_APP_ID`, `JLCPCB_ACCESS_KEY`, `JLCPCB_SECRET_KEY` or the system keyring – never from
`edakit.toml`, never into a run folder or a log. `quote.json` and `actual.json` hold prices and the order number, no
address (the address stays in the shop account).

### 5. What stays

- **M-2 and paying are the owner's.** No path presses "Pay". A path that would place an order needs an explicit flag
  per call and is a decision of its own (3).
- **No key, no change.** Without `[jlc]` nothing runs, and the gate result, hashes and sign-offs do not change.
  `quote.json` and `actual.json` are outputs of a run, not inputs of a hash.
- **Tests without the network.** Recorded answers of the API (signature checked against the spec's example) and a
  saved quote page for the selectors. A live test only on the owner's request, with a throwaway upload and nothing
  ordered.
- **Load.** One call per command and part; the API path and the catalogue search back off on 429 and 403 (the
  catalogue search does not today – it gets that with step 5).

## Order of work

| Step | What | Needs |
| --- | --- | --- |
| 0 | Probe: network access to jlcpcb.com, api.jlcpcb.com, open.jlcpcb.com; read the API docs after login (`pcbParam` fields, signature scheme per API); record one quote page of the shop by hand | the owner's account, environment network |
| 1 | `order_sheet.form`: the form as a dict, `order.md` printed from it – no change of output | – |
| 2 | `edakit jlc actual` from a hand-saved order page and from `pcb/order/detail` records; three-column comparison; fee table proposal | step 1 |
| 3 | Path B up to the quote, read-only: verify, upload, fields, read back, quote – stopping at the preview | step 0, Playwright |
| 4 | Path A, if JLCPCB approves the API application | approval |
| 5 | `edakit stock` through `component/getComponentDetailByCode` when the API is there (one call for the BOM) | step 4 |

Step 2 first: it delivers the feedback into the fee table without automating anything at the shop, and it can be built
from what the owner already has (past order pages).

## Open decisions

1. **Path:** apply for the official API (PCB only, approval uncertain for a private account) or go with the browser
   path B alone? Recommendation: B for PCBA, apply for A in parallel for the quote and the components call.
2. **Terms of use:** JLCPCB's terms on automated use of the shop were not read (not reachable). Read them before
   step 3; if they forbid it, B shrinks to a checklist the owner ticks while the browser shows `order.md` beside it.
3. **Placing orders:** never, or for PCB-only boards behind a flag?
4. **Real cost into the fee table:** as a proposal to review (as above), or automatically for values from the
   owner's own orders?
5. **Browser profile:** edakit's own (above) or the owner's everyday browser through Claude in Chrome?

## Sources

- JLCPCB, "JLCPCB Online API available now": https://jlcpcb.com/help/article/jlcpcb-online-api-available-now
- JLCPCB API portal: https://api.jlcpcb.com/docs/start, https://api.jlcpcb.com/docs/api-request-signature
- Clients of the official API: i2cjak/jlcpcb_api, shpaw415/community_jlcpcb_api_client, holla2040/hendley
  (`docs/api-reference.md`), NeilHanlon/swamp-jlcpcb, Eyalm321/jlcpcb-mcp, rjwalters/kicad-tools
- Web shop calls: Bouni/kicad-jlcpcb-tools (`common/jlcapi.py`), yaqwsx/jlcparts, Dirdmaster/overprint
  (`apps/web/server/utils/jlcUpload.ts`), mszkowalik/KiCad-Lib (`docs/jlcpcb-web-api.md`)
- EasyEDA Pro: https://prodocs.easyeda.com/en/pcb/order-order-pcb, easyeda/easyeda-api-skill
  (`references/classes/PCB_ManufactureData.md`)
