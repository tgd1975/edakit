# Order check – board main at PCBWay, run 20261101-000246

Written by edakit cart check at 2026-11-01T00:31:46+01:00: what the skill cart brought back (quote.json, quote_page.txt) against the job, the release and the page text. job.json `879b8dfbeb6c7cbf65a012069775c61d9d72d3ce26ab69e11c0fcdaa97acd4e3`, quote.json `a9f0cf79336d30bc34316bfec6b5765b67036cac9c8871ea12c7f67117fe0f52`.

| Check | Result | Actual |
|---|---|---|
| ORDER.form form = job | passed | 26 fields as the job says |
| ORDER.parts parts = release | passed | 9 lines – PCBWay matches the BOM in its review after the cart; the parts it buys show on the order page (edakit cart actual) |
| ORDER.quote quote against the estimate | passed | board 35.50 USD; no estimate – PCBWay has no fee table |
| ORDER.read read, not made up | passed | 49 values, each in quote_page.txt |
| ORDER.files the same files | passed | 3 files, SHA-256 of the job and the manifest |
| ORDER.finish lead in the finish | passed | LeadFree HASL: no lead |
| ORDER.review regulatory review of this order | passed | regulatory.md: 8 findings, Order: OK |
| cart cart line | passed | 2 Layers Size 60x28mm 1.6mm: 5 at 35.5 USD |

The cart line is the job's; the order record is written.
