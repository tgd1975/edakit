# Pull request #865 – as posted (M-11)

Posted on 2026-11-03 (https://github.com/oaslananka/easyeda-mcp-pro/pull/865) for #864 on the owner's word, with the issue ([issue-10-net-read-one-page.md](issue-10-net-read-one-page.md)).
From the fork's `fix/net-read-one-page` (`1b90910`, rebased onto `upstream/main` `5f845f0` on 2026-11-03).

### Title

```text
fix(schematic): read nets from the focused page only
```

### Body

````markdown
## Summary

`listNets` and `getNetDetail` support only the focused scope, and `SCH_PrimitiveWire.getAll()` returns the focused page's wires. The parts and net flags came from `SCH_PrimitiveComponent.getAll(undefined, true)`, which also returns every other loaded page – another open schematic of the project too. A flag there that sat on a wire point here joined that wire's net. Now `listNetsApi` reads `getAll(undefined, false)`.

Fixes #864

## Risk

Low – one argument in `easyeda-bridge-extension/src/dispatcher.ts`. The size budgets hold (`dispatcher.js` 248,309 of 248,314; `.eext` 206,179 of 206,184). Revert to roll back.

## Validation

- A test in `dispatcher.test.ts`: a flag of another loaded schematic on a wire end stays out of the net (fails without the fix).
- On main 5f845f0: `pnpm verify:fast` and the extension tests (619) green.
- Live on EasyEDA Pro 3.2.209 with 1.8.0 (the net code is the same in 1.8.1): reproduced, and gone with the other tab closed. The rebuilt extension not run live.
````
