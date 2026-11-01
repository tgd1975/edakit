# Glossary

The words of edakit, one or two sentences each, with the handbook section that treats the term. They are the words
the skills, the agents and the catalog use. The rules for writing are in the [style guide](style.md).

### Accept

You answer a finding you have seen with `accept` and a reason, keyed by its code. Accepted in the graph, the finding
is waived. A warning for the release is accepted in the sign-off file. A pending finding cannot be accepted.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains),
[8.2 Hashes and sign-offs](../handbook/08-release-gate.md#82-hashes-and-sign-offs).

### Agent

A prompt that runs Claude in a context of its own for one role, such as the electrical reviewer. The reviewers change
nothing and return numbered findings.
Handbook: [11.1 What the plugin brings](../handbook/11-working-with-claude.md#111-what-the-plugin-brings),
[14.1 Roles](../handbook/14-design.md#141-roles).

### Board file

`hardware/boards/<name>.toml` holds what the PCB designer decides for one board. That is the placement plan, holes,
routing, silkscreen and order settings.
Handbook: [10.2 The board file](../handbook/10-reference.md#102-the-board-file).

### Bought board

A board you buy and connect by a cable instead of making it, marked `bought = true`. It goes through stages P, G and E.
It has no schematic, PCB or manufacturing files.
Handbook: [8.1 Stages](../handbook/08-release-gate.md#81-stages).

### Bridge

The extension inside EasyEDA Pro, menu "MCP Bridge". The MCP server drives EasyEDA through it.
Handbook: [2.1 What talks to what](../handbook/02-setup.md#21-what-talks-to-what),
[2.5 The bridge extension, patched](../handbook/02-setup.md#25-the-bridge-extension-patched).

### Building block

A piece of graph with checked parts: components with LCSC numbers, nets, and ports. `edakit block add` puts one into
the graph. Short: block.
Handbook: [14.5 Building blocks](../handbook/14-design.md#145-building-blocks).

### Catalog

What edakit knows about circuits, kept as data in `edakit/catalog/`. It holds the engines and codes, the parts schema,
defaults and tables. `edakit explain` and the catalog page show it.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Claim

A session holds EasyEDA while it works in it, so that two sessions do not pull its tab from each other. The first
access claims it. The claim expires after 15 minutes without access.
Handbook: [11.2 Parallel sessions share one EasyEDA](../handbook/11-working-with-claude.md#112-parallel-sessions-share-one-easyeda).

### Code

The name of a check, written `ENGINE.relation`. `LIM.v` is a voltage beyond its limit. Every finding carries one.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Decision log

The project's numbered decisions `D-…`, usually in `docs/decisions.md`. It says why the circuit is as it is.
Handbook: [3.6 Requirements](../handbook/03-hardware-graph.md#36-requirements),
[10.1 edakit.toml](../handbook/10-reference.md#101-edakittoml).

### Decision round

Claude puts open questions to you as numbered findings, each with its alternatives and a recommendation. Your answers
become decisions in the decision log.
Handbook: [11.4 Working agreements that proved themselves](../handbook/11-working-with-claude.md#114-working-agreements-that-proved-themselves).

### Domain

A profile of rules for one area of electronics, such as `usb`, `radio` or `power`. It switches codes on, sets their
severities, and names hints and the reviewers' questions. The domain `core` is always on.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### edakit.toml

The project file at the top of a repository. It names the boards, the graph, the makers and the release settings.
Handbook: [10.1 edakit.toml](../handbook/10-reference.md#101-edakittoml).

### Engine

The part of edakit that decides one kind of relation. LIM compares quantities with their limits, SYNC compares every
artifact with the graph. There are thirteen.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Fee table

What `edakit cost` prices an assembly order with: JLCPCB's fees and PCB prices, each with its date and source. A
project's own orders lay their values over it in `hardware/fees/<maker>.json`.
Handbook: [8.4 Ordering at the manufacturer (up to the cart; the owner orders and pays)](../handbook/08-release-gate.md#84-ordering-at-the-manufacturer-up-to-the-cart-the-owner-orders-and-pays).

### Finding

What a check reports at one place. It has a code, a stage, a place, a text, a fix and a severity.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Firmware contract

What the firmware must know about the board, as a JSON file. `edakit firmware` writes it when edakit.toml has
`[firmware]`.
Handbook: [3.5 The firmware contract](../handbook/03-hardware-graph.md#35-the-firmware-contract).

### Gate run

One run of `edakit gate`. It runs every stage, writes the protocol and the manifest, and decides RELEASED or NOT
RELEASED.
Handbook: [8.1 Stages](../handbook/08-release-gate.md#81-stages),
[8.3 The decision](../handbook/08-release-gate.md#83-the-decision).

### Grade

A sub-case of a code with its own severity. `margin` is a value inside its limit but close to it.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Hand-over

What the circuit tells the layout, written as `layout` in the graph. It names fixed parts, parts at the edge, parts
that sit next to another and hot loops. `edakit handover` shows it.
Handbook: [14.1 Roles](../handbook/14-design.md#141-roles).

### Hand-wired board

A board you wire by hand, marked `wired = true`. Like a bought board, it has no PCB or manufacturing files.
Handbook: [4.5 Own parts](../handbook/04-parts-database.md#45-own-parts),
[8.1 Stages](../handbook/08-release-gate.md#81-stages).

### Hardware graph

The circuit as text: a netlist down to the pins, in `hardware/graph.toml`. It is the only place where parts, values and
connections are decided. A project not converted yet keeps `hardware/graph.json`. Short: graph.
Handbook: [3 The hardware graph](../handbook/03-hardware-graph.md),
[3.1 Format](../handbook/03-hardware-graph.md#31-format).

### Hash

A gate run records hashes of what the sign-offs cover: the circuit, the layout and the manufacturing files. A change
of what a hash covers voids the sign-offs bound to it.
Handbook: [8.2 Hashes and sign-offs](../handbook/08-release-gate.md#82-hashes-and-sign-offs).

### Hint

Knowledge that needs judgement, such as whether a button needs a hardware debounce. `edakit check` shows hints as
notes. They never block.
Handbook: [14.3 Hints](../handbook/14-design.md#143-hints).

### Job

What `edakit cart prepare` writes for one order: the release's upload files with their SHA-256, every field of the
maker's form and the expected parts. The skill cart fills the form from it. `edakit cart check` holds the page to it.
Handbook: [8.4 Ordering at the manufacturer (up to the cart; the owner orders and pays)](../handbook/08-release-gate.md#84-ordering-at-the-manufacturer-up-to-the-cart-the-owner-orders-and-pays).

### Maker

The manufacturer that builds the board: JLCPCB, PCBWay, Eurocircuits or AISLER. Its profile in `edakit/makers/`
translates the order settings into the words of its form.
Handbook: [8.4 Ordering at the manufacturer (up to the cart; the owner orders and pays)](../handbook/08-release-gate.md#84-ordering-at-the-manufacturer-up-to-the-cart-the-owner-orders-and-pays).

### Manual check

A check a person or a reviewer agent does and signs, numbered `M-1` and up. Every release needs M-1, the circuit
against the datasheets; M-5, the layout review; and M-6, the regulatory review.
Handbook: [8.2 Hashes and sign-offs](../handbook/08-release-gate.md#82-hashes-and-sign-offs).

### MCP server

easyeda-mcp-pro, the program between Claude Code or edakit and the bridge in EasyEDA.
Handbook: [2.1 What talks to what](../handbook/02-setup.md#21-what-talks-to-what),
[2.4 The MCP server](../handbook/02-setup.md#24-the-mcp-server).

### Need

What someone wants, in their own words, numbered `N-…` in the requirements file.
Handbook: [3.6 Requirements](../handbook/03-hardware-graph.md#36-requirements).

### Order record

What stays of an order in the repository: `hardware/orders/<date>-<board>-<maker>.json`, written once the board is in
the maker's cart. It names the run, its hashes and the regulatory verdict, later the order number and the real cost.
Handbook: [8.4 Ordering at the manufacturer (up to the cart; the owner orders and pays)](../handbook/08-release-gate.md#84-ordering-at-the-manufacturer-up-to-the-cart-the-owner-orders-and-pays).

### Own part

A part nobody sells: a board of your own, a part from the bin, something made by hand. Its parts entry comes from its
project or from your notes.
Handbook: [4.5 Own parts](../handbook/04-parts-database.md#45-own-parts).

### Parts database

The folder `hardware/parts/`, one parts entry per part.
Handbook: [4 The parts database](../handbook/04-parts-database.md).

### Parts entry

One JSON file per part, named by its LCSC number or its manufacturer part number. It holds what the datasheet says:
pins and their roles, limits, parameters.
Handbook: [4 The parts database](../handbook/04-parts-database.md),
[4.1 Fields](../handbook/04-parts-database.md#41-fields).

### Placement plan

The table `[place]` of the board file and the tables beside it. It says where each part sits, turned how and on which
side. SYNC.plan holds the board to it.
Handbook: [7.4 The placement plan](../handbook/07-pcb.md#74-the-placement-plan).

### Planned maker

The maker a board is planned for: `[cart] maker`, JLCPCB without it. Its checks fail. Those of the other makers of
`[cart] makers` warn.
Handbook: [8.4 Ordering at the manufacturer (up to the cart; the owner orders and pays)](../handbook/08-release-gate.md#84-ordering-at-the-manufacturer-up-to-the-cart-the-owner-orders-and-pays).

### Project scripts and agents

A project's own scripts and agents, registered in edakit.toml with what they read and write. edakit runs each at its
place in the flow.
Handbook: [8.6 Project scripts and agents](../handbook/08-release-gate.md#86-project-scripts-and-agents).

### Proposal

A rule or a feature that a project asks edakit for. The skills propose-rule and propose-feature file it as an issue.
An Action triages the repository owner's proposals; an issue by someone else is welcome and reaches it once the owner
posts a sealed proposal there.
Handbook: [11.6 When edakit falls short: feature proposals](../handbook/11-working-with-claude.md#116-when-edakit-falls-short-feature-proposals),
[14.4 From a finding to a rule](../handbook/14-design.md#144-from-a-finding-to-a-rule).

### Protocol

The report of a gate run. It lists every stage and every finding, then the decision and its reasons.
Handbook: [8.3 The decision](../handbook/08-release-gate.md#83-the-decision).

### Release

A gate run that ended RELEASED. Every stage ran and passed, every warning is accepted, every sign-off is signed for the
current hashes. Its files are what the maker gets.
Handbook: [8.3 The decision](../handbook/08-release-gate.md#83-the-decision).

### Requirement

What the circuit must do, as the maker, a user or a chosen standard states it, numbered `R-…` in the requirements
file. Nothing edakit or the design derived is one. It is bound as
`must`, `should` or `may`.
Handbook: [3.6 Requirements](../handbook/03-hardware-graph.md#36-requirements).

### Requirements file

What the circuit must do, usually `hardware/requirements.toml`. It holds needs and requirements, each with its
evidence.
Handbook: [3.6 Requirements](../handbook/03-hardware-graph.md#36-requirements),
[10.4 The requirements file](../handbook/10-reference.md#104-the-requirements-file).

### Scenario

A case the simulation runs, in `hardware/sim.json`: a supply, a load and the states the circuit must reach.
Handbook: [5.2 Scenarios](../handbook/05-simulation.md#52-scenarios).

### Schematic file

`hardware/schematic.toml` says how the schematic is laid out and drawn.
Handbook: [10.3 The schematic file](../handbook/10-reference.md#103-the-schematic-file).

### Severity

How much a finding weighs. An `error` blocks `edakit check`. A `warning` must be accepted in the sign-off file before
a release. A `pending` finding blocks the release and cannot be accepted. A `note` is information.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Sign-off

A person or a reviewer agent signs a manual check, bound to the hash it covers. A change of what it covers voids it.
Handbook: [8.2 Hashes and sign-offs](../handbook/08-release-gate.md#82-hashes-and-sign-offs).

### Sign-off file

`hardware/signoff.json` holds the sign-offs and the warnings accepted for the release.
Handbook: [8.2 Hashes and sign-offs](../handbook/08-release-gate.md#82-hashes-and-sign-offs).

### Skill

A prompt that steers Claude in a project for one task, started as `/edakit:<name>`.
Handbook: [11.1 What the plugin brings](../handbook/11-working-with-claude.md#111-what-the-plugin-brings).

### Stage

One step of the gate, named by a letter. P checks parts, G the graph, E the simulation, S the schematic, L the board
and F the manufacturing files.
Handbook: [8.1 Stages](../handbook/08-release-gate.md#81-stages).

### Station

One of the two results edakit leads to. The circuit is the graph, its checks, the simulation, the drawn schematic
and the hand-over. The board is the schematic in the EDA program, the PCB, the manufacturing files and the order. The
circuit is a result on its own, for a hand-wired build or a drawing in a document.
Handbook: [6.5 Drawn without EasyEDA](../handbook/06-schematic.md#65-drawn-without-easyeda),
[14.1 Roles](../handbook/14-design.md#141-roles).

### Stock snapshot

`hardware/stock.json`, written by `edakit stock`: what JLCPCB's catalogue said about each assembled part, with its
date. PARTS.stock and `edakit cost` read it offline.
Handbook: [4.2 Finding parts](../handbook/04-parts-database.md#42-finding-parts).

### Tool chain

The EDA program the boards are drawn in: EasyEDA Pro or KiCad. The key `toolchain` in edakit.toml chooses it.
Everything else is the same for both.
Handbook: [16 KiCad as the tool chain](../handbook/16-kicad.md).

### Topic

The part of a code that one domain switches on or one acceptance names. `REQ.missing:cc` is the USB-C termination.
Handbook: [14.2 The catalog: engines, codes, data and domains](../handbook/14-design.md#142-the-catalog-engines-codes-data-and-domains).

### Variant

A project of its own, with its own edakit.toml, in a folder below the main project.
Handbook: [10.1 edakit.toml](../handbook/10-reference.md#101-edakittoml),
[10.4 The requirements file](../handbook/10-reference.md#104-the-requirements-file).

### Working agreements

The numbered rules of section 11.4. Every session in an edakit project starts with them.
Handbook: [11.4 Working agreements that proved themselves](../handbook/11-working-with-claude.md#114-working-agreements-that-proved-themselves).
