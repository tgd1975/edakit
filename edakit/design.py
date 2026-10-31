"""The hardware graph and the parts database, loaded together.

Graph file (JSON), either {"graph": {...}} or the inner object directly:

    components: [{designator, type, lcsc, pins: {number: name}, nc: [pins], board, value, label, notes,
                  verify, accept: {code: reason}, bom: false, easyeda_device: {...}}]
    nets:       [{name, pins: ["R1.1", "U1.PD6", "LED5.anode", ...], v: [min, max], notes, accept}]
    cables:     [{name, from, to, pins: {from_pin: to_pin}, r_ohm_per_wire}]
    locks:      {pins: {"U1.4": net}, doc_pin_table}
    layout:     {loops: [{a, b, max_mm}], ...}
    ground:     name of the ground net (default "GND")

or a .toml file ([project] graph = "hardware/graph.toml") with the same keys, components, nets and cables as tables
keyed by designator and name – [components.R1], [nets."+5V"] –, read to the same dict (graph_of_toml).

Parts database: one JSON file per part (hardware/parts/C17414.json) with kind, pins (name, type, role, vmax),
params, ratings, spice, footprint, lead, compliance, order, verified. See handbook/04-parts-database.md. A component
finds its entry by its LCSC number (the file name) – or, without one, by its manufacturer part number `part` (the
entry's `mpn`): a part bought from another distributor.

Pins by name or role (circuit-language-plan.md, L.1 and L.2): a component without `pins` takes its entry's
{number: name}; without an entry either, the numbers its nets and nc use (STRUCT.entry reports the missing entry). A
pin word in the nets, nc, locks.pins, layout.loops and the pins of a cable is read once, when the Design is built, as
the pin number first, then the name of one pin, then the role of one pin (the entry's), then a name or role several
pins share, which stands for all of them – and written back as "DES.NUM", so that everything after the Design reads
numbers as before. A word that names no pin stays as it is written, for STRUCT.pin to report. word() is the rule the
other way: the word a finding names a pin by.

A resistor whose parts entry has value_ohm 0 is a bridge: copper that crosses a track on a board with all tracks on
one side. The nets it joins are one net for the graph checks (`joined()`) and for the simulation's LED drivers.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from pathlib import Path


def natural_key(text):
    """R2 before R10, D3_A before D10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(text))]


KEYED = {"components": "designator", "nets": "name", "cables": "name"}   # the tables of a TOML graph and their key


def load_graph(path):
    """The graph of a file (the inner object): a .toml file through graph_of_toml, else JSON, {"graph": {...}} or the
    inner object directly."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        return graph_of_toml(text, path)
    data = json.loads(text)
    return data.get("graph", data)


def graph_of_toml(text, where="graph"):
    """The graph of its TOML form, as the JSON gives it: [components.<designator>], [nets.<name>] and [cables.<name>]
    become the lists components, nets and cables in the order of the file, the table's key as designator or name
    first; every other key stays as it is – purpose, conventions, accept, layout, locks, ground, grounds –, the pin
    words as written. A key or table twice and what is no TOML – null among it – is a ConfigError with the file
    (`where`) and the line tomllib names."""
    from .config import ConfigError
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{where}: {e}") from None
    for key, field in KEYED.items():
        table = data.get(key)
        if table is None or table == []:                    # cables = []: none, as the JSON writes it
            continue
        if not isinstance(table, dict):
            raise ConfigError(f"{where}: {key}: a table keyed by {field}, [{key}.<{field}>]")
        rows = []
        for name, row in table.items():
            if not isinstance(row, dict):
                raise ConfigError(f"{where}: {key}.{name}: a table, [{key}.{name}]")
            if field in row:
                raise ConfigError(f"{where}: [{key}.{name}]: {field} is the table's key")
            rows.append({field: name, **row})
        data[key] = rows
    return data


def load_parts(directory):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(directory).glob("*.json"))
            if p.name != "README.json"}


def old_form(graph, parts):
    """What is still in the form of before the restructuring (convert.py), or None."""
    for key, p in parts.items():
        if "ratings" in p or "params" in p or any("vmax" in (pin or {}) for pin in (p.get("pins") or {}).values()):
            return f"parts entry {key}: ratings, params or a pin's vmax"
    for obj in [*graph.get("components", []), *graph.get("nets", [])]:
        if "waive" in obj:
            return f"{obj.get('designator') or obj.get('name')}: waive"
    if "hints" in graph or {"pin_locks", "doc_pin_table"} & set(graph.get("checks") or {}):
        return "the graph: hints or checks"
    return None


# --- configurations of a part (handbook 4.1: configs) ---------------------------------------------------------------
SECTIONS = ("limits", "values")      # a config's overrides of the entry's tables; None removes a key
REPLACED = ("address",)              # a config's own value of these entry keys replaces the entry's; None removes it


def conditional(entry):
    """Whether an entry has configs or pin needs with `when` – only then does a component see more than the entry."""
    return bool(entry.get("configs")) or any(isinstance(n, dict) and "when" in n for p in (entry.get("pins") or {}).values()
                                             for n in (p.get("needs") or []) if isinstance(p.get("needs"), list))


def config_of(entry, comp):
    """The config a component runs its part in: its own `config`, else the entry's `config_default`, else none."""
    return comp.get("config") or entry.get("config_default")


def holds(when, config, connected):
    """Whether a need's `when` holds: a config name or a list of them, or "connected" (the pin is on a net)."""
    names = when if isinstance(when, list) else [when]
    return any(w == config or (w == "connected" and connected) for w in names)


def configured(entry, config, connected_pins=()):
    """The entry as a component in `config` sees it: the config's pins, limits, values and needs over the entry's (a
    key set to None removes it), the pin needs whose `when` does not hold left out and `when` dropped from the rest."""
    out = {k: v for k, v in entry.items() if k not in ("pins", "configs", "config_default")}
    over = (entry.get("configs") or {}).get(config) or {}
    for section in SECTIONS + ("needs",):
        if section in over:
            merged = dict(entry.get(section) or {})
            for k, v in (over[section] or {}).items():
                if v is None:
                    merged.pop(k, None)
                else:
                    merged[k] = v
            out[section] = merged
    for key in REPLACED:
        if key in over:
            if over[key] is None:
                out.pop(key, None)
            else:
                out[key] = over[key]
    pins = {}
    for num, pin in (entry.get("pins") or {}).items():
        pin = dict(pin)
        for k, v in ((over.get("pins") or {}).get(num) or {}).items():
            if v is None:
                pin.pop(k, None)
            else:
                pin[k] = v
        if isinstance(pin.get("needs"), list):
            pin["needs"] = [{k: v for k, v in n.items() if k != "when"} for n in pin["needs"]
                            if not isinstance(n, dict) or "when" not in n or holds(n["when"], config, num in connected_pins)]
        pins[num] = pin
    out["pins"] = pins
    if config:
        out["config"] = config
    return out


# --- pins by number, name or role (circuit-language-plan.md, L.1) ---------------------------------------------------
PLAIN = re.compile(r"\d+|pin\d+")       # a name or role that says no more than the number: R4.1, J1.3 (role pin3)
WORD = re.compile(r'[^\s"\\]+')          # a name a pin can be written by: no blank – "GND (USB)" is written TP1
ONE = {"layout.loops": "a loop end is one pin", "cable": "a wire lands on one pin"}


class Design:
    def __init__(self, graph_path, parts_dir, boards=None, graph=None, parts=None):
        self.graph_path = Path(graph_path)
        self.graph = load_graph(graph_path) if graph is None else graph
        self.ground = self.graph.get("ground", "GND")
        self.boards = list(boards or [])
        default = self.boards[0] if len(self.boards) == 1 else None
        self.comps = {c["designator"]: c for c in self.graph["components"]}
        for c in self.comps.values():
            c.setdefault("board", default)
        self.parts = load_parts(parts_dir) if parts is None else parts
        if why := old_form(self.graph, self.parts):
            from .config import ConfigError
            raise ConfigError(f"{why} – the form of before the restructuring; edakit convert --write converts the "
                              "project once (handbook 10.5)")
        self._seen = {}                 # des -> (entry, what the component sees of it)
        self.by_mpn = {}
        for key, entry in self.parts.items():
            self.by_mpn.setdefault(str(entry.get("mpn") or key), key)
        self.entry_maps = set()         # designators whose pin map is their entry's (L.2)
        self.unresolved = []            # (where, ref, why): a pin word of locks.pins, layout.loops or a cable naming
                                        # no pin or several where one is meant – STRUCT.pin
        self._pin_maps()
        self._resolve()
        self.nets = {n["name"]: n for n in self.graph["nets"]}
        self.pin_net = {ref: n["name"] for n in self.graph["nets"] for ref in n["pins"]}

    # --- pins by number, name or role ------------------------------------------------------------------------------
    def _pin_maps(self):
        """A component without `pins` takes its entry's {number: name}; without an entry the numbers its nets and nc
        use, so that the structure is checked – STRUCT.entry reports the missing entry (L.2)."""
        used = {}
        for net in self.graph["nets"]:
            for ref in net.get("pins") or []:
                des, dot, pin = str(ref).partition(".")
                if dot:
                    used.setdefault(des, []).append(pin)
        for des, c in self.comps.items():
            if c.get("pins") is not None:
                continue
            key = self.entry_key(des)
            pins = self.parts[key].get("pins") if key else None
            if isinstance(pins, dict):
                c["pins"] = {num: (p or {}).get("name", num) for num, p in pins.items()}
                self.entry_maps.add(des)
            else:
                nums = dict.fromkeys(used.get(des, []) + [str(p) for p in c.get("nc") or []])
                c["pins"] = {num: num for num in sorted(nums, key=natural_key)}

    def _roles(self, des):
        """{number: role} of the component's parts entry in the config it runs its part in (handbook 4.1) – an
        SSD1306 panel's D0 is scl in I2C, sck in SPI. part() is not asked: its pin needs depend on the nets this
        resolves first; the roles do not."""
        key = self.entry_key(des)
        if not key:
            return {}
        entry = self.parts[key]
        if conditional(entry):
            entry = configured(entry, config_of(entry, self.comps[des]))
        return {num: (p or {}).get("role") for num, p in (entry.get("pins") or {}).items()}

    def resolve(self, des, word):
        """The pin numbers a word names on `des`: its number; the name of one pin; the role of one pin; else every pin
        that shares the name, else the role; [] for none."""
        pins = (self.comps.get(des) or {}).get("pins")
        if not isinstance(pins, dict):
            return []
        word = str(word)
        if word in pins:
            return [word]
        roles = self._roles(des)
        named = [n for n, name in pins.items() if name == word]
        roled = [n for n in pins if roles.get(n) == word]
        return next((hits for hits in (named, roled) if len(hits) == 1), named or roled)

    def words(self, des, num):
        """The words a pin may be written by, in the order a writer tries them: its name first on an IC or a module
        (their names are the datasheet's), its role first elsewhere (anode, cathode: a symbol's name may mislead). A
        name with a blank, a word that says no more than a number (1, pin3) or one that is another pin's number is
        none. Each may name this pin alone or a group of pins sharing it (resolve)."""
        num = str(num)
        pins = (self.comps.get(des) or {}).get("pins")
        if not isinstance(pins, dict) or num not in pins:
            return []
        key = self.entry_key(des)
        kind = self.parts[key].get("kind") if key else None
        name, role = pins.get(num), self._roles(des).get(num)
        return [w for w in ((name, role) if kind in ("ic", "module") else (role, name))
                if isinstance(w, str) and WORD.fullmatch(w) and not PLAIN.fullmatch(w) and w not in pins]

    def word(self, des, num):
        """The word for one pin: the first of its words that reads back as exactly this pin, else its number."""
        num = str(num)
        return next((w for w in self.words(des, num) if self.resolve(des, w) == [num]), num)

    def pin_text(self, ref):
        """A pin as a finding names it: "U1.PD6 (9)" – its word, with the number in brackets where they differ."""
        des, dot, num = str(ref).partition(".")
        if not dot:
            return str(ref)
        w = self.word(des, num)
        return f"{des}.{num}" if w == num else f"{des}.{w} ({num})"

    def _refs(self, ref):
        """The references "DES.NUM" a written pin stands for; the reference as written where it names no pin."""
        if not isinstance(ref, str):
            return [ref]
        des, dot, word = ref.partition(".")
        if not dot or des not in self.comps or word in (self.comps[des].get("pins") or {}):
            return [ref]
        return [f"{des}.{n}" for n in self.resolve(des, word)] or [ref]

    def _one(self, des, word, where):
        """The one pin a word names where one is meant (a loop end, a cable's wire) – recorded for STRUCT.pin where it
        names none or several."""
        if des not in self.comps or not isinstance(word, (str, int)):
            return word
        hits = self.resolve(des, word)
        if len(hits) == 1:
            return hits[0] if str(word) not in self.comps[des]["pins"] else word
        why = (f"{des}.{word} names no pin of {des}" if not hits else
               f"{des}.{word} names {len(hits)} pins ({', '.join(hits)}) – {ONE[where.split(' ')[0]]}")
        self.unresolved.append((where, f"{des}.{word}", why))
        return word

    def _resolve(self):
        """Every pin word of the graph as "DES.NUM": nets, nc, locks.pins, layout.loops, the pins of a cable."""
        g = self.graph
        for net in g["nets"]:
            if isinstance(net.get("pins"), list):
                net["pins"] = [r for ref in net["pins"] for r in self._refs(ref)]
        for des, c in self.comps.items():
            if isinstance(c.get("nc"), list) and isinstance(c["pins"], dict):
                c["nc"] = [p for w in c["nc"] for p in ([w] if str(w) in c["pins"] else self.resolve(des, w) or [w])]
        lk = g.get("locks")
        if isinstance(lk, dict) and isinstance(lk.get("pins"), dict):
            out = {}
            for ref, net in lk["pins"].items():
                refs = self._refs(ref)
                des, _, word = ref.partition(".")
                if refs == [ref] and des in self.comps and word not in self.comps[des]["pins"]:
                    self.unresolved.append(("locks.pins", ref, f"{ref} names no pin of {des} (locked to net {net})"))
                out.update(dict.fromkeys(refs, net))
            lk["pins"] = out
        for lp in (g.get("layout") or {}).get("loops") or []:
            for k in ("a", "b"):
                if isinstance(lp, dict) and isinstance(lp.get(k), str) and "." in lp[k]:
                    des, _, word = lp[k].partition(".")
                    pin = self._one(des, word, "layout.loops")
                    lp[k] = f"{des}.{pin}"
        for cab in g.get("cables") or []:
            if isinstance(cab, dict) and isinstance(cab.get("pins"), dict):
                where = f"cable {cab.get('name')}"
                cab["pins"] = {self._one(cab.get("from"), a, where): self._one(cab.get("to"), b, where)
                               for a, b in cab["pins"].items()}

    @classmethod
    def from_config(cls, cfg):
        return cls(cfg.graph, cfg.parts, list(cfg.boards))

    @classmethod
    def from_data(cls, graph, parts, boards=None, graph_path="graph.json"):
        """A design from a graph (the dict inside "graph") and parts entries {key: entry} already in memory."""
        return cls(graph_path, None, boards, graph=copy.deepcopy(graph), parts=parts)

    # --- lookups -------------------------------------------------------------------------------------------------
    def entry_key(self, des):
        """The parts entry of a component: its LCSC number, or without one the entry whose mpn is its `part`."""
        c = self.comps[des]
        if c.get("lcsc"):
            return c["lcsc"] if c["lcsc"] in self.parts else None
        return self.by_mpn.get(str(c.get("part") or ""))

    def part(self, des):
        """The parts entry of a component – with the config the component names applied (entry `configs`, component
        `config`) and the pin needs whose `when` does not hold for it left out (handbook 4.1)."""
        key = self.entry_key(des)
        if not key:
            return None
        entry = self.parts[key]
        seen = self._seen.get(des)
        if seen is None or seen[0] is not entry:          # an entry replaced in memory is looked at anew
            part = entry
            if conditional(entry):
                part = configured(entry, config_of(entry, self.comps[des]),
                                  {num for num in entry.get("pins") or {} if f"{des}.{num}" in self.pin_net})
            seen = self._seen[des] = (entry, part)
        return seen[1]

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
                and (p.get("values") or {}).get("value_ohm") == 0]

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
        name (pins, voltage range, waivers and accepts, bus, fn, fn_bus, pwm_hz and clock_hz of all of them), the
        bridges taken out. Without bridges: itself."""
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
                m["accept"] = {**(net.get("accept") or {}), **(m.get("accept") or {})} or None
                for key in ("bus", "fn", "fn_bus", "pwm_hz", "clock_hz"):
                    m[key] = m.get(key) or net.get(key)
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
