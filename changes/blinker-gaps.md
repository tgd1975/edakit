minor
- **When updating:** a sign-off's note is passing evidence for a requirement only where it names the ID after
  "requirements met:" (up to the next `;` or `.`) – an ID elsewhere in the note, "R-4 not met" too, counts for nothing
  (handbook 8.7). The reviewer agents have written that clause since requirements came; a note of another form gets it
  in the sign-off file – `edakit gate` lists a requirement whose note no longer names it.
- KiCad: the pours follow the outline, and a rule area keeps each mounting and tooling hole's keep circle free – no
  square notch to the edge any more (`pcb pour`, `route pours`); GEO.pour and the computed pours of `route check`
  measure the area the pours really fill, without the notch, on EasyEDA too.
- An LED's `values.vf_vs_if`, `[[A, V], …]` read off the datasheet's IV curve, sets the simulation's ideality (2
  without); `edakit part lint` holds the points to their form.
