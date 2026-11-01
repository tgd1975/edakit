# JLCPCB, B6, 2026-11-01 (Chrome, the owner's account)

Walkthrough-gaps B6: does JLCPCB's Economic PCBA take a round board on two customer tooling holes, without rails?
Read off the form, nothing in the cart.

Files: the Gerber of the round probe board (`../../aisler/probe_2026-11-01/run/main/gerber/`, Ø 44 mm, two NPTH
Ø 1.152 mm at (9, 36) and (35, 8) – the outline and `[tooling]` of `examples/coin-cell-led`), BOM and CPL with D1
and SW1 only (`bom_round_top.csv`, `cpl_round_top.csv`): the probe has R1 on the bottom, and Economic is one side.

- Upload: "Detected 2 layer board of 44x44mm(1.732*1.732 inches)", Delivery Format Single PCB.
- PCB Assembly on: PCBA Type Economic, Assembly Side Top Side, PCBA Qty 5, Tooling holes "Added by Customer" –
  set without a dialog or a note (`pcba_top.jpg`).
- BOM: 2 parts detected, 2 confirmed – D1 C84256, SW1 C318884, both Basic, no mark.
- Component Placements: both on their pads, the round outline drawn whole, nothing added at the edge
  (`placement_top.jpg`).
- Quote & Order (`quote.jpg`): PCB $4.00 (Special Offer), Economic PCBA $10.92 – Setup Fee $8.24, Stencil $1.55,
  **Panel $0.00**, Large Size $0.00, Components (2 items) $0.17, SMT Assembly $0.05, Nitrogen reflow soldering $0.91;
  build time PCB 24 hours, assembly 1–2 days; total $14.92. No line, warning or DFM note about rails or panelising.
  Stopped before "SAVE TO CART"; the draft "gerber_round" stays saved in the account (not in the cart).

Result: the online form takes Economic PCBA on a round single board with customer tooling holes and adds no rails or
panel. What JLCPCB's engineers say in the review after an order is left to the first real order (M-2 there). The
order number: read on 2026-10-31 (`../step0_2026-10-31.md`, "Mark on PCB" without it).
