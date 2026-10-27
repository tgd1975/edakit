"""Stage E (simulation): operating points of all scenarios with ngspice, stress and function checks.

    edakit sim [--json FILE] [--keep DIR]

Scenarios = supplies x loads x LED forward-voltage corners from the simulation config (edakit.toml [project] sim),
plus "extra_scenarios" listed there. "combine_sources" adds supplies for every combination of the sources it names:
each alone at both ends of its range, all together with one high and the others low (generated_supplies).
"transients" adds runs over time: the supplies follow [t, V] points (plug, unplug, a switch-over), ngspice .tran from
the operating point at t = 0, judged by E-5 only; without the key nothing runs.

  E-1  the operating point converges (a transient run: it runs to its end)
  E-2  stress of every part against the ratings in the parts database, with the derating from the config; MCU output
       current per pin (gpio_i_max_a) and of all outputs together (gpio_i_total_max_a); the junction temperature
       ambient + P x rth_ja_k_per_w of every part whose entry gives it, against its tj_max_c (at most the criteria's),
       and on a board of touch_c against the temperature people may touch
  E-3  function: supply currents, no supply fed backwards (sources: i_back_max_a, cells: i_charge_max_a, default the
       criteria's blocking_max_a), regulator outputs and headroom, MCU supply and input levels, MCU outputs only on
       pins that can drive, constant-current driver headroom and junction temperature, LED currents on/off as the load
       says (an LED behind a 0 Ω bridge counts on the driver output the bridge joins it to, an LED behind one resistor
       to a single driver output on that output – parallel LEDs with balancing resistors), relays pull in and release
       (v_operate, v_release), a module modelled as a constant current (an own board, part.py) supplied inside
       vin_min … vin_max, every part with an operating range (ratings vdd_op_min/vdd_op_max, pin v_op) supplied
       inside it, every input with thresholds (vih_*/vil_* on the pin or in the params) at a valid logic level and
       the high level of every MCU output reaching them, blocking diodes, every net inside its declared voltage range
       'v', plus the project plugin's own checks
  E-4  every LED – each colour of an RGB LED – has a state E-3 checks in every scenario: its cathode on a driver output
       (directly, behind 0 Ω bridges or behind a balancing resistor) or the load has leds_on; an LED with neither, or
       one the netlist left out because its parts entry lacks a role, fails as "LED without a known driver"
  E-5  transient limits: in every run of transients, each limit of its expect (a net's lowest voltage ≥ min_v, highest
       ≤ max_v, a source's peak current ≤ i_max_a), and every MCU supply pin, once it has reached its vin_min|vsys_min,
       never below it again

Rule, reason and fix of each check: rules.json (`edakit rules E-2`).

The largest current per net goes to <artifacts>/sim/net_currents.json – the input for the track widths
(`edakit pcb plan`, gate check L-5) –, the whole result with the hash of its inputs to <artifacts>/sim/result.json,
which values quoted from the simulation reuse while the inputs are unchanged (edakit docs, G-19). Exit code: 0 = all passed, 2 = at least one 'fail', 1 = tool error.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from . import copper, netlist

DEFAULT_DERATING = {"p": 0.5, "i": 0.8, "v_cap": 0.67, "v_diode": 0.67, "v_bjt": 0.67}
DEFAULT_CRITERIA = {"net_range_tol_v": 0.05, "led_on_min_a": 0.001, "led_on_min_ratio": 0.8, "led_off_max_a": 1e-5,
                    "chain_min_ratio": 0.7, "blocking_max_a": 0.001, "rail_tol": 0.03, "tj_max_c": 125}


class SimError(Exception):
    pass


def ngspice(text, keep=None, name="run"):
    if not shutil.which("ngspice"):
        raise SimError("ngspice not found – install it (Debian/Ubuntu: sudo apt install ngspice)")
    with tempfile.TemporaryDirectory() as tmp:
        cir = Path(keep or tmp) / (re.sub(r"[^\w.-]", "_", name) + ".cir")
        cir.write_text(text)
        res = subprocess.run(["ngspice", "-b", str(cir)], capture_output=True, text=True, timeout=120)
        if keep:
            cir.with_suffix(".log").write_text(res.stdout + res.stderr)
    values = {}
    for line in res.stdout.splitlines():
        m = re.match(r"^\s*(\S+)\s*=\s*(\S+)\s*$", line)
        if m:
            try:
                values[m.group(1).lower()] = float(m.group(2))
            except ValueError:
                pass
    if not values or any(math.isnan(v) for v in values.values()):
        raise SimError("operating point not found: " + " | ".join(
            line for line in (res.stdout + res.stderr).splitlines() if "rror" in line)[:300])
    return values


def ngspice_tran(text, data_file, keep=None, name="run"):
    """A transient netlist (netlist.build with tran) -> (times, columns): the rows ngspice wrote to `data_file` with
    wrdata, the first column the time, the others in the order of meta["tran"]["columns"]."""
    if not shutil.which("ngspice"):
        raise SimError("ngspice not found – install it (Debian/Ubuntu: sudo apt install ngspice)")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(keep or tmp)
        cir = d / (re.sub(r"[^\w.-]", "_", name) + ".cir")
        cir.write_text(text)
        res = subprocess.run(["ngspice", "-b", cir.name], cwd=d, capture_output=True, text=True, timeout=600)
        if keep:
            cir.with_suffix(".log").write_text(res.stdout + res.stderr)
        dat = d / data_file
        rows = []
        for line in (dat.read_text().splitlines()[1:] if dat.exists() else []):
            try:
                rows.append([float(x) for x in line.split()])
            except ValueError:
                pass
    if not rows or any(math.isnan(x) for r in rows for x in r):
        raise SimError("transient run failed: " + " | ".join(
            line for line in (res.stdout + res.stderr).splitlines() if "rror" in line or "too small" in line)[:300])
    return [r[0] for r in rows], [list(c) for c in zip(*(r[1:] for r in rows))]


class Checks:
    def __init__(self, scenario):
        self.sc, self.items = scenario, []

    def add(self, cid, item, what, actual, expected, ok, severity=None, unit=""):
        self.items.append({"id": cid, "scenario": self.sc, "item": item, "check": what,
                           "actual": actual if isinstance(actual, str) else f"{actual:.4g}{unit}",
                           "expected": expected, "result": severity or ("pass" if ok else "fail")})


def v(res, n):
    return 0.0 if n in (None, "0") else res.get(n, float("nan"))


def stress(design, cfg, res, meta, ck):
    der = {**DEFAULT_DERATING, **cfg.get("derating", {})}
    for des, els in sorted(meta["elements"].items()):
        part = design.part(des) or {}
        r = part.get("ratings", {})
        for el in els:
            nodes, kind = el["nodes"], el["kind"]
            i = None
            if "value" in el and kind != "capacitor":
                a, b = (v(res, n) for n in nodes[:2])
                i = (a - b) / el["value"]
            if kind in ("resistor", "pot") and "p_max_w" in r:
                p = i * i * el["value"]
                ck.add("E-2", des, "power dissipation", p, f"≤ {der['p'] * r['p_max_w']:.3g} W "
                       f"({der['p']:.0%} of {r['p_max_w']} W)", p <= der["p"] * r["p_max_w"], unit=" W")
            elif kind == "fuse" and "i_hold_a" in r:
                hold = r["i_hold_a"]
                table = part.get("params", {}).get("i_hold_vs_temp")
                if table:
                    ta = cfg.get("ambient_c", 25)
                    for (t0, h0), (t1, h1) in zip(table, table[1:]):
                        if t0 <= ta <= t1:
                            hold = h0 + (h1 - h0) * (ta - t0) / (t1 - t0)
                ck.add("E-2", des, "current (derated hold current)", abs(i), f"≤ {der['i'] * hold:.3g} A",
                       abs(i) <= der["i"] * hold, unit=" A")
            elif kind in ("switch", "connector", "source") and "i_max_a" in r and i is not None:
                ck.add("E-2", des, "contact current", abs(i), f"≤ {der['i'] * r['i_max_a']:.3g} A",
                       abs(i) <= der["i"] * r["i_max_a"], unit=" A")
            elif kind == "load" and "i_max_a" in r:
                ck.add("E-2", des, "contact current (external load)", el["i"], f"≤ {der['i'] * r['i_max_a']:.3g} A",
                       el["i"] <= der["i"] * r["i_max_a"], unit=" A")
            elif kind == "inductor" and "i_rated_a" in r:
                ck.add("E-2", des, "average current", abs(i), f"≤ {der['i'] * r['i_rated_a']:.3g} A",
                       abs(i) <= der["i"] * r["i_rated_a"], unit=" A")
            elif kind == "buzzer" and "v_max" in r:
                ck.add("E-2", des, "coil voltage", abs(a - b), f"≤ {r['v_max']} V", abs(a - b) <= r["v_max"], unit=" V")
            elif kind == "relay_coil" and "v_coil_max" in r:
                ck.add("E-2", des, "coil voltage", abs(a - b), f"≤ {r['v_coil_max']} V", abs(a - b) <= r["v_coil_max"],
                       unit=" V")
            elif kind == "capacitor" and "v_max" in r:
                a, b = (v(res, n) for n in nodes)
                lim = der["v_cap"] * r["v_max"]
                ck.add("E-2", des, "DC voltage", abs(a - b), f"≤ {lim:.3g} V", abs(a - b) <= lim, unit=" V")
            elif kind in ("led", "diode"):
                a, k = (v(res, n) for n in nodes)
                i = res.get(f"@{el['name']}[id]", float("nan"))
                info = meta["leds"].get(el["name"], {})
                rr = r.get(info["color"], r) if info.get("color") else r
                label = el["name"][2:].upper()
                if kind == "led" and "if_max_a" in rr:
                    ck.add("E-2", label, "forward current", i, f"≤ {der['i'] * rr['if_max_a'] * 1e3:.3g} mA",
                           i <= der["i"] * rr["if_max_a"], unit=" A")
                    if "vr_max" in rr:
                        ck.add("E-2", label, "reverse voltage", max(k - a, 0), f"≤ {rr['vr_max']} V",
                               k - a <= rr["vr_max"], unit=" V")
                elif kind == "diode" and "if_avg_a" in r:
                    ck.add("E-2", des, "forward current", i, f"≤ {der['i'] * r['if_avg_a']:.3g} A",
                           i <= der["i"] * r["if_avg_a"], unit=" A")
                    ck.add("E-2", des, "reverse voltage", max(k - a, 0), f"≤ {der['v_diode'] * r['vrrm']:.3g} V",
                           k - a <= der["v_diode"] * r["vrrm"], unit=" V")
            elif kind in ("npn", "pnp") and "ic_max_a" in r:
                c, b, e = (v(res, n) for n in nodes)
                ic, ib = res.get(f"@{el['name']}[ic]", 0.0), res.get(f"@{el['name']}[ib]", 0.0)
                vce, vbe = c - e, b - e
                p = abs(vce * ic) + abs(vbe * ib)
                ck.add("E-2", des, "collector current", abs(ic), f"≤ {der['i'] * r['ic_max_a']:.3g} A",
                       abs(ic) <= der["i"] * r["ic_max_a"], unit=" A")
                ck.add("E-2", des, "|VCE|", abs(vce), f"≤ {der['v_bjt'] * r['vceo']:.3g} V",
                       abs(vce) <= der["v_bjt"] * r["vceo"], unit=" V")
                if "p_max_w" in r:
                    ck.add("E-2", des, "power dissipation", p, f"≤ {der['p'] * r['p_max_w']:.3g} W",
                           p <= der["p"] * r["p_max_w"], unit=" W")
                if "vebo" in r:
                    rev = -vbe if kind == "npn" else vbe
                    ck.add("E-2", des, "base-emitter reverse voltage", max(rev, 0), f"≤ {r['vebo']} V",
                           rev <= r["vebo"], unit=" V")
            elif kind in ("pmos", "nmos") and "id_max_a" in r:
                d_, g, s = (v(res, n) for n in nodes)
                i = abs(res.get(f"@{el['name']}[id]", 0.0))
                vds, vgs = d_ - s, g - s
                ck.add("E-2", des, "drain current", i, f"≤ {der['i'] * r['id_max_a']:.3g} A",
                       i <= der["i"] * r["id_max_a"], unit=" A")
                ck.add("E-2", des, "|VDS|", abs(vds), f"≤ {der['v_bjt'] * r['vds_max']:.3g} V",
                       abs(vds) <= der["v_bjt"] * r["vds_max"], unit=" V")
                ck.add("E-2", des, "|VGS|", abs(vgs), f"≤ {der['v_bjt'] * r['vgs_max']:.3g} V",
                       abs(vgs) <= der["v_bjt"] * r["vgs_max"], unit=" V")
                if "p_max_w" in r:
                    ck.add("E-2", des, "power dissipation", abs(vds * i), f"≤ {der['p'] * r['p_max_w']:.3g} W",
                           abs(vds * i) <= der["p"] * r["p_max_w"], unit=" W")
        heat = [w for el in els if (w := dissipation(el, res)) is not None]
        if "rth_ja_k_per_w" in r and heat:   # one package: the power of all its elements
            junction(design, cfg, des, sum(heat), r, ck)
    for des, m in meta["mcu"].items():  # MCU outputs: every pin, and all of them through the package's supply pins
        r = m["ratings"]
        cur = {net: res.get(am, 0.0) for net, am in m.get("gpio_ammeters", {}).items()}  # > 0: sourced, < 0: sunk
        if "gpio_i_max_a" in r:
            lim = der["i"] * r["gpio_i_max_a"]
            for net, i in cur.items():
                ck.add("E-2", f"{des} {net}", "GPIO output current", abs(i), f"≤ {lim * 1e3:.3g} mA", abs(i) <= lim,
                       unit=" A")
        if "gpio_i_total_max_a" in r and cur:
            lim = der["i"] * r["gpio_i_total_max_a"]
            for what, i in (("sourced", sum(x for x in cur.values() if x > 0)),
                            ("sunk", -sum(x for x in cur.values() if x < 0))):
                ck.add("E-2", des, f"GPIO current {what} by all outputs together", i, f"≤ {lim * 1e3:.3g} mA",
                       i <= lim, unit=" A")


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


def tj_limit(ratings, crit):
    """Junction limit of a part: its own tj_max_c, the criteria's tj_max_c where that is lower or the part has none."""
    return min(ratings.get("tj_max_c", math.inf), crit["tj_max_c"])


def junction(design, cfg, des, p, r, ck):
    """E-2: ambient + P x Rth(j-a) of a part whose entry gives rth_ja_k_per_w stays at or below its junction limit, and
    on a board people touch at or below the touch limit (touch)."""
    crit = {**DEFAULT_CRITERIA, **cfg.get("criteria", {})}
    amb, rth = cfg.get("ambient_c", 25), r["rth_ja_k_per_w"]
    tj, lim = amb + p * rth, tj_limit(r, crit)
    ck.add("E-2", des, f"junction temperature at {amb} °C: {p:.3g} W × {rth:g} K/W", tj, f"≤ {lim:g} °C", tj <= lim,
           unit=" °C")
    touch(design, cfg, des, tj, ck)


def touch(design, cfg, des, tj, ck):
    """E-2: on a board of touch_c – a board people reach – a part's junction temperature, the upper bound of its
    surface, stays at or below the limit the product's standard sets for that surface and contact time."""
    board = (design.comps.get(des) or {}).get("board")
    lim = (cfg.get("touch_c") or {}).get(board)
    if lim is not None:
        ck.add("E-2", des, f"temperature where people touch (board {board})", tj, f"≤ {lim:g} °C", tj <= lim,
               unit=" °C")


def touch_limits(design, sim):
    """touch_c of the simulation config: {board: °C}, every key a board of the project."""
    touch_c = sim.get("touch_c", {})
    if not isinstance(touch_c, dict) or not all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in touch_c.values()):
        raise SimError(f"touch_c: a map from each board people touch to its limit in °C expected, not {touch_c!r}")
    for board in touch_c:
        if design.boards and board not in design.boards:
            raise SimError(f"touch_c: {board} is no board of the project (boards: {', '.join(design.boards)})")
    return touch_c


def reg_input_current(res, reg):
    """Current a regulator model draws from its input (the same expression as its B-source, lockout included)."""
    iout = max(res.get(reg["ammeter"], 0.0), 0.0)
    p = reg["params"]
    vin = v(res, reg["vin"]) - v(res, reg["gnd"])
    on = 1.0 if reg.get("vin_min") is None else min(1.0, max(vin - reg["vin_min"] + netlist.UVLO_V, 0) / netlist.UVLO_V)
    if reg["kind"] == "ldo":
        return on * (iout + p.get("iq_a", 0.0) + reg["extra_i"])
    return on * (reg["vset"] * (iout + reg["extra_i"]) / (p.get("efficiency", 0.85) * max(vin, 0.3)) + p.get("iq_a", 0.0))


def behind_resistor(design, joined, outputs):
    """{net: driver output} for every net that one resistor (not a 0 Ω bridge) joins to exactly one of `outputs` – the
    cathode net of an LED behind its balancing resistor, when several LEDs share a channel. Nets as the bridges join
    them (`joined`); the ground is never behind an output, a net that reaches two outputs belongs to neither."""
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
    """How E-3/E-4 trace one LED (one colour) to a driver output, its nets as the bridges join them: (output, "cathode")
    when its cathode is on it – directly or behind its balancing resistor (`behind`, behind_resistor) –, (output,
    "anode") when its anode is on it directly (the LED is reversed), else None. edakit firmware traces channels so."""
    if cathode in outputs:
        return cathode, "cathode"
    if anode in outputs:
        return anode, "anode"
    if cathode in behind:
        return behind[cathode], "cathode"
    return None


def functional(design, cfg, res, meta, load, ck, plugin):
    crit = {**DEFAULT_CRITERIA, **cfg.get("criteria", {})}
    amb = cfg.get("ambient_c", 25)
    for des, s in meta["sources"].items():
        i = -res.get(s["branch"], 0.0)
        if s.get("i_max_a"):
            ck.add("E-3", des, "current from the supply", i, f"≤ {s['i_max_a'] * 1e3:.0f} mA", i <= s["i_max_a"], unit=" A")
        else:
            ck.add("E-3", des, "current from the supply", i, "information", True, "info", unit=" A")
        if s.get("i_min_a"):  # power banks switch off below a minimum load
            ck.add("E-3", des, "current keeps the supply on", i, f"≥ {s['i_min_a'] * 1e3:.0f} mA", i >= s["i_min_a"],
                   unit=" A")
    back_feed(cfg, res, meta, crit, ck)
    for des, reg in meta["regs"].items():
        vin = v(res, reg["vin"]) - v(res, reg["gnd"])
        vout = v(res, reg["vout"]) - v(res, reg["gnd"])
        ck.add("E-3", des, f"output voltage ({reg['kind']})", vout, f"{reg['vset']} V ± {crit['rail_tol']:.0%}",
               abs(vout - reg["vset"]) <= reg["vset"] * crit["rail_tol"], unit=" V")
        r = reg.get("ratings", {})
        if "vin_min" in r:
            ck.add("E-3", des, "input voltage", vin, f"≥ {r['vin_min']} V", vin >= r["vin_min"], unit=" V")
        iout = max(res.get(reg["ammeter"], 0.0), 0.0)
        if "i_out_max_a" in r:
            ck.add("E-3", des, "output current", iout, f"≤ {r['i_out_max_a'] * 1e3:.0f} mA", iout <= r["i_out_max_a"],
                   unit=" A")
        if reg["kind"] == "ldo" and "rth_ja_k_per_w" in r:
            tj, lim = amb + (vin - vout) * iout * r["rth_ja_k_per_w"], tj_limit(r, crit)
            ck.add("E-3", des, f"junction temperature at {amb} °C", tj, f"≤ {lim:g} °C", tj <= lim, unit=" °C")
            touch(design, cfg, des, tj, ck)
    for des, m in meta["mcu"].items():
        r = m["ratings"]
        vin = v(res, m["vin"])
        vmin = r.get("vin_min", r.get("vsys_min"))
        if vmin is not None:
            ck.add("E-3", des, "supply voltage", vin, f"≥ {vmin} V", vin >= vmin, unit=" V")
        reg = meta["regs"].get(des)
        lim = r.get("i_out_max_a", r.get("i_3v3_ext_max_a"))
        if reg and lim is not None:
            iout = max(res.get(reg["ammeter"], 0.0), 0.0)
            ck.add("E-3", des, "load on the on-board regulator", iout, f"≤ {lim * 1e3:.0f} mA", iout <= lim, unit=" A")
        p = m["params"]
        v_io = v(res, m["io_rail"]) if m.get("io_rail") else p.get("v_io", 3.3)
        vih = p.get("vih_v", p["vih_ratio"] * v_io if "vih_ratio" in p else None)
        vil = p.get("vil_v", p["vil_ratio"] * v_io if "vil_ratio" in p else None)
        for net in m.get("inputs", []) if vih is not None and vil is not None else []:
            x = v(res, m.get("input_nodes", {}).get(net) or netlist.node(net, design.ground))
            level = "high" if x >= vih else "low" if x <= vil else "undefined"
            ck.add("E-3", f"{des} {net}", f"input level {level} (VIL {vil:.2f} V, VIH {vih:.2f} V)", x,
                   f"≤ {vil:.2f} V or ≥ {vih:.2f} V", level != "undefined", unit=" V")
        for net, pin in m.get("cannot_drive", []):
            ck.add("E-3", f"{des} {net}", f"output on {pin}, a pin that can only be an input", "input only",
                   "a pin that can drive (output or bidirectional)", False)
    for des, rl in meta["relays"].items():
        p = (design.part(des) or {}).get("params", {})
        a, b = rl["coil"]
        vc = abs(v(res, a) - v(res, b)) if a and b else 0.0
        if rl["on"] and "v_operate" in p:
            ck.add("E-3", des, "relay pulls in: coil voltage ≥ must-operate voltage", vc, f"≥ {p['v_operate']} V",
                   vc >= p["v_operate"], unit=" V")
        if not rl["on"] and "v_release" in p:
            ck.add("E-3", des, "relay releases: coil voltage ≤ must-release voltage", vc, f"≤ {p['v_release']} V",
                   vc <= p["v_release"], unit=" V")
    for des in sorted(design.comps):   # a module modelled as a constant current – an own board – inside its range
        p = design.part(des) or {}
        r = p.get("ratings") or {}
        if (p.get("params") or {}).get("behavior") != "current" or not {"vin_min", "vin_max"} & set(r):
            continue
        lo, hi = r.get("vin_min", -math.inf), r.get("vin_max", math.inf)
        want = f"{lo} … {hi} V" if {"vin_min", "vin_max"} <= set(r) else f"≥ {lo} V" if "vin_min" in r else f"≤ {hi} V"
        ground = ground_pin(design, des, p)
        for num, info in p["pins"].items():
            net = design.pin_net.get(f"{des}.{num}")
            if net and info.get("type") == "power_in":
                x = at_pin(design, res, f"{des}.{num}", ground)
                ck.add("E-3", des, f"supply voltage at {info.get('name', num)} within vin_min … vin_max", x, want,
                       lo <= x <= hi, unit=" V")
    operating_range(design, res, ck)
    logic_levels(design, res, meta, ck)

    joined = design.joined_nets()   # nets joined by 0 Ω bridges: an LED behind a bridge is on the driver output
    chan_of = {}
    for des, t in meta["cc"].items():
        p, r = t["params"], t["ratings"]
        iset = p["iout_gain"] * -res.get(t["rext_src"], 0.0)
        t["iset"] = iset
        pd = v(res, t["vdd"]) * p.get("idd_max_a", 0.0) if t["vdd"] else 0.0
        for net, ch in t["channels"].items():
            chan_of[joined.get(net, net)] = (net, ch["on"], iset)
            if not ch["on"]:
                continue
            vo, io = v(res, ch["node"]), res.get(ch["ammeter"], 0.0)
            pd += vo * io
            ck.add("E-3", f"{des} {net}", "output headroom", vo, f"≥ {p.get('vout_knee_v', 0.6)} V",
                   vo >= p.get("vout_knee_v", 0.6), unit=" V")
        if "rth_ja_k_per_w" in r:
            tj, lim = amb + pd * r["rth_ja_k_per_w"], tj_limit(r, crit)
            ck.add("E-3", des, f"junction temperature at {amb} °C", tj, f"≤ {lim:g} °C", tj <= lim, unit=" °C")
            touch(design, cfg, des, tj, ck)

    leds_on = load.get("leds_on")
    groups = defaultdict(list)
    behind = behind_resistor(design, joined, chan_of)   # LEDs in parallel on one channel, each behind its resistor
    for name, info in meta["leds"].items():
        i = res.get(f"@{name}[id]", float("nan"))
        label = name[2:].upper()
        cathode, anode = (joined.get(info[k], info[k]) for k in ("cathode_net", "anode_net"))
        hit = led_on_output(chan_of, behind, anode, cathode)
        if hit and hit[1] == "cathode":
            groups[hit[0]].append((label, i))
        elif hit:
            ck.add("E-3", label, f"LED reversed (anode at the driver output {info['anode_net']})", i,
                   "cathode at the driver output", False, unit=" A")
        elif leds_on is not None:
            on = leds_on == "all" or info["des"] in leds_on or label in leds_on
            if on:
                ck.add("E-3", label, "LED on", i, f"≥ {crit['led_on_min_a'] * 1e3:.2g} mA", i >= crit["led_on_min_a"],
                       unit=" A")
            else:
                ck.add("E-3", label, "LED dark", i, f"≤ {crit['led_off_max_a'] * 1e6:.0f} µA",
                       i <= crit["led_off_max_a"], unit=" A")
        else:   # neither polarity nor current would be checked, and the run would pass without a word
            ck.add("E-4", label, "LED without a known driver", f"cathode at {info['cathode_net']}, on no driver output;"
                   " the load has no leds_on", "the cathode on a driver output, or the load's leds_on", False)
    for name, info in meta["leds_left_out"].items():
        ck.add("E-4", name[2:].upper(), "LED without a known driver", "left out of the simulation: no pin with the "
               f"role {' or '.join(info['roles'])} in its parts entry", "the roles the simulation reads (handbook 4.1)",
               False)
    for key, leds in groups.items():
        net, on, iset = chan_of[key]
        if not on:
            for label, i in leds:
                ck.add("E-3", label, "LED dark", i, f"≤ {crit['led_off_max_a'] * 1e6:.0f} µA",
                       i <= crit["led_off_max_a"], unit=" A")
            continue
        target = iset / len(leds)
        for label, i in leds:
            ck.add("E-3", label, f"LED current ({net})", i, f"≥ {crit['led_on_min_ratio']:.0%} of {target * 1e3:.2f} mA",
                   i >= crit["led_on_min_ratio"] * target, unit=" A")
        if len(leds) > 1:
            cur = [i for _, i in leds]
            ratio = min(cur) / (sum(cur) / len(cur)) if sum(cur) > 0 else 0
            ck.add("E-3", net, "current sharing of parallel LEDs (min/mean)", ratio,
                   f"≥ {crit['chain_min_ratio']:.0%}", ratio >= crit["chain_min_ratio"])

    for des in cfg.get("expect_blocking", []):
        i = res.get(f"@d_{des.lower()}[id]", 0.0)
        ck.add("E-3", des, "diode blocks", abs(i), f"≤ {crit['blocking_max_a'] * 1e3:.0f} mA",
               abs(i) <= crit["blocking_max_a"], unit=" A")

    tol = crit["net_range_tol_v"]
    gnd = design.ground
    for name, net in design.nets.items():
        g = v(res, netlist.node(netlist.local_ground(design, name), gnd))
        lo, hi = net.get("v", [0, 0])
        nodes = netlist.net_nodes(design, name)
        if len(nodes) == 1:
            x = v(res, nodes[0]) - g
            ck.add("E-3", name, "net voltage inside the declared range", x, f"{lo} … {hi} V", lo - tol <= x <= hi + tol,
                   unit=" V")
            continue
        pin_at = {netlist.pin_node(design, ref): ref for ref in reversed(net["pins"])}   # the routed copper: every pin
        (x_lo, n_lo), (x_hi, n_hi) = min(xs := [(v(res, n) - g, n) for n in nodes]), max(xs)
        ck.add("E-3", name, "net voltage inside the declared range",
               f"{x_lo:.4g} V ({pin_at[n_lo]}) … {x_hi:.4g} V ({pin_at[n_hi]})", f"{lo} … {hi} V",
               lo - tol <= x_lo and x_hi <= hi + tol)
    if plugin and hasattr(plugin, "checks"):
        plugin.checks(design=design, cfg=cfg, res=res, meta=meta, load=load, add=ck.add)


def back_feed(cfg, res, meta, crit, ck):
    """E-3: no supply is fed backwards. The current into a source of `sources` – against its direction – stays at or
    below its i_back_max_a, the current into each cell of a battery holder at or below the i_charge_max_a of its cell
    state; both are the criteria's blocking_max_a (1 mA) unless set. Where two supplies meet, the higher one feeds the
    lower one wherever nothing blocks the way: into a PC's USB port, into a primary cell."""
    for des, s in meta["sources"].items():
        lim = cfg.get("sources", {}).get(des, {}).get("i_back_max_a", crit["blocking_max_a"])
        i = res.get(s["branch"], 0.0)                 # ngspice: > 0 flows into the source's plus terminal
        i = i if i > 0 else 0.0
        ck.add("E-3", des, "current into the supply (fed backwards)", i, f"≤ {lim * 1e3:.3g} mA", i <= lim, unit=" A")
    for name, cell in meta.get("cells", {}).items():
        lim = cfg["cells"][cell["state"]].get("i_charge_max_a", crit["blocking_max_a"])
        i = res.get(cell["branch"], 0.0)
        i = i if i > 0 else 0.0
        ck.add("E-3", name, "current into the cell (charging)", i, f"≤ {lim * 1e3:.3g} mA", i <= lim, unit=" A")


SUPPLY_ROLES = ("vdd", "vcc")


def supply_pins(part):
    """The supply pins of a part: its power_in pins with the role vdd or vcc, else all of its power_in pins."""
    pins = {n: i for n, i in (part.get("pins") or {}).items() if i.get("type") == "power_in"}
    return {n: i for n, i in pins.items() if i.get("role") in SUPPLY_ROLES} or pins


def ground_pin(design, des, part):
    """The part's first connected ground pin ('U2.1') – what its supply and its input levels are measured against;
    None without one (the ground net)."""
    return next((f"{des}.{n}" for n, i in (part.get("pins") or {}).items()
                 if i.get("type") == "ground" and f"{des}.{n}" in design.pin_net), None)


def at_pin(design, res, ref, ground=None):
    """Voltage at a pin – on its pad node where the copper of its net is simulated – against a ground pin (None: the
    ground net); nan for a node no element of the netlist reaches."""
    return v(res, netlist.pin_node(design, ref)) - (v(res, netlist.pin_node(design, ground)) if ground else 0.0)


def operating_range(design, res, ck):
    """E-3: a part with an operating supply range – ratings vdd_op_min/vdd_op_max for its supply pins, or v_op
    [min, max] on a pin of its own – is supplied inside it, measured to its own ground pin. Absolute maxima are G-3's;
    this is the range in which the part works."""
    for des in sorted(design.comps):
        part = design.part(des) or {}
        r = part.get("ratings") or {}
        ranges = {n: (r.get("vdd_op_min"), r.get("vdd_op_max")) for n in supply_pins(part)}
        ranges.update({n: tuple(i["v_op"]) for n, i in (part.get("pins") or {}).items() if i.get("v_op")})
        ground, seen = ground_pin(design, des, part), set()
        for num, (lo, hi) in ranges.items():
            net = design.pin_net.get(f"{des}.{num}")
            if net is None or (lo is None and hi is None) or (net, lo, hi) in seen:
                continue
            seen.add((net, lo, hi))
            x = at_pin(design, res, f"{des}.{num}", ground)
            if math.isnan(x):
                continue
            want = f"{lo} … {hi} V" if lo is not None and hi is not None else f"≥ {lo} V" if hi is None else f"≤ {hi} V"
            ok = (lo is None or x >= lo) and (hi is None or x <= hi)
            ck.add("E-3", des, f"supply voltage at {part['pins'][num].get('name', num)} inside its operating range", x,
                   want, ok, unit=" V")


def threshold(params, pin, kind, vdd):
    """VIL or VIH (`kind` 'vil'|'vih') of an input pin: the pin's own kind_v|kind_ratio, else the part's params; a ratio
    is taken of the supply `vdd` (None: no single supply)."""
    for src in (pin, params):
        if f"{kind}_v" in src:
            return src[f"{kind}_v"]
        if f"{kind}_ratio" in src:
            return None if vdd is None else src[f"{kind}_ratio"] * vdd
    return None


def logic_levels(design, res, meta, ck):
    """E-3: every input pin (type input) with thresholds – vih_v|vih_ratio and vil_v|vil_ratio on the pin or in the
    part's params – sits at ≤ VIL or ≥ VIH, a ratio taken of the voltage at the part's supply pin; and the high level
    of every MCU output on its net (behind 0 Ω bridges too) reaches VIH, whatever the load drives. An MCU's own inputs
    go by the config's `inputs` (functional)."""
    joined = design.joined_nets()
    reach = defaultdict(list)                     # net -> (input, VIH) on it
    for des in sorted(design.comps):
        part = design.part(des) or {}
        p = part.get("params") or {}
        if p.get("behavior") == "mcu":
            continue
        inputs = [(n, i) for n, i in (part.get("pins") or {}).items() if i.get("type") == "input"
                  and f"{des}.{n}" in design.pin_net and all(any(f"{k}_{x}" in s for s in (i, p) for x in ("v", "ratio"))
                                                             for k in ("vil", "vih"))]
        if not inputs:
            continue
        ground = ground_pin(design, des, part)
        on = sorted((design.pin_net[f"{des}.{n}"], f"{des}.{n}") for n in supply_pins(part) if f"{des}.{n}" in design.pin_net)
        nets = sorted({net for net, _ in on})
        vdd = at_pin(design, res, on[0][1], ground) if len(nets) == 1 else None
        for num, info in inputs:
            vil, vih = (threshold(p, info, k, vdd) for k in ("vil", "vih"))
            if vil is None or vih is None:
                ck.add("E-3", des, "input thresholds as a ratio of the supply",
                       f"{len(nets)} supply nets ({', '.join(nets) or 'none'}), none with the role vdd or vcc",
                       "one supply pin: a power_in pin with the role vdd or vcc", False)
                break
            net, name = design.pin_net[f"{des}.{num}"], info.get("name", num)
            x = at_pin(design, res, f"{des}.{num}", ground)
            if math.isnan(vil) or math.isnan(vih):
                continue
            reach[joined.get(net, net)].append((f"{des} {name}", vih))
            if math.isnan(x):
                continue
            level = "high" if x >= vih else "low" if x <= vil else "undefined"
            ck.add("E-3", f"{des} {net}", f"input level {level} at {name} (VIL {vil:.2f} V, VIH {vih:.2f} V)", x,
                   f"≤ {vil:.2f} V or ≥ {vih:.2f} V", level != "undefined", unit=" V")
    for des, m in meta["mcu"].items():
        p = m["params"]
        high = v(res, m["vin"]) if p.get("v_io") == "vin" else p.get("v_io", 3.3)
        for net in m.get("gpio_ammeters", {}):
            for who, vih in reach.get(joined.get(net, net), []):
                ck.add("E-3", f"{des} {net}", f"output high level reaches VIH of {who}", high, f"≥ {vih:.2f} V",
                       high >= vih, unit=" V")


def net_currents(design, res, meta):
    """Largest current of a single part per net – a measure for the main trunk of a track."""
    gnd = design.ground
    net_of_node = {netlist.node(n, gnd): n for n in set(design.pin_net.values())}
    net_of_node.update((getattr(design, "copper", None) or {}).get("node_net", {}))   # pad nodes of the routed copper
    cur = defaultdict(float)

    def put(nodes, i):
        for n in nodes:
            net = net_of_node.get(n)
            if net:
                cur[net] = max(cur[net], abs(i))
    for els in meta["elements"].values():
        for el in els:
            if el["kind"] == "capacitor":
                continue
            if "value" in el:
                put(el["nodes"][:2], (v(res, el["nodes"][0]) - v(res, el["nodes"][1])) / el["value"])
            elif el["kind"] in ("led", "diode"):
                put(el["nodes"], res.get(f"@{el['name']}[id]", 0.0))
            elif el["kind"] == "load":
                put(el["nodes"], el["i"])
            elif el["kind"] in ("npn", "pnp"):
                ic, ib = res.get(f"@{el['name']}[ic]", 0.0), res.get(f"@{el['name']}[ib]", 0.0)
                put([el["nodes"][0], el["nodes"][2]], ic)
                put([el["nodes"][1]], ib)
            elif el["kind"] in ("pmos", "nmos"):
                put([el["nodes"][0], el["nodes"][2]], res.get(f"@{el['name']}[id]", 0.0))
    for s in meta["sources"].values():  # the supply current returns through ground: the trunk of the GND net
        put(s["nodes"], -res.get(s["branch"], 0.0))
    for t in meta["cc"].values():
        for ch in t["channels"].values():
            if ch["on"]:
                put([ch["node"]], res.get(ch["ammeter"], 0.0))
    for des, reg in meta["regs"].items():
        put([reg["vout"]], res.get(reg["ammeter"], 0.0))
        put([reg["vin"]], reg_input_current(res, reg))
    for des, m in meta["mcu"].items():
        if des not in meta["regs"] and m["vin"]:
            put([m["vin"]], m["params"].get("i_core_a", 0.03))
    return cur


def supply_settings(sim, supply):
    """What a supply sets – its sources and cell states, without notes."""
    sources, cells = sim.get("sources", {}), sim.get("cells", {})
    return frozenset((k, x) for k, x in supply.items() if k in sources or (isinstance(x, str) and x in cells))


def generated_supplies(sim):
    """The supplies `combine_sources` generates, {name: supply}, in this order: each source alone at the low and the
    high end of its range; with several, all of them together, each one high in turn and the others low. A source of
    `sources` gets [low, high] in volts, a battery holder two cell states of `cells`. A supply with the settings of a
    hand-written one is left out – that one runs."""
    combine = sim.get("combine_sources") or {}
    sources, cells = sim.get("sources", {}), sim.get("cells", {})
    if not isinstance(combine, dict):
        raise SimError(f"combine_sources: a map from each source to its [low, high] expected, not {combine!r}")
    for des, ends in combine.items():
        if not isinstance(ends, list) or len(ends) != 2:
            raise SimError(f"combine_sources {des}: [low, high] expected, not {ends!r}")
        if all(isinstance(x, str) for x in ends):
            if any(x not in cells for x in ends):
                raise SimError(f"combine_sources {des}: {', '.join(x for x in ends if x not in cells)} – no cell "
                               "state of cells")
        elif des not in sources or not all(isinstance(x, (int, float)) for x in ends):
            raise SimError(f"combine_sources {des}: neither a source of sources with [low, high] in volts nor a battery "
                           "holder with two cell states of cells")

    def name(des, x):
        return f"{des} {x:g}" if isinstance(x, (int, float)) else f"{des} {x}"
    out = {name(des, x): {des: x} for des, ends in combine.items() for x in ends}
    if len(combine) > 1:
        for des, (_, high) in combine.items():
            together = [(des, high)] + [(d, ends[0]) for d, ends in combine.items() if d != des]
            out[" + ".join(name(d, x) for d, x in together)] = dict(together)
    hand = {supply_settings(sim, s) for s in sim.get("supplies", {}).values()}
    return {n: s for n, s in out.items() if n not in sim.get("supplies", {}) and supply_settings(sim, s) not in hand}


def scenarios(sim):
    corners = sim.get("corners", ["typ"])
    generated = generated_supplies(sim)
    taken = {(supply_settings(sim, s["supply"]), s["load"]) for s in sim.get("extra_scenarios", [])}
    for supply_name, supply in {**sim.get("supplies", {}), **generated}.items():
        for load_name, load in sim["loads"].items():
            if load.get("matrix") is False:  # fault cases: only where extra_scenarios name them
                continue
            if supply_name in generated and (supply_settings(sim, supply), load_name) in taken:
                continue                     # an extra scenario took the combination over (info: excluded by procedure)
            for corner in corners:
                yield {"name": f"{supply_name}/{load_name}/vf-{corner}", "supply_name": supply_name, "supply": supply,
                       "load_name": load_name, "load": load, "corner": corner}
    for s in sim.get("extra_scenarios", []):
        yield {"name": s["name"], "supply_name": s.get("supply_name", "extra"), "supply": s["supply"],
               "load_name": s["load"], "load": sim["loads"][s["load"]], "corner": s.get("corner", "typ"),
               "info": s.get("info", False)}


RUN_KEYS = {"supply", "load", "corner", "stop_s", "step_s", "expect", "info", "about", "note"}


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def transient_runs(design, sim):
    """The runs of `transients`, {name: run}, checked: a supply per source of `sources` (a voltage, or [t, V] points
    with rising t) or per battery holder (a cell state of `cells`), a load of `loads`, stop_s and step_s in seconds,
    expect per net (min_v, max_v) or per source (i_max_a)."""
    runs = sim.get("transients") or {}
    if not isinstance(runs, dict):
        raise SimError(f"transients: a map from each run's name to the run expected, not {runs!r}")
    sources, cells = sim.get("sources", {}), sim.get("cells", {})
    for name, r in runs.items():
        at = f"transients {name}"
        if not isinstance(r, dict) or set(r) - RUN_KEYS:
            raise SimError(f"{at}: a run with {', '.join(sorted(RUN_KEYS - {'about', 'note'}))} expected, not {r!r}")
        if r.get("load") not in sim.get("loads", {}):
            raise SimError(f"{at}: load {r.get('load')} is no load of loads")
        if r.get("corner", "typ") not in ("min", "typ", "max"):
            raise SimError(f"{at}: corner min, typ or max expected, not {r['corner']!r}")
        stop = r.get("stop_s")
        if not number(stop) or stop <= 0:
            raise SimError(f"{at}: stop_s, the length of the run in seconds, expected")
        step = r.get("step_s", stop / 1000)
        if not number(step) or not 0 < step <= stop:
            raise SimError(f"{at}: step_s, the largest time step in seconds (≤ stop_s), expected, not {step!r}")
        if not isinstance(r.get("supply"), dict):
            raise SimError(f"{at}: supply, a map from each source or battery holder to its curve or state, expected")
        for des, x in r["supply"].items():
            if des in sources:
                pts = x if isinstance(x, list) else None
                if not number(x) and not (pts and all(isinstance(q, list) and len(q) == 2 and all(map(number, q))
                                                      for q in pts)
                                          and pts[0][0] >= 0 and all(a[0] < b[0] for a, b in zip(pts, pts[1:]))):
                    raise SimError(f"{at}: {des} – a voltage or a list of [t, V] points with rising t from 0 expected, "
                                   f"not {x!r}")
            elif not (isinstance(x, str) and x in cells and (design.part(des) or {}).get("kind") == "battery_holder"):
                raise SimError(f"{at}: {des} is neither a source of sources nor a battery holder with a cell state of "
                               "cells")
        for key, lim in (r.get("expect") or {}).items():
            allowed = {"i_max_a"} if key in sources else {"min_v", "max_v"} if key in design.nets else None
            if allowed is None:
                raise SimError(f"{at}: expect {key} is neither a net nor a source of sources")
            if not isinstance(lim, dict) or not lim or set(lim) - allowed or not all(map(number, lim.values())):
                raise SimError(f"{at}: expect {key} – {' and/or '.join(sorted(allowed))} expected, not {lim!r}")
    return runs


def extreme(times, xs, fn, start=0):
    """(value, time) of the minimum (fn=min) or maximum (fn=max) of xs[start:]."""
    i = fn(range(start, len(xs)), key=xs.__getitem__)
    return xs[i], times[i]


def at_time(x, t, unit):
    return f"{x:.4g} {unit} at {t * 1e3:.4g} ms"


def transient(design, sim, name, run, keep=None, models=None):
    """One run of `transients`: ngspice .tran from the operating point at t = 0; E-1 (it converges) and E-5 – every
    limit of expect, and every MCU's supply pin, once it has reached its vin_min|vsys_min, never below it again.
    -> (row of the scenario table, check items)."""
    corner = run.get("corner", "typ")
    ck = Checks(name)
    row = {"name": name, "supply": "transient", "load": run["load"], "corner": corner, "transient": True}
    expect = run.get("expect") or {}
    sources = sim.get("sources", {})
    nets = [n for n in dict.fromkeys([*sim.get("report", []), *(k for k in expect if k not in sources)])]
    grounds = {n: netlist.local_ground(design, n) for n in nets}
    sc = {"name": name, "supply": run["supply"], "load": sim["loads"][run["load"]], "corner": corner}
    tran = {"step_s": run.get("step_s", run["stop_s"] / 1000), "stop_s": run["stop_s"],
            "nets": [*nets, *grounds.values()], "file": re.sub(r"[^\w.-]", "_", name) + ".dat"}
    try:
        text, meta = netlist.build(design, sim, sc, models or {}, tran)
        times, cols = ngspice_tran(text, tran["file"], keep, name)
    except (ValueError, KeyError, SimError) as e:
        ck.add("E-1", "circuit", "transient run", f"{type(e).__name__}: {e}", "converges", False)
        row["status"] = "error"
        return row, ck.items
    ck.add("E-1", "circuit", "transient run", "converged", "converges", True)
    wave = dict(zip(meta["tran"]["columns"], cols))
    zero = [0.0] * len(times)

    def volts(net, fn=min):
        """The net's voltage over time against its ground; with its routed copper the lowest (fn=min) or highest
        (fn=max) of its pins at each time. None for a net no element reaches."""
        nodes = [x for x in netlist.net_nodes(design, net) if x in wave or x == "0"]
        if not nodes:
            return None
        g = wave.get(netlist.node(grounds[net], design.ground), zero)
        return [fn(xs) - y for xs, y in zip(zip(*(wave.get(x, zero) for x in nodes)), g)]
    for key, lim in expect.items():
        if key in sources:
            cur = [-x for x in wave[meta["sources"][key]["branch"]]] if key in meta["sources"] else zero
            peak, t = extreme(times, cur, max)
            ck.add("E-5", key, "peak current from the supply", at_time(peak, t, "A"),
                   f"≤ {lim['i_max_a'] * 1e3:.4g} mA", peak <= lim["i_max_a"])
            continue
        for k, what, fn, sign in (("min_v", "lowest voltage", min, "≥"), ("max_v", "highest voltage", max, "≤")):
            if k not in lim:
                continue
            xs = volts(key, fn)
            if xs is None:
                ck.add("E-5", key, what, "no element of the netlist on the net", f"{sign} {lim[k]} V", False)
                continue
            x, t = extreme(times, xs, fn)
            ck.add("E-5", key, what, at_time(x, t, "V"), f"{sign} {lim[k]} V", x >= lim[k] if fn is min else x <= lim[k])
    for des, m in meta["mcu"].items():
        r = m["ratings"]
        rating = "vin_min" if "vin_min" in r else "vsys_min" if "vsys_min" in r else None
        if rating is None or m["vin"] not in wave:
            continue
        xs, vmin = wave[m["vin"]], r[rating]
        what = f"lowest supply voltage once started ({rating})"
        start = next((i for i, x in enumerate(xs) if x >= vmin), None)
        if start is None:
            ck.add("E-5", des, what, f"never reaches {vmin} V (highest {max(xs):.4g} V)", f"≥ {vmin} V", False)
            continue
        x, t = extreme(times, xs, min, start)
        ck.add("E-5", des, what, at_time(x, t, "V"), f"≥ {vmin} V", x >= vmin)
    if run.get("info"):
        for c in ck.items:
            if c["result"] == "fail":
                c["result"] = "info"
    report = [n for n in sim.get("report", []) if volts(n) is not None]
    row["nets"] = {n: min(volts(n, min)) for n in report}
    row["nets_max"] = {n: max(volts(n, max)) for n in report}
    row["sources"] = {d: max(-x for x in wave[s["branch"]]) for d, s in meta["sources"].items()}
    row["status"] = "ok" if all(c["result"] != "fail" for c in ck.items) else "fail"
    return row, ck.items


def load_plugin(path):
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("edakit_sim_plugin", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_all(design, sim, keep=None, plugin=None, routing=None):
    """All scenarios; `sim` is the parsed simulation config (tests pass modified copies). `routing`: the routed boards
    for sim.json copper (copper.load_routing)."""
    models = getattr(plugin, "MODELS", {}) if plugin else {}
    touch_limits(design, sim)
    runs = transient_runs(design, sim)
    out = {"scenarios": [], "checks": [], "net_currents": {}}
    try:
        cu = copper.annotate(design, sim, routing)
    except copper.CopperError as e:
        raise SimError(str(e)) from None
    notes = Checks("copper")
    for net, why in cu["notes"]:      # a listed net that stays one ideal node
        notes.add("E-1", net, "copper not annotated", why, "the routed copper of the net", True, "info")
    out["checks"] += notes.items
    for sc in scenarios(sim):
        ck = Checks(sc["name"])
        row = {"name": sc["name"], "supply": sc["supply_name"], "load": sc["load_name"], "corner": sc["corner"]}
        try:
            text, meta = netlist.build(design, sim, sc, models)
            res = ngspice(text, keep, sc["name"])
        except (ValueError, KeyError, SimError) as e:
            ck.add("E-1", "circuit", "operating point", f"{type(e).__name__}: {e}", "converges", False)
            row["status"] = "error"
            out["checks"] += ck.items
            out["scenarios"].append(row)
            continue
        ck.add("E-1", "circuit", "operating point", "converged", "converges", True)
        stress(design, sim, res, meta, ck)
        functional(design, sim, res, meta, sc["load"], ck, plugin)
        if sc.get("info"):
            for c in ck.items:
                if c["result"] == "fail":
                    c["result"] = "info"
        row["nets"] = {n: min(v(res, x) for x in netlist.net_nodes(design, n)) for n in sim.get("report", [])}
        row["sources"] = {d: -res.get(s["branch"], 0.0) for d, s in meta["sources"].items()}
        for net, i in net_currents(design, res, meta).items():
            e = out["net_currents"].setdefault(net, {"i_max_a": 0.0, "scenario": ""})
            if i > e["i_max_a"]:
                e.update(i_max_a=i, scenario=sc["name"])
        row["status"] = "ok" if all(c["result"] != "fail" for c in ck.items) else "fail"
        out["checks"] += ck.items
        out["scenarios"].append(row)
    for name, run in runs.items():   # transient runs: E-5, no stress, not in the net currents
        row, items = transient(design, sim, name, run, keep, models)
        out["checks"] += items
        out["scenarios"].append(row)
    return out


def load_sim_config(cfg):
    path = cfg.sim_config
    if not path.exists():
        raise SimError(f"simulation config {path} not found (edakit.toml [project] sim)")
    return json.loads(path.read_text(encoding="utf-8")), path


def inputs_sha256(cfg, sim):
    """Hash of what a simulation result depends on: the circuit hash's files, with copper also the board files and the
    routing it reads."""
    from ..release import gate
    files = gate.state_files(cfg)
    if sim.get("copper"):
        files += [cfg.resolve(b.file) for b in cfg.boards.values()]
        files += [cfg.artifacts / "route" / f"{b}{x}" for b in cfg.boards for x in (".ses", "_board.json")]
    return gate.file_hash(cfg.root, files)


def save_result(cfg, sim, out):
    """The whole result of the last run, with the hash of its inputs: <artifacts>/sim/result.json."""
    path = cfg.artifact("sim", "result.json")
    path.write_text(json.dumps({"inputs_sha256": inputs_sha256(cfg, sim), **out}, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def current_result(cfg):
    """The simulation result of the current state: the one saved by the last run when its inputs are unchanged, else a
    new run (saved in turn) – for values quoted from the simulation (edakit docs, G-19)."""
    sim, _ = load_sim_config(cfg)
    path = cfg.artifacts / "sim" / "result.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        if data.get("inputs_sha256") == inputs_sha256(cfg, sim):
            return data
    from ..design import Design
    plugin = load_plugin(cfg.sim_plugin) if cfg.sim_plugin else None
    routing = copper.load_routing(cfg) if sim.get("copper") else None
    out = run_all(Design.from_config(cfg), sim, plugin=plugin, routing=routing)
    save_result(cfg, sim, out)
    return out


def write_net_currents(cfg, out):
    path = cfg.artifact("sim", "net_currents.json")
    data = {"about": "Largest current of a single part per net over all scenarios of `edakit sim`. Nets with suffix "
                     "__<board> are the same line on the other side of a cable.",
            "nets": {n: {k: round(x, 5) if isinstance(x, float) else x for k, x in e.items()}
                     for n, e in sorted(out["net_currents"].items())}}
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(cfg, args):
    from ..design import Design
    sim, _ = load_sim_config(cfg)
    plugin = load_plugin(cfg.sim_plugin) if cfg.sim_plugin else None
    if args.keep:
        Path(args.keep).mkdir(parents=True, exist_ok=True)
    generated = generated_supplies(sim)
    if generated:
        print("supplies from combine_sources: " + ", ".join(generated))
    routing = copper.load_routing(cfg) if sim.get("copper") else None
    out = run_all(Design.from_config(cfg), sim, args.keep, plugin, routing)
    report = sim.get("report", [])
    print(f"{'scenario':<34} {'status':<7}" + "".join(f" {n:>8}" for n in report) + "   supply current")
    for r in out["scenarios"]:
        if r.get("transient"):
            continue
        nets = "".join(f" {r.get('nets', {}).get(n, float('nan')):7.3f}V" for n in report)
        src = ", ".join(f"{d} {i * 1e3:.0f} mA" for d, i in r.get("sources", {}).items())
        print(f"{r['name']:<34} {r['status']:<7}{nets}   {src}")
    runs = [r for r in out["scenarios"] if r.get("transient")]
    if runs:
        print(f"\n{'transient run':<34} {'status':<7}" + "".join(f" {n + ' min…max':>14}" for n in report)
              + "   peak supply current")
    for r in runs:
        nets = "".join(f" {r.get('nets', {}).get(n, float('nan')):7.3f}…{r.get('nets_max', {}).get(n, float('nan')):.3f}V"
                       for n in report)
        src = ", ".join(f"{d} {i * 1e3:.0f} mA" for d, i in r.get("sources", {}).items())
        print(f"{r['name']:<34} {r['status']:<7}{nets}   {src}")
    summary = defaultdict(int)
    for c in out["checks"]:
        summary[c["result"]] += 1
    print(f"\n{len(out['checks'])} checks: " + ", ".join(f"{k} {n}" for k, n in sorted(summary.items())))
    for c in out["checks"]:
        if c["result"] in ("fail", "warn") or c["scenario"] == "copper":   # a net of copper that stays one node too
            print(f"  {c['result'].upper():<5} {c['id']} {c['scenario']:<30} {c['item']:<12} {c['check']}: "
                  f"{c['actual']} (expected {c['expected']})")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"net currents → {write_net_currents(cfg, out)}")
    save_result(cfg, sim, out)
    return 2 if summary["fail"] else 0
