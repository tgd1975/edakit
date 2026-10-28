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
       an IC (a Type-C controller) is on the CC lines; a module or breakout states the termination of its receptacle
       in params.usb_c: rd_5k1 or controller passes, none has its CC pins checked like a receptacle's and fails
       without them
  G-15 pin functions: a net's "fn" (pwm, adc, spi.sck, i2c.sda, uart.tx, …) is on a pin whose parts entry lists it
       in "functions", the nets of one "fn_bus" on one peripheral instance, PWM nets of one slice with one fixed
       "pwm_hz" and a channel each; a pin without "functions" is a note
  G-16 ground and supply pins: a ground pin on the ground net (or one joined to it by an inductor, or in the graph's
       "grounds"), a supply pin (power_in) on a net that a supply reaches – a power output, a battery holder, a
       connector with a vbus pin or in checks.reverse_protect, a sim source – directly or through fuses, switches,
       connectors, inductors, MOSFETs, resistors up to 100 Ohm and diodes in forward direction
  G-17 fuses: the hold current of a fuse (at the lowest ambient, ambient_min_c of sim.json) is at most the i_max_a of
       every connector, switch and cable its current flows through; a trip current above it is a warning
  G-18 hot loops: a part whose parts entry names its hot-loop pin roles (hot_loop; "gnd" also for ground pins) has
       a layout.loops entry on each net of the loop – the nets of those pins and the net behind a diode on its
       switch node (sw); a buck or boost IC without hot_loop is a warning
  P-1  graph pins (number + name) = parts database, an entry exists for every LCSC number – or, for a part bought
       elsewhere, for its manufacturer part number `part`; with the library's symbol cached by `edakit part import`,
       the graph's pins = that symbol (case and blanks ignored, as S-2)
  P-6  part identity: the component and its parts entry name the same part – the entry's lcsc is its file name,
       the component's lcsc no C99… user-library number (unless bom: false), its part names the entry's mpn (remarks
       in parentheses or after ";" left out, case ignored; a part that starts with a value is that value), its
       value reads as the entry's value_ohm / value_f / value_h within 1 %, its type fits the entry's kind; a
       designator prefix (R, C, L, D, Q, U, J, SW, F, BT, BZ, K, TP) against the kind is a warning
  P-7  through-hole leads known and fitting the footprint, before the layout: L-9's test (release/fab.py hole_ok)
       on the holes of the footprint geometry – the board's `pcb dump`, else the library footprint cached by `edakit
       part import`; plated holes without `lead` in the parts entry pending, a hole that does not take the lead an
       error, tight in the worst case or a plated slot narrower than 0.5 mm a warning
  P-8  formed leads fit only one way round: a part whose board footprint (`pcb dump`) has its plated holes away from
       the library footprint's (more than 0.05 mm from the hole of the same number, the two laid on each other by
       their numbers), three or more of them, is not laid onto itself by a turn of 90°, 180° or 270° – every hole
       within 0.25 mm of a hole – with a pin in the hole of a pin on another net (pins on one net do not count);
       without the library footprint a note
  P-3  own parts (part.py): a board copied from its project with `edakit part own` is that project's current
       datasheet, copied from a commit (pending otherwise); a board that is not released is a warning; the project's
       own datasheets (hardware/datasheet/) are of its current state
  P-4  parts orderable (stock.py): every assembled part listed at JLCPCB, in stock for `quantity` boards with the
       assembler's attrition, the MPN of its entry, not "Standard Only" on an Economic order – read offline from the
       snapshot of `edakit stock`; MSL >= 5, a thin stock margin, another class warn; an old snapshot is pending
  P-5  a part bought separately (bom: false) names its supplier: an LCSC number (a C99… library number is none) or
       `order` in its parts entry (order.py, warning)
  G-9  sign-off: every part verified against its datasheet, no open "verify" notes (pending, blocks only the release)

Only with [project] requirements (requirements.py, handbook 3.6) – the requirements file, which the circuit hash covers:
  G-20 every reference resolves: a need or requirement in from (N-…, R-…) is in the files, a manual check in from or
       in verify signoff (M-…) is one of the sign-off file or a required one, a rows pattern that starts with a check
       ID names a check of the catalog that is not retired, a script is a [scripts.<name>] of kind check or a
       [[release.stages]] id; a from that names a dropped entry is a warning
  G-21 every accepted need is in from of a requirement that is not dropped
  G-22 every requirement that is not dropped has evidence (verify)
  G-23 a draft need or requirement is a warning until the user accepts or drops it
A draft never blocks: every finding about one is a warning (Report.drafts), in the gate's stage G information; it is
an error once the user has accepted the entry. A file named there that is missing or not valid stops edakit check
(exit 1) before any check runs.

0 Ω bridges (resistors with value_ohm 0 in the parts entry) join their nets: G-4, G-5, G-6, G-10 to G-17 see the
joined nets as one net under the group's name (the ground net if it is one of them, else the first in the graph) and
the bridges as copper; G-1, G-2, G-3, G-8, G-18, P-1 and G-9 see every net and part as the graph has them.

edakit check also resolves the project's scripts ([scripts.*] of edakit.toml, with [[release.stages]] and sim_plugin)
with edakit's steps into one order and compares their stamps (hardware/scripts.lock), with the ID scripts – no check
of the catalog (scripts.py, handbook 8.6): what keeps the entries from one order is an error, as an input that is
outdated or never ran; a derive or easyeda script outdated or never run is a warning, what was not compared a note.
The project's agents ([agents.*]) are checked too, with the ID agents: an agent file that is missing, a sign-off that
is not the agent's to sign, an after that names no agent – each an error (scripts.agents). The gate reports the same
in stage G.

Rule, reason, fix and sources of every check: rules.json (`edakit rules G-4`). A failed check is explained once
below the findings. A finding listed in "waive" of the net or component is accepted on purpose and reported with
its reason. Exit code 1 on errors; with --release also on pending sign-offs.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import handover, requirements, rules
from .design import natural_key

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
USB_C_CC = ("rd_5k1", "controller", "none")          # params.usb_c.cc: how a module or breakout terminates its CC lines
COILS = {"relay": ("coil_plus", "coil_minus"), "buzzer": ("plus", "minus")}   # inductive kinds: their coil roles
FN_LINES = {"pwm": (), "adc": (), "spi": ("sck", "tx", "rx", "cs"), "i2c": ("sda", "scl"), "uart": ("tx", "rx")}
FN_NAMES = [k + (f".{line}" if line else "") for k, lines in FN_LINES.items() for line in lines or [""]]   # net fn
SUPPLY_R_MAX = 100                                   # a resistor up to this passes a supply (shunt, filter)
SWITCHERS = ("buck", "boost")                        # behaviour models of switching regulators (hot loop, G-18)
PIN_FUNCTION = re.compile(r"([a-z][a-z0-9]*?)(\d+)(?:\.([a-z]+))?")   # "spi0.sck", "i2c1.sda", "pwm1.a", "adc0"
KINDS_OF_TYPE = {"microcontroller": ("ic", "module"), "regulator": ("ic", "module"),   # P-6: graph type -> parts
                 "transistor": ("npn", "pnp", "nmos", "pmos"), "led": ("led", "led_rgb"),   # entry kinds; any other
                 "switch": ("switch", "dip_switch"), "audio": ("buzzer",)}                  # type: the same word
KINDS_OF_PREFIX = {"R": ("resistor", "potentiometer"), "C": ("capacitor",), "L": ("inductor",),
                   "D": ("diode", "led", "led_rgb"), "Q": ("npn", "pnp", "nmos", "pmos"), "U": ("ic", "module"),
                   "J": ("connector",), "SW": ("switch", "button", "dip_switch"), "F": ("fuse",),
                   "BT": ("battery_holder",), "BZ": ("buzzer",), "K": ("relay",), "TP": ("connector",)}
VALUE_PARAMS = {"value_ohm": ("Ω", "resistance"), "value_f": ("F", "capacitance"), "value_h": ("H", "inductance")}
VALUE_TOL = 0.01      # graph value vs the entry's value parameter
MULTIPLIERS = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6,
               "G": 1e9, "R": 1, "Ω": 1}
QUANTITY = re.compile(r"\s*(\d+)(?:[.,](\d+))?\s*([pnuµμmkKMG]|[RΩ])?(\d+)?\s*(Ω|[oO]hms?|F|H)?(?=$|[\s,;/()])")

EXECUTED = ["G-1", "G-2", "G-3", "G-4", "G-5", "G-6", "G-8", "G-10", "G-11", "G-12", "G-13", "G-14", "G-15", "G-16",
            "G-17", "G-18", "P-1", "P-3", "P-4", "P-5", "P-6", "P-7", "P-8", "G-9"]


def executed(cfg=None):
    """The checks run() runs for this project: EXECUTED, and with [project] requirements G-20 to G-23 – a project
    without the key gets the same checks as before."""
    return EXECUTED + (list(requirements.CHECKS) if cfg is not None and cfg.requirements else [])


class Report:
    def __init__(self):
        self.errors, self.pending, self.waived = [], [], []
        self.warnings, self.notes = [], []   # a warning the gate wants accepted in the sign-off file; information
        self.drafts = []   # about a draft of the requirements file: a warning here, in the gate information (3.6)

    def error(self, check, msg, waive=None):
        if waive and check in waive:
            self.waived.append((check, msg, waive[check]))
        else:
            self.errors.append((check, msg))

    def to_dict(self):
        return {"errors": [{"check": c, "msg": m} for c, m in self.errors],
                "pending": [{"check": c, "msg": m} for c, m in self.pending],
                "waived": [{"check": c, "msg": m, "reason": r} for c, m, r in self.waived],
                "warnings": [{"check": c, "msg": m} for c, m in self.warnings]
                + [{"check": c, "msg": m, "draft": True} for c, m in self.drafts],
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


def check_structure(d, rep, boards, bought=()):
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
        if c.get("board") in bought and c.get("bom") is not False:
            rep.error("G-1", f"{des}: on the bought board {c['board']} – nobody assembles it: bom: false")
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
    """G-14 on the receptacles the graph shows with their CC pins, and on the ones a parts entry states (usb_c): a
    module or breakout that terminates its own receptacle passes, one without termination is checked through its CC
    pins, or fails when they are no pins of the graph."""
    for des in d.comps:
        part = d.part(des)
        if not part:
            continue
        cc, usb, waive = cc_lines(d, des), (part.get("params") or {}).get("usb_c"), d.comps[des].get("waive")
        if usb is not None:
            state = usb.get("cc") if isinstance(usb, dict) else None
            if state not in USB_C_CC:
                rep.error("G-14", f"{des}: params.usb_c of {d.entry_key(des)} needs cc {', '.join(USB_C_CC[:-1])} or "
                                  f"{USB_C_CC[-1]}, not {state!r}")
                continue
            if state != "none":
                continue  # the board terminates its receptacle itself: Rd on it, or a Type-C or PD controller
            if set(cc) != {"cc1", "cc2"}:
                rep.error("G-14", f"{des}: USB-C receptacle without CC termination (params.usb_c of "
                                  f"{d.entry_key(des)}: cc none) and its CC lines are no pins of the graph – a USB-C "
                                  f"source switches VBUS on only with {ohm(USB_RD)} to {d.ground} on each CC pin", waive)
                continue
        elif part.get("kind") != "connector" or set(cc) != {"cc1", "cc2"}:
            continue
        if any(d.pin_info(r).get("type") not in (None, "passive") for n in cc.values() if n
               for r in d.nets[n]["pins"] if not r.startswith(f"{des}.")):
            continue  # a Type-C or PD controller drives the CC lines
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


def hold_current(part, t_min=None):
    """i_hold_a of a fuse, or at the lowest ambient t_min from params.i_hold_vs_temp: linear between its points, the
    end values beyond them."""
    table = sorted((part.get("params") or {}).get("i_hold_vs_temp") or [])
    if t_min is None or not table:
        return part["ratings"]["i_hold_a"]
    if t_min <= table[0][0]:
        return table[0][1]
    for (t0, h0), (t1, h1) in zip(table, table[1:]):
        if t0 <= t_min <= t1:
            return h0 + (h1 - h0) * (t_min - t0) / (t1 - t0)
    return table[-1][1]


def series_nets(d, des):
    """The nets the current of a part flows on: its own, and on through fuses and switches (G-10's walk without the
    connectors – a connector hands the current on through a cable on the same net, not to its other pins); not
    ground."""
    nets = {d.pin_net.get(f"{des}.{p}") for p in d.part(des)["pins"]} - {None, d.ground}
    todo = list(nets)
    while todo:
        for ref in d.nets[todo.pop()]["pins"]:
            other = ref.split(".", 1)[0]
            if (d.part(other) or {}).get("kind") in ("fuse", "switch"):
                for p in d.part(other)["pins"]:
                    n = d.pin_net.get(f"{other}.{p}")
                    if n and n != d.ground and n not in nets:
                        nets.add(n)
                        todo.append(n)
    return nets


def check_fuses(d, rep, sim=None):
    """G-17: a fuse holds no more than the connectors, switches and cables its current flows through carry."""
    t_min = (sim or {}).get("ambient_min_c")
    for fuse in d.comps_of_kind("fuse"):
        part = d.part(fuse)
        r = part.get("ratings") or {}
        if "i_hold_a" not in r:
            continue
        hold, trip, waive = hold_current(part, t_min), r.get("i_trip_a"), d.comps[fuse].get("waive")
        at = f" at {t_min:g} °C" if t_min is not None and (part.get("params") or {}).get("i_hold_vs_temp") else ""
        nets = series_nets(d, fuse)
        rated = [(des, p["ratings"]["i_max_a"]) for des in d.comps_of_kind("connector", "switch")
                 if "i_max_a" in ((p := d.part(des)).get("ratings") or {})
                 and any(d.pin_net.get(f"{des}.{n}") in nets for n in p["pins"])]
        rated += [(f"cable {c['name']}", c["i_max_a"]) for c in d.graph.get("cables", [])
                  if "i_max_a" in c and any(d.pin_net.get(f"{c['from']}.{a}") in nets for a in c["pins"])]
        for what, i_max in rated:
            if hold > i_max:
                rep.error("G-17", f"{fuse}: holds {hold:.3g} A{at}, above the {i_max:g} A of {what} – an overload in "
                                  "between never trips it", waive)
            elif trip is not None and trip > i_max:
                msg = f"{fuse}: trips at {trip:g} A, above the {i_max:g} A of {what} – an overload in between may " \
                      "last for minutes"
                if waive and "G-17" in waive:
                    rep.waived.append(("G-17", msg, waive["G-17"]))
                else:
                    rep.warnings.append(("G-17", msg))


def check_hot_loops(d, rep):
    """G-18: a part whose entry names its hot-loop pins (hot_loop: pin roles, "gnd" also for pins of type ground) has
    a layout.loops entry on every net of that loop – the nets of those pins and, one diode further, the net behind
    the rectifier on the switch node (sw). A buck or boost IC without hot_loop is a warning."""
    covered = {d.pin_net.get(lp.get("a")) for lp in (d.graph.get("layout") or {}).get("loops") or []} - {None}
    for des in d.comps:
        part = d.part(des) or {}
        roles, behavior = part.get("hot_loop"), (part.get("params") or {}).get("behavior")
        who, waive = f"{des} ({behavior})" if behavior else des, d.comps[des].get("waive")
        if roles is None:
            if part.get("kind") == "ic" and behavior in SWITCHERS:
                msg = f"{who}: parts entry {d.entry_key(des)} names no hot_loop – G-18 cannot ask for its hot loop " \
                      "in layout.loops"
                if waive and "G-18" in waive:
                    rep.waived.append(("G-18", msg, waive["G-18"]))
                else:
                    rep.warnings.append(("G-18", msg))
            continue
        pins = {num: "gnd" if p.get("type") == "ground" and p.get("role") is None else p.get("role")
                for num, p in part["pins"].items()}
        for role in [r for r in roles if r not in pins.values()]:
            rep.error("G-18", f"{des}: hot_loop of {d.entry_key(des)} names '{role}', no pin role of the part")
        nets = {}   # net -> why it belongs to the loop
        for num, role in pins.items():
            if role in roles and (net := d.pin_net.get(f"{des}.{num}")):
                nets.setdefault(net, f"{des}.{num} {part['pins'][num]['name']}")
        sw = {d.pin_net.get(f"{des}.{num}") for num, role in pins.items() if role == "sw" and role in roles} - {None}
        for dio in d.comps_of_kind("diode"):
            a, k = d.net_of(dio, "anode"), d.net_of(dio, "cathode")
            for here, there in ((a, k), (k, a)):
                if here in sw and there and there not in nets:
                    nets[there] = f"behind {dio}"
        for net, why in nets.items():
            if net not in covered:
                on_net = d.nets[net].get("waive") or {}
                rep.error("G-18", f"{who}: no layout.loops entry on {net} ({why})",
                          on_net if "G-18" in on_net else waive)


def check_part_pins(d, rep, cfg=None):
    from . import part as parts
    from .schematic import pin_differences
    for des, c in d.comps.items():
        if not c.get("lcsc") and not c.get("part"):
            continue   # a bare test pad: no part to buy, no entry
        symbol = parts.cached(cfg, c.get("lcsc")) if cfg else None   # the library's symbol (edakit part import)
        if symbol and (diffs := pin_differences(symbol["pins"], c["pins"])):
            rep.error("P-1", f"{des}: pins differ from the library symbol of {c['lcsc']} "
                             f"({cfg.relative(parts.library_file(cfg, c['lcsc']))}): {'; '.join(diffs)}", c.get("waive"))
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


def read_value(text):
    """(number, unit or None) of a value as the graph writes it – 10k, 4k7, 2R2, 100nF, 22 µF, 330 Ω 0805 (the
    leading quantity) –, or None when it starts with no quantity (green, 1N4148, 0805W8F…)."""
    m = QUANTITY.match(str(text or ""))
    if not m or (m.group(2) and m.group(4)):
        return None
    whole, frac, mult, frac2, unit = m.groups()
    number = float(f"{whole}.{frac or frac2 or 0}") * MULTIPLIERS.get(mult, 1)
    if (unit and unit[0] in "ΩoO") or (mult in ("R", "Ω") and not unit):
        unit = "Ω"
    return number, unit


def si(x, unit):
    for f, p in ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")):
        if abs(x) >= f or f == 1e-12:
            return f"{x / f:.4g} {p}{unit}" if x else f"0 {unit}"
    return f"{x} {unit}"


def core_mpn(mpn):
    """The part number of an mpn without the remarks entries add: in parentheses, after a semicolon."""
    return " ".join(re.sub(r"\([^)]*\)", " ", str(mpn)).split(";")[0].split())


def value_problem(text, part, key, what):
    """What is wrong with a value of the graph against the value parameter of parts entry `key`, or None."""
    params = part.get("params") or {}
    param = next((k for k in VALUE_PARAMS if isinstance(params.get(k), (int, float))), None)
    if not param:
        return None
    (unit, name), want = VALUE_PARAMS[param], float(params[param])
    got = read_value(text)
    if got is None:
        return f"{what} {text} does not read as a {name} – parts entry {key} has {param} {si(want, unit)}"
    if got[1] and got[1] != unit:
        return f"{what} {text} is no {name} – parts entry {key} has {param} {si(want, unit)}"
    if abs(got[0] - want) > VALUE_TOL * abs(want):
        return f"{what} {text} reads {si(got[0], unit)}, parts entry {key} has {param} {si(want, unit)}"
    return None


def check_identity(d, rep):
    """P-6: the component and its parts entry name the same part."""
    users = defaultdict(list)
    for des in sorted(d.comps, key=natural_key):
        if (key := d.entry_key(des)) is not None:
            users[key].append(des)
    for key, dess in sorted(users.items()):
        lcsc = d.parts[key].get("lcsc")
        if lcsc and lcsc != key:
            rep.error("P-6", f"{key}.json: lcsc {lcsc} – the file is named {key} ({', '.join(dess)})")
    for key, dess in users.items():
        part = d.parts[key]
        for des in dess:
            c, waive = d.comps[des], d.comps[des].get("waive")
            if str(c.get("lcsc") or "").startswith("C99") and c.get("bom") is not False:
                rep.error("P-6", f"{des}: lcsc {c['lcsc']} is a part of an EasyEDA user library – nobody sells it "
                                 "(handbook 4.2)", waive)
            mpn = core_mpn(part.get("mpn") or "")
            if c.get("part") and mpn:
                if read_value(c["part"]):                   # a description ("330 Ω 0805"): its value counts
                    if problem := value_problem(c["part"], part, key, "part"):
                        rep.error("P-6", f"{des}: {problem}", waive)
                elif not re.search(r"(?<![A-Za-z0-9])" + re.escape(mpn).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9])",
                                   c["part"], re.I):
                    rep.error("P-6", f"{des}: part {c['part']} does not name {mpn}, the mpn of parts entry {key}", waive)
            if c.get("value") not in (None, "") and (problem := value_problem(c["value"], part, key, "value")):
                rep.error("P-6", f"{des}: {problem}", waive)
            kind = part.get("kind")
            if not kind:
                continue
            if c.get("type") and kind not in KINDS_OF_TYPE.get(c["type"], (c["type"],)):
                rep.error("P-6", f"{des}: type {c['type']} does not fit kind {kind} of parts entry {key}", waive)
            prefix = re.match(r"[A-Za-z]*", des).group(0).upper()
            if prefix in KINDS_OF_PREFIX and kind not in KINDS_OF_PREFIX[prefix]:
                usual = next((p for p, kinds in KINDS_OF_PREFIX.items() if kind in kinds), None)
                rep.warnings.append(("P-6", f"{des}: designator prefix {prefix}, but parts entry {key} is a {kind}"
                                            + (f" ({usual})" if usual else "")))


def board_dumps(d, cfg):
    """dumped(des) -> the component's footprint as `pcb dump` measured it on its board, or None."""
    from . import part as parts
    from .pcb import geometry_file
    dumps = {name: parts._read(geometry_file(cfg, b)) or {} for name, b in cfg.boards.items()}

    def dumped(des):
        board = d.comps[des].get("board")
        return next((dump[des] for name, dump in dumps.items() if board in (None, name) and des in dump), None)
    return dumped


def footprint_geometry(d, cfg):
    """geometry(des) -> (footprint geometry, where from) or (None, None): the dump of the component's board – the
    project's footprint as placed –, else the library footprint `edakit part import` cached."""
    from . import part as parts
    dumped = board_dumps(d, cfg)

    def geometry(des):
        if geo := dumped(des):
            return geo, "pcb dump"
        lib = parts.library_footprint(cfg, d, des)
        return (lib, f"library geometry {lib['footprint']}") if lib else (None, None)
    return geometry


def check_holes(d, rep, geometry):
    """P-7: L-9's hole-against-lead test (fab.hole_ok) on the plated holes of the footprint geometry, before anything
    is placed or routed. Same words and thresholds as L-9, which stays in the gate on the drill file."""
    from .part import pad_points
    from .release.fab import HOLE_PLAY_MM, HOLE_TOL_MM, JLC_SLOT_MM, hole_ok
    seen, unknown = False, []
    for des in sorted(d.comps, key=natural_key):
        entry = d.part(des)
        geo, where = geometry(des) if entry else (None, None)
        if not geo:
            continue
        seen = True
        holes = [(n, p) for n, _, _, p in pad_points(geo) if p.get("tht") and p.get("plated", True)]
        if not holes:
            continue
        if any(not p.get("hole") for _, p in holes):
            unknown.append(des)
            continue
        leads = entry.get("lead")
        if not leads:
            rep.pending.append(("P-7", f"{des} {d.entry_key(des)}: plated holes but no lead in the parts entry – the "
                                       "lead's cross-section from the datasheet (handbook 4.1)"))
            continue
        bad, tight, narrow, nolead = defaultdict(list), defaultdict(list), defaultdict(list), []
        for n, p in holes:
            lead = leads.get(n) or leads.get("*")
            if lead is None:
                nolead.append(n)
                continue
            w, length = p["hole"]
            ok, is_tight, text = hole_ok(lead, w, length)
            if not ok:
                bad[text].append(n)
            elif is_tight:
                tight[text].append(n)
            if length > w + 0.01 and w < JLC_SLOT_MM - 1e-6:
                narrow[f"{w:.2f} x {length:.2f} mm"].append(n)
        pads = lambda ns: ", ".join(sorted(dict.fromkeys(ns), key=natural_key))  # noqa: E731
        for text, ns in bad.items():
            rep.error("P-7", f"{des} (pads {pads(ns)}, {where}): {text}", d.comps[des].get("waive"))
        if tight:
            rep.warnings.append(("P-7", f"{des} ({where}): tight hole – worst case below {HOLE_PLAY_MM} mm play (hole "
                                        f"-{HOLE_TOL_MM} mm, lead + tolerance): "
                                        + "; ".join(f"pad {pads(ns)}: {t}" for t, ns in tight.items())))
        if narrow:
            rep.warnings.append(("P-7", f"{des} ({where}): slot narrower than {JLC_SLOT_MM} mm (JLCPCB minimum, plated, "
                                        "2 layers): " + "; ".join(f"pad {pads(ns)}: {s}" for s, ns in narrow.items())))
        if nolead:
            rep.pending.append(("P-7", f"{des} {d.entry_key(des)}: no lead for pad {pads(nolead)} in the parts entry"))
    if unknown:
        rep.notes.append(("P-7", f"{', '.join(unknown)}: hole size unknown – edakit pcb dump (the geometry is older "
                                 "than P-7)"))
    return seen


FORMED_MM = 0.05      # P-8: a hole this far from the library's hole of its number is formed for the board (L-10)
LEAD_PUSH_MM = 0.25   # P-8: a formed lead this far off a hole still goes in with a push (about a lead's radius)


def plated_holes(geo):
    """[(number, x mm, y mm, pad)] of the plated through-hole pads of a footprint geometry (P-7 reads the same)."""
    from .part import pad_points
    return [pt for pt in pad_points(geo) if pt[3].get("tht") and pt[3].get("plated", True)]


def on_library_pattern(holes, lib, pad_map):
    """P-8: every hole lies within FORMED_MM of the library footprint's pad of its number (pad_map: intended swaps, as
    L-10), the two laid on each other by the shift that fits the numbers best – a footprint drawn around another
    origin keeps the library's pattern. -> True, False, or the numbers the library lacks."""
    import math

    from .part import pad_points
    at = defaultdict(list)
    for n, x, y, _ in pad_points(lib):
        at[n].append((x, y))
    pairs = [(x, y, at.get(pad_map.get(n, n))) for n, x, y, _ in holes]
    if lacks := sorted({n for (n, *_), (*_, c) in zip(holes, pairs) if not c}, key=natural_key):
        return lacks
    ones = [(c[0][0] - x, c[0][1] - y) for x, y, c in pairs if len(c) == 1]   # shell legs: no shift from them
    dx, dy = (sum(v[0] for v in ones) / len(ones), sum(v[1] for v in ones) / len(ones)) if ones else (0.0, 0.0)
    return all(min(math.dist((x + dx, y + dy), q) for q in c) <= FORMED_MM for x, y, c in pairs)


def self_fits(holes):
    """P-8: [(turn, [(pin, pin whose hole it lands in)])] for every turn of 90°, 180° and 270° that lays the holes on
    themselves, every hole within LEAD_PUSH_MM of a hole – the position-only matching of `part diff` (part.fit)."""
    from .part import TURNS, fit
    out = []
    for turn in (t for t in TURNS if t):
        c = fit(holes, holes, turn, False)
        if max(r for _, _, r in c["pairs"]) <= LEAD_PUSH_MM:
            out.append((turn, [(holes[j][0], holes[i][0]) for i, j, _ in c["pairs"]]))
    return out


def check_formed(d, rep, cfg):
    """P-8: a through-hole part whose plated holes the board's footprint (`pcb dump`) moves away from its library
    footprint – leads formed for this board – and that has three or more of them fits only one way round: no turn by
    90°, 180° or 270° lays its holes onto themselves with a pin in the hole of a pin on another net of the graph. The
    library footprint is the one of the dump's footprint name that `edakit part import` cached; without it, or when
    it lacks a pad number of the dump, a note. A part on its library pattern is not judged: its orientation is the
    print's job (L-8, P-2, M-2)."""
    from . import part as parts
    dumped = board_dumps(d, cfg)
    for des in sorted(d.comps, key=natural_key):
        geo = dumped(des)
        holes = plated_holes(geo) if geo else []
        if len(holes) < 3:
            continue
        name = geo.get("footprint")
        lib = parts.cached_footprint(cfg, name)
        if not lib:
            rep.notes.append(("P-8", f"{des}: formed leads not judged – no library footprint {name} to compare the "
                                     "holes with (edakit part import <LCSC>)"))
            continue
        same = on_library_pattern(holes, lib, (d.part(des) or {}).get("pad_map") or {})
        if isinstance(same, list):
            rep.notes.append(("P-8", f"{des}: formed leads not judged – the library footprint {name} has no pad "
                                     f"{', '.join(same)}"))
            continue
        if same:
            continue
        net = lambda n: d.pin_net.get(f"{des}.{n}")  # noqa: E731
        swaps = []
        for turn, pairs in self_fits(holes):
            shown = []
            for pin, hole in sorted(set(pairs), key=lambda p: (natural_key(p[0]), natural_key(p[1]))):
                if net(pin) != net(hole) and (hole, pin) not in shown:
                    shown.append((pin, hole))
            if shown:
                swaps.append((turn, shown))
        if swaps:
            (turn, shown), more = swaps[0], [t for t, _ in swaps[1:]]
            pin = lambda n: f"pin {n} ({net(n) or 'no net'})"  # noqa: E731
            rep.error("P-8", f"{des}: its formed holes lie on each other turned by {turn}°"
                             + (f" (also {', '.join(f'{t}°' for t in more)})" if more else "") + " – "
                             + ", ".join(f"{pin(a)} in the hole of {pin(b)}" for a, b in shown),
                      d.comps[des].get("waive"))


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
    sim = rules.load_sim(cfg) if cfg else None   # sources (G-16) and the lowest ambient (G-17)
    joined = design.joined()   # nets joined by 0 Ω bridges as one net
    check_structure(design, rep, set(cfg.boards) if cfg else set(), set(cfg.boards) - set(cfg.made()) if cfg else ())
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
    check_power_pins(joined, rep, sim)
    check_fuses(joined, rep, sim)
    check_hot_loops(design, rep)   # layout.loops name pads of the graph's own nets (G-1, L-11)
    check_part_pins(design, rep, cfg)
    check_identity(design, rep)
    if cfg:
        from . import order, part, stock
        part.check(design, rep, cfg)
        if not check_holes(design, rep, footprint_geometry(design, cfg)):
            rep.notes.append(("P-7", "not run: no footprint geometry – edakit pcb dump once the parts are in the PCB, "
                                     "or edakit part import <LCSC> for the library's"))
        from .pcb import move_notes        # a geometry still among the artifacts is read; how to move it
        rep.notes += [("P-7", note) for note in move_notes(cfg)]
        check_formed(design, rep, cfg)
        stock.check(design, rep, cfg)
        order.check(design, rep, cfg)
    check_signoff(design, rep)
    if cfg is not None and cfg.requirements:
        requirements.check(rep, cfg)      # G-20 to G-23 on the requirements file (handbook 3.6)
    return rep


def main(cfg, args):
    from . import scripts
    from .design import Design
    try:        # a requirements file named in [project] requirements that is missing or not valid stops the check
        entries = requirements.load(cfg)
    except requirements.RequirementsError as e:
        print(f"edakit check: {e}", file=sys.stderr)
        return 1
    d = Design.from_config(cfg)
    rep = run(d, cfg)
    found = scripts.findings(cfg)     # [scripts.*]: one order, every script current (8.6)
    rep.errors += [("scripts", m) for level, m in found if level == "error"]
    rep.warnings += [("scripts", m) for level, m in found if level == "warning"]
    rep.notes += [("scripts", m) for level, m in found if level == "note"]
    team = scripts.agents(cfg).findings if cfg.agents else []     # [agents.*]: what each signs, where it reviews
    rep.errors += [("agents", f.msg) for f in team]
    for check, msg in rep.errors:
        print(f"ERROR   {check}  {msg}")
    for check, msg, reason in rep.waived:
        print(f"WAIVED  {check}  {msg}\n                 reason: {reason}")
    for check, msg in rep.pending:
        print(f"PENDING {check}  {msg}")
    warnings = rep.warnings + rep.drafts   # a finding about a draft only warns: a draft never blocks (3.6)
    for check, msg in warnings:
        print(f"WARNING {check}  {msg}")
    for check, msg in rep.notes:
        print(f"NOTE    {check}  {msg}")
    failed = list(dict.fromkeys(c for c, _ in rep.errors))
    if explained := [c for c in failed if rules.entry(c)]:
        print("\nWhat the failed checks are about (edakit rules <ID>):")
        for c in explained:
            print("  " + "\n  ".join(rules.explain(c)))
    if any(level != "note" for level, _ in found):
        print("\nProject scripts: the entries [scripts.<name>] of edakit.toml – what each script reads and writes – "
              "resolve into one order with edakit's steps; a script that is outdated or never ran runs again by hand – "
              "its cmd –, then edakit scripts stamp <name> records the run (handbook 8.6)")
    if team:
        print("\nProject agents: each entry [agents.<name>] of edakit.toml names its agent file and what the agent signs "
              "– a sign-off of its own, or one of edakit's reviews in place of edakit's agent (replaces); edakit scripts "
              "shows who reviews where (handbook 8.6)")
    groups = d.bridge_groups()
    if groups:
        print("joined by 0 Ω bridges, checked as one net: " + "; ".join(
            " = ".join([name] + [n for n in nets if n != name]) + f" ({', '.join(des)})" for name, nets, des in groups))
    hints = rules.open_hints(d, cfg, rules.load_sim(cfg))
    print(f"{len(d.comps)} components, {len(d.nets)} nets, {len(d.parts)} parts entries; "
          f"{len(rep.errors)} errors, {len(rep.waived)} waived, {len(rep.pending)} open sign-offs"
          + (f", {len(warnings)} warnings" if warnings else "")
          + (f"; requirements: {requirements.counts(entries)}" if cfg.requirements else "")
          + (f"; design hints open: {', '.join(hints)} (edakit hints)" if hints else ""))
    if args.json:
        Path(args.json).write_text(json.dumps({**rep.to_dict(), "hints_open": hints}, indent=2, ensure_ascii=False)
                                   + "\n", encoding="utf-8")
    return 1 if rep.errors or (args.release and rep.pending) else 0
