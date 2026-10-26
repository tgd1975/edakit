# Reichelt (reichelt.de)

A German distributor for hand-soldered parts and small quantities. Order number: Reichelt's article number
(`NE 555 TEX`, `SMD-0603 10K`); the URL carries a numeric ID.

Works without a key, with curl and WebFetch (robots.txt allows it):

- Search: `https://www.reichelt.de/de/de/shop/suche/<term>`. The list does not show the manufacturer part number –
  open the product page.
- Product page `https://www.reichelt.de/de/de/shop/produkt/<name>-<id>`: schema.org data (`sku`, `mpn`, `gtin13`,
  price, availability), "Hst.-Teile-Nr.", price breaks, "ab Lager" without a count – report it as "in stock, no
  count", RoHS ("konform"), customs tariff number, datasheet PDF.

Not stated: REACH, country of origin, lifecycle – take them from the manufacturer or leave them open. No API.
