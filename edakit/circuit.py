"""What the engines and the checks read off the graph: voltage ranges, resistors between nets, supplies and how far
they reach, I2C and CC lines, pin functions, values as the graph writes them. Pure functions of a Design – either form
of the parts entries – that decide nothing.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .catalog import table


def values(part):
    """The values of a parts entry."""
    return (part or {}).get("values") or {}


def limits(part):
    """The limits of a parts entry."""
    return (part or {}).get("limits") or {}


def polarized(part):
    """A capacitor with a plus and a minus: values polarized, or a pin with the role plus."""
    return (part or {}).get("kind") == "capacitor" and (values(part).get("polarized") is True or any(
        p.get("role") == "plus" for p in ((part or {}).get("pins") or {}).values()))


ACTIVE_TYPES = {"input", "output", "bidirectional", "power_in", "power_output", "analog", "current_sink"}
BOOT_DRIVERS = {"output", "power_output", "ground"}   # define their net while the firmware is not running
PASS_THROUGH = ("fuse", "switch", "connector")        # pass a reversed source on unchanged
REVERSE_OK = ("battery_holder", "capacitor") + PASS_THROUGH
PURPOSES = ("private", "gift", "sale")                 # purpose.use of the graph: built for oneself, given away, sold
I2C = table("i2c")["pullup"]
I2C_SINK_A, I2C_VOL, I2C_R_MAX = I2C["sink_a"], I2C["vol_v"], I2C["r_max_ohm"]   # UM10204 7.1
USB = table("usb")["cc"]
USB_RD, USB_RD_TOL = USB["rd_ohm"], USB["rd_tol"]                   # USB Type-C sink termination Rd
USB_C_CC = tuple(USB["termination"])   # values.usb_c.cc: how a module or breakout terminates its CC lines
COILS = {"relay": ("coil_plus", "coil_minus"), "buzzer": ("plus", "minus")}   # inductive kinds: their coil roles
FN_LINES = {"pwm": (), "adc": (), "spi": ("sck", "tx", "rx", "cs"), "i2c": ("sda", "scl"), "uart": ("tx", "rx")}
FN_NAMES = [k + (f".{line}" if line else "") for k, lines in FN_LINES.items() for line in lines or [""]]   # net fn
SUPPLY_R_MAX = 100                                   # a resistor up to this passes a supply (shunt, filter)
SWITCHERS = ("buck", "boost")                        # behaviour models of switching regulators (hot loop, REQ.missing)
PIN_FUNCTION = re.compile(r"([a-z][a-z0-9]*?)(\d+)(?:\.([a-z]+))?")   # "spi0.sck", "i2c1.sda", "pwm1.a", "adc0"
KINDS_OF_TYPE = {"microcontroller": ("ic", "module"), "regulator": ("ic", "module"),   # STRUCT.identity: graph type -> parts
                 "transistor": ("npn", "pnp", "nmos", "pmos"), "led": ("led", "led_rgb"),   # entry kinds; any other
                 "switch": ("switch", "dip_switch"), "audio": ("buzzer", "speaker")}       # type: the same word
KINDS_OF_PREFIX = {"R": ("resistor", "potentiometer"), "C": ("capacitor",), "L": ("inductor",),
                   "D": ("diode", "led", "led_rgb"), "Q": ("npn", "pnp", "nmos", "pmos"), "U": ("ic", "module"),
                   "J": ("connector",), "SW": ("switch", "button", "dip_switch"), "F": ("fuse",),
                   "BT": ("battery_holder",), "BZ": ("buzzer",), "K": ("relay", "solenoid"), "TP": ("connector",),
                   "M": ("motor",), "LS": ("speaker",), "SP": ("speaker",), "HE": ("heater",),
                   "OK": ("optocoupler",)}
VALUE_PARAMS = {"value_ohm": ("Ω", "resistance"), "value_f": ("F", "capacitance"), "value_h": ("H", "inductance")}
VALUE_TOL = 0.01      # graph value vs the entry's value parameter
MULTIPLIERS = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6,
               "G": 1e9, "R": 1, "Ω": 1}
QUANTITY = re.compile(r"\s*(\d+)(?:[.,](\d+))?\s*([pnuµμmkKMG]|[RΩ])?(\d+)?\s*(Ω|[oO]hms?|F|H)?(?=$|[\s,;/()])")


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
    return values(part).get("value_ohm") if part.get("kind") == "resistor" else None


def resistors_to(d, net, targets):
    """(designator, value or None, other net) of every resistor between `net` and one of the `targets` nets."""
    out = []
    for des, a, b in resistor_like(d):
        if net in (a, b) and (other := b if a == net else a) in targets:
            out.append((des, resistor_value(d, des), other))
    return out


def resistor_like(d):
    """(des, net_a, net_b) for every resistive two-pole incl. both halves of a potentiometer."""
    out = []
    for des in d.comps_of_kind("resistor", "potentiometer"):
        nets = [d.pin_net.get(f"{des}.{p}") for p, info in d.part(des)["pins"].items() if info.get("type") == "passive"]
        out += [(des, a, b) for i, a in enumerate(nets) for b in nets[i + 1:] if a and b]
    return out


def i2c_name(text):
    """'sda' or 'scl' if the name contains SDA or SCL as a word ('SDA/SDI', 'I2C0_SCL' yes, 'GP4' no)."""
    tokens = set(re.split(r"[^A-Z0-9]+", str(text).upper()))
    return next((t.lower() for t in ("SDA", "SCL") if t in tokens), None)


def i2c_line(info):
    """'sda' or 'scl' from the pin's role, or from its name if it has no role."""
    if info.get("role"):
        return info["role"] if info["role"] in ("sda", "scl") else None
    return i2c_name(info.get("name", ""))


def cc_lines(d, des):
    """{'cc1': net, 'cc2': net} of a USB-C receptacle: pins by role, by name if they have no role."""
    out = {}
    for num, info in d.part(des)["pins"].items():
        line = (info.get("role") or str(info.get("name", ""))).lower()
        if line in ("cc1", "cc2"):
            out[line] = d.pin_net.get(f"{des}.{num}")
    return out


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


def supply_inputs(d, sim=None):
    """Nets a supply feeds: power outputs, and where the supply comes in (the design hint HINT.bulk's power inputs) – the
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


def hold_current(part, t_min=None):
    """i_hold_a of a fuse, or at the lowest ambient t_min from params.i_hold_vs_temp: linear between its points, the
    end values beyond them."""
    table = sorted(values(part).get("i_hold_vs_temp") or [])
    if t_min is None or not table:
        return limits(part)["i_hold_a"]
    if t_min <= table[0][0]:
        return table[0][1]
    for (t0, h0), (t1, h1) in zip(table, table[1:]):
        if t0 <= t_min <= t1:
            return h0 + (h1 - h0) * (t_min - t0) / (t1 - t0)
    return table[-1][1]


def series_nets(d, des):
    """The nets the current of a part flows on: its own, and on through fuses and switches (PATH.reverse's walk without the
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


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


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
    params = values(part)
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



# --- cables ----------------------------------------------------------------------------------------------------------
AWG_D0_MM, AWG_BASE = 0.127, 92     # the gauge's definition (ASTM B258): d(n) = 0.127 mm × 92^((36 − n) / 39)
CABLE_OHM = 0.05                    # a wire without r_ohm_per_wire or length and gauge
CABLE_KEYS = {"name", "from", "to", "pins", "r_ohm_per_wire", "length_m", "awg", "mm2", "l_nh_per_m", "i_max_a",
              "notes", "about"}


def wire_mm2(cable):
    """A cable's wire cross-section in mm²: `mm2`, or from `awg`; None without either."""
    if is_number(cable.get("mm2")):
        return cable["mm2"]
    if is_number(cable.get("awg")):
        d = AWG_D0_MM * AWG_BASE ** ((36 - cable["awg"]) / 39)
        return 3.141592653589793 * d * d / 4
    return None


def wire_ohm(cable):
    """The resistance of one wire: r_ohm_per_wire, or copper of length_m and its gauge (copper.RHO_OHM_MM, 20 °C, as
    the routed tracks), else CABLE_OHM."""
    from .sim.copper import RHO_OHM_MM
    if is_number(cable.get("r_ohm_per_wire")):
        return cable["r_ohm_per_wire"]
    mm2 = wire_mm2(cable)
    if mm2 and is_number(cable.get("length_m")):
        return RHO_OHM_MM * cable["length_m"] * 1000 / mm2
    return CABLE_OHM


def wire_h(cable):
    """The inductance of one wire in H: l_nh_per_m × length_m, 0 without them."""
    if is_number(cable.get("l_nh_per_m")) and is_number(cable.get("length_m")):
        return cable["l_nh_per_m"] * 1e-9 * cable["length_m"]
    return 0.0


def cable_problems(cable):
    """What is wrong with a cable's wire data: its resistance either given or from length and gauge, numbers ≥ 0."""
    out = []
    for k in sorted(set(cable) - CABLE_KEYS):
        out.append(f"unknown key '{k}' (known: {', '.join(sorted(CABLE_KEYS - {'name', 'from', 'to', 'pins'}))})")
    for k in ("r_ohm_per_wire", "length_m", "mm2", "l_nh_per_m", "i_max_a"):
        if k in cable and not (is_number(cable[k]) and cable[k] >= 0):
            out.append(f"{k} must be a number ≥ 0, not {cable[k]!r}")
    if "awg" in cable and not (is_number(cable["awg"]) and 0 <= cable["awg"] <= 40):
        out.append(f"awg must be a gauge from 0 to 40, not {cable['awg']!r}")
    gauge = [k for k in ("awg", "mm2") if k in cable]
    if len(gauge) > 1:
        out.append("awg or mm2, not both")
    if "r_ohm_per_wire" in cable and ("length_m" in cable or gauge):
        out.append("r_ohm_per_wire or length_m with awg or mm2, not both")
    elif "length_m" in cable and not gauge:
        out.append("length_m needs the wire's awg or mm2")
    elif gauge and "length_m" not in cable:
        out.append(f"{gauge[0]} needs the cable's length_m")
    if "l_nh_per_m" in cable and "length_m" not in cable:
        out.append("l_nh_per_m needs the cable's length_m")
    return out
