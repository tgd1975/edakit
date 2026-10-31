"""Graph + parts database -> ngspice netlist for one operating point (.op) of one scenario, or for one transient run
(.tran) whose sources follow piecewise-linear curves ([t, V] points, PWL).

Passive parts, diodes, LEDs, transistors, MOSFETs and JFETs come from the graph 1:1, their values and SPICE models from
the parts database – a transistor's model in the scenario's spread corner (spread.py: hFE, VGS(th), IDSS with VGS(off),
a BJT's leakage in the corner max); a 0 Ω bridge (value_ohm 0) is its maximum resistance r_max_ohm, 50 mΩ without one;
a capacitor with a DC-bias curve (values dc_bias) is the capacitance left at the highest DC its nets' declared ranges
put across it (maker-coverage FT-9) – the operating point a transient or an AC run starts from, not the charge from
0 V. An RGB LED is
three LEDs with the values and limits of their colour, common cathode (roles anode_<color>, cathode) or common anode
(anode, cathode_<color>) as its roles say. An LED whose parts entry lacks one of these roles is left out of the
netlist and listed in meta["leds_left_out"] (SIM.driver); one with a pin in nc is an unused LED and simply left out.
Switches, buttons and DIP switches are closed or open as the scenario's load says; a relay is its coil resistance
(coil_ohm between the roles coil_plus and coil_minus) plus a contact from common to no when the load lists it in
"relays_on", else to nc. Supplies are connectors listed under "sources" in the simulation config, or battery holders
with a cell state – one voltage source per cell, listed in meta["cells"] (LIM.backfeed: no charge current). Off-board loads
(a servo, a motor at a connector) are constant currents between two pins, listed under the load's "external". An LED
strip (kind led_strip) is a ladder of its rails and pixels, and a cable to it gives its pins nodes of their own (strip.py).

ICs and modules are replaced by behaviour models, chosen by values.behavior in the parts database:

  ldo       roles vin, vout (gnd optional): vout = min(vout_v, vin - dropout_v); input current = output + iq_a
  buck      roles vin, vout: ideal output vout_v; input power = output power / efficiency (B-source)
  boost     same as buck; checks vin_min_v from the limits. Without a vout pin (an asynchronous boost, MT3608) the
            output is the net behind the diode on its switch pin (role sw), and its enable (role en) low switches it
            off: the graph's inductor and diode then pass VIN − VD to the output (switch_boost)
            Every regulator (the mcu's on-board one too) whose limits give vin_min_v (mcu: vin_min_v|vsys_min_v) locks out
            below it: output and input current fall to 0 over the UVLO_V below vin_min – a DC result above it is the
            same, a transient run sees the regulator switch off
  mcu       roles vin|vsys|vdd (supply), optional vout|3v3 (on-board regulator: values regulator = "buck"|"ldo",
            output vout_v, default v_io), the core's current i_core_a – an upper bound; i_core_min_a, the least
            current, only in the operating point of the minimum load (scenario "least_current", run.least_current) –,
            gpio pins: outputs from the load's "gpio" levels as source + gpio_r_out_ohm (null: released in that
            load, an input on its pull-up – a key matrix's rows not scanned),
            high level v_io_v in V or "vin" (follows the supply pin, e.g. a 5 V AVR), pull-ups from the config; the
            config's "inputs" are checked for a defined logic level (values vih_v|vih_ratio, vil_v|vil_ratio); an
            output on a pin of type "input" (input-only) is not driven and reported; every output's current is measured
            (limits gpio_i_max_a per pin, gpio_i_total_max_a for the sum)
  cc_sink   constant-current LED driver (TLC5916, STP08CP05 …): roles rext, out (or out0 … outN), vdd, oe_n; R-EXT held at vrext_v,
            each enabled output sinks iout_gain x I(R-EXT) with a soft knee; pins of type output (the serial data
            output SDO of a daisy chain) low through 50 ohm, as in logic
  opamp     roles vcc, vee (or gnd; none: ground), per channel in_p, in_n, out – with a suffix for several channels
            (in_p_a, in_n_a, out_a, in_p_b …): the output follows A_OL x (V(in_p) - V(in_n)), limited (smooth over
            KNEE_V) to the rails plus vout_swing_v [above vee, from vcc] (none: rail to rail), behind r_out_ohm;
            iq_a from vcc to vee. The output's own current comes from ground, not from vcc – drawn from the rail it kept
            the operating point from converging –, so a source's current misses what op-amp outputs source. The inputs
            draw nothing. vicm_v [above vee, from vcc] is the input common-mode range LIM.range holds (engines/sim.py)
  logic     icc_a at the supply pin (a number; or {pin name: A} per supply pin); every output in its state – the
            component's "states", else the pin's "state", else released for an open-drain output, released for a
            tri-state one unless its enable pins are tied active, low for a push-pull one: low through r_out_ohm
            (50 ohm) to ground, high through it to its supply (which delivers what it sources), off not at all
  current   constant i_a at the supply pin
  buck_boost  as buck and boost (the Pico's RT6150): an ideal output whether the input is above or below it
  bridge    bridge driver (DRV8833, TB6612): roles in1_x, in2_x, out1_x, out2_x, (pwm_x, sense_x) per channel, vm, en,
            (vcc); the outputs follow IN1/IN2 (forward, reverse, brake, coast), PWM low brakes, en low turns all off –
            each output a high side 1/r_on_high_ohm to vm and a low side 1/r_on_low_ohm to its return, measured
  charger   linear Li-ion charger (TP4056, MCP73831): roles vin, bat, prog; constant current prog_v / R_PROG
            (i_pre_ratio of it below v_pre_v), constant voltage vout_v, limited by r_on_ohm and v_headroom_v, off below
            uvlo_v or without a PROG resistor; the current measured
  protection  one-cell protection IC (DW01A): roles vdd, gnd, od, oc, vm; OD high above v_uvp_v and below v_ocp_v at
            VM, OC high below v_ovp_v (else at VM), behind r_out_ohm
  cc_led_driver  constant-current step-down LED driver (PT4115, AL8860): roles vin, sense, sw, gnd, dim; R_S from vin
            to sense sets vsense_v / R_S (its top), dim scales it, the switch pulls it into SW while r_on_ohm and
            duty_max_ratio let it; an ideal buck's input current (ic_cc_led_driver)
  none      nothing (e.g. a module that is not powered in this design)

A MOSFET whose entry has the roles gate_2 and source_2 (a dual MOSFET, FS8205A) is two transistors with the same
model, the second's drain on drain_2 or the shared drain.

Constant-current loads – i_core_a, idd_max_a, icc_a, i_a, an external load – fall to 0 below DEAD_RAIL_V across them, so
that a rail nothing feeds stays at 0 V instead of being pulled below ground; above it they are constant. In a transient
run, `steps` turns the current of an external load, an MCU's core or a `current` model into [t, A] points (amps): a
servo starting, a Wi-Fi burst, a motor's start current.

Every element ends on the node of its pin (pn): the node of the pin's net, or – for a net whose routed copper is in the
simulation (sim.json copper, copper.py) – the pin's own pad node, with the tracks and vias as resistors in between.

A project adds its own models in a plugin file (edakit.toml [project] sim_plugin = "hardware/sim_plugin.py") that
defines MODELS = {"name": function(netlist, des, part)}. See handbook/05-simulation.md.
"""

from __future__ import annotations

import math
import re

from ..circuit import capacitance, limits, relay_sets, values, volts_across, wire_h, wire_ohm
from . import strip

VT = 0.02585
LED_N = 2.0
BRIDGE_OHM = 0.05   # a 0 Ω bridge without r_max_ohm: the usual maximum of thick-film jumpers
UVLO_V = 0.2        # undervoltage lockout: a regulator's output falls to 0 over this much below its vin_min
DEAD_RAIL_V = 0.5   # a constant-current load falls to 0 below this voltage across it
I_CORE_A = 0.03     # an MCU's core current without values i_core_a
A_OL = 1e4          # an op-amp's open-loop gain in the model: a follower within 0.3 mV; 1e5 does not converge everywhere
KNEE_V = 0.01       # the smooth min/max of the op-amp's limits: within 10 mV of a limit it bends, linear below
OPAMP_ROLE = re.compile(r"^(in_p|in_n|out)(_[a-z0-9]+)?$")


def core_current(des, p, least=False):
    """An MCU's core current from its values: i_core_a, the upper bound every check uses – or with `least` its least
    current i_core_min_a (default i_core_a), the operating point of the minimum load."""
    high = p.get("i_core_a", I_CORE_A)
    if "i_core_min_a" not in p:
        return high
    low = p["i_core_min_a"]
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (low, high)) or not 0 <= low <= high:
        raise ValueError(f"{des}: i_core_min_a {low!r} – the least current, a number from 0 to i_core_a ({high} A)")
    return low if least else high


def smooth(fn, a, b, w=KNEE_V):
    """min or max of two ngspice expressions, smooth over w: (a + b ∓ sqrt((a − b)² + w²)) / 2."""
    sign = "-" if fn is min else "+"
    return f"(({a})+({b}){sign}sqrt((({a})-({b}))**2+{w * w:g}))/2"


def scaled(value, factor):
    """A supply's value times factor: a voltage, or [t, V] points with each V scaled."""
    if isinstance(value, (int, float)):
        return value * factor
    return [[t, x * factor] for t, x in value]


def pwl(points):
    """[[t, V], …] -> the ngspice source 'PWL(t V …)'; a number -> 'DC V'."""
    if isinstance(points, (int, float)):
        return f"DC {points}"
    return "PWL(" + " ".join(f"{t:.9g} {x:.9g}" for t, x in points) + ")"


def node(net, ground="GND"):
    if net is None:
        return None
    return "0" if net == ground else "n_" + re.sub(r"\W", "_", net.lower())


def pin_node(design, ref):
    """Node of a pin ('U1.39'): its pad node where the routed copper of its net is simulated (copper.py), else the
    node of its net."""
    pads = (getattr(design, "copper", None) or {}).get("pads", {})
    return pads.get(ref) or node(design.pin_net.get(ref), design.ground)


def net_nodes(design, net):
    """The nodes a net's voltage is read at: the node of every pin of a net whose copper is simulated, else the net's
    node."""
    if net in (getattr(design, "copper", None) or {}).get("nets", {}):
        return sorted({pin_node(design, ref) for ref in design.nets[net]["pins"]})
    return [node(net, design.ground)]


def led_model(name, vf, i_test, rs):
    vd = vf - i_test * rs
    i_s = i_test / (math.exp(vd / (LED_N * VT)) - 1)
    return f".model {name} D(IS={i_s:.4e} N={LED_N} RS={rs} BV=5 IBV=10u CJO=20p)"


def led_roles(part):
    """[(colour, anode role, cathode role)] of an LED – one entry, colour None – or of each colour of an RGB LED; a pin
    with the role anode makes it a common anode (handbook 4.1)."""
    if part.get("kind") == "led":
        return [(None, "anode", "cathode")]
    common_anode = any(info.get("role") == "anode" for info in part["pins"].values())
    return [(c, "anode", f"cathode_{c}") if common_anode else (c, f"anode_{c}", "cathode") for c in ("red", "green", "blue")]


def out_role(role):
    """A driver output: the role out, or out0 … outN where the order of the outputs matters (edakit firmware)."""
    return bool(role) and (role == "out" or (role.startswith("out") and role[3:].isdigit()))


SUPPLY_ROLES = ("vdd", "vcc")


def supply_pins(pins):
    """The supply pins of a part (its pins): the power_in pins with the role vdd or vcc, else every power_in pin – as
    engines/sim.py reads the part's supply."""
    power = [n for n, i in pins.items() if i.get("type") == "power_in"]
    return [n for n in power if pins[n].get("role") in SUPPLY_ROLES] or power


def pin_of(pins, key):
    """The number of the pin `key` names – its number, else the first pin of that name – or None."""
    if key is None:
        return None
    key = str(key)
    return key if key in pins else next((n for n, i in pins.items() if i.get("name") == key), None)


def logic_states(design, des, part):
    """{pin number: "high" | "low" | "off"} – where behaviour logic holds each connected output and bidirectional pin
    of `des`: the component's `states` (by pin number or name) over the pin's `state` in its entry; without either an
    open-drain output is off (released), a tri-state output off unless its part ties every enable pin active
    (engines/levels.py enabled) and then low, a push-pull output low, a bidirectional pin off. A word that is none of
    the three, or high on an open-drain output, is STRUCT.entry's or PARTS.schema's and left out here."""
    from ..engines.levels import enabled
    from ..schema import STATES
    pins = part["pins"]
    given = {pin_of(pins, k): v for k, v in ((design.comps.get(des) or {}).get("states") or {}).items()}
    out = {}
    for num, info in pins.items():
        ref, drive = f"{des}.{num}", info.get("drive")
        if info.get("type") not in ("output", "bidirectional") or not design.pin_net.get(ref):
            continue
        state = next((s for s in (given.get(num), info.get("state")) if s in STATES
                      and not (s == "high" and drive == "open_drain")), None)
        if state is None:
            state = ("off" if info["type"] == "bidirectional" or drive == "open_drain"
                     else ("low" if enabled(design, ref) else "off") if drive == "tristate" else "low")
        out[num] = state
    return out


def split_boards(design):
    """Nets that run through a cable get their own node on the cable's source side ('<net>__<board>') with the wire
    resistance in between. Done once per design."""
    if getattr(design, "cable_elements", None) is not None:
        return
    design.cable_elements = []
    board = {d: c.get("board") for d, c in design.comps.items()}
    for cable in design.graph.get("cables", []):
        if strip.feeds(design, cable):        # a cable to an LED strip: each wire its own node there (strip.py)
            continue
        src, dst = cable["from"], cable["to"]
        side = board[src]
        for p_src, p_dst in cable["pins"].items():
            net = design.pin_net.get(f"{src}.{p_src}")
            if net is None or net != design.pin_net.get(f"{dst}.{p_dst}"):
                raise ValueError(f"cable {cable['name']}: {src}.{p_src} and {dst}.{p_dst} are not on the same net")
            alt = f"{net}__{side}"
            for ref in design.nets[net]["pins"]:
                if board[ref.split(".", 1)[0]] == side:
                    design.pin_net[ref] = alt
            design.cable_elements.append({"name": f"R_{cable['name']}_{p_src}", "des": dst, "a": alt, "b": net,
                                          "pa": f"{src}.{p_src}", "pb": f"{dst}.{p_dst}",
                                          "r": wire_ohm(cable), "l": wire_h(cable)})
    strip.split_feeds(design)


def local_ground(design, net):
    """Ground of the board the net is on: its voltage range 'v' refers to it."""
    split_boards(design)
    gnd = design.ground
    boards = {design.comps[ref.split(".", 1)[0]].get("board") for ref in design.nets[net]["pins"]}
    if not boards:                       # a net without pins: STRUCT.net reports it, the simulation goes on
        return gnd
    alt = f"{gnd}__{next(iter(boards))}"
    return alt if len(boards) == 1 and any(el["a"] == alt for el in design.cable_elements) else gnd


class Netlist:
    def __init__(self, design, cfg, scenario, plugin_models=None):
        self.d, self.cfg, self.sc = design, cfg, scenario
        self.load = scenario["load"]
        self.lines, self.models = [], {}
        self.meta = {"leds": {}, "leds_left_out": {}, "cc": {}, "regs": {}, "mcu": {}, "relays": {}, "sources": {},
                     "elements": {}}
        self.plugin_models = plugin_models or {}

    # --- helpers --------------------------------------------------------------------------------------------------
    def n(self, net):
        return node(net, self.d.ground)

    def pn(self, ref):
        """Node of a pin ('U1.39'): its pad node where the copper of its net is simulated, else its net's node."""
        return pin_node(self.d, ref) if ref else None

    def pin_nodes(self, des):
        return {num: self.pn(f"{des}.{num}") for num in self.d.part(des)["pins"]}

    def roles(self, des):
        """role -> net of the first connected pin with that role."""
        return self.d.pins_by_role(des)

    def role_pins(self, des):
        """role -> the first connected pin with that role ('U1.39'), the pin roles() takes the net of."""
        out = {}
        for num, p in ((self.d.part(des) or {}).get("pins") or {}).items():
            ref = f"{des}.{num}"
            if self.d.pin_net.get(ref) and p.get("role") and p["role"] not in out:
                out[p["role"]] = ref
        return out

    def rn(self, des, role, required=False):
        """Node of the pin with this role (pn); None without one, KeyError when it is `required`."""
        pins = self.role_pins(des)
        return self.pn(pins[role] if required else pins.get(role))

    def pin_on(self, des, net):
        """The first pin of `des` on `net` ('U1.4'), None without one."""
        return next((f"{des}.{n}" for n in (self.d.part(des) or {}).get("pins", {})
                     if self.d.pin_net.get(f"{des}.{n}") == net), None)

    def add(self, line, des=None, kind=None, nodes=(), value=None):
        self.lines.append(line)
        if des:
            name = line.split()[0].lower()
            el = {"name": name, "kind": kind, "nodes": list(nodes)}
            if value is not None:
                el["value"] = value
            self.meta["elements"].setdefault(des, []).append(el)

    def amps(self, des, default):
        """The current of a load: `default`, or in a transient run whose `steps` name `des` its [t, A] points – an
        ngspice pwl of time, held at the first point before it and at the last after it."""
        pts = (self.sc.get("steps") or {}).get(des)
        if not pts:
            return default
        pts = ([[0, pts[0][1]]] if pts[0][0] > 0 else []) + list(pts) + [[pts[-1][0] * 10 + 1, pts[-1][1]]]
        return "pwl(time, " + ", ".join(f"{t:.9g}, {a:.9g}" for t, a in pts) + ")"

    def current_load(self, name, plus, minus, i_a, des=None, kind=None):
        """A constant current from `plus` to `minus` that falls to 0 below DEAD_RAIL_V across it (i_a: a number or an
        expression of time, amps)."""
        self.add(f"B_{name} {plus} {minus} I = {i_a}*min(1, max(V({plus},{minus}), 0)/{DEAD_RAIL_V})", des, kind,
                 (plus, minus))

    def gpio_level(self, net, default=0):
        return self.load.get("gpio", {}).get(net, default)

    def model(self, des, part):
        """The part's SPICE model by name; a transistor's in the scenario's spread corner (spread.py)."""
        from . import spread
        corner = spread.corner_of(self.sc, des)
        if corner == "typ" or part.get("kind") not in spread.TRANSISTORS:
            name, text = part["spice"]["model"].split()[1], part["spice"]["model"]
        else:
            name, text = spread.corner_model(part, des, corner)
        self.models[name] = text
        return name

    def leak(self, des, part, c, b):
        """A BJT's collector-base leakage in the spread corner max (spread.leakage): a current from the collector
        into the base at the scenario's ambient_c."""
        from . import spread
        if spread.corner_of(self.sc, des) != "max" or not c or not b:
            return
        i = spread.leakage(part, self.cfg.get("ambient_c", 25))
        if i > 0:
            a, z = (c, b) if part["kind"] == "npn" else (b, c)
            self.add(f"I_{des}_LEAK {a} {z} DC {i:.6g}")
            self.meta.setdefault("leakage", {})[des] = i

    # --- passive and discrete -------------------------------------------------------------------------------------
    def two_pole(self, des, prefix, value, kind, pins=("1", "2")):
        a, b = (self.pn(f"{des}.{p}") for p in pins)
        if a is None or b is None or a == b:
            return
        self.add(f"{prefix}_{des} {a} {b} {value:.6g}", des, kind, (a, b), value)

    def led(self, des, part, color=None, anode_role="anode", cathode_role="cathode"):
        params = values(part)[color] if color else values(part)
        corner = self.sc["corner"]
        vf = params[{"min": "vf_min_v", "max": "vf_max_v"}.get(corner, "vf_typ_v")]
        model = f"LED_{part.get('lcsc', des)}_{color or 'x'}_{corner}"
        self.models[model] = led_model(model, vf, params["vf_at_a"], params.get("rs_ohm", 10))
        roles = self.roles(des)
        a, k = self.rn(des, anode_role), self.rn(des, cathode_role)
        name = f"D_{des}" + (f"_{color}" if color else "")
        if a is None or k is None:   # a pin in nc: an unused LED; a role the parts entry lacks: left out, SIM.driver says so
            known = {info.get("role") for info in part["pins"].values()}
            missing = [r for r in (anode_role, cathode_role) if r not in known]
            if missing:
                self.meta["leds_left_out"][name.lower()] = {"des": des, "color": color, "roles": missing}
            return
        self.add(f"{name} {a} {k} {model}", des, "led", (a, k))
        self.meta["leds"][name.lower()] = {"des": des, "color": color, "anode_net": roles.get(anode_role),
                                           "cathode_net": roles.get(cathode_role)}

    def source(self, des, spec, value):
        """Supply at a connector: voltage source behind a source resistance (cable, power supply). With "outputs"
        several rails against the shared minus (a ±12 V header): each its own source at v_ratio times the supply's
        voltage, oriented so that a rail below the minus (v_ratio < 0) supplies with the same sign of current."""
        from ..circuit import source_outputs
        minus = self.pn(f"{des}.{spec['minus']}")
        for name, plus_pin, ratio in source_outputs(spec):
            out = (spec.get("outputs") or {}).get(name) or {}
            plus = self.pn(f"{des}.{plus_pin}")
            tag = f"{des}_{name}" if name else des
            x = f"x_{tag.lower()}_src"
            v = pwl(scaled(value, abs(ratio)))
            if ratio >= 0:
                self.add(f"V_{tag}_SRC {x} {minus} {v}")
            else:                                   # the rail sits below the minus: + at the minus, - at the rail
                self.add(f"V_{tag}_SRC {minus} {x} {v}")
            r = out.get("r_ohm", spec.get("r_ohm", 0.1))
            self.add(f"R_{tag}_SRC {x} {plus} {r}", des, "source", (x, plus), r)
            key = f"{des}:{name}" if name else des
            self.meta["sources"][key] = {"branch": f"v_{tag}_src#branch".lower(),
                                         "i_max_a": out.get("i_max_a", spec.get("i_max_a")),
                                         "i_min_a": out.get("i_min_a", spec.get("i_min_a")),
                                         "i_back_max_a": out.get("i_back_max_a", spec.get("i_back_max_a")),
                                         "nodes": [plus, minus] if ratio >= 0 else [minus, plus], "des": des}

    def external(self, des, spec):
        """Off-board load at a connector: constant current from pin 'plus' to pin 'minus'."""
        plus = self.pn(f"{des}.{spec['plus']}")
        minus = self.pn(f"{des}.{spec['minus']}")
        if plus is None or minus is None:
            raise ValueError(f"{des}: external load between unconnected pins {spec['plus']} and {spec['minus']}")
        self.current_load(f"{des}_EXT", plus, minus, self.amps(des, spec["i_a"]), des, "load")
        self.meta["elements"][des][-1]["i"] = spec["i_a"]

    def component(self, des):
        part = self.d.part(des)
        sources = self.cfg.get("sources", {})
        supply = self.sc.get("supply", {})
        if des in sources and des in supply:
            self.source(des, sources[des], supply[des])
        if des in self.load.get("external", {}):
            self.external(des, self.load["external"][des])
        if not part:
            return
        kind, p = part["kind"], values(part)
        if kind == "resistor":   # a 0 Ω bridge: ngspice finds no operating point with 0 Ω
            self.two_pole(des, "R", p["value_ohm"] or p.get("r_max_ohm") or BRIDGE_OHM, "resistor")
        elif kind == "capacitor":       # at the DC across it (dc_bias); a net split by a cable: its declared range
            nets = [self.d.pin_net.get(f"{des}.{n}") for n in ("1", "2")]
            nets = [n if n in self.d.nets or not n else n.rsplit("__", 1)[0] for n in nets]
            c = capacitance(part, volts_across(self.d, *nets)) if all(nets) else None
            self.two_pole(des, "C", c if c is not None else p["value_f"], "capacitor")
        elif kind == "fuse":
            self.two_pole(des, "R", p.get("r_max_ohm", 0.1), "fuse")
        elif kind == "inductor":
            a, b = (self.pn(f"{des}.{x}") for x in ("1", "2"))
            self.add(f"L_{des} {a} x_{des.lower()} {p['value_h']:.6g}")
            self.add(f"R_{des} x_{des.lower()} {b} {p.get('dcr_ohm', 0.05)}", des, "inductor",
                     (f"x_{des.lower()}", b), p.get("dcr_ohm", 0.05))
        elif kind == "diode":
            a, k = self.rn(des, "anode"), self.rn(des, "cathode")
            if a and k:
                self.add(f"D_{des} {a} {k} {self.model(des, part)}", des, "diode", (a, k))
        elif kind in ("npn", "pnp"):
            c, b, e = (self.rn(des, x) for x in ("collector", "base", "emitter"))
            self.add(f"Q_{des} {c} {b} {e} {self.model(des, part)}", des, kind, (c, b, e))
            self.leak(des, part, c, b)
        elif kind in ("njfet", "pjfet"):
            dr, g, s = (self.rn(des, x) for x in ("drain", "gate", "source"))
            self.add(f"J_{des} {dr} {g} {s} {self.model(des, part)}", des, kind, (dr, g, s))
        elif kind in ("pmos", "nmos"):
            dr, g, s = (self.rn(des, x) for x in ("drain", "gate", "source"))
            self.add(f"M_{des} {dr} {g} {s} {s} {self.model(des, part)}", des, kind, (dr, g, s))
            g2, s2 = self.rn(des, "gate_2"), self.rn(des, "source_2")
            if g2 and s2:        # a dual MOSFET (FS8205A): the second channel, its drain shared unless drain_2
                d2 = self.rn(des, "drain_2") or dr
                self.add(f"M_{des}_2 {d2} {g2} {s2} {s2} {self.model(des, part)}", des, kind, (d2, g2, s2))
        elif kind == "led":
            self.led(des, part)
        elif kind == "led_rgb":   # the roles say the layout: a common anode, or a common cathode
            for color, *roles in led_roles(part):
                self.led(des, part, color, *roles)
        elif kind == "battery_holder":
            cell_name = supply.get(des)
            if cell_name is None:
                return
            cell = self.cfg["cells"][cell_name]
            count = p.get("cells", 1)
            for s in [""] if count == 1 else [f"_{chr(ord('a') + i)}" for i in range(count)]:
                name = des + s
                plus, minus = self.rn(des, "plus" + s, True), self.rn(des, "minus" + s, True)
                self.add(f"V_{name} x_{name.lower()} {minus} DC {cell['v']}")
                self.add(f"R_{name} x_{name.lower()} {plus} {cell['r']}", des, "battery",
                         (f"x_{name.lower()}", plus), cell["r"])
                self.meta.setdefault("cells", {})[name] = {"des": des, "state": cell_name,
                                                           "branch": f"v_{name}#branch".lower()}
        elif kind == "buzzer":
            a, b = self.rn(des, "plus", True), self.rn(des, "minus", True)
            self.add(f"R_{des} {a} {b} {p['coil_ohm']}", des, "buzzer", (a, b), p["coil_ohm"])
        elif kind in ("motor", "solenoid", "speaker"):   # the winding's DC resistance; a motor at stall
            a, b = self.rn(des, "plus"), self.rn(des, "minus")
            ohm = p.get("impedance_ohm" if kind == "speaker" else "coil_ohm")
            if a and b and a != b and ohm:
                self.add(f"R_{des} {a} {b} {ohm}", des, kind, (a, b), ohm)
        elif kind == "heater":
            self.two_pole(des, "R", p["value_ohm"], "heater")
        elif kind == "optocoupler":
            a, k = self.rn(des, "anode"), self.rn(des, "cathode")
            c, e = self.rn(des, "collector"), self.rn(des, "emitter")
            if a and k:
                model = f"LED_{part.get('lcsc', des)}_opto"
                self.models[model] = led_model(model, p.get("vf_v", 1.2), p.get("vf_at_a", 0.01), 10)
                self.add(f"V_{des}_LA {a} x_{des.lower()}_a 0")
                self.add(f"D_{des} x_{des.lower()}_a {k} {model}", des, "opto_led", (f"x_{des.lower()}_a", k))
                if c and e:          # the transistor passes at least ctr_min times the LED current, as VCE allows
                    self.add(f"B_{des}_CE {c} {e} I = {p.get('ctr_min_ratio', 0.5)}*max(i(V_{des}_LA), 0)"
                             f"*min(1, max(V({c},{e}), 0)/0.2)", des, "opto_out", (c, e))
                if p.get("behavior") == "photomos":
                    self.photomos(des, part)
        elif kind == "relay":
            a, b = self.rn(des, "coil_plus"), self.rn(des, "coil_minus")
            if a and b and a != b:
                self.add(f"R_{des}_COIL {a} {b} {p['coil_ohm']}", des, "relay_coil", (a, b), p["coil_ohm"])
            on = des in self.load.get("relays_on", [])
            for sset in sorted(relay_sets(part)):    # every contact set: "" the first, "_2" the second (DPDT) …
                c, t = self.rn(des, "common" + sset), self.rn(des, ("no" if on else "nc") + sset)
                if c and t and c != t:
                    self.add(f"R_{des}_K{sset.lstrip('_')} {c} {t} {p.get('r_contact_ohm', 0.05)}", des, "switch",
                             (c, t), p.get("r_contact_ohm", 0.05))
            self.meta["relays"][des] = {"on": on, "coil": (a, b)}
        elif kind == "switch":
            if des in self.load.get("open", []):
                return
            a = self.rn(des, "common")
            b = self.rn(des, self.load.get("throw", {}).get(des, "throw_a")) or self.rn(des, "throw_b")
            if a and b:
                self.add(f"R_{des} {a} {b} {p.get('r_on_ohm', 0.05)}", des, "switch", (a, b), p.get("r_on_ohm", 0.05))
        elif kind == "dip_switch":
            closed = self.load.get("dip_closed", {}).get(des, []) if isinstance(self.load.get("dip_closed"), dict) \
                else self.load.get("dip_closed", [])
            for i in range(1, p.get("positions", 8) + 1):
                if closed == "all" or i in closed:
                    a, b = self.rn(des, f"a{i}"), self.rn(des, f"b{i}")
                    if a and b:
                        self.add(f"R_{des}_{i} {a} {b} {p.get('r_on_ohm', 0.1)}", des, "switch", (a, b),
                                 p.get("r_on_ohm", 0.1))
        elif kind == "button":
            if des in self.load.get("buttons", []):
                a, b = self.rn(des, "a"), self.rn(des, "b")
                if a and b:
                    self.add(f"R_{des} {a} {b} {p.get('r_on_ohm', 0.1)}", des, "switch", (a, b), p.get("r_on_ohm", 0.1))
        elif kind == "potentiometer":
            pos = self.load.get("pot", {}).get(des, 0.5) if isinstance(self.load.get("pot"), dict) else 0.5
            ra, rb = max(p["value_ohm"] * pos, 1), max(p["value_ohm"] * (1 - pos), 1)
            w, ea, eb = (self.rn(des, x, True) for x in ("wiper", "end_a", "end_b"))
            self.add(f"R_{des}_a {ea} {w} {ra:.6g}", des, "pot", (ea, w), ra)
            self.add(f"R_{des}_b {w} {eb} {rb:.6g}", des, "pot", (w, eb), rb)
        elif kind == "esd_array":
            self.esd_array(des, part)
        elif kind == "led_strip":       # its rails and pixels as a ladder (strip.py)
            strip.build(self, des, part)
        elif kind in ("ic", "module"):
            behavior = p.get("behavior", "none")
            fn = self.plugin_models.get(behavior) or getattr(self, f"ic_{behavior}", None)
            if fn is None:
                raise ValueError(f"{des}: unknown behaviour model '{behavior}' (built in: ldo, buck, boost, buck_boost, "
                                 "mcu, cc_sink, opamp, logic, current, bridge, charger, protection, matrix_driver, "
                                 "pd_sink, pass_gate, photomos, cc_led_driver, none; or a plugin model)")
            fn(self, des, part) if behavior in self.plugin_models else fn(des, part)

    # --- behaviour models -----------------------------------------------------------------------------------------
    def _gnd_of(self, des):
        return self.rn(des, "gnd") or "0"

    def _regulator(self, des, vin, vout, gnd, kind, p, extra_i=0.0, vin_min=None, extra=None):
        """Output source at vout with an ammeter; input current from vin by kind ('ldo' or 'buck'/'boost'). With
        vin_min: undervoltage lockout – output and input current scaled by `on`, 1 at vin_min and above, 0 at
        vin_min - UVLO_V and below. extra_i: a current the regulator feeds besides its output pin (an MCU's core);
        extra: the same as an expression of time (amps), extra_i then its value at t = 0."""
        tag = des.lower()
        extra = extra_i if extra is None else extra
        vset = p.get("vout_v", 3.3)
        on = "" if vin_min is None else f"min(1, max(V({vin},{gnd})-{vin_min - UVLO_V:.6g}, 0)/{UVLO_V})*"
        self.add(f"V_{des}_AM x_{tag}_o {vout} 0")
        if kind == "ldo":
            self.add(f"B_{des}_O x_{tag}_o {gnd} V = {on}min({vset}, max(V({vin},{gnd})-{p.get('dropout_v', 0.3)}, 0))")
            self.add(f"B_{des}_I {vin} {gnd} I = {on}(max(i(V_{des}_AM),0) + {p.get('iq_a', 0.0)} + {extra})")
        else:
            eta = p.get("efficiency", 0.85)
            self.add(f"B_{des}_O x_{tag}_o {gnd} V = {on}{vset}")
            self.add(f"B_{des}_I {vin} {gnd} I = {on}({vset}*(max(i(V_{des}_AM),0)+{extra})/({eta}*max(V({vin},{gnd}),0.3))"
                     f" + {p.get('iq_a', 0.0)})")
        self.meta["regs"][des] = {"kind": kind, "vin": vin, "vout": vout, "gnd": gnd, "vset": vset,
                                  "ammeter": f"v_{tag}_am#branch", "values": p, "extra_i": extra_i, "vin_min": vin_min}

    def reg_values(self, des, part):
        """The regulator's values; an adjustable one's vout_v from its divider and vref_v (circuit.feedback_vout)."""
        from ..circuit import feedback_vout
        p = dict(values(part))
        if (fb := feedback_vout(self.d, des)) is not None:
            p["vout_v"] = round(fb[0], 6)
        return p

    def ic_ldo(self, des, part):
        self._regulator(des, self.rn(des, "vin", True), self.rn(des, "vout", True), self._gnd_of(des), "ldo",
                        self.reg_values(des, part), vin_min=limits(part).get("vin_min_v"))
        self.meta["regs"][des]["limits"] = limits(part)

    def ic_buck(self, des, part, kind="buck"):
        self._regulator(des, self.rn(des, "vin", True), self.rn(des, "vout", True), self._gnd_of(des), kind,
                        self.reg_values(des, part), vin_min=limits(part).get("vin_min_v"))
        self.meta["regs"][des]["limits"] = limits(part)

    def ic_boost(self, des, part):
        """A boost with a vout pin as buck; an asynchronous one whose output is behind the diode on its switch pin
        (MT3608, no vout pin): switch_boost."""
        if self.rn(des, "vout") is None and self.rn(des, "sw") is not None:
            self.switch_boost(des, part)
        else:
            self.ic_buck(des, part, "boost")

    # --- a boost converter's enable, a constant-current LED buck (maker-coverage FT-5, FT-14) -----------------------
    def probe(self, des, what, expr):
        """A node that holds an expression of the operating point (0 … 1) for the checks to read: x_<des>_<what>."""
        x = f"x_{des.lower()}_{what}"
        self.add(f"B_{des}_{what.upper()} {x} 0 V = {expr}")
        return x

    def switch_boost(self, des, part):
        """An asynchronous boost whose output is no pin of its own (MT3608): the output is the net behind the diode on
        its switch pin (circuit.switch_output), held at vout_v – from the divider and vref_v – while its enable (role
        en) is high; input power = output power / efficiency, plus iq_a, as buck. EN low – at the pin's VIL and below,
        rising to VIH (level, to the fourth power: nothing left at 0 V) – switches it off: the output source lets go
        (between them a conductance of en / BOOST_ON_OHM that only sources – the rectifier lets no current back), the
        input current stops, and the graph's inductor and diode still join the input to the output – VIN − VD at the
        load's current, as the topology has it: no switch disconnects the load (TI SLVA191A). The shutdown current is
        left out; EN unconnected is on."""
        from ..circuit import is_number, switch_output
        p = self.reg_values(des, part)
        vin, gnd = self.rn(des, "vin", True), self._gnd_of(des)
        behind = switch_output(self.d, des)
        if behind is None:
            raise ValueError(f"{des}: a boost without a vout pin needs one diode from its switch pin (role sw) to its "
                             "output")
        if not is_number(p.get("vout_v")):
            raise ValueError(f"{des}: no output voltage – vout_v, or vref_v with its divider on FB (role fb)")
        dio, tag, vset = behind[1], des.lower(), p["vout_v"]
        vout = self.rn(dio, "cathode")
        vin_min = limits(part).get("vin_min_v")
        on = "" if vin_min is None else f"min(1, max(V({vin},{gnd})-{vin_min - UVLO_V:.6g}, 0)/{UVLO_V})*"
        level = self.level(des, part, "en", vin)
        en = self.probe(des, "en", f"({level})**4" if level else "1")
        self.add(f"B_{des}_O x_{tag}_s {gnd} V = {on}{vset}")
        self.add(f"B_{des}_G x_{tag}_s x_{tag}_o I = V({en})*max(V(x_{tag}_s)-V(x_{tag}_o), 0)/{BOOST_ON_OHM}")
        self.add(f"V_{des}_AM x_{tag}_o {vout} 0")
        eta = p.get("efficiency", 0.85)
        self.add(f"B_{des}_I {vin} {gnd} I = {on}V({en})*({vset}*max(i(V_{des}_AM),0)/({eta}*max(V({vin},{gnd}),0.3))"
                 f" + {p.get('iq_a', 0.0)})")
        self.meta["regs"][des] = {"kind": "boost", "vin": vin, "vout": vout, "gnd": gnd, "vset": vset,
                                  "ammeter": f"v_{tag}_am#branch", "values": p, "extra_i": 0.0, "vin_min": vin_min,
                                  "limits": limits(part), "enable": en, "diode": dio}

    def led_string(self, start, stop):
        """(LEDs, inductors) of a constant-current buck's string: from the net `start` (its sense pin) on through LEDs,
        anode to cathode, and inductors, up to the net `stop` (its switch pin)."""
        leds, coils, seen, todo = [], [], {start, stop}, [start]
        while todo:
            net = todo.pop()
            for ref in self.d.nets.get(net, {}).get("pins", []):
                x = ref.split(".", 1)[0]
                kind = (self.d.part(x) or {}).get("kind")
                if kind == "led" and self.d.net_of(x, "anode") == net and x not in leds:
                    leds.append(x)
                    nxt = self.d.net_of(x, "cathode")
                elif kind == "inductor" and x not in coils:
                    coils.append(x)
                    nxt = next((n for n in (self.d.pin_net.get(f"{x}.{p}") for p in ("1", "2")) if n != net), None)
                else:
                    continue
                if nxt and nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        return leds, coils

    def ic_cc_led_driver(self, des, part):
        """Constant-current step-down LED driver with high-side sense (PT4115, AL8860): roles vin, sense, sw, gnd, dim.
        The resistors from the vin net to the sense net (R_S, in parallel) set I = vsense_v / R_S – the top of vsense_v
        [min, typ, max], the upper bound every check uses –, scaled by dim: off at the pin's VIL and below, full at VIH
        and above, linear in between (the datasheets' DC dimming differs in detail). A pin's own pull-up to an internal
        supply (pull up, pull_ohm, pull_v) is in the operating point; a dim pin without one that only capacitors touch
        floats – on, as both datasheets say; unconnected, or without vih_v and vil_v: on. The switch pulls that current
        into SW – the LED string between sense and SW, through the inductor, carries it – as far as it can: at most
        (V(sw) − (1 − D_max) × V(vin)) / (D_max × r_on_ohm), on for its maximum duty cycle duty_max_ratio (default 1).
        Of the current the share D = 1 − V(sw) / V(vin) goes to ground, the rest back to vin – the freewheeling
        diode's –: the input current of an ideal buck, D × I, the diode's and the switch's losses left out (the graph's
        diode stays blocked). Off below uvlo_v; iq_a from vin."""
        from ..circuit import resistors_to
        p, tag = values(part), des.lower()
        vin, sw, gnd = self.rn(des, "vin"), self.rn(des, "sw"), self._gnd_of(des)
        vin_net, sense_net, sw_net = (self.d.net_of(des, r) for r in ("vin", "sense", "sw"))
        if vin is None or sw is None:
            return
        rs = [x for _, x, _ in resistors_to(self.d, sense_net, {vin_net}) if x and x > 0] \
            if sense_net and vin_net else []
        r_s = 1 / sum(1 / x for x in rs) if rs else None
        vs = [x for x in (p.get("vsense_v") if isinstance(p.get("vsense_v"), list) else [p.get("vsense_v")])
              if isinstance(x, (int, float))]
        i_set = max(vs) / r_s if r_s and vs else 0.0
        frac = "1"
        ref = self.role_pins(des).get("dim")
        if ref:
            info, node = part["pins"][ref.split(".", 1)[1]], self.pn(ref)
            pulled = info.get("pull") == "up" and info.get("pull_ohm") and info.get("pull_v") is not None
            if pulled:
                self.add(f"V_{des}_PULL x_{tag}_pull {gnd} DC {info['pull_v']}")
                self.add(f"R_{des}_PULL x_{tag}_pull {node} {info['pull_ohm']:.6g}")
            others = [r for r in self.d.nets[self.d.pin_net[ref]]["pins"] if r.split(".", 1)[0] != des]
            floating = not pulled and all((self.d.part(r.split(".", 1)[0]) or {}).get("kind") == "capacitor"
                                          for r in others)
            vil, vih = info.get("vil_v"), info.get("vih_v")
            if not floating and isinstance(vil, (int, float)) and isinstance(vih, (int, float)) and vih > vil:
                x = f"(V({node},{gnd})-{vil:g})/{vih - vil:g}"
                frac = smooth(min, smooth(max, x, "0", 1e-4), "1", 1e-4)
        dim = self.probe(des, "dim", frac)
        dmax, r_on, uvlo = p.get("duty_max_ratio", 1.0), p.get("r_on_ohm", 0.0), p.get("uvlo_v")
        rest = f"-{1 - dmax:g}*V({vin},{gnd})" if dmax < 1 else ""
        lim = f"max(V({sw},{gnd}){rest}, 0)/{max(dmax * r_on, 1e-3):g}"
        on = f"0.5*(1+tanh((V({vin},{gnd})-{uvlo:g})/0.02))*" if uvlo else ""
        i_tot = f"{on}V({dim})*{smooth(min, f'{i_set:.6g}', lim, 1e-3)}"
        duty = f"min(max(1-V({sw},{gnd})/max(V({vin},{gnd}),0.1), 0), 1)"
        self.add(f"V_{des}_AM {sw} x_{tag}_sw 0")
        self.add(f"B_{des}_SW x_{tag}_sw {gnd} I = {duty}*{i_tot}")
        self.add(f"B_{des}_FW x_{tag}_sw {vin} I = (1-{duty})*{i_tot}")
        if p.get("iq_a"):
            self.current_load(f"{des}_IQ", vin, gnd, p["iq_a"])
        leds, coils = self.led_string(sense_net, sw_net) if sense_net and sw_net else ([], [])
        self.meta.setdefault("cc_bucks", {})[des] = {
            "vin": vin, "sw": sw, "gnd": gnd, "ammeter": f"v_{tag}_am#branch", "r_s": r_s, "vsense": vs,
            "i_set": i_set, "dim": dim, "values": p, "limits": limits(part), "coils": coils,
            "leds": [f"d_{x}".lower() for x in leds],
            "parallel": max(1, sum(1 for x in leds if self.d.net_of(x, "anode") == sense_net))}

    def ic_mcu(self, des, part):
        p = values(part)
        rp = self.role_pins(des)
        vin = self.pn(rp.get("vsys") or rp.get("vin") or rp.get("vdd"))
        vout = self.pn(rp.get("vout") or rp.get("3v3"))
        v_io = p.get("v_io_v", 3.3)  # a number, or "vin": the I/O runs from the supply pin (5 V AVR boards)
        mcfg = self.cfg.get("mcu", {}).get(des) or self.cfg.get("mcu", {})
        i_core = core_current(des, p, self.sc.get("least_current", False))
        if vout and p.get("regulator"):
            vset = p.get("vout_v", v_io)
            if not isinstance(vset, (int, float)):
                raise ValueError(f"{des}: v_io_v = '{v_io}' – give the on-board regulator's output as values vout_v")
            r = limits(part)
            self._regulator(des, vin, vout, "0", p["regulator"], {**p, "vout_v": vset}, extra_i=i_core,
                            vin_min=r.get("vin_min_v", r.get("vsys_min_v")), extra=self.amps(des, i_core))
        elif vin:
            self.current_load(f"{des}_CORE", vin, "0", self.amps(des, i_core))
        gpio = {self.d.pin_net.get(f"{des}.{n}") for n, i in part["pins"].items() if i.get("role") == "gpio"}
        rail = (self.pn(self.pin_on(des, mcfg["io_rail"])) or self.n(mcfg["io_rail"])) if mcfg.get("io_rail") \
            else (vin if v_io == "vin" else vout or vin)
        ammeters, cannot_drive = {}, []
        for net in mcfg.get("outputs", []):
            pins = [i for n, i in part["pins"].items() if self.d.pin_net.get(f"{des}.{n}") == net]
            if pins and not any(i.get("type") in ("output", "bidirectional") for i in pins):
                cannot_drive.append((net, "/".join(i["name"] for i in pins)))  # an input-only pin
            elif net in gpio and net in self.load.get("gpio", {}) and self.load["gpio"][net] is None:
                continue          # released in this load: an input (a matrix row not scanned), its pull-up holds it
            elif net in gpio:
                ammeters[net] = f"v_{des}_{net}_am#branch".lower()
                x = f"x_{des.lower()}_{net.lower()}"
                if self.gpio_level(net) and v_io == "vin":
                    self.add(f"B_{des}_{net} {x}s 0 V = V({vin})")
                else:
                    self.add(f"V_{des}_{net} {x}s 0 DC {v_io if self.gpio_level(net) else 0}")
                self.add(f"V_{des}_{net}_AM {x}s {x} 0")
                self.add(f"R_{des}_{net} {x} {self.pn(self.pin_on(des, net))} {p.get('gpio_r_out_ohm', 30)}")
                if self.gpio_level(net) and rail:  # what a high output sources comes out of the I/O supply
                    self.add(f"B_{des}_{net}_SUP {rail} 0 I = max(i(V_{des}_{net}_AM), 0)")
        for net in mcfg.get("pullups", []):
            if net in gpio and rail:
                self.add(f"R_{des}_PU_{net} {rail} {self.pn(self.pin_on(des, net))} {mcfg.get('pullup_ohm', 50000)}")
        self.meta["mcu"][des] = {"vin": vin, "vout": vout, "values": p, "limits": limits(part),
                                 "io_rail": rail if v_io == "vin" or mcfg.get("io_rail") else None,
                                 "inputs": [net for net in mcfg.get("inputs", []) if net in gpio],
                                 "input_nodes": {net: self.pn(self.pin_on(des, net)) for net in mcfg.get("inputs", [])
                                                 if net in gpio},
                                 "gpio_ammeters": ammeters, "cannot_drive": cannot_drive}

    def ic_cc_sink(self, des, part):
        p = values(part)
        nets = {i.get("role"): self.d.pin_net.get(f"{des}.{n}") for n, i in part["pins"].items() if i.get("role")}
        vdd = self.rn(des, "vdd")
        if vdd:
            self.current_load(f"{des}_VDD", vdd, "0", p.get("idd_max_a", 0.01))
        self.add(f"V_{des}_REXT {self.rn(des, 'rext', True)} 0 DC {p['vrext_v']}")
        oe = nets.get("oe_n")
        enabled = oe is None or self.gpio_level(oe, default=1) == 0
        want = self.load.get("cc_on", {}).get(des, []) if isinstance(self.load.get("cc_on"), dict) else []
        chans = {}
        for num, info in part["pins"].items():
            if not out_role(info.get("role")):
                continue
            net = self.d.pin_net.get(f"{des}.{num}")
            if net is None:
                continue
            o = self.pn(f"{des}.{num}")
            on = enabled and (want == "all" or net in want or info["name"] in want)
            if on:
                y = f"y_{des.lower()}_{num}"
                self.add(f"V_{des}_A{num} {o} {y} 0")
                self.add(f"B_{des}_O{num} {y} 0 I = {p['iout_gain']}*max(-i(V_{des}_REXT),0)"
                         f"*(1-exp(-max(V({y}),0)/0.15))")
            else:
                self.add(f"R_{des}_OFF{num} {o} 0 100Meg")
            chans[net] = {"on": on, "ammeter": f"v_{des.lower()}_a{num}#branch", "node": o}
        for num, info in part["pins"].items():     # the serial data output (SDO): low through 50 Ω, as in 'logic'
            net = self.d.pin_net.get(f"{des}.{num}")
            if net and info.get("type") == "output":
                self.add(f"R_{des}_{num} {self.pn(f'{des}.{num}')} 0 50")
        self.meta["cc"][des] = {"rext_src": f"v_{des.lower()}_rext#branch", "vdd": vdd, "channels": chans,
                                "values": p, "limits": limits(part)}

    def ic_opamp(self, des, part):
        p = values(part)
        vcc = self.rn(des, "vcc", True)
        vee = self.rn(des, "vee") or self.rn(des, "gnd") or "0"
        lo, hi = (p.get("vout_swing_v") or [0, 0])[:2]
        chans = {}
        for role, ref in self.role_pins(des).items():
            m = OPAMP_ROLE.match(role)
            if m:
                chans.setdefault((m.group(2) or "")[1:], {})[m.group(1)] = self.pn(ref)
        tag = des.lower()
        for ch, n in sorted(chans.items()):
            if not {"in_p", "in_n", "out"} <= set(n):
                raise ValueError(f"{des}: channel {ch or '–'} needs the roles in_p, in_n and out")
            x = f"x_{tag}_{ch or 'o'}"
            ideal = f"{A_OL}*(V({n['in_p']})-V({n['in_n']}))"
            top = smooth(min, ideal, f"V({vcc})+{hi}")       # a hard min/max does not converge
            self.add(f"B_{des}_O{ch} {x}s 0 V = {smooth(max, top, f'V({vee})+{lo}')}")
            self.add(f"V_{des}_A{ch} {x}s {x} 0")
            self.add(f"R_{des}_R{ch} {x} {n['out']} {p.get('r_out_ohm', 50)}", des, "opamp_out", (x, n["out"]),
                     p.get("r_out_ohm", 50))
            for k in ("in_p", "in_n"):
                self.add(f"R_{des}_{k}{ch} {n[k]} 0 1e12")
            chans[ch] = {**n, "ammeter": f"v_{tag}_a{ch}#branch".lower()}
        if p.get("iq_a"):
            self.current_load(f"{des}_IQ", vcc, vee, p["iq_a"])
        self.meta.setdefault("opamps", {})[des] = {"vcc": vcc, "vee": vee, "channels": chans, "values": p}

    def ic_logic(self, des, part):
        """A logic part – a sensor, a transceiver, a USB-UART: its supply current icc_a – a number at its supply pin
        (supply_pins), or {pin name: A} per supply pin – to its ground pin, and every output in its state
        (logic_states): low through r_out_ohm (50 Ω) to ground; high through it to its supply – the pin its `ref`
        names, else the supply pin –, which delivers what the output sources (ammeter in meta["logic"]); off not at
        all."""
        p, pins = values(part), part["pins"]
        connected = {n for n in pins if self.d.pin_net.get(f"{des}.{n}")}
        gnd = next((self.pn(f"{des}.{n}") for n, i in pins.items() if i.get("type") == "ground" and n in connected), "0")
        icc = p.get("icc_a", 0.001)
        draw = {pin_of(pins, name): a for name, a in icc.items()} if isinstance(icc, dict) \
            else dict.fromkeys(supply_pins(pins), icc)
        for num, a in draw.items():
            if num in connected:
                self.current_load(f"{des}_{num}", self.pn(f"{des}.{num}"), gnd, a)
        r_out = p.get("r_out_ohm", 50)
        rails = [n for n in supply_pins(pins) if n in connected]
        out = self.meta.setdefault("logic", {})[des] = {}
        for num, state in logic_states(self.d, des, part).items():
            o = self.pn(f"{des}.{num}")
            sup = pin_of(pins, pins[num].get("ref")) or (rails[0] if rails else None)
            if state == "low":
                self.add(f"R_{des}_{num} {o} {gnd} {r_out}")
            elif state == "high" and sup in connected:
                x, s = f"x_{des.lower()}_{num}", self.pn(f"{des}.{sup}")
                self.add(f"B_{des}_{num} {x}s {gnd} V = V({s},{gnd})")
                self.add(f"V_{des}_{num}_AM {x}s {x} 0")
                self.add(f"R_{des}_{num} {x} {o} {r_out}")
                self.add(f"B_{des}_{num}_SUP {s} {gnd} I = max(i(V_{des}_{num}_AM), 0)")   # sourced from its supply
                out[num] = {"state": state, "node": o, "ammeter": f"v_{des}_{num}_am#branch".lower()}
                continue
            out[num] = {"state": "off" if state == "high" else state, "node": o}

    def ic_current(self, des, part):
        for num, info in part["pins"].items():
            net = self.d.pin_net.get(f"{des}.{num}")
            if net and info["type"] == "power_in":
                self.current_load(f"{des}_{num}", self.pn(f"{des}.{num}"), "0", self.amps(des, values(part).get("i_a", 0.001)))

    def ic_none(self, des, part):
        pass

    def ic_matrix_driver(self, des, part):
        """A multiplexing LED driver (MAX7219): its segment and digit outputs scan the LEDs between them – no DC state
        to model; engines/sim.py leaves those LEDs out of SIM.state and SIM.driver and says so."""

    # --- W5: a USB PD sink, a pass-gate translator, a photo-MOS output, an ESD array ------------------------------
    def ic_pd_sink(self, des, part):
        """A USB PD sink (CH224K): its VDD a shunt regulator – it holds VDD at vdd_shunt_v by sinking current, up to
        i_shunt_max_a, from the series resistor the board feeds it through; beyond that VDD rises. The voltage it
        requests from the charger by its configuration pins (values pd_request_v) is REQ.value/pd_request's, stage G;
        the charger itself is the project's source of sources (sim.json)."""
        p = values(part)
        vdd, gnd = self.rn(des, "vdd"), self._gnd_of(des)
        vset = p.get("vdd_shunt_v")
        vset = vset[1] if isinstance(vset, list) and len(vset) > 1 and vset[1] is not None else vset
        if vdd is None or vset is None:
            return
        tag = des.lower()
        i_max = p.get("i_shunt_max_a", 0.03)
        self.add(f"V_{des}_SH {vdd} x_{tag}_sh 0")
        self.add(f"B_{des}_SH x_{tag}_sh {gnd} I = min({i_max}, max(V(x_{tag}_sh,{gnd})-{vset}, 0)/{PD_SHUNT_OHM})",
                 des, "pd_shunt", (vdd, gnd))
        self.meta.setdefault("pd_sinks", {})[des] = {"ammeter": f"v_{tag}_sh#branch", "vdd": vdd, "gnd": gnd,
                                                     "vset": vset, "i_max_a": i_max}

    def ic_pass_gate(self, des, part):
        """A pass-gate translator (PCA9306 class): per channel a switch between a<n> and b<n> through r_on_ohm that
        conducts while the lower side sits below the reference vref1 – the gate of the pass transistor follows
        vref1 by vgs_th_v, so a side pulled low passes, two released sides stay apart at their own pull-ups – and
        only while en is above vref1. Values r_on_ohm, vgs_th_v (a number); roles vref1, en, a1/b1, a2/b2 …"""
        p = values(part)
        rp = self.role_pins(des)
        ref, en = self.pn(rp.get("vref1")), self.pn(rp.get("en"))
        if ref is None:
            return
        r_on = p.get("r_on_ohm", 5.0)
        r_on = max(x for x in r_on if x is not None) if isinstance(r_on, list) else r_on
        enable = f"min(1, max(V({en})-V({ref}), 0)/{PASS_GATE_KNEE_V})" if en else "1"
        for role, ref_a in sorted(rp.items()):
            if not role.startswith("a") or not role[1:].isdigit() or f"b{role[1:]}" not in rp:
                continue
            a, b = self.pn(ref_a), self.pn(rp[f"b{role[1:]}"])
            low = smooth(min, f"V({a})", f"V({b})")
            on = f"min(1, max(V({ref})-{low}, 0)/{PASS_GATE_KNEE_V})"
            self.add(f"B_{des}_{role.upper()} {a} {b} I = (V({a})-V({b}))/{r_on}*{on}*{enable}", des, "pass_gate",
                     (a, b))

    def photomos(self, des, part):
        """A photo-MOS output (AQY212): between load_a and load_b a resistance both ways – r_on_ohm (its maximum) while
        the LED carries if_on_a or more, the off-state leakage i_leak_a at v_load_max_v below if_off_a, linear in
        between. The LED is the optocoupler's (its ammeter V_<des>_LA)."""
        p, r = values(part), limits(part)
        a, b = self.rn(des, "load_a"), self.rn(des, "load_b")
        if not a or not b or a == b:
            return
        r_on = p.get("r_on_ohm", 1.0)
        r_on = max(x for x in r_on if x is not None) if isinstance(r_on, list) else r_on
        i_on, i_off = p.get("if_on_a", 0.005), p.get("if_off_a", 0.0)
        g_off = p.get("i_leak_a", 0.0) / r.get("v_load_max_v", 1.0) if p.get("i_leak_a") else 1e-12
        lit = f"min(1, max(i(V_{des}_LA)-{i_off}, 0)/{max(i_on - i_off, 1e-9)})"
        x = f"x_{des.lower()}_ld"
        self.add(f"V_{des}_LD {a} {x} 0")
        self.add(f"B_{des}_LOAD {x} {b} I = (V({x})-V({b}))*({g_off} + {lit}/{r_on})", des, "photomos", (a, b))
        self.meta.setdefault("photomos", {})[des] = {"led": f"v_{des.lower()}_la#branch", "nodes": (a, b),
                                                     "ammeter": f"v_{des.lower()}_ld#branch", "r_on": r_on,
                                                     "if_on_a": i_on, "if_off_a": i_off}

    def esd_array(self, des, part):
        """An ESD array (USBLC6-2): from each protected line (roles io<n>) a steering diode to the rail (vbus) and one
        from ground, and from the rail a transil to ground breaking down at vbr_min_v – in normal operation they carry
        nothing; a line beyond its rail or below ground does."""
        p = values(part)
        rail, gnd = self.rn(des, "vbus"), self._gnd_of(des)
        vf, at = p.get("vf_v", 1.0), p.get("vf_at_a", 0.01)
        model = f"ESD_{part.get('lcsc', des)}"
        n, rs = 1.5, 1.0                  # a silicon steering diode: no reverse breakdown in its working range
        i_s = at / (math.exp((vf - at * rs) / (n * VT)) - 1)
        self.models[model] = f".model {model} D(IS={i_s:.4e} N={n} RS={rs} BV=100)"
        done = set()
        for role, ref in sorted(self.role_pins(des).items()):
            if not role.startswith("io"):
                continue
            io = self.pn(ref)
            if io in done:
                continue
            done.add(io)
            if rail:
                self.add(f"D_{des}_{role}H {io} {rail} {model}", des, "esd_diode", (io, rail))
            self.add(f"D_{des}_{role}L {gnd} {io} {model}", des, "esd_diode", (gnd, io))
        if rail and p.get("vbr_min_v"):
            zener = f"ESDZ_{part.get('lcsc', des)}"
            self.models[zener] = f".model {zener} D(IS=1e-12 N=1 BV={p['vbr_min_v']} IBV=1e-3 RS=0.5)"
            self.add(f"D_{des}_Z {gnd} {rail} {zener}", des, "esd_diode", (gnd, rail))

    # --- bridge drivers, chargers, cell protection (schema-gaps E2–E4) ----------------------------------------------
    def level(self, des, part, role, supply=None):
        """A logic input's level as an expression from 0 (low) to 1 (high), smooth between its VIL and VIH – the pin's
        own vih_v/vil_v, else the part's, else the part's vih_ratio/vil_ratio of `supply` (a node) – or None when the
        role's pin is not connected. The step is an eighth of VIH − VIL wide: an input at its rail leaves a residue
        of about 1e-9, an output switched off by it no conductance worth a current (a quarter left 5e-5 of
        1/r_on – a milliampere through a stopped motor)."""
        ref = self.role_pins(des).get(role)
        if ref is None:
            return None
        pin, p = part["pins"][ref.split(".", 1)[1]], values(part)
        vih, vil = pin.get("vih_v", p.get("vih_v")), pin.get("vil_v", p.get("vil_v"))
        if vih is None or vil is None:
            hi, lo = p.get("vih_ratio", 0.7), p.get("vil_ratio", 0.3)
            vs = f"V({supply})" if supply else "3.3"
            mid, w = f"({(hi + lo) / 2:g}*{vs})", f"max({(hi - lo) / 8:g}*{vs}, 0.01)"
        else:
            mid, w = f"{(vih + vil) / 2:g}", f"{max((vih - vil) / 8, 0.01):g}"
        return f"(0.5*(1+tanh((V({self.pn(ref)})-{mid})/{w})))"

    def ic_bridge(self, des, part):
        """Bridge driver (DRV8833, TB6612): per channel the roles in1_x, in2_x, out1_x, out2_x, optional pwm_x and
        sense_x (the low side's return, DRV8833 xISEN – else gnd); vm the bridge supply, en the enable (DRV8833 nSLEEP,
        TB6612 STBY – high runs), vcc a logic supply. The outputs follow the common truth table of both datasheets:
        IN1 IN2 = 1 0 forward (OUT1 high, OUT2 low), 0 1 reverse, 1 1 brake (both low), 0 0 coast (both off); PWM low
        brakes a driven channel; en low turns every output off. A high side is a conductance 1/r_on_high_ohm to vm, a
        low side 1/r_on_low_ohm to its return, each scaled by the smooth input levels; idd_max_a at vcc (else vm)."""
        p, tag = values(part), des.lower()
        vm, gnd = self.rn(des, "vm"), self._gnd_of(des)
        vcc = self.rn(des, "vcc")
        if vm is None:
            return
        r_hi, r_lo = p.get("r_on_high_ohm", p.get("r_out_ohm", 1.0)), p.get("r_on_low_ohm", p.get("r_out_ohm", 1.0))
        en = self.level(des, part, "en", vcc or vm) or "1"
        chans = {}
        for role in self.role_pins(des):
            m = re.match(r"^(in1|in2|out1|out2|pwm|sense)_([a-z0-9]+)$", role)
            if m:
                chans.setdefault(m.group(2), set()).add(m.group(1))
        outs = {}
        for ch in sorted(chans):
            a = self.level(des, part, f"in1_{ch}", vcc or vm)
            b = self.level(des, part, f"in2_{ch}", vcc or vm)
            if a is None or b is None:
                continue
            pwm = self.level(des, part, f"pwm_{ch}", vcc or vm) or "1"
            ret = self.rn(des, f"sense_{ch}") or gnd
            drive = {"1": (f"{en}*{a}*(1-{b})*{pwm}", f"{en}*({b}+{a}*(1-{b})*(1-{pwm}))"),
                     "2": (f"{en}*{b}*(1-{a})*{pwm}", f"{en}*({a}+{b}*(1-{a})*(1-{pwm}))")}
            for k, (hi, lo) in drive.items():
                o = self.rn(des, f"out{k}_{ch}")
                if o is None:
                    continue
                x = f"x_{tag}_{ch}{k}"
                self.add(f"B_{des}_H{ch}{k} {vm} {x}h I = {hi}*V({vm},{x}h)/{r_hi}")
                self.add(f"V_{des}_AH{ch}{k} {x}h {o} 0")
                self.add(f"B_{des}_L{ch}{k} {o} {x}l I = {lo}*V({o},{x}l)/{r_lo}")
                self.add(f"V_{des}_AL{ch}{k} {x}l {ret} 0")
                outs[f"out{k}_{ch}"] = {"node": o, "vm": vm, "ret": ret,
                                        "high": f"v_{tag}_ah{ch}{k}#branch", "low": f"v_{tag}_al{ch}{k}#branch"}
        if p.get("idd_max_a"):
            self.current_load(f"{des}_IDD", vcc or vm, gnd, p["idd_max_a"])
        self.meta.setdefault("bridges", {})[des] = {"vm": vm, "gnd": gnd, "vcc": vcc, "outputs": outs, "values": p}

    def ic_charger(self, des, part):
        """Linear Li-ion charger (TP4056, MCP73831): roles vin, bat, prog, gnd. Constant current prog_v / R_PROG (the
        resistors from PROG to ground, in parallel) – i_pre_ratio of it below v_pre_v (precondition) –, constant voltage
        at vout_v (the float voltage): the current falls to 0 as the cell reaches it, held by a stiffness of
        CHARGER_CV_OHM. The pass element limits the current to (V(vin) − V(bat) − v_headroom_v) / r_on_ohm; below
        uvlo_v at vin, and without a PROG resistor, it does not charge. iq_a from vin. Termination (i_term_ratio) is a
        state of the charge cycle, not of an operating point: the model charges while the cell is below the float
        voltage."""
        from ..circuit import resistors_to
        p, tag = values(part), des.lower()
        vin, bat, gnd = self.rn(des, "vin"), self.rn(des, "bat"), self._gnd_of(des)
        prog_net = self.d.net_of(des, "prog")
        if vin is None or bat is None:
            return
        rs = [r for _, r, _ in resistors_to(self.d, prog_net, {self.d.ground}) if r and r > 0] if prog_net else []
        r_prog = 1 / sum(1 / r for r in rs) if rs else None
        i_set = p["prog_v"] / r_prog if r_prog and p.get("prog_v") else 0.0
        pre, v_pre = p.get("i_pre_ratio", 1.0), p.get("v_pre_v", 0.0)
        cc = f"{i_set:.6g}*({pre:g}+{1 - pre:g}*0.5*(1+tanh((V({bat},{gnd})-{v_pre:g})/0.01)))"
        cv = f"({p.get('vout_v', 4.2):g}-V({bat},{gnd}))/{CHARGER_CV_OHM}"
        head = smooth(max, f"V({vin},{bat})-{p.get('v_headroom_v', 0.0):g}", "0", 0.01)   # smooth: Newton converges
        drop = f"({head})/{p.get('r_on_ohm', 0.5):g}"
        on = f"0.5*(1+tanh((V({vin},{gnd})-{p.get('uvlo_v', 0.0):g})/0.02))"
        i_expr = f"{on}*{smooth(max, smooth(min, smooth(min, cc, cv, 1e-3), drop, 1e-3), '0', 1e-4)}"
        self.add(f"B_{des}_CH {vin} x_{tag}_bat I = {i_expr}")
        self.add(f"V_{des}_AM x_{tag}_bat {bat} 0")
        if p.get("iq_a"):
            self.current_load(f"{des}_IQ", vin, gnd, p["iq_a"])
        self.meta.setdefault("chargers", {})[des] = {"vin": vin, "bat": bat, "gnd": gnd, "i_set": i_set,
                                                     "r_prog": r_prog, "ammeter": f"v_{tag}_am#branch", "values": p}

    def ic_protection(self, des, part):
        """One-cell protection IC (DW01A): roles vdd (the cell through its resistor), gnd (the cell's minus), od
        (discharge MOSFET's gate), oc (charge MOSFET's gate), vm (current sense, the pack's minus through a resistor).
        OD high – at vdd – while the cell is above v_uvp_v (overdischarge) and VM below v_ocp_v (overcurrent), else at
        gnd; OC high while the cell is below v_ovp_v (overcharge), else at VM (the datasheet's timing: OC low follows
        VM). Above v_ovp_v the overcurrent comparison is off and OD stays high, as in the timing diagram (Rev B p. 5:
        OD at VCC through the overcharge state, the cell discharges through the charge MOSFET's body diode) – the
        charger pulls the pack's minus above the cell's there. The release voltages (v_uvp_release_v,
        v_ovp_release_v) and the delays need the history an operating point does not have: the model is the state of a
        cell coming from the normal range. Within a few 10 mV of a threshold the comparator's 20 mV step and the
        circuit can form a loop the operating point may not converge in. Each output behind r_out_ohm."""
        p, tag = values(part), des.lower()
        vdd, gnd = self.rn(des, "vdd"), self._gnd_of(des)
        if vdd is None:
            return
        vm = self.rn(des, "vm") or gnd
        cell = f"V({vdd},{gnd})"

        def step(x):
            return f"0.5*(1+tanh(({x})/0.02))"
        uvp, ocp, ovp = p.get("v_uvp_v", 0.0), p.get("v_ocp_v", 1e3), p.get("v_ovp_v", 1e3)
        oc_on = step(f"{ovp:g}-{cell}")
        od_on = f"{step(f'{cell}-{uvp:g}')}*(1-{step(f'V({vm},{gnd})-{ocp:g}')}*{oc_on})"
        r = p.get("r_out_ohm", 1e3)
        for role, level, low in (("od", od_on, gnd), ("oc", oc_on, vm)):
            o = self.rn(des, role)
            if o is None:
                continue
            self.add(f"B_{des}_{role.upper()} x_{tag}_{role} 0 V = V({low})+{level}*(V({vdd})-V({low}))")
            self.add(f"R_{des}_{role.upper()} x_{tag}_{role} {o} {r:g}")
        if p.get("iq_a"):
            self.current_load(f"{des}_IQ", vdd, gnd, p["iq_a"])
        self.meta.setdefault("protections", {})[des] = {"vdd": vdd, "gnd": gnd, "vm": vm, "values": p}

    def ic_buck_boost(self, des, part):
        """Buck-boost regulator (the Raspberry Pi Pico's RT6150): as buck and boost – an ideal output at vout_v whether
        the input is above or below it, input power = output power / efficiency."""
        self.ic_buck(des, part, "buck_boost")

    # --- build ----------------------------------------------------------------------------------------------------
    def build(self, tran=None):
        for des in sorted(self.d.comps):
            self.component(des)
        self.window_pulls()
        for el in getattr(self.d, "cable_elements", []):
            a, b = self.pn(el["pa"]), self.pn(el["pb"])
            if el.get("l"):          # the wire's inductance after its resistance: an LC spike at hot-plug
                x = f"x_{el['name'].lower()}"
                self.add(f"{el['name']} {a} {x} {el['r']:.6g}", el["des"], "connector", (a, x), el["r"])
                self.add(f"L{el['name'][1:]} {x} {b} {el['l']:.6g}")
            else:
                self.add(f"{el['name']} {a} {b} {el['r']:.6g}", el["des"], "connector", (a, b), el["r"])
        for name, a, b, r in (getattr(self.d, "copper", None) or {}).get("elements", []):   # tracks and vias
            self.add(f"R_CU_{name} {a} {b} {r:.6g}")
        for i, ref in enumerate(self.sc.get("short", [])):   # a generated fault: a pin shorted to ground (FT-8)
            self.add(f"R_FAULT{i} {self.pn(ref)} 0 {FAULT_SHORT_OHM}")
        prints = ["print all"]
        for els in self.meta["elements"].values():
            for el in els:
                if el["kind"] in ("led", "diode"):
                    prints.append(f"print @{el['name']}[id]")
                elif el["kind"] in ("npn", "pnp"):
                    prints.append(f"print @{el['name']}[ic] @{el['name']}[ib]")
                elif el["kind"] in ("pmos", "nmos"):
                    prints.append(f"print @{el['name']}[id]")
                elif el["kind"] in ("njfet", "pjfet"):
                    prints.append(f"print @{el['name']}[id] @{el['name']}[ig]")
        body = "\n".join(self.lines)
        models = "\n".join(self.models.values())
        control = "op\n" + "\n".join(prints) if tran is None else self.tran_control(tran)
        return (f"edakit {self.sc['name']}\n{body}\n{models}\n"
                f".options gmin=1e-12 reltol=1e-4 itl1=500 rshunt=1e12\n.control\n{control}\n.endc\n.end\n")

    def window_pulls(self):
        """A configuration pin's own pull (pin windows with pull up|down and pull_ohm – MAX98357A SD_MODE's 100 kΩ to
        ground): it sets, with the board's resistors, the voltage the pin's windows read (REQ.value/window). Only pins
        with windows: the other pins' pulls stay out of the operating point as before."""
        for des in sorted(self.d.comps):
            pins = (self.d.part(des) or {}).get("pins") or {}
            on = {t: next((f"{des}.{n}" for n, p in pins.items() if p.get("type") == t
                           and self.d.pin_net.get(f"{des}.{n}")), None) for t in ("ground", "power_in")}
            for num, p in pins.items():
                ref = f"{des}.{num}"
                if not p.get("windows") or not p.get("pull_ohm") or p.get("pull") not in ("up", "down") \
                        or not self.d.pin_net.get(ref):
                    continue
                to = on["power_in" if p["pull"] == "up" else "ground"]
                self.add(f"R_PULL_{des}_{num} {self.pn(ref)} {self.pn(to) if to else '0'} {p['pull_ohm']:.6g}")

    def tran_control(self, tran):
        """.tran from the operating point at t = 0 (every source at its first point), the voltages of the nets in
        tran["nets"] and of every MCU supply pin and the current of every source written to tran["file"] (wrdata, one
        time column); their order in meta["tran"]["columns"]."""
        present = {t for line in self.lines for t in line.split()}
        nodes = [x for net in tran["nets"] for x in net_nodes(self.d, net)] + [m["vin"] for m in self.meta["mcu"].values()]
        nodes = list(dict.fromkeys(x for x in nodes if x and x != "0" and x in present))
        branches = [s["branch"] for s in self.meta["sources"].values()]
        self.meta["tran"] = {"columns": nodes + branches, "file": tran["file"]}
        vectors = [f"v({x})" for x in nodes] + [f"i({b.split('#')[0]})" for b in branches]
        lines = [f"tran {tran['step_s']:.6g} {tran['stop_s']:.6g}"]
        if vectors:
            lines += ["set wr_singlescale", "set wr_vecnames", f"wrdata {tran['file']} " + " ".join(vectors)]
        return "\n".join(lines)


FAULT_SHORT_OHM = 0.01      # a short of a generated fault scenario
PD_SHUNT_OHM = 0.1          # the dynamic resistance of a PD sink's VDD shunt in the model: within 3 mV at 30 mA
PASS_GATE_KNEE_V = 0.1      # a pass gate turns on over this much below its reference
CHARGER_CV_OHM = 0.01       # how stiffly the charger model holds the float voltage – a model constant, no datasheet value
BOOST_ON_OHM = 1e-3         # a switch_boost's output source while enabled – a model constant, no datasheet value


def build(design, cfg, scenario, plugin_models=None, tran=None):
    """-> (netlist text, meta). With tran ({"step_s", "stop_s", "nets", "file"}): a transient run instead of the
    operating point."""
    split_boards(design)
    nl = Netlist(design, cfg, scenario, plugin_models)
    return nl.build(tran), nl.meta
