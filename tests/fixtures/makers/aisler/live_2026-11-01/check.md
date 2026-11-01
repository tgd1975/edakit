# Order check – board main at AISLER, run 20261101-084718

Written by edakit cart check at 2026-11-01T09:00:08+01:00: what the skill cart brought back (quote.json, quote_page.txt) against the job, the release and the page text. job.json `5a573c15ae8e5442a62153ec68165da4c21602914bb04132c5943cd8fb55fcd2`, quote.json `3049bd3fe253f1fddd87f06ed2812f56c4a137f8f83691cf254152c1cc05132d`.

| Check | Result | Actual |
|---|---|---|
| ORDER.form form = job | passed | 8 fields as the job says, 2 parts marked not to place |
| ORDER.parts parts = release | FAILED | 0805W8F7503T5E R1: Out of Stock; 0805W8F2000T5E R2: Out of Stock |
| ORDER.quote quote against the estimate | passed | board 175.24 EUR; no estimate – AISLER has no fee table |
| ORDER.read read, not made up | passed | 34 values, each in quote_page.txt |
| ORDER.files the same files | passed | 1 files, SHA-256 of the job and the manifest |
| ORDER.finish lead in the finish | passed | LeadFree HASL: no lead |
| ORDER.review regulatory review of this order | open | regulatory.md not there – the agent regulatory-reviewer on the order (skill cart, step 8) |

The order stops here: nothing into the cart until the checks pass.
