"""Bus parameters (maker-coverage FT-16): what the firmware and the checks know about the SPI and I2C buses of a board.

Per device on a bus its SPI modes and its highest clock from its parts entry (values spi_modes, limits f_sck_max_hz,
f_scl_max_hz), the clock a net runs at (net clock_hz, set by the project as pwm_hz is), and the speed an I2C bus's
pull-ups allow with its capacitance – NXP UM10204 Rev. 7.0, 7.1: the rise time tr = 0.8473 · Rp · Cb within each mode's
tr(max), and Cb within its Cb(max) (catalog tables/i2c.toml). Cb is what is known of it: the pins' own input
capacitance as their datasheets give it (pin c_in_f) and a cable's c_pf_per_m × length_m. Tracks are not counted, and
a pin without c_in_f is named, not guessed – so the real bus is slower still than the speed found here.

The firmware contract carries all of it (firmware.py, `devices`, `bus_speed`); LIMITS holds a net's clock_hz to every
device on it and to the pull-ups (LIM.range/clock, limits.py).
"""

from __future__ import annotations

from .catalog import table
from .circuit import i2c_name, is_number, limits, resistors_to, si, supply_nets, values
from .design import natural_key

DEVICE_KINDS = ("ic", "module")
I2C = table("i2c")
RISE = I2C["rise"]["factor"]                       # tr = 0.8473 · Rp · Cb (UM10204 7.1)
MODES = sorted(I2C["modes"], key=lambda m: m["f_scl_hz"])
SOURCE = f"{I2C['rise']['source']}; {MODES[0]['source'].split(', table')[0]}, table 11"


def master(d, des):
    """The bus's controller: a part with the behaviour mcu or a component typed microcontroller."""
    return values(d.part(des)).get("behavior") == "mcu" or (d.comps.get(des) or {}).get("type") == "microcontroller"


def devices_on(d, net):
    """The devices with a pin on a net: parts of kind ic or module that are not the controller, sorted."""
    out = set()
    for ref in (d.nets.get(net) or {}).get("pins", []):
        des = ref.partition(".")[0]
        if (d.part(des) or {}).get("kind") in DEVICE_KINDS and not master(d, des):
            out.add(des)
    return sorted(out, key=natural_key)


def i2c_role(info):
    """'sda' or 'scl' from a pin's role, or from its name where it has no role."""
    if info.get("role"):
        return info["role"] if info["role"] in ("sda", "scl") else None
    return i2c_name(info.get("name", ""))


def scl_nets(d):
    """The I2C clock lines: nets with fn i2c.scl, a pin whose role (or name) is SCL, or the name SCL."""
    return sorted(name for name, net in d.nets.items()
                  if net.get("fn") == "i2c.scl" or i2c_name(name) == "scl"
                  or any(i2c_role(d.pin_info(r)) == "scl" for r in net["pins"]))


def sck_nets(d):
    """The SPI clock lines: nets with fn spi.sck."""
    return sorted(name for name, net in d.nets.items() if net.get("fn") == "spi.sck")


def sda_of(d, scl):
    """The data line that belongs to an I2C clock line: the SDA net of the first device on it (by role or name), else
    the net with fn i2c.sda of the same fn_bus; None without one."""
    for des in devices_on(d, scl):
        for num, info in ((d.part(des) or {}).get("pins") or {}).items():
            if i2c_role(info) == "sda" and (net := d.pin_net.get(f"{des}.{num}")):
                return net
    bus = d.nets[scl].get("fn_bus")
    return next((n for n, net in sorted(d.nets.items()) if net.get("fn") == "i2c.sda" and net.get("fn_bus") == bus),
                None)


def spi_devices(d, sck):
    """[{part, modes, f_max_hz}] of the devices on an SPI clock line: the modes its entry gives (values spi_modes),
    its highest SCK (limits f_sck_max_hz) – null where the entry gives none."""
    return [{"part": des, "modes": values(d.part(des)).get("spi_modes"),
             "f_max_hz": limits(d.part(des)).get("f_sck_max_hz")} for des in devices_on(d, sck)]


def i2c_devices(d, scl):
    """[{part, f_max_hz}] of the devices on an I2C clock line: its highest SCL (limits f_scl_max_hz) or null."""
    return [{"part": des, "f_max_hz": limits(d.part(des)).get("f_scl_max_hz")} for des in devices_on(d, scl)]


def capacitance(d, net):
    """(Cb in F, [what it holds], [IC and module pins without c_in_f]) of a net: the c_in_f of its pins and the cables
    that carry it (c_pf_per_m × length_m). Resistors, capacitors and connectors add nothing known."""
    total, held, unknown = 0.0, [], []
    for ref in sorted((d.nets.get(net) or {}).get("pins", []), key=natural_key):
        des = ref.partition(".")[0]
        if (d.part(des) or {}).get("kind") not in DEVICE_KINDS:
            continue
        c = d.pin_info(ref).get("c_in_f")
        if is_number(c):
            total += c
            held.append(f"{ref} {si(c, 'F')}")
        else:
            unknown.append(ref)
    for cable in d.graph.get("cables") or []:
        wires = [a for a, b in (cable.get("pins") or {}).items()
                 if net in (d.pin_net.get(f"{cable.get('from')}.{a}"), d.pin_net.get(f"{cable.get('to')}.{b}"))]
        if not wires:
            continue
        name = cable.get("name") or f"{cable.get('from')}–{cable.get('to')}"
        if is_number(cable.get("c_pf_per_m")) and is_number(cable.get("length_m")):
            c = cable["c_pf_per_m"] * 1e-12 * cable["length_m"]
            total += c
            held.append(f"cable {name} {cable['length_m']:g} m × {cable['c_pf_per_m']:g} pF/m")
        else:
            unknown.append(f"cable {name} (no c_pf_per_m)")
    return total, held, unknown


def pull_up(d, net):
    """The pull-up resistance of a line: the resistors to a supply and the pins' own pulls in parallel; None where
    there is none or one has no value."""
    rs = [r for _, r, _ in resistors_to(d, net, supply_nets(d))]
    rs += [d.pin_info(ref).get("pull_ohm") for ref in d.nets[net]["pins"] if d.pin_info(ref).get("pull") == "up"]
    if not rs or not all(is_number(r) and r > 0 for r in rs):
        return None
    return 1 / sum(1 / r for r in rs)


def line_speed(d, net):
    """The speed one I2C line's pull-up allows: {line, pull_up_ohm, c_bus_f, c_bus, rise_ns, mode, f_max_hz} – the
    fastest mode of UM10204 whose tr(max) and Cb(max) the line keeps; f_max_hz null (and why) where the pull-up or
    every capacitance is unknown, or where it keeps none."""
    cb, held, unknown = capacitance(d, net)
    rp = pull_up(d, net)
    said = ", ".join(held) or "nothing known"
    c_text = f"{said}{'; not known: ' + ', '.join(unknown) if unknown else ''}; tracks not counted"
    row = {"line": net, "pull_up_ohm": rp, "c_bus_f": cb or None, "c_bus": c_text, "rise_ns": None, "mode": None,
           "f_max_hz": None}
    if rp is None:
        return row | {"why": "no pull-up of known value on the line"}
    if not held:
        return row | {"why": "no capacitance known (no c_in_f on its pins, no cable with c_pf_per_m)"}
    tr = RISE * rp * cb
    row["rise_ns"] = round(tr * 1e9, 1)
    fits = [m for m in MODES if tr <= m["tr_max_s"] and cb <= m["cb_max_f"]]
    if not fits:
        return row | {"why": f"tr {tr * 1e9:.0f} ns above Standard-mode's {MODES[0]['tr_max_s'] * 1e9:.0f} ns"}
    return row | {"mode": fits[-1]["name"], "f_max_hz": float(fits[-1]["f_scl_hz"])}


def i2c_speed(d, scl, sda=None):
    """The speed the pull-ups of an I2C bus allow: the slower of its two lines (line_speed), with both lines."""
    lines = [line_speed(d, n) for n in (scl, sda) if n]
    known = [x for x in lines if x["f_max_hz"] is not None]
    if len(known) < len(lines):
        return next(x for x in lines if x["f_max_hz"] is None)
    return min(known, key=lambda x: (x["f_max_hz"], -(x["rise_ns"] or 0)))


def slowest(rows):
    """(f_max_hz, part) of the device with the lowest highest clock, (None, None) where none gives one."""
    known = [(r["f_max_hz"], r["part"]) for r in rows if is_number(r["f_max_hz"])]
    return min(known) if known else (None, None)


def common_modes(rows):
    """The SPI modes every device that gives its modes runs in – sorted; None where no device gives them."""
    given = [set(r["modes"]) for r in rows if isinstance(r["modes"], list)]
    return sorted(set.intersection(*given)) if given else None
