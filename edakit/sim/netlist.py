"""Graph + parts database -> ngspice netlist for one operating point (.op) of one scenario, or for one transient run
(.tran) whose sources follow piecewise-linear curves ([t, V] points, PWL).

Passive parts, diodes, LEDs, transistors and MOSFETs come from the graph 1:1, their values and SPICE models from the
parts database; a 0 Ω bridge (value_ohm 0) is its maximum resistance r_max_ohm, 50 mΩ without one. An RGB LED is
three LEDs with the values and limits of their colour, common cathode (roles anode_<color>, cathode) or common anode
(anode, cathode_<color>) as its roles say. An LED whose parts entry lacks one of these roles is left out of the
netlist and listed in meta["leds_left_out"] (SIM.driver); one with a pin in nc is an unused LED and simply left out.
Switches, buttons and DIP switches are closed or open as the scenario's load says; a relay is its coil resistance
(coil_ohm between the roles coil_plus and coil_minus) plus a contact from common to no when the load lists it in
"relays_on", else to nc. Supplies are connectors listed under "sources" in the simulation config, or battery holders
with a cell state – one voltage source per cell, listed in meta["cells"] (LIM.backfeed: no charge current). Off-board loads
(a servo, a motor at a connector) are constant currents between two pins, listed under the load's "external".

ICs and modules are replaced by behaviour models, chosen by values.behavior in the parts database:

  ldo       roles vin, vout (gnd optional): vout = min(vout_v, vin - dropout_v); input current = output + iq_a
  buck      roles vin, vout: ideal output vout_v; input power = output power / efficiency (B-source)
  boost     same as buck; checks vin_min_v from the limits
            Every regulator (the mcu's on-board one too) whose limits give vin_min_v (mcu: vin_min_v|vsys_min_v) locks out
            below it: output and input current fall to 0 over the UVLO_V below vin_min – a DC result above it is the
            same, a transient run sees the regulator switch off
  mcu       roles vin|vsys|vdd (supply), optional vout|3v3 (on-board regulator: values regulator = "buck"|"ldo",
            output vout_v, default v_io), the core's current i_core_a – an upper bound; i_core_min_a, the least
            current, only in the operating point of the minimum load (scenario "least_current", run.least_current) –,
            gpio pins: outputs from the load's "gpio" levels as source + gpio_r_out_ohm,
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
  logic     icc_a at the supply pin, outputs low through 50 ohm
  current   constant i_a at the supply pin
  none      nothing (e.g. a module that is not powered in this design)

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

from ..circuit import limits, values, wire_h, wire_ohm

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


def split_boards(design):
    """Nets that run through a cable get their own node on the cable's source side ('<net>__<board>') with the wire
    resistance in between. Done once per design."""
    if getattr(design, "cable_elements", None) is not None:
        return
    design.cable_elements = []
    board = {d: c.get("board") for d, c in design.comps.items()}
    for cable in design.graph.get("cables", []):
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
        name = part["spice"]["model"].split()[1]
        self.models[name] = part["spice"]["model"]
        return name

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
        """Supply at a connector: voltage source behind a source resistance (cable, power supply)."""
        plus = self.pn(f"{des}.{spec['plus']}")
        minus = self.pn(f"{des}.{spec['minus']}")
        x = f"x_{des.lower()}_src"
        self.add(f"V_{des}_SRC {x} {minus} {pwl(value)}")
        r = spec.get("r_ohm", 0.1)
        self.add(f"R_{des}_SRC {x} {plus} {r}", des, "source", (x, plus), r)
        self.meta["sources"][des] = {"branch": f"v_{des}_src#branch".lower(), "i_max_a": spec.get("i_max_a"),
                                     "i_min_a": spec.get("i_min_a"), "nodes": [plus, minus]}

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
        elif kind == "capacitor":
            self.two_pole(des, "C", p["value_f"], "capacitor")
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
        elif kind in ("pmos", "nmos"):
            dr, g, s = (self.rn(des, x) for x in ("drain", "gate", "source"))
            self.add(f"M_{des} {dr} {g} {s} {s} {self.model(des, part)}", des, kind, (dr, g, s))
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
        elif kind == "relay":
            a, b = self.rn(des, "coil_plus"), self.rn(des, "coil_minus")
            if a and b and a != b:
                self.add(f"R_{des}_COIL {a} {b} {p['coil_ohm']}", des, "relay_coil", (a, b), p["coil_ohm"])
            on = des in self.load.get("relays_on", [])
            c, t = self.rn(des, "common"), self.rn(des, "no" if on else "nc")
            if c and t and c != t:
                self.add(f"R_{des}_K {c} {t} {p.get('r_contact_ohm', 0.05)}", des, "switch", (c, t),
                         p.get("r_contact_ohm", 0.05))
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
        elif kind in ("ic", "module"):
            behavior = p.get("behavior", "none")
            fn = self.plugin_models.get(behavior) or getattr(self, f"ic_{behavior}", None)
            if fn is None:
                raise ValueError(f"{des}: unknown behaviour model '{behavior}' (built in: ldo, buck, boost, mcu, cc_sink,"
                                 " opamp, logic, current, none; or a plugin model)")
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

    def ic_ldo(self, des, part):
        self._regulator(des, self.rn(des, "vin", True), self.rn(des, "vout", True), self._gnd_of(des), "ldo",
                        values(part), vin_min=limits(part).get("vin_min_v"))
        self.meta["regs"][des]["limits"] = limits(part)

    def ic_buck(self, des, part, kind="buck"):
        self._regulator(des, self.rn(des, "vin", True), self.rn(des, "vout", True), self._gnd_of(des), kind,
                        values(part), vin_min=limits(part).get("vin_min_v"))
        self.meta["regs"][des]["limits"] = limits(part)

    def ic_boost(self, des, part):
        self.ic_buck(des, part, "boost")

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
        for num, info in part["pins"].items():
            net = self.d.pin_net.get(f"{des}.{num}")
            if not net:
                continue
            if info["type"] == "power_in":
                self.current_load(f"{des}_{num}", self.pn(f"{des}.{num}"), "0", values(part).get("icc_a", 0.001))
            elif info["type"] == "output":
                self.add(f"R_{des}_{num} {self.pn(f'{des}.{num}')} 0 50")

    def ic_current(self, des, part):
        for num, info in part["pins"].items():
            net = self.d.pin_net.get(f"{des}.{num}")
            if net and info["type"] == "power_in":
                self.current_load(f"{des}_{num}", self.pn(f"{des}.{num}"), "0", self.amps(des, values(part).get("i_a", 0.001)))

    def ic_none(self, des, part):
        pass

    # --- build ----------------------------------------------------------------------------------------------------
    def build(self, tran=None):
        for des in sorted(self.d.comps):
            self.component(des)
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
        body = "\n".join(self.lines)
        models = "\n".join(self.models.values())
        control = "op\n" + "\n".join(prints) if tran is None else self.tran_control(tran)
        return (f"edakit {self.sc['name']}\n{body}\n{models}\n"
                f".options gmin=1e-12 reltol=1e-4 itl1=500 rshunt=1e12\n.control\n{control}\n.endc\n.end\n")

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


def build(design, cfg, scenario, plugin_models=None, tran=None):
    """-> (netlist text, meta). With tran ({"step_s", "stop_s", "nets", "file"}): a transient run instead of the
    operating point."""
    split_boards(design)
    nl = Netlist(design, cfg, scenario, plugin_models)
    return nl.build(tran), nl.meta
