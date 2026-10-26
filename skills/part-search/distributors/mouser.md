# Mouser (mouser.de)

Order number: a manufacturer prefix and the manufacturer part number (`595-NE555P`).

Without a key: nothing. Search and product pages answer "Access to this page has been denied" – with HTTP status 200,
so read the body, not the status; WebFetch times out. A web search can name the Mouser number, but not the stock.

With `MOUSER_API_KEY` in the environment (a My Mouser account and the Search API sign-up,
`https://www.mouser.com/api-search/`, the key comes at once): `POST
https://api.mouser.com/api/v1/search/partnumber?apiKey=$MOUSER_API_KEY` for exact manufacturer part numbers (up to ten,
joined by `|`) and `/api/v1/search/keyword`; the request bodies are in the Swagger page
`https://api.mouser.com/api/docs/ui/index`. It returns `MouserPartNumber`, `ManufacturerPartNumber`,
`AvailabilityInStock`, `PriceBreaks`, `ROHSStatus`, the REACH SVHC statement, `LifecycleStatus`, `IsDiscontinued`,
`DataSheetUrl` and `ProductCompliance`; no country of origin. Limits: about 30 calls a minute and 1000 a day. Never
print the key.
