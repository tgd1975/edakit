"""Parts: what the library says about an LCSC number, how a new footprint maps onto the old one, and own parts.

    edakit part import C2297 [--update]
                                symbol pins, footprint and identification of exactly that LCSC number from the
                                library's public data, without EasyEDA: a new parts entry, or the differences to the
                                existing one (--update fills in missing fields); the geometry and the symbol cached in
                                <artifacts>/footprints/<footprint>.json and <artifacts>/library/<LCSC>.json
    edakit part diff OLD NEW [--json FILE]
                                before a swap: the turn and shift that lay NEW's pads over OLD's (and whether the
                                mirror image fits), the pad map by position, roles, pitch, holes and box that change,
                                the graph change it implies; exit 0 = drop-in, 2 = something to decide

The library geometry has the units and axes of `edakit pcb dump` (mil, y up, relative to the part origin at 0° on
TOP); a pad with a hole adds `hole` [w, l] in mm and `plated`, every pad its shape, size `w` × `h` (mil) and `rot`.
P-1 compares the graph with a cached symbol, `pcb plan` takes a cached footprint for a part that is not in the PCB yet.

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
  ratings     vin_min, vin_max: the voltage at the connector over those scenarios – E-3 holds the host to it
  compliance  from the board's parts: RoHS, REACH statements, radio
  own         what "pcb", connectors, the hash of the board's circuit (state_sha256); the copy adds path, commit,
              repository and the release of that state

P-3 compares the copy with its source and a project's datasheets with its state (checks.py calls check()).
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from . import checks, config
from .config import MIL_PER_MM
from .design import Design, natural_key

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
    return gate.file_hash(cfg.root, gate.state_files(cfg))


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
    """The board's own scenarios (fault cases with info left out), with the nets in `probe` reported."""
    from .sim import run as simrun
    info = {s["name"] for s in simrun.scenarios(sim) if s.get("info")}
    plugin = simrun.load_plugin(cfg.sim_plugin) if cfg.sim_plugin else None
    out = simrun.run_all(d, {**sim, "report": list(dict.fromkeys(probe))}, plugin=plugin)
    rows = [s for s in out["scenarios"] if s["name"] not in info]
    bad = [s["name"] for s in rows if s["status"] != "ok"]
    if bad:
        raise PartError(f"the simulation of the board fails in {len(bad)} scenario(s) ({', '.join(bad[:3])}) – "
                        "edakit sim; a datasheet of a board that does not work describes nothing")
    return rows


def pull(d, net):
    """('up'|'down', parallel resistance or None) of the resistors from the net to a supply or to ground."""
    for way, targets in (("up", checks.supply_nets(d)), ("down", {d.ground})):
        rs = [r for _, r, _ in checks.resistors_to(d, net, targets)]
        if rs:
            return way, (1 / sum(1 / r for r in rs) if all(rs) else None)
    return None, None


def limit(d, net, inside):
    """Lowest voltage limit on the net: pin vmax, capacitor v_max / 1.5 (G-8's margin) – with what sets it."""
    found = []
    for ref in inside:
        info = d.pin_info(ref)
        if info.get("vmax") is not None:
            found.append((float(info["vmax"]), f"{ref} ({info.get('name', '')}) vmax"))
        p = d.part(ref.split(".", 1)[0]) or {}
        if p.get("kind") == "capacitor" and (p.get("ratings") or {}).get("v_max"):
            found.append((round(p["ratings"]["v_max"] / checks.CAP_FACTOR, 2),
                          f"{ref.split('.', 1)[0]} v_max {p['ratings']['v_max']} V / {checks.CAP_FACTOR}"))
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
    line = checks.i2c_name(net) or next((x for x in map(checks.i2c_line, map(d.pin_info, inside)) if x), None)
    if line:
        return {"type": "bidirectional", "role": line}
    if d.nets[net].get("bus") == "i2c":
        return {"type": "bidirectional"}      # an I2C line that does not say which: the host's net says it
    return {"type": next((t for t in SIGNALS if t in types), "passive")}


def compliance(d, project, state):
    """What the parts entries of the board say about RoHS, REACH and radio."""
    rohs = {"not compliant": [], "exemption": [], "not known": []}
    reach, radio, n = [], [], 0
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
        if c.get("radio"):
            radio.append({"part": des, **c["radio"]})
    out = {"rohs": True if not any(rohs.values()) else "; ".join(f"{k}: {', '.join(v)}" for k, v in rohs.items() if v),
           "reach": (f"a supplier statement for each of the {n} parts" if not reach else
                     f"{n - len(reach)} of {n} parts with a supplier statement; none for {', '.join(reach)}")}
    if radio:
        out["radio"] = radio[0] if len(radio) == 1 else radio
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
            info["vmax"] = vmax
            srcs.append(f"pin {num} vmax: {why}")
        entry_pins[num] = info
        notes[num] = inside
    i_a = round(worst["sources"][des], 4)
    lo, hi = round(min(volts), 3), round(max(volts), 3)
    srcs += [f"params.i_a: the largest current from {des} over {len(rows)} scenarios of "
             f"{cfg.relative(cfg.sim_config)} ({worst['name']})",
             f"ratings vin_min, vin_max: the voltage at {des} over those scenarios"]
    entry = {
        "mpn": name or cfg.project, "manufacturer": f"own board ({cfg.project})", "kind": "module",
        "datasheet": {"url": file_name(name or cfg.project)[:-5] + ".md"},
        "pins": entry_pins,
        "params": {"behavior": "current", "i_a": i_a},
        "ratings": {"vin_min": lo, "vin_max": hi},
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
        pull_txt = f"{p['pull']} {checks.ohm(p['pull_ohm'])}" if p.get("pull_ohm") else p.get("pull", "–")
        lines.append(f"| {num} | {p['name']} | {p['type']} | {p.get('role', '–')} | {p.get('vmax', '–')} | "
                     f"{pull_txt} | {there or '–'} |")
    i_a, r = entry["params"]["i_a"], entry["ratings"]
    lines += ["", "## Supply", "",
              f"Through {plus} against {minus} at {des}, as simulated over {len(rows)} scenarios of "
              f"{cfg.relative(cfg.sim_config)} (`edakit sim` there):", "",
              f"- voltage at the connector: {r['vin_min']} … {r['vin_max']} V – a project that uses the board must "
              "keep it there (E-3)",
              f"- largest current: {i_a * 1e3:.0f} mA", "",
              "| Scenario | Voltage | Current |", "|---|---|---|"]
    lines += [f"| {s['name']} | {s['nets'][plus] - s['nets'][minus]:.3f} V | {s['sources'][des] * 1e3:.0f} mA |"
              for s in rows]
    c = entry["compliance"]
    radio = c.get("radio")
    lines += ["", "## Compliance", "",
              f"- RoHS: {'all parts compliant' if c['rohs'] is True else c['rohs']}",
              f"- REACH: {c['reach']}",
              "- radio: " + ("none" if not radio else "; ".join(
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
              "it checks them with G-3, G-4, G-5 and G-11"]
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
        todo.append(f"copied from uncommitted changes in {path} – commit there and copy again (P-3 stays open)")
    if not entry["own"]["released"]:
        todo.append(f"{path} is not released at this state – P-3 warns until it is (edakit gate there, then copy "
                    "again) or the warning is accepted in the sign-off file")
    if not entry["verified"]:
        todo.append("sign it off against its datasheet (handbook 4.3; G-9 stays open until then)")
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
    geo = {"footprint": footprint, "bbox": [round(v, 2) for v in box], "pads": {}}
    for n, p in pads:
        geo["pads"].setdefault(n, p)
    nums = [n for n, _ in pads]
    if dup := sorted({n for n in nums if nums.count(n) > 1}, key=natural_key):   # shell legs: all of them here
        geo["pads_same_number"] = {n: [p for m, p in pads if m == n] for n in dup}
    return geo


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
    """The cached library geometry of a component's footprint: the name of its parts entry, else of the library."""
    name = (design.part(des) or {}).get("footprint") or (cached(cfg, design.comps[des].get("lcsc")) or {}).get(
        "footprint")
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
    in the footprint name, which L-4 compares as it is), pins as S-2 compares them."""
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
              "(handbook 4.3; G-9 stays open until then)")
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
    print(f"  symbol: {cfg.relative(cache['symbol'])} – P-1 compares the graph with it")
    return 2 if diffs else 0


# --- how a new footprint maps onto the old one (part diff) ---------------------------------------------------------

TURNS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}   # cos, sin
TIE_MM = 0.05         # another fit within this RMS of the best one: the pad set is symmetric, the numbers decide
ROW_MM = 0.05         # pads whose centres share a coordinate within this stand in one row


def part_geometry(cfg, d, key):
    """(geometry, where it comes from) of a part named by its LCSC number or parts-entry key: the dump of a placed
    component that uses it – the project's footprint –, else the library footprint part import cached."""
    from .pcb import geometry_file
    for board in cfg.boards.values():
        dump = _read(geometry_file(cfg, board)) or {}
        for des in sorted(d.comps, key=natural_key):
            if des in dump and key in (d.entry_key(des), d.comps[des].get("lcsc")):
                return dump[des], f"pcb dump of {des}"
    entry = d.parts.get(key) or d.parts.get(d.by_mpn.get(key, "")) or {}
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
            line["l9"] = f"no lead data in the entry of {new_key} – the fit is not checked (P-7)"
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
        out.append(f"hole {pads}: {h['text']}" + (f" – L-9: {h['l9']}" if h.get("l9") else ""))
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


# --- P-3 -------------------------------------------------------------------------------------------------------------

def check(d, rep, cfg):
    """P-3: own parts against their source, and this project's datasheets against its state."""
    for key in sorted({d.entry_key(des) for des in d.comps} - {None}):
        entry = d.parts[key]
        own_ = entry.get("own")
        if not own_:
            continue
        who = f"{', '.join(des for des in d.comps if d.entry_key(des) == key)} {entry.get('mpn', key)}"
        if own_.get("what") not in WHAT:
            rep.error("P-3", f"{who}: own.what is {own_.get('what')!r} – one of {', '.join(WHAT)}")
            continue
        if own_["what"] != "pcb":
            continue
        missing = [k for k in ("path", "connectors", "state_sha256", "commit") if not own_.get(k)]
        if missing:
            rep.error("P-3", f"{who}: own part without own.{missing[0]} – edakit part own")
            continue
        path = own_["path"]
        if "uncommitted" in own_["commit"]:
            rep.pending.append(("P-3", f"{who}: copied from uncommitted changes in {path} – commit there and renew "
                                       f"with edakit part own {path}"))
        toml = cfg.root / path / "edakit.toml"
        if not toml.is_file():
            rep.notes.append(("P-3", f"{who}: {path} not found – the copy is not compared with its source"))
        else:
            try:
                changed = state_hash(config.load(toml)) != own_["state_sha256"]
            except config.ConfigError as e:
                rep.notes.append(("P-3", f"{who}: {path} cannot be read ({e}) – the copy is not compared with its "
                                         "source"))
            else:
                if changed:
                    rep.pending.append(("P-3", f"{who}: {path} has changed since its datasheet – edakit part "
                                               f"datasheet there, then edakit part own {path}"))
        if not own_.get("released"):
            rep.warnings.append(("P-3", f"{who}: {path} is not released at the state of its datasheet – release it "
                                        f"(edakit gate) and renew with edakit part own {path}, or accept the warning "
                                        "in the sign-off file"))
    sheets = sorted(datasheet_dir(cfg).glob("*.json"))
    state = state_hash(cfg) if sheets else None
    for f in sheets:
        sheet = json.loads(f.read_text(encoding="utf-8"))
        if (sheet.get("own") or {}).get("state_sha256") != state:
            rep.pending.append(("P-3", f"{sheet.get('mpn', f.stem)}: datasheet export of an older state – edakit "
                                       "part datasheet"))


def main(cfg, args):
    from .sim import run as simrun
    try:
        if args.action == "import":
            return main_import(cfg, args)
        if args.action == "diff":
            return main_diff(cfg, args)
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
                      f"{', '.join(e['own']['connectors'])}, {e['params']['i_a'] * 1e3:.0f} mA at "
                      f"{e['ratings']['vin_min']} … {e['ratings']['vin_max']} V")
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
