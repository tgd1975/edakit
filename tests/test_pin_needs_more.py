"""What a pin needs, the rest of it (docs/concepts/done/schema-gaps.md D1–D5): a capacitor between two pins of the part
(a charge pump), a crystal with its frequency window, a pin tied to another pin, no pull resistor, no series resistor, a
required capacitor's voltage rating, a capacitor window judged on the local decoupling (layout.near); and a
bidirectional pin that must not float (float_ok = false). Each with the circuit that lacks it and the one that has it –
values for the tests, not from a datasheet."""

import copy

from edakit.design import Design
from edakit.engines.levels import open_inputs, undefined_inputs
from edakit.engines.requires import pin_needs

PINS = {"1": {"name": "VDD", "type": "power_in"}, "2": {"name": "GND", "type": "ground"},
        "3": {"name": "VCP", "type": "passive"}, "4": {"name": "VM", "type": "power_in"},
        "5": {"name": "XI", "type": "input"}, "6": {"name": "XO", "type": "output"},
        "7": {"name": "CSB", "type": "input"}, "8": {"name": "RST", "type": "input", "pull": "up"},
        "9": {"name": "DP", "type": "bidirectional"}, "10": {"name": "SDO", "type": "bidirectional"}}


def part(needs=None, **pins):
    p = {"lcsc": "C1000", "mpn": "TEST-IC", "kind": "ic", "pins": copy.deepcopy(PINS), "values": {}}
    for num, need in (needs or {}).items():
        p["pins"][num]["needs"] = need
    for num, fields in pins.items():
        p["pins"][num.lstrip("p")].update(fields)
    return p


def cap(key, f, v=None):
    e = {"lcsc": key, "mpn": f"cap {f}", "kind": "capacitor", "pins": {"1": {"name": "1", "type": "passive"},
                                                                         "2": {"name": "2", "type": "passive"}},
         "values": {"value_f": f}}
    if v is not None:
        e["limits"] = {"v_max_v": v}
    return e


def res(key, ohm):
    return {"lcsc": key, "mpn": f"res {ohm}", "kind": "resistor",
            "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
            "values": {"value_ohm": ohm}}


def xtal(key, hz):
    return {"lcsc": key, "mpn": f"xtal {hz}", "kind": "crystal",
            "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
            "values": {"f_hz": hz}}


def design(ic, extra=(), nets=None, layout=None):
    """U1 (the test IC) on its own nets: VDD on 3V3, GND, VM on VM, every other pin on a net of its name; extra parts
    [(designator, entry, (net a, net b))]."""
    base = {"1": "3V3", "2": "GND", "3": "VCP", "4": "VM", "5": "XI", "6": "XO", "7": "CSB", "8": "RST", "9": "DP",
            "10": "SDO"}
    base.update(nets or {})
    parts, comps = {"C1000": ic}, [{"designator": "U1", "type": "ic", "lcsc": "C1000", "board": "main",
                                     "pins": {n: p["name"] for n, p in ic["pins"].items()}}]
    net_pins = {}
    for num, net in base.items():
        net_pins.setdefault(net, []).append(f"U1.{num}")
    for des, entry, (a, b) in extra:
        parts[entry["lcsc"]] = entry
        comps.append({"designator": des, "type": entry["kind"], "lcsc": entry["lcsc"], "board": "main",
                      "pins": {"1": "1", "2": "2"}})
        net_pins.setdefault(a, []).append(f"{des}.1")
        net_pins.setdefault(b, []).append(f"{des}.2")
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps,
             "nets": [{"name": n, "pins": p, "v": [0, 5]} for n, p in net_pins.items()]}
    if layout:
        graph["layout"] = layout
    return Design.from_data(graph, parts)


def texts(d, code=None):
    return [f.text for f in pin_needs(d) if code is None or f.code == code]


# --- D1: a capacitor between two pins -----------------------------------------------------------------------------
def test_a_capacitor_between_two_pins_of_the_part():
    ic = part({"3": [{"what": "capacitor", "to": "VM", "c_min_f": 10e-9, "c_max_f": 22e-9}]})
    assert texts(design(ic, [("C1", cap("C1", 10e-9), ("VCP", "VM"))])) == []
    assert texts(design(ic, [("C1", cap("C1", 10e-9), ("VCP", "GND"))]), "REQ.missing") == [
        "U1.3 (VCP): needs a capacitor of 10 nF … 22 nF to U1.4 (VM) (VM) – VCP has none"]
    assert texts(design(ic, [("C1", cap("C1", 1e-9), ("VCP", "VM"))]), "REQ.value") == [
        "U1.3 (VCP): needs a capacitor of 10 nF … 22 nF to U1.4 (VM) (VM) – C1 on VCP: 1 nF"]


def test_to_names_a_pin_by_number_or_name_and_nothing_else():
    ic = part({"3": [{"what": "capacitor", "to": "4", "c_min_f": 10e-9}]})
    assert texts(design(ic, [("C1", cap("C1", 10e-9), ("VCP", "VM"))])) == []
    ic = part({"3": [{"what": "capacitor", "to": "VBOOT"}]})
    assert [f.text for f in pin_needs(design(ic)) if f.code == "PARTS.schema"] == [
        "C1000: pin 3 needs capacitor: to 'VBOOT' names no pin of the part"]


# --- D2: a crystal ------------------------------------------------------------------------------------------------
def test_a_crystal_between_two_pins_in_its_window():
    need = [{"what": "crystal", "to": "XO", "f_min_hz": 11.98e6, "f_max_hz": 12.02e6}]
    ic = part({"5": need})
    assert texts(design(ic, [("Y1", xtal("Y1", 12e6), ("XI", "XO"))])) == []
    assert texts(design(ic, [("Y1", xtal("Y1", 8e6), ("XI", "XO"))]), "REQ.value") == [
        "U1.5 (XI): needs a crystal of 11.98 MHz … 12.02 MHz to U1.6 (XO) – Y1: 8 MHz"]
    assert texts(design(ic), "REQ.missing") == [
        "U1.5 (XI): needs a crystal of 11.98 MHz … 12.02 MHz to U1.6 (XO) (XO) – none between XI and it"]


def test_a_crystal_need_names_its_other_pin():
    ic = part({"5": [{"what": "crystal", "f_min_hz": 12e6}]})
    assert [f.text for f in pin_needs(design(ic)) if f.code == "PARTS.schema"] == [
        "C1000: pin 5 needs crystal: to – the other pin of the part – is missing"]


# --- D3: tie, no pull, no series resistor --------------------------------------------------------------------------
def test_a_pin_tied_to_another_pin():
    ic = part({"7": [{"what": "tie", "to": "VDD"}]})
    assert texts(design(ic, nets={"7": "3V3"})) == []
    assert texts(design(ic, [("R1", res("R1", 10e3), ("CSB", "3V3"))]), "REQ.missing") == [
        "U1.7 (CSB): must be tied to U1.1 (VDD) (3V3), is on CSB"]


def test_no_external_pull_resistor():
    ic = part({"8": [{"what": "no_pull", "dir": "up"}]})
    assert texts(design(ic)) == []
    assert texts(design(ic, [("R1", res("R1", 10e3), ("RST", "3V3"))]), "REQ.forbidden") == [
        "U1.8 (RST): must have no external pull-up resistor – R1 on RST"]
    assert texts(design(ic, [("R1", res("R1", 10e3), ("RST", "GND"))])) == []       # dir up: a pull-down is allowed
    ic = part({"8": [{"what": "no_pull"}]})
    assert texts(design(ic, [("R1", res("R1", 10e3), ("RST", "GND"))]), "REQ.forbidden") == [
        "U1.8 (RST): must have no external pull resistor – R1 on RST"]


def test_no_series_resistor():
    ic = part({"9": [{"what": "no_series"}]})
    assert texts(design(ic)) == []
    assert texts(design(ic, [("R1", res("R1", 22), ("DP", "USB_DP"))]), "REQ.forbidden") == [
        "U1.9 (DP): must have no series resistor – R1 on DP"]


# --- D4: a required capacitor's voltage rating ---------------------------------------------------------------------
def test_a_required_capacitor_rated_too_low():
    ic = part({"3": [{"what": "capacitor", "c_min_f": 10e-9, "v_min_v": 50}]})
    assert texts(design(ic, [("C1", cap("C1", 10e-9, v=50), ("VCP", "GND"))])) == []
    assert texts(design(ic, [("C1", cap("C1", 10e-9, v=16), ("VCP", "GND"))]), "REQ.value") == [
        "U1.3 (VCP): needs a capacitor rated at least 50 V to GND – C1 16 V"]
    assert texts(design(ic, [("C1", cap("C1", 10e-9), ("VCP", "GND"))])) == []       # rating unknown: not judged


# --- D5: the local decoupling -------------------------------------------------------------------------------------
def test_a_capacitor_window_judged_on_the_capacitors_next_to_the_part():
    ic = part({"1": [{"what": "capacitor", "c_min_f": 0.1e-6, "c_max_f": 1e-6}]})
    caps = [("C1", cap("C1", 0.1e-6), ("3V3", "GND")), ("C2", cap("C2", 10e-6), ("3V3", "GND"))]
    assert texts(design(ic, caps), "REQ.value") == [
        "U1.1 (VDD): needs a capacitor of 100 nF … 1 µF to GND – C1, C2 on 3V3: 10.1 µF"]   # the net's sum
    assert texts(design(ic, caps, layout={"near": {"C1": "U1"}})) == []                     # C1 next to U1
    assert texts(design(ic, caps, layout={"near": {"C2": "U1"}}), "REQ.value") == [
        "U1.1 (VDD): needs a capacitor of 100 nF … 1 µF to GND next to the part (layout.near) – C2 on 3V3: 10 µF"]


# --- float_ok = false on a bidirectional pin ------------------------------------------------------------------------
def test_a_bidirectional_pin_that_must_not_float():
    def sdo(findings):
        return [f.text for f in findings if f.place.startswith(("SDO", "U1.10"))]
    ic = part(p10={"float_ok": False})
    assert sdo(undefined_inputs(design(ic))) == ["SDO: input without driver or pull resistor"]
    assert sdo(undefined_inputs(design(ic, [("R1", res("R1", 10e3), ("SDO", "GND"))]))) == []
    assert sdo(undefined_inputs(design(part()))) == []              # without float_ok = false: the pin may float
    d = design(ic)
    d.comps["U1"]["nc"] = ["10"]
    assert sdo(open_inputs(d)) == ["U1.10 (SDO): an input left open (nc) – it floats"]
