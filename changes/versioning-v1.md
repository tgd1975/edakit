minor
- **When updating:** nothing beyond the update itself – 0.2.0 is edakit's first number. From now on the
  plugin comes from the version's tag, and `edakit --version` and the gate manifest's `tools.edakit` name the version
  (from a git checkout with its commit: `0.2.0+g1a2b3c4`). A project that sets the new `purpose.country` (below)
  changes its circuit hash and signs M-6 again.
- What came on 2026-11-01, before the first number:
  - **New checks:** PARTS.fact/reach – a part's SVHC when the board is given or sold (#95); DOCS.derived – a
    requirement names who stated it (#98); GEO.formed/counter – formed leads in one row (#100); GEO.pour – every bare
    area above `[copper] max_bare_mm2` on each side (#103); PARTS.fact/rohs for every BOM part and FILES.order/lead at
    the release; LIM.i holds a magnetic buzzer's coil current to its rating (#90).
  - **New:** `purpose.country` – the country whose law the regulatory review applies, DE and AT (#94); a touch limit
    with its own ambient in `touch_c` (#93); an RGB LED's limits per colour in `edakit check --coverage` (#91); pictures
    in the release protocol, and the board's layers over each other with stage F (#99); CPL rotations per maker
    (`[cpl] zero`, `[cpl.turns]`, SYNC.cpl); JLCPCB's customs description as `[order] customs`; the makers' RoHS and
    REACH statements in their profiles; AISLER matches the parts by MPN, which the KiCad footprints now carry;
    Eurocircuits' BOM import and basket; the skill cart stops at every consent.
  - **Fixed:** stage L finds a part bought elsewhere by the MPN its `part` names (GEO.hole, GEO.mark,
    SYNC.footprint, #88); GEO.mark takes a "+" as artwork only on an artwork's shapes (#92); SYNC.odb takes an edge one
    raster point off as rounding; `silk apply` no longer doubles the print on a fresh clone; no `fab/<board>/current`
    left beside a run's files; `place` takes every part with `bom: false` out of the BOM (M-9); what the KiCad live
    test found (LT-1 to LT-8, LT-10, LT-11); the skill requirements writes the maker's inputs, not edakit's outputs
    (#97).
