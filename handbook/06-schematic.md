# 6 Schematic (stage S)

Two schematics per board, both generated:

| | name (default) | made by | content | edited by hand |
|---|---|---|---|---|
| template | `generated_<board>` | `edakit schematic create` | every part, every net as short stubs with net labels – exact, ugly | never; rebuilt on every run |
| board schematic | `layout_<board>` | `edakit schematic copy` + `layout` | readable sheet: blocks with titles and notes, real wires, power flags, GPIO table | never; rebuilt by `layout` |

The PCB hangs on the board schematic. Once it does, the board schematic cannot be replaced (the PCB would lose its
schematic); `layout` then syncs the parts in place instead of copying.

Without EasyEDA, `edakit schematic draw` draws the schematic as an SVG from the graph and the parts database alone
(6.5) – for a project without a PCB, for the documentation, for a look at a design before EasyEDA is involved.

## 6.1 Generate the template

```bash
edakit schematic create --dry-run          # graph and placement only, no EasyEDA
edakit schematic create --only U3,R10,C5   # partial build to try a part
edakit schematic create --save             # everything, then save
```

Steps (each with duration and EasyEDA's memory): bridge → project (it must exist – the local desktop client refuses
`DMT_Project.createProject`, so create a new project by hand once; edakit remembers its UUID and goes on only when
the open project has the configured name) → delete and recreate the template (never a
schematic that belongs to a board) → close other schematic tabs (EasyEDA sometimes switches to them by itself) →
search every LCSC number once (cache `<artifacts>/device_cache.json`, `--refresh-devices` searches again) → place in
blocks of 40 (`batch_write`; bigger blocks crashed EasyEDA) → set designators → compare symbol pins with the graph →
connect nets as stubs (longer stubs on collisions) → connect leftover pins one by one → mark no-connects → compare the
netlist with the graph → ERC → save.

Timing in the reference project: 13 parts 12–41 s; 123 parts 6 minutes (placing 2.1 min, connecting 3.7 min).

## 6.2 Check against the graph

```bash
edakit schematic check                                  # the template
edakit schematic check --schematic layout_main --no-pins
```

Read only (it activates the pages, though). Parts (missing, extra, duplicate, LCSC), nets (every graph pin on its net,
no foreign pins, no unknown nets), pin numbers **and names** and no-connect markers. About 10 s. A name that
differs from the symbol (`D11/MOSI` in the graph, `D11` in the symbol) fails: the graph then assumed another
pinout, and that is the error to catch here – or the library part disagrees with itself (an LED symbol naming pin 1
`K` while its footprint prints `+` at pad 1). Names follow the symbol; the meaning sits in the roles. The gate runs it for every board
(S-2). Run it also at the start of every EasyEDA session and before every gate run: a template once had a pin on two
nets without anyone having written to it; regenerating fixed it.

## 6.3 Copy and lay out

```bash
edakit schematic copy                      # template -> board schematic, seconds (only while no PCB hangs on it)
edakit schematic layout --dry-run          # plan + <artifacts>/layout_preview_<schematic>.svg, offline after the first run
edakit schematic layout --save             # rebuild the board schematic (1–2 min for 120 parts)
edakit schematic check --schematic layout_main
```

`layout` deletes all wires, flags, rectangles and texts of the page, moves and rotates the parts and wires them again:

- **Blocks** (`[schematic.layout] rows`): rows → columns → blocks with a title and start parts (connectors, ICs, the
  MCU). Every block gets a dashed frame, its title and notes (`[schematic.layout.notes]`).
- **Placement:** all other parts attach by breadth-first search over signal nets (not over power nets, not past
  another start part). The MCU goes last, so it collects only what is left (buttons, LEDs on GPIOs).
- **Capacitors** that touch only supply nets go to the part in `[schematic.layout] near`.
- **Orientation:** every child is rotated so its connecting pin points at the parent pin; children of one pin are
  stacked; the branches of one side are spread without overlaps and without crossings (isotonic regression keeps the
  order).
- **Connections:** a net inside a block is one branched wire with its name; to other blocks a labelled stub; power
  nets get flags (`power_flags`).
- **Page:** the smallest landscape standard size that holds the content and leaves the title block free (A4 … A0).
- **GPIO table** (`[schematic.layout.pin_table]`): pin → net → function, generated from the graph into the MCU block,
  plus the spare pins.
- **Before writing** the plan is checked for shorts (wires of different nets touching, wires over foreign pins,
  four-branch crossings which EasyEDA refuses). `--force` writes anyway.
- **After writing:** netlist against the graph, ERC.

The symbol geometry (pins and body per part) is cached per schematic; `--dry-run` works offline with it, `--reread`
reads it again.

If the board schematic is linked to a PCB, `layout` first syncs parts with the graph: missing ones are placed,
extra ones deleted, swapped ones (other LCSC number) replaced – a swapped part keeps its UniqueId and with it the link
to its footprint. New parts reach the PCB with `edakit pcb parts --write` (chapter 7).

## 6.4 What made this hard (and is handled)

- `modifySchematicName` renames the **active** schematic, not the one passed by UUID; right after creation it does
  nothing. edakit activates first and compares all names afterwards; it never deletes on a mismatch.
- Texts deleted with `SCH_PrimitiveText.delete` come back after a reload; edakit deletes them through another
  primitive class.
- Deleting parts or flags leaves their attribute texts as orphans on the page; edakit removes them.
- Moving a part does not move its wires; edakit deletes wires, moves, draws again.
- A big page takes minutes to open; a timeout while opening does not mean failure.
- The sheet frame (title block) may be missing; edakit creates it from the system library.

Details: [chapter 9.3](09-easyeda-api.md#93-schematic).

## 6.5 Drawn without EasyEDA

```bash
edakit schematic draw                          # <artifacts>/schematic_<board>.svg
edakit schematic draw --out docs/schematic.svg
```

The graph and the parts database are enough – no EasyEDA, no bridge, about a second. The arrangement is the one of
`layout` (6.3): blocks with titles and notes, placement by topology, real wires, flags, GPIO table. Only the symbols
come from the parts database instead of EasyEDA's library:

| kind | symbol |
|---|---|
| resistor, capacitor, inductor, fuse, diode, LED, buzzer, battery holder, button | two terminals; anode, plus or pin 1 on the left; `+` at a polarised capacitor |
| switch, potentiometer | common or wiper between the two other pins |
| npn, pnp, nmos, pmos | base or gate on the left, collector/drain and emitter/source up and down, with pin numbers |
| ic, module | a box with the connected pins in the order of their numbers, down the left side and up the right one as on a DIP package |
| connector, relay, RGB LED, DIP switch, anything else | a box with every pin (a connector in one column, a relay's coil on the left) |

A parts entry can arrange its box itself – a module whose pin numbers do not run like a DIP package:
`"symbol": {"left": ["1", …, "20"], "right": ["40", …, "21"], "bottom": ["41", "42", "43"]}` (left and right from top
to bottom, top and bottom from left to right; connected pins not listed go to the right).

**Without `[schematic.layout]`** the drawing arranges itself:

- every IC, module, connector, relay and battery holder starts a block, the power inputs first; title: designator and
  label, the block's note: the part's `notes`;
- ground symbols for the ground and every net with a ground pin; supply flags for every supply net (a supply output or
  an IC supply pin on it) and every net with ten or more pins – drawn as a wire, a rail behind a diode would gather
  half the board into one block;
- a capacitor between flagged nets sits at the IC or module that takes its supply in.

`rows`, `power_flags`, `near` and `notes` in edakit.toml replace each of these.

Before the file is written, the drawing is checked like a plan for EasyEDA – no wire touches another net or a foreign
pin – and every connected pin must end in a wire or a flag of its own net; otherwise nothing is written (exit 2,
`--force` writes anyway). The page is as big as the drawing plus the title block and to scale: one unit is 10 mil,
designators are 1.8 mm high.

A project without a PCB – a development board and hand wiring – never needs EasyEDA: checks, simulation and this
drawing work from the graph alone. For a PCB, EasyEDA's board schematic stays the one that counts; the PCB hangs on it.
