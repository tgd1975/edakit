"""The board's firmware contract: what firmware must know about the board, written from the graph and the parts
entries as neutral JSON – and its drift.

    edakit firmware            write the contract ([firmware] out, default hardware/firmware.json)
    edakit firmware --check    compare the committed contract with the graph; exit 2 on drift (pre-commit hook)

Opt-in: only with [firmware] in edakit.toml. Without it nothing changes – a project whose firmware is the reference
keeps checking the graph against the firmware with locks.pins (STRUCT.lock); both can stand side by side. Turning the
contract into firmware source (a MicroPython module, a C header) is the project's job: a script that reads the JSON.

What the contract holds (handbook 3.5):
    graph_version, graph_date, state_sha256   the circuit it was written from (state_sha256 = the gate's circuit hash)
    mcu        the MCU it describes ([firmware] mcu, default the one part with GPIO pins)
    pins       {net: {pin, name, gpio, dir, pull, idle, active[, leds, fn, fn_bus, pwm_hz]}} – every connected pin of
               the MCU with the role gpio; gpio is the first group of [firmware] gpio over the pin's name
    pwm        {net: pwm_hz or null} of the nets with fn "pwm" (graph, REQ.function)
    inputs     buttons and switches on MCU pins with their active level; DIP switches bit by bit in the order of their
               roles a1 … aN / b1 … bN
    buses      {fn_bus: {fn: net}} (graph, REQ.function), I2C lines by pin role sda/scl as "i2c"
    analog     {net: {pin, gpio, channel, divider, pull_up_ohm, pull_down_ohm}} – every MCU pin on a net with fn "adc":
               the converter channel (the pin's functions adc…, null without), the divider in front of it (the net one
               resistor from another net and one from ground: from, top_ohm, bottom_ohm, ratio), or a lone pull-up or
               pull-down (a thermistor's partner); values of the resistors' entries
    devices    {"i2c": [{bus, address, part, how}]} – every device on an I2C line of the MCU whose entry gives its address
               (REQ.forbidden/address), the address as its pins decide it, the bus named by its SDA net
    chains     from an MCU net through the roles sdi → sdo of shift registers and LED drivers: data net, parts in
               shift order, read-back net (the last sdo on an MCU pin), the MCU nets every part of it shares, and
               values.first_bit_to of its parts ("unknown" without it)
    channels   driver outputs (roles out0 … outN) → the LEDs they light, traced as SIM.state/SIM.driver trace them (directly, behind
               0 Ω bridges, behind a balancing resistor); channel = the outputs of the drivers before it in its chain
               + its output number

Only roles decide – a pin name never says which pin is the cathode, the data input or output 3. The one exception is
the GPIO number, which [firmware] gpio reads from the MCU pin's name.
Exit codes: 0 = written or current, 2 = drift (--check), 1 = error.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import circuit
from .design import natural_key
from .sim.netlist import led_roles, out_role
from .engines.sim import behind_resistor, led_on_output

SWITCH_KINDS = ("button", "switch", "dip_switch")
DRIVES_MCU = ("output", "power_output")          # pin types that drive a net the MCU reads


class ContractError(Exception):
    pass


def mcu_of(design, fw):
    want = fw.get("mcu")
    if want:
        if want not in design.comps:
            raise ContractError(f"[firmware] mcu: no part {want} in the graph")
        return want
    mcus = [d for d in design.comps if any(i.get("role") == "gpio" for i in (design.part(d) or {}).get("pins", {}).values())]
    if len(mcus) != 1:
        raise ContractError(f"[firmware] mcu: {'several parts' if mcus else 'no part'} with GPIO pins (role gpio)"
                            f"{' – ' + ', '.join(sorted(mcus, key=natural_key)) if mcus else ''}; name it")
    return mcus[0]


def far_side(design, des, role):
    """The roles that a switch closes `role` against: a ↔ b, ak ↔ bk, common ↔ throw_a/throw_b."""
    if role in ("a", "b"):
        return ["b" if role == "a" else "a"]
    m = re.fullmatch(r"([ab])(\d+)", role or "")
    if m:
        return [("b" if m[1] == "a" else "a") + m[2]]
    if role == "common":
        return ["throw_a", "throw_b"]
    return ["common"] if role in ("throw_a", "throw_b") else []


class Board:
    """The graph as firmware sees it: nets joined by 0 Ω bridges, rails, resistors."""

    def __init__(self, design, mcu):
        self.d, self.mcu = design, mcu
        self.j = design.joined()
        self.join = design.joined_nets()
        self.rails = circuit.supply_nets(self.j)
        self.res = circuit.resistor_like(self.j)

    def jn(self, net):
        return self.join.get(net, net)

    def level(self, net):
        """1 on a supply rail, 0 on ground, else None."""
        return 0 if net == self.j.ground else 1 if net in self.rails else None

    def others(self, net):
        return [r for r in self.j.nets[net]["pins"] if r.split(".", 1)[0] != self.mcu]

    def pulls_at(self, net, skip=()):
        return [(des, circuit.resistor_value(self.j, des), other) for des, a, b in self.res if des not in skip
                and net in (a, b) and self.level(other := b if a == net else a) is not None]

    def series(self, net):
        """(resistor, far net) of every resistor from `net` to a net that is no rail."""
        return [(des, b if a == net else a) for des, a, b in self.res if net in (a, b)
                and self.level(b if a == net else a) is None]

    def pull(self, net):
        """{dir, by, ohm} of the resistors that pull the net: on it, or behind one series resistor (a transistor's base
        resistor and its pull-down); None without one."""
        found, chain = self.pulls_at(net), []
        if not found:
            for des, far in self.series(net):
                behind = self.pulls_at(far, skip={des})
                if behind:
                    found, chain = behind, [des]
                    break
        if not found:
            return None
        dirs = {self.level(other) for _, _, other in found}
        if len(dirs) > 1:
            return {"dir": "divider", "by": sorted({d for d, _, _ in found}, key=natural_key)}
        vals = [v for _, v, _ in found]
        ohm = 1 / sum(1 / v for v in vals) if vals and all(vals) else None
        if ohm is not None and chain:
            ohm += circuit.resistor_value(self.j, chain[0]) or 0
        return {"dir": "up" if dirs.pop() else "down", "by": chain + sorted({d for d, _, _ in found}, key=natural_key),
                "ohm": round(ohm, 6) if ohm is not None else None}

    def switches(self, net):
        """(part, kind, role on the net, level of its far side) of every switch pin on the net."""
        out = []
        for ref in self.others(net):
            des = ref.split(".", 1)[0]
            part = self.j.part(des) or {}
            if part.get("kind") not in SWITCH_KINDS:
                continue
            role = self.j.pin_info(ref).get("role")
            levels = {self.level(n) for r in far_side(self.j, des, role) if (n := self.j.pins_by_role(des).get(r))}
            out.append((des, part["kind"], role, levels.pop() if len(levels) == 1 else None))
        return out


def gpio_leds(board, nets):
    """{net: [{des, color, side}]} – LEDs an MCU pin lights directly or through its series resistor."""
    behind = behind_resistor(board.d, board.join, set(nets))
    out = {}
    for des in sorted(board.d.comps, key=natural_key):
        part = board.d.part(des) or {}
        if part.get("kind") not in ("led", "led_rgb"):
            continue
        for color, a_role, k_role in led_roles(part):
            roles = board.d.pins_by_role(des)
            sides = {"anode": roles.get(a_role), "cathode": roles.get(k_role)}
            for side, net in sides.items():
                net = board.jn(net) if net else None
                at = net if net in nets else behind.get(net)
                if at:
                    color = color or circuit.values(part).get("color")
                    out.setdefault(at, []).append({"des": des, **({"color": color} if color else {}), "side": side})
                    break
    return out


def pin_entry(board, ref, net, regex, leds):
    """One MCU pin: direction, pull, idle and active level."""
    info = board.d.pin_info(ref)
    jnet = board.jn(net)
    m = re.search(regex, info.get("name", ""))
    e = {"pin": ref, "name": info.get("name"), "gpio": int(m.group(1)) if m and m.group(1).isdigit() else None}
    others = board.others(jnet)
    types = {board.j.pin_info(r).get("type") for r in others}
    sw = board.switches(jnet)
    loads = leds.get(jnet) or any(board.j.pin_info(r).get("type") == "input"
                                  or board.j.pin_info(r).get("role") in ("base", "gate")
                                  for _, far in board.series(jnet) for r in board.j.nets[far]["pins"])
    drives_in = bool(sw) or bool(types & set(DRIVES_MCU))
    driven = "input" in types or bool(loads)
    e["dir"] = ("inout" if drives_in and driven else "in" if drives_in else "out" if driven
                else "inout" if "bidirectional" in types else None)
    pull = board.pull(jnet)
    if pull is None:
        own = [board.j.pin_info(r).get("pull") for r in board.j.nets[jnet]["pins"]]
        if any(own):
            pull = {"dir": next(p for p in own if p), "by": "pin"}
        elif sw and len({lv for *_, lv in sw}) == 1 and sw[0][3] is not None:
            pull = {"dir": "up" if sw[0][3] == 0 else "down", "by": "internal"}   # the firmware switches it on
    e["pull"] = pull
    e["idle"] = {"up": 1, "down": 0}.get((pull or {}).get("dir"))
    if sw and len({lv for *_, lv in sw}) == 1:
        e["active"] = sw[0][3]
    elif leds.get(jnet):
        e["active"] = 1 if leds[jnet][0]["side"] == "anode" else 0
    else:
        e["active"] = None if e["idle"] is None or e["dir"] != "out" else 1 - e["idle"]
    if leds.get(jnet):
        e["leds"] = leds[jnet]
    for key in ("fn", "fn_bus", "pwm_hz"):
        if board.d.nets[net].get(key) is not None:
            e[key] = board.d.nets[net][key]
    return e


def inputs(board, pins):
    out, seen = [], set()
    by_jnet = {board.jn(n): n for n in pins}
    for jnet, net in by_jnet.items():
        for des, kind, role, level in board.switches(jnet):
            if des in seen:
                continue
            if kind != "dip_switch":
                seen.add(des)
                out.append({"part": des, "kind": kind, "net": net, "gpio": pins[net]["gpio"], "active": level})
                continue
            seen.add(des)
            bits, levels = [], set()
            part = board.j.part(des)
            for num, info in sorted(part["pins"].items(), key=lambda kv: natural_key(kv[1].get("role") or "")):
                m = re.fullmatch(r"([ab])(\d+)", info.get("role") or "")
                n = board.jn(board.j.pin_net.get(f"{des}.{num}")) if board.j.pin_net.get(f"{des}.{num}") else None
                if m and n in by_jnet:
                    far = board.j.pins_by_role(des).get(far_side(board.j, des, m[0])[0])
                    levels.add(board.level(far) if far else None)
                    bits.append({"switch": int(m[2]), "net": by_jnet[n], "gpio": pins[by_jnet[n]]["gpio"]})
            out.append({"part": des, "kind": kind, "active": levels.pop() if len(levels) == 1 else None,
                        "bits": sorted(bits, key=lambda b: b["switch"])})
    return sorted(out, key=lambda x: natural_key(x["part"]))


def role_pins(design, des, test):
    return {num: info["role"] for num, info in ((design.part(des) or {}).get("pins") or {}).items()
            if test(info.get("role")) and f"{des}.{num}" in design.pin_net}


def chains(board, pins):
    """Shift chains from an MCU net through sdi → sdo."""
    j = board.j
    sdi = {}
    for des in j.comps:
        for num in role_pins(j, des, lambda r: r == "sdi"):
            sdi.setdefault(j.pin_net[f"{des}.{num}"], []).append(des)
    mcu_nets = {board.jn(n): n for n in pins}
    out = []
    for jnet, net in sorted(mcu_nets.items(), key=lambda kv: natural_key(kv[1])):
        for first in sorted(sdi.get(jnet, []), key=natural_key):
            parts, cur = [], jnet
            nxt = first
            while nxt and nxt not in parts:
                parts.append(nxt)
                cur = j.pins_by_role(nxt).get("sdo")
                nxt = next((d for d in sorted(sdi.get(cur, []), key=natural_key) if d not in parts), None) if cur else None
            back = mcu_nets.get(cur) if cur and cur != jnet else None
            reach = [{mcu_nets[n] for num in j.part(d)["pins"] if (n := j.pin_net.get(f"{d}.{num}")) in mcu_nets}
                     for d in parts]
            common = set.intersection(*reach) - {net, back}
            facts = {d: circuit.values(j.part(d)).get("first_bit_to") or "unknown" for d in parts}
            first = next(iter(facts.values())) if len(set(facts.values())) == 1 else facts   # per part where they differ
            out.append({"data": net, "parts": parts, "read_back": back, "first_bit_to": first,
                        "common": sorted(common, key=natural_key)})
    return out


def channels(board, chain_list):
    """Driver output → LEDs, as SIM.state/SIM.driver trace them."""
    d = board.d
    drivers = [x for x in d.comps if role_pins(d, x, out_role)]
    chained = {p: (i, pos) for i, ch in enumerate(chain_list) for pos, p in enumerate(ch["parts"])}
    for des in drivers:
        roles = role_pins(d, des, out_role)
        if des in chained and any(r == "out" for r in roles.values()):
            raise ContractError(f"{des}: its outputs have the role out without a number – give them out0 … "
                                f"out{len(roles) - 1} in its parts entry {d.entry_key(des)} (handbook 4.1); the channel "
                                "order comes from the roles, never from pin names")
    outs = {}      # joined net -> (des, index, pin, net)
    for des in drivers:
        for num, role in role_pins(d, des, out_role).items():
            if role != "out":
                net = d.pin_net[f"{des}.{num}"]
                outs[board.jn(net)] = (des, int(role[3:]), f"{des}.{num}", net)
    behind = behind_resistor(d, board.join, set(outs))
    lit = {}
    for des in sorted(d.comps, key=natural_key):
        part = d.part(des) or {}
        if part.get("kind") not in ("led", "led_rgb"):
            continue
        for color, a_role, k_role in led_roles(part):
            a, k = (board.jn(n) if (n := d.pins_by_role(des).get(r)) else None for r in (a_role, k_role))
            hit = led_on_output(outs, behind, a, k)
            if hit:
                color = color or circuit.values(part).get("color")
                entry = {"des": des, **({"color": color} if color else {})}
                lit.setdefault(hit[0], {"leds": [], "reversed": []})["leds" if hit[1] == "cathode" else "reversed"] \
                    .append(entry)
    rows = []
    for jnet, (des, idx, pin, net) in outs.items():
        chain, pos = chained.get(des, (None, None))
        base = 0
        if chain is not None:
            for before in chain_list[chain]["parts"][:pos]:
                base += len(role_pins(d, before, out_role))
        row = {"channel": base + idx, "chain": chain, "driver": des, "output": idx, "pin": pin, "net": net,
               "leds": lit.get(jnet, {}).get("leds", [])}
        if lit.get(jnet, {}).get("reversed"):
            row["reversed"] = lit[jnet]["reversed"]
        rows.append(row)
    return sorted(rows, key=lambda r: (r["chain"] is None, r["chain"] or 0, r["channel"], natural_key(r["driver"])))


def analog(design, pins):
    """{net: …} of the MCU's analog inputs (fn adc): channel, divider or pull – from the resistors on the net."""
    out = {}
    for net, e in pins.items():
        if design.nets.get(net, {}).get("fn") != "adc":
            continue
        info = design.pin_info(e["pin"])
        channel = next((f for f in info.get("functions") or [] if str(f).lower().startswith("adc")), None)
        top, bottom = [], []
        for des in sorted(design.comps_of_kind("resistor"), key=natural_key):
            a, b = (design.pin_net.get(f"{des}.{p}") for p in ("1", "2"))
            if net not in (a, b) or a == b:
                continue
            other, ohm = (b if a == net else a), circuit.resistor_value(design, des)
            (bottom if other == design.ground else top).append((des, other, ohm))
        row = {"pin": e["pin"], "gpio": e["gpio"], "channel": channel, "divider": None, "pull_up_ohm": None,
               "pull_down_ohm": None}
        if len(top) == 1 and len(bottom) == 1 and top[0][2] and bottom[0][2]:
            rt, rb = top[0][2], bottom[0][2]
            row["divider"] = {"from": top[0][1], "top": top[0][0], "top_ohm": rt, "bottom": bottom[0][0],
                              "bottom_ohm": rb, "ratio": round(rb / (rt + rb), 6)}
        elif len(top) == 1 and not bottom:
            row["pull_up_ohm"] = top[0][2]
        elif len(bottom) == 1 and not top:
            row["pull_down_ohm"] = bottom[0][2]
        out[net] = row
    return out


def devices(design, buses):
    """{"i2c": [...]} – the devices with an address on the MCU's I2C lines (the SDA nets of buses)."""
    from .engines.requires import bus_devices
    sda = {nets.get("sda") for name, nets in buses.items() if name == "i2c" or name.startswith("i2c")} - {None}
    found, _ = bus_devices(design)
    rows = [{"bus": bus, "address": f"0x{x:02X}", "part": des, "how": how}
            for bus, devs in sorted(found.items()) if bus in sda for x, des, how in devs]
    return {"i2c": sorted(rows, key=lambda r: (r["bus"], r["address"], natural_key(r["part"])))} if rows else {}


def contract(cfg, design):
    from .release import gate
    fw = cfg.firmware or {}
    mcu = mcu_of(design, fw)
    board = Board(design, mcu)
    gpio = {num: info for num, info in (design.part(mcu) or {}).get("pins", {}).items() if info.get("role") == "gpio"}
    nets = {}
    for num in gpio:
        ref = f"{mcu}.{num}"
        if ref in design.pin_net:
            nets.setdefault(design.pin_net[ref], ref)
    leds = gpio_leds(board, {board.jn(n) for n in nets})
    pins = {net: pin_entry(board, ref, net, fw.get("gpio", r"(\d+)"), leds) for net, ref in nets.items()}
    pins = dict(sorted(pins.items(), key=lambda kv: (kv[1]["gpio"] is None, kv[1]["gpio"] or 0, natural_key(kv[0]))))
    buses = {}
    for net, e in pins.items():
        if e.get("fn_bus"):
            buses.setdefault(e["fn_bus"], {})[e.get("fn") or net] = net
        else:
            line = next((r for r in (board.j.pin_info(x).get("role") for x in board.j.nets[board.jn(net)]["pins"])
                         if r in ("sda", "scl")), None) or ((e.get("fn") or "").split(".")[1]
                                                            if (e.get("fn") or "").startswith("i2c.") else None)
            if line:
                buses.setdefault("i2c", {})[line] = net
    chain_list = chains(board, pins)
    return {
        "about": f"Firmware contract of {cfg.project}, written by edakit firmware from the graph and the parts entries "
                 "– do not edit: change the graph and run edakit firmware again (edakit handbook 3.5).",
        "graph_version": design.version, "graph_date": design.graph.get("date"),
        "state_sha256": gate.state_hash(cfg),
        "mcu": mcu,
        "pins": pins,
        "pwm": {n: e.get("pwm_hz") for n, e in pins.items() if e.get("fn") == "pwm"},
        "inputs": inputs(board, pins),
        "buses": buses,
        "analog": analog(design, pins),
        "devices": devices(design, buses),
        "chains": chain_list,
        "channels": channels(board, chain_list),
    }


def gaps(design, c):
    """What the contract cannot say, for the console: drivers whose outputs carry no number, pins without a GPIO
    number, LEDs reversed on a driver output."""
    out = []
    chained = {p for ch in c["chains"] for p in ch["parts"]}
    for des in sorted(design.comps, key=natural_key):
        plain = [n for n, r in role_pins(design, des, out_role).items() if r == "out"]
        if plain and des not in chained:
            out.append(f"{des}: {len(plain)} outputs with the role out without a number (out0 … outN) – not in the "
                       "channels")
    out += [f"{net}: no GPIO number in the pin name {e['name']} ([firmware] gpio)" for net, e in c["pins"].items()
            if e["gpio"] is None]
    out += [f"{ch['driver']} out{ch['output']} ({ch['net']}): reversed LED "
            f"{', '.join(x['des'] for x in ch['reversed'])} – edakit sim reports it too" for ch in c["channels"]
            if ch.get("reversed")]
    return out


def render(c):
    return json.dumps(c, indent=1, ensure_ascii=False) + "\n"


def differences(old, new, path="", limit=20):
    """Lines 'path: old → new' where two contracts differ."""
    out = []
    if isinstance(old, dict) and isinstance(new, dict):
        for k in list(old) + [k for k in new if k not in old]:
            out += differences(old.get(k), new.get(k), f"{path}.{k}" if path else k, limit)
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new) and old != new:
        for i, (a, b) in enumerate(zip(old, new)):
            out += differences(a, b, f"{path}[{i}]", limit)
    elif old != new:
        show = lambda x: json.dumps(x, ensure_ascii=False) if x is not None else "–"  # noqa: E731
        out.append(f"{path}: {show(old)} → {show(new)}")
    return out[:limit]


def main(cfg, args):
    from .design import Design
    if cfg.firmware is None:
        print("edakit firmware: no [firmware] table in edakit.toml – the contract is opt-in (handbook 3.5)",
              file=sys.stderr)
        return 1
    design = Design.from_config(cfg)
    try:
        c = contract(cfg, design)
    except ContractError as e:
        print(f"edakit firmware: {e}", file=sys.stderr)
        return 1
    out = cfg.resolve(cfg.firmware["out"])
    text = render(c)
    rel = cfg.relative(out)
    summary = (f"{len(c['pins'])} pins, {len(c['inputs'])} inputs, {len(c['chains'])} chains"
               + (f" ({'; '.join(' → '.join(ch['parts']) for ch in c['chains'])})" if c["chains"] else "")
               + f", {len(c['channels'])} channels")
    for line in gaps(design, c):
        print(f"  ! {line}")
    if getattr(args, "check", False):
        if not out.exists():
            print(f"{rel}: drift – not written yet (edakit firmware)")
            return 2
        old = out.read_text(encoding="utf-8")
        if old == text:
            print(f"{rel} is current: {summary}")
            return 0
        try:
            lines = differences(json.loads(old), c)
        except json.JSONDecodeError:
            lines = ["not valid JSON"]
        print(f"{rel}: drift – it no longer matches the graph (edakit firmware writes it again):")
        for line in lines or ["formatting only"]:
            print(f"  {line}")
        return 2
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{rel} written: {summary}")
    return 0
