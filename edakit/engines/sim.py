"""SIM: the simulation's quantities and states (concept rules-at-scale.md, sections 1 and 2). The simulation is a
producer: what ngspice found in a scenario becomes quantities – a part's voltages, currents, power, temperature, a
supply at a pin – that LIMITS judges against the limits of the parts entries (derated: catalog/tables/derating.toml,
sim.json derating), levels LEVELS judges against the thresholds, and states SIM judges against what the scenario
expects (LEDs on or dark, a regulator at its voltage, a diode blocking).

scenario(...) and transient(...) take what sim/run.py has after ngspice – the result, the netlist's meta – and give
the findings. `design` is the design the netlist was built from (its nodes and copper), `new` the same design in the
form of the restructuring (its limits and values).
"""

from __future__ import annotations

import math
from collections import defaultdict

from ..catalog import table
from ..circuit import limits, values
from ..findings import Finding
from ..sim import netlist
from .limits import judge_all
from .quantities import Limit, Quantity

DERATING = table("derating")["E"]
# (netlist element kind, quantity) -> the derating of sim.json / derating.toml [E.derate] that applies to its limit
DERATE = {"v": {"capacitor": "v_cap"}, "vr": {"diode": "v_diode"}, "vce": {"npn": "v_bjt", "pnp": "v_bjt"},
          "vds": {"nmos": "v_bjt", "pmos": "v_bjt"}, "vgs": {"nmos": "v_bjt", "pmos": "v_bjt"}}
DIM = {"p": "p", "i": "i", "if": "i", "ic": "i", "id": "i", "gpio_i": "i", "gpio_i_total": "i"}


def v(res, n):
    return 0.0 if n in (None, "0") else res.get(n, float("nan"))


class Scene:
    """One scenario's producer: its quantities and its direct findings."""

    def __init__(self, design, new, sim, res, meta, name, info=False):
        self.d, self.n, self.sim, self.res, self.meta, self.name, self.info = design, new, sim, res, meta, name, info
        self.der = {**DERATING["derate"], **sim.get("derating", {})}
        self.crit = {**DERATING["criteria"], **sim.get("criteria", {})}
        self.amb = sim.get("ambient_c", 25)
        self.qs, self.found = [], []

    def q(self, place, name, value, unit, kind="", des=None, how="", lo=None, code="", lims=(), color="", old="E-2",
          entry=True):
        """A quantity; its limits from the entry of `des` (by name, derated by kind) unless `entry` is False."""
        key = self.n.entry_key(des) if des and entry and des in self.n.comps else None
        dim = DIM.get(name) or DERATE.get(name, {}).get(kind)
        self.qs.append(Quantity(place, name, value, unit=unit, stage="E", lo=lo, how=how or name, kind=kind, entry=key,
                                scenario=self.name, code=code, on=(("component", des),) if des in self.n.comps else (),
                                old=old, limits=list(lims), color=color,
                                derate=self.der.get(dim, 1.0) if dim else 1.0))

    def fail(self, code, place, text, source="", old="E-3"):
        self.found.append(Finding(code, "E", place, text, source, scenario=self.name, old=old))

    def findings(self):
        out = judge_all(self.n, self.qs) + self.found
        for f in out:
            f.scenario = self.name
            if self.info:
                f.data["info"] = True
        return out


# --- E-2: stress --------------------------------------------------------------------------------------------------------
def stress(s):
    """Every part's voltages, currents, power and temperature against its entry's limits."""
    res, meta = s.res, s.meta
    for des, els in sorted(meta["elements"].items()):
        part = s.n.part(des) or {}
        r = limits(part)
        for el in els:
            nodes, kind = el["nodes"], el["kind"]
            i = None
            if "value" in el and kind != "capacitor":
                a, b = (v(res, x) for x in nodes[:2])
                i = (a - b) / el["value"]
            if kind in ("resistor", "pot"):
                s.q(des, "p", i * i * el["value"], "W", kind, des, "power dissipation")
            elif kind == "fuse" and "i_hold_a" in r:
                hold = r["i_hold_a"]
                tab = values(part).get("i_hold_vs_temp")
                if tab:
                    for (t0, h0), (t1, h1) in zip(tab, tab[1:]):
                        if t0 <= s.amb <= t1:
                            hold = h0 + (h1 - h0) * (s.amb - t0) / (t1 - t0)
                s.q(des, "i", abs(i), "A", kind, des, "current (hold current)", entry=False,
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
            elif kind in ("led", "diode"):
                a, k = (v(res, x) for x in nodes)
                cur = res.get(f"@{el['name']}[id]", float("nan"))
                info = meta["leds"].get(el["name"], {})
                label = el["name"][2:].upper()
                color = info.get("color") or ""
                rr = limits(part).get(color, r) if color else r
                if kind == "led" and "if_max_a" in rr:
                    s.q(label, "if", cur, "A", kind, des, "forward current", color=color)
                    s.q(label, "vr", max(k - a, 0), "V", "led", des, "reverse voltage", color=color)
                elif kind == "diode" and "if_max_a" in r:
                    s.q(des, "if", cur, "A", kind, des, "forward current")
                    s.q(des, "vr", max(k - a, 0), "V", kind, des, "reverse voltage")
            elif kind in ("npn", "pnp") and "ic_max_a" in r:
                c, b, e = (v(res, x) for x in nodes)
                ic, ib = res.get(f"@{el['name']}[ic]", 0.0), res.get(f"@{el['name']}[ib]", 0.0)
                vce, vbe = c - e, b - e
                s.q(des, "ic", abs(ic), "A", kind, des, "collector current")
                s.q(des, "vce", abs(vce), "V", kind, des, "|VCE|")
                s.q(des, "p", abs(vce * ic) + abs(vbe * ib), "W", kind, des, "power dissipation")
                rev = -vbe if kind == "npn" else vbe
                s.q(des, "veb", max(rev, 0), "V", kind, des, "base-emitter reverse voltage")
            elif kind in ("pmos", "nmos") and "id_max_a" in r:
                d_, g, src = (v(res, x) for x in nodes)
                cur = abs(res.get(f"@{el['name']}[id]", 0.0))
                vds, vgs = d_ - src, g - src
                s.q(des, "id", cur, "A", kind, des, "drain current")
                s.q(des, "vds", abs(vds), "V", kind, des, "|VDS|")
                s.q(des, "vgs", abs(vgs), "V", kind, des, "|VGS|")
                s.q(des, "p", abs(vds * cur), "W", kind, des, "power dissipation")
        from ..sim.run import dissipation
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
    return min(r.get("tj_max_c", math.inf), crit["tj_max_c"])


def junction(s, des, p, r, what=None, old="E-2"):
    """The junction temperature ambient + P × Rth(j-a) against the junction limit, and on a board people touch
    against the touch limit."""
    rth = r["rth_ja_k_per_w"]
    tj = s.amb + p * rth
    s.q(des, "tj", tj, "°C", "", des, what or f"junction temperature at {s.amb} °C: {p:.3g} W × {rth:g} K/W",
        entry=False, old=old, lims=[Limit(max=tj_limit(r, s.crit), source=f"tj_max_c of {s.n.entry_key(des)} "
                                          f"(at most the criteria's {s.crit['tj_max_c']:g} °C)")])
    touch(s, des, tj, "E-2")      # the touch limit was E-2's wherever the temperature came from


def touch(s, des, tj, old):
    board = (s.n.comps.get(des) or {}).get("board")
    lim = (s.sim.get("touch_c") or {}).get(board)
    if lim is not None:
        s.q(des, "tj", tj, "°C", "", des, f"temperature where people touch (board {board})", entry=False, old=old,
            lims=[Limit(max=lim, source=f"touch_c of sim.json for board {board}")])


# --- E-3, E-4: function -------------------------------------------------------------------------------------------------
def function(s, load, low=None, plugin_items=()):
    """What the circuit does in the scenario: supply currents, back-feed, regulators, MCU supply and levels, relays,
    operating ranges, thresholds, driver headroom, LEDs, blocking diodes, the declared net ranges."""
    from ..sim.run import at_pin, behind_resistor, ground_pin, led_on_output, ldo_power, supply_pins, threshold
    res, meta, crit, d = s.res, s.meta, s.crit, s.d
    for des, src in meta["sources"].items():
        i = -res.get(src["branch"], 0.0)
        if src.get("i_max_a"):
            s.q(des, "i", i, "A", "", des, "current from the supply", entry=False, old="E-3",
                lims=[Limit(max=src["i_max_a"], source=f"i_max_a of sources.{des} in sim.json")])
        if src.get("i_min_a"):
            what, i_on = "current that keeps the supply on", i
            if low:
                cores, res_low = low
                what += " (least current: " + ", ".join(f"{x} {c * 1e3:.3g} mA" for x, c in cores.items()) + ")"
                i_on = -res_low.get(src["branch"], 0.0)
            s.q(des, "i", None, "A", "", des, what, lo=i_on, entry=False, old="E-3",
                lims=[Limit(min=src["i_min_a"], source=f"i_min_a of sources.{des} in sim.json")])
    for des, src in meta["sources"].items():
        lim = s.sim.get("sources", {}).get(des, {}).get("i_back_max_a", crit["blocking_max_a"])
        i = max(res.get(src["branch"], 0.0), 0.0)
        s.q(des, "i", i, "A", "", des, "current into the supply (fed backwards)", code="LIM.backfeed", entry=False,
            old="E-3", lims=[Limit(max=lim, source=f"i_back_max_a of sources.{des} (default the criteria's "
                                                     "blocking_max_a)")])
    for name, cell in meta.get("cells", {}).items():
        lim = s.sim["cells"][cell["state"]].get("i_charge_max_a", crit["blocking_max_a"])
        i = max(res.get(cell["branch"], 0.0), 0.0)
        s.q(name, "i", i, "A", "", None, "current into the cell (charging)", code="LIM.backfeed", entry=False,
            old="E-3", lims=[Limit(max=lim, source=f"i_charge_max_a of cells.{cell['state']} in sim.json")])
    for des, reg in meta["regs"].items():
        r = limits(s.n.part(des))
        vin = v(res, reg["vin"]) - v(res, reg["gnd"])
        vout = v(res, reg["vout"]) - v(res, reg["gnd"])
        if not abs(vout - reg["vset"]) <= reg["vset"] * crit["rail_tol"]:
            s.fail("SIM.state", des, f"output voltage ({reg['kind']}) {vout:.4g} V, expected {reg['vset']} V ± "
                                     f"{crit['rail_tol']:.0%}")
        if des in meta["mcu"]:
            continue          # a module's own regulator: its supply and load below
        if "vin_min_v" in r:
            s.q(des, "vin", None, "V", "", des, "input voltage", lo=vin, code="LIM.range", entry=False, old="E-3",
                lims=[Limit(min=r["vin_min_v"], source=f"vin_min_v of {s.n.entry_key(des)}")])
        iout = max(res.get(reg["ammeter"], 0.0), 0.0)
        s.q(des, "i_out", iout, "A", "", des, "output current", old="E-3")
        if reg["kind"] == "ldo" and "rth_ja_k_per_w" in r:
            junction(s, des, ldo_power(res, reg), r, f"junction temperature at {s.amb} °C", "E-3")
    for des, m in meta["mcu"].items():
        r = limits(s.n.part(des))
        vin = v(res, m["vin"])
        vmin = r.get("vin_min_v", r.get("vsys_min_v"))
        reg = meta["regs"].get(des)
        if vmin is not None:
            s.q(des, "vsys", None, "V", "", des, "supply voltage", lo=vin, code="LIM.range", entry=False, old="E-3",
                lims=[Limit(min=vmin, source=f"vin_min_v or vsys_min_v of {s.n.entry_key(des)}")])
        if reg and "i_out_max_a" in r:
            s.q(des, "i_out", max(res.get(reg["ammeter"], 0.0), 0.0), "A", "", des, "load on the on-board regulator",
                old="E-3", entry=False, lims=[Limit(max=r["i_out_max_a"],
                                                    source=f"i_out_max_a of {s.n.entry_key(des)}")])
        if reg and reg["kind"] == "ldo" and "rth_ja_k_per_w" in r:
            heat, rth = ldo_power(res, reg), r["rth_ja_k_per_w"]
            junction(s, des, heat, r, f"junction temperature of the on-board regulator at {s.amb} °C: {heat:.3g} W × "
                                      f"{rth:g} K/W", "E-3")
        p = values(s.n.part(des))
        v_io = v(res, m["io_rail"]) if m.get("io_rail") else p.get("v_io_v", 3.3)
        vih = p.get("vih_v", p["vih_ratio"] * v_io if "vih_ratio" in p else None)
        vil = p.get("vil_v", p["vil_ratio"] * v_io if "vil_ratio" in p else None)
        for net in m.get("inputs", []) if vih is not None and vil is not None else []:
            x = v(res, m.get("input_nodes", {}).get(net) or netlist.node(net, d.ground))
            if not (x >= vih or x <= vil):
                s.fail("LVL.threshold", f"{des} {net}", f"input at {x:.4g} V between VIL {vil:.2f} V and VIH "
                                                        f"{vih:.2f} V", f"vil/vih of {s.n.entry_key(des)}")
        for net, pin in m.get("cannot_drive", []):
            s.fail("LVL.direction", f"{des} {net}", f"an output on {pin}, a pin that can only be an input")
    for des, rl in meta["relays"].items():
        p = values(s.n.part(des))
        a, b = rl["coil"]
        vc = abs(v(res, a) - v(res, b)) if a and b else 0.0
        if rl["on"] and "v_operate_v" in p:
            s.q(des, "v_coil_op", None, "V", "", des, "relay pulls in: coil voltage", lo=vc, code="LIM.range",
                entry=False, old="E-3", lims=[Limit(min=p["v_operate_v"], source=f"v_operate_v of "
                                                                                  f"{s.n.entry_key(des)}")])
        if not rl["on"] and "v_release_v" in p:
            s.q(des, "v_coil_rel", vc, "V", "", des, "relay releases: coil voltage", code="LIM.range", entry=False,
                old="E-3", lims=[Limit(max=p["v_release_v"], source=f"v_release_v of {s.n.entry_key(des)}")])
    for des in sorted(s.n.comps):
        part = s.n.part(des) or {}
        r = limits(part)
        if values(part).get("behavior") != "current" or not {"vin_min_v", "vin_max_v"} & set(r):
            continue
        ground = ground_pin(d, des, part)
        for num, info in part["pins"].items():
            if d.pin_net.get(f"{des}.{num}") and info.get("type") == "power_in":
                x = at_pin(d, res, f"{des}.{num}", ground)
                s.q(des, "vin", x, "V", "", des, f"supply voltage at {info.get('name', num)}", lo=x,
                    code="LIM.range", entry=False, old="E-3",
                    lims=[Limit(max=r.get("vin_max_v"), min=r.get("vin_min_v"),
                                source=f"vin_min_v … vin_max_v of {s.n.entry_key(des)}")])
    operating_range(s, at_pin, ground_pin, supply_pins)
    logic_levels(s, at_pin, ground_pin, supply_pins, threshold)

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
            knee = p.get("vout_knee_v", 0.6)
            s.q(f"{des} {net}", "v_out", None, "V", "", des, "output headroom", lo=vo, code="LIM.range", entry=False,
                old="E-3", lims=[Limit(min=knee, source=f"vout_knee_v of {s.n.entry_key(des)}")])
        if "rth_ja_k_per_w" in r:
            junction(s, des, pd, r, f"junction temperature at {s.amb} °C", "E-3")

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
            s.fail("SIM.state", label, f"LED reversed: its anode at the driver output {info['anode_net']}")
        elif leds_on is not None:
            on = leds_on == "all" or info["des"] in leds_on or label in leds_on
            if on and not i >= crit["led_on_min_a"]:
                s.fail("SIM.state", label, f"LED on: {i * 1e3:.3g} mA, at least {crit['led_on_min_a'] * 1e3:.2g} mA")
            elif not on and not i <= crit["led_off_max_a"]:
                s.fail("SIM.state", label, f"LED dark: {i * 1e6:.3g} µA, at most {crit['led_off_max_a'] * 1e6:.0f} µA")
        else:
            s.fail("SIM.driver", label, f"LED without a known driver: cathode at {info['cathode_net']}, on no driver "
                                        "output; the load has no leds_on", old="E-4")
    for name, info in meta["leds_left_out"].items():
        s.fail("SIM.driver", name[2:].upper(), "LED without a known driver: left out of the simulation, no pin with "
                                               f"the role {' or '.join(info['roles'])} in its parts entry", old="E-4")
    for key, leds in groups.items():
        net, on, iset = chan_of[key]
        if not on:
            for label, i in leds:
                if not i <= crit["led_off_max_a"]:
                    s.fail("SIM.state", label, f"LED dark: {i * 1e6:.3g} µA, at most "
                                               f"{crit['led_off_max_a'] * 1e6:.0f} µA")
            continue
        target = iset / len(leds)
        for label, i in leds:
            if not i >= crit["led_on_min_ratio"] * target:
                s.fail("SIM.state", label, f"LED current ({net}) {i * 1e3:.3g} mA, at least "
                                           f"{crit['led_on_min_ratio']:.0%} of {target * 1e3:.2f} mA")
        if len(leds) > 1:
            cur = [i for _, i in leds]
            ratio = min(cur) / (sum(cur) / len(cur)) if sum(cur) > 0 else 0
            if not ratio >= crit["chain_min_ratio"]:
                s.fail("SIM.state", net, f"parallel LEDs share the current {ratio:.0%} (min/mean), at least "
                                         f"{crit['chain_min_ratio']:.0%}")
    for des in s.sim.get("expect_blocking", []):
        i = res.get(f"@d_{des.lower()}[id]", 0.0)
        if not abs(i) <= crit["blocking_max_a"]:
            s.fail("SIM.state", des, f"diode blocks: {abs(i) * 1e3:.3g} mA through it, at most "
                                     f"{crit['blocking_max_a'] * 1e3:.0f} mA")
    tol, gnd = crit["net_range_tol_v"], d.ground
    for name, net in d.nets.items():
        g = v(res, netlist.node(netlist.local_ground(d, name), gnd))
        lo, hi = net.get("v", [0, 0])
        nodes = netlist.net_nodes(d, name)
        xs = [v(res, x) - g for x in nodes]
        s.q(name, "v_net", max(xs), "V", "", None, "net voltage", lo=min(xs), code="LIM.declared", entry=False,
            old="E-3", lims=[Limit(max=hi, min=lo, eps=tol, source=f"v of net {name} in the graph")])
    for item in plugin_items:
        if item["result"] == "fail":
            s.fail("SIM.state", item["item"], f"{item['check']}: {item['actual']} (expected {item['expected']})",
                   "the project's simulation plugin", old=item["id"])


def operating_range(s, at_pin, ground_pin, supply_pins):
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
            s.q(des, "v_op", x, "V", "", des, f"supply voltage at {part['pins'][num].get('name', num)}", lo=x,
                code="LIM.range", entry=False, old="E-3",
                lims=[Limit(max=hi, min=lo, source=f"operating range of {s.n.entry_key(des)}")])


def logic_levels(s, at_pin, ground_pin, supply_pins, threshold):
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
                s.fail("SIM.config", des, f"input thresholds as a ratio of the supply, but {len(nets)} supply nets "
                                          f"({', '.join(nets) or 'none'}), none with the role vdd or vcc")
                break
            net, name = d.pin_net[f"{des}.{num}"], info.get("name", num)
            x = at_pin(d, res, f"{des}.{num}", ground)
            if math.isnan(vil) or math.isnan(vih):
                continue
            reach[joined.get(net, net)].append((f"{des} {name}", vih))
            if math.isnan(x):
                continue
            if not (x >= vih or x <= vil):
                s.fail("LVL.threshold", f"{des} {net}", f"{name} at {x:.4g} V between VIL {vil:.2f} V and VIH "
                                                        f"{vih:.2f} V", f"vil/vih of {s.n.entry_key(des)}")
    for des, m in s.meta["mcu"].items():
        p = values(s.n.part(des))
        high = v(res, m["vin"]) if p.get("v_io_v") == "vin" else p.get("v_io_v", 3.3)
        for net in m.get("gpio_ammeters", {}):
            for who, vih in reach.get(joined.get(net, net), []):
                if not high >= vih:
                    s.fail("LVL.threshold", f"{des} {net}", f"output high {high:.4g} V below VIH {vih:.2f} V of {who}",
                           f"vih of {who.split()[0]}")


# --- E-5: transient runs ------------------------------------------------------------------------------------------------
def transient_findings(name, expect, sources, meta, times, wave, volts, extreme, info=False):
    """The limits of a run's expect and the MCU supply once started, from the waveforms of sim/run.py transient."""
    out = []

    def add(code, place, text, source="", old="E-5"):
        out.append(Finding(code, "E", place, text, source, scenario=name, old=old, data={"info": True} if info else {}))
    for key, lim in expect.items():
        if key in sources:
            cur = [-x for x in wave[meta["sources"][key]["branch"]]] if key in meta["sources"] else [0.0] * len(times)
            peak, t = extreme(times, cur, max)
            if peak > lim["i_max_a"]:
                add("LIM.i", key, f"peak current from the supply {peak:.4g} A at {t * 1e3:.4g} ms, at most "
                                  f"{lim['i_max_a'] * 1e3:.4g} mA", f"expect of transients.{name}")
            continue
        for k, what, fn in (("min_v", "lowest voltage", min), ("max_v", "highest voltage", max)):
            if k not in lim:
                continue
            xs = volts(key, fn)
            if xs is None:
                add("SIM.config", key, f"{what}: no element of the netlist on the net")
                continue
            x, t = extreme(times, xs, fn)
            if (x < lim[k]) if fn is min else (x > lim[k]):
                add("LIM.v", key, f"{what} {x:.4g} V at {t * 1e3:.4g} ms, {'at least' if fn is min else 'at most'} "
                                  f"{lim[k]} V", f"expect of transients.{name}")
    return out


def mcu_once_started(name, meta, new, wave, times, extreme, info=False):
    out = []
    for des, m in meta["mcu"].items():
        r = limits(new.part(des))
        rating = "vin_min_v" if "vin_min_v" in r else "vsys_min_v" if "vsys_min_v" in r else None
        if rating is None or m["vin"] not in wave:
            continue
        xs, vmin = wave[m["vin"]], r[rating]
        start = next((i for i, x in enumerate(xs) if x >= vmin), None)
        data = {"info": True} if info else {}
        if start is None:
            out.append(Finding("LIM.range", "E", des, f"supply never reaches {vmin} V (highest {max(xs):.4g} V)",
                               f"{rating} of {new.entry_key(des)}", scenario=name, old="E-5", data=data))
            continue
        x, t = extreme(times, xs, min, start)
        if x < vmin:
            out.append(Finding("LIM.range", "E", des, f"supply once started down to {x:.4g} V at {t * 1e3:.4g} ms, at "
                               f"least {vmin} V", f"{rating} of {new.entry_key(des)}", scenario=name, old="E-5",
                               data=data))
    return out
