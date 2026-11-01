# Probe: the turned CPL at Eurocircuits (2026-11-01)

After live run 5.8, on the owner's word, nothing put into the basket. The configurator
(be.eurocircuits.com/shop/assembly/configurator.aspx, signed in) took run 20261101-101815's `gerber_main.zip`
(60.00 x 28.00 mm measured), `bom_main_mpn.csv` (9 lines identified, imported without a mapping dialog) and
`cpl_main_eurocircuits.csv` (beside this file) as edakit's `[cpl.turns]` wrote it: Q1 at 270° instead of 180°, every
other part as in `cpl_main.csv`. The Assembly Editor ("Source: cpl_main_eurocircuits.csv", 10 components), status
per part (Selected component), then Cancel:

| Part | Rotation | Status |
|---|---|---|
| C1 | 0 | No issues detected |
| C2 | 270 | No issues detected |
| C3 | 0 | The component footprint does not match the board layout |
| C4 | 90 | No issues detected |
| D1 | 0 | No issues detected; No data available to check pin 1 location |
| Q1 | 270 | No issues detected; No data available to check pin 1 location |
| R1 | 180 | No issues detected |
| R2 | 0 | No issues detected |
| R3 | 0 | The component footprint does not match the board layout |
| U1 | 0 | No issues detected; No data available to check pin 1 location |

Q1's three pads lie on the board's (two on the left, one on the right), the body's pin-1 dot upper left, where pin 1
(GATE) is on the board – in 5.8, at 180°, it was drawn turned by 90°. C3 and R3 are read as in 5.8; the editor
hatches copper beside their pads yellow – along the track meeting C3's left pad at an angle, around both of R3's
pads: the board's copper, not the rotation.
