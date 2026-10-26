# Farnell (de.farnell.com, element14)

Order number: seven digits (`1775880`); the suffix `RL` is a re-reel.

Without a key: nothing. Search and product pages answer 403, WebFetch times out, and robots.txt excludes the search.
A web search can name the order code, but not the stock.

With `ELEMENT14_API_KEY` in the environment (register at `https://partner.element14.com`; the Product Search API is a
"courtesy usage allowance" – keep the calls few):

```text
https://api.element14.com/catalog/products?term=manuPartNum:<MPN>&storeInfo.id=de.farnell.com
  &resultsSettings.offset=0&resultsSettings.numberOfResults=10&resultsSettings.responseGroup=large
  &callInfo.responseDataFormat=JSON&callInfo.apiKey=$ELEMENT14_API_KEY
```

(one line; `term=id:<order code>` for an order code, `term=any:<words>` for a keyword). It returns `sku` (the order
code), `translatedManufacturerPartNumber`, stock, prices, `rohsStatusCode`, `productStatus` (`STOCKED`,
`NO_LONGER_STOCKED`, `NO_LONGER_MANUFACTURED`, `DIRECT_SHIP`), datasheets, `countryOfOrigin` and the SVHC statement
as an attribute. Never print the key.
