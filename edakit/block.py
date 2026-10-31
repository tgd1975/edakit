"""Building blocks: small circuits with checked parts that go into the hardware graph in one step.

    edakit block list
    edakit block show NAME
    edakit block add NAME --as INSTANCE [--connect PORT=NET ...] [--without DES ...] [--board B] [--file BLOCK.json]
                     [--dry-run]

A block (edakit/blocks/<name>.json, or any file given with --file) is a piece of graph: components with LCSC numbers,
nets, and ports – the nets that connect to the rest of the circuit. `add` copies it into the project's graph:

  - designators get the next free numbers of their prefix (R1 -> R7), "{as}" in labels becomes the instance name
  - internal nets are named <INSTANCE>_<NET>; a port joins the net given with --connect PORT=NET; a port without
    --connect becomes its own net <INSTANCE>_<PORT>, except "gnd", which joins the project's ground
  - a net that does not exist yet gets the block's voltage range: [min, max], or "@port" for the range of the net that
    port is connected to
  - missing parts entries are copied from edakit's parts library (edakit/parts/, edakit part add) with their
    provenance; an existing entry must have the same pins
  - "graph": {"grounds": [net, …]} – graph-level keys the block brings: its nets that are a ground of their own (a
    protection IC on the cell's minus) join the project's `grounds`
  - "optional": {"parts": [designator, …], "ports": [port, …]} – parts --without may leave out, and ports that may stay
    unconnected: a pin left alone on its net goes into its component's nc instead of a net of one pin
  - an accept keyed by "code place" names the block's designators; they are renamed with the parts
  - the graph file keeps its formatting (indent, UTF-8); nothing is written with --dry-run

The block's notes say what is left to decide (values, sim.json, the graph's checks). Afterwards: edakit check, edakit hints,
edakit sim – a block is a starting point that passed the checks once, not a sign-off.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .design import natural_key

LIBRARY = Path(__file__).with_name("blocks")


class BlockError(Exception):
    pass


def library():
    return {p.stem: p for p in sorted(LIBRARY.glob("*.json"))}


def load(name=None, file=None):
    path = Path(file) if file else library().get(name)
    if path is None or not path.exists():
        raise BlockError(f"no block '{name or file}' – blocks: {', '.join(library())}")
    return json.loads(path.read_text(encoding="utf-8"))


def library_part(lcsc):
    from . import library as parts_library
    return parts_library.entry(lcsc)


def split_designator(des):
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", des)
    if not m:
        raise BlockError(f"block designator '{des}' is not <letters><number>")
    return m.group(1), int(m.group(2))


def free_numbers(graph):
    """{prefix: highest number in use} of the project graph."""
    top = {}
    for c in graph["components"]:
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", c["designator"])
        if m:
            top[m.group(1)] = max(top.get(m.group(1), 0), int(m.group(2)))
    return top


def without_parts(block, without):
    """The block with the optional parts `without` names left out – their pins out of the nets (a net left without
    pins is not made; one pin alone on an unconnected optional port goes into its component's nc, plan)."""
    optional = block.get("optional") or {}
    unknown = sorted(set(without) - set(optional.get("parts", [])))
    if unknown:
        raise BlockError(f"block {block['name']}: {', '.join(unknown)} is no optional part (optional: "
                         f"{', '.join(optional.get('parts', [])) or 'none'})")
    gone = set(without)
    comps = [dict(c) for c in block["components"] if c["designator"] not in gone]
    nets = [{**n, "pins": [r for r in n["pins"] if r.split(".", 1)[0] not in gone]} for n in block["nets"]]
    return {**block, "components": comps, "nets": nets}     # a net left without pins still lends its range (@port)


def rename_accept(acc, rename):
    """An accept table with the designators its "code place" keys name renamed as the parts are."""
    out = {}
    for key, reason in (acc or {}).items():
        code, sep, place = key.partition(" ")
        if sep:
            des, dot, rest = place.partition(".")
            place = rename.get(des, des) + dot + rest
        out[code + sep + place] = reason
    return out


def plan(block, graph, instance, connect, ground, board=None, without=()):
    """What `add` would do: (components, new nets, extended nets {name: [pins]}, attributes for existing nets
    {name: {key: value}} such as "bus": "i2c", LCSC numbers used, grounds the block brings)."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", instance or ""):
        raise BlockError("--as needs a name for this instance: letters, digits, underscore (e.g. STATUS, BUZ)")
    block = without_parts(block, without)
    ports = block.get("ports", {})
    unknown = sorted(set(connect) - set(ports))
    if unknown:
        raise BlockError(f"block {block['name']} has no port {', '.join(unknown)} (ports: {', '.join(ports)})")
    loose = set((block.get("optional") or {}).get("ports", []))       # unconnected, a pin alone goes into nc
    nc_more = {}
    kept = []
    for net in block["nets"]:
        if net["name"] in loose and net["name"] not in connect and len(net["pins"]) == 1:
            des, _, pin = net["pins"][0].partition(".")
            nc_more.setdefault(des, []).append(pin)
            continue
        kept.append(net)
    block = {**block, "nets": kept}
    top = free_numbers(graph)
    rename = {}
    for c in block["components"]:
        prefix, _ = split_designator(c["designator"])
        top[prefix] = top.get(prefix, 0) + 1
        rename[c["designator"]] = f"{prefix}{top[prefix]}"
    existing = {n["name"]: n for n in graph["nets"]}
    target = {}
    for net in block["nets"]:
        name = net["name"]
        if name in ports:
            target[name] = connect.get(name) or (ground if name == "gnd" else f"{instance}_{name}".upper())
        else:
            target[name] = f"{instance}_{name}".upper()
    own = [n for n in target if n not in ports or (n not in connect and n != "gnd")]  # names the block makes up
    clash = sorted(target[n] for n in own if target[n] in existing)
    if clash:
        raise BlockError(f"net {', '.join(clash)} exists already – choose another --as")

    def v_of(name, seen=()):
        net = next(n for n in block["nets"] if n["name"] == name)
        if target[name] in existing:
            return existing[target[name]].get("v")
        v = net.get("v")
        if isinstance(v, str) and v.startswith("@"):
            ref = v[1:]
            if ref in seen or ref not in target:
                raise BlockError(f"block {block['name']}: net {name} takes its range from unknown port {ref}")
            return v_of(ref, seen + (name,))
        if v is None:
            raise BlockError(f"port {name}: net {target[name]} does not exist and the block has no voltage range for "
                             f"it – connect the port to an existing net (--connect {name}=<NET>) or create the net first")
        return v

    comps = []
    for c in block["components"]:
        new = {k: v for k, v in c.items() if k != "designator"}
        new = {"designator": rename[c["designator"]], **{k: (v.replace("{as}", instance) if isinstance(v, str) else v)
                                                          for k, v in new.items()}}
        if c["designator"] in nc_more:
            new["nc"] = list(dict.fromkeys(list(new.get("nc", [])) + nc_more[c["designator"]]))
        if new.get("accept"):
            new["accept"] = rename_accept(new["accept"], rename)
        new["notes"] = (new.get("notes", "") + f" (block {block['name']}, {instance})").strip()
        if board:
            new["board"] = board
        comps.append(new)
    new_nets, extended, attrs = {}, {}, {}
    for net in block["nets"]:
        pins = [f"{rename[p.split('.', 1)[0]]}.{p.split('.', 1)[1]}" for p in net["pins"]]
        if not pins:                       # all its pins were optional parts left out
            continue
        name = target[net["name"]]
        extra = {k: v for k, v in net.items() if k not in ("name", "pins", "v", "notes")}  # e.g. "bus": "i2c"
        if extra.get("accept"):
            extra["accept"] = rename_accept(extra["accept"], rename)
        if name in existing:
            extended.setdefault(name, []).extend(pins)
            attrs.setdefault(name, {}).update(extra)
        elif name in new_nets:  # two ports connected to the same new net
            new_nets[name]["pins"] += pins
            new_nets[name].update(extra)
        else:
            new_nets[name] = {"name": name, "pins": pins, "v": v_of(net["name"]), **extra}
            if net.get("notes"):
                new_nets[name]["notes"] = net["notes"].replace("{as}", instance)
    lcsc = sorted({c["lcsc"] for c in comps if c.get("lcsc")}, key=natural_key)
    grounds = []
    for name in (block.get("graph") or {}).get("grounds", []):
        if name not in target:
            raise BlockError(f"block {block['name']}: graph.grounds names {name}, which is none of its nets")
        grounds.append(target[name])
    return comps, list(new_nets.values()), extended, attrs, lcsc, grounds


def parts_to_copy(lcsc_numbers, parts_dir, comps):
    """LCSC numbers whose entry must come from the library; an existing project entry must have the block's pins."""
    copy = []
    for lcsc in lcsc_numbers:
        mine = parts_dir / f"{lcsc}.json"
        entry = json.loads(mine.read_text(encoding="utf-8")) if mine.exists() else library_part(lcsc)
        if entry is None:
            raise BlockError(f"{lcsc}: neither in {parts_dir} nor in the parts library – part-search skill first")
        names = {k: v["name"] for k, v in entry["pins"].items()}
        for c in comps:
            if c.get("lcsc") == lcsc and c["pins"] != names:
                raise BlockError(f"{c['designator']}: pins of the block {c['pins']} differ from the parts entry {lcsc} "
                                 f"{names}")
        if not mine.exists():
            copy.append(lcsc)
    return copy


def write_json(path, data):
    """Write like the file was written before: same indent, UTF-8 characters as they are."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^( +)\S", text, re.M)
    path.write_text(json.dumps(data, indent=len(m.group(1)) if m else 1, ensure_ascii=False) + "\n", encoding="utf-8")


def add(cfg, name, instance, connect, board=None, file=None, dry_run=False, without=()):
    block = load(name, file)
    data = json.loads(cfg.graph.read_text(encoding="utf-8"))
    graph = data.get("graph", data)
    if board is None and len(cfg.boards) > 1:
        raise BlockError(f"several boards ({', '.join(cfg.boards)}): say which one with --board")
    if board is not None and board not in cfg.boards:
        raise BlockError(f"no board '{board}' in edakit.toml (boards: {', '.join(cfg.boards)})")
    missing = sorted(t for t in connect.values() if t not in {n["name"] for n in graph["nets"]})
    comps, new_nets, extended, attrs, lcsc, grounds = plan(block, graph, instance, connect, graph.get("ground", "GND"),
                                                           board if len(cfg.boards) > 1 else None, without)
    copy = parts_to_copy(lcsc, cfg.parts, comps)
    if not dry_run:
        if grounds:
            graph["grounds"] = list(dict.fromkeys(list(graph.get("grounds") or []) + grounds))
        graph["components"] += comps
        for net in graph["nets"]:
            net["pins"] += extended.get(net["name"], [])
            for key, value in attrs.get(net["name"], {}).items():
                net.setdefault(key, value)
        graph["nets"] += new_nets
        write_json(cfg.graph, data)
        from . import library as parts_library
        for n in copy:
            parts_library.copy_into(cfg.parts, n)
    return block, comps, new_nets, extended, attrs, copy, missing


def main(cfg, args):
    try:
        if args.action == "list":
            for name, path in library().items():
                b = json.loads(path.read_text(encoding="utf-8"))
                print(f"{name:<16} {b['title']}\n{'':<16} ports: {', '.join(b['ports'])}")
            print("\nDetails: edakit block show NAME")
            return 0
        if not args.name:
            raise BlockError("which block? edakit block list")
        if args.action == "show":
            b = load(args.name, args.file)
            print(f"{b['name']}: {b['title']}\n\n{b['about']}\n\nPorts:")
            for port, about in b["ports"].items():
                print(f"  {port:<8} {about}")
            print("\nParts:")
            for c in b["components"]:
                print(f"  {c['designator']:<5} {c.get('lcsc', ''):<9} {c.get('value', ''):<8} {c['label']}")
            print("\nNets:")
            for n in b["nets"]:
                print(f"  {n['name']:<8} {', '.join(n['pins'])}" + (f"   v {n['v']}" if "v" in n else ""))
            if b.get("covers"):
                print(f"\nCovers: {', '.join(b['covers'])} (edakit rules …)")
            for note in b.get("notes", []):
                print(f"- {note}")
            return 0
        connect = {}
        for item in args.connect or []:
            port, sep, net = item.partition("=")
            if not sep or not net:
                raise BlockError(f"--connect {item}: expected PORT=NET")
            connect[port] = net
        block, comps, new_nets, extended, attrs, copy, missing = add(cfg, args.name, args.instance, connect,
                                                                     args.board, args.file, args.dry_run,
                                                                     getattr(args, "without", None) or ())
    except (BlockError, KeyError, ValueError) as e:
        print(f"edakit block: {e}")
        return 1
    head = "would add" if args.dry_run else "added"
    print(f"{head} block {block['name']} as {args.instance}:")
    for c in comps:
        print(f"  {c['designator']:<5} {c.get('lcsc', ''):<9} {c.get('value', ''):<8} {c['label']}")
    for name, pins in extended.items():
        print(f"  net {name} (exists) + {', '.join(pins)}"
              + "".join(f", {k}: {v}" for k, v in attrs.get(name, {}).items()))
    for n in new_nets:
        print(f"  net {n['name']} (new, v {n['v']}): {', '.join(n['pins'])}"
              + ("  – created by --connect" if n["name"] in missing else ""))
    if copy:
        print(f"  parts entries {'to copy' if args.dry_run else 'copied'} from the parts library: {', '.join(copy)}")
    for note in block.get("notes", []):
        print(f"- {note}")
    print("Next: edakit check, edakit hints, edakit sim – and the decisions the notes name.")
    return 0
