# Pull request #819 – as posted (M-10)

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/pull/819) for #818 on the owner's word, from the fork's
`fix/rebuild-copper-batch-reconcile` (`0094ca5`, rebased onto `upstream/main` `cde4a39` before posting).

### Title

```text
fix(pcb): reconcile a net's second fresh pour against copper rebuilt earlier in the batch
```

### Body

````markdown
## Summary

`independentlyReconciled` took a beta return that names another pour only if exactly one Poured was new in the whole batch and the named pour had copper before the call. In a net's two fresh pours the second rebuild returns the first one's Poured, so it failed and locked every later rebuild. Now every new Poured must belong to a pour of the batch, and the named pour may also be one the batch rebuilt earlier; the other checks stay. A one-pour call is checked as before.

Fixes #818

## Risk

Low – `easyeda-bridge-extension/src/pcb-mutation-operations.ts` only, the reconciliation path. Revert to roll back.

## Validation

- Two tests in `pcb-mutation-operations.test.ts`: a net's second pour reconciled (fails without the fix), stray new copper still rejected.
- On main cde4a39: `pnpm verify:fast` and the extension tests (585) green.
- Live on EasyEDA Pro 3.2.209 with 1.6.0: the mismatch reproduced; one pour per call verifies. The rebuilt extension not run live.
````
