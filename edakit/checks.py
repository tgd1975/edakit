"""Stages P (parts) and G (graph): rule checks on the hardware graph, offline, in well under a second.

    edakit check [--release] [--json FILE]

  G-1  structure: unique names, every pin in exactly one net or "nc", nets with >= 2 pins, a voltage range per net,
       a known board per component, nets across boards only through a cable
  G-2  pin locks: pins the firmware relies on are on the expected nets ([checks] pin_locks in edakit.toml), and an
       optional pin table in a Markdown document matches the graph ([checks] doc_pin_table)
  G-3  voltage domains: net voltage range within the pin limits (vmax) from the parts database
  G-4  no floating inputs; an input driven only by MCU pins needs a pull resistor; transistors need a base resistor
  G-5  at most one push-pull output or supply output per net
  G-6  decoupling: per net at least one capacitor to ground per IC supply pin (power_in)
  G-8  voltage ratings of capacitors, diodes, transistors, MOSFETs, fuses, switches, connectors with margin
  G-10 reverse polarity: what a reversed source (battery holders, [checks] reverse_protect) reaches through fuses,
       switches and connectors is only capacitors, the anode of a blocking diode or the drain of a PMOS
  P-1  graph pins (number + name) = parts database, an entry exists for every LCSC number
  G-9  sign-off: every part verified against its datasheet, no open "verify" notes (pending, blocks only the release)

A finding listed in "waive" of the net or component is accepted on purpose and reported with its reason.
Exit code 1 on errors; with --release also on pending sign-offs.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CAP_FACTOR = 1.5      # rated voltage >= 1.5 x max. voltage across
DIODE_FACTOR = 1.5    # VRRM >= 1.5 x max. reverse voltage
BJT_FACTOR = 1.5      # VCEO, VDS, VGS >= 1.5 x max.
ACTIVE_TYPES = {"input", "output", "bidirectional", "power_in", "power_output", "analog", "current_sink"}
BOOT_DRIVERS = {"output", "power_output", "ground"}   # define their net while the firmware is not running
PASS_THROUGH = ("fuse", "switch", "connector")        # pass a reversed source on unchanged
REVERSE_OK = ("battery_holder", "capacitor") + PASS_THROUGH

CHECK_TEXT = {
    "G-1": "Structure: unique names, every pin in exactly one net or nc, voltage range per net",
    "G-2": "Pin locks and pin table match the graph",
    "G-3": "Voltage range of every net within the pin limits",
    "G-4": "No floating input; inputs driven only by MCU pins have a pull resistor",
    "G-5": "At most one output per net",
    "G-6": "One capacitor to ground per IC supply pin",
    "G-8": "Voltage rating of capacitors, diodes, transistors, fuses, switches, connectors",
    "G-10": "Reverse polarity: a reversed source reaches only capacitors and blocking devices",
    "P-1": "Graph pins = parts database, an entry for every part",
    "G-9": "Parts verified against the datasheet, no open 'verify' notes",
}
EXECUTED = list(CHECK_TEXT)


class Report:
    def __init__(self):
        self.errors, self.pending, self.waived = [], [], []

    def error(self, check, msg, waive=None):
        if waive and check in waive:
            self.waived.append((check, msg, waive[check]))
        else:
            self.errors.append((check, msg))

    def to_dict(self):
        return {"errors": [{"check": c, "msg": m} for c, m in self.errors],
                "pending": [{"check": c, "msg": m} for c, m in self.pending],
                "waived": [{"check": c, "msg": m, "reason": r} for c, m, r in self.waived]}


def v_range(net):
    v = net.get("v")
    return v if isinstance(v, list) and len(v) == 2 and v[0] <= v[1] else [0, 0]


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


def check_pin_locks(d, rep, cfg_checks, root):
    for ref, net in (cfg_checks.get("pin_locks") or {}).items():
        if d.pin_net.get(ref) != net:
            rep.error("G-2", f"{ref} expected on net {net}, found {d.pin_net.get(ref)}")
    table = cfg_checks.get("doc_pin_table")
    if not table:
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


def check_part_pins(d, rep):
    for des, c in d.comps.items():
        if not c.get("lcsc"):
            continue
        part = d.part(des)
        if not part:
            rep.error("P-1", f"{des}: no parts entry {c['lcsc']}.json")
            continue
        want = {k: v["name"] for k, v in part["pins"].items()}
        if c["pins"] != want:
            only_g = {k: v for k, v in c["pins"].items() if want.get(k) != v}
            only_p = {k: v for k, v in want.items() if c["pins"].get(k) != v}
            rep.error("P-1", f"{des}: pins differ from parts entry {c['lcsc']}: graph {only_g} vs parts {only_p}")
        for pin in c.get("nc", []):
            if part["pins"].get(str(pin), {}).get("type") == "power_in":
                rep.error("P-1", f"{des}.{pin} ({part['pins'][str(pin)]['name']}) is a supply pin but marked nc",
                          c.get("waive"))


def check_signoff(d, rep):
    for lcsc in sorted({c["lcsc"] for c in d.comps.values() if c.get("lcsc")}):
        part = d.parts.get(lcsc)
        if part and not part.get("verified"):
            users = [des for des, c in d.comps.items() if c.get("lcsc") == lcsc]
            rep.pending.append(("G-9", f"{lcsc} {part.get('mpn', '')} ({', '.join(users)}) not verified against "
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
    checks = cfg.checks if cfg else {}
    check_structure(design, rep, set(cfg.boards) if cfg else set())
    check_pin_locks(design, rep, checks, cfg.root if cfg else ".")
    check_domains(design, rep)
    check_inputs(design, rep)
    check_contention(design, rep)
    check_decoupling(design, rep)
    check_ratings(design, rep)
    check_reverse(design, rep, checks.get("reverse_protect", []))
    check_part_pins(design, rep)
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
    print(f"{len(d.comps)} components, {len(d.nets)} nets, {len(d.parts)} parts entries; "
          f"{len(rep.errors)} errors, {len(rep.waived)} waived, {len(rep.pending)} open sign-offs")
    if args.json:
        Path(args.json).write_text(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if rep.errors or (args.release and rep.pending) else 0
