"""edakit command line. Every command reads the project's edakit.toml (see handbook/10-reference.md).

    edakit check                     stages P/G: rule checks on the graph (offline, < 1 s)
    edakit rules [CODE ...]          the engines and the codes of the catalog
    edakit explain CODE ...          rule, why, fix and sources of a code (LIM.v, REQ.missing …)
    edakit graph show NAME           one part or net: what the graph and its parts entry say, the findings on it
    edakit mutate [--sim]            mistakes built into a copy of the design one at a time: what no code catches
    edakit graph json [--write|--check]   the resolved graph with pin numbers; beside a TOML graph hardware/graph.json,
                                     --check: drift (pre-commit hook)
    edakit graph convert [--dry-run] a JSON graph moved to hardware/graph.toml once, its sign-offs carried over
    edakit block list|show|add       building blocks with checked parts into the graph
    edakit part import LCSC [--update]   symbol pins and footprint of an LCSC number from the library – no EasyEDA
    edakit part lint [KEY ...]       every parts entry held to the schema of its kind (catalog/kinds.toml)
    edakit part add [KEY] [--update] | sign KEY --by NAME   entries of edakit's parts library: copied in, signed
    edakit part diff OLD NEW         how a new footprint maps onto the old one before a swap (offline)
    edakit part fetch KEY [--url U] | --all   a part's datasheet PDF, kept beside the project and checked to be of it
    edakit part search "KEYWORDS"    JLCPCB's parts catalogue: LCSC number, class, stock – no EasyEDA
    edakit part datasheet|own        own parts: a board of an edakit project as a part in another project
    edakit part footprint KEY [--write]   a library footprint as data in the parts entry (footprint_data) – offline
    edakit part build KEY [--write]  the project's copy in EasyEDA built from the entry's footprint data
    edakit stock [--refresh]         what JLCPCB says about the assembled parts, as a dated snapshot (check PARTS.stock)
    edakit cost [--json F]           the order for `quantity` boards from BOM, board and the dated fee table
    edakit order [--out DIR]         the assembler's BOM, a cart per other supplier, the hand-assembly list (PARTS.supplier)
    edakit inventory [QUERY ...]     your parts on hand (edakit.local.toml) against the hand-soldered parts; QUERY: rows;
                                     template FILE: a new empty inventory as .md, .xlsx or .ods
    edakit order check               the supplier's cart as the skill cart read it back, against the basket (ORDER.basket)
    edakit cart fields|prepare|check|confirm|actual   the order at the maker: its form from [order], the job of the skill
                                     cart, ORDER.form to ORDER.review on what it brought back, the maker's confirmations
                                     after the order (M-2 on --sign), the real cost (never orders, never pays)
    edakit cart compare              the quotes of every maker of [cart] makers side by side: price, parts, lead time, check
    edakit sim                       stage E: ngspice operating points of all scenarios (offline, seconds)
    edakit docs [--write]            values quoted in documents and schematic notes: DOCS.quote for stale ones, --write fills in
    edakit firmware [--check]        the board's firmware contract as JSON from the graph; --check: drift (opt-in)
    edakit req [ID ...]              what the circuit must do: needs and requirements with status, binding, evidence;
                                     with an ID its chain – from where, the requirement, what verifies it (opt-in)
    edakit scripts [stamp NAME ...]  the project's scripts: about, state (current, outdated, never run), the order;
                                     stamp records the run of scripts that ran by hand (hardware/scripts.lock)
    edakit run NAME ...              runs project scripts in their order and records their runs – an easyeda script
                                     under the EasyEDA claim. pcb place|parts|plan|apply, route all, silk apply|preview
                                     and gate run the outdated input scripts they read first (--no-scripts: none)
    edakit handover                  what the circuit hands over to the layout: state, sign-offs, layout requirements
    edakit schematic create|check|copy|layout
    edakit schematic draw            the schematic as SVG from graph and parts database – no EasyEDA (offline);
                                     labels, or wired through by style in the schematic file
    edakit pcb dump|plan|place|parts|nets|apply|tooling|pour|autolayout|takeover
    edakit perfboard [--board B]     the plan of a hand-wired board on a perfboard: its nets against the graph, grid,
                                     bodies, wires; top and bottom view, cut, build and test lists (offline)
    edakit route all|read|dsn|route|check|apply|verify|pours|reload|drc|save
    edakit route fill                the pours already in the PCB filled one per call, tooling holes set again –
                                     after `route pours` stopped with "no-copper" – the PCB reloaded first (M-13)
    edakit route diagnose [--net N]  why each open connection is open: walled in, blocked, or a free way (offline)
    edakit silk apply|check|preview
    edakit export                    PDFs, Gerber, BOM, CPL, netlist and a project copy to <artifacts>/export
    edakit gate [--eda]              release gate with test protocol and manufacturing files
    edakit release current|withdraw RUN --reason T|verify FILE…   the one current release, the files to upload
    edakit release publish [--draft] [--dry-run] [--tag T] | --built T   the order files of every board's current
                                     release as a GitHub release (gh); --built: a board of it works
    edakit fab --board B --out DIR   stages L/F for one board (the gate calls it)
    edakit fab diff RUN_A RUN_B      where the manufacturing files of two gate runs differ (raster, drill, BOM, CPL,
                                     the order settings of [order])
    edakit lock [status|claim|release|yield CHAT]   share EasyEDA between parallel Claude sessions
    edakit proposal template|seal|verify   a rule or feature proposal for the edakit repository, sealed with its SHA-256
    edakit doctor                    Node, easyeda-mcp-pro, bridge, EasyEDA process, ngspice, Freerouting
    edakit convert [--write]         graph, parts entries and sign-off file into the form of the restructuring
    edakit domains [--review R]      the project's domains (core, usb, radio …): on, off, suggested; with --review the
                                     questions of the enabled domains for the electrical, regulatory or pcb review

Exit codes everywhere: 0 = ok, 2 = findings, 1 = error. `edakit lock`, `edakit run` of an easyeda script: 3 = another
session holds EasyEDA. `edakit cart check`: 3 = ORDER.form to ORDER.finish passed, the regulatory review of the order (ORDER.review) is open.
`route all|drc` and `silk apply|check`: 3 = the DRC's only item is "Import Changes" and schematic = PCB – EasyEDA
waits for the import acknowledgement (Design → Import Changes once).
"""

from __future__ import annotations

import argparse
import sys

DSL_ACTIONS = ("fmt", "derive", "sysml", "kerml")   # `edakit graph` of the explorative DSL ([beta] dsl)
DSL_OPTIONS = ("--to", "--out", "--map", "--set", "--part")   # its options of graph and block add


def dsl_words(argv):
    """True when a command line names something of the explorative DSL – `lsp`, an action of DSL_ACTIONS after
    `graph`, and after `graph` or `block` `--to circuit`, `--to toml` or another option of DSL_OPTIONS: only then the
    parser knows them (build_parser(dsl=True)); every other command line is parsed, and refused, as edakit without the
    DSL. The other commands' own --out stays theirs."""
    argv = list(argv)
    if argv[:1] == ["lsp"]:
        return True
    if argv[:1] not in (["graph"], ["block"]):
        return False
    if argv[:1] == ["graph"] and any(a in DSL_ACTIONS for a in argv[1:2]):
        return True
    for i, a in enumerate(argv):
        name, eq, value = a.partition("=")
        if name == "--to":
            value = value if eq else (argv[i + 1] if i + 1 < len(argv) else "")
            if value in ("toml", "circuit"):
                return True
        elif name in DSL_OPTIONS:
            return True
    return False


def _common(p):
    p.add_argument("--config", help="path to edakit.toml (default: search upwards from the current directory)")
    p.add_argument("-v", "--verbose", action="store_true", help="show the MCP traffic")


def _no_scripts(p):
    p.add_argument("--no-scripts", action="store_true", help="run no project script first – the step reads the files "
                                                             "as they are (handbook 8.6)")


def dsl_used(args):
    """The command of the explorative DSL a parsed command line runs – "edakit graph fmt", "edakit graph convert --to
    circuit", … –, or None: what a project without [beta] dsl = true refuses."""
    if args.command == "graph":
        if args.action in DSL_ACTIONS:
            return f"edakit graph {args.action}"
        options = [o for o, on in (("--to circuit", args.to == "circuit"), ("--map", args.map), ("--out", args.out))
                   if on]
        return " ".join(["edakit graph", args.action, *options]) if options else None
    if args.command == "block" and (args.set or args.part):
        return "edakit block add --set/--part"
    return None


def build_parser(dsl=False):
    """The command line's parser – edakit's without the DSL; dsl=True adds the explorative DSL's actions, options and
    `lsp`, hidden from the help (dsl_words decides, edakit/beta.py refuses them without [beta] dsl = true)."""
    from .version import version
    ap = argparse.ArgumentParser(prog="edakit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"edakit {version()}",
                    help="the version – from a git checkout away from its tag with the commit")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("version", help="what runs, what the plugin installed per scope, the newest version and what "
                                       "changed since – its When updating lines first –, where the project pins edakit")
    p.add_argument("action", nargs="?", choices=["pin", "unpin"], help="pin: one version in every edakit.toml "
                                                                     "([project] edakit = \"==x\") and every call in CI "
                                                                     "and scripts; unpin: follow the updates again")
    p.add_argument("target", nargs="?", help="pin: current (the edakit in effect here, default), latest or a number")
    p.add_argument("--write", action="store_true", help="pin, unpin: write the changes (default: list them)")
    p.add_argument("--offline", action="store_true", help="read no tags and no changelog from GitHub")
    p.add_argument("--json", help="write the state and the findings as JSON")

    p = sub.add_parser("hook", help="the project's pre-commit hook: edakit's block written or renewed (install), what "
                                    "is missing (check), the steps of the staged configurations (run – the block calls it)")
    p.add_argument("action", nargs="?", default="check", choices=["check", "install", "run"])

    p = sub.add_parser("check", help="rule checks on the graph (stages P, G)")
    p.add_argument("--release", action="store_true", help="also fail on open sign-offs")
    p.add_argument("--json", help="write the findings as JSON")
    p.add_argument("--coverage", action="store_true", help="list what went unchecked for lack of data, per code")
    _common(p)

    p = sub.add_parser("rules", help="the engines and codes of the catalog")
    p.add_argument("ids", nargs="*", help="codes (LIM.v); an old check ID (G-4) names the codes replacing it; default: "
                                          "the list")

    p = sub.add_parser("explain", help="rule, why, fix and sources of a code")
    p.add_argument("ids", nargs="+", help="codes, e.g. LIM.v REQ.missing (an old ID such as G-4 names its codes)")

    p = sub.add_parser("graph", help="what the graph says about one part or net; the resolved graph as JSON; a JSON "
                                     "graph moved to TOML")
    p.add_argument("action", choices=["show", "json", "convert", *(DSL_ACTIONS if dsl else ())],
                   **({"metavar": "{show,json,convert}"} if dsl else {}))
    p.add_argument("name", nargs="?", help="show: a designator (U1) or a net name (LED_CLK)")
    p.add_argument("--json", help="show: write the view and its findings as JSON")
    p.add_argument("--write", action="store_true", help="json: write the resolved graph beside a TOML graph "
                                                        "(hardware/graph.json)")
    p.add_argument("--check", action="store_true", help="json: compare the generated file with the graph, write "
                                                        "nothing; exit 2 on drift")
    p.add_argument("--dry-run", action="store_true", help="convert: print what would change, write nothing")
    if dsl:     # the explorative DSL's (docs/dsl/README.md): parsed, never shown
        p.add_argument("--to", choices=["toml", "circuit"], default="toml", help=argparse.SUPPRESS)
        p.add_argument("--out", metavar="DIR", help=argparse.SUPPRESS)
        p.add_argument("--map", metavar="FILE", help=argparse.SUPPRESS)
    p.set_defaults(files=[], to="toml", out=None, map=None)
    _common(p)

    if dsl:
        sub.add_parser("lsp")                     # the explorative DSL's language server

    p = sub.add_parser("domains", help="the domains of the project: on, off, suggested; the reviewers' questions")
    p.add_argument("--review", choices=["electrical", "regulatory", "pcb"], help="the questions of the enabled domains "
                                                                                "for this review")
    _common(p)

    p = sub.add_parser("convert", help="graph, parts entries and sign-off file into the form of the restructuring")
    p.add_argument("--write", action="store_true", help="write the converted files (default: list them)")
    _common(p)

    p = sub.add_parser("mutate", help="mistakes built into a copy of the design one at a time: what no code catches")
    p.add_argument("--sim", action="store_true", help="judge each mistake with the simulation as well (slower)")
    p.add_argument("--json", help="write every mistake with what caught it as JSON")
    _common(p)

    p = sub.add_parser("block", help="building blocks: list, show, or add one to the graph")
    p.add_argument("action", choices=["list", "show", "add"])
    p.add_argument("name", nargs="?", help="block name (edakit block list)")
    p.add_argument("--as", dest="instance", help="add: name of this instance, used for its nets and labels")
    p.add_argument("--connect", action="extend", nargs="+", metavar="PORT=NET", help="add: join ports to nets")
    p.add_argument("--without", action="extend", nargs="+", metavar="DES", help="add: leave out these optional parts "
                                                                                "of the block")
    p.add_argument("--board", help="add: board of the new parts (needed with several boards)")
    if dsl:     # the explorative DSL's derivations (docs/dsl/derivations.md)
        p.add_argument("--set", action="extend", nargs="+", metavar="PARAM=VALUE", help=argparse.SUPPRESS)
        p.add_argument("--part", action="extend", nargs="+", metavar="DES=KEY", help=argparse.SUPPRESS)
    p.set_defaults(set=None, part=None)
    p.add_argument("--file", help="a block from this JSON file instead of the library")
    p.add_argument("--dry-run", action="store_true", help="add: show what would change, write nothing")
    _common(p)

    p = sub.add_parser("part", help="the library's data of an LCSC number, a footprint swap compared, datasheets, "
                                    "a catalogue search, own parts, own footprints as data, entries of edakit's "
                                    "parts library")
    p.add_argument("action", choices=["import", "diff", "fetch", "search", "datasheet", "own", "footprint", "build",
                                      "lint", "add", "sign"])
    p.add_argument("source", nargs="?", help="import: the LCSC number; diff: the old part; fetch, footprint, build: "
                                             "the parts-entry key; search: the keywords; own: the board's project (its "
                                             "directory or edakit.toml); add, sign: the library entry (edakit/parts/)")
    p.add_argument("new", nargs="?", help="diff: the new part (LCSC number or parts-entry key)")
    p.add_argument("--update", action="store_true", help="import: fill in what the existing entry lacks; add: take "
                                                         "the library's version over the project's copy")
    p.add_argument("--by", help="sign: the owner's name")
    p.add_argument("--url", help="fetch: try this URL first")
    p.add_argument("--all", action="store_true", help="fetch: every parts entry without a kept datasheet")
    p.add_argument("--json", help="diff: write the comparison as JSON; search: the hits")
    p.add_argument("--basic", action="store_true", help="search: only Basic and preferred parts")
    p.add_argument("--min-stock", type=int, help="search: at least this assembly stock")
    p.add_argument("--limit", type=int, default=25, help="search: hits asked of the catalogue (default 25)")
    p.add_argument("--connector", action="append", help="datasheet: a connector of the board, in the order of the "
                                                        "part's pins (repeat for several; none: renew the datasheets)")
    p.add_argument("--name", help="the part's name (mpn) – datasheet: default the project name; own: which datasheet")
    p.add_argument("--board", help="footprint: the board whose dump to read (default: each made board); build: the "
                                   "board whose template holds the carrier (default: the only made board)")
    p.add_argument("--write", action="store_true", help="footprint: write the data into the parts entry; build: "
                                                        "rebuild the copy in EasyEDA (default: show only)")
    _common(p)

    p = sub.add_parser("stock", help="ask JLCPCB about every assembled part and write the stock snapshot (PARTS.stock)")
    p.add_argument("--board", help="only the parts of this board")
    p.add_argument("--refresh", action="store_true", help="ask about every part again, not only missing or old ones")
    p.add_argument("--lcsc", nargs="+", metavar="C", help="print what JLCPCB says about these parts, write nothing "
                                                          "(part search; no project needed)")
    _common(p)

    p = sub.add_parser("cost", help="estimate the order: PCB, PCBA fees, parts, extras, shipping, VAT; drivers, budget")
    p.add_argument("--board", help="only this board (no shipping, extras, VAT)")
    p.add_argument("--json", help="also write the estimate as JSON to this file")
    _common(p)

    p = sub.add_parser("order", help="assembler's BOM, one cart per other supplier, hand-assembly list for all sets; "
                                     "check: the supplier's cart as the skill cart read it back (ORDER.basket)")
    p.add_argument("action", nargs="?", choices=["check"], help="check the supplier's cart against basket.json")
    p.add_argument("--out", help="folder for the files (default: <artifacts>/order)")
    p.add_argument("--supplier", help="check: the supplier whose cart is checked (default: lcsc)")
    p.add_argument("--with", dest="with_", action="append", metavar="CONFIG",
                   help="another project's edakit.toml whose carts go into the same files (several times)")
    _common(p)

    p = sub.add_parser("inventory", help="your parts on hand, named in edakit.local.toml: the project's hand-soldered "
                                         "parts and extras against them; QUERY: the rows holding every word; template "
                                         "FILE: a new empty inventory (.md, .xlsx, .ods)")
    p.add_argument("words", nargs="*", metavar="QUERY", help="words a row's ID, name or description holds – or "
                                                             "template FILE")
    _common(p)

    p = sub.add_parser("cart", help="the order at the maker: the form's fields, the job of the skill cart, its check, "
                                    "the maker's confirmations after the order (M-2), the real cost, the makers' quotes "
                                    "compared – up to the maker's cart, never further")
    p.add_argument("action", choices=["fields", "prepare", "check", "confirm", "actual", "compare"])
    p.add_argument("--board", help="the board (needed with several made boards)")
    p.add_argument("--maker", help="a maker of [cart] makers (default: [cart] maker, jlcpcb without [cart])")
    p.add_argument("--cart", action="store_true", help="check: the cart line after the cart button (cart.json)")
    p.add_argument("--from", dest="source", help="actual: a saved order page or invoice instead of the order history")
    p.add_argument("--sign", metavar="BY", help="confirm: write M-2 into the sign-off file as signed by BY – the owner's word")
    p.add_argument("--note", help="confirm: appended to M-2's note, e.g. \"requirements met: R-31\"")
    _common(p)

    p = sub.add_parser("sim", help="simulation (stage E)")
    p.add_argument("--json", help="write every single check as JSON")
    p.add_argument("--keep", help="keep netlists and ngspice output in this directory")
    _common(p)

    p = sub.add_parser("docs", help="values quoted from the design data in documents and notes (DOCS.quote)")
    p.add_argument("--write", action="store_true", help="fill in the current values")
    _common(p)

    p = sub.add_parser("firmware", help="the board's firmware contract from the graph ([firmware] in edakit.toml)")
    p.add_argument("--check", action="store_true", help="compare the committed contract with the graph, write nothing")
    _common(p)

    p = sub.add_parser("req", help="what the circuit must do: needs and requirements with status, binding and "
                                   "evidence ([project] requirements in edakit.toml)")
    p.add_argument("ids", nargs="*", help="need or requirement IDs, e.g. R-4 N-2: the chain of each (default: a list)")
    _common(p)

    p = sub.add_parser("scripts", help="the project's scripts ([scripts.<name>]): state and order; stamp records a run")
    p.add_argument("action", nargs="?", choices=["stamp"], help="stamp NAME …: the named scripts ran by hand – their "
                                                                 "stamps go into hardware/scripts.lock")
    p.add_argument("names", nargs="*", help="stamp: the scripts that ran")
    _common(p)

    p = sub.add_parser("run", help="run project scripts ([scripts.<name>]) in their order and record their runs; an "
                                   "easyeda script under the EasyEDA claim")
    p.add_argument("names", nargs="+", metavar="NAME", help="input, derive or easyeda scripts – they run in the order "
                                                            "edakit scripts shows, whatever order they are named in")
    _common(p)

    p = sub.add_parser("handover", help="the hand-over from the circuit to the layout: state, sign-offs, requirements")
    p.add_argument("--board")
    _common(p)

    p = sub.add_parser("schematic", help="generate, check, copy or lay out a schematic in EasyEDA – or draw it without")
    p.add_argument("action", choices=["create", "check", "copy", "layout", "draw"])
    p.add_argument("--board")
    p.add_argument("--schematic", help="schematic name (default: template for create/check, layout for layout)")
    p.add_argument("--source", help="copy: source schematic (default: the template)")
    p.add_argument("--target", help="copy: target schematic (default: the board schematic)")
    p.add_argument("--only", help="create: only these designators, comma-separated")
    p.add_argument("--dry-run", action="store_true", help="plan only (create: placement, layout: SVG preview)")
    p.add_argument("--reread", action="store_true", help="layout: read the symbol geometry again")
    p.add_argument("--force", action="store_true", help="layout, draw: write despite geometry conflicts")
    p.add_argument("--out", help="draw: the SVG file (default: <artifacts>/schematic_<board>.svg)")
    p.add_argument("--no-frame", action="store_true", help="draw: no sheet border and no title block in the SVG "
                                                           "(frame = false in the schematic file does the same)")
    p.add_argument("--no-pins", action="store_true", help="check: skip the per-part pin check")
    p.add_argument("--refresh-devices", action="store_true", help="create: search every LCSC number again")
    p.add_argument("--create-project", action="store_true", help="create the EasyEDA project if it is not open")
    p.add_argument("--save", action="store_true", help="save the project at the end – create and layout only when "
                                                       "the netlist equals the graph")
    p.add_argument("--json", help="check: write the differences as JSON")
    p.add_argument("--wait", type=int, default=90, help="seconds to wait for the bridge")
    _common(p)

    p = sub.add_parser("perfboard", help="the plan of a hand-wired board on a perfboard ([perfboard] in its board "
                                         "file): checked against the graph, drawn, its cut, build and test lists")
    p.add_argument("--board", help="the hand-wired board (default: every one with a plan)")
    _common(p)

    p = sub.add_parser("pcb", help="placement plan, parts and nets sync, fixed parts, tooling holes, pours")
    p.add_argument("action", choices=["dump", "plan", "place", "parts", "nets", "apply", "tooling", "pour",
                                      "autolayout", "takeover"])
    p.add_argument("--board")
    p.add_argument("--write", action="store_true", help="parts/nets: change the PCB; place, takeover: add the rows to "
                                                        "[place] (default: show only)")
    p.add_argument("--ref", help="dump: only these designators, comma-separated")
    p.add_argument("--only", help="place: only these designators, comma-separated")
    p.add_argument("--rest", action="store_true", help="place: every other part of the board without a row, or with "
                                                       "an auto row, as well – by airline length")
    p.add_argument("--verify-all", action="store_true", help="apply: compare the pads of every part with the plan")
    _no_scripts(p)
    _common(p)

    p = sub.add_parser("route", help="route with Freerouting and write the result into EasyEDA")
    p.add_argument("action", choices=["all", "read", "dsn", "route", "check", "diagnose", "apply", "verify", "pours",
                                      "fill", "reload", "drc", "save"])
    p.add_argument("--board")
    p.add_argument("--net", help="diagnose: only this net")
    p.add_argument("--passes", type=int, help="maximum Freerouting passes")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--clearance", type=float, help="copper-to-copper clearance in mil")
    p.add_argument("--no-optimizer", action="store_true", help="route only, skip Freerouting's optimiser")
    p.add_argument("--cleanup", action="store_true", help="verify: delete tracks and vias that are not planned")
    _no_scripts(p)
    _common(p)

    p = sub.add_parser("silk", help="designators where there is room, silkscreen check on the Gerber export")
    p.add_argument("action", choices=["apply", "check", "preview"])
    p.add_argument("--board")
    _no_scripts(p)
    _common(p)

    p = sub.add_parser("export", help="documentation and manufacturing files from EasyEDA")
    p.add_argument("--board")
    _common(p)

    p = sub.add_parser("gate", help="release gate: all stages, test protocol, manufacturing files")
    p.add_argument("--eda", "--easyeda", dest="eda", action="store_true",
                   help="also run S, L and F in the EDA program: EasyEDA with the bridge, or KiCad with kicad-cli "
                        "([project] toolchain); --easyeda is the old name")
    _no_scripts(p)
    _common(p)

    p = sub.add_parser("release", help="the current release: show it, withdraw a run, check the files to upload, "
                                       "publish what is ordered")
    p.add_argument("action", choices=["current", "withdraw", "verify", "publish"])
    p.add_argument("items", nargs="*", help="withdraw: the run (folder name under reports); verify: files or folders "
                                            "(their .zip and .csv files)")
    p.add_argument("--reason", help="withdraw: why the run must not be uploaded")
    p.add_argument("--draft", action="store_true", help="publish: a draft release only the account sees – no tag, no "
                                                        "guards; a test")
    p.add_argument("--tag", help="publish: the tag (default: today, YYYY-MM-DD; -2, -3 when the remote has it)")
    p.add_argument("--dry-run", action="store_true", help="publish: staging and notes in build/publish/<tag>/, nothing "
                                                          "uploaded")
    p.add_argument("--built", metavar="TAG", help="publish: a board of release TAG has been built and works – no "
                                                  "longer a pre-release")
    _common(p)

    p = sub.add_parser("fab", help="stages L and F for one board; diff: where the manufacturing files of two runs "
                                   "differ")
    p.add_argument("action", nargs="?", choices=["diff"], help="diff RUN_A RUN_B: Gerber layers, drill hits, BOM "
                                                               "and CPL rows, order settings of two gate runs compared")
    p.add_argument("runs", nargs="*", help="diff: two gate runs (folder names under reports, or their folders)")
    p.add_argument("--board")
    p.add_argument("--out", help="report folder; files go to OUT/<board>/ (required unless diff)")
    p.add_argument("--offline", action="store_true", help="only check what is already in OUT/<board>/")
    _common(p)

    p = sub.add_parser("lock", help="EasyEDA claim between parallel Claude sessions")
    p.add_argument("action", nargs="?", default="status", choices=["status", "claim", "release", "yield", "hook"])
    p.add_argument("chat", nargs="?", help="yield: the session id (prefix) of the chat to let in")
    p.add_argument("--note")
    p.add_argument("--auto", action="store_true", help="claim from a script (logged as automatic)")
    _common(p)

    p = sub.add_parser("proposal", help="rule and feature proposals for the edakit repository: template, seal, verify")
    p.add_argument("action", choices=["template", "seal", "verify"])
    p.add_argument("--feature", action="store_true", help="template: a feature proposal instead of a rule proposal")
    p.add_argument("file", nargs="?", help="seal, verify: the text (- for stdin)")
    p.add_argument("--out", help="seal: write the issue body into this file instead of stdout")

    p = sub.add_parser("doctor", help="check the tool chain")
    p.add_argument("--offline", action="store_true", help="skip the bridge part: start no server, ask no bridge")
    _common(p)
    if dsl:
        sub.metavar = "{" + ",".join(c for c in sub.choices if c != "lsp") + "}"   # lsp: the DSL's, unlisted
    return ap


def main(argv=None):
    from .config import ConfigError
    try:
        return _main(argv)
    except ConfigError as e:     # a board refused while a command runs (unknown, or bought or hand-wired for a layout command)
        print(f"edakit: {e}", file=sys.stderr)
        return 1


def _main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = build_parser(dsl=dsl_words(argv))
    if argv[:2] == ["graph", "fmt"]:
        args, rest = parser.parse_known_args(argv)
        if rest and not any(a.startswith("-") for a in rest):
            # `graph fmt --check A B`: before Python 3.13 argparse fills the positionals before the option and leaves
            # the files after it over – they are the files fmt names; no other command takes more than it declares
            if args.name is None:
                args.name, rest = rest[0], rest[1:]
            args.files = [*args.files, *rest]
        elif rest:
            parser.error(f"unrecognized arguments: {' '.join(rest)}")
    else:
        args = parser.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up at once, also when piped
    if args.command == "lock":
        from . import lock
        return lock.main(args)
    if args.command == "version":
        from . import update
        return update.main(args)
    if args.command == "hook":
        from . import hook
        return hook.main(args)
    if args.command == "rules":
        from . import catalog
        return catalog.main_rules(args)
    if args.command == "explain":
        from . import catalog
        return catalog.main_explain(args)
    if args.command == "proposal":
        from . import proposal
        return proposal.main(args)
    if args.command == "stock" and args.lcsc:
        from . import stock
        return stock.main_lcsc(args.lcsc)
    if args.command == "block" and args.action in ("list", "show"):
        from . import block
        return block.main(None, args)
    if args.command == "lsp":            # the editor's: no project needed – each file's project switches the DSL on
        from .lang import server
        return server.main(args)
    if args.command == "graph" and args.action == "fmt" and args.name:     # files named: each one's project decides
        from . import beta
        off = [f for f in [args.name, *args.files] if not beta.dsl_of(f)]
        if off:
            print(beta.refusal(f"edakit graph fmt {off[0]}"), file=sys.stderr)
            return 1
        from .lang import cli as lang_cli
        return lang_cli.main(None, args)
    from . import config
    try:
        cfg = config.load(args.config)
    except config.ConfigError as e:
        if args.command == "doctor":
            cfg, args.config_error = None, str(e)
        else:
            print(f"edakit: {e}", file=sys.stderr)
            return 1
    if args.command in ("pcb", "route", "silk", "gate"):    # the outdated input scripts a step reads run first (8.6)
        from . import scripts
        code, cfg = scripts.before_step(cfg, args)
        if code is not None:
            return code
    if cfg is not None and not cfg.dsl and (what := dsl_used(args)):   # doctor runs without a project
        from . import beta
        print(beta.refusal(what), file=sys.stderr)
        return 1
    if args.command == "check":
        from . import checks
        return checks.main(cfg, args)
    if args.command == "block":
        from . import block
        return block.main(cfg, args)
    if args.command == "part":
        from . import part
        return part.main(cfg, args)
    if args.command == "mutate":
        from . import mutate
        return mutate.main(cfg, args)
    if args.command == "convert":
        from . import convert
        return convert.main(cfg, args)
    if args.command == "graph" and args.action == "show":
        from . import graph_show
        return graph_show.main(cfg, args)
    if args.command == "graph" and args.action in DSL_ACTIONS:
        from .lang import cli as lang_cli
        return lang_cli.main(cfg, args)
    if args.command == "graph":
        from . import graph_form
        return graph_form.main(cfg, args)
    if args.command == "domains":
        from . import profile
        return profile.main(cfg, args)
    if args.command == "stock":
        from . import stock
        return stock.main(cfg, args)
    if args.command == "cost":
        from . import cost
        return cost.main(cfg, args)
    if args.command == "order":
        from . import order
        return order.main(cfg, args)
    if args.command == "inventory":
        from . import inventory
        return inventory.main(cfg, args)
    if args.command == "cart":
        from . import cart
        return cart.main(cfg, args)
    if args.command == "sim":
        from .sim import run
        try:
            return run.main(cfg, args)
        except run.SimError as e:
            print(f"edakit sim: {e}", file=sys.stderr)
            return 1
    if args.command == "docs":
        from . import docs
        return docs.main(cfg, args)
    if args.command == "firmware":
        from . import firmware
        return firmware.main(cfg, args)
    if args.command == "req":
        from . import requirements
        return requirements.main(cfg, args)
    if args.command == "scripts":
        from . import scripts
        return scripts.main(cfg, args)
    if args.command == "run":
        from . import scripts
        return scripts.main_run(cfg, args)
    if args.command == "handover":
        from . import handover
        return handover.main(cfg, args)
    if args.command == "schematic":
        from . import schematic
        return schematic.main(cfg, args)
    if args.command == "perfboard":
        from . import perfboard
        return perfboard.main(cfg, args)
    if args.command == "pcb":      # pcb dump, route all: made again after an easyeda script changed the library (8.6)
        from . import pcb, scripts
        return scripts.after_step(cfg, args, pcb.main(cfg, args))
    if args.command == "route":
        from . import route, scripts
        return scripts.after_step(cfg, args, route.main(cfg, args))
    if args.command == "silk":
        from . import silk
        return silk.main(cfg, args)
    if args.command == "export":
        from . import export
        return export.main(cfg, args)
    if args.command == "gate":
        from .release import gate
        return gate.main(cfg, args)
    if args.command == "release" and args.action == "publish":
        from .release import publish
        return publish.main(cfg, args)
    if args.command == "release":
        from .release import gate
        return gate.main_release(cfg, args)
    if args.command == "fab":
        from .release import fab
        return fab.main(cfg, args)
    if args.command == "doctor":
        from . import doctor
        return doctor.main(cfg, args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
