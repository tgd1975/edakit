# DigiKey (digikey.de)

Order number: `296-NE555P-ND`. One number per packaging: `-CT-` cut tape, `-TR-` reel, `-DKR-` Digi-Reel – for a few
boards the cut tape.

Without a key, **WebFetch works** (robots.txt allows it); curl gets a Cloudflare challenge (403).

- `https://www.digikey.de/de/products/result?keywords=<MPN>` leads straight to the product page for an exact
  manufacturer part number; a partial one lists the hits.
- The product page shows stock, status ("Aktiv"), EUR price breaks and the datasheet. Its environmental section
  (RoHS, REACH) comes back empty – take those from the API or the manufacturer.

With `DIGIKEY_CLIENT_ID` and `DIGIKEY_CLIENT_SECRET` in the environment (Product Information API v4,
`https://developer.digikey.com`, the client-credentials flow – see its docs for the token): `GET
https://api.digikey.com/products/v4/search/<MPN or DigiKey number>/productdetails` or `POST
https://api.digikey.com/products/v4/search/keyword`, with the headers `X-DIGIKEY-Client-Id`, the bearer token,
`X-DIGIKEY-Locale-Site: DE` and `X-DIGIKEY-Locale-Currency: EUR`. It returns the DigiKey number per packaging,
`QuantityAvailable`, `StandardPricing`, `ProductStatus`, `EndOfLife`, `DatasheetUrl` and `Classifications`
(`RohsStatus`, `ReachStatus`); no country of origin. Limits: 120 calls a minute, 1000 a day; keyword results may be
up to a day old. Never print the secret.
