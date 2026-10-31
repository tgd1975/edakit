"""Quantities and limits – two of the five things the engines work on (concept rules-at-scale.md, section 1).

A quantity is a value at a place: the voltage across C1, at pin U1.3, through J1 – with the stage it comes from (G:
the graph's declared ranges, E: the simulation) and how it arose. A limit bounds a quantity of the same name at the
same place: a parts entry's limits ({name}_max_{unit}, {name}_min_{unit}), a pin's, a default of the pin's type, or
one the project sets (sim.json, a net's declared range). The producers here yield the quantities of stage G; the
simulation's are in sim.py. LIMITS (limits.py) joins the two.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..catalog import table
from ..circuit import ACTIVE_TYPES, hold_current, limits, polarized, series_nets, v_range, values

UNITS = {"V": "v", "A": "a", "W": "w", "°C": "c", "dBm": "dbm"}
FACTOR = table("derating")["G"]["factor"]          # stage G: value × factor ≤ limit
SIM_EPS_V = 1e-6                 # stage E: a voltage within 1 µV of its limit is at it – ngspice leaves 1e-18 V of noise
NEGATIVE_SUPPLY_ROLES = {"vee", "v_minus", "vneg"}   # a negative rail's supply pin: held to its own range, not to
                                                     # the floor of an active signal pin
PIN_MIN_V = table("derating")["pin"]["v_min_v"]     # an active pin below this conducts through its protection


@dataclass
class Limit:
    max: float | None = None
    min: float | None = None
    source: str = ""
    factor: float = 1.0       # the value is multiplied by it (stage G derating)
    derate: float = 1.0       # the limit is multiplied by it (stage E derating)
    eps: float = 0.0


@dataclass
class Quantity:
    place: str                # "C1", a pin "U1.3", "cable W1"
    name: str                 # "v", "vr", "vce", "vds", "vgs", "i", "eirp"
    hi: float | None
    unit: str = "V"
    stage: str = "G"
    lo: float | None = None
    how: str = ""             # how it arose: "across +12V (0…12 V) and GND"
    kind: str = ""            # the part's kind – the derating table's row
    entry: str | None = None  # the parts entry whose limits bound it
    pin: str = ""             # the pin number, when the pin's limits bound it
    pin_type: str = ""
    scenario: str = ""
    code: str = ""            # LIM.v, LIM.i … – by default from the unit
    grade: str = ""
    on: tuple = ()
    limits: list = field(default_factory=list)   # limits that come with the quantity (the project's)
    say: object = None        # (value, limit, factor) -> the finding's text where it says more than the default
    color: str = ""           # one colour of an RGB LED: its limits are the entry's limits.<color>
    derate: float = 1.0       # stage E: the derating of the entry's limit (derating.toml, sim.json)


def part_limits(design, q):
    """The limits a parts entry or a pin declares on a quantity, and the defaults of the pin's type."""
    out = []
    suffix = UNITS.get(q.unit, "")
    part = design.parts.get(q.entry) if q.entry else None
    if part is None:
        return out
    if q.pin:
        info = (part.get("pins") or {}).get(q.pin) or {}
        table_, where = info, f"pin {q.pin} ({info.get('name', q.pin)}) of {q.entry}"
    elif q.color and isinstance(limits(part).get(q.color), dict):
        table_, where = limits(part)[q.color], f"{q.entry} ({q.color})"
    else:
        table_, where = limits(part), q.entry
    hi, lo = table_.get(f"{q.name}_max_{suffix}"), table_.get(f"{q.name}_min_{suffix}")
    factor = FACTOR.get(q.kind, 1.0) if q.stage == "G" and not q.pin else 1.0
    eps = SIM_EPS_V if q.stage == "E" and q.unit == "V" else 0.0     # ngspice's noise against a limit of 0 V
    if isinstance(hi, (int, float)):
        out.append(Limit(max=hi, factor=factor, derate=q.derate, eps=eps, source=f"{q.name}_max_{suffix} of {where}"))
    if isinstance(lo, (int, float)):
        out.append(Limit(min=lo, eps=eps, source=f"{q.name}_min_{suffix} of {where}"))
    negative_supply = q.pin and q.pin_type == "power_in" and table_.get("role") in NEGATIVE_SUPPLY_ROLES
    if q.pin and q.name == "v" and q.pin_type in ACTIVE_TYPES and not negative_supply:
        out.append(Limit(min=PIN_MIN_V, eps=eps, source="an active pin: derating.toml [pin] v_min_v"))
    return out


# --- producers of stage G: the declared ranges -----------------------------------------------------------------------
def own_ground(d, des):
    """The net of a part's first connected ground pin, where it is not the board's ground (a cell protection IC on the
    cell's minus); None otherwise."""
    part = d.part(des) or {}
    net = next((d.pin_net[f"{des}.{n}"] for n, i in (part.get("pins") or {}).items()
                if i.get("type") == "ground" and f"{des}.{n}" in d.pin_net), None)
    return net if net is not None and net != d.ground and net in d.nets else None


def pin_voltages(d):
    """The voltage at every pin: the declared range of its net – against the part's own ground pin where that is not
    the board's ground (schema-gaps I1): the pin's range less the ground net's, extreme by extreme, since both move
    with that ground (a declared range cannot say which states coincide; stage E judges the operating points)."""
    out = []
    for name, net in d.nets.items():
        lo, hi = v_range(net)
        for ref in net["pins"]:
            des, _, num = ref.partition(".")
            info = d.pin_info(ref)
            pin = f"{ref} ({info.get('name', num)})"
            g = own_ground(d, des) if des in d.comps else None
            plo, phi, how = lo, hi, f"{name} {lo:g}…{hi:g} V at {pin}"
            if g is not None:
                if g == name:
                    continue                 # the ground pin itself: 0 V against itself
                glo, ghi = v_range(d.nets[g])
                plo, phi = lo - glo, hi - ghi
                how += f", against {g} ({glo:g}…{ghi:g} V), the part's own ground"
            out.append(Quantity(ref, "v", phi, lo=plo, entry=d.entry_key(des) if des in d.comps else None, pin=num,
                                pin_type=info.get("type", ""), how=how, on=(("net", name),),
                                say=lambda v, lim, f, name=name, pin=pin, g=g: (
                                    (f"{name} up to {v:g} V" + (f" against {g}" if g else "") + f", but {pin} allows "
                                     f"{lim:g} V") if v > 0 or lim > 0
                                    else f"{name} down to {v:g} V" + (f" against {g}" if g else "") + f" at {pin}")))
    return out


# kind -> [(quantity name, how to read it)]: the voltages a part's declared nets put on it
ACROSS = {"capacitor": [("v", "across")], "diode": [("vr", "reverse")], "npn": [("vce", "collector-emitter")],
          "pnp": [("vce", "collector-emitter")], "nmos": [("vds", "drain-source"), ("vgs", "gate-source")],
          "pmos": [("vds", "drain-source"), ("vgs", "gate-source")]}
PASSIVE = ("fuse", "switch", "dip_switch", "button", "potentiometer", "resistor", "buzzer", "connector")
TERMINALS = {"collector-emitter": ("collector", "emitter"), "drain-source": ("drain", "source"),
             "gate-source": ("gate", "source")}


def coupling(d, *nets):
    """A capacitor in a signal path – a side on a net marked signal or instrument: both sides carry the same AC, what
    it sees is the DC between them, which stage E judges on the operating points; the extremes of the two declared
    ranges never coincide (schema-gaps I7)."""
    return any((d.nets.get(n) or {}).get(k) for n in nets for k in ("signal", "instrument"))


def part_voltages(d):
    """The voltages every part sees from the declared ranges of its nets: across a capacitor, reverse across a diode –
    a TVS (values tvs) against its working voltage without the derating factor –, VCE, VDS and VGS, and on a passive
    part the highest voltage of any of its nets."""
    out = []

    def rng(net):
        return v_range(d.nets[net]) if net else [0, 0]

    def across(a, b):
        (alo, ahi), (blo, bhi) = rng(a), rng(b)
        return max(abs(ahi - blo), abs(bhi - alo))
    for des in d.comps:
        part = d.part(des)
        if not part:
            continue
        kind, key, on = part["kind"], d.entry_key(des), (("component", des),)
        nets = [d.pin_net.get(f"{des}.{p}") for p in part["pins"]]
        for name, what in ACROSS.get(kind, []):
            if what == "across":
                v, how = across(*nets[:2]), f"{des}: across its pins"
                say = (lambda v, lim, f, des=des: f"{des}: up to {v:.1f} V, rated {lim:g} V (needs ×{f:g})")
            elif what == "reverse":
                a, k = d.net_of(des, "anode"), d.net_of(des, "cathode")
                v, how = rng(k)[1] - rng(a)[0], f"{des}: reverse from {k} to {a}"
                if values(part).get("tvs"):    # a TVS: vr_max_v is its working voltage VRWM, no margin on top
                    out.append(Quantity(des, name, v, kind="tvs", entry=key, how=how, on=on,
                                        say=lambda v, lim, f, des=des: f"{des}: reverse up to {v:.1f} V, working "
                                                                       f"voltage VRWM {lim:g} V"))
                    continue
                say = (lambda v, lim, f, des=des: f"{des}: reverse up to {v:.1f} V, VRRM {lim:g} V")
            else:
                x, y = TERMINALS[what]
                v, how = across(d.net_of(des, x), d.net_of(des, y)), f"{des}: |{name.upper()}|"
                label = "VCE" if name == "vce" else name.upper()
                say = (lambda v, lim, f, des=des, label=label: f"{des}: |{label}| up to {v:.1f} V, "
                       + (f"VCEO {lim:g} V" if label == "VCE" else f"rated {lim:g} V"))
            out.append(Quantity(des, name, v, kind=kind, entry=key, how=how, on=on, say=say))
        if kind == "esd_array":           # the rail (or, without one, every protected line) against VRWM, no margin
            rail = d.net_of(des, "vbus")
            lines = [rail] if rail else [d.net_of(des, r) for r in {p.get("role") for p in part["pins"].values()}
                                         if str(r or "").startswith("io")]
            for net in [n for n in lines if n]:
                out.append(Quantity(des, "vrwm", max(abs(x) for x in rng(net)), kind="tvs", entry=key,
                                    on=on + (("net", net),),
                                    how=f"{des}: {net}",
                                    say=lambda v, lim, f, des=des, net=net: f"{des}: {net} up to {v:.2f} V, stand-off "
                                                                            f"voltage VRWM {lim:g} V"))
        if (polarized(part) and (plus := d.net_of(des, "plus")) and (minus := d.net_of(des, "minus"))
                and not coupling(d, plus, minus)):
            out.append(Quantity(des, "vr", rng(minus)[1] - rng(plus)[0], kind=kind, entry=key, grade="polarized",
                                how=f"{des}: reverse from {minus} to {plus}", on=on,
                                say=lambda v, lim, f, des=des: f"{des}: reverse up to {v:.1f} V, allowed {lim:g} V"))
        if kind in PASSIVE:
            v = max((abs(x) for n in nets if n for x in rng(n)), default=0)
            out.append(Quantity(des, "v", v, kind=kind, entry=key, how=f"{des}: its nets up to", on=on,
                                say=lambda v, lim, f, des=des: f"{des}: nets up to {v:.1f} V, rated {lim:g} V"))
    return out


def fuse_currents(d, sim=None):
    """What a fuse lets pass – its hold current at the lowest ambient, and its trip current (grade margin) – through
    every connector, switch and cable on its nets."""
    t_min = (sim or {}).get("ambient_min_c")
    out = []
    for fuse in d.comps_of_kind("fuse"):
        part = d.part(fuse)
        r = limits(part)
        if "i_hold_a" not in r:
            continue
        hold, trip = hold_current(part, t_min), r.get("i_trip_a")
        at = f" at {t_min:g} °C" if t_min is not None and (part.get("values") or {}).get("i_hold_vs_temp") else ""
        nets, on = series_nets(d, fuse), (("component", fuse),)
        rated = [(des, d.entry_key(des), []) for des in d.comps_of_kind("connector", "switch")
                 if "i_max_a" in limits(d.part(des)) and any(d.pin_net.get(f"{des}.{n}") in nets
                                                            for n in d.part(des)["pins"])]
        rated += [(f"cable {c['name']}", None, [Limit(max=c["i_max_a"], source=f"i_max_a of cable {c['name']}")])
                  for c in d.graph.get("cables", [])
                  if "i_max_a" in c and any(d.pin_net.get(f"{c['from']}.{a}") in nets for a in c["pins"])]
        for place, key, lims in rated:
            out.append(Quantity(place, "i", hold, unit="A", entry=key, limits=lims, on=on,
                                how=f"{fuse} holds {hold:.3g} A{at}",
                                say=lambda v, lim, f, fuse=fuse, at=at, place=place: (
                                    f"{fuse}: holds {v:.3g} A{at}, above the {lim:g} A of {place} – an overload in "
                                    "between never trips it")))
            if trip is not None:
                out.append(Quantity(place, "i", trip, unit="A", entry=key, limits=lims, on=on, grade="margin",
                                    how=f"{fuse} trips at {trip:g} A",
                                    say=lambda v, lim, f, fuse=fuse, place=place: (
                                        f"{fuse}: trips at {v:g} A, above the {lim:g} A of {place} – an overload in "
                                        "between may last for minutes")))
    return out
