# AISLER, live run 5.10 – the first try (2026-11-01)

The 555 blinker's copy, released as run 20261101-082445 (SYNC.odb equal on every layer after the edge tolerance),
`edakit cart prepare --maker aisler`, a new project EBRTNFZJ in the owner's Sandbox, odb_main.zip uploaded. Nothing
ordered; "Checkout now, starting at just €17.36" not touched.

Overview: 60 mm x 28 mm, 2 layers, minimal drill 0.3 mm, 2 elongated holes, 0 castellated.
Assembly tab: single-sided (top), 7 distinct components, 8 SMT, 0 THT, 0 press-fit; "Part polarity – please check".

BOM tab, "Auto assign parts using: Auto detect MPN" (AISLER's default):
- needs assignment: BT1 (2468), D1 (red), Q1 (AO3415A), SW1 (SK12D07VG4)
- assigned for review, by value and package – AISLER's own choice, not the release's part: C1 100.0nF 0805,
  C2/C4 1.0µF 0805, C3 10.0nF 0805, R1 750.0kΩ 0805, R2 200.0Ω 0805, R3 10.0kΩ 0805; U1 LMC555CMX/NOPB (Texas
  Instruments) – the one exact part, because its value is its MPN
- excluded: TH1, TH2 (tooling hole, Tooling)

"Auto assign parts using: lcsc" ("Rerun auto assignment? … Reset and reassign"): 12 parts need a component, none
assigned – the LCSC numbers stand as "Comment from Design" (C49678, C28323, …) and as "MPN from Design" in the
assign dialog, where AISLER's search finds nothing for C90760.

AISLER's search by MPN, nothing assigned: APTD2012LSURCK – Kingbright, LED RED CLEAR 2012 SMD, €0.15, available;
AO3415A – Alpha & Omega Semiconductor (SOT23, €0.18, available), UMW (€0.15), AOS (availability unknown).

The ODB++ components carried PRP Datasheet, Description, LCSC, Package, Value – no MPN, no manufacturer. Stopped at
the parts, as the skill must: an unassigned part is not guessed. Built from it: the KiCad footprints carry MPN and
Manufacturer of the parts entry, AISLER's profile `[bom] match = "mpn"`, SYNC.odb holds the ODB++ to the number the
maker matches by (it had passed on LCSC numbers alone).
