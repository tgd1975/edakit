# The build guide: soldering and first power step by step – and a layout that can be measured

Status 2026-11-11: proposed, nothing decided, nothing built. Asked for by the owner after the bell's two through-hole
boards arrived bare and a session wrote their build guide: "schreib im edakit projekt ein konzept, dass dieses aufbau
dokument beschreibt ... und reg dort an, dass im pcb layout design vielleicht messbarkeit berücksichtigt werden sollte
... uu ein skill, ein agent ... keine ahnung ... überlegt dir im konzept auch, welcher sprachstil verwendet werden
soll ... und wie und wann das ganze gemacht werden soll". Written against main at `ecd94952`.

The experience behind it is two documents written by hand: pytree's `docs/aufbau.md` and the bell's `docs/aufbau.md`
with its script `docs/aufbau.py` (automatic_christmas_bell, boards tht and esp32tht, ordered bare on 2026-11-02,
delivered on 2026-11-11). Every number below is the bell's.

## The short answer

edakit ends at two lists. `hand_assembly.md` says which parts are fitted by hand (handbook 8.4), and section 6 of the
protocol says what the acceptance checks on a delivered board (M-4, handbook 8.5). Between them lies the build: which
part goes in when and which way round, what is measured before the board sees power, how it gets power the first time,
and what the readings must be. Nothing in edakit holds that today. It existed in the session's head and in the
owner's, and both projects wrote it down by hand.

The bell's guide took one session with more than twenty requests and corrections by the owner. Most of its content
came from data edakit already holds, and most of the corrections were about the same few things: who the reader is,
what state the board is in at each step, and where a probe can be put safely. The proposal has three parts:

1. **The measuring plan as data.** A command derives from the graph what can be measured on the assembled board –
   unpowered and powered –, between which points and with which reading.
2. **The build guide as a document of the project**, drafted from that plan and the parts list by a skill, in the
   register below, with pictures edakit draws.
3. **Measurability as a matter of the layout.** The plan goes into the hand-over, a check says where a point of the
   plan cannot be reached or only next to a foreign net, and the layout review (M-5) judges the rest.

Measured against the yardstick (design as text): the build order, the measuring points and the expected readings
exist today only in someone's head. The plan puts them into the repository as text an LLM can write and check.

## What the bell's guide contains

485 lines of Markdown in the project's language, German, a PDF of 16 pages built from it, 13 pictures of measuring
points and three of resistor colour bands, all drawn by a script of 413 lines. One guide covers both boards; what
holds for one only is tagged **[THT]** or **[ESP32 THT]**.

| Part | What it says | Where its content came from |
| --- | --- | --- |
| Parts | one row per kind of part with designators, value and the supplier's number on the bag; one cell where both boards take the same part | graph, parts entries, the order |
| Colour bands | a drawn resistor per value and where it goes | parts entries (`value_ohm`, `tolerance`) |
| Polarity | the three parts that matter, each with the rule in the board's own terms: "long leg left, at the printed +" | parts entries, the pads' nets in the footprint geometry, the silkscreen |
| Tools | iron, meter with its four modes, what is needed for the first power | by hand |
| Order | a table of the steps with the state of the board at each: module in or out, USB on or off, servo on or off | by hand: flat parts first, power last |
| Steps 1–7 | one short section per group of parts | by hand |
| Measuring without power | supply rail against ground, every LED path by diode test, every button, every line from the module's socket to the connector – each with a picture, the points and the reading, and what a wrong reading means | graph: what lies between two nets when the module is out |
| Measuring with power | the rails' voltages with the module in | parts entries, simulation |
| Firmware and test | upload, what the board does, in the order the tester sees it | the firmware's source |
| When something fails | a table: what you see, the likely cause | by hand |
| Test record | every check as a row to tick, with a field for the reading, one sheet per board | the sections above |

The pictures are the release's board views with the fitted parts drawn over them. A measuring point is a pad of the
footprint geometry (`boards/<b>.geometry.json`) turned into board coordinates with the placement plan, so no point is
placed by eye. The script checks that every labelled point lies on the net its label names, and stops otherwise: the
first version of the guide had named the wrong socket contact for 3V3, and the check was added after that.

The PDF names the boards' revisions, the commit and its date on the first page and in the header and footer of every
page, with a mark when the guide was not committed. A printed sheet on the bench says which state it describes.

## What the owner corrected

These are the lessons, each with the correction that taught it. They are the rules a skill would carry.

- **The reader knows electronics.** A hobby maker who understands what is written but does not know a colour code by
  heart. A review "for understandability" added how to read colour bands, what a pull-down is for and what "OL" means.
  The owner struck all of it: "wir machen keine schulungsunterlage". Lookup aids stay – the band pictures, the
  supplier's numbers –, explanations go.
- **No framing.** The opening that told what the guide would cover went ("jo eh ... streichen"), and so did every
  reference to the decision log: irrelevant while soldering.
- **The state of the board at every step.** "mir ist auch nicht klar, wann ich das modul reinstecken soll un wann
  nicht und wann ich das teil an die stromversorgung hängen soll und wann nicht". Since then every step opens with one
  line: module in or out, power on or off.
- **What a measuring step tests, before how.** One or two sentences after each heading: what is tested, with or
  without the module, with or without power.
- **A net's name is not a voltage.** "wie kann ich 5V messen, wenn kein modul drinnen ist?" The table said "5V against
  GND" for a resistance reading on an unpowered board. The guide now names the meter's mode with every step.
- **Pictures show the board as it is at that step.** The first measuring pictures showed the bare board; the
  measuring happens after assembly.
- **The reader has the board in hand.** A full-width placement drawing with values was offered and refused: the
  designators are printed on the board.
- **A record to tick.** "ein prüfprotokoll noch einfügen ... also am ende vom testkapitel die ganzen punkte mit
  abhaken".
- **A warning is a reminder.** Asked for where a slipped probe can damage a part; the first version explained two
  failure mechanisms in eight lines. "die persona weiß das prinzipiell ... nur zur erinnerung ... viel knapper
  halten". It is two lines now.
- **Remove a hazard before warning of it.** The powered 5 V reading was taken at the servo header, where the 5 V pin
  sits 2.54 mm from ground on one side and from a 3.3 V pin of the module on the other. It moved to the legs of a
  load resistor 15.5 mm apart. That is the layout's matter, below.

A review with fresh eyes also found what the writing session had not: "senkrecht" read as mounted upright, the "+"
printed beside every LED was never mentioned, the sockets of the Nano board are not in the order of the LEDs, and the
countdown was described differently from what the firmware does.

## The register of a build guide

`docs/style.md` covers edakit's own documentation. A build guide is a project's document in the project's language,
so it needs a register of its own, short enough to stand in the skill:

- **Reader:** someone who solders and measures, understands a circuit and has the board, the parts and this guide on
  the bench. The guide is read one step at a time, between two actions.
- **Voice:** the reader addressed directly – "du" in a German project, "you" in an English one –, in the imperative
  or the plain present. One action per sentence, in the order it is done.
- **Content of a step:** what to take, where it goes, which way round, how to tell it is right. Then the next step.
- **Left out:** why the circuit is as it is, what a part is for, definitions of terms and symbols, the project's
  history, decision and requirement IDs, what the guide is about to say.
- **Kept:** lookup aids – a table, a picture, a number the reader would otherwise look up.
- **Directions:** fixed once at the top – the printed side, with one edge named – and used with the same four words
  throughout. A part is named as it is printed on the board.
- **State:** one line at the start of a step that changes or relies on it – what is plugged in, what is powered.
- **Readings:** a table with the two points, the meter's mode, the reading with its tolerance and what a wrong reading
  means. A reading names its unit; a net's name is never used where a voltage could be understood.
- **Bold:** only what breaks something when done wrong.
- **Warnings:** one or two lines naming the hazard and what to do instead, only where a slip costs a part.
- **Pictures:** the board as it looks at that step, never a state the reader has already left.

Two rules edakit's documentation has apply unchanged: one word per thing, and a number with its unit.

## Measurability in the layout

Building the bell's boards showed where the layout made measuring harder than it had to be. The owner asked: "hätten
wir beim pcb design testpunkte einbauen können/sollen? etwas, dass uns jetzt die arbeit leichter macht?" On a
through-hole board dedicated test points were not what was missing. What was:

- **Names at the module's sockets.** Ten nets – eleven on the ESP32 board – are measured at the female headers the
  module plugs into. The print names none of them, so the guide counts contacts in a picture, and on the Nano board they
  are not in the order of the LEDs.
- **A ground to clip to.** Every reading uses ground, and the only place is a 2.54 mm header pin.
- **A rail that is reachable from one side only.** The T-Display's 3.3 V comes out at one socket contact. With the
  module in, it can be probed only at the solder joint on the back.
- **A powered point between two foreign nets.** The 5 V pin of the servo header lies between ground and the signal
  pin, which goes to a 3.3 V pin of the module on the ESP32 board. A probe across two pins shorts the supply or puts
  5 V on that pin.
- **One footprint marked differently from its neighbours.** The red LED's footprint has its square pad on the anode,
  the others on the cathode; the guide has to say so.

All five are cheap at layout time and were found on the bench. Four are in the bell's list for a next revision
(`variants/README.md`); the fourth of the list above was found when the owner asked for the warning.

Where a safe point was needed afterwards, the footprint geometry answered: the first candidate, a load resistor's
leg, lies 3.5 mm from the pad of a button's pull-down on the ESP32 board; its neighbour has no foreign pad closer than
4.5 mm on either board. That is a computation, not a judgement, and it can run before the order.

### The measuring plan

The plan is the list of what the guide measures, as data: an ID, the two nets, whether the module is in, whether
power is on, the meter's mode and the expected reading. The bell's has four groups, and each follows from the graph:

- a supply rail against ground without power: what lies between them when the module is out (two 100 Ω load resistors
  in parallel, 50 Ω) – a short and a missing part both show;
- a path from a module pin through a series resistor and an LED to ground: a diode test, forward and reversed;
- a button with its pull resistor: open and pressed;
- a line from a module pin to a connector pin: continuity, and none to its neighbours.

With power on, each rail's voltage with its tolerance. A project adds what its circuit needs; the derived entries are
a start, not the limit.

The plan has two readers. The guide's tables and pictures are drawn from it. The layout is checked against it.

### In the hand-over, as a check, in the review

- **Hand-over.** The plan belongs to what the circuit hands to the layout (`edakit handover`): which nets are
  measured, which of them under power.
- **A check** over the board file and the footprint geometry, for every net of the plan: is there a place a probe
  reaches on the assembled board – a through-hole pad or lead on the side that stays free, a header pin, a test pad
  (`own.what = "copper"`) – and, for a net measured under power, how far is the nearest pad of another net. On a board
  of surface-mount parts only, the first question has no answer without test pads; today nothing says so before the
  order.
- **Silkscreen.** Names beside the contacts of a module's sockets and beside test pads; `silk apply` already places
  test points' labels first (handbook 7.7).
- **The review.** The layout reviewer (M-5) gets the plan and judges what a number does not: whether a point can be
  reached with the module plugged in, whether the board can lie flat while it is measured.

Whether the check is an error, a warning or a note, and from which distance on, is open (question 2). The bell gives
three numbers, not a rule: 2.54 mm was the hazard, 3.5 mm was avoided, 4.5 mm was accepted.

## A skill, a command, an agent

The owner left open what does the work. The parts differ in kind, so the proposal splits them:

| Part | Kind | Why |
| --- | --- | --- |
| The measuring plan, the pictures, the check that a labelled point lies on its net | code – a command | computed from the graph, the board file and the geometry; the bell's script shows the size |
| The guide's text, its order, the rounds with the owner | a skill, `build-guide` | prose in the project's language, in the register above, written in the session that talks to the owner |
| Measurability | a catalog code, a line in the hand-over, a point of the layout review | belongs to the layout, before the order |
| Reading the finished guide as the builder | an agent, optional | fresh context: it does not know the board, as the reader does not |

The agent is the weakest of the four. The review that found the ambiguous instructions also added the explanations
the owner then struck. A reviewer with a fixed brief – the reader of the register above, findings only for an
instruction that can be misread or is wrong against the data, no additions – would keep the first and not do the
second. Whether that needs an agent or a section of the skill is open (question 3).

## When and how

| When | What | Who |
| --- | --- | --- |
| The circuit is handed over | the measuring plan is derived and goes into the hand-over | the circuit's session |
| A layout round | the check on reach and distance; the names at sockets and test pads | the layout's session |
| The layout review (M-5) | the reviewer judges the plan against the board | pcb-reviewer |
| The release | the guide's draft: parts, polarity, order, measuring tables and pictures from the released run | the skill |
| The boards are at the maker | the owner reads the draft; nothing can change on the board any more, so the guide can be finished while waiting | the owner, the skill |
| Delivery | the first board is built with the guide; what the bench shows goes back into it | the owner, the skill |
| Every board | the test record is filled in; signed, it is the evidence for M-4 | the owner |

The bell's guide was written on the day the boards arrived, nine days after the order. All of it but the corrections
from the bench could have been ready by then.

**Which boards.** A board that comes bare gets the whole guide. A board the maker assembles gets the parts fitted by
hand (`hand_assembly.md`) and everything from the measuring on. A project with variants gets one guide, with tags
where the boards differ.

**Kept current.** The values a guide quotes can follow the design data the way other documents do (`[docs] files`,
handbook 6.6); the pictures are drawn again by the command. The guide names the boards' revisions and its commit.

**The test record and the acceptance.** The record's rows and section 6 of the protocol list partly the same checks.
One list should feed the other, so that the acceptance steps of a requirement appear in the record and a filled-in
record is what M-4 signs.

**The PDF.** The bell's script turns the Markdown into HTML and prints it with Chromium. Whether edakit should build
a PDF at all is open (question 5).

## Steps

None is decided. In the order they would build on each other:

| Step | What |
| --- | --- |
| BG.1 | The measuring plan from the graph: the four groups above, the powered rails; written as a file of the run, listed in the hand-over |
| BG.2 | The pictures: the board as assembled, a measuring point from the geometry, the check that it lies on its net |
| BG.3 | The skill `build-guide` with the register, drafting the guide from BG.1, the parts list and BG.2; the test record |
| BG.4 | The check on reach and distance, its catalog entry; the names at sockets and test pads in the silkscreen |
| BG.5 | The layout reviewer's point; the record as evidence for M-4 |
| BG.6 | The bell's guide rebuilt with BG.1 to BG.3 and compared with the one written by hand |

BG.6 is the test: what the generated draft lacks against the hand-written guide is the list of what the skill still
has to ask or write.

## Open for the owner

1. **The plan's home.** Derived on every run and never edited, or a file of the project that starts derived and is
   then kept by hand. Recommended: derived, with the project's additions in the graph beside the nets they concern.
2. **The check's grade and number.** Recommended: a note for a net without a reachable place, a warning for a net
   measured under power with a foreign pad closer than a distance to be set from more than one board – not an error.
3. **A reviewing agent** or a section of the skill. Recommended: a section of the skill first; an agent once a second
   project shows the review is worth a session of its own.
4. **The register's home.** In the skill only, or also as a page of the handbook a project can read. Recommended: the
   skill; the handbook gets a pointer.
5. **The PDF.** edakit builds it, or it stays a project's script. Recommended: it stays the project's until a second
   project wants one; the header with revision and commit is then the part worth sharing.
6. **The record and M-4.** Whether a filled-in test record is the acceptance's evidence. Recommended: yes, one sheet
   per board, named in M-4's note.
