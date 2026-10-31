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
from ..circuit import limits, polarized, values
from ..findings import Finding
from ..sim import netlist
from .limits import CODE, compare
from .quantities import Limit, Quantity, part_limits

DERATING = table("derating")["E"]
# (netlist element kind, quantity) -> the derating of sim.json / derating.toml [E.derate] that applies to its limit
DERATE = {"v": {"capacitor": "v_cap"}, "vr": {"diode": "v_diode"}, "vce": {"npn": "v_bjt", "pnp": "v_bjt"},
          "vds": {"nmos": "v_bjt", "pmos": "v_bjt"}, "vgs": {"nmos": "v_bjt", "pmos": "v_bjt"}}
DIM = {"p": "p", "i": "i", "if": "i", "ic": "i", "id": "i", "gpio_i": "i", "gpio_i_total": "i"}
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
            if kind in ("pmos", "nmos"):
                gate_drive(s, des, part, nodes)
        heat = [w for el in els if (w := dissipation(el, res)) is not None]
        if "rth_ja_k_per_w" in r and heat:
            junction(s, des, sum(heat), r)
    for des, m in meta["mcu"].items():
        r = limits(s.n.part(des))
        cur = {net: res.get(am, 0.0) for net, am in m.get("gpio_ammeters", {}).items()}
        for net, i in cur.items():
            s.q(f"{des} {net}", "gpio_i", abs(i), "A", "mcu", des, "GPIO output current")
        if "gpio_i_total_max_a" in r and cur:
            for what, i in (("sourced", sum(x for x in cur.values() if x > 0)),
                            ("sunk", -sum(x for x in cur.values() if x < 0))):
                s.q(des, "gpio_i_total", i, "A", "mcu", des, f"GPIO current {what} by all outputs together")


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
        lim = s.sim.get("sources", {}).get(des, {}).get("i_back_max_a", crit["blocking_max_a"])
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
        s.check("SIM.state", des, f"output voltage ({reg['kind']})", vout, f"{reg['vset']} V ± {crit['rail_tol']:.0%}",
                abs(vout - reg["vset"]) <= reg["vset"] * crit["rail_tol"], "V")
        if des in meta["mcu"]:
            continue          # a module's own regulator: its supply and load below
        if "vin_min_v" in r:
            s.q(des, "vin", None, "V", "", des, "input voltage", lo=vin, code="LIM.range", entry=False,
                lims=[Limit(min=r["vin_min_v"], source=f"vin_min_v of {s.n.entry_key(des)}")])
        s.q(des, "i_out", max(res.get(reg["ammeter"], 0.0), 0.0), "A", "", des, "output current")
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
    input_injection(s)
    adc_windows(s)
    switch_dc(s)
    supply_pin_currents(s)
    clocks(s)
    logic_levels(s)
    leds(s, load)
    for des in s.sim.get("expect_blocking", []):
        i = res.get(f"@d_{des.lower()}[id]", 0.0)
        s.check("SIM.state", des, "diode blocks", abs(i), f"≤ {crit['blocking_max_a'] * 1e3:.0f} mA",
                abs(i) <= crit["blocking_max_a"], "A")
    tol, gnd = crit["net_range_tol_v"], d.ground
    for name, net in d.nets.items():
        g = v(res, netlist.node(netlist.local_ground(d, name), gnd))
        lo, hi = net.get("v", [0, 0])
        nodes = netlist.net_nodes(d, name)
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
    vgs = abs(g - src)
    half = vth < vgs < spec
    s.check("LIM.range", des, "gate drive off or specified on", f"|VGS| {vgs:.3g} V" + (" – half on" if half else ""),
            f"≤ {vth:g} V (VGS(th)) or ≥ {spec:g} V (RDS(on) specified)", not half,
            source=f"vgs_th_v, rds_on_max_ohm of {s.n.entry_key(des)}", grade="gate", on=(("component", des),))


def input_injection(s):
    """LIM.v/inject: no input above its own part's supply by more than the entry allows (limits vin_rel_max_v) – the
    clamp diode conducts, the part is powered through its input or latches up."""
    d, res = s.d, s.res
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        rel = limits(part).get("vin_rel_max_v")
        pins = [n for n in supply_pins(part) if f"{des}.{n}" in d.pin_net]
        if rel is None or not pins:
            continue
        ground = ground_pin(d, des, part)
        vdd = at_pin(d, res, f"{des}.{pins[0]}", ground)
        for num, info in (part.get("pins") or {}).items():
            if info.get("type") != "input" or f"{des}.{num}" not in d.pin_net:
                continue
            x = at_pin(d, res, f"{des}.{num}", ground) - vdd
            s.q(f"{des}.{num}", "vin_rel", x, "V", "", des, f"input {info.get('name', num)} above its supply",
                code="LIM.v", entry=False, grade="inject",
                lims=[Limit(max=rel, source=f"vin_rel_max_v of {s.n.entry_key(des)}")])


SWITCH_DC_MAX_V = 0.01     # edakit's choice for "within a few mV" (maker-coverage CK-30), not a datasheet figure
CONTACT_KINDS = ("switch", "button", "dip_switch", "relay", "potentiometer")


def switch_dc(s):
    """REQ.value/switch: the contacts of a switch, button, relay or pot whose sides are both in a signal path (nets
    with signal or instrument) sit at one DC level in the scenario – a step across them is the pop when it switches
    and the scratch when a pot turns. A side no element reaches (nan) is LVL.undefined/analog's, not this check's."""
    d, res = s.d, s.res
    signal = {name for name, net in d.nets.items() if net.get("signal") or net.get("instrument")}
    if len(signal) < 2:
        return
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        kind = part.get("kind")
        if kind not in CONTACT_KINDS:
            continue
        on = {}
        for num, info in (part.get("pins") or {}).items():
            if kind == "relay" and info.get("role") not in ("common", "no", "nc"):
                continue
            net = d.pin_net.get(f"{des}.{num}")
            if net in signal:
                on.setdefault(net, num)
        if len(on) < 2:
            continue
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
            vil, vih = (threshold(p, info, k, vdd) for k in ("vil", "vih"))
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


def leds(s, load):
    """SIM.state of the LEDs: each LED of a driver channel at its share of the set current, parallel LEDs sharing it,
    an LED on or dark as the load says, none reversed; SIM.driver: an LED with no state to check; the driver's headroom
    and junction temperature."""
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
    for name, info in meta["leds"].items():
        i = res.get(f"@{name}[id]", float("nan"))
        label = name[2:].upper()
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
