"""Stages P (parts) and G (graph): rule checks on the hardware graph, offline, in well under a second.

    edakit check [--release] [--json FILE]

  G-1  structure: unique names, every pin in exactly one net or "nc", nets with >= 2 pins, a voltage range per net,
       a known board per component, nets across boards only through a cable, layout requirements that name parts
       and pins of the graph (handover.py), purpose.use private, gift or sale, check settings that name parts of
       the graph, a ground net that exists
  G-2  pin locks: pins the firmware relies on are on the expected nets (checks.pin_locks of the graph), and an
       optional pin table in a Markdown document matches the graph (checks.doc_pin_table)
  G-3  voltage domains: net voltage range within the pin limits (vmax) from the parts database
  G-4  no floating inputs; an input driven only by MCU pins needs a pull resistor; transistors need a base resistor,
       MOSFETs a gate resistor to their source or a rail
  G-5  at most one push-pull output or supply output per net
  G-6  decoupling: per net at least one capacitor to ground per IC supply pin (power_in)
  G-8  voltage ratings of capacitors, diodes, transistors, MOSFETs, fuses, switches, connectors with margin
  G-10 reverse polarity: what a reversed source (battery holders, checks.reverse_protect) reaches through fuses,
       switches and connectors is only capacitors, the anode of a blocking diode or the drain of a PMOS
  G-11 I2C lines (net "bus": "i2c", a net name with SDA/SCL, pin role sda/scl, or a pin named SDA/SCL without a
       role) have a pull-up to a supply between (V - 0.4 V) / 3 mA and 10 kOhm; pins with "pull": "up" (and
       "pull_ohm") count
  G-12 strapping pins ("strap": "high"|"low" in the parts entry) are at that level at reset: no pull, ground, supply
       or output on their net that says otherwise, and something (an external pull or "pull" of the pin) holds them
  G-13 flyback diode across inductive loads (relay coil, buzzer with coil_ohm) that a transistor or an output
       switches: cathode at the positive terminal
  G-14 USB-C sink: CC1 and CC2 of a receptacle (role cc1/cc2) each with its own 5.1 kOhm ± 10 % to ground, unless
       an IC (a Type-C controller) is on the CC lines
  G-15 pin functions: a net's "fn" (pwm, adc, spi.sck, i2c.sda, uart.tx, …) is on a pin whose parts entry lists it
       in "functions", the nets of one "fn_bus" on one peripheral instance, PWM nets of one slice with one fixed
       "pwm_hz" and a channel each; a pin without "functions" is a note
  G-16 ground and supply pins: a ground pin on the ground net (or one joined to it by an inductor, or in the graph's
       "grounds"), a supply pin (power_in) on a net that a supply reaches – a power output, a battery holder, a
       connector with a vbus pin or in checks.reverse_protect, a sim source – directly or through fuses, switches,
       connectors, inductors, MOSFETs, resistors up to 100 Ohm and diodes in forward direction
  P-1  graph pins (number + name) = parts database, an entry exists for every LCSC number – or, for a part bought
       elsewhere, for its manufacturer part number `part`
  P-3  own parts (part.py): a board copied from its project with `edakit part own` is that project's current
       datasheet, copied from a commit (pending otherwise); a board that is not released is a warning; the project's
       own datasheets (hardware/datasheet/) are of its current state
  G-9  sign-off: every part verified against its datasheet, no open "verify" notes (pending, blocks only the release)

0 Ω bridges (resistors with value_ohm 0 in the parts entry) join their nets: G-4, G-5, G-6, G-10 to G-16 see the
joined nets as one net under the group's name (the ground net if it is one of them, else the first in the graph) and
the bridges as copper; G-1, G-2, G-3, G-8, P-1 and G-9 see every net and part as the graph has them.

Rule, reason, fix and sources of every check: rules.json (`edakit rules G-4`). A failed check is explained once
below the findings. A finding listed in "waive" of the net or component is accepted on purpose and reported with
its reason. Exit code 1 on errors; with --release also on pending sign-offs.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import handover, rules

CAP_FACTOR = 1.5      # rated voltage >= 1.5 x max. voltage across
DIODE_FACTOR = 1.5    # VRRM >= 1.5 x max. reverse voltage
BJT_FACTOR = 1.5      # VCEO, VDS, VGS >= 1.5 x max.
ACTIVE_TYPES = {"input", "output", "bidirectional", "power_in", "power_output", "analog", "current_sink"}
BOOT_DRIVERS = {"output", "power_output", "ground"}   # define their net while the firmware is not running
PASS_THROUGH = ("fuse", "switch", "connector")        # pass a reversed source on unchanged
REVERSE_OK = ("battery_holder", "capacitor") + PASS_THROUGH
PURPOSES = ("private", "gift", "sale")                 # purpose.use of the graph: built for oneself, given away, sold
CHECK_KEYS = ("pin_locks", "reverse_protect", "doc_pin_table")   # checks of the graph
I2C_SINK_A, I2C_VOL, I2C_R_MAX = 0.003, 0.4, 10e3    # UM10204 7.1: Rp(min) = (V - VOL) / 3 mA; 10 k for 100 kHz
USB_RD, USB_RD_TOL = 5100, 0.10                      # USB Type-C sink termination Rd
COILS = {"relay": ("coil_plus", "coil_minus"), "buzzer": ("plus", "minus")}   # inductive kinds: their coil roles
FN_LINES = {"pwm": (), "adc": (), "spi": ("sck", "tx", "rx", "cs"), "i2c": ("sda", "scl"), "uart": ("tx", "rx")}
FN_NAMES = [k + (f".{line}" if line else "") for k, lines in FN_LINES.items() for line in lines or [""]]   # net fn
SUPPLY_R_MAX = 100                                   # a resistor up to this passes a supply (shunt, filter)
PIN_FUNCTION = re.compile(r"([a-z][a-z0-9]*?)(\d+)(?:\.([a-z]+))?")   # "spi0.sck", "i2c1.sda", "pwm1.a", "adc0"

EXECUTED = ["G-1", "G-2", "G-3", "G-4", "G-5", "G-6", "G-8", "G-10", "G-11", "G-12", "G-13", "G-14", "G-15", "G-16",
            "P-1", "P-3", "G-9"]


class Report:
    def __init__(self):
        self.errors, self.pending, self.waived = [], [], []
        self.warnings, self.notes = [], []   # a warning the gate wants accepted in the sign-off file; information

    def error(self, check, msg, waive=None):
        if waive and check in waive:
            self.waived.append((check, msg, waive[check]))
        else:
            self.errors.append((check, msg))

    def to_dict(self):
        return {"errors": [{"check": c, "msg": m} for c, m in self.errors],
                "pending": [{"check": c, "msg": m} for c, m in self.pending],
                "waived": [{"check": c, "msg": m, "reason": r} for c, m, r in self.waived],
                "warnings": [{"check": c, "msg": m} for c, m in self.warnings],
                "notes": [{"check": c, "msg": m} for c, m in self.notes]}


def v_range(net):
    v = net.get("v")
    return v if isinstance(v, list) and len(v) == 2 and v[0] <= v[1] else [0, 0]


def ohm(x):
    return f"{x / 1000:.3g} kΩ" if x >= 1000 else f"{x:.3g} Ω"


def supply_nets(d):
    """Nets that carry a supply: a supply output or an IC supply pin is on them (ground excluded)."""
    return {name for name, net in d.nets.items() if name != d.ground
            and any(d.pin_info(r).get("type") in ("power_output", "power_in") for r in net["pins"])}


def resistor_value(d, des):
    part = d.part(des) or {}
    return (part.get("params") or {}).get("value_ohm") if part.get("kind") == "resistor" else None


def resistors_to(d, net, targets):
    """(designator, value or None, other net) of every resistor between `net` and one of the `targets` nets."""
    out = []
    for des, a, b in resistor_like(d):
        if net in (a, b) and (other := b if a == net else a) in targets:
            out.append((des, resistor_value(d, des), other))
    return out


def check_structure(d, rep, boards):
    g = d.graph
    for des, n in Counter(c["designator"] for c in g["components"]).items():
        if n > 1:
            rep.error("G-1", f"duplicate designator {des}")
    for name, n in Counter(n["name"] for n in g["nets"]).items():
        if n > 1:
            rep.error("G-1", f"duplicate net {name}")
    used = Counter()
    for net in g["nets"]:
        if len(net["pins"]) < 2:
            rep.error("G-1", f"net {net['name']} has fewer than two pins", net.get("waive"))
        for ref in net["pins"]:
            des, _, pin = ref.partition(".")
            if des not in d.comps:
                rep.error("G-1", f"net {net['name']}: unknown component {des}")
            elif pin not in d.comps[des]["pins"]:
                rep.error("G-1", f"net {net['name']}: {des} has no pin {pin}")
            used[ref] += 1
    for des, c in d.comps.items():
        nc = {str(p) for p in c.get("nc", [])}
        for pin in c["pins"]:
            ref = f"{des}.{pin}"
            if pin in nc and used[ref]:
                rep.error("G-1", f"{ref} is marked nc but used in net {d.pin_net[ref]}")
            elif pin not in nc and used[ref] == 0:
                rep.error("G-1", f"{ref} ({c['pins'][pin]}) is neither connected nor nc")
        for p in sorted(nc - set(c["pins"])):
            rep.error("G-1", f"{des}.{p} in nc but not a pin")
        if boards and c.get("board") not in boards:
            rep.error("G-1", f"{des}: 'board' must be one of {sorted(boards)} (edakit.toml [boards])")
    for ref, n in used.items():
        if n > 1:
            rep.error("G-1", f"{ref} used in {n} nets")
    for net in g["nets"]:
        v = net.get("v")
        if not (isinstance(v, list) and len(v) == 2 and v[0] <= v[1]):
            rep.error("G-1", f"net {net['name']}: missing or invalid voltage range 'v'")
    cable_pins = set()
    for cab in g.get("cables", []):
        for a, b in cab["pins"].items():
            ref_a, ref_b = f"{cab['from']}.{a}", f"{cab['to']}.{b}"
            cable_pins |= {ref_a, ref_b}
            if d.pin_net.get(ref_a) != d.pin_net.get(ref_b):
                rep.error("G-1", f"cable {cab['name']}: {ref_a} and {ref_b} are on different nets")
    for net in g["nets"]:
        on = {d.comps[r.partition(".")[0]].get("board") for r in net["pins"] if r.partition(".")[0] in d.comps}
        if len(on) > 1 and not cable_pins & set(net["pins"]):
            rep.error("G-1", f"net {net['name']} spans several boards without a cable")
    for problem in handover.problems(d):
        rep.error("G-1", problem)
    if "purpose" in g and (g["purpose"] or {}).get("use") not in PURPOSES:
        rep.error("G-1", f"purpose.use must be one of {', '.join(PURPOSES)} – the regulatory review (M-6) starts there")
    for problem in settings_problems(d):
        rep.error("G-1", problem)


def settings_problems(d):
    """The ground net and the check settings of the graph name what the graph has."""
    g, out = d.graph, []
    if "ground" in g and g["ground"] not in d.nets:
        out.append(f"ground: no net {g['ground']} in the graph")
    checks = g.get("checks") or {}
    out += [f"checks: unknown key '{k}' (known: {', '.join(CHECK_KEYS)})" for k in checks if k not in CHECK_KEYS]
    named = [("pin_locks", ref.partition(".")[0]) for ref in checks.get("pin_locks") or {}]
    named += [("reverse_protect", des) for des in checks.get("reverse_protect") or []]
    if checks.get("doc_pin_table"):
        named.append(("doc_pin_table", checks["doc_pin_table"].get("component")))
    out += [f"checks.{key}: no part {des} in the graph" for key, des in named if des not in d.comps]
    return out


def check_pin_locks(d, rep, checks, root):
    for ref, net in (checks.get("pin_locks") or {}).items():
        if d.pin_net.get(ref) != net:
            rep.error("G-2", f"{ref} expected on net {net}, found {d.pin_net.get(ref)}")
    table = checks.get("doc_pin_table")
    if not table or table.get("component") not in d.comps:   # an unknown component is G-1's
        return
    doc = Path(root) / table["file"]
    comp = table["component"]
    prefix = table.get("prefix", "GP")
    regex = re.compile(table.get("regex", r"^\|.*?\|\s*\*\*" + re.escape(prefix) + r"(\d+)"), re.M)
    used = {int(m.group(1)) for num, name in d.comps[comp]["pins"].items()
            if (m := re.match(re.escape(prefix) + r"(\d+)", name)) and f"{comp}.{num}" in d.pin_net}
    if not doc.exists():
        rep.error("G-2", f"pin table {table['file']} not found")
        return
    listed = {int(n) for n in regex.findall(doc.read_text(encoding="utf-8"))}
    for n in sorted(used - listed):
        rep.error("G-2", f"{prefix}{n} is connected in the graph but missing in the pin table of {table['file']}")
    for n in sorted(listed - used):
        rep.error("G-2", f"{prefix}{n} is in the pin table of {table['file']} but not connected in the graph")


def check_domains(d, rep):
    for name, net in d.nets.items():
        lo, hi = v_range(net)
        for ref in net["pins"]:
            info = d.pin_info(ref)
            if "vmax" in info and hi > info["vmax"]:
                rep.error("G-3", f"{name} up to {hi} V, but {ref} ({info['name']}) allows {info['vmax']} V",
                          net.get("waive"))
            if info.get("type") in ACTIVE_TYPES and lo < -0.3:
                rep.error("G-3", f"{name} down to {lo} V at {ref} ({info['name']})", net.get("waive"))


def resistor_like(d):
    """(des, net_a, net_b) for every resistive two-pole incl. both halves of a potentiometer."""
    out = []
    for des in d.comps_of_kind("resistor", "potentiometer"):
        nets = [d.pin_net.get(f"{des}.{p}") for p, info in d.part(des)["pins"].items() if info.get("type") == "passive"]
        out += [(des, a, b) for i, a in enumerate(nets) for b in nets[i + 1:] if a and b]
    return out


def check_inputs(d, rep):
    rails = {name for name, net in d.nets.items()
             if any(d.pin_info(r).get("type") in BOOT_DRIVERS for r in net["pins"])}
    pulls = defaultdict(list)
    for des, a, b in resistor_like(d):
        if b in rails:
            pulls[a].append(des)
        if a in rails:
            pulls[b].append(des)
    for name, net in d.nets.items():
        types = [d.pin_info(r).get("type") for r in net["pins"]]
        if "input" not in types:
            continue
        drivers = [t for t in types if t in BOOT_DRIVERS | {"bidirectional"}]
        if not drivers and not pulls[name]:
            rep.error("G-4", f"{name}: input without driver or pull resistor", net.get("waive"))
        elif not any(t in BOOT_DRIVERS for t in types) and not pulls[name]:
            rep.error("G-4", f"{name}: only MCU pins drive this input – floating until the firmware runs",
                      net.get("waive"))
    for des in d.comps_of_kind("npn", "pnp"):
        base, emitter = d.net_of(des, "base"), d.net_of(des, "emitter")
        if not any({a, b} == {base, emitter} for _, a, b in resistor_like(d)):
            rep.error("G-4", f"{des}: no base-emitter resistor – state undefined while the firmware is not running",
                      d.comps[des].get("waive"))
    held = rails | supply_nets(d)
    for des in d.comps_of_kind("nmos", "pmos"):
        gate, source = d.net_of(des, "gate"), d.net_of(des, "source")
        if gate is None or gate in held:
            continue
        if not resistors_to(d, gate, held | {source}):
            rep.error("G-4", f"{des}: no resistor from the gate to its source or a rail – the MOSFET is undefined while "
                             "the firmware is not running", d.comps[des].get("waive"))


def check_contention(d, rep):
    for name, net in d.nets.items():
        drivers = [r for r in net["pins"] if d.pin_info(r).get("type") in ("output", "power_output")]
        if len(drivers) > 1:
            rep.error("G-5", f"{name}: several outputs drive this net: {', '.join(drivers)}", net.get("waive"))


def check_decoupling(d, rep):
    gnd = d.ground
    caps = Counter()
    for des in d.comps_of_kind("capacitor"):
        a, b = d.pin_net.get(f"{des}.1"), d.pin_net.get(f"{des}.2")
        if gnd in (a, b):
            caps[b if a == gnd else a] += 1
    for name, net in d.nets.items():
        supply = [r for r in net["pins"] if d.pin_info(r).get("type") == "power_in"]
        if supply and caps[name] < len(supply):
            rep.error("G-6", f"{name}: {len(supply)} IC supply pins ({', '.join(supply)}) "
                             f"but {caps[name]} capacitor(s) to {gnd}", net.get("waive"))


def check_ratings(d, rep):
    def rng(net):
        return v_range(d.nets[net]) if net else [0, 0]

    def across(a, b):
        (alo, ahi), (blo, bhi) = rng(a), rng(b)
        return max(abs(ahi - blo), abs(bhi - alo))

    for des in d.comps:
        part, comp = d.part(des), d.comps[des]
        if not part:
            continue
        kind, r = part["kind"], part.get("ratings", {})
        waive = comp.get("waive")
        nets = [d.pin_net.get(f"{des}.{p}") for p in part["pins"]]
        if kind == "capacitor" and "v_max" in r:
            v = across(*nets[:2])
            if v * CAP_FACTOR > r["v_max"]:
                rep.error("G-8", f"{des}: up to {v:.1f} V, rated {r['v_max']} V (needs ×{CAP_FACTOR})", waive)
        elif kind == "diode" and "vrrm" in r:
            a, k = d.net_of(des, "anode"), d.net_of(des, "cathode")
            vr = rng(k)[1] - rng(a)[0]
            if vr * DIODE_FACTOR > r["vrrm"]:
                rep.error("G-8", f"{des}: reverse up to {vr:.1f} V, VRRM {r['vrrm']} V", waive)
        elif kind in ("npn", "pnp") and "vceo" in r:
            v = across(d.net_of(des, "collector"), d.net_of(des, "emitter"))
            if v * BJT_FACTOR > r["vceo"]:
                rep.error("G-8", f"{des}: |VCE| up to {v:.1f} V, VCEO {r['vceo']} V", waive)
        elif kind in ("pmos", "nmos"):
            s = d.net_of(des, "source")
            for label, other, lim in (("VDS", d.net_of(des, "drain"), r.get("vds_max")),
                                      ("VGS", d.net_of(des, "gate"), r.get("vgs_max"))):
                v = across(other, s)
                if lim is not None and v * BJT_FACTOR > lim:
                    rep.error("G-8", f"{des}: |{label}| up to {v:.1f} V, rated {lim} V", waive)
        elif kind in ("fuse", "switch", "dip_switch", "button", "potentiometer", "resistor", "buzzer", "connector"):
            v = max((abs(x) for n in nets if n for x in rng(n)), default=0)
            if "v_max" in r and v > r["v_max"]:
                rep.error("G-8", f"{des}: nets up to {v:.1f} V, rated {r['v_max']} V", waive)


def check_reverse(d, rep, sources=()):
    """G-10 from the topology instead of the declared ranges: nets a reversed source reaches through pass-through
    parts may only touch holders, capacitors, pass-through parts, the anode of a diode whose cathode is outside, or
    the drain of a PMOS whose source and gate are outside (body diode blocks, VGS <= 0)."""
    gnd = d.ground
    starts = set(d.comps_of_kind("battery_holder")) | set(sources)
    side = {d.pin_net.get(f"{h}.{p}") for h in starts if d.part(h) for p in d.part(h)["pins"]} - {None, gnd}
    todo = list(side)
    while todo:
        net = todo.pop()
        for ref in d.nets[net]["pins"]:
            des = ref.split(".", 1)[0]
            if des in starts or (d.part(des) or {}).get("kind") not in PASS_THROUGH:
                continue
            for p in d.part(des)["pins"]:
                n = d.pin_net.get(f"{des}.{p}")
                if n and n != gnd and n not in side:
                    side.add(n)
                    todo.append(n)
    for net in sorted(side):
        for ref in d.nets[net]["pins"]:
            des = ref.split(".", 1)[0]
            part = d.part(des) or {}
            if part.get("kind") in REVERSE_OK or not part:
                continue
            role = d.pin_info(ref).get("role")
            if part.get("kind") == "diode" and role == "anode" and d.net_of(des, "cathode") not in side:
                continue
            if part.get("kind") == "pmos" and role == "drain" and d.net_of(des, "source") not in side \
                    and d.net_of(des, "gate") not in side:
                continue
            rep.error("G-10", f"{ref} on {net}: a reversed source reaches this pin without a blocking device",
                      d.nets[net].get("waive"))


def i2c_name(text):
    """'sda' or 'scl' if the name contains SDA or SCL as a word ('SDA/SDI', 'I2C0_SCL' yes, 'GP4' no)."""
    tokens = set(re.split(r"[^A-Z0-9]+", str(text).upper()))
    return next((t.lower() for t in ("SDA", "SCL") if t in tokens), None)


def i2c_line(info):
    """'sda' or 'scl' from the pin's role, or from its name if it has no role."""
    if info.get("role"):
        return info["role"] if info["role"] in ("sda", "scl") else None
    return i2c_name(info.get("name", ""))


def check_i2c(d, rep):
    supplies = supply_nets(d)
    for name, net in d.nets.items():
        names = net.get("joined") or [name]
        if net.get("bus") != "i2c" and not any(map(i2c_name, names)) and \
                not any(i2c_line(d.pin_info(r)) for r in net["pins"]):
            continue
        waive = net.get("waive")
        pulls = [(r, rail) for _, r, rail in resistors_to(d, name, supplies)]
        pulls += [(d.pin_info(r).get("pull_ohm"), None) for r in net["pins"] if d.pin_info(r).get("pull") == "up"]
        if not pulls:
            rep.error("G-11", f"{name}: I2C line without a pull-up to a supply – the outputs are open-drain", waive)
            continue
        if any(r is None for r, _ in pulls):
            continue  # a pull-up of unknown value: its presence is all that can be checked
        r_eff = 1 / sum(1 / r for r, _ in pulls)
        v = max([v_range(d.nets[rail])[1] for _, rail in pulls if rail] or [v_range(net)[1]])
        r_min = (v - I2C_VOL) / I2C_SINK_A
        if r_eff > I2C_R_MAX:
            rep.error("G-11", f"{name}: pull-up {ohm(r_eff)} – above {ohm(I2C_R_MAX)}, the rising edges get too slow",
                      waive)
        elif r_eff < r_min:
            rep.error("G-11", f"{name}: pull-up {ohm(r_eff)} – below ({v} V − {I2C_VOL} V) / 3 mA = {ohm(r_min)}, a "
                              "device cannot pull the line low enough", waive)


def check_straps(d, rep):
    """G-12: what holds a strapping pin at reset – pulls, rails and outputs on its net, else the pin's own pull."""
    supplies = supply_nets(d)
    for des in d.comps:
        for num, info in ((d.part(des) or {}).get("pins") or {}).items():
            ref, want = f"{des}.{num}", info.get("strap")
            net = d.pin_net.get(ref)
            if want not in ("high", "low") or net is None:
                continue
            forces = []  # (level, by)
            for r in d.nets[net]["pins"]:
                t = d.pin_info(r).get("type")
                if r != ref and t in ("ground", "power_output", "power_in", "output"):
                    forces.append(({"ground": "low", "output": "driven"}.get(t, "high"), r))
            forces += [("low", r) for r, _, _ in resistors_to(d, net, {d.ground})]
            forces += [("high", r) for r, _, _ in resistors_to(d, net, supplies)]
            what, waive = f"{ref} ({info['name']}) must be {want} at reset", d.nets[net].get("waive")
            driven = [by for lvl, by in forces if lvl == "driven"]
            wrong = [by for lvl, by in forces if lvl not in (want, "driven")]
            if driven:
                rep.error("G-12", f"{what}, but {', '.join(driven)} drives it – its level at power-up is not "
                                  "defined by the graph", waive)
            if wrong:
                rep.error("G-12", f"{what}, but {', '.join(wrong)} holds it {'low' if want == 'high' else 'high'}",
                          waive)
            elif not forces and info.get("pull") != {"high": "up", "low": "down"}[want]:
                rep.error("G-12", f"{what}, but nothing holds it there: no pull on {net} and no internal pull "
                                  "in the parts entry", waive)


def check_flyback(d, rep):
    for des in d.comps_of_kind(*COILS):
        part = d.part(des)
        if part["kind"] == "buzzer" and "coil_ohm" not in (part.get("params") or {}):
            continue  # a piezo buzzer has no coil
        plus, minus = (d.net_of(des, role) for role in COILS[part["kind"]])
        if not plus or not minus or plus == minus:
            continue
        switches = [q for q in d.comps_of_kind("npn", "pnp", "nmos", "pmos")
                    if {d.net_of(q, "collector"), d.net_of(q, "drain")} & {plus, minus}]
        switches += [r for n in (plus, minus) for r in d.nets[n]["pins"]
                     if d.pin_info(r).get("type") in ("output", "bidirectional")]
        if switches and not any(d.net_of(x, "cathode") == plus and d.net_of(x, "anode") == minus
                                for x in d.comps_of_kind("diode")):
            rep.error("G-13", f"{des}: coil switched by {', '.join(switches)} without a diode across it (cathode at "
                              f"{plus}, anode at {minus})", d.comps[des].get("waive"))


def cc_lines(d, des):
    """{'cc1': net, 'cc2': net} of a USB-C receptacle: pins by role, by name if they have no role."""
    out = {}
    for num, info in d.part(des)["pins"].items():
        line = (info.get("role") or str(info.get("name", ""))).lower()
        if line in ("cc1", "cc2"):
            out[line] = d.pin_net.get(f"{des}.{num}")
    return out


def check_usb_c(d, rep):
    for des in d.comps_of_kind("connector"):
        cc = cc_lines(d, des)
        if set(cc) != {"cc1", "cc2"}:
            continue
        if any(d.pin_info(r).get("type") not in (None, "passive") for n in cc.values() if n
               for r in d.nets[n]["pins"] if not r.startswith(f"{des}.")):
            continue  # a Type-C or PD controller drives the CC lines
        waive = d.comps[des].get("waive")
        if cc["cc1"] and cc["cc1"] == cc["cc2"]:
            rep.error("G-14", f"{des}: CC1 and CC2 on one net {cc['cc1']} – each needs its own {ohm(USB_RD)} to "
                              f"{d.ground}", waive)
            continue
        for line, net in sorted(cc.items()):
            if net is None:
                rep.error("G-14", f"{des}: {line.upper()} not connected – a USB-C source switches VBUS on only with "
                                  f"{ohm(USB_RD)} to {d.ground} on each CC pin", waive)
                continue
            rd = resistors_to(d, net, {d.ground})
            known = [r for _, r, _ in rd if r is not None]
            if not rd:
                rep.error("G-14", f"{des}: {line.upper()} ({net}) without a resistor to {d.ground} – needs "
                                  f"{ohm(USB_RD)}", waive)
            elif known and not any(abs(r - USB_RD) <= USB_RD * USB_RD_TOL for r in known):
                rep.error("G-14", f"{des}: {line.upper()} ({net}) has {', '.join(ohm(r) for r in known)} to "
                                  f"{d.ground} – needs {ohm(USB_RD)} ± {USB_RD_TOL:.0%}", waive)


def fn_match(fn, function):
    """(instance, line) if the pin function serves the net's fn: 'spi.tx' and 'spi0.tx' -> ('0', 'tx'); 'pwm' and
    'pwm1.b' -> ('1', 'b') – slice and channel; 'adc' and 'adc0' -> ('0', None)."""
    m = PIN_FUNCTION.fullmatch(str(function))
    kind, _, line = fn.partition(".")
    if not m or m[1] != kind or (line and m[3] != line):
        return None
    return m[2], m[3]


def hz_text(hz):
    if hz is None:
        return "pwm_hz missing"
    return f"{hz[0]:g}–{hz[1]:g} Hz" if isinstance(hz, list) else f"{hz:g} Hz"


def valid_hz(hz):
    def num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0
    return hz is None or num(hz) or (isinstance(hz, list) and len(hz) == 2 and all(map(num, hz)) and hz[0] <= hz[1])


def check_pin_functions(d, rep):
    """G-15: the pin of a net with `fn` has that function (`functions` of its parts entry), the nets of one `fn_bus`
    use one peripheral instance per part, PWM nets of one slice have one fixed `pwm_hz` and a channel each."""
    hits = {}   # net -> [(ref, instance, line)] of the pins that serve its fn
    for name, net in sorted(d.nets.items()):
        fn, waive = net.get("fn"), net.get("waive")
        if not valid_hz(net.get("pwm_hz")):
            rep.error("G-15", f"{name}: pwm_hz must be a frequency in Hz or [min, max], not {net['pwm_hz']!r}", waive)
        if not fn:
            continue
        if fn not in FN_NAMES:
            rep.error("G-15", f"{name}: unknown fn {fn!r} (known: {', '.join(FN_NAMES)})", waive)
            continue
        known = [(r, d.pin_info(r)) for r in net["pins"] if isinstance(d.pin_info(r).get("functions"), list)]
        if not known:
            rep.notes.append(("G-15", f"{name}: needs {fn}, but no pin on it has functions in its parts entry – not "
                                      "checked"))
            continue
        hits[name] = [(r, *m) for r, info in known for f in info["functions"] if (m := fn_match(fn, f))]
        if not hits[name]:
            has = "; ".join(f"{r} ({info['name']}) has " + (", ".join(info["functions"]) or "no free function")
                            for r, info in known)
            rep.error("G-15", f"{name}: needs {fn}, but {has}", waive)
    buses = defaultdict(dict)   # (bus, peripheral, part) -> {net: {instance: pin}}
    for name, pins in hits.items():
        if bus := d.nets[name].get("fn_bus"):
            for ref, inst, _ in pins:
                buses[(bus, d.nets[name]["fn"].partition(".")[0], ref.partition(".")[0])].setdefault(name, {})[inst] = ref
    for (bus, kind, des), nets in sorted(buses.items()):
        if len(nets) > 1 and not set.intersection(*map(set, nets.values())):
            waive = {k: v for n in nets for k, v in (d.nets[n].get("waive") or {}).items()}
            on = ", ".join(f"{n} on " + "/".join(f"{kind}{i}" for i in sorted(inst)) + " ("
                           + ", ".join(inst[i] for i in sorted(inst)) + ")" for n, inst in sorted(nets.items()))
            rep.error("G-15", f"bus {bus}: {on} – the nets of one bus need one {kind} of {des}", waive)
    slices = defaultdict(list)   # (part, slice) -> [(net, channel, ref)]
    for name, pins in hits.items():
        if d.nets[name]["fn"] == "pwm":
            for ref, inst, channel in pins:
                slices[(ref.partition(".")[0], inst)].append((name, channel, ref))
    for (des, inst), users in sorted(slices.items()):
        for i, (a, ch_a, ref_a) in enumerate(users):
            for b, ch_b, ref_b in users[i + 1:]:
                if a == b:
                    continue
                waive = {**(d.nets[b].get("waive") or {}), **(d.nets[a].get("waive") or {})}
                hz_a, hz_b = d.nets[a].get("pwm_hz"), d.nets[b].get("pwm_hz")
                where = f"PWM slice {inst} of {des} ({ref_a}, {ref_b})"
                if ch_a == ch_b:
                    rep.error("G-15", f"{a} and {b} on the same PWM channel pwm{inst}.{ch_a} of {des} ({ref_a}, "
                                      f"{ref_b}) – one output for both", waive)
                elif hz_a is None or hz_b is None:
                    rep.error("G-15", f"{a} ({hz_text(hz_a)}) and {b} ({hz_text(hz_b)}) share {where} – give both "
                                      "their pwm_hz: a slice has one frequency", waive)
                elif isinstance(hz_a, list) or isinstance(hz_b, list):
                    rep.error("G-15", f"{a} ({hz_text(hz_a)}) and {b} ({hz_text(hz_b)}) share {where} – a slice has "
                                      "one frequency, a net whose frequency changes needs a slice of its own", waive)
                elif hz_a != hz_b:
                    rep.error("G-15", f"{a} ({hz_text(hz_a)}) and {b} ({hz_text(hz_b)}) share {where} – a slice has "
                                      "one frequency", waive)


def supply_inputs(d, sim=None):
    """Nets a supply feeds: power outputs, and where the supply comes in (the design hint H-1's power inputs) – the
    plus of a battery holder, the vbus pins of a connector, every pin of a connector in checks.reverse_protect, the
    plus of a simulation source."""
    out = {n for n, net in d.nets.items() if any(d.pin_info(r).get("type") == "power_output" for r in net["pins"])}
    protect = set((d.graph.get("checks") or {}).get("reverse_protect") or [])
    for des in d.comps:
        part = d.part(des) or {}
        roles = {num: str(p.get("role") or "") for num, p in (part.get("pins") or {}).items()}
        if part.get("kind") == "battery_holder":
            take = [n for n, r in roles.items() if r.startswith("plus")] or list(roles)
        elif part.get("kind") == "connector" and "vbus" in roles.values():
            take = [n for n, r in roles.items() if r == "vbus"]
        elif des in protect:
            take = list(roles)
        else:
            continue
        out |= {d.pin_net.get(f"{des}.{n}") for n in take}
    for des, src in ((sim or {}).get("sources") or {}).items():
        if des in d.comps and isinstance(src, dict) and "plus" in src:
            out.add(d.pin_net.get(f"{des}.{src['plus']}"))
    return out - {None}


def supply_paths(d):
    """{net: nets a supply reaches from it through one part}: fuses, switches, connectors and inductors (every pin),
    MOSFETs (drain and source), resistors up to SUPPLY_R_MAX both ways, diodes from anode to cathode."""
    nxt = defaultdict(set)
    for des in d.comps:
        part = d.part(des) or {}
        kind, value = part.get("kind"), resistor_value(d, des)
        if kind == "diode":
            a, k = d.net_of(des, "anode"), d.net_of(des, "cathode")
            if a and k:
                nxt[a].add(k)
            continue
        if kind in ("nmos", "pmos"):
            nets = {d.net_of(des, "drain"), d.net_of(des, "source")}
        elif kind in PASS_THROUGH + ("inductor",) or (value is not None and value <= SUPPLY_R_MAX):
            nets = {d.pin_net.get(f"{des}.{p}") for p in part.get("pins") or {}}
        else:
            continue
        for n in nets - {None}:
            nxt[n] |= nets - {None, n}
    return nxt


def reach(starts, nxt, stop=()):
    seen, todo = set(starts), list(starts)
    while todo:
        for n in nxt.get(todo.pop(), ()):
            if n not in seen and n not in stop:
                seen.add(n)
                todo.append(n)
    return seen


def check_power_pins(d, rep, sim=None):
    """G-16: ground pins on ground, supply pins on a net that a supply reaches."""
    alias = {a: name for name, net in d.nets.items() for a in net.get("joined") or [name]}   # 0 Ω bridges joined
    named = d.graph.get("grounds") or []
    for n in named:
        if n not in alias:
            rep.error("G-16", f"grounds: no net {n} in the graph")
    inductors = defaultdict(set)
    for des in d.comps_of_kind("inductor"):
        nets = {d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"]} - {None}
        for n in nets:
            inductors[n] |= nets - {n}
    grounds = reach({d.ground} | {alias[n] for n in named if n in alias}, inductors)
    supplied = reach(supply_inputs(d, sim) - grounds, supply_paths(d), stop=grounds)
    for des in d.comps:
        for num, info in ((d.part(des) or {}).get("pins") or {}).items():
            ref, net = f"{des}.{num}", d.pin_net.get(f"{des}.{num}")
            if net is None:
                continue
            what, waive = f"{ref} ({info.get('name', num)}) on {net}", d.nets[net].get("waive")
            if info.get("type") == "ground" and net not in grounds:
                rep.error("G-16", f"{what}, not on {d.ground}", waive)
            elif info.get("type") == "power_in" and net in grounds:
                rep.error("G-16", f"{what}: a supply pin on ground", waive)
            elif info.get("type") == "power_in" and net not in supplied:
                rep.error("G-16", f"{what}: nothing supplies this net", waive)


def check_part_pins(d, rep):
    for des, c in d.comps.items():
        if not c.get("lcsc") and not c.get("part"):
            continue   # a bare test pad: no part to buy, no entry
        part = d.part(des)
        if not part:
            rep.error("P-1", f"{des}: no parts entry " + (f"{c['lcsc']}.json" if c.get("lcsc")
                                                          else f"with mpn {c['part']}"))
            continue
        want = {k: v["name"] for k, v in part["pins"].items()}
        if c["pins"] != want:
            only_g = {k: v for k, v in c["pins"].items() if want.get(k) != v}
            only_p = {k: v for k, v in want.items() if c["pins"].get(k) != v}
            rep.error("P-1", f"{des}: pins differ from parts entry {d.entry_key(des)}: graph {only_g} vs parts {only_p}")
        for pin in c.get("nc", []):
            if part["pins"].get(str(pin), {}).get("type") == "power_in":
                rep.error("P-1", f"{des}.{pin} ({part['pins'][str(pin)]['name']}) is a supply pin but marked nc",
                          c.get("waive"))


def check_signoff(d, rep):
    for key in sorted({d.entry_key(des) for des in d.comps} - {None}):
        part = d.parts[key]
        if not part.get("verified"):
            users = [des for des in d.comps if d.entry_key(des) == key]
            rep.pending.append(("G-9", f"{key} {part.get('mpn', '')} ({', '.join(users)}) not verified against "
                                       "its datasheet"))
    for des, c in d.comps.items():
        if c.get("verify"):
            rep.pending.append(("G-9", f"{des}: open note 'verify': {c['verify']}"))
        if not c.get("lcsc") and not c.get("easyeda_device"):
            msg = f"{des}: neither an LCSC part nor an EasyEDA device"
            if (c.get("waive") or {}).get("G-9"):
                rep.waived.append(("G-9", msg, c["waive"]["G-9"]))
            else:
                rep.pending.append(("G-9", msg))


def run(design, cfg=None):
    rep = Report()
    checks = design.graph.get("checks") or {}
    joined = design.joined()   # nets joined by 0 Ω bridges as one net
    check_structure(design, rep, set(cfg.boards) if cfg else set())
    check_pin_locks(design, rep, checks, cfg.root if cfg else ".")
    check_domains(design, rep)
    check_inputs(joined, rep)
    check_contention(joined, rep)
    check_decoupling(joined, rep)
    check_ratings(design, rep)
    check_reverse(joined, rep, [des for des in checks.get("reverse_protect", []) if des in design.comps])  # else G-1
    check_i2c(joined, rep)
    check_straps(joined, rep)
    check_flyback(joined, rep)
    check_usb_c(joined, rep)
    check_pin_functions(joined, rep)
    check_power_pins(joined, rep, rules.load_sim(cfg) if cfg else None)
    check_part_pins(design, rep)
    if cfg:
        from . import part
        part.check(design, rep, cfg)
    check_signoff(design, rep)
    return rep


def main(cfg, args):
    from .design import Design
    d = Design.from_config(cfg)
    rep = run(d, cfg)
    for check, msg in rep.errors:
        print(f"ERROR   {check}  {msg}")
    for check, msg, reason in rep.waived:
        print(f"WAIVED  {check}  {msg}\n                 reason: {reason}")
    for check, msg in rep.pending:
        print(f"PENDING {check}  {msg}")
    for check, msg in rep.warnings:
        print(f"WARNING {check}  {msg}")
    for check, msg in rep.notes:
        print(f"NOTE    {check}  {msg}")
    failed = list(dict.fromkeys(c for c, _ in rep.errors))
    if failed:
        print("\nWhat the failed checks are about (edakit rules <ID>):")
        for c in failed:
            print("  " + "\n  ".join(rules.explain(c)))
    groups = d.bridge_groups()
    if groups:
        print("joined by 0 Ω bridges, checked as one net: " + "; ".join(
            " = ".join([name] + [n for n in nets if n != name]) + f" ({', '.join(des)})" for name, nets, des in groups))
    hints = rules.open_hints(d, cfg, rules.load_sim(cfg))
    print(f"{len(d.comps)} components, {len(d.nets)} nets, {len(d.parts)} parts entries; "
          f"{len(rep.errors)} errors, {len(rep.waived)} waived, {len(rep.pending)} open sign-offs"
          + (f", {len(rep.warnings)} warnings" if rep.warnings else "")
          + (f"; design hints open: {', '.join(hints)} (edakit hints)" if hints else ""))
    if args.json:
        Path(args.json).write_text(json.dumps({**rep.to_dict(), "hints_open": hints}, indent=2, ensure_ascii=False)
                                   + "\n", encoding="utf-8")
    return 1 if rep.errors or (args.release and rep.pending) else 0
