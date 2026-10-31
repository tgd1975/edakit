"""An addressable LED strip in the simulation (parts kind led_strip, maker-coverage FT-13).

The strip is a ladder: its pixels sit in a row between a +V rail and a GND rail, r_vdd_ohm_per_m and r_gnd_ohm_per_m
of copper per metre each. A pixel draws i_idle_a, plus the load's share of full white (sim.json load `strips`) of the
rest up to i_pixel_a – a constant current between the two rails, falling to 0 below the netlist's DEAD_RAIL_V across it
like every constant-current load. A strip of more than SECTIONS pixels is lumped into SECTIONS sections of (nearly)
equal pixel counts, each section's current at the mean place of its pixels; up to SECTIONS pixels every pixel is a
section of its own. The pins with the roles vdd and gnd feed the rails at the start, vdd_end and gnd_end at the far end
(the strip's length: the component's strip.length_m or strip.pixels), each through an ammeter.

A cable of the graph to a strip (split_feeds) gives the strip's pin a node of its own, the wire's resistance between it
and the board's end – every feed carries its own current, also where several wires bring one net to the strip. With
`at_m` the cable's wires land on the rails at that place along the strip instead of at the pins they name, each on the
rail of its pin (an injection point).

judge() holds the supply of every section, measured between its two rails, to the pixel's operating range
(vdd_op_min_v … vdd_op_max_v of the entry, LIM.range/strip), reports the first and the last pixel and the current of every
feed, and holds the wires of a feeding cable to the cable's i_max_a (LIM.i); a stress row of the netlist holds the
connector at the board's end of each wire to its contact rating, as for every cable.
"""

from __future__ import annotations

import math

from ..circuit import is_number, limits, strip_pixels, values, wire_h, wire_ohm

KIND = "led_strip"
SECTIONS = 50        # a strip of more pixels is lumped into this many sections
R_MIN = 1e-6         # two places of a rail at one point, a wire of 0 Ω: ngspice takes no 0 Ω resistor
REQUIRED = ("pixels_per_m", "i_pixel_a", "r_vdd_ohm_per_m", "r_gnd_ohm_per_m")
RAILS = {"v": ("vdd", "vdd_end", "r_vdd_ohm_per_m"), "g": ("gnd", "gnd_end", "r_gnd_ohm_per_m")}


def is_strip(design, des):
    return des in design.comps and (design.part(des) or {}).get("kind") == KIND


def feeds(design, cable):
    """Whether a cable runs to an LED strip – split_feeds handles its wires, not the cables between boards."""
    return is_strip(design, cable.get("from")) or is_strip(design, cable.get("to"))


def role_of(design, ref):
    des, _, num = ref.partition(".")
    return (((design.part(des) or {}).get("pins") or {}).get(num) or {}).get("role")


def split_feeds(design):
    """The wires of every cable to an LED strip, once per design (netlist.split_boards, after the cables between
    boards): the strip's pin gets a node of its own ('<net>__<pin>') and the wire runs from the other end's node to it
    (design.cable_elements, the stress of a cable's connector); a cable with at_m lands on the rails at that place
    instead (design.strip_taps, built with the strip)."""
    design.strip_taps = {}
    nets = {ref: n["name"] for n in design.graph["nets"] for ref in n["pins"]}

    def own(ref):                        # a node of the strip pin's own, once
        if not design.pin_net[ref].endswith(f"__{ref}"):
            design.pin_net[ref] = f"{design.pin_net[ref]}__{ref}"
    apart = set()                        # (strip, net) a cable brings from another board
    for cable in design.graph.get("cables", []):
        if not feeds(design, cable):
            continue
        src, dst = cable["from"], cable["to"]
        strip = dst if is_strip(design, dst) else src
        for p_src, p_dst in cable["pins"].items():
            a, b = f"{src}.{p_src}", f"{dst}.{p_dst}"
            if nets.get(a) is None or nets.get(a) != nets.get(b):
                raise ValueError(f"cable {cable['name']}: {a} and {b} are not on the same net")
            mine, other = (b, a) if strip == dst else (a, b)
            if design.comps[strip].get("board") != design.comps[other.split(".", 1)[0]].get("board"):
                apart.add((strip, nets[a]))
            wire = {"name": f"R_{cable['name']}_{p_src}", "des": other.split(".", 1)[0], "pa": other, "pb": mine,
                    "r": max(wire_ohm(cable), R_MIN), "l": wire_h(cable), "cable": cable["name"], "wire": p_src,
                    "strip": strip, "i_max_a": cable.get("i_max_a")}
            if cable.get("at_m") is not None:      # an injection point along the strip
                design.strip_taps.setdefault(strip, []).append({**wire, "at_m": cable["at_m"]})
                continue
            for ref in (a, b):
                if is_strip(design, ref.split(".", 1)[0]):
                    own(ref)
            design.cable_elements.append({**wire, "a": design.pin_net[other], "b": design.pin_net[mine]})
    for strip, net in apart:             # on a board of its own the strip is reached through its cables only: a pin
        for ref in design.nets[net]["pins"]:      # no wire lands on is an open end of its rail
            if ref.split(".", 1)[0] == strip:
                own(ref)


def share_of(load, des):
    """The share of full white a load gives a strip's pixels: its `strips` entry, 0 (dark) without one."""
    x = (load.get("strips") or {}).get(des, 0) if isinstance(load.get("strips"), dict) else 0
    return min(max(float(x), 0.0), 1.0) if is_number(x) else 0.0


def label(sec):
    where = f"{sec['x_m']:.2f} m"
    if sec["first"] == sec["last"]:
        return f"pixel {sec['first']}, {where}"
    return f"pixels {sec['first']}–{sec['last']}, {where}"


def build(nl, des, part):
    """The ladder of the strip `des` in the netlist `nl` (netlist.Netlist.component for the kind led_strip); its
    sections, pins and taps in nl.meta["strips"]. ValueError where the component or the entry lacks what it takes."""
    d, p = nl.d, values(part)
    n, length = strip_pixels(d.comps[des], part)
    if missing := [k for k in REQUIRED if not is_number(p.get(k))]:
        raise ValueError(f"{des}: parts entry {d.entry_key(des)} gives no {', '.join(missing)} – the model of the strip "
                         "needs them (PARTS.fact)")
    share, idle = share_of(nl.load, des), p.get("i_idle_a", 0.0)
    i_px = idle + share * (p["i_pixel_a"] - idle)
    pitch, count = 1 / p["pixels_per_m"], min(n, SECTIONS)
    bounds = [j * n // count for j in range(count + 1)]
    tag = des.lower()
    sections = [{"first": bounds[j] + 1, "last": bounds[j + 1], "n": bounds[j + 1] - bounds[j],
                 "x_m": (bounds[j] + bounds[j + 1]) / 2 * pitch, "v": f"x_{tag}_v{j}", "g": f"x_{tag}_g{j}"}
                for j in range(count)]
    taps = getattr(d, "strip_taps", {}).get(des, [])
    for t in taps:
        if not (is_number(t["at_m"]) and 0 <= t["at_m"] <= length + 1e-9):
            raise ValueError(f"cable {t['cable']}: at_m {t['at_m']!r} – a place along {des}, 0 … {length:g} m")
        if role_of(d, t["pb"]) not in RAILS["v"][:2] + RAILS["g"][:2]:
            raise ValueError(f"cable {t['cable']}: with at_m its wires land on the rails of {des} – {t['pb']} is no "
                             "supply pin (roles vdd, gnd, vdd_end, gnd_end)")
    pins = {}
    for rail, (start, end, r_key) in RAILS.items():
        points = [(sec["x_m"], 1, sec[rail]) for sec in sections]          # (place, order at one place, node)
        for role, x, order in ((start, 0.0, 0), (end, length, 2)):
            hub = f"x_{tag}_{rail}{'s' if order == 0 else 'e'}"
            on = [num for num, info in part["pins"].items() if info.get("role") == role and f"{des}.{num}" in d.pin_net]
            for num in on:
                nl.add(f"V_{des}_F{num} {nl.pn(f'{des}.{num}')} {hub} 0")
                pins[num] = {"x_m": x, "rail": rail, "branch": f"v_{tag}_f{num}#branch"}
            if on:
                points.append((x, order, hub))
        for k, t in enumerate(taps):
            if role_of(d, t["pb"]) in (start, end):
                points.append((t["at_m"], 1, f"x_{tag}_{rail}t{k}"))
        points.sort(key=lambda q: (q[0], q[1]))
        for i, ((x0, _, a), (x1, _, b)) in enumerate(zip(points, points[1:])):
            r = max((x1 - x0) * p[r_key], R_MIN)
            nl.add(f"R_{des}_{rail.upper()}{i} {a} {b} {r:.6g}", des, "strip_rail", (a, b), r)
    for k, t in enumerate(taps):
        node = f"x_{tag}_{'v' if role_of(d, t['pb']) in RAILS['v'][:2] else 'g'}t{k}"
        a = nl.pn(t["pa"])
        if t["l"]:                       # the wire's inductance after its resistance, as a cable's
            nl.add(f"{t['name']} {a} {node}_l {t['r']:.6g}", t["des"], "connector", (a, f"{node}_l"), t["r"])
            nl.add(f"L{t['name'][1:]} {node}_l {node} {t['l']:.6g}")
        else:
            nl.add(f"{t['name']} {a} {node} {t['r']:.6g}", t["des"], "connector", (a, node), t["r"])
        t["node"] = node
    for j, sec in enumerate(sections):
        nl.current_load(f"{des}_P{j}", sec["v"], sec["g"], f"{sec['n'] * i_px:.9g}", des, "strip_pixels")
    nl.meta.setdefault("strips", {})[des] = {"sections": sections, "pins": pins, "taps": [dict(t) for t in taps],
                                             "length_m": length, "pixels": n, "share": share, "i_pixel_a": i_px}


def volt(res, node):
    return 0.0 if node in (None, "0") else res.get(node, math.nan)


def config(s, load):
    """SIM.config: a load's `strips` names LED strips of the graph, each with a share of full white from 0 to 1."""
    st = load.get("strips")
    if st is None:
        return
    want = "a map from each LED strip (kind led_strip) to the share of full white its pixels show, 0 … 1"
    if not isinstance(st, dict):
        s.check("SIM.config", "strips", "strips of the load", repr(st), want, False)
        return
    for des, x in sorted(st.items()):
        if not is_strip(s.d, des):
            s.check("SIM.config", des, "strips of the load", f"{des} is no LED strip of the graph", want, False)
        elif not (is_number(x) and 0 <= x <= 1):
            s.check("SIM.config", des, "strips of the load", repr(x), want, False)


def judge(s, load):
    """Every strip of the scenario `s` (engines/sim.py Scene): the supply of its pixels against the pixel's operating
    range (LIM.range/strip), the first and the last pixel, the current of every feed, a feeding cable's i_max_a."""
    from ..engines.quantities import Limit
    from .netlist import pin_node
    res, d = s.res, s.d
    config(s, load)
    for des, m in sorted(s.meta.get("strips", {}).items()):
        part = s.n.part(des) or {}
        key, r = s.n.entry_key(des), limits(part)
        volts = [(volt(res, sec["v"]) - volt(res, sec["g"]), sec) for sec in m["sections"]]
        (lo, lo_sec), (hi, hi_sec) = min(volts, key=lambda q: q[0]), max(volts, key=lambda q: q[0])
        lims = [Limit(max=r.get("vdd_op_max_v"), min=r.get("vdd_op_min_v"),
                      source=f"vdd_op_min_v … vdd_op_max_v of {key}")] \
            if r.get("vdd_op_min_v") is not None or r.get("vdd_op_max_v") is not None else []
        white = f"{m['share']:.0%} of full white, {m['i_pixel_a'] * 1e3:.3g} mA per pixel"
        s.q(des, "v_pixel", hi if lims else lo, "V", "", des, f"supply of every pixel ({m['pixels']} at {white}) inside "
            "the pixel's operating range", lo=lo, code="LIM.range", entry=False, grade="strip", lims=lims, report=True)
        s.qs[-1].actual = f"{lo:.4g} V ({label(lo_sec)}) … {hi:.4g} V ({label(hi_sec)})"
        for which, (x, sec) in (("first", volts[0]), ("last", volts[-1])):
            s.q(f"{des} {which} pixel", "v_pixel", x, "V", "", des, f"supply of the {which} pixel"
                f"{'s' if sec['n'] > 1 else ''} ({label(sec)})", code="LIM.range", entry=False, report=True)
        for num, pin in sorted(m["pins"].items()):
            i = res.get(pin["branch"], math.nan)
            info = (part.get("pins") or {}).get(num, {})
            name, rated = info.get("name", num), info.get("i_max_a")      # rated: the strip's own lead or connector
            into = i if pin["rail"] == "v" else -i
            s.q(f"{des}.{num}", "i_feed", abs(into) if is_number(rated) else into, "A", "", des,
                f"current {'into' if pin['rail'] == 'v' else 'out of'} {des} at {name} (pin {num}, {pin['x_m']:.3g} m)",
                code="LIM.i", entry=False, report=True, grade="strip" if is_number(rated) else "",
                lims=[Limit(max=rated, derate=s.der.get("i", 1.0), source=f"i_max_a of pin {name} of {key}")]
                if is_number(rated) else [])
        for t in m["taps"]:
            i = (volt(res, pin_node(d, t["pa"])) - volt(res, t["node"])) / t["r"]
            plus = role_of(d, t["pb"]) in RAILS["v"][:2]
            s.q(f"cable {t['cable']}", "i_feed", i if plus else -i, "A", "", None, f"current {'into' if plus else 'out of'}"
                f" {des} through {t['name'][2:]} at {t['at_m']:g} m", entry=False, report=True)
    wires = [w for w in getattr(d, "cable_elements", []) if w.get("strip")]
    wires += [t for m in s.meta.get("strips", {}).values() for t in m["taps"]]
    for w in wires:
        if w.get("i_max_a") is None:
            continue
        far = w["node"] if "node" in w else pin_node(d, w["pb"])
        i = abs(volt(res, pin_node(d, w["pa"])) - volt(res, far)) / w["r"]
        s.q(f"cable {w['cable']}", "i", i, "A", "", None, f"current through wire {w['name'][2:]} (to {w['strip']})",
            code="LIM.i", entry=False, grade="strip",
            lims=[Limit(max=w["i_max_a"], derate=s.der.get("i", 1.0), source=f"i_max_a of cable {w['cable']}")])
