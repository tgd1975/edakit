# 6 Schematic (stage S)

Two schematics per board, both generated:

| | name (default) | made by | content | edited by hand |
|---|---|---|---|---|
| template | `generated_<board>` | `edakit schematic create` | every part, every net as short stubs with net labels – exact, ugly | never; rebuilt on every run |
| board schematic | `layout_<board>` | `edakit schematic copy` + `layout` | readable sheet: blocks with titles and notes, real wires, power flags, GPIO table | never; rebuilt by `layout` |

The PCB hangs on the board schematic. Once it does, the board schematic cannot be replaced (the PCB would lose its
schematic); `layout` then syncs the parts in place instead of copying.

## 6.1 Generate the template

```bash
edakit schematic create --dry-run          # graph and placement only, no EasyEDA
edakit schematic create --only U3,R10,C5   # partial build to try a part
edakit schematic create --save             # everything, then save
```

Steps (each with duration and EasyEDA's memory): bridge → project (create only with `--create-project`, because
EasyEDA does not list local projects and a duplicate could appear) → delete and recreate the template (never a
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
no foreign pins, no unknown nets), pin numbers and no-connect markers. About 10 s. The gate runs it for every board
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
