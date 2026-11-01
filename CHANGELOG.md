# Changelog

What changed in each version of edakit, newest first – for a maker who updates the plugin. Every merge that changes
edakit is a version of its own: the minor number goes up when a project must act, and its lines begin with **When
updating:**; the patch number goes up otherwise; the major number marks a milestone of edakit itself. Each section is
written once, by `.github/merge.py`, from the fragments in [changes/](changes/README.md) – the rule is in
[versioning.md](docs/concepts/new/versioning.md). Update with `claude plugin marketplace update edakit && claude plugin
update edakit@edakit`, then `/reload-plugins` or a new session; `edakit --version` names the version that runs.

## 0.4.3 – 2026-11-01

- GEO.pour finds every bare area above `[copper] max_bare_mm2` on each side, not only the largest circle (#103).

## 0.4.2 – 2026-11-01

- A project never opened is found by its name through EasyEDA's API – `getAllProjectsUuid` with each project folder of `DMT_Team.getAllTeamsInfo` (E-9) – instead of reading EasyEDA's `config.json` and `.eprj2` files; `EDAKIT_EASYEDA_HOME` is gone.

## 0.4.1 – 2026-11-01

- The concept of the proposals pipeline moved to docs/concepts/done/; comments and links follow it.

## 0.4.0 – 2026-11-01

- **When updating:** in EasyEDA Pro uninstall the old bridge extension, import `~/.easyeda-mcp-pro/easyeda-bridge-extension-1.6.0.eext` (built by `bridge-extension-patch.sh`, handbook 2.5), allow "External Interactions", restart EasyEDA and every MCP server – easyeda-mcp-pro is pinned to 1.6.0 now, and since 1.5.1 a server whose extension has another version refuses every write, export and `easyeda_api_call`.
- The PCB's parts are read with the PCB focused and its project's exact UUID – 1.6.0 refuses projectId "current".
- EasyEDA's BOM is no longer cleaned of designators listed twice – since 1.6.0 it lists each part once, and SYNC.bom reports a designator listed twice (TD-54).

## 0.3.3 – 2026-11-01

- The proposals Action waits for its tests before a result and lists each proposal as one item in the pull request,
  with no placeholder left in it (TD-43).

## 0.3.2 – 2026-11-01

- The proposals Action carries over a commit an earlier triage pushed after its pull request was merged even when the
  generated catalog page conflicts – the page is written again – and the new pull request names it (TD-43).

## 0.3.1 – 2026-11-01

- The proposals Action judges with a token that cannot write, and a fixed job checks each build against the
  pipeline's paths before anything is pushed: the pipeline never changes through itself. The queue triages a proposal
  once even when several are filed together. Issues by others are welcome – the owner hands one over with a sealed
  proposal as a comment (`propose-rule`, `propose-feature`) (TD-42, docs/concepts/done/proposals-pipeline.md).

## 0.3.0 – 2026-11-01

- **When updating:** a project without `[project] requirements` writes its requirements file with `/edakit:requirements` and names it in `edakit.toml` before its next release – DOCS.file is open until then: `edakit check` passes, `edakit check --release` and the gate do not release (handbook 3.6, 8.7).

## 0.2.0 – 2026-11-01

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
