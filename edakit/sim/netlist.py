"""Graph + parts database -> ngspice netlist for one operating point (.op) of one scenario.

Passive parts, diodes, LEDs, transistors and MOSFETs come from the graph 1:1, their values and SPICE models from the
parts database. Switches, buttons and DIP switches are closed or open as the scenario's load says. Supplies are
connectors listed under "sources" in the simulation config, or battery holders with a cell state. Off-board loads
(a servo, a motor at a connector) are constant currents between two pins, listed under the load's "external".

ICs and modules are replaced by behaviour models, chosen by params.behavior in the parts database:

  ldo       roles vin, vout (gnd optional): vout = min(vout_v, vin - dropout_v); input current = output + iq_a
  buck      roles vin, vout: ideal output vout_v; input power = output power / efficiency (B-source)
  boost     same as buck; checks vin_min from the ratings
  mcu       roles vin|vsys|vdd (supply), optional vout|3v3 (on-board regulator: params regulator = "buck"|"ldo",
            output vout_v, default v_io), gpio pins: outputs from the load's "gpio" levels as source + gpio_r_out_ohm,
            high level v_io in V or "vin" (follows the supply pin, e.g. a 5 V AVR), pull-ups from the config; the
            config's "inputs" are checked for a defined logic level (params vih_v|vih_ratio, vil_v|vil_ratio)
  cc_sink   constant-current LED driver (TLC5916, STP08CP05 …): roles rext, out, vdd, oe_n; R-EXT held at vrext_v,
            each enabled output sinks iout_gain x I(R-EXT) with a soft knee
  logic     icc_a at the supply pin, outputs low through 50 ohm
  current   constant i_a at the supply pin
  none      nothing (e.g. a module that is not powered in this design)

A project adds its own models in a plugin file (edakit.toml [sim] plugin = "hardware/sim_plugin.py") that defines
MODELS = {"name": function(netlist, des, part)}. See handbook/05-simulation.md.
"""

from __future__ import annotations

import math
import re

VT = 0.02585
LED_N = 2.0


def node(net, ground="GND"):
    if net is None:
        return None
    return "0" if net == ground else "n_" + re.sub(r"\W", "_", net.lower())


def led_model(name, vf, i_test, rs):
    vd = vf - i_test * rs
    i_s = i_test / (math.exp(vd / (LED_N * VT)) - 1)
    return f".model {name} D(IS={i_s:.4e} N={LED_N} RS={rs} BV=5 IBV=10u CJO=20p)"


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
                                          "r": cable.get("r_ohm_per_wire", 0.05)})


def local_ground(design, net):
    """Ground of the board the net is on: its voltage range 'v' refers to it."""
    split_boards(design)
    gnd = design.ground
    boards = {design.comps[ref.split(".", 1)[0]].get("board") for ref in design.nets[net]["pins"]}
    alt = f"{gnd}__{next(iter(boards))}"
    return alt if len(boards) == 1 and any(el["a"] == alt for el in design.cable_elements) else gnd


class Netlist:
    def __init__(self, design, cfg, scenario, plugin_models=None):
        self.d, self.cfg, self.sc = design, cfg, scenario
        self.load = scenario["load"]
        self.lines, self.models = [], {}
        self.meta = {"leds": {}, "cc": {}, "regs": {}, "mcu": {}, "sources": {}, "elements": {}}
        self.plugin_models = plugin_models or {}

    # --- helpers --------------------------------------------------------------------------------------------------
    def n(self, net):
        return node(net, self.d.ground)

    def pin_nodes(self, des):
        return {num: self.n(self.d.pin_net.get(f"{des}.{num}")) for num in self.d.part(des)["pins"]}

    def roles(self, des):
        return self.d.pins_by_role(des)

    def add(self, line, des=None, kind=None, nodes=(), value=None):
        self.lines.append(line)
        if des:
            name = line.split()[0].lower()
            el = {"name": name, "kind": kind, "nodes": list(nodes)}
            if value is not None:
                el["value"] = value
            self.meta["elements"].setdefault(des, []).append(el)

    def gpio_level(self, net, default=0):
        return self.load.get("gpio", {}).get(net, default)

    def model(self, des, part):
        name = part["spice"]["model"].split()[1]
        self.models[name] = part["spice"]["model"]
        return name

    # --- passive and discrete -------------------------------------------------------------------------------------
    def two_pole(self, des, prefix, value, kind, pins=("1", "2")):
        a, b = (self.n(self.d.pin_net.get(f"{des}.{p}")) for p in pins)
        if a is None or b is None or a == b:
            return
        self.add(f"{prefix}_{des} {a} {b} {value:.6g}", des, kind, (a, b), value)

    def led(self, des, part, color=None, anode_role="anode"):
        params = part["params"][color] if color else part["params"]
        corner = self.sc["corner"]
        vf = params[{"min": "vf_min", "max": "vf_max"}.get(corner, "vf_typ")]
        model = f"LED_{part.get('lcsc', des)}_{color or 'x'}_{corner}"
        self.models[model] = led_model(model, vf, params["vf_at_a"], params.get("rs_ohm", 10))
        roles = self.roles(des)
        a, k = self.n(roles.get(anode_role)), self.n(roles.get("cathode"))
        if a is None or k is None:
            return
        name = f"D_{des}" + (f"_{color}" if color else "")
        self.add(f"{name} {a} {k} {model}", des, "led", (a, k))
        self.meta["leds"][name.lower()] = {"des": des, "color": color, "anode_net": roles.get(anode_role),
                                           "cathode_net": roles.get("cathode")}

    def source(self, des, spec, value):
        """Supply at a connector: voltage source behind a source resistance (cable, power supply)."""
        plus = self.n(self.d.pin_net.get(f"{des}.{spec['plus']}"))
        minus = self.n(self.d.pin_net.get(f"{des}.{spec['minus']}"))
        x = f"x_{des.lower()}_src"
        self.add(f"V_{des}_SRC {x} {minus} DC {value}")
        r = spec.get("r_ohm", 0.1)
        self.add(f"R_{des}_SRC {x} {plus} {r}", des, "source", (x, plus), r)
        self.meta["sources"][des] = {"branch": f"v_{des}_src#branch".lower(), "i_max_a": spec.get("i_max_a"),
                                     "nodes": [plus, minus]}

    def external(self, des, spec):
        """Off-board load at a connector: constant current from pin 'plus' to pin 'minus'."""
        plus = self.n(self.d.pin_net.get(f"{des}.{spec['plus']}"))
        minus = self.n(self.d.pin_net.get(f"{des}.{spec['minus']}"))
        if plus is None or minus is None:
            raise ValueError(f"{des}: external load between unconnected pins {spec['plus']} and {spec['minus']}")
        self.add(f"I_{des}_EXT {plus} {minus} DC {spec['i_a']}", des, "load", (plus, minus))
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
        kind, p = part["kind"], part.get("params", {})
        if kind == "resistor":
            self.two_pole(des, "R", p["value_ohm"], "resistor")
        elif kind == "capacitor":
            self.two_pole(des, "C", p["value_f"], "capacitor")
        elif kind == "fuse":
            self.two_pole(des, "R", p.get("r_max_ohm", 0.1), "fuse")
        elif kind == "inductor":
            a, b = (self.n(self.d.pin_net.get(f"{des}.{x}")) for x in ("1", "2"))
            self.add(f"L_{des} {a} x_{des.lower()} {p['value_h']:.6g}")
            self.add(f"R_{des} x_{des.lower()} {b} {p.get('dcr_ohm', 0.05)}", des, "inductor",
                     (f"x_{des.lower()}", b), p.get("dcr_ohm", 0.05))
        elif kind == "diode":
            roles = self.roles(des)
            a, k = self.n(roles.get("anode")), self.n(roles.get("cathode"))
            if a and k:
                self.add(f"D_{des} {a} {k} {self.model(des, part)}", des, "diode", (a, k))
        elif kind in ("npn", "pnp"):
            roles = self.roles(des)
            c, b, e = (self.n(roles.get(x)) for x in ("collector", "base", "emitter"))
            self.add(f"Q_{des} {c} {b} {e} {self.model(des, part)}", des, kind, (c, b, e))
        elif kind in ("pmos", "nmos"):
            roles = self.roles(des)
            dr, g, s = (self.n(roles.get(x)) for x in ("drain", "gate", "source"))
            self.add(f"M_{des} {dr} {g} {s} {s} {self.model(des, part)}", des, kind, (dr, g, s))
        elif kind == "led":
            self.led(des, part)
        elif kind == "led_rgb":
            for color in ("red", "green", "blue"):
                self.led(des, part, color, f"anode_{color}")
        elif kind == "battery_holder":
            cell_name = supply.get(des)
            if cell_name is None:
                return
            cell = self.cfg["cells"][cell_name]
            roles = self.roles(des)
            count = p.get("cells", 1)
            for s in [""] if count == 1 else [f"_{chr(ord('a') + i)}" for i in range(count)]:
                name = des + s
                plus, minus = self.n(roles["plus" + s]), self.n(roles["minus" + s])
                self.add(f"V_{name} x_{name.lower()} {minus} DC {cell['v']}")
                self.add(f"R_{name} x_{name.lower()} {plus} {cell['r']}", des, "battery",
                         (f"x_{name.lower()}", plus), cell["r"])
        elif kind == "buzzer":
            roles = self.roles(des)
            self.add(f"R_{des} {self.n(roles['plus'])} {self.n(roles['minus'])} {p['coil_ohm']}", des, "buzzer",
                     (self.n(roles["plus"]), self.n(roles["minus"])), p["coil_ohm"])
        elif kind == "switch":
            if des in self.load.get("open", []):
                return
            roles = self.roles(des)
            a = self.n(roles.get("common"))
            b = self.n(roles.get(self.load.get("throw", {}).get(des, "throw_a"))) or self.n(roles.get("throw_b"))
            if a and b:
                self.add(f"R_{des} {a} {b} {p.get('r_on_ohm', 0.05)}", des, "switch", (a, b), p.get("r_on_ohm", 0.05))
        elif kind == "dip_switch":
            closed = self.load.get("dip_closed", {}).get(des, []) if isinstance(self.load.get("dip_closed"), dict) \
                else self.load.get("dip_closed", [])
            roles = self.roles(des)
            for i in range(1, p.get("positions", 8) + 1):
                if closed == "all" or i in closed:
                    a, b = self.n(roles.get(f"a{i}")), self.n(roles.get(f"b{i}"))
                    if a and b:
                        self.add(f"R_{des}_{i} {a} {b} {p.get('r_on_ohm', 0.1)}", des, "switch", (a, b),
                                 p.get("r_on_ohm", 0.1))
        elif kind == "button":
            if des in self.load.get("buttons", []):
                roles = self.roles(des)
                a, b = self.n(roles.get("a")), self.n(roles.get("b"))
                if a and b:
                    self.add(f"R_{des} {a} {b} {p.get('r_on_ohm', 0.1)}", des, "switch", (a, b), p.get("r_on_ohm", 0.1))
        elif kind == "potentiometer":
            roles = self.roles(des)
            pos = self.load.get("pot", {}).get(des, 0.5) if isinstance(self.load.get("pot"), dict) else 0.5
            ra, rb = max(p["value_ohm"] * pos, 1), max(p["value_ohm"] * (1 - pos), 1)
            w = self.n(roles["wiper"])
            self.add(f"R_{des}_a {self.n(roles['end_a'])} {w} {ra:.6g}", des, "pot", (self.n(roles["end_a"]), w), ra)
            self.add(f"R_{des}_b {w} {self.n(roles['end_b'])} {rb:.6g}", des, "pot", (w, self.n(roles["end_b"])), rb)
        elif kind in ("ic", "module"):
            behavior = p.get("behavior", "none")
            fn = self.plugin_models.get(behavior) or getattr(self, f"ic_{behavior}", None)
            if fn is None:
                raise ValueError(f"{des}: unknown behaviour model '{behavior}' (built in: ldo, buck, boost, mcu, cc_sink,"
                                 " logic, current, none; or a plugin model)")
            fn(self, des, part) if behavior in self.plugin_models else fn(des, part)

    # --- behaviour models -----------------------------------------------------------------------------------------
    def _gnd_of(self, roles):
        return self.n(roles.get("gnd")) or "0"

    def _regulator(self, des, vin, vout, gnd, kind, p, extra_i=0.0):
        """Output source at vout with an ammeter; input current from vin by kind ('ldo' or 'buck'/'boost')."""
        tag = des.lower()
        vset = p.get("vout_v", 3.3)
        self.add(f"V_{des}_AM x_{tag}_o {vout} 0")
        if kind == "ldo":
            self.add(f"B_{des}_O x_{tag}_o {gnd} V = min({vset}, max(V({vin},{gnd})-{p.get('dropout_v', 0.3)}, 0))")
            self.add(f"B_{des}_I {vin} {gnd} I = max(i(V_{des}_AM),0) + {p.get('iq_a', 0.0) + extra_i}")
        else:
            eta = p.get("efficiency", 0.85)
            self.add(f"B_{des}_O x_{tag}_o {gnd} V = {vset}")
            self.add(f"B_{des}_I {vin} {gnd} I = {vset}*(max(i(V_{des}_AM),0)+{extra_i})/({eta}*max(V({vin},{gnd}),0.3))"
                     f" + {p.get('iq_a', 0.0)}")
        self.meta["regs"][des] = {"kind": kind, "vin": vin, "vout": vout, "gnd": gnd, "vset": vset,
                                  "ammeter": f"v_{tag}_am#branch", "params": p, "extra_i": extra_i}

    def ic_ldo(self, des, part):
        roles = self.roles(des)
        self._regulator(des, self.n(roles["vin"]), self.n(roles["vout"]), self._gnd_of(roles), "ldo", part["params"])
        self.meta["regs"][des]["ratings"] = part.get("ratings", {})

    def ic_buck(self, des, part, kind="buck"):
        roles = self.roles(des)
        self._regulator(des, self.n(roles["vin"]), self.n(roles["vout"]), self._gnd_of(roles), kind, part["params"])
        self.meta["regs"][des]["ratings"] = part.get("ratings", {})

    def ic_boost(self, des, part):
        self.ic_buck(des, part, "boost")

    def ic_mcu(self, des, part):
        p = part["params"]
        roles = self.roles(des)
        vin = self.n(roles.get("vsys") or roles.get("vin") or roles.get("vdd"))
        vout = self.n(roles.get("vout") or roles.get("3v3"))
        v_io = p.get("v_io", 3.3)  # a number, or "vin": the I/O runs from the supply pin (5 V AVR boards)
        mcfg = self.cfg.get("mcu", {}).get(des) or self.cfg.get("mcu", {})
        if vout and p.get("regulator"):
            vset = p.get("vout_v", v_io)
            if not isinstance(vset, (int, float)):
                raise ValueError(f"{des}: v_io = '{v_io}' – give the on-board regulator's output as params vout_v")
            self._regulator(des, vin, vout, "0", p["regulator"], {**p, "vout_v": vset}, extra_i=p.get("i_core_a", 0.03))
        elif vin:
            self.add(f"I_{des}_CORE {vin} 0 DC {p.get('i_core_a', 0.03)}")
        gpio = {self.d.pin_net.get(f"{des}.{n}") for n, i in part["pins"].items() if i.get("role") == "gpio"}
        for net in mcfg.get("outputs", []):
            if net in gpio:
                x = f"x_{des.lower()}_{net.lower()}"
                if self.gpio_level(net) and v_io == "vin":
                    self.add(f"B_{des}_{net} {x} 0 V = V({vin})")
                else:
                    self.add(f"V_{des}_{net} {x} 0 DC {v_io if self.gpio_level(net) else 0}")
                self.add(f"R_{des}_{net} {x} {self.n(net)} {p.get('gpio_r_out_ohm', 30)}")
        rail = self.n(mcfg["io_rail"]) if mcfg.get("io_rail") else (vin if v_io == "vin" else vout or vin)
        for net in mcfg.get("pullups", []):
            if net in gpio and rail:
                self.add(f"R_{des}_PU_{net} {rail} {self.n(net)} {mcfg.get('pullup_ohm', 50000)}")
        self.meta["mcu"][des] = {"vin": vin, "vout": vout, "params": p, "ratings": part.get("ratings", {}),
                                 "io_rail": rail if v_io == "vin" or mcfg.get("io_rail") else None,
                                 "inputs": [net for net in mcfg.get("inputs", []) if net in gpio]}

    def ic_cc_sink(self, des, part):
        p = part["params"]
        nets = {i.get("role"): self.d.pin_net.get(f"{des}.{n}") for n, i in part["pins"].items() if i.get("role")}
        vdd = self.n(nets.get("vdd"))
        if vdd:
            self.add(f"I_{des}_VDD {vdd} 0 DC {p.get('idd_max_a', 0.01)}")
        self.add(f"V_{des}_REXT {self.n(nets['rext'])} 0 DC {p['vrext_v']}")
        oe = nets.get("oe_n")
        enabled = oe is None or self.gpio_level(oe, default=1) == 0
        want = self.load.get("cc_on", {}).get(des, []) if isinstance(self.load.get("cc_on"), dict) else []
        chans = {}
        for num, info in part["pins"].items():
            if info.get("role") != "out":
                continue
            net = self.d.pin_net.get(f"{des}.{num}")
            if net is None:
                continue
            o = self.n(net)
            on = enabled and (want == "all" or net in want or info["name"] in want)
            if on:
                y = f"y_{des.lower()}_{num}"
                self.add(f"V_{des}_A{num} {o} {y} 0")
                self.add(f"B_{des}_O{num} {y} 0 I = {p['iout_gain']}*max(-i(V_{des}_REXT),0)"
                         f"*(1-exp(-max(V({y}),0)/0.15))")
            else:
                self.add(f"R_{des}_OFF{num} {o} 0 100Meg")
            chans[net] = {"on": on, "ammeter": f"v_{des.lower()}_a{num}#branch", "node": o}
        self.meta["cc"][des] = {"rext_src": f"v_{des.lower()}_rext#branch", "vdd": vdd, "channels": chans,
                                "params": p, "ratings": part.get("ratings", {})}

    def ic_logic(self, des, part):
        for num, info in part["pins"].items():
            net = self.d.pin_net.get(f"{des}.{num}")
            if not net:
                continue
            if info["type"] == "power_in":
                self.add(f"I_{des}_{num} {self.n(net)} 0 DC {part['params'].get('icc_a', 0.001)}")
            elif info["type"] == "output":
                self.add(f"R_{des}_{num} {self.n(net)} 0 50")

    def ic_current(self, des, part):
        for num, info in part["pins"].items():
            net = self.d.pin_net.get(f"{des}.{num}")
            if net and info["type"] == "power_in":
                self.add(f"I_{des}_{num} {self.n(net)} 0 DC {part['params'].get('i_a', 0.001)}")

    def ic_none(self, des, part):
        pass

    # --- build ----------------------------------------------------------------------------------------------------
    def build(self):
        for des in sorted(self.d.comps):
            self.component(des)
        for el in getattr(self.d, "cable_elements", []):
            a, b = self.n(el["a"]), self.n(el["b"])
            self.add(f"{el['name']} {a} {b} {el['r']}", el["des"], "connector", (a, b), el["r"])
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
        return (f"edakit {self.sc['name']}\n{body}\n{models}\n"
                ".options gmin=1e-12 reltol=1e-4 itl1=500\n.control\nop\n" + "\n".join(prints) + "\n.endc\n.end\n")


def build(design, cfg, scenario, plugin_models=None):
    split_boards(design)
    nl = Netlist(design, cfg, scenario, plugin_models)
    return nl.build(), nl.meta
