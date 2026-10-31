"""Parts: what the library says about an LCSC number, how a new footprint maps onto the old one, datasheets, and own
parts.

    edakit part import C2297 [--update]
                                symbol pins, footprint and identification of exactly that LCSC number from the
                                library's public data, without EasyEDA: a new parts entry, or the differences to the
                                existing one (--update fills in missing fields); the geometry and the symbol cached in
                                <artifacts>/footprints/<footprint>.json and <artifacts>/library/<LCSC>.json
    edakit part diff OLD NEW [--json FILE]
                                before a swap: the turn and shift that lay NEW's pads over OLD's (and whether the
                                mirror image fits), the pad map by position, roles, pitch, holes and box that change,
                                the graph change it implies; exit 0 = drop-in, 2 = something to decide
    edakit part fetch KEY [--url URL] | --all
                                the datasheet PDF of a parts entry, kept as <datasheets>/<KEY>.pdf with <KEY>.json (url,
                                sha256, date, pages, text layer, whether it names the mpn). Sources in this order:
                                --url, the entry's datasheet.url, LCSC's product data (pdfUrl), JLCPCB's catalogue
                                (dataManualUrl); an HTML page is searched once for a link to a PDF. Only a complete PDF
                                counts – anything else keeps the earlier copy (exit 2). --all: every entry without one.
                                The entry is not touched (a change would lapse its sign-off); verified.datasheet_sha256
                                of a sign-off says which file was signed
    edakit part search "KEYWORDS" [--basic] [--min-stock N] [--limit 25] [--json FILE]
                                JLCPCB's public parts catalogue (PARTS.stock's endpoint), without EasyEDA: LCSC number, mpn,
                                manufacturer, class (Basic, Extended, preferred), assembly stock, package, category;
                                C99… dropped, Basic first, then by stock; an LCSC number gives only its exact hit.
                                Exit 2 when nothing is found
    edakit part footprint KEY [--board B] [--write]
    edakit part build KEY [--board B] [--write]
                                own footprints as data in the parts entry (footprint.py, handbook 4.5): a library
                                footprint taken over as footprint_data, the project's copy in EasyEDA built from it

The library geometry has the units and axes of `edakit pcb dump` (mil, y up, relative to the part origin at 0° on
TOP); a pad with a hole adds `hole` [w, l] in mm and `plated`, every pad its shape, size `w` × `h` (mil) and `rot`.
STRUCT.entry compares the graph with a cached symbol, `pcb plan` takes a cached footprint for a part that is not in the PCB yet
– or, where the parts entry has footprint data, that data (library_footprint).

Own parts: a board of an edakit project used as a part in another project. No distributor sells it; its datasheet
comes from the project that designed it (handbook 4.5).

    edakit part datasheet --connector J1 [--connector J2] [--name NAME]
                                in the board's project: the board as a parts entry and a readable datasheet,
                                hardware/datasheet/<NAME>.json and .md (NAME: the project name)
    edakit part datasheet       renew every datasheet of the project, with its connectors and name
    edakit part own PATH [--name NAME]
                                in the project that uses the board: copy its datasheet into the parts database, with
                                the commit it comes from and whether that state of the board is released

Derived from the board's project:
  pins        the pins of the connectors in the given order – one connector keeps its numbers, several are numbered
              on; the name is the net on the board. Type and role from what the net reaches there: the simulation's
              source is power_in/vin, the ground ground/gnd, a supply rail the board makes power_output/vout, an I2C
              line bidirectional/sda|scl, otherwise the strongest of output, bidirectional, current_sink, input,
              analog, passive among its pins. pull and pull_ohm from resistors to a supply or to ground; vmax is the
              lowest limit on the net: pin vmax, capacitor v_max / 1.5
  params      behaviour "current": the largest current from the connector over the board's scenarios
  ratings     vin_min, vin_max: the voltage at the connector over those scenarios – SIM.state holds the host to it
  compliance  from the board's parts: RoHS, REACH statements, radio
  own         what "pcb", connectors, the hash of the board's circuit (state_sha256); the copy adds path, commit,
              repository and the release of that state

SYNC.source compares the copy with its source and a project's datasheets with its state (checks.py calls check()).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

from . import circuit, config
from .config import MIL_PER_MM
from .design import Design, load_parts, natural_key

WHAT = ("pcb", "bin", "handmade")   # own.what: a board of an edakit project, a part from the bin, made by hand
SIGNALS = ("output", "bidirectional", "current_sink", "input", "analog")   # strongest first

# EasyEDA's public component data (EasyEDA Standard format), the endpoint easyeda2kicad reads; undocumented, no key
LIBRARY_URL = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
UNIT_MIL = 10                       # EasyEDA Standard: one canvas unit is 10 mil, y points down
PAD_LAYERS = {"1": "TOP", "2": "BOTTOM", "11": "MULTI"}
ENTRY_FIELDS = ("mpn", "manufacturer", "footprint", "jlc_class")   # what part import writes besides pins


class PartError(Exception):
    pass


def datasheet_dir(cfg):
    return cfg.parts.parent / "datasheet"


def state_hash(cfg):
    """The hash of the circuit the gate signs (graph, simulation config, parts database)."""
    from .release import gate
    return gate.state_hash(cfg)


def file_name(mpn):
    """Parts file of an entry named by its mpn: characters a file name cannot hold become _ (handbook 4)."""
    return re.sub(r'[\\/:*?"<>|\s]', "_", mpn) + ".json"


def git(root, *args):
    try:
        res = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


# --- the datasheet of a board ------------------------------------------------------------------------------------

def interface(d, connectors):
    """[(number, pin ref, net or None)] of the connectors, in the given order."""
    for des in connectors:
        if des not in d.comps:
            raise PartError(f"{des}: not in the graph")
        if d.comps[des].get("type") != "connector":
            raise PartError(f"{des}: not a connector ({d.comps[des].get('type')}) – a board is a part through its "
                            "connectors")
    refs = [f"{des}.{num}" for des in connectors for num in sorted(d.comps[des]["pins"], key=natural_key)]
    numbers = [r.split(".", 1)[1] for r in refs] if len(connectors) == 1 else [str(i + 1) for i in range(len(refs))]
    return [(n, r, d.pin_net.get(r)) for n, r in zip(numbers, refs)]


def supply_of(sim, connectors):
    found = [des for des in connectors if des in sim.get("sources", {})]
    if not found:
        raise PartError(f"{', '.join(connectors)}: no source of the simulation (sources in the simulation config) – "
                        "the datasheet needs the current the board draws through its connector")
    if len(found) > 1:
        raise PartError(f"{', '.join(found)} are all sources of the simulation – a datasheet describes one supply")
    return found[0], sim["sources"][found[0]]


def simulate(cfg, d, sim, probe):
    """The board's own scenarios (fault cases with info and transient runs left out), with the nets in `probe`
    reported."""
    from .sim import copper
    from .sim import run as simrun
    info = {s["name"] for s in simrun.scenarios(sim) if s.get("info")}
    plugin = simrun.load_plugin(cfg.sim_plugin) if cfg.sim_plugin else None
    routing = copper.load_routing(cfg) if sim.get("copper") else None
    out = simrun.run_all(d, {**sim, "report": list(dict.fromkeys(probe))}, plugin=plugin, routing=routing)
    rows = [s for s in out["scenarios"] if s["name"] not in info and not s.get("transient")]
    bad = [s["name"] for s in rows if s["status"] != "ok"]
    if bad:
        raise PartError(f"the simulation of the board fails in {len(bad)} scenario(s) ({', '.join(bad[:3])}) – "
                        "edakit sim; a datasheet of a board that does not work describes nothing")
    return rows


def pull(d, net):
    """('up'|'down', parallel resistance or None) of the resistors from the net to a supply or to ground."""
    for way, targets in (("up", circuit.supply_nets(d)), ("down", {d.ground})):
        rs = [r for _, r, _ in circuit.resistors_to(d, net, targets)]
        if rs:
            return way, (1 / sum(1 / r for r in rs) if all(rs) else None)
    return None, None


def limit(d, net, inside):
    """Lowest voltage limit on the net: a pin's v_max_v, a capacitor's v_max_v / its derating factor (LIM.v's margin,
    catalog/tables/derating.toml) – with what sets it."""
    from .engines.quantities import FACTOR
    found = []
    for ref in inside:
        info = d.pin_info(ref)
        if info.get("v_max_v") is not None:
            found.append((float(info["v_max_v"]), f"{ref} ({info.get('name', '')}) v_max_v"))
        p = d.part(ref.split(".", 1)[0]) or {}
        if p.get("kind") == "capacitor" and circuit.limits(p).get("v_max_v"):
            v_max, f = circuit.limits(p)["v_max_v"], FACTOR["capacitor"]
            found.append((round(v_max / f, 2), f"{ref.split('.', 1)[0]} v_max_v {v_max} V / {f}"))
    return min(found) if found else (None, "")


def classify(d, net, inside, powered):
    """Type and role of a connector pin from what its net reaches on the board."""
    if net == d.ground:
        return {"type": "ground", "role": "gnd"}
    types = {d.pin_info(r).get("type") for r in inside}
    if "power_output" in types or ("power_in" in types and powered):
        return {"type": "power_output", "role": "vout"}
    if "power_in" in types:
        return None   # a supply input the simulation does not feed
    line = circuit.i2c_name(net) or next((x for x in map(circuit.i2c_line, map(d.pin_info, inside)) if x), None)
    if line:
        return {"type": "bidirectional", "role": line}
    if d.nets[net].get("bus") == "i2c":
        return {"type": "bidirectional"}      # an I2C line that does not say which: the host's net says it
    return {"type": next((t for t in SIGNALS if t in types), "passive")}


def compliance(d, project, state):
    """What the parts entries of the board say about RoHS, REACH and radio. radio: the radios of its parts, "none"
    when none transmits and every module and microcontroller says so (PARTS.fact), else left out – not known."""
    from .radio import RADIO_TYPES
    rohs = {"not compliant": [], "exemption": [], "not known": []}
    reach, radio, unstated, n = [], [], [], 0
    for des in sorted(d.comps, key=natural_key):
        p = d.part(des)
        if not p:
            continue
        n += 1
        c = p.get("compliance") or {}
        r = c.get("rohs")
        if r is False:
            rohs["not compliant"].append(des)
        elif r is None:
            rohs["not known"].append(des)
        elif r is not True:
            rohs["exemption"].append(f"{des} ({r})")
        if not c.get("reach"):
            reach.append(des)
        r = c.get("radio")
        if isinstance(r, dict):
            radio.append({"part": des, **r})
        elif isinstance(r, list):                       # an own board on the board: the radios of its parts
            radio += [{"part": des, **x} for x in r if isinstance(x, dict)]
        elif r != "none" and d.comps[des].get("type") in RADIO_TYPES:
            unstated.append(des)
    out = {"rohs": True if not any(rohs.values()) else "; ".join(f"{k}: {', '.join(v)}" for k, v in rohs.items() if v),
           "reach": (f"a supplier statement for each of the {n} parts" if not reach else
                     f"{n - len(reach)} of {n} parts with a supplier statement; none for {', '.join(reach)}")}
    if radio:
        out["radio"] = radio[0] if len(radio) == 1 else radio
    elif not unstated:
        out["radio"] = "none"
    out["source"] = f"the parts database of {project} (state {state[:12]}), by edakit part datasheet"
    return out


def datasheet(cfg, connectors, name=None):
    """(parts entry, Markdown datasheet) of the board seen through its connectors."""
    d = Design.from_config(cfg)
    pins = interface(d, connectors)
    if not cfg.sim_config.exists():
        raise PartError(f"{cfg.relative(cfg.sim_config)} missing – the datasheet needs the board's simulation")
    sim = json.loads(cfg.sim_config.read_text(encoding="utf-8"))
    des, src = supply_of(sim, connectors)
    plus, minus = d.pin_net.get(f"{des}.{src['plus']}"), d.pin_net.get(f"{des}.{src['minus']}")
    nets = [n for _, _, n in pins if n]
    rows = simulate(cfg, d, sim, [plus, minus, *nets])
    volts = [s["nets"][plus] - s["nets"][minus] for s in rows]
    worst = max(rows, key=lambda s: s["sources"][des])
    state = state_hash(cfg)
    entry_pins, notes, srcs = {}, {}, [f"pins: nets and parts of {cfg.relative(cfg.graph)}, graph {d.version}"]
    for num, ref, net in pins:
        if net is None:
            entry_pins[num] = {"name": "NC", "type": "no_connect", "from": ref}
            continue
        inside = [r for r in d.nets[net]["pins"] if r.split(".", 1)[0] not in connectors]
        if ref == f"{des}.{src['plus']}":
            kind = {"type": "power_in", "role": "vin"}
        elif ref == f"{des}.{src['minus']}":
            kind = {"type": "ground", "role": "gnd"}
        else:
            kind = classify(d, net, inside, max(abs(s["nets"][net]) for s in rows) > 0.5)
            if kind is None:
                raise PartError(f"{ref} ({net}): the board takes a supply here that its simulation does not give – a "
                                f"datasheet describes one supply, the source {des}")
        info = {"name": net, **kind, "from": ref}
        if kind["type"] not in ("ground", "power_in", "power_output"):
            way, ohm = pull(d, net)
            if way:
                info["pull"] = way
                if ohm:
                    info["pull_ohm"] = round(ohm, 1)
        vmax, why = limit(d, net, inside)
        if vmax is not None and kind["type"] != "ground":
            info["v_max_v"] = vmax
            srcs.append(f"pin {num} v_max_v: {why}")
        entry_pins[num] = info
        notes[num] = inside
    i_a = round(worst["sources"][des], 4)
    lo, hi = round(min(volts), 3), round(max(volts), 3)
    srcs += [f"values.i_a: the largest current from {des} over {len(rows)} scenarios of "
             f"{cfg.relative(cfg.sim_config)} ({worst['name']})",
             f"limits vin_min_v, vin_max_v: the voltage at {des} over those scenarios"]
    entry = {
        "mpn": name or cfg.project, "manufacturer": f"own board ({cfg.project})", "kind": "module",
        "datasheet": {"url": file_name(name or cfg.project)[:-5] + ".md"},
        "pins": entry_pins,
        "values": {"behavior": "current", "i_a": i_a},
        "limits": {"vin_min_v": lo, "vin_max_v": hi},
        "compliance": compliance(d, cfg.project, state),
        "sources": srcs,
        "own": {"what": "pcb", "project": cfg.project, "connectors": list(connectors), "graph_version": d.version,
                "state_sha256": state},
        "verified": None,
    }
    return entry, markdown(cfg, d, entry, notes, rows, des, plus, minus)


def markdown(cfg, d, entry, notes, rows, des, plus, minus):
    name, o = entry["mpn"], entry["own"]
    board = cfg.boards.get(d.comps[o["connectors"][0]].get("board") or "") or next(iter(cfg.boards.values()))
    lines = [f"# {name} – own board of the project {cfg.project}", "",
             f"Graph {d.version}" + (f" of {d.graph['date']}" if d.graph.get("date") else "")
             + (f": {d.graph['description']}" if d.graph.get("description") else ""),
             "",
             f"A part through its connector{'s' if len(o['connectors']) > 1 else ''} "
             f"{', '.join(o['connectors'])}. Written by `edakit part datasheet` from the state {o['state_sha256'][:12]}; "
             f"the parts entry other projects copy with `edakit part own` is {name}.json next to this file.", "",
             "## Pins", "",
             "| Pin | Name | Type | Role | max. V | Pull | On the board |", "|---|---|---|---|---|---|---|"]
    for num, p in entry["pins"].items():
        inside = notes.get(num, [])
        there = ", ".join(f"{r} ({n})" if (n := d.pin_info(r).get("name")) and n != r.split(".", 1)[1] else r
                          for r in inside[:4]) + (f", … ({len(inside)} pins)" if len(inside) > 4 else "")
        pull_txt = f"{p['pull']} {circuit.ohm(p['pull_ohm'])}" if p.get("pull_ohm") else p.get("pull", "–")
        lines.append(f"| {num} | {p['name']} | {p['type']} | {p.get('role', '–')} | {p.get('v_max_v', '–')} | "
                     f"{pull_txt} | {there or '–'} |")
    i_a, r = entry["values"]["i_a"], entry["limits"]
    lines += ["", "## Supply", "",
              f"Through {plus} against {minus} at {des}, as simulated over {len(rows)} scenarios of "
              f"{cfg.relative(cfg.sim_config)} (`edakit sim` there):", "",
              f"- voltage at the connector: {r['vin_min_v']} … {r['vin_max_v']} V – a project that uses the board must "
              "keep it there (LIM.range)",
              f"- largest current: {i_a * 1e3:.0f} mA", "",
              "| Scenario | Voltage | Current |", "|---|---|---|"]
    lines += [f"| {s['name']} | {s['nets'][plus] - s['nets'][minus]:.3f} V | {s['sources'][des] * 1e3:.0f} mA |"
              for s in rows]
    c = entry["compliance"]
    radio = c.get("radio")
    lines += ["", "## Compliance", "",
              f"- RoHS: {'all parts compliant' if c['rohs'] is True else c['rohs']}",
              f"- REACH: {c['reach']}",
              "- radio: " + ("none" if radio == "none" else "not stated by every module and microcontroller of "
                             "the board" if not radio else "; ".join(
                  f"{x['part']} {x.get('bands_mhz', '')} MHz, {x.get('max_dbm', '?')} dBm"
                  for x in (radio if isinstance(radio, list) else [radio]))),
              f"- from {c['source']}"]
    if board.outline:
        xs, ys = [p[0] for p in board.outline], [p[1] for p in board.outline]
        holes = board.holes
        lines += ["", "## Board", "",
                  f"Outline {max(xs) - min(xs):.1f} × {max(ys) - min(ys):.1f} mm ({board.file or board.name})"
                  + (f", {len(holes)} mounting hole(s) Ø "
                     + ", ".join(sorted({f'{h["d"]:g}' for h in holes})) + " mm" if holes else "") + "."]
    lines += ["", "## Not in this datasheet", "",
              "- the footprint and the EasyEDA device the board gets in a project that uses it",
              "- the board's logic levels and timing: its signal pins are typed, not simulated – a project that uses "
              "it checks them with LIM.v, LVL.undefined, LVL.contention and REQ.missing"]
    return "\n".join(lines) + "\n"


def write_datasheet(cfg, connectors, name=None):
    entry, md = datasheet(cfg, connectors, name)
    out = datasheet_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    json_file, md_file = out / file_name(entry["mpn"]), out / (file_name(entry["mpn"])[:-5] + ".md")
    json_file.write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    md_file.write_text(md, encoding="utf-8")
    return json_file, md_file


def renew_datasheets(cfg):
    done = []
    for f in sorted(datasheet_dir(cfg).glob("*.json")):
        sheet = json.loads(f.read_text(encoding="utf-8"))
        done.append(write_datasheet(cfg, sheet["own"]["connectors"], sheet["mpn"])[0])
    return done


# --- the copy in the project that uses the board -----------------------------------------------------------------

def latest_release(cfg, state):
    """{time, git} of the newest gate run of the board's project that released this state, or None."""
    for m in sorted(cfg.reports.glob("*/fab/manifest.json"), reverse=True):
        data = json.loads(m.read_text(encoding="utf-8"))
        if data.get("released") and data.get("state_sha256") == state:
            return {"time": data.get("time"), "git": data.get("git")}
    return None


def web_url(root, commit, file):
    """The file on GitHub at that commit, if the repository's origin is there."""
    origin = git(root, "remote", "get-url", "origin") or ""
    m = re.match(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?$", origin)
    top = git(root, "rev-parse", "--show-toplevel")
    if not m or not top:
        return None
    return f"https://github.com/{m.group(1)}/blob/{commit}/{Path(file).resolve().relative_to(Path(top).resolve())}"


def own(cfg, source, name=None):
    """Copy a board's datasheet into this project's parts database: (file, entry, what is left to do)."""
    source = Path(source)
    toml = source if source.is_file() else source / "edakit.toml"
    if not toml.is_file():
        raise PartError(f"{source}: no edakit.toml – the board's project is needed")
    src = config.load(toml)
    sheets = {json.loads(f.read_text(encoding="utf-8"))["mpn"]: f for f in sorted(datasheet_dir(src).glob("*.json"))}
    if not sheets:
        raise PartError(f"{source}: no datasheet yet – edakit part datasheet --connector … in that project")
    if name and name not in sheets:
        raise PartError(f"{source}: no datasheet {name} (there: {', '.join(sheets)})")
    if not name and len(sheets) > 1:
        raise PartError(f"{source} has several datasheets ({', '.join(sheets)}) – pick one with --name")
    sheet = sheets[name or next(iter(sheets))]
    entry = json.loads(sheet.read_text(encoding="utf-8"))
    state = entry["own"]["state_sha256"]
    if state != state_hash(src):
        raise PartError(f"{source}: the datasheet {entry['mpn']} is of an older state of the board – edakit part "
                        "datasheet there first")
    commit = git(src.root, "rev-parse", "HEAD")
    if not commit:
        raise PartError(f"{source}: not a git repository – the copy names the commit the board comes from")
    from .release import gate
    files = [sheet, sheet.with_suffix(".md"), *gate.state_files(src)]
    dirty = git(src.root, "status", "--porcelain", "--", *[str(f) for f in files])
    path = os.path.relpath(src.root, cfg.root)
    md = sheet.with_suffix(".md")
    entry["datasheet"] = {"url": web_url(src.root, commit, md) or os.path.relpath(md, cfg.root)}
    entry["own"].update(path=path, commit=commit + (" + uncommitted changes" if dirty else ""),
                        repo=git(src.root, "remote", "get-url", "origin"), released=latest_release(src, state))
    out = cfg.parts / file_name(entry["mpn"])
    if out.exists():
        old = json.loads(out.read_text(encoding="utf-8"))
        if old.get("verified") and (old.get("own") or {}).get("state_sha256") == state:
            entry["verified"] = old["verified"]       # the same board: the sign-off still holds
    out.write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    todo = []
    if dirty:
        todo.append(f"copied from uncommitted changes in {path} – commit there and copy again (SYNC.source stays open)")
    if not entry["own"]["released"]:
        todo.append(f"{path} is not released at this state – SYNC.source warns until it is (edakit gate there, then copy "
                    "again) or the warning is accepted in the sign-off file")
    if not entry["verified"]:
        todo.append("sign it off against its datasheet (handbook 4.3; PARTS.verified stays open until then)")
    todo.append(f"the component: \"part\": \"{entry['mpn']}\", \"bom\": false, pins "
                + json.dumps({k: p["name"] for k, p in entry["pins"].items()}, ensure_ascii=False)
                + ", an easyeda_device with symbol and footprint of the board")
    return out, entry, todo


# --- the library's data of an LCSC number (part import) ---------------------------------------------------------------

def lcsc_number(text):
    """An LCSC number the library can be asked for: C and digits, and not a C99… number of a user library."""
    if not re.fullmatch(r"C\d+", text or ""):
        raise PartError(f"{text}: not an LCSC number (C followed by digits)")
    if text.startswith("C99"):
        raise PartError(f"{text}: a C99… number is a part of an EasyEDA user library – nobody sells it, nothing to "
                        "import (handbook 4.2)")
    return text


def _open(url):
    """The one network access of part import (the tests answer from recordings)."""
    req = urllib.request.Request(url, headers={"User-Agent": "edakit"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def library_part(lcsc):
    """What the library says about exactly this LCSC number: {lcsc, mpn, manufacturer, footprint, jlc_class, pins
    {number: name}, geometry (the cache format), source}. The one source is EasyEDA's public component data; another
    one – a KiCad library, an EasyEDA Pro export – replaces this function."""
    url = LIBRARY_URL.format(lcsc=lcsc_number(lcsc))
    try:
        data = json.loads(_open(url))
    except urllib.error.HTTPError as e:
        raise PartError(f"{lcsc}: the library refused (HTTP {e.code}) – it answers a few dozen requests in a row, "
                        f"then refuses for a while; try again later – {url}") from None
    except (OSError, ValueError) as e:
        raise PartError(f"{lcsc}: no answer from the library ({e}) – {url}") from None
    if not data.get("success"):          # an unknown number comes with HTTP 200 as well
        raise PartError(f"{lcsc}: not in the library ({data.get('message') or data.get('code')})")
    return parse_component(lcsc, data["result"], url)


def parse_component(lcsc, res, source):
    para = {k: v for k, v in (res["dataStr"]["head"].get("c_para") or {}).items()
            if v and str(v).strip().lower() not in ("null", "none", "-")}     # the library writes "null" for nothing
    if para.get("Supplier Part") not in (None, "", lcsc):
        raise PartError(f"{lcsc}: the library answered with {para['Supplier Part']}")
    pkg = res.get("packageDetail") or {}
    footprint = pkg.get("title") or para.get("package")
    return {"lcsc": lcsc, "mpn": para.get("Manufacturer Part"), "manufacturer": para.get("Manufacturer"),
            "footprint": footprint, "jlc_class": para.get("JLCPCB Part Class"), "pins": symbol_pins(res),
            "geometry": footprint_geometry(pkg["dataStr"], footprint) if pkg.get("dataStr") else None,
            "source": source}


def symbol_pins(res):
    """{number: name} of the symbol's pins, all units. A pin: `P~show~type~number~x~y~…^^dot^^path^^name^^…`, the
    name text the fifth field of its fourth segment."""
    shapes = list(res["dataStr"].get("shape") or [])
    for sub in res.get("subparts") or []:
        shapes += (sub.get("dataStr") or {}).get("shape") or []
    pins = {}
    for s in shapes:
        if s.startswith("P~"):
            seg = [x.split("~") for x in s.split("^^")]
            pins.setdefault(seg[0][3], seg[3][4] if len(seg) > 3 and len(seg[3]) > 4 else "")
    return dict(sorted(pins.items(), key=lambda kv: natural_key(kv[0])))


def footprint_geometry(ds, footprint):
    """The footprint as `pcb dump` stores it – mil, y up, relative to the origin – with shape, size and hole per pad.
    A pad: `PAD~shape~x~y~w~h~layer~net~number~hole radius~points~rotation~id~slot length~hole point~plated~…` in
    10-mil units, y down, relative to head x/y."""
    hx, hy = float(ds["head"]["x"]), float(ds["head"]["y"])
    pads = []
    for s in ds.get("shape") or []:
        f = s.split("~")
        if f[0] != "PAD":
            continue
        f += [""] * (16 - len(f))
        r = float(f[9] or 0) * UNIT_MIL
        pad = {"x": round((float(f[2]) - hx) * UNIT_MIL, 2), "y": round((hy - float(f[3])) * UNIT_MIL, 2), "net": "",
               "tht": r > 0, "shape": f[1], "w": round(float(f[4]) * UNIT_MIL, 2), "h": round(float(f[5]) * UNIT_MIL, 2),
               "rot": round(-float(f[11] or 0) % 360, 2), "layer": PAD_LAYERS.get(f[6], f[6])}
        if f[1] == "POLYGON" and f[10].strip():      # a polygon pad: its corners, relative to the pad (KiCad: custom)
            v = [float(t) for t in f[10].split()]
            pad["points"] = [[round((x - float(f[2])) * UNIT_MIL, 2), round((float(f[3]) - y) * UNIT_MIL, 2)]
                             for x, y in zip(v[0::2], v[1::2])]
        if r > 0:
            w = 2 * r / MIL_PER_MM
            pad["hole"] = [round(w, 3), round(max(w, float(f[13] or 0) * UNIT_MIL / MIL_PER_MM), 3)]
            pad["plated"] = f[15].strip().lower() not in ("n", "no", "false", "0")
        pads.append((f[8], pad))
    bb = ds.get("BBox")
    if bb:
        box = [(bb["x"] - hx) * UNIT_MIL, (hy - bb["y"] - bb["height"]) * UNIT_MIL,
               (bb["x"] + bb["width"] - hx) * UNIT_MIL, (hy - bb["y"]) * UNIT_MIL]
    else:
        half = [max(p["w"], p["h"]) / 2 for _, p in pads] or [0]
        box = [min(p["x"] - h for (_, p), h in zip(pads, half)), min(p["y"] - h for (_, p), h in zip(pads, half)),
               max(p["x"] + h for (_, p), h in zip(pads, half)), max(p["y"] + h for (_, p), h in zip(pads, half))]
    geo = {"footprint": footprint, "bbox": [round(v, 2) for v in box], "pads": {}, "silk": footprint_silk(ds, hx, hy)}
    for n, p in pads:
        geo["pads"].setdefault(n, p)
    nums = [n for n, _ in pads]
    if dup := sorted({n for n in nums if nums.count(n) > 1}, key=natural_key):   # shell legs: all of them here
        geo["pads_same_number"] = {n: [p for m, p in pads if m == n] for n in dup}
    return geo


SILK_LAYERS = {"3": "TOP", "4": "BOTTOM"}   # EasyEDA Standard: top and bottom silkscreen


def footprint_silk(ds, hx, hy):
    """The silkscreen of the library footprint – what the KiCad tool chain draws with the pads (handbook 16), polarity
    marks included: [{layer, points [[x, y], …], width, fill}] in mil, y up, relative to the origin. Lines (TRACK),
    circles, arcs, filled regions and the strokes of texts other than the designator and the name."""
    out = []

    def add(layer, polylines, width, fill=False):
        for pts in polylines:
            if len(pts) >= 2:
                out.append({"layer": SILK_LAYERS[layer], "points": [[round((x - hx) * UNIT_MIL, 2),
                                                                     round((hy - y) * UNIT_MIL, 2)] for x, y in pts],
                            "width": round(width * UNIT_MIL, 2), "fill": fill})
    for s in ds.get("shape") or []:
        f = s.split("~")
        try:
            if f[0] == "TRACK" and f[2] in SILK_LAYERS:
                v = [float(t) for t in f[4].split()]
                add(f[2], [list(zip(v[0::2], v[1::2]))], float(f[1]))
            elif f[0] == "CIRCLE" and f[5] in SILK_LAYERS:
                cx, cy, r = float(f[1]), float(f[2]), float(f[3])
                add(f[5], [[(cx + r * math.cos(2 * math.pi * k / 24), cy + r * math.sin(2 * math.pi * k / 24))
                            for k in range(25)]], float(f[4]))
            elif f[0] == "ARC" and f[2] in SILK_LAYERS:
                add(f[2], svg_polylines(f[4]), float(f[1]))
            elif f[0] == "SOLIDREGION" and f[1] in SILK_LAYERS:
                add(f[1], svg_polylines(f[3]), 0, fill=True)
            elif f[0] == "TEXT" and f[7] in SILK_LAYERS and f[1] not in ("P", "N") and len(f) > 11:
                add(f[7], svg_polylines(f[11]), float(f[4]))
        except (IndexError, ValueError):
            continue              # a shape the library writes otherwise: left out, the gate's GEO.mark and GEO.silk see the print
    return out


def svg_polylines(d):
    """An SVG path (EasyEDA's canvas units) -> polylines, arcs and curves as points 1/8 of their length apart."""
    from svgelements import Close, Line, Move, Path
    lines = []
    for seg in Path(d):
        if isinstance(seg, Move):
            lines.append([(seg.end.x, seg.end.y)])
        elif isinstance(seg, (Line, Close)):
            if not lines:
                lines.append([(seg.start.x, seg.start.y)])
            lines[-1].append((seg.end.x, seg.end.y))
        elif seg.start is not None:
            if not lines:
                lines.append([(seg.start.x, seg.start.y)])
            lines[-1] += [(q.x, q.y) for q in (seg.point(k / 8) for k in range(1, 9))]
    return [ln for ln in lines if len(ln) >= 2]


def library_file(cfg, lcsc):
    return cfg.artifacts / "library" / f"{lcsc}.json"


def footprint_file(cfg, footprint):
    return cfg.artifacts / "footprints" / file_name(footprint)


def _read(f):
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def cached(cfg, lcsc):
    """The library's data of an LCSC number as part import cached it (identification, footprint, symbol pins)."""
    return _read(library_file(cfg, lcsc)) if lcsc else None


def cached_footprint(cfg, footprint):
    return _read(footprint_file(cfg, footprint)) if footprint else None


def library_footprint(cfg, design, des):
    """A component's footprint before its dump: the footprint data of its parts entry (4.5) – the copy edakit builds,
    "source": "data"; None while the data is not complete (PARTS.footprint) –, else the cached library geometry of its footprint:
    the name of its parts entry, else of the library."""
    entry = design.part(des) or {}
    if "footprint_data" in entry:
        from .footprint import geometry
        return geometry(entry)
    name = entry.get("footprint") or (cached(cfg, design.comps[des].get("lcsc")) or {}).get("footprint")
    return cached_footprint(cfg, name)


def write_cache(cfg, lib, today):
    read = {"source": lib["source"], "read": today}
    out = {"symbol": cfg.artifact("library", f"{lib['lcsc']}.json")}
    out["symbol"].write_text(json.dumps({**{k: lib[k] for k in ("lcsc", *ENTRY_FIELDS, "pins")}, **read}, indent=1,
                                        ensure_ascii=False) + "\n", encoding="utf-8")
    if lib["geometry"]:
        out["footprint"] = cfg.artifact("footprints", file_name(lib["footprint"]))
        out["footprint"].write_text(json.dumps({**lib["geometry"], **read}, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    return out


def entry_differences(entry, lib):
    """Where a parts entry differs from the library: fields it lacks, values that differ (case and blanks ignored but
    in the footprint name, which SYNC.footprint compares as it is), pins as SYNC.schematic compares them."""
    from .schematic import pin_differences
    out = []
    for k in ENTRY_FIELDS:
        have, want = entry.get(k), lib.get(k)
        if not want:
            continue
        if have in (None, ""):
            out.append(f"{k}: missing in the entry, library '{want}' (--update fills it in)")
        elif have != want if k == "footprint" else "".join(str(have).split()).upper() != "".join(want.split()).upper():
            out.append(f"{k}: library '{want}', entry '{have}'")
    names = {n: p.get("name", "") for n, p in (entry.get("pins") or {}).items()}
    if not names:
        out.append("pins: missing in the entry (--update fills them in)")
    else:
        out += pin_differences(lib["pins"], names, labels=("library", "entry"))
    return out


def import_part(cfg, lcsc, update=False, today=None):
    """(parts file, what was written, differences): a new entry from the library, or the differences of the existing
    one, whose missing fields `update` fills in – an existing entry is never overwritten. The library's geometry and
    symbol go into the cache either way."""
    lib = library_part(lcsc)
    today = today or datetime.date.today().isoformat()
    cache = write_cache(cfg, lib, today)
    out = cfg.parts / f"{lcsc}.json"
    source = f"EasyEDA library data of {lcsc}, {lib['source']}, read {today} (edakit part import)"
    pins = {n: {"name": name} for n, name in lib["pins"].items()}
    if not out.exists():
        entry = {"lcsc": lcsc, **{k: lib[k] for k in ENTRY_FIELDS}, "kind": None, "pins": pins,
                 "sources": [f"mpn, manufacturer, footprint, jlc_class, pin numbers and names: {source}"],
                 "verified": None}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return out, ["new entry"], [], cache, lib
    entry = json.loads(out.read_text(encoding="utf-8"))
    filled = []
    if update:
        filled = [k for k in ENTRY_FIELDS if entry.get(k) in (None, "") and lib[k]]
        entry.update({k: lib[k] for k in filled})
        if not entry.get("pins") and pins:
            entry["pins"] = pins
            filled.append("pins")
        if filled:
            entry["sources"] = [*(entry.get("sources") or []), f"{', '.join(filled)}: {source}"]
            from .block import write_json
            write_json(out, entry)
    return out, filled, entry_differences(entry, lib), cache, lib


def main_import(cfg, args):
    if not args.source:
        raise PartError("the LCSC number is missing (edakit part import C2297)")
    out, done, diffs, cache, lib = import_part(cfg, args.source, args.update)
    if done == ["new entry"]:
        print(f"{cfg.relative(out)}: new entry – {lib['mpn']} ({lib['manufacturer']}), footprint {lib['footprint']}, "
              f"{lib['jlc_class']}, {len(lib['pins'])} pins")
        print("  kind, pin types and roles, values and ratings are for whoever signs it off against its datasheet "
              "(handbook 4.3; PARTS.verified stays open until then)")
    elif diffs:
        print(f"{cfg.relative(out)}: differs from the library – the entry is kept" +
              (f" (filled in: {', '.join(done)})" if done else ""))
        for d in diffs:
            print(f"  {d}")
    else:
        print(f"{cfg.relative(out)}: agrees with the library" + (f" (filled in: {', '.join(done)})" if done else ""))
    geo = lib["geometry"]
    if geo:
        x0, y0, x1, y1 = geo["bbox"]
        holes = sum(1 for p in geo["pads"].values() if p.get("hole"))
        print(f"  library geometry: {cfg.relative(cache['footprint'])} ({len(geo['pads'])} pads"
              + (f", {holes} with a hole" if holes else "") + f", {(x1 - x0) / MIL_PER_MM:.1f} x "
              f"{(y1 - y0) / MIL_PER_MM:.1f} mm)")
    print(f"  symbol: {cfg.relative(cache['symbol'])} – STRUCT.entry compares the graph with it")
    return 2 if diffs else 0


# --- the datasheet of a part (part fetch) ----------------------------------------------------------------------------

LCSC_PRODUCT = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={lcsc}"   # LCSC's product data: pdfUrl
LCSC_PAGE = re.compile(r"https?://(?:www\.)?lcsc\.com/datasheet/lcsc_datasheet_([^/?#]+\.pdf)", re.I)
LCSC_FILE = "https://wmsc.lcsc.com/wmsc/upload/file/pdf/v2/lcsc/{name}"   # the file behind LCSC's datasheet page
REDIRECT = re.compile(r"""(?:location(?:\.href)?\s*=|location\.replace\s*\()\s*["']([^"']+)["']"""
                      r"""|http-equiv\s*=\s*["']?refresh["']?[^>]*?url\s*=\s*([^"'>\s]+)""", re.I)
BROWSER = "Mozilla/5.0 (compatible; edakit)"     # datasheet hosts answer a browser, some refuse anything else
SCAN_CHARS = 20       # fewer characters (blanks not counted) per page than this: no text layer, a scan
EOF_TAIL = 64 * 1024  # a complete PDF has its %%EOF this close to its end (some tools append metadata after it)
PDF_URL = re.compile(r"[^?#]*\.pdf(?:[?#].*)?$", re.I)
VIEWERS = {"iframe": "src", "embed": "src", "object": "data"}   # an embedded viewer: the element and its address


def today():
    return datetime.date.today().isoformat()


def _download(url):
    """The one network access of part fetch for a URL: the answer's bytes (the tests answer from recordings)."""
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def catalogue_search(keyword, page_size=25):
    """JLCPCB's public parts catalogue through PARTS.stock's client (release/fab.py jlc_search; no login, only the keyword
    leaves the machine): the hits of a full-text search as the catalogue gives them. Network errors and a changed
    answer raise. The one place part fetch and part search reach the catalogue."""
    from .release import fab
    return fab.jlc_search(keyword, page_size=page_size)


def datasheet_files(cfg, key):
    """(<datasheets>/<key>.pdf, <datasheets>/<key>.json)."""
    stem = cfg.datasheets / file_name(key)
    return stem.with_suffix(".pdf"), stem.with_suffix(".json")


def is_html(data):
    """A page – also the bare script with which LCSC's datasheet file sends the browser on to the PDF."""
    head = data[:1024].lstrip().lower()
    return head.startswith((b"<!doctype", b"<html", b"<?xml", b"<head", b"<script", b"<meta")) or b"<html" in head


def page_pdfs(data):
    """The PDF addresses of an HTML page in their order: [(kind, address, words)] – kind 'redirect' for a page that
    sends the browser on by script or meta refresh, 'viewer' for the src of an iframe or embed and the data of an
    object, 'link' for an a href; words: a link's text, title and aria-label."""
    from html.parser import HTMLParser

    class Links(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.found, self.open = [], None

        def handle_starttag(self, tag, attrs):
            a = {k: v or "" for k, v in attrs}
            if tag in VIEWERS and PDF_URL.match(a.get(VIEWERS[tag], "").strip()):
                self.found.append(["viewer", a[VIEWERS[tag]].strip(), ""])
            elif tag == "a" and PDF_URL.match(a.get("href", "").strip()):
                self.open = ["link", a["href"].strip(), " ".join((a.get("title", ""), a.get("aria-label", "")))]
                self.found.append(self.open)

        def handle_data(self, text):
            if self.open:
                self.open[2] += " " + text

        def handle_endtag(self, tag):
            if tag == "a":
                self.open = None

    text = data.decode("utf-8", "replace")
    p = Links()
    p.feed(text)
    redirects = [("redirect", (m.group(1) or m.group(2)).strip(), "") for m in REDIRECT.finditer(text)
                 if PDF_URL.match((m.group(1) or m.group(2)).strip())]
    return redirects + [tuple(f) for f in p.found]


def pdf_link(data, base, names=()):
    """(link, others) of an HTML page: the link to the part's PDF, absolute and without its #fragment – where the page
    sends the browser by script or meta refresh, else the first viewer, else the first link whose address or words
    name the part (one of `names`: its mpn, its LCSC number) or say datasheet –, and the file names of the page's
    other PDF links. Those are no datasheet: LCSC's datasheet address answers with a page of the shop whose only PDFs
    are the certificates in its footer, and the first of them was once kept as the datasheet of a battery holder
    (handbook 17)."""
    import urllib.parse
    found = [(kind, urllib.parse.urldefrag(urllib.parse.urljoin(base, url))[0], words)
             for kind, url, words in page_pdfs(data)]
    marks = [n.lower() for n in names if n] + ["datasheet", "data sheet"]

    def names_part(url, words):
        where = urllib.parse.unquote(url).lower()
        return any(n in where for n in marks[:-2]) or any(m in " ".join(words.lower().split()) for m in marks)
    link = next((u for k, u, _ in found if k == "redirect"), None) or \
        next((u for k, u, _ in found if k == "viewer"), None) or \
        next((u for k, u, w in found if names_part(u, w)), None)
    others = [urllib.parse.unquote(u.rsplit("/", 1)[-1].split("?")[0]) for _, u, _ in found if u != link]
    return link, list(dict.fromkeys(others))


def get_pdf(url, follow=True, names=()):
    """(bytes, url) of a complete PDF at the URL; an HTML page is searched once for a link to the part's PDF
    (pdf_link, `names`: the part's mpn and LCSC number). Anything else raises PartError with what came back."""
    import http.client
    try:
        data = _download(url)
    except urllib.error.HTTPError as e:
        raise PartError(f"HTTP {e.code}") from None
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise PartError(f"no answer ({e})") from None
    if data.startswith(b"%PDF"):
        eof = data.rfind(b"%%EOF")
        if eof < 0 or len(data) - eof > EOF_TAIL:
            raise PartError(f"an incomplete PDF ({len(data)} bytes, no %%EOF in its last {EOF_TAIL // 1024} kB)")
        return data, url
    if not is_html(data):
        raise PartError(f"not a PDF ({len(data)} bytes, starting {data[:12]!r})")
    if not follow:
        raise PartError(f"an HTML page ({len(data)} bytes)")
    link, others = pdf_link(data, url, names)
    if not link and others:
        raise PartError(f"an HTML page ({len(data)} bytes) whose PDF links neither name the part nor say datasheet: "
                        + ", ".join(others[:5]) + (f" and {len(others) - 5} more" if len(others) > 5 else ""))
    if not link:
        raise PartError(f"an HTML page ({len(data)} bytes) without a link to a PDF")
    try:
        return get_pdf(link, follow=False)
    except PartError as e:
        raise PartError(f"an HTML page whose PDF link {link} gave {e}") from None


def lcsc_pdf_url(lcsc):
    """pdfUrl of LCSC's product data of the number."""
    try:
        data = json.loads(_download(LCSC_PRODUCT.format(lcsc=lcsc)))
    except urllib.error.HTTPError as e:
        raise PartError(f"HTTP {e.code}") from None
    except (OSError, ValueError) as e:
        raise PartError(f"no answer ({e})") from None
    url = (data.get("result") or {}).get("pdfUrl")
    if not url:
        raise PartError("no pdfUrl")
    return url


def jlc_manual_url(lcsc):
    """dataManualUrl of exactly that number in JLCPCB's catalogue – LCSC's datasheet page there taken as the file
    behind it (lcsc_file): the page is a page of the shop since 2026, the file sends on to the PDF."""
    try:
        hit = next((c for c in catalogue_search(lcsc) if c.get("componentCode") == lcsc), None)
    except Exception as e:  # network, changed API
        raise PartError(f"no answer ({str(e)[:200]})") from None
    if not hit:
        raise PartError("not listed")
    if not hit.get("dataManualUrl"):
        raise PartError("no dataManualUrl")
    return lcsc_file(hit["dataManualUrl"])


def lcsc_file(url):
    """The file behind LCSC's datasheet page of a part (www.lcsc.com/datasheet/lcsc_datasheet_<name>.pdf, JLCPCB's
    dataManualUrl): wmsc.lcsc.com/…/<name>.pdf, which sends the browser on to the PDF by script (tried 2026-10-29 on
    C70377, C318884, C17471, C2297). Any other URL as it is."""
    m = LCSC_PAGE.match(url)
    return LCSC_FILE.format(name=m.group(1)) if m else url


def short(url):
    """A URL for a message: a long query string (a signed link that expires anyway) cut off."""
    base, _, query = url.partition("?")
    return url if len(query) <= 60 else f"{base}?…"


def datasheet_sources(key, entry, url=None):
    """[(name, URL or a function that finds one)] in the order part fetch tries them."""
    out = [("--url", url)] if url else []
    if (entry.get("datasheet") or {}).get("url"):
        out.append(("datasheet.url", entry["datasheet"]["url"]))
    lcsc = entry.get("lcsc") or (key if re.fullmatch(r"C\d+", key) else None)
    if lcsc and re.fullmatch(r"C\d+", lcsc) and not lcsc.startswith("C99"):
        out += [("LCSC product data", lambda: lcsc_pdf_url(lcsc)), ("JLCPCB catalogue", lambda: jlc_manual_url(lcsc))]
    return out


def pdf_text(path):
    """The text of a PDF by pdftotext (one form feed ends each page), or None without pdftotext on PATH."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "-enc", "UTF-8", str(path), "-"], capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def count_pages(data):
    """Pages of a PDF from its page objects – None where they sit in compressed object streams."""
    n = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", data))
    return n or None


def names_mpn(text, mpn):
    """'yes' when the text names the mpn as a whole word (case ignored), the longer part number it names when it
    names the mpn only inside one (MT3608L for MT3608), else 'no'."""
    if re.search(r"(?<![A-Za-z0-9])" + re.escape(mpn) + r"(?![A-Za-z0-9])", text, re.I):
        return "yes"
    longer = [t for t in re.findall(r"[A-Za-z0-9]*" + re.escape(mpn) + r"[A-Za-z0-9]*", text, re.I)
              if t.upper() != mpn.upper()]
    return Counter(longer).most_common(1)[0][0] if longer else "no"


def fetch(cfg, key, url=None):
    """Fetch the datasheet of a parts entry and keep it: {key, mpn, file, record, tried [(source, url, outcome)],
    kept (the earlier record when every source failed), findings [(level, text)]}. A download counts only as a
    complete PDF; anything else leaves the kept copy as it is. The record: url (the source's address), pdf_url (the
    link a page led to, if it did), source, sha256, fetched, bytes, pages, text (a text layer; None without
    pdftotext), names_mpn ('yes', 'no', the longer variant named; None unchecked). The parts entry is never touched
    – a change there would lapse its sign-offs (handbook 4.3). It reads the parts database only: a datasheet is
    fetched before the part is in the graph, also before there is a graph."""
    entry = load_parts(cfg.parts).get(key)
    if entry is None:
        raise PartError(f"no parts entry {key} in {cfg.relative(cfg.parts)} – edakit part import {key} for an LCSC "
                        "number")
    pdf, rec_file = datasheet_files(cfg, key)
    before = _read(rec_file) if pdf.is_file() else None
    mpn = str(entry.get("mpn") or key)
    out = {"key": key, "mpn": mpn, "file": pdf, "record": None, "tried": [], "kept": None, "findings": []}
    sources = datasheet_sources(key, entry, url)
    if not sources:
        raise PartError(f"{key}: no source – no datasheet.url in the entry and no LCSC number; name one with --url")
    data = None
    for name, where in sources:
        try:
            where = where() if callable(where) else where
            data, got = get_pdf(where, names=(mpn, entry.get("lcsc") or key))
        except PartError as e:
            out["tried"].append((name, where if isinstance(where, str) else "", str(e)))
            continue
        out["tried"].append((name, where, "PDF" if got == where else f"PDF behind the page's link {short(got)}"))
        break
    if data is None:
        out["kept"] = before
        return out
    pdf.parent.mkdir(parents=True, exist_ok=True)
    tmp = pdf.with_suffix(".part")
    tmp.write_bytes(data)
    text = pdf_text(tmp)
    sha = hashlib.sha256(data).hexdigest()
    pages = (text.count("\f") or None) if text is not None else count_pages(data)
    layer = None if text is None else len("".join(text.split())) >= SCAN_CHARS * (pages or 1)
    rec = {"key": key, "mpn": mpn, "url": where, **({"pdf_url": got} if got != where else {}), "source": name,
           "sha256": sha, "fetched": today(), "bytes": len(data), "pages": pages, "text": layer,
           "names_mpn": names_mpn(text, mpn) if layer else None}
    tmp.replace(pdf)
    rec_file.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    out["record"] = rec
    f = out["findings"]
    if before and before.get("sha256") != sha:
        f.append(("info", f"replaces the copy of {before.get('fetched')} (sha256 {str(before.get('sha256'))[:12]}…)"))
    signed = (entry.get("verified") or {}).get("datasheet_sha256")
    if signed and signed == sha:
        f.append(("info", "the signed file (verified.datasheet_sha256)"))
    elif signed:
        f.append(("warning", f"changed since the sign-off: verified.datasheet_sha256 {signed[:12]}…, this file "
                             f"{sha[:12]}… – read it and renew the sign-off (handbook 4.3)"))
    if text is None:
        f.append(("note", "pdftotext not on PATH: the text is not checked (poppler-utils; edakit doctor)"))
    elif not layer:
        f.append(("note", "no text layer: scanned, read the drawings as images (pdftoppm -r 300 -png)"))
    elif rec["names_mpn"] == "no":
        f.append(("note", f"the text does not name {mpn} – some vendors never print it; compare package, drawing "
                          "and values with the entry"))
    elif rec["names_mpn"] != "yes":
        f.append(("warning", f"the text names {rec['names_mpn']}, not {mpn} – a sheet of a variant? Compare pinout "
                             "and ratings, or fetch another with --url"))
    return out


def main_fetch(cfg, args):
    if args.all and args.url:
        raise PartError("--url names the datasheet of one part, not of --all")
    if args.all:
        keys = sorted(load_parts(cfg.parts))
    elif args.source:
        keys = [args.source]
    else:
        raise PartError("which part? edakit part fetch C2297 [--url URL], or --all")
    worst = 0
    for key in keys:
        pdf, rec_file = datasheet_files(cfg, key)
        if args.all and pdf.is_file() and (rec := _read(rec_file)):
            print(f"{key}: kept, fetched {rec.get('fetched')}")
            continue
        try:
            r = fetch(cfg, key, args.url)
        except PartError as e:
            if not args.all:
                raise
            print(f"{key}: {e}")
            continue
        print(f"{key} {r['mpn']}")
        for name, where, outcome in r["tried"]:
            print("  " + " ".join(x for x in (name, where) if x) + f": {outcome}")
        if r["record"] is None:
            if r["kept"]:
                print(f"  kept the copy of {r['kept'].get('fetched')} – every source failed: {cfg.relative(pdf)}")
                worst = max(worst, 2)
            else:
                print("  no datasheet: every source failed – name one with --url")
                worst = max(worst, 2 if args.all else 1)
            continue
        rec = r["record"]
        print(f"  {cfg.relative(pdf)}: {rec['bytes'] / 1024:.0f} kB, "
              + (f"{rec['pages']} pages, " if rec["pages"] else "")
              + {True: "text layer", False: "no text layer", None: "text not checked"}[rec["text"]]
              + (f", names {r['mpn']}" if rec["names_mpn"] == "yes" else "")
              + f", sha256 {rec['sha256'][:12]}…")
        for level, text in r["findings"]:
            print(f"  {'' if level == 'info' else f'{level.upper():<7} '}{text}")
            if level == "warning":
                worst = max(worst, 2)
    return worst


# --- a search through JLCPCB's catalogue (part search) ------------------------------------------------------------

def catalogue_class(h):
    """Basic, Extended, preferred – as JLCPCB's assembly charges them (preferred Extended parts have no feeder fee)."""
    if h.get("componentLibraryType") == "base":
        return "Basic"
    return "Extended, preferred" if h.get("preferredComponentFlag") else "Extended"


def search(keyword, basic=False, min_stock=None, limit=25):
    """(hits, dropped C99… numbers) of a catalogue search: one row per hit {lcsc, mpn, manufacturer, category, package,
    class, stock}, Basic before preferred before Extended, then by stock. An LCSC number as the keyword gives only its
    exact hit – the search is full text."""
    try:
        found = catalogue_search(keyword, page_size=limit)
    except Exception as e:  # network, changed API
        raise PartError(f"the catalogue did not answer ({str(e)[:200]})") from None
    if re.fullmatch(r"C\d+", keyword.strip()):
        found = [h for h in found if h.get("componentCode") == keyword.strip()]
    dropped = [h for h in found if str(h.get("componentCode") or "").startswith("C99")]
    rows = [{"lcsc": h.get("componentCode"), "mpn": h.get("componentModelEn"), "manufacturer": h.get("componentBrandEn"),
             "category": h.get("componentTypeEn"), "package": h.get("componentSpecificationEn"),
             "class": catalogue_class(h), "stock": int(h.get("stockCount") or 0)} for h in found if h not in dropped]
    if basic:
        rows = [r for r in rows if r["class"] != "Extended"]
    if min_stock is not None:
        rows = [r for r in rows if r["stock"] >= min_stock]
    rank = {"Basic": 0, "Extended, preferred": 1, "Extended": 2}
    return sorted(rows, key=lambda r: (rank[r["class"]], -r["stock"])), len(dropped)


def main_search(cfg, args):
    if not args.source:
        raise PartError('what to search for? edakit part search "RGB LED 5mm common cathode"')
    rows, dropped = search(args.source, args.basic, args.min_stock, args.limit)
    print(f'JLCPCB catalogue, "{args.source}", {today()}: '
          + (f"{len(rows)} hit(s)" if rows else "no hits")
          + (f", {dropped} C99… number{'s' if dropped > 1 else ''} dropped (user libraries, nobody sells them)"
             if dropped else ""))
    widths = {k: max([len(str(r[k] or "")) for r in rows] + [0]) for k in ("lcsc", "mpn", "manufacturer", "class")}
    for r in rows:
        print(f"{r['lcsc']:<{widths['lcsc']}}  {str(r['mpn'] or ''):<{widths['mpn']}}  "
              f"{str(r['manufacturer'] or ''):<{widths['manufacturer']}}  {r['class']:<{widths['class']}}  "
              f"{r['stock']:>8}  {r['package'] or ''} – {r['category'] or ''}")
    if args.json:
        Path(args.json).write_text(json.dumps({"query": args.source, "date": today(), "dropped_c99": dropped,
                                               "hits": rows}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if rows else 2


# --- how a new footprint maps onto the old one (part diff) ---------------------------------------------------------

TURNS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}   # cos, sin
TIE_MM = 0.05         # another fit within this RMS of the best one: the pad set is symmetric, the numbers decide
ROW_MM = 0.05         # pads whose centres share a coordinate within this stand in one row


def part_geometry(cfg, d, key):
    """(geometry, where it comes from) of a part named by its LCSC number or parts-entry key: the dump of a placed
    component that uses it – the project's footprint –, else the footprint data of its entry (4.5), else the library
    footprint part import cached."""
    from .footprint import geometry as data_geometry
    from .pcb import geometry_file
    for board in cfg.boards.values():
        dump = _read(geometry_file(cfg, board)) or {}
        for des in sorted(d.comps, key=natural_key):
            if des in dump and key in (d.entry_key(des), d.comps[des].get("lcsc")):
                return dump[des], f"pcb dump of {des}"
    entry = d.parts.get(key) or d.parts.get(d.by_mpn.get(key, "")) or {}
    if "footprint_data" in entry and (geo := data_geometry(entry)):
        return geo, f"footprint data of {key}"
    name = entry.get("footprint") or (cached(cfg, key) or {}).get("footprint")
    geo = cached_footprint(cfg, name)
    if geo:
        return geo, f"library geometry {name}"
    how = f"edakit part import {key}" if re.fullmatch(r"C\d+", key) else "edakit pcb dump once it is in the PCB"
    raise PartError(f"{key}: no footprint geometry – {how}")


def pad_points(geo):
    """[(number, x mm, y mm, pad)] – every pad, each shell leg of a number used several times."""
    out = []
    for n, p in geo["pads"].items():
        for q in (geo.get("pads_same_number") or {}).get(n) or [p]:
            out.append((n, q["x"] / MIL_PER_MM, q["y"] / MIL_PER_MM, {**p, **q}))
    return out


def turned(x, y, turn, mirror):
    """A pad of NEW turned on the same side – or, mirrored, as on the other side: EasyEDA mirrors the local y, then
    turns (config.Board.transform)."""
    c, s = TURNS[turn]
    y = -y if mirror else y
    return x * c - y * s, x * s + y * c


def fit(old, new, turn, mirror):
    """NEW's pads assigned to OLD's by position only – nearest assignment, after the origins and then the centroids
    are laid on each other, and the shift that lays the assigned pads over each other best."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    a = np.array([(x, y) for _, x, y, _ in old])
    b0 = np.array([turned(x, y, turn, mirror) for _, x, y, _ in new])
    best = None
    for shift in (np.zeros(2), a.mean(0) - b0.mean(0)):
        for _ in range(5):
            cost = np.linalg.norm(a[:, None, :] - (b0 + shift)[None, :, :], axis=2)
            i, j = linear_sum_assignment(cost)
            moved = (a[i] - b0[j]).mean(0)
            if np.allclose(moved, shift, atol=1e-6):
                break
            shift = moved
        cost = np.linalg.norm(a[:, None, :] - (b0 + shift)[None, :, :], axis=2)
        i, j = linear_sum_assignment(cost)
        res = cost[i, j]
        rms = float(np.sqrt((res ** 2).mean()))
        if best is None or rms < best["rms"] - 1e-9:
            best = {"turn": turn, "mirror": mirror, "shift": [float(v) for v in shift], "rms": rms,
                    "pairs": [(int(p), int(q), float(r)) for p, q, r in zip(i, j, res)]}
    return best


def spacing(points):
    """Smallest distance between two pads – a map is unambiguous while every pad lands within half of it."""
    import math
    return min((math.dist(p[1:3], q[1:3]) for k, p in enumerate(points) for q in points[k + 1:]), default=float("inf"))


def lands(c, old, new, limit):
    """Every pad of OLD has its partner: its centre lies on the copper of NEW's pad there (the pad's shape, size and
    rotation, turned and mirrored with NEW) – or, where a pad's size is unknown (a dump), within `limit` of it."""
    import math
    for i, j, r in c["pairs"]:
        pad = new[j][3]
        if not pad.get("w") or not pad.get("h"):
            if r >= limit:
                return False
            continue
        x, y = turned(new[j][1], new[j][2], c["turn"], c["mirror"])
        dx, dy = old[i][1] - x - c["shift"][0], old[i][2] - y - c["shift"][1]
        a = math.radians((-pad.get("rot", 0) if c["mirror"] else pad.get("rot", 0)) + c["turn"])
        u, v = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
        hw, hh = pad["w"] / MIL_PER_MM / 2, pad["h"] / MIL_PER_MM / 2
        inside = (u / hw) ** 2 + (v / hh) ** 2 <= 1 if pad.get("shape") == "ELLIPSE" else abs(u) <= hw and abs(v) <= hh
        if not inside:
            return False
    return True


def transform_name(c):
    return ("the mirror image" + (f" turned {c['turn']}°" if c["turn"] else "")) if c["mirror"] \
        else f"turned {c['turn']}°"


def pad_map(c, old, new):
    out = {}
    for i, j, _ in c["pairs"]:
        out.setdefault(old[i][0], set()).add(new[j][0])
    return {n: "/".join(sorted(m, key=natural_key)) for n, m in sorted(out.items(), key=lambda kv: natural_key(kv[0]))}


def rows(points, axis):
    """Pads in a row: centres sharing y (axis 1) or x (axis 0) within ROW_MM, at least two, ordered along the row."""
    groups = []
    for k in sorted(range(len(points)), key=lambda k: points[k][1 + axis]):
        if groups and abs(points[groups[-1][-1]][1 + axis] - points[k][1 + axis]) <= ROW_MM:
            groups[-1].append(k)
        else:
            groups.append([k])
    return [sorted(g, key=lambda k: points[k][2 - axis]) for g in groups if len(g) > 1]


def hole_text(pad):
    h = pad.get("hole")
    if not h:
        return "no hole" if not pad.get("tht") else "hole unknown"
    return f"Ø{h[0]:.2f}" if abs(h[1] - h[0]) < 0.01 else f"slot {h[0]:.2f} x {h[1]:.2f}"


def compare(cfg, old_key, new_key):
    """The comparison of `part diff` as a dict; text() prints it."""
    import math
    import statistics

    from .release.fab import JLC_SLOT_MM, hole_ok
    d = Design.from_config(cfg)
    (og, owhere), (ng, nwhere) = part_geometry(cfg, d, old_key), part_geometry(cfg, d, new_key)
    old, new = pad_points(og), pad_points(ng)
    if not old or not new:
        raise PartError(f"{old_key if not old else new_key}: a footprint without pads")
    limit = min(spacing(old), spacing(new)) / 2
    cands = [fit(old, new, t, m) for m in (False, True) for t in TURNS]
    for c in cands:
        c["fits"] = lands(c, old, new, limit)
        c["map"] = pad_map(c, old, new)
    ok = sorted((c for c in cands if c["fits"]), key=lambda c: c["rms"])
    same = [c for c in ok if not c["mirror"]]
    best = (same or ok or sorted(cands, key=lambda c: c["rms"]))[0]
    tie = [c for c in ok if c["rms"] <= best["rms"] + TIE_MM and c["mirror"] == best["mirror"]] or [best]
    best = min(tie, key=lambda c: (any(k != v for k, v in c["map"].items()), c["turn"]))   # numbers kept, least turn
    tie += [c for c in ok if c["rms"] <= best["rms"] + TIE_MM and c not in tie]
    others = [c for c in tie if c is not best and c["map"] != best["map"]]
    better = [c for c in ok if c["rms"] < best["rms"] - TIE_MM]          # only a mirror image can fit better
    entry = lambda key: d.parts.get(key) or d.parts.get(d.by_mpn.get(key, "")) or {}  # noqa: E731
    oe, ne = entry(old_key), entry(new_key)
    role = lambda e, n: ((e.get("pins") or {}).get(n) or {}).get("role")  # noqa: E731
    roles = [f"old {n} {role(oe, n) or '–'} → new {m} {role(ne, m) or '–'}" for n, m in best["map"].items()
             if "/" not in m and role(oe, n) != role(ne, m) and (role(oe, n) or role(ne, m))]
    pos = {j: turned(x, y, best["turn"], best["mirror"]) for j, (_, x, y, _) in enumerate(new)}
    partner = {i: j for i, j, _ in best["pairs"]}
    pitch = []
    for axis in (1, 0):
        for row in rows(old, axis):
            if all(k in partner for k in row):
                was = statistics.median(math.dist(old[a][1:3], old[b][1:3]) for a, b in zip(row, row[1:]))
                now = statistics.median(math.dist(pos[partner[a]], pos[partner[b]]) for a, b in zip(row, row[1:]))
                pitch.append({"row": "-".join(old[k][0] for k in row), "old_mm": round(was, 3), "new_mm": round(now, 3)})
    leads, holes, holes_fit = ne.get("lead"), [], True
    for i, j, _ in sorted(best["pairs"], key=lambda p: natural_key(old[p[0]][0])):
        po, pn = old[i][3], new[j][3]
        if not (po.get("tht") or pn.get("tht")):
            continue
        line = {"old": old[i][0], "new": new[j][0], "text": f"{hole_text(po)} → {hole_text(pn)} mm"}
        h = pn.get("hole")
        lead = (leads or {}).get(new[j][0]) or (leads or {}).get("*")
        if h and pn.get("plated", True) and lead:
            fits, tight, text = hole_ok(lead, h[0], h[1])
            narrow = h[1] > h[0] + 0.01 and h[0] < JLC_SLOT_MM - 1e-6
            line["l9"] = text + ("" if fits else " – does not take the lead") + (" – tight" if fits and tight else "") \
                + (f" – slot narrower than {JLC_SLOT_MM} mm (JLCPCB minimum)" if narrow else "")
            holes_fit &= fits and not narrow
        elif h:
            line["l9"] = f"no lead data in the entry of {new_key} – the fit is not checked (GEO.hole)"
        if not any(x["old"] == line["old"] and x["text"] == line["text"] for x in holes):   # shell legs: once
            holes.append(line)
    box = lambda g: ((g["bbox"][2] - g["bbox"][0]) / MIL_PER_MM, (g["bbox"][3] - g["bbox"][1]) / MIL_PER_MM)  # noqa
    nw, nh = box(ng)
    graph = []
    for des in sorted(d.comps, key=natural_key):
        c = d.comps[des]
        if old_key not in (d.entry_key(des), c.get("lcsc")):
            continue
        for p in sorted(c["pins"], key=natural_key):
            net = d.pin_net.get(f"{des}.{p}")
            if net and best["map"].get(p) != p:
                graph.append(f"{des}: {net} {p} → {best['map'].get(p) or 'no pad'}")
    matched = len(best["pairs"]) == len(old) == len(new)
    residuals = {}
    for i, _, r in best["pairs"]:        # shell legs of one number: the largest
        residuals[old[i][0]] = round(max(r, residuals.get(old[i][0], 0)), 3)
    return {"old": {"part": old_key, "footprint": og.get("footprint"), "from": owhere},
            "new": {"part": new_key, "footprint": ng.get("footprint"), "from": nwhere},
            "fits": best["fits"], "turn": best["turn"], "mirror": best["mirror"],
            "shift_mm": [round(v, 3) + 0.0 for v in best["shift"]], "rms_mm": round(best["rms"], 3),
            "mirror_only": bool(ok) and not same,
            "residual_mm": residuals,
            "map": best["map"], "symmetric": bool(others), "also_fit": [transform_name(c) for c in others],
            "fits_better": [f"{transform_name(c)} (RMS {c['rms']:.2f} mm)" for c in better],
            "unmatched_old": sorted({old[i][0] for i in range(len(old))} - {old[i][0] for i, _, _ in best["pairs"]},
                                    key=natural_key),
            "unmatched_new": sorted({new[j][0] for j in range(len(new))} - {new[j][0] for _, j, _ in best["pairs"]},
                                    key=natural_key),
            "roles": roles, "pitch": pitch, "holes": holes,
            "box_mm": {"old": [round(v, 2) for v in box(og)],
                       "new": [round(v, 2) for v in ((nh, nw) if best["turn"] in (90, 270) else (nw, nh))]},
            "graph": graph,
            "drop_in": bool(best["fits"] and not best["mirror"] and best["turn"] == 0 and matched and not roles
                            and all(k == v for k, v in best["map"].items()) and holes_fit)}


def text(r):
    """The comparison for the terminal."""
    o, n = r["old"], r["new"]
    out = [f"{o['part']} {o['footprint']} ({o['from']}) → {n['part']} {n['footprint']} ({n['from']})"]
    how = f"{transform_name(r)}, shift ({r['shift_mm'][0]:+.2f}, {r['shift_mm'][1]:+.2f}) mm, RMS {r['rms_mm']:.2f} mm"
    if not r["fits"]:
        out.append(f"no turn fits – the pads do not correspond one to one (closest: {how})")
    elif r["mirror_only"]:
        out.append(f"mirror image only – not on the same side: {how}")
    else:
        out.append(f"fit: {how}" + (f" – {' and '.join(r['also_fit'])} fit{'s' if len(r['also_fit']) == 1 else ''} "
                                    "equally (symmetric: the numbers decide)" if r["symmetric"] else ""))
        if r["fits_better"]:
            out.append(f"on the other side {' and '.join(r['fits_better'])} would fit better")
    out.append("map by position: " + ", ".join(f"{k}→{v}" for k, v in r["map"].items()))
    out.append("residual per pad (mm): " + ", ".join(f"{k} {v:.2f}" for k, v in sorted(
        r["residual_mm"].items(), key=lambda kv: natural_key(kv[0]))))
    if r["unmatched_old"] or r["unmatched_new"]:
        out.append(f"without a partner: old {', '.join(r['unmatched_old']) or '–'}, new "
                   f"{', '.join(r['unmatched_new']) or '–'}")
    if r["roles"]:
        out.append("roles that change: " + "; ".join(r["roles"]))
    for p in r["pitch"]:
        out.append(f"row {p['row']}: pitch {p['old_mm']:.2f} → {p['new_mm']:.2f} mm")
    for h in r["holes"]:
        pads = h["old"] if h["old"] == h["new"] else f"{h['old']}→{h['new']}"
        out.append(f"hole {pads}: {h['text']}" + (f" – GEO.hole: {h['l9']}" if h.get("l9") else ""))
    b = r["box_mm"]
    out.append(f"box: {b['old'][0]:.1f} x {b['old'][1]:.1f} mm → {b['new'][0]:.1f} x {b['new'][1]:.1f} mm")
    out += [f"graph change: {g}" for g in r["graph"]]
    out.append("drop-in: the same pads at the same places" if r["drop_in"] else "something to decide")
    return "\n".join(out)


def main_diff(cfg, args):
    if not (args.source and args.new):
        raise PartError("two parts are needed (edakit part diff C17179532 C49284748)")
    r = compare(cfg, args.source, args.new)
    print(text(r))
    if args.json:
        Path(args.json).write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if r["drop_in"] else 2


# --- SYNC.source -------------------------------------------------------------------------------------------------------------

def check(d, rep, cfg):
    """SYNC.source: own parts against their source, and this project's datasheets against its state."""
    for key in sorted({d.entry_key(des) for des in d.comps} - {None}):
        entry = d.parts[key]
        own_ = entry.get("own")
        if not own_:
            continue
        who = f"{', '.join(des for des in d.comps if d.entry_key(des) == key)} {entry.get('mpn', key)}"
        if own_.get("what") not in WHAT:
            rep.error("SYNC.source", f"{who}: own.what is {own_.get('what')!r} – one of {', '.join(WHAT)}")
            continue
        if own_["what"] != "pcb":
            continue
        missing = [k for k in ("path", "connectors", "state_sha256", "commit") if not own_.get(k)]
        if missing:
            rep.error("SYNC.source", f"{who}: own part without own.{missing[0]} – edakit part own")
            continue
        path = own_["path"]
        if "uncommitted" in own_["commit"]:
            rep.pending.append(("SYNC.source", f"{who}: copied from uncommitted changes in {path} – commit there and renew "
                                       f"with edakit part own {path}"))
        toml = cfg.root / path / "edakit.toml"
        if not toml.is_file():
            rep.notes.append(("SYNC.source", f"{who}: {path} not found – the copy is not compared with its source"))
        else:
            try:
                changed = state_hash(config.load(toml)) != own_["state_sha256"]
            except config.ConfigError as e:
                rep.notes.append(("SYNC.source", f"{who}: {path} cannot be read ({e}) – the copy is not compared with its "
                                         "source"))
            else:
                if changed:
                    rep.pending.append(("SYNC.source", f"{who}: {path} has changed since its datasheet – edakit part "
                                               f"datasheet there, then edakit part own {path}"))
        if not own_.get("released"):
            rep.warnings.append(("SYNC.source", f"{who}: {path} is not released at the state of its datasheet – release it "
                                        f"(edakit gate) and renew with edakit part own {path}, or accept the warning "
                                        "in the sign-off file"))
    sheets = sorted(datasheet_dir(cfg).glob("*.json"))
    state = state_hash(cfg) if sheets else None
    for f in sheets:
        sheet = json.loads(f.read_text(encoding="utf-8"))
        if (sheet.get("own") or {}).get("state_sha256") != state:
            rep.pending.append(("SYNC.source", f"{sheet.get('mpn', f.stem)}: datasheet export of an older state – edakit "
                                       "part datasheet"))


def main(cfg, args):
    from .sim import run as simrun
    try:
        if args.action == "import":
            return main_import(cfg, args)
        if args.action == "lint":
            from . import schema
            return schema.main_lint(cfg, args)
        if args.action == "diff":
            return main_diff(cfg, args)
        if args.action == "fetch":
            return main_fetch(cfg, args)
        if args.action == "search":
            return main_search(cfg, args)
        if args.action in ("footprint", "build"):
            from . import footprint
            try:
                return (footprint.main_footprint if args.action == "footprint" else footprint.main_build)(cfg, args)
            except footprint.FootprintError as e:
                print(f"edakit part {args.action}: {e}", file=sys.stderr)
                return 1
        if args.action == "datasheet":
            if args.connector:
                done = [write_datasheet(cfg, args.connector, args.name)[0]]
            else:
                done = renew_datasheets(cfg)
                if not done:
                    print("edakit part datasheet: no datasheet yet – name the connectors: --connector J1",
                          file=sys.stderr)
                    return 1
            for f in done:
                e = json.loads(f.read_text(encoding="utf-8"))
                print(f"{cfg.relative(f)} and {f.with_suffix('.md').name}: {e['mpn']} through "
                      f"{', '.join(e['own']['connectors'])}, {e['values']['i_a'] * 1e3:.0f} mA at "
                      f"{e['limits']['vin_min_v']} … {e['limits']['vin_max_v']} V")
                for num, p in e["pins"].items():
                    print(f"  {num:>3} {p['name']:<12} {p['type']:<14} {p.get('role', '')}")
            return 0
        if not args.source:
            print("edakit part own: the board's project is missing (edakit part own ../board)", file=sys.stderr)
            return 1
        out, entry, todo = own(cfg, args.source, args.name)
        o = entry["own"]
        print(f"{cfg.relative(out)}: {entry['mpn']} from {o['path']} at {o['commit'][:12]}"
              + (" (released " + str(o["released"]["time"]) + ")" if o.get("released") else " – not released"))
        for t in todo:
            print("  " + t)
        return 0
    except (PartError, config.ConfigError, simrun.SimError) as e:
        print(f"edakit part: {e}", file=sys.stderr)
        return 1
