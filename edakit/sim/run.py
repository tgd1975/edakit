"""Stage E (simulation): operating points of all scenarios with ngspice, stress and function checks.

    edakit sim [--json FILE] [--keep DIR]

Scenarios = supplies x loads x LED forward-voltage corners from the simulation config (edakit.toml [project] sim),
plus "extra_scenarios" listed there.

  E-1  the operating point converges
  E-2  stress of every part against the ratings in the parts database, with the derating from the config; MCU output
       current per pin (gpio_i_max_a) and of all outputs together (gpio_i_total_max_a)
  E-3  function: supply currents, regulator outputs and headroom, MCU supply and input levels, MCU outputs only on
       pins that can drive, constant-current driver headroom and junction temperature, LED currents on/off as the load
       says (an LED behind a 0 Ω bridge counts on the driver output the bridge joins it to, an LED behind one resistor
       to a single driver output on that output – parallel LEDs with balancing resistors), relays pull in and release
       (v_operate, v_release), a module modelled as a constant current (an own board, part.py) supplied inside
       vin_min … vin_max, blocking diodes, every net inside its declared voltage range 'v', plus the project
       plugin's own checks
  E-4  every LED – each colour of an RGB LED – has a state E-3 checks in every scenario: its cathode on a driver output
       (directly, behind 0 Ω bridges or behind a balancing resistor) or the load has leds_on; an LED with neither, or
       one the netlist left out because its parts entry lacks a role, fails as "LED without a known driver"

Rule, reason and fix of each check: rules.json (`edakit rules E-2`).

The largest current per net goes to <artifacts>/sim/net_currents.json – the input for the track widths
(`edakit pcb plan`, gate check L-5). Exit code: 0 = all passed, 2 = at least one 'fail', 1 = tool error.
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

from . import netlist

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


def reg_input_current(res, reg):
    """Current a regulator model draws from its input (the same expression as its B-source)."""
    iout = max(res.get(reg["ammeter"], 0.0), 0.0)
    p = reg["params"]
    if reg["kind"] == "ldo":
        return iout + p.get("iq_a", 0.0) + reg["extra_i"]
    vin = max(v(res, reg["vin"]) - v(res, reg["gnd"]), 0.3)
    return reg["vset"] * (iout + reg["extra_i"]) / (p.get("efficiency", 0.85) * vin) + p.get("iq_a", 0.0)


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
            tj = amb + (vin - vout) * iout * r["rth_ja_k_per_w"]
            ck.add("E-3", des, f"junction temperature at {amb} °C", tj, f"≤ {crit['tj_max_c']} °C",
                   tj <= crit["tj_max_c"], unit=" °C")
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
            x = v(res, netlist.node(net, design.ground))
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
        ground = next((design.pin_net[f"{des}.{n}"] for n, i in p["pins"].items()
                       if i.get("type") == "ground" and f"{des}.{n}" in design.pin_net), design.ground)
        for num, info in p["pins"].items():
            net = design.pin_net.get(f"{des}.{num}")
            if net and info.get("type") == "power_in":
                x = v(res, netlist.node(net, design.ground)) - v(res, netlist.node(ground, design.ground))
                ck.add("E-3", des, f"supply voltage at {info.get('name', num)} within vin_min … vin_max", x, want,
                       lo <= x <= hi, unit=" V")

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
            tj = amb + pd * r["rth_ja_k_per_w"]
            ck.add("E-3", des, f"junction temperature at {amb} °C", tj, f"≤ {crit['tj_max_c']} °C",
                   tj <= crit["tj_max_c"], unit=" °C")

    leds_on = load.get("leds_on")
    groups = defaultdict(list)
    behind = behind_resistor(design, joined, chan_of)   # LEDs in parallel on one channel, each behind its resistor
    for name, info in meta["leds"].items():
        i = res.get(f"@{name}[id]", float("nan"))
        label = name[2:].upper()
        cathode, anode = (joined.get(info[k], info[k]) for k in ("cathode_net", "anode_net"))
        if cathode in chan_of:
            groups[cathode].append((label, i))
        elif anode in chan_of:
            ck.add("E-3", label, f"LED reversed (anode at the driver output {info['anode_net']})", i,
                   "cathode at the driver output", False, unit=" A")
        elif cathode in behind:
            groups[behind[cathode]].append((label, i))
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
        x = v(res, netlist.node(name, gnd)) - v(res, netlist.node(netlist.local_ground(design, name), gnd))
        lo, hi = net.get("v", [0, 0])
        ck.add("E-3", name, "net voltage inside the declared range", x, f"{lo} … {hi} V", lo - tol <= x <= hi + tol,
               unit=" V")
    if plugin and hasattr(plugin, "checks"):
        plugin.checks(design=design, cfg=cfg, res=res, meta=meta, load=load, add=ck.add)


def net_currents(design, res, meta):
    """Largest current of a single part per net – a measure for the main trunk of a track."""
    gnd = design.ground
    net_of_node = {netlist.node(n, gnd): n for n in set(design.pin_net.values())}
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


def scenarios(sim):
    corners = sim.get("corners", ["typ"])
    for supply_name, supply in sim["supplies"].items():
        for load_name, load in sim["loads"].items():
            if load.get("matrix") is False:  # fault cases: only where extra_scenarios name them
                continue
            for corner in corners:
                yield {"name": f"{supply_name}/{load_name}/vf-{corner}", "supply_name": supply_name, "supply": supply,
                       "load_name": load_name, "load": load, "corner": corner}
    for s in sim.get("extra_scenarios", []):
        yield {"name": s["name"], "supply_name": s.get("supply_name", "extra"), "supply": s["supply"],
               "load_name": s["load"], "load": sim["loads"][s["load"]], "corner": s.get("corner", "typ"),
               "info": s.get("info", False)}


def load_plugin(path):
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("edakit_sim_plugin", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_all(design, sim, keep=None, plugin=None):
    """All scenarios; `sim` is the parsed simulation config (tests pass modified copies)."""
    models = getattr(plugin, "MODELS", {}) if plugin else {}
    out = {"scenarios": [], "checks": [], "net_currents": {}}
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
        row["nets"] = {n: v(res, netlist.node(n, design.ground)) for n in sim.get("report", [])}
        row["sources"] = {d: -res.get(s["branch"], 0.0) for d, s in meta["sources"].items()}
        for net, i in net_currents(design, res, meta).items():
            e = out["net_currents"].setdefault(net, {"i_max_a": 0.0, "scenario": ""})
            if i > e["i_max_a"]:
                e.update(i_max_a=i, scenario=sc["name"])
        row["status"] = "ok" if all(c["result"] != "fail" for c in ck.items) else "fail"
        out["checks"] += ck.items
        out["scenarios"].append(row)
    return out


def load_sim_config(cfg):
    path = cfg.sim_config
    if not path.exists():
        raise SimError(f"simulation config {path} not found (edakit.toml [project] sim)")
    return json.loads(path.read_text(encoding="utf-8")), path


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
    out = run_all(Design.from_config(cfg), sim, args.keep, plugin)
    report = sim.get("report", [])
    print(f"{'scenario':<34} {'status':<7}" + "".join(f" {n:>8}" for n in report) + "   supply current")
    for r in out["scenarios"]:
        nets = "".join(f" {r.get('nets', {}).get(n, float('nan')):7.3f}V" for n in report)
        src = ", ".join(f"{d} {i * 1e3:.0f} mA" for d, i in r.get("sources", {}).items())
        print(f"{r['name']:<34} {r['status']:<7}{nets}   {src}")
    summary = defaultdict(int)
    for c in out["checks"]:
        summary[c["result"]] += 1
    print(f"\n{len(out['checks'])} checks: " + ", ".join(f"{k} {n}" for k, n in sorted(summary.items())))
    for c in out["checks"]:
        if c["result"] in ("fail", "warn"):
            print(f"  {c['result'].upper():<5} {c['id']} {c['scenario']:<30} {c['item']:<12} {c['check']}: "
                  f"{c['actual']} (expected {c['expected']})")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"net currents → {write_net_currents(cfg, out)}")
    return 2 if summary["fail"] else 0
