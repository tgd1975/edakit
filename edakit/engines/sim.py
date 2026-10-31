"""SIM: the simulation as a producer (concept rules-at-scale.md, sections 1 and 2). What ngspice found in a scenario
becomes quantities – a part's voltages, currents, power and temperature, a supply at a pin – that LIMITS judges
against the limits of the parts entries (derated: catalog/tables/derating.toml, sim.json derating), and states the
scenario expects – LEDs on or dark, a regulator at its voltage, a diode blocking, an input at a defined level – that
are judged here (SIM.state, LVL.threshold, LVL.direction, SIM.driver).

A Scene is one scenario or transient run: stress() and function() fill it from the ngspice result and the netlist's
meta, finish() gives its rows – every comparison with its actual and expected value and pass, fail or info, the
protocol's simulation table and what documents and requirements quote – and its findings. `design` is the design the
netlist was built from (its nodes and copper), `new` the same design as the engines read it.
"""

from __future__ import annotations

import math
from collections import defaultdict

from .. import catalog
from ..catalog import table
from ..circuit import is_number, limits, polarized, relay_sets, switch_sets, values
from ..findings import Finding
from ..sim import netlist, strip
from .limits import CODE, compare
from .quantities import SIM_EPS_V, Limit, Quantity, part_limits

DERATING = table("derating")["E"]
# (netlist element kind, quantity) -> the derating of sim.json / derating.toml [E.derate] that applies to its limit
FETS = {"nmos": "v_bjt", "pmos": "v_bjt", "njfet": "v_bjt", "pjfet": "v_bjt"}
DERATE = {"v": {"capacitor": "v_cap"}, "vr": {"diode": "v_diode"}, "vce": {"npn": "v_bjt", "pnp": "v_bjt"},
          "vds": FETS, "vgs": FETS, "vdg": FETS}
DIM = {"p": "p", "i": "i", "if": "i", "ic": "i", "id": "i", "ig": "i", "gpio_i": "i", "gpio_i_total": "i",
       "i_contact": "i", "i_switch": "i"}
# what a generated fault scenario (FT-8) judges: the parts' limits – a board without its supply does not reach the
# states its load expects, and its nets leave their declared ranges by design of the fault
FAULT_CODES = ("LIM.v", "LIM.i", "LIM.p", "LIM.t", "LIM.backfeed")
SUPPLY_ROLES = ("vdd", "vcc")


def v(res, n):
    return 0.0 if n in (None, "0") else res.get(n, float("nan"))


def fmt(x, unit=""):
    return x if isinstance(x, str) else f"{x:.4g}{' ' + unit if unit else ''}"


class Scene:
    """One scenario's producer: its quantities, its state checks, its rows and findings."""

    def __init__(self, design, new, sim, res, meta, name, info=False):
        self.d, self.n, self.sim, self.res, self.meta, self.name, self.info = design, new, sim, res, meta, name, info
        self.der = {**DERATING["derate"], **sim.get("derating", {})}
        self.crit = {**DERATING["criteria"], **sim.get("criteria", {})}
        self.amb = sim.get("ambient_c", 25)
        self.qs, self.rows, self.found = [], [], []

    def q(self, place, name, value, unit, kind="", des=None, how="", lo=None, code="", lims=(), color="",
          entry=True, report=False, grade=""):
        """A quantity; its limits from the entry of `des` (by name, derated by kind) unless `entry` is False; with
        `report` a row of information where it has no limit."""
        key = self.n.entry_key(des) if des and entry and des in self.n.comps else None
        dim = DIM.get(name) or DERATE.get(name, {}).get(kind)
        q = Quantity(place, name, value, unit=unit, stage="E", lo=lo, how=how or name, kind=kind, entry=key,
                     scenario=self.name, code=code, grade=grade, on=(("component", des),) if des in self.n.comps else (),
                     limits=list(lims), color=color, derate=self.der.get(dim, 1.0) if dim else 1.0)
        q.report = report
        self.qs.append(q)

    def check(self, code, place, what, actual, expected, ok, unit="", source="", grade="", on=()):
        """A state the scenario expects: a row, and where it is not reached a finding."""
        self.rows.append({"id": code, "scenario": self.name, "item": place, "check": what,
                          "actual": fmt(actual, unit), "expected": expected, "result": "pass" if ok else "fail"})
        if not ok:
            self.found.append(Finding(code, "E", place, f"{what}: {fmt(actual, unit)}, expected {expected}", source,
                                      scenario=self.name, grade=grade, on=on))

    def plugin_add(self, cid, item, what, actual, expected, ok, severity=None, unit=""):
        """The `add` a project's simulation plugin calls: its rows are SIM.state unless it names a code."""
        code = cid if catalog.code(cid) else "SIM.state"
        if severity == "info":
            self.rows.append({"id": code, "scenario": self.name, "item": item, "check": what,
                              "actual": fmt(actual, unit.strip()), "expected": expected, "result": "info"})
            return
        self.check(code, item, what, actual, expected, ok, unit.strip(), "the project's simulation plugin")

    def finish(self):
        """(rows, findings): every quantity against its limits – a row per comparison, a finding per violation –, a
        row of information for a reported quantity without a limit, and the state checks; in an informational
        scenario a failure is information."""
        rows, found = [], []
        for q in self.qs:
            lims = part_limits(self.n, q) + q.limits
            code = q.code or CODE.get(q.unit, "LIM.v")
            if not lims and getattr(q, "report", False):
                value = q.hi if q.hi is not None else q.lo
                rows.append({"id": code, "scenario": self.name, "item": q.place, "check": q.how,
                             "actual": fmt(value, q.unit), "expected": "information", "result": "info"})
            for lim in lims:
                sides = compare(q, lim)
                if len(sides) == 2:      # a range: one row and at most one finding, as the protocol always had it
                    lo, hi = q.lo, q.hi
                    actual = getattr(q, "actual", None) or (fmt(hi, q.unit) if lo == hi else
                                                            f"{lo:.4g} … {hi:.4g} {q.unit}")
                    expected = f"{lim.min:g} … {lim.max:g} {q.unit}"
                    ok = all(ok for ok, *_ in sides)
                    rows.append({"id": code, "scenario": self.name, "item": q.place, "check": q.how, "actual": actual,
                                 "expected": expected, "result": "pass" if ok else "fail"})
                    if not ok:
                        found.append(Finding(code, "E", q.place, f"{q.how}: {actual}, expected {expected}", lim.source,
                                             scenario=self.name, on=q.on, grade=q.grade,
                                             data={"value": [lo, hi], "unit": q.unit}))
                    continue
                for ok, what, allowed, value, bound in sides:
                    if len(sides) == 1:
                        rows.append({"id": code, "scenario": self.name, "item": q.place, "check": q.how,
                                     "actual": fmt(value, q.unit), "expected": allowed,
                                     "result": "pass" if ok else "fail"})
                    if not ok:
                        found.append(Finding(code, "E", q.place, f"{what}, allowed {allowed}", lim.source,
                                             scenario=self.name, on=q.on, grade=q.grade,
                                             data={"value": value, "limit": bound, "unit": q.unit}))
        rows += self.rows
        found += self.found
        if self.info:
            for r in rows:
                if r["result"] == "fail":
                    r["result"] = "info"
            for f in found:
                f.data["info"] = True
        elif getattr(self, "fault", False):      # a generated fault scenario (FT-8): the parts' limits, warnings at most
            for r in rows:
                if r["result"] == "fail":
                    r["result"] = "warn" if r["id"] in FAULT_CODES else "info"
            found = [f for f in found if f.code in FAULT_CODES]
            for f in found:
                f.data["fault"] = True
        return rows, found


# --- helpers: pins, grounds, thresholds ------------------------------------------------------------------------------
def supply_pins(part):
    """The supply pins of a part: its power_in pins with the role vdd or vcc, else all of its power_in pins."""
    pins = {n: i for n, i in (part.get("pins") or {}).items() if i.get("type") == "power_in"}
    return {n: i for n, i in pins.items() if i.get("role") in SUPPLY_ROLES} or pins


def ground_pin(design, des, part):
    """The part's first connected ground pin ('U2.1'), or None (the ground net)."""
    return next((f"{des}.{n}" for n, i in (part.get("pins") or {}).items()
                 if i.get("type") == "ground" and f"{des}.{n}" in design.pin_net), None)


def at_pin(design, res, ref, ground=None):
    """Voltage at a pin – on its pad node where the copper of its net is simulated – against a ground pin (None: the
    ground net); nan for a node no element of the netlist reaches."""
    return v(res, netlist.pin_node(design, ref)) - (v(res, netlist.pin_node(design, ground)) if ground else 0.0)


def threshold(vals, pin, kind, vdd):
    """VIL or VIH (`kind` 'vil'|'vih') of an input pin: the pin's own kind_v|kind_ratio, else the part's values; a
    ratio is taken of the supply `vdd` (None: no single supply)."""
    for src in (pin, vals):
        if f"{kind}_v" in src:
            return src[f"{kind}_v"]
        if f"{kind}_ratio" in src:
            return None if vdd is None else src[f"{kind}_ratio"] * vdd
    return None


def dissipation(el, res):
    """Power an element of the netlist turns into heat in its part (W); None where the part is not what dissipates it –
    a capacitor, the resistance of a source or a cell, an external load."""
    kind, nodes = el["kind"], el["nodes"]
    if kind in ("capacitor", "source", "battery", "load"):
        return None
    if kind in ("led", "diode"):
        a, k = (v(res, n) for n in nodes)
        return abs((a - k) * res.get(f"@{el['name']}[id]", 0.0))
    if kind in ("npn", "pnp"):
        c, b, e = (v(res, n) for n in nodes)
        return abs((c - e) * res.get(f"@{el['name']}[ic]", 0.0)) + abs((b - e) * res.get(f"@{el['name']}[ib]", 0.0))
    if kind in ("pmos", "nmos"):   # @m[id] includes the body diode's current
        d_, _, s = (v(res, n) for n in nodes)
        return abs((d_ - s) * res.get(f"@{el['name']}[id]", 0.0))
    if kind in ("njfet", "pjfet"):
        d_, g, s = (v(res, n) for n in nodes)
        return abs((d_ - s) * res.get(f"@{el['name']}[id]", 0.0)) + abs((g - s) * res.get(f"@{el['name']}[ig]", 0.0))
    if "value" in el:
        a, b = (v(res, n) for n in nodes[:2])
        return (a - b) ** 2 / el["value"]
    return None


def lockout(res, reg):
    """The `on` of a regulator model: 1 at and above its vin_min, falling to 0 over the UVLO_V below it."""
    if reg.get("vin_min") is None:
        return 1.0
    vin = v(res, reg["vin"]) - v(res, reg["gnd"])
    return min(1.0, max(vin - reg["vin_min"] + netlist.UVLO_V, 0) / netlist.UVLO_V)


def ldo_power(res, reg):
    """Heat of an LDO model: (vin − vout) × all the current it carries – the load at its output, and what it feeds
    inside a module besides (extra_i: the MCU's core), off below its lockout."""
    vin, vout = (v(res, reg[k]) - v(res, reg["gnd"]) for k in ("vin", "vout"))
    return (vin - vout) * (max(res.get(reg["ammeter"], 0.0), 0.0) + lockout(res, reg) * reg["extra_i"])


def behind_resistor(design, joined, outputs):
    """{net: driver output} for every net that one resistor (not a 0 Ω bridge) joins to exactly one of `outputs` – the
    cathode net of an LED behind its balancing resistor. Nets as the bridges join them; the ground is never behind an
    output, a net that reaches two outputs belongs to neither."""
    reach = defaultdict(set)
    bridges = set(design.bridges())
    for des in design.comps:
        part = design.part(des) or {}
        if part.get("kind") != "resistor" or des in bridges:
            continue
        nets = {joined.get(n, n) for p in part.get("pins") or {} if (n := design.pin_net.get(f"{des}.{p}"))}
        if len(nets) == 2:
            a, b = nets
            for net, out in ((a, b), (b, a)):
                if out in outputs and net != design.ground:
                    reach[net].add(out)
    return {net: next(iter(outs)) for net, outs in reach.items() if len(outs) == 1}


def led_on_output(outputs, behind, anode, cathode):
    """How one LED (one colour) traces to a driver output: (output, "cathode") when its cathode is on it – directly or
    behind its balancing resistor –, (output, "anode") when its anode is on it directly (the LED is reversed), else
    None. edakit firmware traces channels so."""
    if cathode in outputs:
        return cathode, "cathode"
    if anode in outputs:
        return anode, "anode"
    if cathode in behind:
        return behind[cathode], "cathode"
    return None


# --- stress: every part against its limits ---------------------------------------------------------------------------
def parallel_contacts(s, des, node):
    """How many of a connector's pins are on the net a supply feeds at `node` – USB-C's four VBUS pins share it."""
    nets = {s.d.pin_net.get(f"{des}.{num}") for num in (s.n.part(des) or {}).get("pins") or {}
            if netlist.pin_node(s.d, f"{des}.{num}") == node}
    nets.discard(None)
    if not nets:
        return 1
    return max(1, sum(1 for num in (s.n.part(des) or {}).get("pins") or {} if s.d.pin_net.get(f"{des}.{num}") in nets))


def matrix_key_blocked(s, des):
    """A key of a key matrix (a net of it with matrix row or col) whose diode does not conduct in this scenario: its
    row is not scanned, the diode blocks it on purpose – no reading through the contact, so no minimum load to hold.
    The key's diode: the one on its net that is not a row or column, as REQ.missing/matrix finds it."""
    d = s.d
    nets = {d.pin_net.get(f"{des}.{p}") for p in (s.n.part(des) or {}).get("pins") or {}} - {None}
    side = {n for n in nets if (d.nets.get(n) or {}).get("matrix") in ("row", "col")}
    if not side:
        return False
    for dio in d.comps_of_kind("diode"):
        a, k = d.net_of(dio, "anode"), d.net_of(dio, "cathode")
        if {a, k} & (nets - side) and {a, k} & set(d.nets) - nets:
            anode, cathode = (next(f"{dio}.{n}" for n, p in d.part(dio)["pins"].items() if p.get("role") == r)
                              for r in ("anode", "cathode"))
            return at_pin(d, s.res, anode) - at_pin(d, s.res, cathode) < MATRIX_DIODE_ON_V
    return False


MATRIX_DIODE_ON_V = 0.05  # a key diode with less forward voltage blocks: a silicon one carries < 1 nA, a Schottky ~1 µA


def min_load(s, des, part, i):
    """REQ.value/min_load: a closed contact carries at least the minimum load of its entry (values min_load_a) – below
    it a contact may not close reliably: no current breaks the film on it. A contact in a signal path carries no DC by
    design (grade switch): there its entry's rating is judged instead (switch_dc)."""
    least = values(part).get("min_load_a")
    if least is None or des in signal_path_contacts(s) or matrix_key_blocked(s, des):
        return
    s.check("REQ.value", des, f"current through a closed contact of {des}", i * 1e6, f"≥ {least * 1e6:g} µA",
            i >= least, "µA", f"min_load_a of {s.n.entry_key(des)}", grade="min_load", on=(("component", des),))


def stress(s):
    """Every part's voltages, currents, power and temperature against its entry's limits."""
    res, meta = s.res, s.meta
    for des, els in sorted(meta["elements"].items()):
        part = s.n.part(des) or {}
        r = limits(part)
        for el in els:
            nodes, kind = el["nodes"], el["kind"]
            i = a = b = None
            if "value" in el and kind != "capacitor":
                a, b = (v(res, x) for x in nodes[:2])
                i = (a - b) / el["value"]
            if kind in ("resistor", "pot", "heater", "speaker"):
                s.q(des, "p", i * i * el["value"], "W", kind, des, "power dissipation")
                if kind in ("heater", "speaker"):
                    s.q(des, "v", abs(a - b), "V", kind, des, "voltage across it")
            elif kind in ("motor", "solenoid"):
                s.q(des, "i", abs(i), "A", kind, des, "winding current (at standstill)")
                s.q(des, "v", abs(a - b), "V", kind, des, "voltage across it")
            elif kind == "opto_led":     # through its ammeter: the diode's own current is not printed
                cur = res.get(f"v_{des.lower()}_la#branch", float("nan"))
                s.q(des, "if", cur, "A", "led", des, "LED forward current")
            elif kind == "fuse" and "i_hold_a" in r:
                hold = r["i_hold_a"]
                for (t0, h0), (t1, h1) in zip(values(part).get("i_hold_vs_temp") or [],
                                              (values(part).get("i_hold_vs_temp") or [])[1:]):
                    if t0 <= s.amb <= t1:
                        hold = h0 + (h1 - h0) * (s.amb - t0) / (t1 - t0)
                s.q(des, "i", abs(i), "A", kind, des, "current (derated hold current)", entry=False,
                    lims=[Limit(max=hold, derate=s.der["i"], source=f"i_hold_a of {s.n.entry_key(des)} at {s.amb} °C")])
            elif kind in ("switch", "connector", "source") and i is not None:
                s.q(des, "i", abs(i), "A", kind, des, "contact current")
                n = parallel_contacts(s, des, nodes[1]) if kind == "source" else 1
                s.q(des, "i_contact", abs(i) / n, "A", kind, des,
                    "current per contact" + (f" ({n} contacts on the supply's net)" if n > 1 else ""))
                if kind == "switch":     # a closed contact of a switch, button, DIP switch or relay
                    s.q(des, "i_switch", abs(i), "A", kind, des, "current it breaks when it opens", grade="switching")
                    min_load(s, des, part, abs(i))
            elif kind == "load":
                s.q(des, "i", el["i"], "A", kind, des, "contact current (external load)")
            elif kind == "inductor":
                s.q(des, "i", abs(i), "A", kind, des, "average current")
            elif kind == "buzzer":
                s.q(des, "v", abs(a - b), "V", kind, des, "coil voltage")
            elif kind == "relay_coil":
                s.q(des, "v_coil", abs(a - b), "V", kind, des, "coil voltage")
            elif kind == "capacitor":
                a, b = (v(res, x) for x in nodes)
                s.q(des, "v", abs(a - b), "V", kind, des, "DC voltage")
                if polarized(part):
                    roles = [p.get("role") for p in part["pins"].values()]
                    plus, minus = (a, b) if roles[:1] != ["minus"] and roles[1:2] != ["plus"] else (b, a)
                    s.q(des, "vr", max(minus - plus, 0), "V", kind, des, "reverse voltage", grade="polarized")
            elif kind in ("led", "diode"):
                a, k = (v(res, x) for x in nodes)
                cur = res.get(f"@{el['name']}[id]", float("nan"))
                info = meta["leds"].get(el["name"], {})
                label, color = el["name"][2:].upper(), info.get("color") or ""
                rr = r.get(color, r) if color else r
                if kind == "led" and "if_max_a" in rr:
                    s.q(label, "if", cur, "A", kind, des, "forward current", color=color)
                    s.q(label, "vr", max(k - a, 0), "V", kind, des, "reverse voltage", color=color)
                elif kind == "diode" and "if_max_a" in r:
                    s.q(des, "if", cur, "A", kind, des, "forward current")
                    s.q(des, "vr", max(k - a, 0), "V", kind, des, "reverse voltage")
            elif kind in ("npn", "pnp") and "ic_max_a" in r:
                c, bb, e = (v(res, x) for x in nodes)
                ic, ib = res.get(f"@{el['name']}[ic]", 0.0), res.get(f"@{el['name']}[ib]", 0.0)
                vce, vbe = c - e, bb - e
                s.q(des, "ic", abs(ic), "A", kind, des, "collector current")
                s.q(des, "vce", abs(vce), "V", kind, des, "|VCE|")
                s.q(des, "p", abs(vce * ic) + abs(vbe * ib), "W", kind, des, "power dissipation")
                s.q(des, "veb", max(-vbe if kind == "npn" else vbe, 0), "V", kind, des, "base-emitter reverse voltage")
            elif kind in ("pmos", "nmos") and "id_max_a" in r:
                d_, g, src = (v(res, x) for x in nodes)
                cur = abs(res.get(f"@{el['name']}[id]", 0.0))
                s.q(des, "id", cur, "A", kind, des, "drain current")
                s.q(des, "vds", abs(d_ - src), "V", kind, des, "|VDS|")
                s.q(des, "vgs", abs(g - src), "V", kind, des, "|VGS|")
                s.q(des, "p", abs((d_ - src) * cur), "W", kind, des, "power dissipation")
            elif kind in ("njfet", "pjfet"):
                jfet(s, des, kind, el)
            if kind in ("pmos", "nmos"):
                gate_drive(s, des, part, nodes)
        heat =[w for el in els if (w := dissipation(el, res)) is not None]
        if "rth_ja_k_per_w" in r and heat:
            junction(s, des, sum(heat), r)
    cable_ratings(s)
    for des, m in meta["mcu"].items():
        r = limits(s.n.part(des))
        cur = {net: res.get(am, 0.0) for net, am in m.get("gpio_ammeters", {}).items()}
        for net, i in cur.items():
            s.q(f"{des} {net}", "gpio_i", abs(i), "A", "mcu", des, "GPIO output current")
        if "gpio_i_total_max_a" in r and cur:
            for what, i in (("sourced", sum(x for x in cur.values() if x > 0)),
                            ("sunk", -sum(x for x in cur.values() if x < 0))):
                s.q(des, "gpio_i_total", i, "A", "mcu", des, f"GPIO current {what} by all outputs together")


# --- cables: a wire's current against the cable's own rating (maker-coverage FT-2, rules-at-scale.md decision 22) -----
def wire_current(d, res, w):
    """The current through a wire of a cable (netlist.cable_wires): ngspice's own (@r_w1_8[i]), else from the voltages
    at its two ends."""
    i = res.get(f"@{w['name'].lower()}[i]")
    if i is None:
        far = w["node"] if "node" in w else netlist.pin_node(d, w["pb"])
        i = (v(res, netlist.pin_node(d, w["pa"])) - v(res, far)) / w["r"]
    return abs(i)


def cable_ratings(s):
    """LIM.i/cable: the current of every wire of a cable between boards within the cable's i_max_a – the rating per
    wire of the cable's own datasheet, derated as every current; edakit derives none from the gauge. The wires of a
    cable to an LED strip are the strip's (strip.judge, grade strip)."""
    for w in getattr(s.d, "cable_elements", None) or []:
        if w.get("strip") or not is_number(w.get("i_max_a")):
            continue
        s.q(f"cable {w['cable']}", "i", wire_current(s.d, s.res, w), "A", "", None,
            f"current through wire {w['name'][2:]}", code="LIM.i", entry=False, grade="cable",
            lims=[Limit(max=w["i_max_a"], derate=s.der.get("i", 1.0), source=f"i_max_a of cable {w['cable']}")])


def cable_currents(d, res, meta):
    """{cable: (current, wire)}: the highest current through a wire of each cable in one operating point – the wire
    named by its pin at the cable's from end."""
    out = {}
    for w in netlist.cable_wires(d, meta):
        i, wire = wire_current(d, res, w), w.get("wire") or w["name"].rsplit("_", 1)[-1]
        if w["cable"] not in out or i > out[w["cable"]][0]:
            out[w["cable"]] = (i, wire)
    return out


def jfet(s, des, kind, el):
    """A junction FET against its entry: |VDS|, |VDG|, the gate's reverse voltage against the source, its forward
    current (a gate driven positive conducts like a diode), the drain current and the power."""
    d_, g, src = (v(s.res, x) for x in el["nodes"])
    cur, ig = abs(s.res.get(f"@{el['name']}[id]", 0.0)), s.res.get(f"@{el['name']}[ig]", 0.0)
    sign = 1 if kind == "njfet" else -1          # the gate of an n-channel JFET is reverse-biased below its source
    s.q(des, "id", cur, "A", kind, des, "drain current")
    s.q(des, "vds", abs(d_ - src), "V", kind, des, "|VDS|")
    s.q(des, "vdg", abs(d_ - g), "V", kind, des, "|VDG|")
    s.q(des, "vgs", max(sign * (src - g), 0), "V", kind, des, "gate reverse voltage |VGS|")
    s.q(des, "ig", max(ig, 0), "A", kind, des, "forward gate current")   # ngspice: + forward, for either channel
    s.q(des, "p", abs((d_ - src) * cur) + abs((g - src) * ig), "W", kind, des, "power dissipation")


def tj_limit(r, crit):
    """Junction limit of a part: its own tj_max_c, the criteria's where that is lower or the part has none."""
    return min(r.get("tj_max_c", math.inf), crit["tj_max_c"])


def junction(s, des, p, r, what=None):
    """ambient + P × Rth(j-a) against the junction limit, and on a board people touch against the touch limit."""
    rth = r["rth_ja_k_per_w"]
    tj = s.amb + p * rth
    s.q(des, "tj", tj, "°C", "", des, what or f"junction temperature at {s.amb} °C: {p:.3g} W × {rth:g} K/W",
        entry=False, lims=[Limit(max=tj_limit(r, s.crit), source=f"tj_max_c of {s.n.entry_key(des)} (at most the "
                                                                  f"criteria's {s.crit['tj_max_c']:g} °C)")])
    board = (s.n.comps.get(des) or {}).get("board")
    lim = (s.sim.get("touch_c") or {}).get(board)
    if lim is not None:
        s.q(des, "tj", tj, "°C", "", des, f"temperature where people touch (board {board})", entry=False,
            lims=[Limit(max=lim, source=f"touch_c of sim.json for board {board}")])


# --- function: what the circuit does in the scenario -----------------------------------------------------------------
def function(s, load, low=None, plugin=None):
    """Supply currents, back-feed, regulators, MCU supply and levels, relays, operating ranges, thresholds, driver
    headroom, LEDs, blocking diodes, the declared net ranges, the project plugin's checks."""
    res, meta, crit, d = s.res, s.meta, s.crit, s.d
    for des, src in meta["sources"].items():
        i = -res.get(src["branch"], 0.0)
        s.q(des, "i", i, "A", "", des, "current from the supply", entry=False, report=True,
            lims=[Limit(max=src["i_max_a"], source=f"i_max_a of sources.{des} in sim.json")] if src.get("i_max_a")
            else [])
        if src.get("i_min_a"):
            what, i_on = "current keeps the supply on", i
            if low:
                cores, res_low = low
                what += " (least current: " + ", ".join(f"{x} {c * 1e3:.3g} mA" for x, c in cores.items()) + ")"
                i_on = -res_low.get(src["branch"], 0.0)
            s.q(des, "i", None, "A", "", des, what, lo=i_on, entry=False,
                lims=[Limit(min=src["i_min_a"], source=f"i_min_a of sources.{des} in sim.json")])
    for key, lim in sorted((load.get("expect") or {}).items()):     # what the project expects in this load
        if key in meta["sources"]:
            s.q(key, "i", -res.get(meta["sources"][key]["branch"], 0.0), "A", "", key, "current from the supply "
                "(expected in this load)", code="LIM.i", entry=False,
                lims=[Limit(max=lim.get("i_max_a"), min=lim.get("i_min_a"), source="expect of the load in sim.json")])
        elif key in d.nets:
            g = v(res, netlist.node(netlist.local_ground(d, key), d.ground))
            x = max(v(res, n) for n in netlist.net_nodes(d, key)) - g
            s.q(key, "v_expect", x, "V", "", None, "net voltage (expected in this load)", lo=x, code="LIM.v",
                entry=False, lims=[Limit(max=lim.get("max_v"), min=lim.get("min_v"),
                                         source="expect of the load in sim.json")])
        else:
            s.check("SIM.config", key, "expect of the load", f"{key} is neither a source nor a net",
                    "a source of sources (i_max_a, i_min_a) or a net (min_v, max_v)", False)
    for des, src in meta["sources"].items():
        lim = src.get("i_back_max_a")
        lim = crit["blocking_max_a"] if lim is None else lim
        s.q(des, "i", max(res.get(src["branch"], 0.0), 0.0), "A", "", des, "current into the supply (fed backwards)",
            code="LIM.backfeed", entry=False,
            lims=[Limit(max=lim, source=f"i_back_max_a of sources.{des} (default the criteria's blocking_max_a)")])
    for name, cell in meta.get("cells", {}).items():
        lim = s.sim["cells"][cell["state"]].get("i_charge_max_a", crit["blocking_max_a"])
        s.q(name, "i", max(res.get(cell["branch"], 0.0), 0.0), "A", "", None, "current into the cell (charging)",
            code="LIM.backfeed", entry=False,
            lims=[Limit(max=lim, source=f"i_charge_max_a of cells.{cell['state']} in sim.json")])
        if (most := s.sim["cells"][cell["state"]].get("i_max_a")) is not None:
            s.q(name, "i", max(-res.get(cell["branch"], 0.0), 0.0), "A", "", None, "current from the cell", code="LIM.i",
                entry=False, grade="cell",
                lims=[Limit(max=most, source=f"i_max_a of cells.{cell['state']} in sim.json")])
    for des, reg in meta["regs"].items():
        r = limits(s.n.part(des))
        vin = v(res, reg["vin"]) - v(res, reg["gnd"])
        vout = v(res, reg["vout"]) - v(res, reg["gnd"])
        if reg.get("enable") and v(res, reg["enable"]) < 0.5:      # maker-coverage FT-5: switched off by its enable
            boost_off(s, des, reg, vin, vout)
            continue
        s.check("SIM.state", des, f"output voltage ({reg['kind']})", vout, f"{reg['vset']} V ± {crit['rail_tol']:.0%}",
                abs(vout - reg["vset"]) <= reg["vset"] * crit["rail_tol"], "V")
        if des in meta["mcu"]:
            continue          # a module's own regulator: its supply and load below
        if "vin_min_v" in r:
            s.q(des, "vin", None, "V", "", des, "input voltage", lo=vin, code="LIM.range", entry=False,
                lims=[Limit(min=r["vin_min_v"], source=f"vin_min_v of {s.n.entry_key(des)}")])
        s.q(des, "i_out", max(res.get(reg["ammeter"], 0.0), 0.0), "A", "", des, "output current")
        if (least := reg["values"].get("i_load_min_a")) is not None:      # maker-coverage FT-5: LM317, AMS1117
            s.q(des, "i_out_min", None, "A", "", des, "output current at least the minimum load", code="LIM.range",
                entry=False, grade="min_load", lo=max(res.get(reg["ammeter"], 0.0), 0.0),
                lims=[Limit(min=least, source=f"i_load_min_a of {s.n.entry_key(des)}")])
        if reg["kind"] == "ldo" and "rth_ja_k_per_w" in r:
            junction(s, des, ldo_power(res, reg), r, f"junction temperature at {s.amb} °C")
    for des, m in meta["mcu"].items():
        r, p = limits(s.n.part(des)), values(s.n.part(des))
        vmin = r.get("vin_min_v", r.get("vsys_min_v"))
        reg = meta["regs"].get(des)
        if vmin is not None:
            s.q(des, "vsys", None, "V", "", des, "supply voltage", lo=v(res, m["vin"]), code="LIM.range", entry=False,
                lims=[Limit(min=vmin, source=f"vin_min_v or vsys_min_v of {s.n.entry_key(des)}")])
        if reg and "i_out_max_a" in r:
            s.q(des, "i_out", max(res.get(reg["ammeter"], 0.0), 0.0), "A", "", des, "load on the on-board regulator",
                entry=False, lims=[Limit(max=r["i_out_max_a"], source=f"i_out_max_a of {s.n.entry_key(des)}")])
        if reg and reg["kind"] == "ldo" and "rth_ja_k_per_w" in r:
            heat, rth = ldo_power(res, reg), r["rth_ja_k_per_w"]
            junction(s, des, heat, r, f"junction temperature of the on-board regulator at {s.amb} °C: {heat:.3g} W × "
                                      f"{rth:g} K/W")
        v_io = v(res, m["io_rail"]) if m.get("io_rail") else p.get("v_io_v", 3.3)
        vih = p.get("vih_v", p["vih_ratio"] * v_io if "vih_ratio" in p else None)
        vil = p.get("vil_v", p["vil_ratio"] * v_io if "vil_ratio" in p else None)
        for net in m.get("inputs", []) if vih is not None and vil is not None else []:
            x = v(res, m.get("input_nodes", {}).get(net) or netlist.node(net, d.ground))
            level = "high" if x >= vih else "low" if x <= vil else "undefined"
            s.check("LVL.threshold", f"{des} {net}", f"input level {level} (VIL {vil:.2f} V, VIH {vih:.2f} V)", x,
                    f"≤ {vil:.2f} V or ≥ {vih:.2f} V", level != "undefined", "V", f"vil/vih of {s.n.entry_key(des)}")
        for net, pin in m.get("cannot_drive", []):
            s.check("LVL.direction", f"{des} {net}", f"output on {pin}, a pin that can only be an input", "input only",
                    "a pin that can drive (output or bidirectional)", False)
    for des, rl in meta["relays"].items():
        p = values(s.n.part(des))
        a, b = rl["coil"]
        vc = abs(v(res, a) - v(res, b)) if a and b else 0.0
        if rl["on"] and "v_operate_v" in p:
            s.q(des, "v_coil_op", None, "V", "", des, "relay pulls in: coil voltage ≥ must-operate voltage", lo=vc,
                code="LIM.range", entry=False, lims=[Limit(min=p["v_operate_v"],
                                                           source=f"v_operate_v of {s.n.entry_key(des)}")])
        if not rl["on"] and "v_release_v" in p:
            s.q(des, "v_coil_rel", vc, "V", "", des, "relay releases: coil voltage ≤ must-release voltage",
                code="LIM.range", entry=False, lims=[Limit(max=p["v_release_v"],
                                                           source=f"v_release_v of {s.n.entry_key(des)}")])
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        r = limits(part)
        if values(part).get("behavior") != "current" or not {"vin_min_v", "vin_max_v"} & set(r):
            continue
        ground = ground_pin(d, des, part)
        for num, info in part["pins"].items():
            if d.pin_net.get(f"{des}.{num}") and info.get("type") == "power_in":
                x = at_pin(d, res, f"{des}.{num}", ground)
                s.q(des, "vin", x, "V", "", des, f"supply voltage at {info.get('name', num)} within vin_min … vin_max",
                    lo=x, code="LIM.range", entry=False,
                    lims=[Limit(max=r.get("vin_max_v"), min=r.get("vin_min_v"),
                                source=f"vin_min_v … vin_max_v of {s.n.entry_key(des)}")])
    operating_range(s)
    opamps(s)
    bridges(s)
    chargers(s)
    cc_led_drivers(s)
    input_injection(s)
    supply_order_e(s)
    powered_pins(s)
    pin_currents(s)
    adc_windows(s)
    switch_dc(s)
    photomos_states(s)
    pd_shunts(s)
    config_windows(s)
    supply_pin_currents(s)
    clocks(s)
    logic_levels(s)
    leds(s, load)
    strip.judge(s, load)          # LED strips: every pixel's supply, every feed (sim/strip.py)
    for des in s.sim.get("expect_blocking", []):
        i = res.get(f"@d_{des.lower()}[id]", 0.0)
        s.check("SIM.state", des, "diode blocks", abs(i), f"≤ {crit['blocking_max_a'] * 1e3:.0f} mA",
                abs(i) <= crit["blocking_max_a"], "A")
    tol, gnd = crit["net_range_tol_v"], d.ground
    for name, net in d.nets.items():
        if net.get("isolated"):
            continue        # its range is its own loop's, not against this board's ground (net key isolated)
        g = v(res, netlist.node(netlist.local_ground(d, name), gnd))
        lo, hi = net.get("v", [0, 0])
        nodes = netlist.net_nodes(d, name)
        if nodes and all(x not in res and x != "0" for x in nodes):
            continue        # no element of the netlist touches the net (a header pin, an MCU input): nothing to judge
        xs = [(v(res, x) - g, x) for x in nodes]
        s.q(name, "v_net", max(xs)[0], "V", "", None, "net voltage inside the declared range", lo=min(xs)[0],
            code="LIM.declared", entry=False, lims=[Limit(max=hi, min=lo, eps=tol, source=f"v of net {name} in the "
                                                                                          "graph")])
        if len(nodes) > 1:      # the routed copper: the pins of the lowest and the highest voltage
            pin_at = {netlist.pin_node(d, ref): ref for ref in reversed(net["pins"])}
            (x_lo, n_lo), (x_hi, n_hi) = min(xs), max(xs)
            s.qs[-1].actual = f"{x_lo:.4g} V ({pin_at[n_lo]}) … {x_hi:.4g} V ({pin_at[n_hi]})"
    if plugin and hasattr(plugin, "checks"):
        plugin.checks(design=d, cfg=s.sim, res=res, meta=meta, load=load, add=s.plugin_add)


def operating_range(s):
    """LIM.range: a part with an operating supply range – vdd_op_min_v/vdd_op_max_v for its supply pins, or a pin's
    v_op_min_v/v_op_max_v – supplied inside it, measured to its own ground pin."""
    d, res = s.d, s.res
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        if part.get("kind") == strip.KIND:
            continue              # every pixel along it, not its pins: strip.judge
        r = limits(part)
        ranges = {n: (r.get("vdd_op_min_v"), r.get("vdd_op_max_v")) for n in supply_pins(part)}
        ranges.update({n: (i.get("v_op_min_v"), i.get("v_op_max_v")) for n, i in (part.get("pins") or {}).items()
                       if i.get("v_op_min_v") is not None or i.get("v_op_max_v") is not None})
        ground, seen = ground_pin(d, des, part), set()
        for num, (lo, hi) in ranges.items():
            net = d.pin_net.get(f"{des}.{num}")
            if net is None or (lo is None and hi is None) or (net, lo, hi) in seen:
                continue
            seen.add((net, lo, hi))
            x = at_pin(d, res, f"{des}.{num}", ground)
            if math.isnan(x):
                continue
            s.q(des, "v_op", x, "V", "", des, f"supply voltage at {part['pins'][num].get('name', num)} inside its "
                                              "operating range", lo=x, code="LIM.range", entry=False,
                lims=[Limit(max=hi, min=lo, source=f"operating range of {s.n.entry_key(des)}")])


def gate_drive(s, des, part, nodes):
    """LIM.range/gate: a MOSFET switch is off (|VGS| below the smallest |vgs_th_v|) or on at a VGS its entry specifies
    RDS(on) at (rds_on_max_ohm as a table {VGS: Ω}) – in between it is half on: hot, or a load that never switches
    off."""
    p = values(part)
    table, th = p.get("rds_on_max_ohm"), p.get("vgs_th_v")
    if not isinstance(table, dict) or not table or th is None:
        return
    given = [abs(x) for x in (th if isinstance(th, list) else [th]) if isinstance(x, (int, float))]
    if not given:                       # [min, typ, max] with nothing but null: no threshold to hold the gate to
        return
    vth = min(given)                    # a datasheet without a typical value: [min, null, max]
    spec = min(abs(float(vgs)) for vgs in table)
    _, g, src = (v(s.res, x) for x in nodes)
    # the drive in the device's own sense: VGS for an N-MOSFET, VSG for a P-MOSFET – a gate driven the other way
    # (a PMOS gate above its source) holds it off however large the magnitude
    drive = (src - g) if part.get("kind") == "pmos" else (g - src)
    half = vth < drive < spec
    name = "VSG" if part.get("kind") == "pmos" else "VGS"
    s.check("LIM.range", des, "gate drive off or specified on", f"{name} {drive:.3g} V" + (" – half on" if half else ""),
            f"≤ {vth:g} V (VGS(th)) or ≥ {spec:g} V (RDS(on) specified)", not half,
            source=f"vgs_th_v, rds_on_max_ohm of {s.n.entry_key(des)}", grade="gate", on=(("component", des),))


RELATIVE_TYPES = ("input", "bidirectional", "output")     # the pins the part's vin_rel_max_v holds by default
POWERED_FALLBACK_V = 1.0       # a part counts as powered from 1 V on its supply pin where its entry gives no minimum –
                               # edakit's choice, not a datasheet's


def pin_by_name(part, name):
    """The number of the part's first pin of this name, or None."""
    return next((n for n, i in (part.get("pins") or {}).items() if i.get("name") == name), None)


def reference(d, res, des, part, info, ground, key="ref"):
    """(volts, what) – the supply a pin's relative limit and threshold ratios refer to: the pin its `ref` names (for
    the relative limit `rel_ref` first, where the datasheet refers it to another supply than the thresholds), else the
    part's first connected supply pin; (None, …) without one."""
    name = info.get(key) or info.get("ref")
    if name:
        num = pin_by_name(part, name)
        if num and f"{des}.{num}" in d.pin_net:
            return at_pin(d, res, f"{des}.{num}", ground), name
        return None, name
    pins = [n for n in supply_pins(part) if f"{des}.{n}" in d.pin_net]
    if not pins:
        return None, "its supply"
    return at_pin(d, res, f"{des}.{pins[0]}", ground), "its supply"


def thevenin(s, des, ref):
    """(V, R) – the source a pin sees on its net when every other part on the net is a resistor or a capacitor: the
    resistors to their far ends in parallel; None where anything else is on the net or a resistor has no value."""
    d, res = s.d, s.res
    net = d.pin_net.get(ref)
    if net not in d.nets:         # a node of its own behind a cable wire (a strip's pin): not known here
        return None
    nodes = set(netlist.net_nodes(d, net))
    conductance, current = 0.0, 0.0
    for other in d.nets[net]["pins"]:
        o_des = other.split(".", 1)[0]
        if o_des == des:
            continue
        kind = (s.n.part(o_des) or {}).get("kind")
        if kind == "capacitor":
            continue
        if kind != "resistor":
            return None
        els = [el for el in s.meta["elements"].get(o_des, []) if el["kind"] == "resistor" and el.get("value")]
        if not els:
            return None
        el = els[0]
        far = next((x for x in el["nodes"][:2] if x not in nodes), None)
        if far is None:
            continue
        conductance += 1 / el["value"]
        current += v(res, far) / el["value"]
    if conductance == 0:
        return None
    return current / conductance, 1 / conductance


def input_injection(s):
    """LIM.v/inject: no pin above the supply it refers to by more than its entry allows – the pin's v_rel_max_v (null:
    none, a pin rated above its supply) against the pin its `ref` names, else the part's vin_rel_max_v for its inputs,
    bidirectional pins and outputs against its supply. Where the pin gives i_inject_max_a and only resistors feed it,
    the current its clamp diode takes – (V_open − V_ref − v_rel) / R_source – is held to that instead: the clamp
    conducts, the part is powered through its pin or latches up. A pin on a net no element of the netlist reaches has
    no voltage (nan) and is not judged, as LIM.range does."""
    d, res = s.d, s.res
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        default = limits(part).get("vin_rel_max_v")
        ground = ground_pin(d, des, part)
        for num, info in (part.get("pins") or {}).items():
            ref = f"{des}.{num}"
            if ref not in d.pin_net:
                continue
            if "v_rel_max_v" in info:
                rel, where = info["v_rel_max_v"], f"v_rel_max_v of pin {info.get('name', num)} of {s.n.entry_key(des)}"
            elif info.get("type") in RELATIVE_TYPES:
                rel, where = default, f"vin_rel_max_v of {s.n.entry_key(des)}"
            else:
                continue
            if rel is None:
                continue
            vref, ref_name = reference(d, res, des, part, info, ground, key="rel_ref")
            if vref is None or math.isnan(vref):
                continue
            x = at_pin(d, res, ref, ground) - vref
            if math.isnan(x):
                continue          # a net no element of the netlist reaches (QSPI lines between two ICs): no reading
            name = info.get("name", num)
            inject = info.get("i_inject_max_a")
            src = thevenin(s, des, ref) if is_number(inject) and x > rel else None
            if src is not None:
                v_open, r_src = src
                i = max((v_open - (vref + rel)) / r_src, 0.0)
                s.q(ref, "i_inject", i, "A", "", des, f"current into the clamp of {name} ({x:.3g} V above {ref_name} "
                    f"through {r_src:.4g} Ω)", code="LIM.v", entry=False, grade="inject",
                    lims=[Limit(max=inject, source=f"i_inject_max_a of pin {name} of {s.n.entry_key(des)}")])
                continue
            s.q(ref, "vin_rel", x, "V", "", des, f"{info.get('type', 'pin')} {name} above {ref_name}",
                code="LIM.v", entry=False, grade="inject", lims=[Limit(max=rel, source=where)])


def supply_order_e(s):
    """LIM.v/order at the operating point: a supply the entry says never rises above another (supply_order) is not
    above it in this scenario."""
    from .limits import order_pairs
    d, res = s.d, s.res
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        ground = ground_pin(d, des, part)
        for lo_pin, hi_pin, lo_name, hi_name in order_pairs(part):
            a, b = f"{des}.{lo_pin}", f"{des}.{hi_pin}"
            if a not in d.pin_net or b not in d.pin_net:
                continue
            x = at_pin(d, res, a, ground) - at_pin(d, res, b, ground)
            s.q(des, "v_order", x, "V", "", des, f"{lo_name} above {hi_name}", code="LIM.v", entry=False,
                grade="order", lims=[Limit(max=0.0, eps=SIM_EPS_V, source=f"supply_order of {s.n.entry_key(des)}")])


def powered(s, des, part, ground):
    """Whether the part is powered in this scenario: its first supply pin at least its operating minimum (the pin's
    v_op_min_v, the entry's vdd_op_min_v, vin_min_v or vsys_min_v), else at least POWERED_FALLBACK_V."""
    d = s.d
    pins = [n for n in supply_pins(part) if f"{des}.{n}" in d.pin_net]
    if not pins:
        return False
    info, r = part["pins"][pins[0]], limits(part)
    least = next((x for x in (info.get("v_op_min_v"), r.get("vdd_op_min_v"), r.get("vin_min_v"), r.get("vsys_min_v"))
                  if is_number(x)), POWERED_FALLBACK_V)
    return at_pin(d, s.res, f"{des}.{pins[0]}", ground) >= least


def powered_pins(s):
    """LIM.v at a pin with v_max_powered_v (schema-gaps B3 – the RP2350's fault-tolerant GPIOs): while the part is
    powered held to v_max_powered_v, while it is not to v_max_v (grade powered)."""
    d, res = s.d, s.res
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        pins = {n: i for n, i in (part.get("pins") or {}).items()
                if is_number(i.get("v_max_powered_v")) and f"{des}.{n}" in d.pin_net}
        if not pins:
            continue
        ground = ground_pin(d, des, part)
        on = powered(s, des, part, ground)
        for num, info in pins.items():
            x = at_pin(d, res, f"{des}.{num}", ground)
            lim = info["v_max_powered_v"] if on else info.get("v_max_v")
            if not is_number(lim):
                continue
            s.q(f"{des}.{num}", "v_pin", x, "V", "", des, f"{info.get('name', num)} while {des} is "
                f"{'powered' if on else 'unpowered'}", code="LIM.v", entry=False, grade="" if on else "powered",
                lims=[Limit(max=lim, eps=SIM_EPS_V, source=f"{'v_max_powered_v' if on else 'v_max_v'} of pin "
                                                           f"{info.get('name', num)} of {s.n.entry_key(des)}")])


CURRENT_KINDS = ("resistor", "capacitor", "led", "diode")    # parts whose current the operating point gives


def pin_current(s, des, ref):
    """The current out of a pin into its net (A, + sourced), from the operating point – only where every other part on
    the net is a resistor, a capacitor, an LED or a diode; None otherwise."""
    d, res = s.d, s.res
    net = d.pin_net.get(ref)
    if net not in d.nets:         # a node of its own behind a cable wire (a strip's pin): not known here
        return None
    nodes = set(netlist.net_nodes(d, net))
    total = 0.0
    for other in d.nets[net]["pins"]:
        o_des = other.split(".", 1)[0]
        if o_des == des:
            if other != ref:
                return None                    # two pins of the part on the net: their shares are not known
            continue
        kind = (s.n.part(o_des) or {}).get("kind")
        if kind not in CURRENT_KINDS:
            return None
        if kind == "capacitor":
            continue
        for el in s.meta["elements"].get(o_des, []):
            here = [x for x in el["nodes"][:2] if x in nodes]
            if len(here) != 1:
                continue
            if el["kind"] == "resistor" and el.get("value"):
                near, far = (el["nodes"][0], el["nodes"][1]) if el["nodes"][0] in nodes else (el["nodes"][1],
                                                                                              el["nodes"][0])
                total += (v(res, near) - v(res, far)) / el["value"]
            elif el["kind"] in ("led", "diode"):
                i = res.get(f"@{el['name']}[id]", float("nan"))
                total += i if el["nodes"][0] in nodes else -i
    return total


def mcu_pin_currents(s, des, part):
    """{pin number: current out of the pin (A)} of an MCU's outputs, from their ammeters."""
    amps = (s.meta["mcu"].get(des) or {}).get("gpio_ammeters", {})
    out = {}
    for num in (part.get("pins") or {}):
        net = s.d.pin_net.get(f"{des}.{num}")
        if net in amps:
            out[num] = s.res.get(amps[net], 0.0)
    return out


def pin_currents(s):
    """LIM.i/pin (schema-gaps C1): a pin's current within its i_max_a, a group's sourced and sunk sums within the max of
    the entry's i_group_max_a ("dir": "sourced" or "sunk" for a group the datasheet sums in one direction only) – where
    the operating point gives the currents: pin_current, an MCU's output ammeters (its pins' own limit is gpio_i)."""
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        mcu = values(part).get("behavior") == "mcu"
        wanted = not mcu and any(is_number(i.get("i_max_a")) for i in (part.get("pins") or {}).values())
        if not wanted and not part.get("i_group_max_a"):
            continue
        known = mcu_pin_currents(s, des, part) if mcu else {}
        for num, info in ({} if mcu else (part.get("pins") or {})).items():
            ref = f"{des}.{num}"
            if ref not in s.d.pin_net:
                continue
            i = pin_current(s, des, ref)
            if i is None or math.isnan(i):
                continue
            known[num] = i
            if is_number(info.get("i_max_a")):
                s.q(ref, "i_pin", abs(i), "A", "", des, f"current of pin {info.get('name', num)}", code="LIM.i",
                    entry=False, grade="pin", lims=[Limit(max=info["i_max_a"], derate=s.der.get("i", 1.0),
                                                         source=f"i_max_a of pin {info.get('name', num)} of "
                                                                f"{s.n.entry_key(des)}")])
        for group, g in (part.get("i_group_max_a") or {}).items():
            got = [known[str(n)] for n in g.get("pins", []) if str(n) in known]
            if not got or not is_number(g.get("max")):
                continue
            for what, x in (("sourced", sum(i for i in got if i > 0)), ("sunk", -sum(i for i in got if i < 0))):
                if g.get("dir") not in (None, what):
                    continue
                s.q(f"{des} {group}", "i_group", x, "A", "", des, f"current {what} by the pins of {group} together",
                    code="LIM.i", entry=False, grade="pin",
                    lims=[Limit(max=g["max"], derate=s.der.get("i", 1.0),
                                source=f"i_group_max_a.{group} of {s.n.entry_key(des)}")])


SWITCH_DC_MAX_V = 0.01     # edakit's choice for "within a few mV" (maker-coverage CK-30), not a datasheet figure
SIGNAL_MIN_LOAD_A = 10e-6  # a contact rated for signal currents: a signal relay's minimum applicable load
                           # (Hongfa HFD4: 10 µA at 10 mV) – rules-at-scale.md, decision 14
CONTACT_KINDS = ("switch", "button", "dip_switch", "relay", "potentiometer")


def photomos_states(s):
    """A photo-MOS output (behaviour photomos): its LED current either at if_on_a or more – guaranteed on – or at
    if_off_a or less – guaranteed off; in between the datasheet promises neither (LIM.range/photomos). The load
    current and the voltage across the output against i_load_max_a and v_load_max_v of its entry."""
    res = s.res
    for des, m in sorted((s.meta.get("photomos") or {}).items()):
        i_led = res.get(m["led"], float("nan"))
        a, b = (v(res, x) for x in m["nodes"])
        i_load = abs(res.get(m["ammeter"], 0.0))
        s.q(des, "i_load", i_load, "A", "photomos", des, "load current through the photo-MOS output")
        s.q(des, "v_load", abs(a - b), "V", "photomos", des, "voltage across the photo-MOS output")
        if i_led != i_led:
            continue
        state = "on" if i_led >= m["if_on_a"] else "off" if i_led <= m["if_off_a"] else "neither"
        s.check("LIM.range", des, f"LED current of {des} guarantees a state (on ≥ {m['if_on_a'] * 1e3:g} mA, off ≤ "
                f"{m['if_off_a'] * 1e3:g} mA)", i_led * 1e3, f"on or off, not between – {state}", state != "neither",
                "mA", f"if_on_a, if_off_a of {s.n.entry_key(des)}", grade="photomos", on=(("component", des),))


def pd_shunts(s):
    """A USB PD sink's VDD shunt (behaviour pd_sink): the current it sinks within i_shunt_max_a – at the limit it can
    hold VDD no longer and VDD rises with the supply (the series resistor too small for the highest request)."""
    res = s.res
    for des, m in sorted((s.meta.get("pd_sinks") or {}).items()):
        i = res.get(m["ammeter"], 0.0)
        vdd = v(res, m["vdd"]) - v(res, m["gnd"])
        s.q(des, "i_shunt", i, "A", "", des, f"VDD shunt current (VDD {vdd:.3g} V)", code="LIM.i", entry=False,
            lims=[Limit(max=m["i_max_a"] * 0.999, source=f"i_shunt_max_a of {s.n.entry_key(des)}")])


def signal_path_contacts(s):
    """{designator: [{net: pin}, …]} of the switches, buttons, relays and pots whose contacts have both sides in a
    signal path (nets with signal or instrument) – one group per contact set (a DPDT relay's two sets apart, a 3PDT
    switch's three poles)."""
    if getattr(s, "_signal_contacts", None) is not None:
        return s._signal_contacts
    d, out = s.d, {}
    signal = {name for name, net in d.nets.items() if net.get("signal") or net.get("instrument")}
    for des in sorted(s.n.comps) if len(signal) >= 2 else ():
        part = s.n.part(des) or {}
        kind = part.get("kind")
        if kind not in CONTACT_KINDS:
            continue
        if kind == "relay":           # each contact set apart: a DPDT's two sets sit in two signal paths
            groups = [sorted(n for nums in roles.values() for n in nums) for roles in relay_sets(part).values()]
        elif kind == "switch" and len(switch_sets(part)) > 1:     # each pole apart: a 3PDT's poles, three paths
            groups = [sorted(n for nums in roles.values() for n in nums) for roles in switch_sets(part).values()]
        else:
            groups = [list((part.get("pins") or {}))]
        found = []
        for group in groups:
            on = {}
            for num in group:
                net = d.pin_net.get(f"{des}.{num}")
                if net and net not in d.nets:      # a net a cable runs through: its node on this board, 'IN__main'
                    net = net.rsplit("__", 1)[0]
                if net in signal:
                    on.setdefault(net, num)
            if len(on) >= 2:
                found.append(on)
        if found:
            out[des] = found
    s._signal_contacts = out
    return out


def switch_dc(s):
    """REQ.value/switch: the contacts of a switch, button, relay or pot whose sides are both in a signal path (nets
    with signal or instrument) sit at one DC level in the scenario – a step across them is the pop when it switches
    and the scratch when a pot turns. A side no element reaches (nan) is LVL.undefined/analog's, not this check's.
    REQ.value/min_load: such a contact is rated for signal currents – the minimum load of its entry (values
    min_load_a) at most 10 µA; an entry without min_load_a is not judged."""
    d, res = s.d, s.res
    for des, groups in signal_path_contacts(s).items():
        least = values(s.n.part(des) or {}).get("min_load_a")
        if least is not None:
            s.check("REQ.value", des, f"minimum load of {des}'s contacts in the signal path", least * 1e6,
                    f"≤ {SIGNAL_MIN_LOAD_A * 1e6:g} µA", least <= SIGNAL_MIN_LOAD_A, "µA",
                    f"min_load_a of {s.n.entry_key(des)}; the line: Hongfa HFD4, 10 µA at 10 mV (decision 14)", grade="min_load",
                    on=(("component", des),))
        for on in groups:
            xs = {net: at_pin(d, res, f"{des}.{num}") for net, num in on.items()}
            if any(x != x for x in xs.values()):
                continue
            lo, hi = min(xs, key=xs.get), max(xs, key=xs.get)
            dv = xs[hi] - xs[lo]
            s.check("REQ.value", des, f"DC across {des} in the signal path ({lo} {xs[lo]:.3g} V, {hi} {xs[hi]:.3g} V)",
                    dv * 1e3, f"≤ {SWITCH_DC_MAX_V * 1e3:g} mV", dv <= SWITCH_DC_MAX_V, "mV", "maker-coverage CK-30",
                    grade="switch", on=(("component", des),))


def adc_windows(s):
    """LIM.range/adc: the voltage at a pin of a net with fn adc inside the window its entry gives the converter
    (pin adc.range_v)."""
    d, res = s.d, s.res
    for name, net in sorted(d.nets.items()):
        if net.get("fn") != "adc":
            continue
        for ref in net["pins"]:
            info = d.pin_info(ref)
            window = (info.get("adc") or {}).get("range_v") if isinstance(info.get("adc"), dict) else None
            if not window:
                continue
            des = ref.partition(".")[0]
            x = at_pin(d, res, ref, ground_pin(d, des, s.n.part(des) or {}))
            s.q(ref, "v_adc", x, "V", "", des, f"{name} inside the ADC's window", lo=x, code="LIM.range", entry=False,
                grade="adc", lims=[Limit(min=window[0], max=window[1], source=f"adc.range_v of {ref}")])



def config_windows(s):
    """REQ.value/window (maker-coverage CK-20): a configuration pin that reads its setting by voltage window (pin
    windows: [{state, min_v, max_v}], the windows its datasheet guarantees – between the trip points' max and min) sits
    inside one window in the operating point, not between two, where the part may read either; the pin's own pull is in
    the netlist (netlist.window_pulls)."""
    d, res = s.d, s.res
    for des in sorted(d.comps):
        part = s.n.part(des) or {}
        ground = None
        for num, p in (part.get("pins") or {}).items():
            ws, ref = p.get("windows"), f"{des}.{num}"
            if not isinstance(ws, list) or not ws or not d.pin_net.get(ref):
                continue
            ground = ground or ground_pin(d, des, part)
            x = at_pin(d, res, ref, ground)
            hit = [w.get("state") for w in ws if not math.isnan(x)
                   and w.get("min_v", -math.inf) <= x <= w.get("max_v", math.inf)]
            expected = "; ".join(f"{w.get('state')} " + (f"{w['min_v']:g}" if "min_v" in w else "") + " … "
                                 + (f"{w['max_v']:g}" if "max_v" in w else "") + " V" for w in ws)
            s.check("REQ.value", ref, f"{ref} ({p.get('name', num)}) inside one window of its setting"
                    + (f": {hit[0]}" if hit else ""), x, expected, bool(hit), "V",
                    f"pin windows of {s.n.entry_key(des)}", grade="window", on=(("component", des),))


def supply_pin_currents(s):
    """LIM.i/supply_pin: what a constant-current driver's outputs sink together, plus its own supply current, through
    its ground pin – within limits i_supply_pin_max_a."""
    res = s.res
    for des, t in sorted((s.meta.get("cc") or {}).items()):
        most = limits(s.n.part(des)).get("i_supply_pin_max_a")
        if most is None:
            continue
        total = sum(max(res.get(ch["ammeter"], 0.0), 0.0) for ch in t["channels"].values())
        total += t["values"].get("idd_max_a", 0.0) if t.get("vdd") else 0.0
        s.q(des, "i_pin", total, "A", "", des, "current through its supply pins (all outputs together)", code="LIM.i",
            entry=False, grade="supply_pin",
            lims=[Limit(max=most, source=f"i_supply_pin_max_a of {s.n.entry_key(des)}")])


def clocks(s):
    """LIM.range/clock: an MCU's clock (values f_clock_hz) within the highest clock its supply allows (limits f_max_hz
    by supply voltage, {"2.7": 10e6, "4.5": 20e6}, linear in between) – an ATmega328P at 16 MHz needs more than
    3.3 V."""
    res = s.res
    for des, m in sorted(s.meta.get("mcu", {}).items()):
        f, curve = m["values"].get("f_clock_hz"), m["limits"].get("f_max_hz")
        if f is None or not isinstance(curve, dict) or not curve:
            continue
        node = m.get("io_rail") or m.get("vout") or m.get("vin")
        x = v(res, node)
        pts = sorted((float(volts), hz) for volts, hz in curve.items())
        if x <= pts[0][0]:
            fmax = pts[0][1] if x >= pts[0][0] - 1e-9 else 0.0
        elif x >= pts[-1][0]:
            fmax = pts[-1][1]
        else:
            fmax = next(f0 + (f1 - f0) * (x - v0) / (v1 - v0) for (v0, f0), (v1, f1) in zip(pts, pts[1:]) if v0 <= x <= v1)
        s.check("LIM.range", des, "clock within what its supply allows", f"{f / 1e6:.4g} MHz at {x:.3g} V",
                f"≤ {fmax / 1e6:.4g} MHz (f_max_hz of {s.n.entry_key(des)})", f <= fmax * (1 + 1e-9), grade="clock",
                on=(("component", des),))


def bridges(s):
    """A bridge driver (behaviour bridge): every output's current within i_out_max_a (LIM.i), the heat of its high
    and low sides – I² × r_on – and its supply current against the junction limit (LIM.t, with rth_ja_k_per_w)."""
    res = s.res
    for des, br in sorted((s.meta.get("bridges") or {}).items()):
        part = s.n.part(des)
        r, key = limits(part), s.n.entry_key(des)
        heat = 0.0
        for role, o in sorted(br["outputs"].items()):
            hi, lo = res.get(o["high"], 0.0), res.get(o["low"], 0.0)
            vo = v(res, o["node"])
            heat += abs((v(res, o["vm"]) - vo) * hi) + abs((vo - v(res, o["ret"])) * lo)
            if "i_out_max_a" in r:
                s.q(f"{des} {role}", "i_out", max(abs(hi), abs(lo)), "A", "", des, f"output {role} current", entry=False,
                    lims=[Limit(max=r["i_out_max_a"], source=f"i_out_max_a of {key}")])
        supply = br["vcc"] or br["vm"]
        heat += (v(res, supply) - v(res, br["gnd"])) * br["values"].get("idd_max_a", 0.0)
        if "rth_ja_k_per_w" in r:
            junction(s, des, heat, r, f"junction temperature at {s.amb} °C: {heat:.3g} W in the bridges × "
                                      f"{r['rth_ja_k_per_w']:g} K/W")


def chargers(s):
    """A linear charger (behaviour charger): the current it charges with within its i_out_max_a (LIM.i/charge – the
    programmed current, prog_v / R_PROG, is held statically by engines/limits.py), and its heat, (V(vin) − V(bat)) ×
    I plus the quiescent current, against the junction limit (LIM.t, with rth_ja_k_per_w)."""
    res = s.res
    for des, ch in sorted((s.meta.get("chargers") or {}).items()):
        part = s.n.part(des)
        r, key = limits(part), s.n.entry_key(des)
        i = max(res.get(ch["ammeter"], 0.0), 0.0)
        vin, bat, gnd = (v(res, ch[k]) for k in ("vin", "bat", "gnd"))
        what = f"charge current (programmed {ch['i_set'] * 1e3:.3g} mA)" if ch["i_set"] else "charge current – no PROG resistor"
        s.q(des, "i_charge", i, "A", "", des, what, code="LIM.i", grade="charge", entry=False, report=True,
            lims=[Limit(max=r["i_out_max_a"], source=f"i_out_max_a of {key}")] if "i_out_max_a" in r else [])
        heat = (vin - bat) * i + (vin - gnd) * ch["values"].get("iq_a", 0.0)
        if "rth_ja_k_per_w" in r:
            junction(s, des, heat, r, f"junction temperature at {s.amb} °C: {heat:.3g} W – (VIN − VBAT) × I + VIN × "
                                      f"IQ – × {r['rth_ja_k_per_w']:g} K/W")


# --- a boost converter's enable, a constant-current LED buck (maker-coverage FT-5, FT-14) -----------------------------
def boost_off(s, des, reg, vin, vout):
    """A boost converter its enable switched off (switch_boost): its output is what the inductor and the diode behind
    its switch pin pass from the input – a row of information instead of SIM.state; what hangs on the output is judged
    at that level (the load's expect, LEDs on or dark, the parts' limits)."""
    s.rows.append({"id": "SIM.state", "scenario": s.name, "item": des,
                   "check": "output with EN low (converter off, no load disconnect)", "actual": f"{vout:.4g} V",
                   "expected": f"the input {vin:.4g} V through the inductor and {reg['diode']} – information",
                   "result": "info"})


def cc_led_drivers(s):
    """A constant-current step-down LED driver (behaviour cc_led_driver – PT4115, AL8860): the current R_S sets,
    vsense_v [min … max] / R_S, within the driver's i_out_max_a (LIM.i/cc) and R_S at least r_sense_min_ohm
    (REQ.value/cc); the input at least what the string needs – the voltage across R_S, the LEDs and the inductor, over
    the maximum duty cycle, plus the set current through the switch's r_on_ohm: the on-time equation of both datasheets
    (LIM.range/cc); each LED of the string at its share of the set current, or dark with dim low (SIM.state/cc); the
    inductor of the string saturating above the peak current, the set current × (1 + ripple_ratio / 2) (LIM.i/cc).
    The LEDs' own if_max_a and the inductor's i_max_a hold the simulated current (stress), the top of vsense_v."""
    res, crit = s.res, s.crit
    for des, cc in sorted((s.meta.get("cc_bucks") or {}).items()):
        key, on, p = s.n.entry_key(des), (("component", des),), cc["values"]
        r_s, vs = cc["r_s"], cc["vsense"]
        if r_s is None or not vs:
            s.check("SIM.state", des, "LED current set by R_S", "no resistor from VIN to the sense pin" if vs
                    else "no vsense_v in the entry", "R_S from VIN to the sense pin, I = vsense_v / R_S", False,
                    grade="cc", on=on)
            continue
        lo, hi = min(vs) / r_s, max(vs) / r_s
        s.q(des, "i_out", hi, "A", "", des, f"LED current set by R_S {r_s:.4g} Ω ({min(vs) * 1e3:.4g} … "
            f"{max(vs) * 1e3:.4g} mV / R_S, {lo * 1e3:.4g} … {hi * 1e3:.4g} mA)", lo=lo, code="LIM.i", grade="cc",
            report=True)
        if (least := cc["limits"].get("r_sense_min_ohm")) is not None:
            s.q(des, "r_sense", None, "Ω", "", des, "sense resistor R_S", lo=r_s, code="REQ.value", grade="cc",
                entry=False, lims=[Limit(min=least, source=f"r_sense_min_ohm of {key}")])
        frac = min(max(v(res, cc["dim"]), 0.0), 1.0)
        target = cc["i_set"] * frac
        if frac > 1e-3:
            g = v(res, cc["gnd"])
            vin, sw = v(res, cc["vin"]) - g, v(res, cc["sw"]) - g
            dmax, r_on = p.get("duty_max_ratio", 1.0), p.get("r_on_ohm", 0.0)
            across = vin - sw
            how = (f"input above the LED string: {across:.4g} V across R_S, the LEDs and the inductor"
                   + (f" / {dmax:g} (maximum duty cycle)" if dmax != 1 else "") + f" + {target * 1e3:.4g} mA × "
                   f"{r_on:g} Ω (switch)")
            s.q(des, "vin_cc", None, "V", "", des, how, lo=vin, code="LIM.range", grade="cc", entry=False,
                lims=[Limit(min=round(across / dmax + target * r_on, 6),
                            source=f"vsense_v, r_on_ohm{', duty_max_ratio' if dmax != 1 else ''} of {key} – the "
                                   "on-time equation of its datasheet")])
        n, off_max = cc["parallel"], crit["led_off_max_a"]
        for name in cc["leds"]:
            label, cur = name[2:].upper(), res.get(f"@{name}[id]", float("nan"))
            here = (("component", label),)
            if frac > 1e-3:
                share = target / n
                s.check("SIM.state", label, f"LED current ({des} string)", cur, f"≥ {crit['led_on_min_ratio']:.0%} of "
                        f"{share * 1e3:.2f} mA", cur >= crit["led_on_min_ratio"] * share, "A", grade="cc", on=here)
            else:
                s.check("SIM.state", label, "LED dark", cur, f"≤ {off_max * 1e6:.0f} µA", cur <= off_max, "A",
                        grade="cc", on=here)
        ripple = p.get("ripple_ratio")
        for coil in cc["coils"] if ripple is not None and frac > 1e-3 else []:
            sat = limits(s.n.part(coil)).get("i_sat_a")
            if sat is not None:
                s.q(coil, "i_peak", hi * frac * (1 + ripple / 2), "A", "inductor", coil,
                    f"peak current: {hi * frac * 1e3:.4g} mA × (1 + {ripple:g} / 2), the ripple of {key}", code="LIM.i",
                    grade="cc", entry=False, lims=[Limit(max=sat, source=f"i_sat_a of {s.n.entry_key(coil)}")])


def opamps(s):
    """LIM.range/opamp: every input of an op-amp (behaviour opamp) inside its common-mode range – vicm_v [above vee,
    from vcc] –, and every output inside its swing: an output held at the limit of vout_swing_v while its inputs stand
    apart has left the linear range (a comparator, values comparator: true, is meant to)."""
    res = s.res
    for des, oa in sorted((s.meta.get("opamps") or {}).items()):
        p, key = oa["values"], s.n.entry_key(des)
        vcc, vee = v(res, oa["vcc"]), v(res, oa["vee"])
        for ch, n in sorted(oa["channels"].items()):
            if p.get("vicm_v"):
                lo_off, hi_off = p["vicm_v"][:2]
                for k in ("in_p", "in_n"):
                    x = v(res, n[k])
                    s.q(des, "vicm", x, "V", "", des, f"input {k}{'_' + ch if ch else ''} inside the common-mode range",
                        lo=x, code="LIM.range", entry=False, grade="opamp",
                        lims=[Limit(min=round(vee + lo_off, 6), max=round(vcc + hi_off, 6),
                                    source=f"vicm_v of {key}, from the rails {vee:.3g} V and {vcc:.3g} V")])
            if p.get("comparator"):
                continue
            lo, hi = (p.get("vout_swing_v") or [0, 0])[:2]
            low, high = vee + lo, vcc + hi
            target = netlist.A_OL * (v(res, n["in_p"]) - v(res, n["in_n"]))
            out = v(res, n["out"])
            clipped = target > high + 1e-3 or target < low - 1e-3
            s.check("LIM.range", des, f"output {'out_' + ch if ch else 'out'} linear, inside its swing",
                    f"{out:.4g} V – held at the limit, inputs {abs(target) / netlist.A_OL * 1e3:.3g} mV apart"
                    if clipped else f"{out:.4g} V", f"{low:.4g} … {high:.4g} V (vout_swing_v of {key})", not clipped,
                    grade="opamp", on=(("component", des),))


def logic_levels(s):
    """LVL.threshold: every input with thresholds (vih/vil, as a voltage or a ratio of its supply) at ≤ VIL or ≥ VIH,
    and the high level of every MCU output on its net reaching them; a ratio without one supply pin: SIM.config."""
    d, res = s.d, s.res
    joined = d.joined_nets()
    reach = defaultdict(list)
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        p = values(part)
        if p.get("behavior") == "mcu":
            continue
        inputs = [(n, i) for n, i in (part.get("pins") or {}).items() if i.get("type") == "input"
                  and f"{des}.{n}" in d.pin_net and all(any(f"{k}_{x}" in src for src in (i, p) for x in ("v", "ratio"))
                                                        for k in ("vil", "vih"))]
        if not inputs:
            continue
        ground = ground_pin(d, des, part)
        on = sorted((d.pin_net[f"{des}.{n}"], f"{des}.{n}") for n in supply_pins(part) if f"{des}.{n}" in d.pin_net)
        nets = sorted({net for net, _ in on})
        vdd = at_pin(d, res, on[0][1], ground) if len(nets) == 1 else None
        for num, info in inputs:
            vio = reference(d, res, des, part, info, ground)[0] if info.get("ref") else vdd
            vil, vih = (threshold(p, info, k, vio) for k in ("vil", "vih"))
            if vil is None or vih is None:
                s.check("SIM.config", des, "input thresholds as a ratio of the supply",
                        f"{len(nets)} supply nets ({', '.join(nets) or 'none'}), none with the role vdd or vcc",
                        "one supply pin: a power_in pin with the role vdd or vcc", False)
                break
            net, name = d.pin_net[f"{des}.{num}"], info.get("name", num)
            x = at_pin(d, res, f"{des}.{num}", ground)
            if math.isnan(vil) or math.isnan(vih):
                continue
            reach[joined.get(net, net)].append((f"{des} {name}", vih))
            if math.isnan(x):
                continue
            level = "high" if x >= vih else "low" if x <= vil else "undefined"
            s.check("LVL.threshold", f"{des} {net}", f"input level {level} at {name} (VIL {vil:.2f} V, VIH {vih:.2f} V)",
                    x, f"≤ {vil:.2f} V or ≥ {vih:.2f} V", level != "undefined", "V", f"vil/vih of {s.n.entry_key(des)}")
    for des, m in s.meta["mcu"].items():
        p = values(s.n.part(des))
        high = v(res, m["vin"]) if p.get("v_io_v") == "vin" else p.get("v_io_v", 3.3)
        for net in m.get("gpio_ammeters", {}):
            for who, vih in reach.get(joined.get(net, net), []):
                s.check("LVL.threshold", f"{des} {net}", f"output high level reaches VIH of {who}", high,
                        f"≥ {vih:.2f} V", high >= vih, "V", f"vih of {who.split()[0]}")


def multiplexed(d, anode_net, cathode_net):
    """The part that scans an LED – behaviour matrix_driver (MAX7219) with pins on both its nets –, or None."""
    on = [{r.partition(".")[0] for r in (d.nets.get(n) or {}).get("pins", [])} for n in (anode_net, cathode_net)]
    return next((des for des in sorted(on[0] & on[1])
                 if values(d.part(des) or {}).get("behavior") == "matrix_driver"), None)


def leds(s, load):
    """SIM.state of the LEDs: each LED of a driver channel at its share of the set current, parallel LEDs sharing it,
    an LED on or dark as the load says, none reversed; SIM.driver: an LED with no state to check; the driver's headroom
    and junction temperature. An LED a multiplexing driver scans (matrix_driver) has no DC state: a row of
    information."""
    res, meta, crit, d = s.res, s.meta, s.crit, s.d
    joined = d.joined_nets()
    chan_of = {}
    for des, t in meta["cc"].items():
        p, r = values(s.n.part(des)), limits(s.n.part(des))
        iset = p["iout_gain"] * -res.get(t["rext_src"], 0.0)
        t["iset"] = iset
        pd = v(res, t["vdd"]) * p.get("idd_max_a", 0.0) if t["vdd"] else 0.0
        for net, ch in t["channels"].items():
            chan_of[joined.get(net, net)] = (net, ch["on"], iset)
            if not ch["on"]:
                continue
            vo, io = v(res, ch["node"]), res.get(ch["ammeter"], 0.0)
            pd += vo * io
            s.q(f"{des} {net}", "v_out", None, "V", "", des, "output headroom", lo=vo, code="LIM.range", entry=False,
                lims=[Limit(min=p.get("vout_knee_v", 0.6), source=f"vout_knee_v of {s.n.entry_key(des)}")])
        if "rth_ja_k_per_w" in r:
            junction(s, des, pd, r, f"junction temperature at {s.amb} °C")
    on_min, off_max = crit["led_on_min_a"], crit["led_off_max_a"]
    leds_on = load.get("leds_on")
    groups = defaultdict(list)
    behind = behind_resistor(d, joined, chan_of)
    strings = {name for cc in (meta.get("cc_bucks") or {}).values() for name in cc["leds"]}
    for name, info in meta["leds"].items():
        if name in strings:
            continue      # the string of a constant-current buck: cc_led_drivers judges it
        i = res.get(f"@{name}[id]", float("nan"))
        label = name[2:].upper()
        if mux := multiplexed(d, info["anode_net"], info["cathode_net"]):
            s.rows.append({"id": "SIM.driver", "scenario": s.name, "item": label, "check": "LED multiplexed",
                           "actual": f"between {info['anode_net']} and {info['cathode_net']}, scanned by {mux} "
                                     "(matrix_driver)", "expected": "no DC state to judge", "result": "info"})
            continue
        cathode, anode = (joined.get(info[k], info[k]) for k in ("cathode_net", "anode_net"))
        hit = led_on_output(chan_of, behind, anode, cathode)
        if hit and hit[1] == "cathode":
            groups[hit[0]].append((label, i))
        elif hit:
            s.check("SIM.state", label, f"LED reversed (anode at the driver output {info['anode_net']})", i,
                    "cathode at the driver output", False, "A")
        elif leds_on is not None:
            if leds_on == "all" or info["des"] in leds_on or label in leds_on:
                s.check("SIM.state", label, "LED on", i, f"≥ {on_min * 1e3:.2g} mA", i >= on_min, "A")
            else:
                s.check("SIM.state", label, "LED dark", i, f"≤ {off_max * 1e6:.0f} µA", i <= off_max, "A")
        else:
            s.check("SIM.driver", label, "LED without a known driver", f"cathode at {info['cathode_net']}, on no driver "
                    "output; the load has no leds_on", "the cathode on a driver output, or the load's leds_on", False)
    for name, info in meta["leds_left_out"].items():
        s.check("SIM.driver", name[2:].upper(), "LED without a known driver", "left out of the simulation: no pin with "
                f"the role {' or '.join(info['roles'])} in its parts entry", "the roles the simulation reads (handbook "
                "4.1)", False)
    for key, group in groups.items():
        net, on, iset = chan_of[key]
        if not on:
            for label, i in group:
                s.check("SIM.state", label, "LED dark", i, f"≤ {off_max * 1e6:.0f} µA", i <= off_max, "A")
            continue
        target = iset / len(group)
        for label, i in group:
            s.check("SIM.state", label, f"LED current ({net})", i, f"≥ {crit['led_on_min_ratio']:.0%} of "
                    f"{target * 1e3:.2f} mA", i >= crit["led_on_min_ratio"] * target, "A")
        if len(group) > 1:
            cur = [i for _, i in group]
            ratio = min(cur) / (sum(cur) / len(cur)) if sum(cur) > 0 else 0
            s.check("SIM.state", net, "current sharing of parallel LEDs (min/mean)", ratio,
                    f"≥ {crit['chain_min_ratio']:.0%}", ratio >= crit["chain_min_ratio"])


# --- transient runs ---------------------------------------------------------------------------------------------------
def transient(s, expect, sources, times, wave, volts, extreme):
    """A run's limits: each of its expect (a net's lowest voltage ≥ min_v, highest ≤ max_v, a source's peak current
    ≤ i_max_a), and every MCU's supply pin, once it has reached its vin_min_v|vsys_min_v, never below it again."""
    meta = s.meta
    zero = [0.0] * len(times)
    for key, lim in expect.items():
        if key in sources:
            cur = [-x for x in wave[meta["sources"][key]["branch"]]] if key in meta["sources"] else zero
            peak, t = extreme(times, cur, max)
            s.check("LIM.i", key, "peak current from the supply", f"{peak:.4g} A at {t * 1e3:.4g} ms",
                    f"≤ {lim['i_max_a'] * 1e3:.4g} mA", peak <= lim["i_max_a"], source=f"expect of transients.{s.name}")
            continue
        for k, what, fn, sign in (("min_v", "lowest voltage", min, "≥"), ("max_v", "highest voltage", max, "≤")):
            if k not in lim:
                continue
            xs = volts(key, fn)
            if xs is None:
                s.check("SIM.config", key, what, "no element of the netlist on the net", f"{sign} {lim[k]} V", False)
                continue
            x, t = extreme(times, xs, fn)
            s.check("LIM.v", key, what, f"{x:.4g} V at {t * 1e3:.4g} ms", f"{sign} {lim[k]} V",
                    x >= lim[k] if fn is min else x <= lim[k], source=f"expect of transients.{s.name}")
    for des, m in meta["mcu"].items():
        r = limits(s.n.part(des))
        rating = "vin_min_v" if "vin_min_v" in r else "vsys_min_v" if "vsys_min_v" in r else None
        if rating is None or m["vin"] not in wave:
            continue
        xs, vmin = wave[m["vin"]], r[rating]
        what = f"lowest supply voltage once started ({rating})"
        start = next((i for i, x in enumerate(xs) if x >= vmin), None)
        if start is None:
            s.check("LIM.range", des, what, f"never reaches {vmin} V (highest {max(xs):.4g} V)", f"≥ {vmin} V", False,
                    source=f"{rating} of {s.n.entry_key(des)}")
            continue
        x, t = extreme(times, xs, min, start)
        s.check("LIM.range", des, what, f"{x:.4g} V at {t * 1e3:.4g} ms", f"≥ {vmin} V", x >= vmin,
                source=f"{rating} of {s.n.entry_key(des)}")
