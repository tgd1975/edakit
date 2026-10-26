# LCSC and JLCPCB

The default: JLCPCB assembles from its own library, which is LCSC's stock, and EasyEDA's symbols and footprints come
from the same catalogue. Order number: the LCSC number (`C17414`), the same at both – it names the parts entry and the
BOM line.

1. **Search:** `easyeda_schematic_search_device` with `key: "<LCSC number or manufacturer part number>"` (needs the
   EasyEDA bridge). It returns footprint, manufacturer number, Basic/Extended and `otherProperty` (parameters), but no
   stock and no price. **Take only hits whose `supplierId` equals the LCSC number** – the search is full text (`C5613`
   also finds `C5613331`). `C99…` numbers are user libraries, not orderable. Free text ("led 5mm red") gives mostly
   noise; manufacturer series names work (`XL-304`, `UNI-ROYAL 0805W8F…`). LCSC's own search pages are JavaScript
   only, and its old search endpoint answers 403 – do not work around that.
2. **Stock, price breaks, RoHS, datasheet** (curl, no key):
   `https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=C17414` (JSON), or the part page
   `https://www.lcsc.com/product-detail/C17414.html` with the same data embedded (`stockNumber`, `productPriceList`,
   `isEnvironment` = RoHS, `pdfUrl`). WebFetch drops stock and prices – use curl.
3. **Basic or Extended:** `https://jlcpcb.com/partdetail/C17414` (`componentLibraryType` "base" = Basic). Basic parts
   first (no feeder fee), Extended when needed.
4. JLCPCB's assembly stock differs from LCSC's. The gate asks JLCPCB's public catalogue for every BOM line (F-2); a
   part missing there can only be pre-ordered.
5. **Compliance:** RoHS only (with certificate); no REACH statement, no country of origin.

A part outside JLCPCB's library can still be assembled there, at a cost: *Global Sourcing* (JLCPCB buys it at DigiKey,
Mouser and others; review 1–3 days, then weeks for the purchase, duty and fees on top, the parts are used only for
JLCPCB's assembly) or *consigned parts* (you ship them to JLCPCB's warehouse after registering them). Both are the
user's decision.

Official APIs need an application and approval: LCSC (`https://www.lcsc.com/agent`), JLCPCB's Components API
(`https://api.jlcpcb.com`). The pages above are enough for single parts.
