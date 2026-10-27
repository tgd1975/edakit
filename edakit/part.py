"""Parts: what the library says about an LCSC number, and own parts.

    edakit part import C2297 [--update]
                                symbol pins, footprint and identification of exactly that LCSC number from the
                                library's public data, without EasyEDA: a new parts entry, or the differences to the
                                existing one (--update fills in missing fields); the geometry and the symbol cached in
                                <artifacts>/footprints/<footprint>.json and <artifacts>/library/<LCSC>.json

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
