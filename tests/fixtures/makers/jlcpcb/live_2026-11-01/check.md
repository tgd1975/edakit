# Order check – board main at JLCPCB, run 20261101-000246

Written by edakit cart check at 2026-11-01T00:22:01+01:00: what the skill cart brought back (quote.json, quote_page.txt) against the job, the release and the page text. job.json `836d888ba3c468f8fdf1393c573595555603a2556804e3a381b88107da9b2b62`, quote.json `885bd69e5193c6917d0a765d789d5078306faa2189060e631b9e21cfdf0ca701`.

| Check | Result | Actual |
|---|---|---|
| ORDER.form form = job | passed | 35 fields as the job says |
| ORDER.parts parts = release | passed | 9 lines, 10 parts as the release |
| ORDER.quote quote against the estimate | warning | PCB: quote 5.10, estimate 10.70 USD; assembly fees: quote 23.81, estimate 22.21 USD; parts: quote 4.15, estimate 3.70 USD – board 33.06 USD, estimate 36.61 USD |
| ORDER.read read, not made up | passed | 86 values, each in quote_page.txt |
| ORDER.files the same files | passed | 3 files, SHA-256 of the job and the manifest |
| ORDER.finish lead in the finish | passed | LeadFree HASL: no lead |
| ORDER.review regulatory review of this order | passed | regulatory.md: 8 findings, Order: OK |
| cart cart line | passed | gerber_main_Y9: 5 at 33.06 USD |

The cart line is the job's; the order record is written.
