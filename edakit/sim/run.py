"""Stage E (simulation): operating points of all scenarios with ngspice; the engines judge what they find.

    edakit sim [--json FILE] [--keep DIR]

Scenarios = supplies x loads x LED forward-voltage corners x the spread corners of the transistors ("spread",
sim/spread.py – without the key only typ) from the simulation config (edakit.toml [project] sim),
plus "extra_scenarios" listed there. "combine_sources" adds supplies for every combination of the sources it names:
each alone at both ends of its range, all together with one high and the others low (generated_supplies).
"ac" adds AC runs around an operating point – only where it names an expectation, only with the domain audio or guitar on
(sim/ac.py, decision 9). "fault_scenarios" adds generated fault cases (a reversed source, a cable wire shorted at its far end, one source off),
their findings warnings at most. "transients" adds runs over time: the supplies follow [t, V] points (plug, unplug, a switch-over), loads may step
([t, A] points under "steps": a servo starting, a Wi-Fi burst), ngspice .tran from the operating point at t = 0;
without the key nothing runs.

The simulation is a producer (engines/sim.py): every scenario's voltages, currents, power and temperatures against the
limits of the parts entries (LIM.v, LIM.i, LIM.p, LIM.t), supplies against operating ranges (LIM.range), the declared
net ranges (LIM.declared), back-feed (LIM.backfeed), logic levels (LVL.threshold, LVL.direction), the states a load
expects (SIM.state), every LED with a state to check (SIM.driver); a scenario that does not converge is SIM.converge.
Every comparison is a row with its actual and expected value (out["checks"]: the protocol's simulation table, what
documents and requirements quote), every violation a finding (out["findings"]). Rule, reason and fix: edakit explain.

The largest current per net goes to <artifacts>/sim/net_currents.json – the input for the track widths
(`edakit pcb plan`, GEO.width) –, the whole result with the hash of its inputs to <artifacts>/sim/result.json, which
values quoted from the simulation reuse while the inputs are unchanged (edakit docs, DOCS.quote). Exit code: 0 = no
finding of severity error, 2 = at least one, 1 = tool error.
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

from .. import engines
from ..engines import sim as esim
from ..findings import Finding, format_findings
from . import copper, netlist, spread



class SimError(Exception):
    pass


NGSPICE_OP_S = 120         # an operating point that takes longer does not converge
NGSPICE_TRAN_S = 600       # a transient run that takes longer is too fine for the check


def ngspice(text, keep=None, name="run"):
    if not shutil.which("ngspice"):
        raise SimError("ngspice not found – install it (Debian/Ubuntu: sudo apt install ngspice)")
    with tempfile.TemporaryDirectory() as tmp:
        cir = Path(keep or tmp) / (re.sub(r"[^\w.-]", "_", name) + ".cir")
        cir.write_text(text)
        try:
            res = subprocess.run(["ngspice", "-b", str(cir)], capture_output=True, text=True, timeout=NGSPICE_OP_S)
        except subprocess.TimeoutExpired:
            raise SimError(f"{name}: ngspice found no operating point within {NGSPICE_OP_S} s – a model that does not "
                           "converge there (the scenario's sources, a behaviour model near its threshold)") from None
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
        try:
            res = subprocess.run(["ngspice", "-b", cir.name], cwd=d, capture_output=True, text=True,
                                 timeout=NGSPICE_TRAN_S)
        except subprocess.TimeoutExpired:
            raise SimError(f"{name}: the transient run took more than {NGSPICE_TRAN_S} s – a shorter stop_s or a "
                           "coarser step") from None
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


def check_sources(design, sim):
    """The sources of sim.json: a plus and a minus pin of their connector, or "outputs" – several rails against the
    shared minus, each {plus, v_ratio (default 1; −1 for a rail below the minus), r_ohm, i_max_a}."""
    for des, spec in (sim.get("sources") or {}).items():
        at = f"sources.{des}"
        if not isinstance(spec, dict) or spec.get("minus") is None:
            raise SimError(f"{at}: a table with plus and minus (pin numbers of {des}) expected, not {spec!r}")
        if "outputs" in spec:
            outs = spec["outputs"]
            if "plus" in spec or not isinstance(outs, dict) or not outs:
                raise SimError(f"{at}: outputs – a table of rails {{name: {{plus, v_ratio}}}} instead of plus, "
                               f"not {outs!r}")
            for name, o in outs.items():
                if not isinstance(o, dict) or o.get("plus") is None:
                    raise SimError(f"{at}.outputs.{name}: plus, the pin of the rail, expected, not {o!r}")
                ratio = o.get("v_ratio", 1.0)
                if not number(ratio) or ratio == 0:
                    raise SimError(f"{at}.outputs.{name}: v_ratio – a number other than 0 (the rail's voltage over "
                                   f"the supply's), not {ratio!r}")
        elif spec.get("plus") is None:
            raise SimError(f"{at}: plus (the pin of the supply) or outputs (several rails) expected")


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
    p = reg["values"]
    vin = esim.v(res, reg["vin"]) - esim.v(res, reg["gnd"])
    on = esim.lockout(res, reg)
    if reg["kind"] == "ldo":
        return on * (iout + p.get("iq_a", 0.0) + reg["extra_i"])
    return on * (reg["vset"] * (iout + reg["extra_i"]) / (p.get("efficiency", 0.85) * max(vin, 0.3)) + p.get("iq_a", 0.0))




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
                put(el["nodes"][:2], (esim.v(res, el["nodes"][0]) - esim.v(res, el["nodes"][1])) / el["value"])
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
            elif el["kind"] in ("njfet", "pjfet"):
                put([el["nodes"][0], el["nodes"][2]], res.get(f"@{el['name']}[id]", 0.0))
                put([el["nodes"][1]], res.get(f"@{el['name']}[ig]", 0.0))
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
            put([m["vin"]], m["values"].get("i_core_a", netlist.I_CORE_A))
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
    """supplies × loads × LED corners × spread corners (sim/spread.py; without `spread` only typ, the names as before),
    then the extra scenarios with their own corner and spread."""
    corners = sim.get("corners", ["typ"])
    spreads = spread.matrix(sim)
    generated = generated_supplies(sim)
    taken = {(supply_settings(sim, s["supply"]), s["load"]) for s in sim.get("extra_scenarios", [])}
    for supply_name, supply in {**sim.get("supplies", {}), **generated}.items():
        for load_name, load in sim["loads"].items():
            if load.get("matrix") is False:  # fault cases: only where extra_scenarios name them
                continue
            if supply_name in generated and (supply_settings(sim, supply), load_name) in taken:
                continue                     # an extra scenario took the combination over (info: excluded by procedure)
            for corner in corners:
                for sp in spreads:
                    yield {"name": f"{supply_name}/{load_name}/vf-{corner}" + ("" if sp == "typ" else f"/spread-{sp}"),
                           "supply_name": supply_name, "supply": supply, "load_name": load_name, "load": load,
                           "corner": corner, "spread": sp}
    for s in sim.get("extra_scenarios", []):
        yield {"name": s["name"], "supply_name": s.get("supply_name", "extra"), "supply": s["supply"],
               "load_name": s["load"], "load": sim["loads"][s["load"]], "corner": s.get("corner", "typ"),
               "spread": s.get("spread", "typ"), "info": s.get("info", False)}


FAULT_KEYS = ("reversed", "shorted", "off", "supply", "load")


def fault_scenarios(design, sim):
    """The scenarios "fault_scenarios" generates (maker-coverage FT-8), opt-in – on the first supply and the first load
    unless it names others: "reversed" a source the graph marks reversible at its voltage reversed, "shorted" each
    signal wire of a cable shorted to ground at its far end, "off" each source of a supply with several left out while
    the others stay on. Their findings are warnings at most (Report.resolve, data fault): what a fault does to the board
    is a question for the designer, not a release blocker by itself."""
    from ..circuit import supply_nets
    spec = sim.get("fault_scenarios")
    if not spec:
        return []
    if not isinstance(spec, dict) or set(spec) - set(FAULT_KEYS):
        raise SimError(f"fault_scenarios: a table of {', '.join(FAULT_KEYS)}, not {spec!r}")
    supplies, loads = sim.get("supplies", {}), sim.get("loads", {})
    if not supplies or not loads:
        return []
    sname, lname = spec.get("supply") or next(iter(supplies)), spec.get("load") or next(iter(loads))
    if sname not in supplies or lname not in loads:
        raise SimError(f"fault_scenarios: no supply {sname} or no load {lname} in the simulation config")
    supply, load, sources, cells = supplies[sname], loads[lname], sim.get("sources", {}), sim.get("cells", {})
    base = {"load_name": lname, "load": load, "corner": "typ", "fault": True}
    out = []
    if spec.get("reversed"):
        for des in sorted(d for d, c in design.comps.items() if c.get("source") == "reversible"):
            x = supply.get(des)
            if des in sources and isinstance(x, (int, float)) and x:
                out.append({**base, "name": f"fault {des} reversed/{lname}", "supply_name": f"{sname}, {des} reversed",
                            "supply": {**supply, des: -x}})
    if spec.get("shorted"):
        quiet = {design.ground} | supply_nets(design)
        for c in design.graph.get("cables", []):
            for a, b in c.get("pins", {}).items():
                net = design.pin_net.get(f"{c['from']}.{a}")
                if net and net not in quiet:
                    out.append({**base, "name": f"fault {net} shorted at {c['to']}/{lname}", "supply_name": sname,
                                "supply": supply, "short": [f"{c['to']}.{b}"]})
    if spec.get("off"):
        on = [d for d, x in supply.items() if d in sources or (isinstance(x, str) and x in cells)]
        if len(on) > 1:
            for des in on:
                out.append({**base, "name": f"fault {des} off/{lname}", "supply_name": f"{sname}, {des} off",
                            "supply": {k: x for k, x in supply.items() if k != des}})
    return out


RUN_KEYS = {"supply", "load", "corner", "spread", "stop_s", "step_s", "steps", "expect", "info", "about", "note"}


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
        steps = r.get("steps") or {}
        if not isinstance(steps, dict):
            raise SimError(f"{at}: steps, a map from each load that steps to its [t, A] points, expected")
        external = sim["loads"][r["load"]].get("external") or {}
        for des, pts in steps.items():
            behavior = ((design.part(des) or {}).get("values") or {}).get("behavior")
            if des not in external and behavior not in ("mcu", "current"):
                raise SimError(f"{at}: steps {des} – an external load of load {r['load']}, an MCU or a part of behaviour "
                               "current steps, nothing else")
            if not (isinstance(pts, list) and pts and all(isinstance(q, list) and len(q) == 2 and all(map(number, q))
                                                          and q[1] >= 0 for q in pts)
                    and pts[0][0] >= 0 and all(a[0] < b[0] for a, b in zip(pts, pts[1:]))):
                raise SimError(f"{at}: steps {des} – a list of [t, A] points with rising t from 0 and currents ≥ 0 "
                               f"expected, not {pts!r}")
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


def transient(design, new, sim, name, run, keep=None, models=None):
    """One run of `transients`: ngspice .tran from the operating point at t = 0; SIM.converge, and every limit of
    expect and every MCU's supply once started (engines/sim.py transient). -> (row of the scenario table, rows,
    findings)."""
    corner = run.get("corner", "typ")
    row = {"name": name, "supply": "transient", "load": run["load"], "corner": corner, "transient": True}
    expect = run.get("expect") or {}
    sources = sim.get("sources", {})
    nets = [n for n in dict.fromkeys([*sim.get("report", []), *(k for k in expect if k not in sources)])]
    grounds = {n: netlist.local_ground(design, n) for n in nets}
    sc = {"name": name, "supply": run["supply"], "load": sim["loads"][run["load"]], "corner": corner,
          "steps": run.get("steps") or {}, "spread": run.get("spread", "typ")}
    tran = {"step_s": run.get("step_s", run["stop_s"] / 1000), "stop_s": run["stop_s"],
            "nets": [*nets, *grounds.values()], "file": re.sub(r"[^\w.-]", "_", name) + ".dat"}
    s = esim.Scene(design, new, sim, {}, {}, name, run.get("info", False))
    try:
        text, meta = netlist.build(design, sim, sc, models or {}, tran)
        times, cols = ngspice_tran(text, tran["file"], keep, name)
    except (ValueError, KeyError, SimError) as e:
        s.check("SIM.converge", "circuit", "transient run", f"{type(e).__name__}: {e}", "converges", False)
        row["status"] = "error"
        return (row, *s.finish())
    s.check("SIM.converge", "circuit", "transient run", "converged", "converges", True)
    s.meta = meta
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
    esim.transient(s, expect, sources, times, wave, volts, extreme)
    rows, found = s.finish()
    report = [n for n in sim.get("report", []) if volts(n) is not None]
    row["nets"] = {n: min(volts(n, min)) for n in report}
    row["nets_max"] = {n: max(volts(n, max)) for n in report}
    row["sources"] = {d: max(-x for x in wave[src["branch"]]) for d, src in meta["sources"].items()}
    row["status"] = "ok" if all(r["result"] != "fail" for r in rows) else "fail"
    return row, rows, found


def load_plugin(path):
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("edakit_sim_plugin", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def least_current(design, sim, sc, meta, models=None, keep=None):
    """The operating point of SIM.state's minimum load: the scenario with every MCU at its least current (params
    i_core_min_a) instead of its upper bound i_core_a, which every other check keeps. -> ({MCU: least current in A},
    ngspice result); None where no source of the scenario has i_min_a or no MCU a least current below its i_core_a –
    the scenario's own operating point is then the check's, as without the key."""
    cores = {des: m["values"]["i_core_min_a"] for des, m in meta["mcu"].items() if "i_core_min_a" in m["values"]
             and m["values"]["i_core_min_a"] != m["values"].get("i_core_a", netlist.I_CORE_A)}
    if not cores or not any(s.get("i_min_a") for s in meta["sources"].values()):
        return None
    text, _ = netlist.build(design, sim, {**sc, "least_current": True}, models)
    try:
        return cores, ngspice(text, keep, f"{sc['name']} least current")
    except SimError as e:
        raise SimError(f"at the least current ({', '.join(cores)} at i_core_min_a): {e}") from None


def ac_scenarios(dc, name, run):
    """[(name, DC scenario)] an AC run linearises around: the scenario it names; without one the first DC scenario –
    with spread corners the first of each corner (the same supply, load and LED corner), the run named
    '<name> spread-<corner>' there: the gain of a stage moves with its transistors as its bias does."""
    if run.get("scenario"):
        return [(name, next(sc for sc in dc if sc["name"] == run["scenario"]))]
    first = {}
    for sc in dc:
        if isinstance(sc.get("spread", "typ"), str):
            first.setdefault(sc.get("spread", "typ"), sc)
    if set(first) <= {"typ"}:
        return [(name, dc[0])]
    return [(name if x == "typ" else f"{name} spread-{x}", sc) for x, sc in first.items()]


def unrated_cables(design, currents):
    """A row of information per cable without i_max_a that carries current (maker-coverage FT-2, rules-at-scale.md
    decision 22): its highest current over the scenarios and the loss per metre of wire it causes – no limit to judge
    it by; edakit check --coverage names the same cables."""
    from ..engines.coverage import CARRIES_A, cable_loss
    rows = []
    for c in design.graph.get("cables") or []:
        e = currents.get(c.get("name"))
        if e is None or e["i_a"] < CARRIES_A or number(c.get("i_max_a")):
            continue
        amount, basis = cable_loss(c, e["i_a"])
        rows.append({"id": "LIM.i", "scenario": e["scenario"], "item": f"cable {c['name']}",
                     "check": f"highest current through a wire, no i_max_a (wire {e['wire']} – {amount}, {basis})",
                     "actual": f"{e['i_a']:.4g} A", "expected": "information", "result": "info"})
    return rows


def run_all(design, sim, keep=None, plugin=None, routing=None):
    """All scenarios and transient runs; `sim` is the parsed simulation config (tests pass modified copies), `routing`
    the routed boards for sim.json copper (copper.load_routing). -> {"scenarios", "checks" (rows), "findings",
    "net_currents", "cable_currents" ({cable: {i_a, wire, scenario}}: the highest current through a wire of each cable
    over the DC scenarios, the generated faults left out)}"""
    from . import ac
    models = getattr(plugin, "MODELS", {}) if plugin else {}
    check_sources(design, sim)
    touch_limits(design, sim)
    runs = transient_runs(design, sim)
    try:
        spread.check(design, sim)
    except spread.SpreadError as e:
        raise SimError(str(e)) from None
    dc = list(scenarios(sim))
    try:
        ac_runs = ac.runs(design, sim, [sc["name"] for sc in dc])
    except ac.ACError as e:
        raise SimError(str(e)) from None
    out = {"scenarios": [], "checks": [], "net_currents": {}, "cable_currents": {}}
    new, found = design, []
    try:
        cu = copper.annotate(design, sim, routing)
    except copper.CopperError as e:
        raise SimError(str(e)) from None
    for net, why in cu["notes"]:      # a listed net that stays one ideal node
        out["checks"].append({"id": "SIM.copper", "scenario": "copper", "item": net, "check": "copper not annotated",
                              "actual": why, "expected": "the routed copper of the net", "result": "info"})
        found.append(Finding("SIM.copper", "E", net, f"copper not annotated: {why}"))
    if any(sc["spread"] != "typ" for sc in dc) and (bare := spread.without(design)):
        out["checks"].append({"id": "SIM.config", "scenario": "spread", "item": "spread",
                              "check": "transistors without a spread in their entry – the same model in every corner",
                              "actual": "; ".join(f"{des}: {why}" for des, why in bare.items()),
                              "expected": "the spread of each transistor's datasheet", "result": "info"})
    for sc in [*dc, *fault_scenarios(design, sim)]:
        row = {"name": sc["name"], "supply": sc["supply_name"], "load": sc["load_name"], "corner": sc["corner"],
               **({"spread": sc["spread"]} if sc.get("spread", "typ") != "typ" else {})}
        s = esim.Scene(design, new, sim, {}, {}, sc["name"], sc.get("info", False))
        s.fault = sc.get("fault", False)
        try:
            text, meta = netlist.build(design, sim, sc, models)
            res = ngspice(text, keep, sc["name"])
            low = least_current(design, sim, sc, meta, models, keep)
        except (ValueError, KeyError, SimError) as e:
            s.check("SIM.converge", "circuit", "operating point", f"{type(e).__name__}: {e}", "converges", False)
            rows, fs = s.finish()
            row["status"] = "error"
            out["checks"] += rows
            found += fs
            out["scenarios"].append(row)
            continue
        s.res, s.meta = res, meta
        s.check("SIM.converge", "circuit", "operating point", "converged", "converges", True)
        esim.stress(s)
        esim.function(s, sc["load"], low, plugin)
        rows, fs = s.finish()
        row["nets"] = {n: min(esim.v(res, x) for x in netlist.net_nodes(design, n)) for n in sim.get("report", [])}
        row["sources"] = {d: -res.get(src["branch"], 0.0) for d, src in meta["sources"].items()}
        for net, i in net_currents(design, res, meta).items():
            e = out["net_currents"].setdefault(net, {"i_max_a": 0.0, "scenario": ""})
            if i > e["i_max_a"]:
                e.update(i_max_a=i, scenario=sc["name"])
        if not sc.get("fault"):      # a generated fault's short is no operating current of a wire
            for name, (i, wire) in esim.cable_currents(design, res, meta).items():
                e = out["cable_currents"].setdefault(name, {"i_a": i, "wire": wire, "scenario": sc["name"]})
                if i > e["i_a"]:
                    e.update(i_a=i, wire=wire, scenario=sc["name"])
        results = {r["result"] for r in rows}
        row["status"] = "fail" if "fail" in results else "warn" if "warn" in results else "ok"
        out["checks"] += rows
        found += fs
        out["scenarios"].append(row)
    out["checks"] += unrated_cables(design, out["cable_currents"])
    for name, run in runs.items():   # transient runs: their limits, no stress, not in the net currents
        row, rows, fs = transient(design, new, sim, name, run, keep, models)
        out["checks"] += rows
        found += fs
        out["scenarios"].append(row)
    prof = engines.profile(new)
    if ac_runs and not prof.on(Finding("SIM.response", "E", "", "")):
        found.append(ac.off_note(ac_runs))       # opt-in: only with the domain audio or guitar on (decision 9)
    elif ac_runs:
        out["ac"] = {}
        for name, run in ac_runs.items():        # AC runs: around a DC operating point, their expectations only
            for tag, sc in ac_scenarios(dc, name, run):
                row, rows, fs, curve = ac.run_one(design, new, sim, tag, run, sc, ngspice_tran, keep, models)
                out["checks"] += rows
                found += fs
                out["scenarios"].append(row)
                if curve:
                    out["ac"][tag] = curve
    rep = engines.report(found, prof, new.graph, notes=False)
    out["findings"] = [f.to_dict() for f in rep.findings]
    judge_rows(out, rep.findings)
    return out


def judge_rows(out, findings):
    """The row of a failed comparison takes its finding's verdict, once the profile and the graph's accepts are applied
    – as the gate judges a finding of stages P and G: accepted on its part, its net or the graph, it is waived with the
    reason; a warning is warn, for the sign-off file to accept; a note is info; an error stays fail. A scenario's status
    follows its rows. A row is its finding's by code, scenario, place and the check its text starts with."""
    pool = defaultdict(list)
    for f in findings:
        pool[(f.code, f.scenario, f.place)].append(f)
    for r in out["checks"]:
        fs = pool.get((r["id"], r.get("scenario", ""), r.get("item", ""))) if r["result"] == "fail" else None
        f = next((f for f in fs or () if f.text.startswith(str(r.get("check", "")))), None)
        if f is None:
            continue
        fs.remove(f)
        if f.accepted and f.severity != "pending":
            r["result"], r["reason"] = "waived", f.accepted
        elif f.severity in ("warning", "note"):
            r["result"] = {"warning": "warn", "note": "info"}[f.severity]
    by_scenario = defaultdict(set)
    for r in out["checks"]:
        by_scenario[r.get("scenario")].add(r["result"])
    for row in out["scenarios"]:
        if row.get("status") == "fail" and "fail" not in by_scenario.get(row.get("name"), {"fail"}):
            row["status"] = "warn" if "warn" in by_scenario[row["name"]] else "ok"


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


def saved_result(cfg, sim=None):
    """The result the last run saved, when its inputs are unchanged – else None; runs nothing (edakit check --coverage
    takes the cables' currents from it)."""
    try:
        sim = sim if sim is not None else load_sim_config(cfg)[0]
        data = json.loads((cfg.artifacts / "sim" / "result.json").read_text(encoding="utf-8"))
        same = isinstance(data, dict) and data.get("inputs_sha256") == inputs_sha256(cfg, sim)
    except (OSError, ValueError, SimError):
        return None
    return data if same else None


def current_result(cfg):
    """The simulation result of the current state: the one saved by the last run when its inputs are unchanged, else a
    new run (saved in turn) – for values quoted from the simulation (edakit docs, DOCS.quote)."""
    sim, _ = load_sim_config(cfg)
    if (data := saved_result(cfg, sim)) is not None:
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
    found = [Finding(**f) for f in out["findings"]]
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
    print(f"\n{len(out['checks'])} comparisons: " + ", ".join(f"{k} {n}" for k, n in sorted(summary.items())))
    if found:
        print("\n" + "\n".join(format_findings(found)))
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    try:            # the results stand above; a project whose artifacts cannot be written loses only the files
        print(f"net currents → {write_net_currents(cfg, out)}")
        save_result(cfg, sim, out)
    except OSError as e:
        print(f"note: the artifacts were not written ({e}) – the results above are complete")
    return 2 if any(f.severity == "error" and not f.accepted for f in found) else 0
