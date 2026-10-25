# 8 The release gate

Only the gate creates the files that go to the manufacturer, and only a run whose manifest says `"released": true`
may be uploaded. The gate runs every check, on the files themselves, and writes a test protocol.

```bash
edakit gate              # P, G, E and the project's own stages – offline, seconds
edakit gate --easyeda    # plus S, L, F – EasyEDA with the bridge, minutes
```

"Guaranteed correct" is not reachable with any tool chain. Reachable is:

1. Every known error class has an automatic check, and every check was seen red once.
2. What cannot be automated is a manual check in the sign-off file, signed for exactly the checked state.
3. After delivery an acceptance test of every board checks the assumptions by measurement.

## 8.1 Stages

| Stage | What | Checks |
|---|---|---|
| P – Parts | parts database complete and signed | P-1, G-9 (chapter 3, 4) |
| G – Graph | rule checks | G-1 … G-10 (chapter 3) |
| E – Simulation | operating points, stress, function | E-1 … E-3 (chapter 5) |
| *project stages* | e.g. K – mechanics of an enclosure | `[[release.stages]]`, see below |
| S – Schematic | EasyEDA schematic = graph | S-2 per board |
| L – Board | PCB = graph and plan, copper from the Gerber files | L-1 … L-11 |
| F – Manufacturing | BOM, stock, pick and place, Gerber set | F-1 … F-5 |

**Stage L** (per board, `edakit fab`):

| Check | What | Why it exists |
|---|---|---|
| L-1 | parts in the PCB = graph; every pad carries the graph's net; every graph pin has a pad | the import may lose or mismatch parts |
| L-2 | copper from the **Gerber files**, rasterised at 0.02 mm, layers joined through plated holes, pads from FlyingProbeTesting.json, nets from the graph: every net connected, no short, every pad present | do not trust EasyEDA – check what goes to the factory |
| L-3 | EasyEDA DRC 0 (after save and reload) | |
| L-4 | footprint per part = parts database | a swapped footprint variant |
| L-5 | track width ≥ IPC-2221 for 1.5 × the simulated current (fail), ≥ class width (warn), voltage drop upper bound (info) | power tracks too thin |
| L-7 | fixed parts in the PCB = plan (± 0.02 mm, rotation, side); the plan itself without findings | a part moved by hand or by the auto-layout |
| L-8 | silkscreen "+"/"−" next to a pad with that polarity role | a sign at the wrong pole |
| L-9 | every through hole takes its lead at nominal size (lead data in the parts database); worst case (hole −0.08 mm, lead + tolerance) below 0.05 mm play or plated slots narrower than 0.5 mm: warning per part | two parts whose leads would not have fitted the library holes |
| L-10 | every pad sits where the library footprint has the pad with that number (`pad_map` for intended swaps) | a pad swap that was reset by EasyEDA |
| L-11 | short current loops (`[[boards.<b>.loops]]`): shortest path over tracks per pad pair within its limit | a switching regulator loop routed 61 mm around the board |

**Stage F:**

| Check | What |
|---|---|
| F-1 | BOM generated **from the graph** in JLCPCB format = EasyEDA's BOM per designator; every LCSC number in the parts database; parts with `bom: false` left out on purpose |
| F-2 | every BOM line in JLCPCB's public assembly catalogue with stock for `quantity` boards (otherwise only pre-order) |
| F-3 | pick and place: every BOM part exactly once, side and rotation = PCB; sides and SMD-only as `[release] assembly` says (Economic PCBA: one side, SMD only; two SMD sides need Standard PCBA) |
| F-4 | Gerber ZIP, BOM and pick and place from the same run; `fab/manifest.json` with SHA-256 per file and the state hashes |
| F-5 | Gerber set complete; outline and mounting holes from the outline layer = plan (± 0.2 mm); tooling holes in the NPTH file, mask open, no copper in the opening |

Plus P-2: a **polarity sheet** per board – every polarised part drawn from the Gerber data with copper, silkscreen,
pad numbers, pin roles and nets, bottom parts mirrored as seen from below. It is what the second check compares with
the datasheet drawings, and what you compare with JLCPCB's assembly preview.

**Project stages** (`[[release.stages]]` in edakit.toml): `{id = "K", name = "Mechanics", cmd = ["uv", "run",
"mech/check.py", "--json"], advisory = true}`. The command's last stdout line may be a JSON list of
`[id, check, actual, expected, ok]`; otherwise its exit code counts. `advisory` findings are listed but do not block
(in the reference project the printed enclosure was adapted after delivery anyway).

## 8.2 Hashes and sign-offs

Every run records two hashes in the protocol header:

- **circuit** (`state_sha256`): graph, parts database, simulation config (and plugin, `[release] state_files`)
- **layout** (`layout_sha256`): `[release] layout_files` (default edakit.toml) and the footprint geometry

The sign-off file (`[release] signoff`, [example](../examples/led-bar/hardware/signoff.json)) holds manual checks and
accepted warnings. Each counts only if the hash of its scope equals the current one:

```json
{
  "state_sha256": "<from the protocol header>",
  "layout_sha256": "<from the protocol header>",
  "manual": [
    {"id": "M-1", "phase": "export", "scope": "circuit", "text": "critical parts checked again …",
     "done_by": "agent electrical-reviewer (own session)", "date": "2026-10-24", "note": "…"}
  ],
  "accepted_warnings": [
    {"match": "L-5 main track width >= practical width*", "scope": "decision",
     "reason": "D-38: 18 mil is above IPC for 1.5 x the current; wider tracks left 16 links open", "by": "owner",
     "date": "2026-10-22"}
  ]
}
```

| Phase | When | Blocks the release |
|---|---|---|
| `export` | before the files are released (M-1 second datasheet check, M-5 layout review) | yes |
| `order` | after uploading, before paying (M-2: JLCPCB's assembly preview, BOM tool, price) | no |
| `acceptance` | after delivery (M-4: acceptance test of every board) | no |

`match` is an fnmatch pattern over "ID scenario item step" as section 3 of the protocol prints it. Scope `decision`
counts regardless of the hash and must refer to a numbered decision. **Only the owner accepts a warning** – it is a
decision. **A manual check an agent can do is signed by the agent's result** (chapter 11): OK → signed with the agent
as `done_by`; not OK → fix the cause, check again.

The lesson behind M-5: the first released run of the reference project had passed every automatic check, and nobody
had looked at the layout as a whole. The layout review agent then found a switching regulator loop routed across the
whole board (now L-11) and that the visible side was crowded with tracks. Since then the layout review is a condition
of the release, not a tool you may use.

## 8.3 The decision

RELEASED only if every stage ran, no check failed, every warning is accepted, every part is signed, every manual check
of phase `export` is signed – all for the current hashes. Otherwise NOT RELEASED with the reasons. Exit 0 / 2.

Result folder `<reports>/<YYYYMMDD-hhmmss>/`: `protocol.md`, `graph_checks.json`, `sim.json`,
`schematic_<board>.json`, `fab/<board>/` (Gerber ZIP, BOM, CPL, raw data), `fab/polarity_<board>.png`,
`fab/manifest.json`. Archive a released folder in git (`git add -f`) – it is the record of what was ordered.

## 8.4 Ordering at JLCPCB (the owner does it)

The MCP server cannot order. Lessons from the reference order:

- Upload `gerber_<b>.zip`, `bom_<b>.csv`, `cpl_<b>.csv` from the released folder only; compare the checksums.
- **Economic PCBA** assembles one side, SMD only; a second SMD side or certain parts (large battery holders) need
  Standard PCBA with a higher setup fee per side. Plan the board so the cheap option works (through-hole parts you
  solder yourself get `bom: false`).
- **Tooling holes:** with your own (chapter 7.2) choose "added by customer"; otherwise JLCPCB adds rails or holes.
- **Moisture-sensitive parts:** JLCPCB bakes MSL ≥ 5 parts for a fee and includes the 48 h in the lead time; its MSL
  classification may differ from the manufacturer's datasheet – check the BOM tool.
- **Tented vias** if a side is visible (open vias are holes and tin dots).
- **Order number:** "specify a location" when a placeholder is printed.
- **Remarks** (max. 200 characters): where panel tabs may and may not go, no V-cut on visible edges.
- **M-2** in the assembly preview: rotation and polarity of every polarised part on both sides (compare with the
  polarity sheet), no part missing in the BOM tool, then pay.
- If JLCPCB's DFM check reports something the layout review already accepted (e.g. a drill-to-drill distance on two via
  pairs), it is in the checklist so nobody panics.

## 8.5 Acceptance (M-4)

After delivery every board gets a short acceptance test: visual check (polarity of every polarised part), supply
current at the nominal voltage against the simulated value, every LED/output, every input, the firmware's self-test.
Deviation beyond tolerance → find the cause (model, firmware, assembly) before the board is used.
