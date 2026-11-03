# Pull request – draft (M-11)

Not posted – waits for the owner's word, with the issue ([issue-10-net-read-one-page.md](issue-10-net-read-one-page.md)).
From the fork's `fix/net-read-one-page` (`149dbe3`, on `upstream/main` `017f423`); "#<issue>" is filled in when the
issue is posted.

### Title

```text
fix(schematic): read nets from the focused page only
```

### Body

````markdown
## Summary

`listNets` and `getNetDetail` support only the focused scope, and `SCH_PrimitiveWire.getAll()` returns the focused page's wires. The parts and net flags came from `SCH_PrimitiveComponent.getAll(undefined, true)`, which also returns every other loaded page – another open schematic of the project too. A flag there that sat on a wire point here joined that wire's net. Now `listNetsApi` reads `getAll(undefined, false)`.

Fixes #<issue>

## Risk

Low – one argument in `easyeda-bridge-extension/src/dispatcher.ts`. The `dispatcher.js` budget holds (242,699 of 243,000; `.eext` 203,832 of 204,000). Revert to roll back.

## Validation

- A test in `dispatcher.test.ts`: a flag of another loaded schematic on a wire end stays out of the net (fails without the fix).
- On main 017f423: `pnpm verify:fast` and the extension tests (610) green.
- Live on EasyEDA Pro 3.2.209 with 1.8.0: reproduced, and gone with the other tab closed. The rebuilt extension not run live.
````
