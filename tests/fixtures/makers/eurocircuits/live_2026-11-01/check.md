# Order check – board main at Eurocircuits, run 20261101-101815

Written by edakit cart check at 2026-11-01T10:40:14+01:00: what the skill cart brought back (quote.json, quote_page.txt) against the job, the release and the page text. job.json `a13032784fd5f2df4715a2b0d96b1054d5eef4aa469faefe5ed0bbaae971dc8d`, quote.json `f663441660f151e61cf7c244ecacd3ba0cd21697b06d726af5d3b4867bfbacbb`.

| Check | Result | Actual |
|---|---|---|
| ORDER.form form = job | passed | 13 fields as the job says |
| ORDER.parts parts = release | passed | 9 lines, 10 parts as the release |
| ORDER.quote quote against the estimate | passed | board 326.76 EUR; no estimate – Eurocircuits has no fee table |
| ORDER.read read, not made up | passed | 85 values, each in quote_page.txt |
| ORDER.files the same files | passed | 3 files, SHA-256 of the job and the manifest |
| ORDER.finish lead in the finish | passed | LeadFree HASL: no lead |
| ORDER.review regulatory review of this order | passed | regulatory.md: 3 findings, Order: OK |
| cart cart line | passed | gerber_main: 5 at 272.3 EUR |

The cart line is the job's; the order record is written.
