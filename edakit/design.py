"""The hardware graph and the parts database, loaded together.

Graph file (JSON), either {"graph": {...}} or the inner object directly:

    components: [{designator, type, lcsc, pins: {number: name}, nc: [numbers], board, value, label, notes,
                  verify, waive: {check: reason}, bom: false, easyeda_device: {...}}]
    nets:       [{name, pins: ["R1.1", ...], v: [min, max], notes, waive}]
    cables:     [{name, from, to, pins: {from_pin: to_pin}, r_ohm_per_wire}]
    ground:     name of the ground net (default "GND")

Parts database: one JSON file per part (hardware/parts/C17414.json) with kind, pins (name, type, role, vmax),
params, ratings, spice, footprint, lead, compliance, order, verified. See handbook/04-parts-database.md. A component
finds its entry by its LCSC number (the file name) – or, without one, by its manufacturer part number `part` (the
entry's `mpn`): a part bought from another distributor.

A resistor whose parts entry has value_ohm 0 is a bridge: copper that crosses a track on a board with all tracks on
one side. The nets it joins are one net for the graph checks (`joined()`) and for the simulation's LED drivers.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path


def natural_key(text):
    """R2 before R10, D3_A before D10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(text))]


def load_graph(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("graph", data)


def load_parts(directory):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(directory).glob("*.json"))
            if p.name != "README.json"}


class Design:
    def __init__(self, graph_path, parts_dir, boards=None):
        self.graph_path = Path(graph_path)
        self.graph = load_graph(graph_path)
        self.ground = self.graph.get("ground", "GND")
        self.boards = list(boards or [])
        default = self.boards[0] if len(self.boards) == 1 else None
        self.comps = {c["designator"]: c for c in self.graph["components"]}
        for c in self.comps.values():
            c.setdefault("board", default)
        self.nets = {n["name"]: n for n in self.graph["nets"]}
        self.pin_net = {ref: n["name"] for n in self.graph["nets"] for ref in n["pins"]}
        self.parts = load_parts(parts_dir)
        self.by_mpn = {}
        for key, entry in self.parts.items():
            self.by_mpn.setdefault(str(entry.get("mpn") or key), key)

    @classmethod
    def from_config(cls, cfg):
        return cls(cfg.graph, cfg.parts, list(cfg.boards))

    # --- lookups -------------------------------------------------------------------------------------------------
    def entry_key(self, des):
        """The parts entry of a component: its LCSC number, or without one the entry whose mpn is its `part`."""
        c = self.comps[des]
        if c.get("lcsc"):
            return c["lcsc"] if c["lcsc"] in self.parts else None
        return self.by_mpn.get(str(c.get("part") or ""))

    def part(self, des):
        key = self.entry_key(des)
        return self.parts[key] if key else None

    def pin_info(self, ref):
        des, _, pin = ref.partition(".")
        return ((self.part(des) or {}).get("pins") or {}).get(pin, {})

    def net_of(self, des, role):
        """Net of the first pin of `des` with this role in the parts database."""
        for num, p in ((self.part(des) or {}).get("pins") or {}).items():
            if p.get("role") == role:
                return self.pin_net.get(f"{des}.{num}")
        return None

    def pins_by_role(self, des):
        out = {}
        for num, p in ((self.part(des) or {}).get("pins") or {}).items():
            net = self.pin_net.get(f"{des}.{num}")
            if net and p.get("role") and p["role"] not in out:
                out[p["role"]] = net
        return out

    def comps_of_kind(self, *kinds):
        return [d for d in self.comps if (self.part(d) or {}).get("kind") in kinds]

    # --- 0 Ω bridges -----------------------------------------------------------------------------------------------
    def bridges(self):
        """Designators of the resistors whose parts entry has value_ohm 0."""
        return [d for d in self.comps if (p := self.part(d) or {}).get("kind") == "resistor"
                and (p.get("params") or {}).get("value_ohm") == 0]

    def bridge_groups(self):
        """[(name, nets, bridges)] for every set of nets that bridges join: the nets in graph order, the name is the
        ground net if it is one of them, else the first of them."""
        parent, used = {}, {}

        def root(n):
            while parent.setdefault(n, n) != n:
                n = parent[n]
            return n
        for des in self.bridges():
            nets = [n for p in self.part(des)["pins"] if (n := self.pin_net.get(f"{des}.{p}"))]
            for n in nets:
                parent[root(n)] = root(nets[0])
            if nets:
                used.setdefault(nets[0], []).append(des)
        order = {n: i for i, n in enumerate(self.nets)}
        groups = {}
        for n in sorted(parent, key=lambda n: (order.get(n, len(order)), n)):
            groups.setdefault(root(n), []).append(n)
        out = []
        for nets in groups.values():
            if len(nets) > 1:
                des = sorted((d for n in nets for d in used.get(n, [])), key=natural_key)
                out.append((self.ground if self.ground in nets else nets[0], nets, des))
        return out

    def joined_nets(self):
        """{net: name of its group} for every net a bridge joins to another."""
        return {n: name for name, nets, _ in self.bridge_groups() for n in nets}

    def joined(self):
        """The design as the graph checks see it: the nets of every bridge group merged into one net under the group's
        name (pins, voltage range, waivers and bus of all of them), the bridges taken out. Without bridges: itself."""
        bridges = set(self.bridges())
        if not bridges:
            return self
        name = self.joined_nets()
        nets = {}
        for net in self.graph["nets"]:
            to = name.get(net["name"], net["name"])
            pins = [r for r in net["pins"] if r.split(".", 1)[0] not in bridges]
            m = nets.setdefault(to, {**(self.nets.get(to) or net), "name": to, "pins": []})
            m["pins"] += pins
            if to != net["name"]:
                m["joined"] = m.get("joined", [to]) + [net["name"]]
                v, w = m.get("v"), net.get("v")
                if isinstance(v, list) and isinstance(w, list) and len(v) == len(w) == 2:
                    m["v"] = [min(v[0], w[0]), max(v[1], w[1])]
                m["waive"] = {**(net.get("waive") or {}), **(m.get("waive") or {})} or None
                m["bus"] = m.get("bus") or net.get("bus")
        out = copy.copy(self)
        out.graph = {**self.graph, "nets": list(nets.values()),
                     "components": [c for c in self.graph["components"] if c["designator"] not in bridges]}
        out.comps = {d: c for d, c in self.comps.items() if d not in bridges}
        out.nets = nets
        out.pin_net = {r: n["name"] for n in nets.values() for r in n["pins"]}
        return out

    def board_comps(self, board):
        return {d: c for d, c in self.comps.items() if c.get("board") == board}

    def board_nets(self, board):
        """Nets restricted to the pins of one board (same name on both sides of a cable)."""
        comps = self.board_comps(board)
        out = {}
        for n in self.graph["nets"]:
            pins = [p for p in n["pins"] if p.split(".", 1)[0] in comps]
            if pins:
                out[n["name"]] = pins
        return out

    @property
    def version(self):
        return self.graph.get("version", "?")
