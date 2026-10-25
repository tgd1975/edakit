"""The hardware graph and the parts database, loaded together.

Graph file (JSON), either {"graph": {...}} or the inner object directly:

    components: [{designator, type, lcsc, pins: {number: name}, nc: [numbers], board, value, label, notes,
                  verify, waive: {check: reason}, bom: false, easyeda_device: {...}}]
    nets:       [{name, pins: ["R1.1", ...], v: [min, max], notes, waive}]
    cables:     [{name, from, to, pins: {from_pin: to_pin}, r_ohm_per_wire}]

Parts database: one JSON file per LCSC number (hardware/parts/C17414.json) with kind, pins (name, type, role,
vmax), params, ratings, spice, footprint, lead, verified. See handbook/04-parts-database.md.
"""

from __future__ import annotations

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
    def __init__(self, graph_path, parts_dir, boards=None, ground="GND"):
        self.graph_path = Path(graph_path)
        self.graph = load_graph(graph_path)
        self.ground = ground
        self.boards = list(boards or [])
        default = self.boards[0] if len(self.boards) == 1 else None
        self.comps = {c["designator"]: c for c in self.graph["components"]}
        for c in self.comps.values():
            c.setdefault("board", default)
        self.nets = {n["name"]: n for n in self.graph["nets"]}
        self.pin_net = {ref: n["name"] for n in self.graph["nets"] for ref in n["pins"]}
        self.parts = load_parts(parts_dir)

    @classmethod
    def from_config(cls, cfg):
        return cls(cfg.graph, cfg.parts, list(cfg.boards), cfg.ground)

    # --- lookups -------------------------------------------------------------------------------------------------
    def part(self, des):
        return self.parts.get(self.comps[des].get("lcsc") or "")

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
