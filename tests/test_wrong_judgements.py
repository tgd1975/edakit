"""Where edakit judged a correct circuit wrongly (docs/concepts/new/schema-gaps.md, A1–A5, A7, I1, I7) – each with the
circuit that was judged wrong and the one where the finding is right and stays."""

import copy
import json
import shutil

import pytest

from edakit import library
from edakit.design import Design
from edakit.engines import levels, quantities, requires


def comp(des, key, entry, nc=(), type_="ic"):
    return {"designator": des, "type": type_, "lcsc": key, "board": "main",
            "pins": {n: p["name"] for n, p in entry["pins"].items()}, "nc": [n for n in entry["pins"] if n in nc]}


def design(parts, comps, nets):
    graph = {"name": "t", "version": "1", "ground": "GND", "components": comps, "nets": nets}
    return Design.from_data(graph, parts)


def lib(key):
    return copy.deepcopy(library.entry(key))


# --- A1: PWM through the ESP32's GPIO matrix ----------------------------------------------------------------------------
def esp32_with(fn, pin_name, matrix=True):
    e = lib("C701341")
    if not matrix:
        e.pop("matrix")
    num = next(n for n, p in e["pins"].items() if p["name"] == pin_name)
    return design({"C701341": e}, [comp("U1", "C701341", e, type_="microcontroller")],
                  [{"name": "SIG", "pins": [f"U1.{num}"], "v": [0, 3.3], "fn": fn}])


def req_function(d):
    return [f.text for f in requires.functions(d) if f.code == "REQ.function"]


def test_pwm_through_the_gpio_matrix_is_on_any_gpio_that_drives():
    assert "pwm" in library.entry("C701341")["matrix"]
    assert req_function(esp32_with("pwm", "IO32")) == []
    assert len(req_function(esp32_with("pwm", "IO32", matrix=False))) == 1      # before: no PWM listed on the pin
    assert len(req_function(esp32_with("pwm", "IO34"))) == 1                    # an input-only GPIO cannot drive it
    assert req_function(esp32_with("uart.rx", "IO34")) == []                    # an input line it can take


def test_a_matrix_lifts_the_one_instance_per_bus_rule():
    e = lib("C701341")
    pins = {p["name"]: n for n, p in e["pins"].items()}
    nets = [{"name": "TX", "pins": [f"U1.{pins['IO32']}"], "v": [0, 3.3], "fn": "uart.tx", "fn_bus": "dbg"},
            {"name": "RX", "pins": [f"U1.{pins['IO33']}"], "v": [0, 3.3], "fn": "uart.rx", "fn_bus": "dbg"}]
    for n in e["pins"].values():                     # pins with fixed functions of different instances only
        if n["name"] == "IO32":
            n["functions"] = ["uart1.tx"]
        if n["name"] == "IO33":
            n["functions"] = ["uart2.rx"]
    d = design({"C701341": e}, [comp("U1", "C701341", e, type_="microcontroller")], nets)
    assert req_function(d) == []
    e.pop("matrix")
    assert any("bus dbg" in t for t in req_function(design({"C701341": e}, [comp("U1", "C701341", e,
                                                                                  type_="microcontroller")], nets)))


# --- A5: a peripheral's functions do not hide the MCU's ---------------------------------------------------------------
def mcu_and_peripheral(mcu_functions):
    mcu = {"kind": "ic", "values": {"behavior": "mcu"}, "pins": {"1": {"name": "GP0", "type": "bidirectional",
                                                                       "functions": mcu_functions}}}
    amp = {"kind": "ic", "values": {}, "pins": {"1": {"name": "DIN", "type": "input", "functions": ["i2s0.sd"]}}}
    return design({"M": mcu, "A": amp}, [comp("U1", "M", mcu, type_="microcontroller"), comp("U2", "A", amp)],
                  [{"name": "SD", "pins": ["U1.1", "U2.1"], "v": [0, 3.3], "fn": "i2s.sd"}])


def test_a_peripherals_pin_functions_do_not_answer_for_the_mcu():
    assert len(req_function(mcu_and_peripheral(["uart0.tx"]))) == 1             # before: the amplifier's i2s0.sd hid it
    assert req_function(mcu_and_peripheral(["i2s0.sd"])) == []


# --- A2: a bridge output defines its net ------------------------------------------------------------------------------
def motor_on(key, out_pins):
    import reference
    driver, motor = lib(key), dict(reference.MOTOR)
    d = design({key: driver, motor["lcsc"]: motor},
               [comp("U9", key, driver, nc=[n for n in driver["pins"] if n not in out_pins]),
                comp("M9", motor["lcsc"], motor, type_="motor")],
               [{"name": "MA", "pins": [f"U9.{out_pins[0]}", "M9.1"], "v": [0, 10]},
                {"name": "MB", "pins": [f"U9.{out_pins[1]}", "M9.2"], "v": [0, 10]}])
    return d, driver


def open_drain(d):
    return sorted(f.place for f in levels.released_nets(d))


def test_a_motor_on_bridge_outputs_does_not_float():
    d, driver = motor_on("C50506", ("2", "4"))            # DRV8833 AOUT1, AOUT2
    assert driver["pins"]["2"]["drive"] == "bridge"
    assert open_drain(d) == []
    for n in ("2", "4"):                                  # before: tristate – the motor nets were said to float
        d.parts["C50506"]["pins"][n]["drive"] = "tristate"
    assert open_drain(d) == ["MA", "MB"]


def test_an_open_drain_line_without_pull_up_still_floats():
    driver = lib("C50506")
    d = design({"C50506": driver}, [comp("U9", "C50506", driver, nc=[n for n in driver["pins"] if n != "8"])],
               [{"name": "FAULT", "pins": ["U9.8"], "v": [0, 3.3]}])
    assert open_drain(d) == ["FAULT"]                     # nFault: open drain, no pull-up


# --- A3: an input the part biases itself ------------------------------------------------------------------------------
def amp_input(biased=True):
    amp, cap = lib("C17337"), lib("C2895284")
    if not biased:
        for n in ("7", "10"):
            amp["pins"][n].pop("biased")
    return design({"C17337": amp, "C2895284": cap},
                  [comp("U9", "C17337", amp, nc=[n for n in amp["pins"] if n != "7"]),
                   comp("C9", "C2895284", cap, type_="capacitor")],
                  [{"name": "INL", "pins": ["U9.7", "C9.2"], "v": [0, 5]},
                   {"name": "SRC", "pins": ["C9.1"], "v": [-1, 1]}])


def test_an_input_biased_inside_the_part_has_its_dc_level():
    assert library.entry("C17337")["pins"]["7"]["biased"] is True
    assert [f.place for f in levels.analog_nodes(amp_input())] == []
    assert [f.place for f in levels.analog_nodes(amp_input(biased=False))] == ["INL"]


# --- A4: address pins with four states --------------------------------------------------------------------------------
def two_inas(a0_first, a0_second):
    """Two INA219 on one bus; each A0 tied to the net named (SDA, SCL, VS or GND), A1 to GND."""
    e = lib("C87469")
    nets = {"SDA": ["U1.6", "U2.6"], "SCL": ["U1.5", "U2.5"], "GND": ["U1.3", "U2.3", "U1.8", "U2.8"],
            "VS": ["U1.4", "U2.4"]}
    nets[a0_first].append("U1.7")
    nets[a0_second].append("U2.7")
    rng = {"SDA": [0, 3.3], "SCL": [0, 3.3], "GND": [0, 0], "VS": [3.3, 3.3]}
    return design({"C87469": e}, [comp(u, "C87469", e, nc=["1", "2"]) for u in ("U1", "U2")],
                  [{"name": n, "pins": p, "v": rng[n]} for n, p in nets.items()])


def address_clashes(d):
    return [f.text for f in requires.addresses(d)]


def test_address_pins_on_the_bus_lines_are_states_of_their_own():
    assert library.entry("C87469")["address"]["pins"]["7"] == {"low": 0, "high": 1, "sda": 2, "scl": 3}
    assert address_clashes(two_inas("SDA", "SCL")) == []                        # 0x42 and 0x43
    assert address_clashes(two_inas("VS", "SDA")) == []                         # 0x41 and 0x42
    clash = address_clashes(two_inas("SDA", "SDA"))
    assert len(clash) == 1 and "0x42" in clash[0]


def test_a_two_state_address_pin_reads_a_bus_line_as_high():
    d = two_inas("SDA", "SCL")
    d.parts["C87469"]["address"]["pins"] = {"7": 1, "8": 4}                   # before: SDA and SCL both "high"
    clash = address_clashes(d)
    assert len(clash) == 1 and "0x41" in clash[0]


# --- I1: a part's pins against its own ground ---------------------------------------------------------------------------
def local_ground_part(ground_net):
    e = {"kind": "ic", "values": {}, "limits": {}, "pins": {"1": {"name": "GND", "type": "ground"},
                                                          "2": {"name": "TD", "type": "input", "v_max_v": 10}}}
    nets = [{"name": "TD", "pins": ["U9.2"], "v": [-4.35, 0]}]
    if ground_net == "GND":
        nets.append({"name": "GND", "pins": ["U9.1"], "v": [0, 0]})
    else:
        nets += [{"name": ground_net, "pins": ["U9.1"], "v": [-4.2, 0]}, {"name": "GND", "pins": [], "v": [0, 0]}]
    return design({"P": e}, [comp("U9", "P", e)], nets)


def td(d):
    return next(q for q in quantities.pin_voltages(d) if q.place == "U9.2")


def test_a_pin_is_judged_against_the_parts_own_ground():
    q = td(local_ground_part("CELL_N"))                   # a protection IC on the cell's minus
    assert q.lo == pytest.approx(-0.15) and q.hi == pytest.approx(0) and "against CELL_N" in q.how
    assert not any(q.place == "U9.1" for q in quantities.pin_voltages(local_ground_part("CELL_N")))
    q = td(local_ground_part("GND"))                      # on the board's ground: the net's range as before
    assert q.lo == pytest.approx(-4.35)


# --- I7: a coupling electrolytic in a signal path ---------------------------------------------------------------------
def coupling_cap(mark):
    cap = lib("C2895284")
    out = {"name": "OUT", "pins": ["C9.2"], "v": [-1.5, 1.5]}
    if mark:
        out[mark] = True
    return design({"C2895284": cap}, [comp("C9", "C2895284", cap, type_="capacitor")],
                  [{"name": "OPOUT", "pins": ["C9.1"], "v": [0, 5]}, out])


def reverse(d):
    return [q.hi for q in quantities.part_voltages(d) if q.grade == "polarized"]


def test_a_coupling_capacitor_in_a_signal_path_is_left_to_stage_e():
    assert reverse(coupling_cap("signal")) == []
    assert reverse(coupling_cap("instrument")) == []
    assert reverse(coupling_cap(None)) == [pytest.approx(1.5)]                  # a capacitor off the signal path


# --- A7: LEDs a matrix driver scans ------------------------------------------------------------------------------------
@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
@pytest.mark.parametrize("behavior, multiplexed", [("matrix_driver", True), ("none", False)])
def test_leds_a_matrix_driver_scans_have_no_dc_state(project, behavior, multiplexed):
    from edakit.sim import run as simrun
    e = lib("C52476")
    e["values"]["behavior"] = behavior
    project.save_part("C52476", e)
    g = project.graph()
    graph = g["graph"]
    graph["components"].append({"designator": "U9", "type": "ic", "lcsc": "C52476", "board": "main",
                                "pins": {n: p["name"] for n, p in e["pins"].items()},
                                "nc": [n for n in e["pins"] if n not in ("4", "9", "14", "2")]})
    graph["components"].append({"designator": "D9", "type": "led", "lcsc": "C2297", "board": "main",
                                "pins": {"1": "A", "2": "K"}})
    graph["nets"] += [{"name": "SEGA", "pins": ["U9.14", "D9.1"], "v": [0, 5.5]},
                      {"name": "DIG0", "pins": ["U9.2", "D9.2"], "v": [0, 5.5]}]
    next(n for n in graph["nets"] if n["name"] == "GND")["pins"] += ["U9.4", "U9.9"]
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simrun.run_all(Design.from_config(project.config()), sim)
    d9 = [c for c in out["checks"] if c["item"] == "D9" and c["id"].startswith("SIM.")]
    if multiplexed:
        assert d9 and all(c["result"] == "info" and c["check"] == "LED multiplexed" for c in d9)
    else:
        assert any(c["id"] == "SIM.driver" and c["result"] == "fail" for c in d9)
    assert not [c for c in out["checks"] if c["item"] == "D9" and c["result"] == "fail" and not c["id"].startswith("SIM.")]
