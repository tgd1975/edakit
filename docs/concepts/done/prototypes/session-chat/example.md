# Layout example

```chat
--- 8 Have it reviewed
claude: Two reviewers check it now, each in a session of its own. The regulatory review is support, not legal advice.
do: Start each reviewer in a new session when Claude asks.
ran: electrical-reviewer: 5 notes · regulatory-reviewer: 4 notes, none blocking
form: Two notes need you, the rest Claude fixed
  ? Who uses the board? The cell comes out by hand, and a swallowed coin cell burns.
  - Adults at a desk, out of reach of small children (recommended).
  - Children: then a holder that needs a tool.
  > Adults at a desk
  ? R-2, dark while nobody presses, has no number. At most 1 µA from the cell?
  > yes

--- 9 Lay out the board
do: Install EasyEDA Pro. Create the project by hand: File → New → Project, "coin-cell-led".
  † Not with KiCad: there edakit writes the project itself. EasyEDA's interface cannot create one yet; we reported
  it to EasyEDA ([issue #45](https://github.com/easyeda/easyeda-api-sdk/issues/45)), and the click goes once it is
  fixed. The other click, Design → Import Changes, is gone since 2026-11-01: we reported it too
  ([issue #46](https://github.com/easyeda/easyeda-api-sdk/issues/46)), and edakit now writes what the import set.
claude: The board's size and shape? And what must stay where a person touches or looks?
you: Round, please.
claude: Ø 44 mm. The cell nearly in the middle, 10 mm above it to lever it out. Button, LED and resistor below.
img: ../../../../../examples/coin-cell-led/docs/pcb_plan_main.png | The placement plan
```
