patch
- `schematic check` and stage S close every saved schematic tab before they read, not only their own: EasyEDA lists a pin of the template on a second net while the board's schematic is open (E-18, #117 – live on pytree). Another schematic with unsaved changes stays open and is named in the finding `saved`.
