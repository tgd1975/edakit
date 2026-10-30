# LCSC and JLCPCB

The default: JLCPCB assembles from its own library, which is LCSC's stock, and EasyEDA's symbols and footprints come
from the same catalogue. Order number: the LCSC number (`C17414`), the same at both – it names the parts entry and the
BOM line.

**Search in this order.** Say that a part is not available only after all three routes, and name each route with its
queries in the result:

1. **Search the catalogue:** `edakit part search "<keywords>"`. It asks JLCPCB's public parts catalogue (the endpoint
   of PARTS.stock) and needs no bridge and no claim. Each hit shows the LCSC number, manufacturer part number, manufacturer,
   class (Basic, Extended, preferred), JLCPCB's assembly stock, package and category. `C99…` numbers are dropped, and
   the order is Basic first, then by stock. Function and package words work ("RGB LED 5mm common cathode" gives the
   Kingbright C6751358 and the XINGLIGHT C7371894 in one query). `--basic`, `--min-stock N`, `--json FILE`. An LCSC
   number gives only its exact hit.
2. **Search EasyEDA:** `easyeda_schematic_search_device` with `key: "<LCSC number or manufacturer part number>"`. It
   needs the EasyEDA bridge but no claim: it runs while another session holds EasyEDA, and takes none itself. It
   returns footprint, manufacturer number, Basic/Extended and `otherProperty` (parameters), but no stock and no price.
   - **Take only hits whose `supplierId` equals the LCSC number.** The search is full text: `C5613` also finds
     `C5613331`.
   - `C99…` numbers are user libraries and cannot be ordered.
   - Free text ("led 5mm red") gives mostly noise.
   - LCSC's own search pages are JavaScript only, and its old search endpoint answers 403. Do not work around that.
3. **Search by series name:** the manufacturer's series name in either search (`XL-304`, `WP154A4`,
   `UNI-ROYAL 0805W8F…`). Take it from a candidate's datasheet or from the manufacturer's catalogue.

Then:

- **The library's data of one number:** `edakit part import <LCSC>`. It needs no bridge and no claim.
  - It writes a new entry with manufacturer, manufacturer part number, footprint, Basic/Extended and the symbol's
    pins. Kind, types, roles and values are yours to fill in.
  - For an existing entry it lists where it differs (exit 2). `--update` fills in missing fields only.
  - It caches symbol and footprint for STRUCT.entry and `pcb plan`.
  - Import one number at a time: the endpoint throttles after a few dozen requests (HTTP 403 for a while).
- **Stock, price breaks, RoHS** (curl, no key):
  `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=C17414` (JSON), or the part page
  `https://www.lcsc.com/product-detail/C17414.html` with the same data embedded (`stockNumber`, `productPriceList`,
  `isEnvironment` = RoHS). WebFetch drops stock and prices – use curl. **The datasheet:** `edakit part fetch <LCSC>`
  once the entry exists – it tries the entry's `datasheet.url`, this JSON's `pdfUrl` and JLCPCB's `dataManualUrl`,
  keeps the PDF and says whether it names the part (handbook 4.6). Do not download it by hand.
- **What JLCPCB says:** `edakit stock --lcsc C17414 C…` for every candidate (no project needed): listed or pre-order
  only, Basic/Extended (preferred), JLCPCB's stock, PCBA type ("Standard Only" forces Standard PCBA), MSL (≥ 5 is
  baked for a fee), X-ray, hand soldering, attrition and minimum. Basic parts first (no loading fee in Economic),
  Extended when needed, "Standard Only" only on a Standard order.
- JLCPCB's assembly stock differs from LCSC's. Once the part is in the graph, `edakit stock` records it in the
  project's snapshot and PARTS.stock checks it on every `edakit check`; at the export PARTS.stock asks the catalogue again.
- **Compliance:** RoHS only (with certificate); no REACH statement, no country of origin.

A part outside JLCPCB's library can still be assembled there, at a cost: *Global Sourcing* (JLCPCB buys it at DigiKey,
Mouser and others; review 1–3 days, then weeks for the purchase, duty and fees on top, the parts are used only for
JLCPCB's assembly) or *consigned parts* (you ship them to JLCPCB's warehouse after registering them). Both are the
user's decision.

Official APIs need an application and approval: LCSC (`https://www.lcsc.com/agent`), JLCPCB's Components API
(`https://api.jlcpcb.com`). The pages above are enough for single parts.
