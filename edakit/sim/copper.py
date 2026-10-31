"""The routed copper of chosen nets as resistors in the simulation (sim.json "copper").

    "copper": {"nets": ["+5V", "VIN"], "oz": 1, "via_ohm": 0.001}

Per board the routing of `edakit route` – <artifacts>/route/<board>.ses with <board>_board.json, read as `edakit route
check` reads them. For every listed net each of its pins gets a node of its own; every track piece becomes a resistor
rho x L / (w x t) between its ends (t = oz x 35 µm), every via via_ohm between its two layers. A track end or a via
inside a pad joins that pad's pin, ends that meet are one point (route.segments). The net's pours ([[pours]] of the
board file) count as ideal: on a layer the net pours, all its copper is one node. A net on a board without routing,
with a pin that has no pad, or whose copper leaves a pin unconnected stays one ideal node, and the simulation notes it
(SIM.copper, "copper not annotated").

annotate() stores the result on the design (design.copper), as split_boards stores the cables; netlist.Netlist puts a
pin of an annotated net on its pad node, run.py reads a net's voltage at the lowest and the highest of its pins.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict

RHO_OHM_MM = 1.72e-5      # copper at 20 °C: 0.0172 Ω·mm²/m
OZ_MM = 0.035             # 1 oz/ft² copper: 35 µm
MM_PER_MIL = 0.0254
KEYS = {"nets", "oz", "via_ohm", "about", "note"}


class CopperError(ValueError):
    pass


def settings(design, sim):
    """The checked `copper` of the simulation config, or None without it."""
    spec = sim.get("copper")
    if spec is None:
        return None
    if not isinstance(spec, dict) or set(spec) - KEYS:
        extra = ", ".join(sorted(set(spec) - KEYS)) if isinstance(spec, dict) else repr(spec)
        raise CopperError(f"copper: {extra} – a map with nets, oz and via_ohm expected")
    nets = spec.get("nets")
    if not isinstance(nets, list) or not all(isinstance(n, str) for n in nets):
        raise CopperError(f"copper: nets, a list of net names, expected, not {nets!r}")
    for n in nets:
        if n not in design.nets:
            raise CopperError(f"copper: {n} is no net of the graph")
        if n == design.ground:
            raise CopperError(f"copper: {n} is the ground net – the reference of every voltage stays one node")
    oz, via = spec.get("oz", 1), spec.get("via_ohm", 0.001)
    if not isinstance(oz, (int, float)) or isinstance(oz, bool) or oz <= 0:
        raise CopperError(f"copper: oz, the copper weight (1 = 35 µm), expected, not {oz!r}")
    if not isinstance(via, (int, float)) or isinstance(via, bool) or via < 0:
        raise CopperError(f"copper: via_ohm, the resistance of one via in Ω, expected, not {via!r}")
    return {"nets": list(dict.fromkeys(nets)), "oz": oz, "via_ohm": via}


def load_routing(cfg):
    """{board: {"data", "routes", "rules"}} of every board whose routing session and board json exist in the artifacts
    (read only), {board: None} for the others."""
    from .. import route
    out = {}
    for name in cfg.boards:
        board = cfg.board(name)
        ses, data = (cfg.artifacts / "route" / f"{board.name}{x}" for x in (".ses", "_board.json"))  # as route.paths,
        if not (ses.exists() and data.exists()):                                                # without creating it
            out[name] = None
            continue
        rules = route.Rules(board)
        out[name] = {"data": json.loads(data.read_text()), "routes": route.read_ses(ses, rules), "rules": rules}
    return out


def node_name(text):
    return "n_" + re.sub(r"\W", "_", text.lower())


def poured_layers(board, net):
    """Layers on which the board pours the net (as `pcb pour` does: planes default to BOTTOM, pours to both)."""
    return {layer for p in board.pours if p.get("net") == net
            for layer in p.get("layers", ["BOTTOM"] if p.get("plane") else ["TOP", "BOTTOM"])}


def net_network(net, refs, r, oz, via_ohm):
    """The copper of one net on one board (pins `refs`) -> ((pads {pin ref: key}, resistors [(key, key, Ω)]), None),
    the keys already joined where copper meets without resistance; (None, the reason) where it cannot be annotated."""
    from shapely.geometry import Point
    from .. import route
    data, routes, rules = r["data"], r["routes"], r["rules"]
    pads = defaultdict(list)
    for p in data.get("pads", []):
        if p.get("net") == net:
            pads[f"{p['ref']}.{p['num']}"].append(p)
    missing = [ref for ref in refs if ref not in pads]
    if missing:
        return None, f"no pad for {', '.join(missing)} in route/{rules.board.name}_board.json"
    if "segs" not in r:
        r["segs"] = route.segments(rules, routes, data)
    segs = r["segs"].get(net, [])
    vias = [tuple(v) for v in routes.get(net, {}).get("vias", [])]
    r_via = rules.via[1] / 2
    poured = poured_layers(rules.board, net)
    parent = {}

    def root(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def join(a, b):
        parent[root(a)] = root(b)
    shapes = [(ref, set(route.pad_layers(p)), route.pad_outline(p).buffer(0.01)) for ref in refs for p in pads[ref]]
    for ref, layers, _ in shapes:
        root(("pad", ref))
        for layer in layers & poured:
            join(("pad", ref), ("pour", layer))
    resistors = []
    t = OZ_MM * oz
    for layer, w, a, b in segs:
        length = math.dist(a, b) * MM_PER_MIL
        if length > 0:
            resistors.append((("pt", layer, a), ("pt", layer, b), RHO_OHM_MM * length / (w * MM_PER_MIL * t)))
        for pt in (a, b):
            key = ("pt", layer, pt)
            root(key)
            for ref, layers, shape in shapes:
                if layer in layers and shape.contains(Point(pt)):
                    join(key, ("pad", ref))
            for k, v in enumerate(vias):
                if math.dist(pt, v) <= r_via:
                    join(key, ("via", k, layer))
            if layer in poured:
                join(key, ("pour", layer))
    for k, v in enumerate(vias):
        for layer in ("TOP", "BOTTOM"):
            for ref, layers, shape in shapes:
                if layer in layers and shape.contains(Point(v)):
                    join(("via", k, layer), ("pad", ref))
            if layer in poured:
                join(("via", k, layer), ("pour", layer))
        if via_ohm > 0:
            resistors.append((("via", k, "TOP"), ("via", k, "BOTTOM"), via_ohm))
        else:
            join(("via", k, "TOP"), ("via", k, "BOTTOM"))
    resistors = [(root(a), root(b), ohm) for a, b, ohm in resistors if root(a) != root(b)]
    reach, todo = {root(("pad", refs[0]))}, [root(("pad", refs[0]))]
    edges = defaultdict(list)
    for a, b, _ in resistors:
        edges[a].append(b)
        edges[b].append(a)
    while todo:
        for nxt in edges[todo.pop()]:
            if nxt not in reach:
                reach.add(nxt)
                todo.append(nxt)
    open_pins = [ref for ref in refs if root(("pad", ref)) not in reach]
    if open_pins:
        return None, f"{', '.join(open_pins)} not connected to {refs[0]} by tracks, vias or pours (edakit route check)"
    return ({ref: root(("pad", ref)) for ref in refs}, [x for x in resistors if x[0] in reach and x[1] in reach]), None


def annotate(design, sim, routing):
    """Copper of every net of sim.json `copper` on every board -> design.copper: {"pads": {pin ref: node},
    "elements": [(name, node, node, Ω)], "nets": {net: [pad nodes]}, "node_pins": {node: [pin refs]},
    "node_net": {node: net}, "notes": [(net, reason)]}. Done once per design."""
    if getattr(design, "copper", None) is not None:
        return design.copper
    spec = settings(design, sim)
    out = {"pads": {}, "elements": [], "nets": {}, "node_pins": defaultdict(list), "node_net": {}, "notes": []}
    design.copper = out
    if spec is None:
        return out
    boards = list(design.boards)
    for net in spec["nets"]:
        by_board = defaultdict(list)
        for ref in design.nets[net]["pins"]:
            b = design.comps[ref.split(".", 1)[0]].get("board") or (boards[0] if len(boards) == 1 else None)
            by_board[b].append(ref)
        for board, refs in by_board.items():
            r = (routing or {}).get(board)
            if r is None:
                out["notes"].append((net, f"no routing of board {board} (route/{board}.ses and route/{board}_board.json "
                                          "in the artifacts – edakit route)"))
                continue
            result, why = net_network(net, refs, r, spec["oz"], spec["via_ohm"])
            if result is None:
                out["notes"].append((net, why))
                continue
            pads, resistors = result
            if len(set(pads.values())) < 2:        # every pin on one node (a pour): nothing to add
                continue
            names, k = {}, 0
            for ref in sorted(refs, key=lambda x: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", x)]):
                names.setdefault(pads[ref], node_name(f"{net}__{ref}"))
            for a, b, _ in resistors:
                for key in (a, b):
                    if key not in names:
                        k += 1
                        names[key] = node_name(f"{net}__{board}_cu{k}")
            for ref, key in pads.items():
                out["pads"][ref] = names[key]
                out["node_pins"][names[key]].append(ref)
            out["nets"][net] = sorted(set(out["nets"].get(net, [])) | {names[key] for key in pads.values()})
            out["node_net"].update({name: net for name in names.values()})
            for i, (a, b, ohm) in enumerate(resistors, 1):
                out["elements"].append((f"{node_name(net)[2:]}_{board}_{i}", names[a], names[b], ohm))
    out["node_pins"] = dict(out["node_pins"])
    return out
