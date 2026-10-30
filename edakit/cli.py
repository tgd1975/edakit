"""edakit command line. Every command reads the project's edakit.toml (see handbook/10-reference.md).

    edakit check                     stages P/G: rule checks on the graph (offline, < 1 s)
    edakit rules [ID ...]            the rule catalog: what each check and hint is about, why, what to do
    edakit hints                     design hints that apply to the graph, notes from the parts database
    edakit block list|show|add       building blocks with checked parts into the graph
    edakit part import LCSC [--update]   symbol pins and footprint of an LCSC number from the library – no EasyEDA
    edakit part diff OLD NEW         how a new footprint maps onto the old one before a swap (offline)
    edakit part fetch KEY [--url U] | --all   a part's datasheet PDF, kept beside the project and checked to be of it
    edakit part search "KEYWORDS"    JLCPCB's parts catalogue: LCSC number, class, stock – no EasyEDA
    edakit part datasheet|own        own parts: a board of an edakit project as a part in another project
    edakit part footprint KEY [--write]   a library footprint as data in the parts entry (footprint_data) – offline
    edakit part build KEY [--write]  the project's copy in EasyEDA built from the entry's footprint data
    edakit stock [--refresh]         what JLCPCB says about the assembled parts, as a dated snapshot (check P-4)
    edakit cost [--json F]           the order for `quantity` boards from BOM, board and the dated fee table
    edakit order [--out DIR]         the assembler's BOM, a cart per other supplier, the hand-assembly list (P-5)
    edakit cart fields|prepare|check|actual   the order at the maker: its form from [order], the job of the skill
                                     cart, B-1 to B-7 on what it brought back, the real cost (never orders, never pays)
    edakit sim                       stage E: ngspice operating points of all scenarios (offline, seconds)
    edakit docs [--write]            values quoted in documents and schematic notes: G-19 for stale ones, --write fills in
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
    edakit schematic draw            the schematic as SVG from graph and parts database – no EasyEDA (offline)
    edakit pcb dump|plan|place|parts|nets|apply|tooling|pour|autolayout|takeover
    edakit route all|read|dsn|route|check|apply|verify|pours|reload|drc|save
    edakit route diagnose [--net N]  why each open connection is open: walled in, blocked, or a free way (offline)
    edakit silk apply|check
    edakit export                    PDFs, Gerber, BOM, CPL, netlist and a project copy to <artifacts>/export
    edakit gate [--easyeda]          release gate with test protocol and manufacturing files
    edakit release current|withdraw RUN --reason T|verify FILE…   the one current release, the files to upload
    edakit fab --board B --out DIR   stages L/F for one board (the gate calls it)
    edakit fab diff RUN_A RUN_B      where the manufacturing files of two gate runs differ (raster, drill, BOM, CPL,
                                     the order settings of [order])
    edakit lock [status|claim|release|yield CHAT]   share EasyEDA between parallel Claude sessions
    edakit proposal template|seal|verify   a rule or feature proposal for the edakit repository, sealed with its SHA-256
    edakit doctor                    Node, easyeda-mcp-pro, bridge, EasyEDA process, ngspice, Freerouting

Exit codes everywhere: 0 = ok, 2 = findings, 1 = error. `edakit lock`, `edakit run` of an easyeda script: 3 = another
session holds EasyEDA. `edakit cart check`: 3 = B-1 to B-6 passed, the regulatory review of the order (B-7) is open.
`route all|drc` and `silk apply|check`: 3 = the DRC's only item is "Import Changes" and schematic = PCB – EasyEDA
waits for the import acknowledgement (Design → Import Changes once).
"""

from __future__ import annotations

import argparse
import sys


def _common(p):
    p.add_argument("--config", help="path to edakit.toml (default: search upwards from the current directory)")
    p.add_argument("-v", "--verbose", action="store_true", help="show the MCP traffic")


def _no_scripts(p):
    p.add_argument("--no-scripts", action="store_true", help="run no project script first – the step reads the files "
                                                             "as they are (handbook 8.6)")


def build_parser():
    ap = argparse.ArgumentParser(prog="edakit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check", help="rule checks on the graph (stages P, G)")
    p.add_argument("--release", action="store_true", help="also fail on open sign-offs")
    p.add_argument("--json", help="write the findings as JSON")
    _common(p)

    p = sub.add_parser("rules", help="the rule catalog: checks and hints with reason, fix and sources")
    p.add_argument("ids", nargs="*", help="check or hint IDs, e.g. G-4 L-9 H-1 (default: the list)")

    p = sub.add_parser("hints", help="design hints that apply to the graph, and notes from the parts database")
    p.add_argument("--json", help="write them as JSON")
    _common(p)

    p = sub.add_parser("block", help="building blocks: list, show, or add one to the graph")
    p.add_argument("action", choices=["list", "show", "add"])
    p.add_argument("name", nargs="?", help="block name (edakit block list)")
    p.add_argument("--as", dest="instance", help="add: name of this instance, used for its nets and labels")
    p.add_argument("--connect", action="extend", nargs="+", metavar="PORT=NET", help="add: join ports to nets")
    p.add_argument("--board", help="add: board of the new parts (needed with several boards)")
    p.add_argument("--file", help="a block from this JSON file instead of the library")
    p.add_argument("--dry-run", action="store_true", help="add: show what would change, write nothing")
    _common(p)

    p = sub.add_parser("part", help="the library's data of an LCSC number, a footprint swap compared, datasheets, "
                                    "a catalogue search, own parts, own footprints as data")
    p.add_argument("action", choices=["import", "diff", "fetch", "search", "datasheet", "own", "footprint", "build"])
    p.add_argument("source", nargs="?", help="import: the LCSC number; diff: the old part; fetch, footprint, build: "
                                             "the parts-entry key; search: the keywords; own: the board's project (its "
                                             "directory or edakit.toml)")
    p.add_argument("new", nargs="?", help="diff: the new part (LCSC number or parts-entry key)")
    p.add_argument("--update", action="store_true", help="import: fill in what the existing entry lacks")
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

    p = sub.add_parser("stock", help="ask JLCPCB about every assembled part and write the stock snapshot (P-4)")
    p.add_argument("--board", help="only the parts of this board")
    p.add_argument("--refresh", action="store_true", help="ask about every part again, not only missing or old ones")
    p.add_argument("--lcsc", nargs="+", metavar="C", help="print what JLCPCB says about these parts, write nothing "
                                                          "(part search; no project needed)")
    _common(p)

    p = sub.add_parser("cost", help="estimate the order: PCB, PCBA fees, parts, extras, shipping, VAT; drivers, budget")
    p.add_argument("--board", help="only this board (no shipping, extras, VAT)")
    p.add_argument("--json", help="also write the estimate as JSON to this file")
    _common(p)

    p = sub.add_parser("order", help="assembler's BOM, one cart per other supplier, hand-assembly list for all sets")
    p.add_argument("--out", help="folder for the files (default: <artifacts>/order)")
    _common(p)

    p = sub.add_parser("cart", help="the order at the maker: the form's fields, the job of the skill cart, its check, "
                                    "the real cost – up to the maker's cart, never further")
    p.add_argument("action", choices=["fields", "prepare", "check", "actual"])
    p.add_argument("--board", help="the board (needed with several made boards)")
    p.add_argument("--maker", help="a maker of [cart] makers (default: [cart] maker, jlcpcb without [cart])")
    p.add_argument("--cart", action="store_true", help="check: the cart line after the cart button (cart.json)")
    p.add_argument("--from", dest="source", help="actual: a saved order page or invoice instead of the order history")
    _common(p)

    p = sub.add_parser("sim", help="simulation (stage E)")
    p.add_argument("--json", help="write every single check as JSON")
    p.add_argument("--keep", help="keep netlists and ngspice output in this directory")
    _common(p)

    p = sub.add_parser("docs", help="values quoted from the design data in documents and notes (G-19)")
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
    p.add_argument("--no-pins", action="store_true", help="check: skip the per-part pin check")
    p.add_argument("--refresh-devices", action="store_true", help="create: search every LCSC number again")
    p.add_argument("--create-project", action="store_true", help="create the EasyEDA project if it is not open")
    p.add_argument("--save", action="store_true", help="save the project at the end – create and layout only when "
                                                       "the netlist equals the graph")
    p.add_argument("--json", help="check: write the differences as JSON")
    p.add_argument("--wait", type=int, default=90, help="seconds to wait for the bridge")
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
                                      "reload", "drc", "save"])
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
    p.add_argument("--easyeda", "--eda", dest="easyeda", action="store_true",
                   help="also run S, L and F (EasyEDA with the bridge, or KiCad with kicad-cli: [project] toolchain)")
    _no_scripts(p)
    _common(p)

    p = sub.add_parser("release", help="the current release: show it, withdraw a run, check the files to upload")
    p.add_argument("action", choices=["current", "withdraw", "verify"])
    p.add_argument("items", nargs="*", help="withdraw: the run (folder name under reports); verify: files or folders "
                                            "(their .zip and .csv files)")
    p.add_argument("--reason", help="withdraw: why the run must not be uploaded")
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
    return ap


def main(argv=None):
    from .config import ConfigError
    try:
        return _main(argv)
    except ConfigError as e:     # a board refused while a command runs (unknown, or bought for a layout command)
        print(f"edakit: {e}", file=sys.stderr)
        return 1


def _main(argv=None):
    args = build_parser().parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up at once, also when piped
    if args.command == "lock":
        from . import lock
        return lock.main(args)
    if args.command == "rules":
        from . import rules
        return rules.main_rules(args)
    if args.command == "proposal":
        from . import proposal
        return proposal.main(args)
    if args.command == "stock" and args.lcsc:
        from . import stock
        return stock.main_lcsc(args.lcsc)
    if args.command == "block" and args.action in ("list", "show"):
        from . import block
        return block.main(None, args)
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
    if args.command == "check":
        from . import checks
        return checks.main(cfg, args)
    if args.command == "hints":
        from . import rules
        return rules.main_hints(cfg, args)
    if args.command == "block":
        from . import block
        return block.main(cfg, args)
    if args.command == "part":
        from . import part
        return part.main(cfg, args)
    if args.command == "stock":
        from . import stock
        return stock.main(cfg, args)
    if args.command == "cost":
        from . import cost
        return cost.main(cfg, args)
    if args.command == "order":
        from . import order
        return order.main(cfg, args)
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
