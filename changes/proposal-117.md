patch
- `schematic check` and the gate's stage S read a schematic as saved: its tab is closed and its pages opened again
  first, so the result no longer depends on whether stage F of an earlier gate closed the template's tab. A tab with
  unsaved changes stays open and is named in a finding `saved`. `schematic create --save` reads the save opened again
  and exits 2 when it differs from the graph (E-18, #117).
