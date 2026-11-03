patch
- Parts on hand: an inventory – a table with `ID` and `Quantity` in `.md`, `.html`, `.csv`, `.xlsx` or `.ods`, named in
  the new `edakit.local.toml` beside edakit.toml (in `.gitignore`) – is taken from first by `edakit order`: only the
  rest is ordered, `hand_assembly.md` says what comes out of the drawer; edakit never lowers a quantity. `edakit
  inventory` compares the project's hand-soldered parts with it, `edakit inventory template FILE` starts one (handbook
  8.4, 10.1; docs/concepts/done/parts-on-hand.md). Without the file nothing changes.
