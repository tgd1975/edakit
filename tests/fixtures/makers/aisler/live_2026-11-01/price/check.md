# Order check – board main at AISLER, run 20261101-102149

Written by edakit cart check at 2026-11-01T10:37:09+01:00: what the skill cart brought back (quote.json, quote_page.txt) against the job, the release and the page text. job.json `2baf8ad7eefb2248509bdda5ef5a51e08c01216236f2e78a6792072737184819`, quote.json `558a3ee9d666941ca52c7ce3fbaf05c974396f6782a5d6a0bf74ad9d0cbe2b1f`.

| Check | Result | Actual |
|---|---|---|
| ORDER.form form = job | passed | 8 fields as the job says, 2 parts marked not to place |
| ORDER.parts parts = release | passed | 9 lines, 10 parts as the release |
| ORDER.quote quote against the estimate | passed | board 348.03 EUR; no estimate – AISLER has no fee table |
| ORDER.read read, not made up | passed | 38 values, each in quote_page.txt |
| ORDER.files the same files | passed | 1 files, SHA-256 of the job and the manifest |
| ORDER.finish lead in the finish | passed | LeadFree HASL: no lead |
| ORDER.review regulatory review of this order | passed | regulatory.md: 8 findings, Order: OK |

Every check passed: the skill may press the maker's cart button.
