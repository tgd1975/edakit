# Eurocircuits live, 2026-11-01 – the two stops before the basket

The copy of `examples/blinker-555` (KiCad tool chain), signed in to be.eurocircuits.com, nothing ordered.

## 1. Board thickness (run 20261101-000246)

"Board thickness" behind "More Options" offers 0.2, 0.36, 0.5, 0.8, 1.0, 1.2, 1.55, 2.0, 2.4 and 3.2 mm – no 1.6 mm, the
board's. The skill stopped with the field's name, as it must; the thicknesses went into the profile. For the test the
owner gave their word on `thickness_mm = 1.55` in the copy's board file, and on Eurocircuits as the copy's only maker
of `[cart]`. Only `order.json` changed (`edakit fab diff 20261101-084718 20261101-094147`); M-5 signed again by the
agent pcb-reviewer for fab `ab99c177…`.

## 2. The BOM's columns (run 20261101-095338)

`bom_main_mpn.csv` in the columns PCBWay's profile had lent to Eurocircuits' – Designator, Quantity, Manufacturer,
MPN, Comment. The import ("Manual import", step "Identify which columns to use") mapped them by name:

| Column | Mapped to |
|---|---|
| Designator | Reference Designator |
| Quantity | Quantity |
| Manufacturer | Manufacturer |
| MPN | -- None -- |
| Comment | Manufacturer part number (MPN) |

So the values became part numbers: C1 "100nF" a "Foam Adhesive 100NF Lavender 5 gal Box" (3M), R2 "200" a "4 'D' SIZE
Battery HOLDER" (Keystone), Q1 and U1 right only because their Comment is their MPN, five lines "Unidentified". The
import's choices: -- None --, -- Ignore --, Manufacturer part number (MPN), Manufacturer, Description, Package name,
Quantity, Reference Designator, Supplier name, Supplier part number (SPN), Library name, Value, Comment, URL, Placed,
Alternative MPN. Ordering step 0's BOM (Designator, Quantity, Value, Package, Manufacturer, Manufacturer Part Number)
had been identified. The import was cancelled, nothing submitted.

edakit writes that header now for every maker that takes `bom_<b>_mpn.csv` (PCBWay's engineers read the file by
eye); released again as run 20261101-101815 – the fab hash the same, the BOM not in it –, the configurator started
anew with the new job's files: nine lines identified by MPN, every check passed, into the basket (`cart.json`).
