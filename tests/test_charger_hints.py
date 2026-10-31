"""A load on the charging cell (HINT.power_path, maker-coverage HT-5) and what needs behaviour over time
(rules-at-scale.md, decision 17): HINT.charge_termination, HINT.protection_timing, HINT.pd_negotiation where such a part
is used, and the coverage report's "not simulated" for the same parts.

The circuit is AN1149's (Microchip DS01149C, 2008, p. 5): an MCP73831 charges a cell from +5V; the system load – an
RT9080 regulator – sits on the cell (the fault), or on SYS, fed from the input through a Schottky while a P-MOSFET whose
gate the input holds high cuts the cell off (the load sharing of the application note)."""

from test_block import place
from test_sim_w5 import pd_sink

from edakit import engines, profile
from edakit.design import Design
from edakit.engines import hint
from edakit.engines.coverage import coverage, summary

CELL = {"lcsc": "C9300001", "mpn": "one Li-ion cell holder (test)", "kind": "battery_holder",
        "verified": {"by": "test"}, "limits": {"v_max_v": 4.35},
        "pins": {"1": {"name": "+", "type": "passive", "role": "plus"},
                 "2": {"name": "-", "type": "passive", "role": "minus"}}}
CHARGE_HINTS = ("HINT.power_path", "HINT.charge_termination", "HINT.protection_timing", "HINT.pd_negotiation")


def charging(project, load="cell"):
    """U100 MCP73831 from +5V into VBAT (R100 10 kΩ, 100 mA), BT100 the cell; U101 an RT9080 as the system load with
    VIN and EN on the net `load` takes: "cell" VBAT itself; "sharing" SYS, fed by D101 SS14 from +5V and by Q101 AO3401A
    from VBAT (drain VBAT, source SYS, gate +5V, R101 10 kΩ to GND – AN1149 fig. 5–7); "diodes" SYS from +5V through
    D101 and from VBAT through D102; "switch" SYS through Q101 alone, its gate driven by the MCU's GP7."""
    for key in ("C424093", "C841192", "C2480", "C15127", "C17414"):
        project.use_library_part(key)
    project.save_part(CELL["lcsc"], CELL)
    g = project.graph()
    gg = g["graph"]
    comps = [("U100", "ic", "C424093", {"1": "STAT", "2": "VSS", "3": "VBAT", "4": "VDD", "5": "PROG"}, ["1"]),
             ("R100", "resistor", "C17414", {"1": "1", "2": "2"}, []),
             ("BT100", "battery_holder", CELL["lcsc"], {"1": "+", "2": "-"}, []),
             ("U101", "ic", "C841192", {"1": "VIN", "2": "GND", "3": "EN", "4": "NC", "5": "VOUT"}, ["4", "5"])]
    nets = {"+5V": ["U100.4"], "GND": ["U100.2", "R100.2", "BT100.2", "U101.2"], "PROG": ["U100.5", "R100.1"],
            "VBAT": ["U100.3", "BT100.1"]}
    sys = "VBAT" if load == "cell" else "SYS"
    nets.setdefault(sys, [])
    nets[sys] += ["U101.1", "U101.3"]
    if load in ("sharing", "diodes"):
        comps.append(("D101", "diode", "C2480", {"1": "K", "2": "A"}, []))
        nets["+5V"].append("D101.2")
        nets["SYS"].append("D101.1")
    if load in ("sharing", "switch"):
        comps.append(("Q101", "transistor", "C15127", {"1": "G", "2": "S", "3": "D"}, []))
        nets["VBAT"].append("Q101.3")
        nets["SYS"].append("Q101.2")
    if load == "sharing":
        comps.append(("R101", "resistor", "C17414", {"1": "1", "2": "2"}, []))
        nets["+5V"] += ["Q101.1", "R101.1"]
        nets["GND"].append("R101.2")
    if load == "diodes":
        comps.append(("D102", "diode", "C2480", {"1": "K", "2": "A"}, []))
        nets["VBAT"].append("D102.2")
        nets["SYS"].append("D102.1")
    if load == "switch":
        project.free_pins(g, "U1.10")
        nets["GATE"] = ["Q101.1", "U1.10"]
    for des, kind, key, pins, nc in comps:
        gg["components"].append({"designator": des, "type": kind, "lcsc": key, "pins": pins, "nc": nc,
                                 **({"bom": False} if kind == "battery_holder" else {})})
    for name, pins in nets.items():
        net = next((n for n in gg["nets"] if n["name"] == name), None)
        if net is None:
            gg["nets"].append({"name": name, "pins": pins, "v": [0, 5.5]})
        else:
            net["pins"] += pins
    project.save_graph(g)


def hints(project):
    """{code: [places]} of the four hints as edakit check reports them under the project's domains."""
    cfg = project.config()
    found = {}
    for f in engines.run(Design.from_config(cfg), cfg).findings:
        if f.code in CHARGE_HINTS:
            found.setdefault(f.code, []).append(f.place)
    return found


def test_a_load_on_the_charging_cell_gets_the_hint(project):
    charging(project, "cell")
    found = hints(project)
    assert found["HINT.power_path"] == ["U100"]
    assert found["HINT.charge_termination"] == ["U100"]


def test_the_load_sharing_of_an1149_is_a_power_path(project):
    charging(project, "sharing")                  # Q101 off while +5V is there, D101 feeds SYS from the input
    found = hints(project)
    assert "HINT.power_path" not in found and found["HINT.charge_termination"] == ["U100"]


def test_two_diodes_onto_the_system_rail_are_a_power_path(project):
    charging(project, "diodes")                   # D102 blocks while D101 holds SYS above the cell
    assert "HINT.power_path" not in hints(project)


def test_a_load_switch_the_firmware_drives_is_no_power_path(project):
    charging(project, "switch")                   # Q101 conducts while the MCU holds it on – also while charging
    assert hints(project)["HINT.power_path"] == ["U100"]


def test_the_cells_protection_and_a_divider_are_no_load(project):
    """The block lipo-charger: the cell feeds the DW01A's supply through 100 Ω and SYS only through Q2, whose gate
    vbus holds – no HINT.power_path; the charger and the DW01A get the hints of decision 17. A divider on the cell
    to an ADC pin draws from it, but is no load the hint is about."""
    place(project, "lipo-charger")
    d = Design.from_config(project.config())
    assert "power" in profile.suggested(d)                         # a charger suggests the domain, holder or not
    charger = next(x for x in d.comps if d.comps[x].get("lcsc") == "C424093")
    guard = next(x for x in d.comps if d.comps[x].get("lcsc") == "C351410")
    found = hints(project)
    assert "HINT.power_path" not in found
    assert found["HINT.charge_termination"] == [charger] and found["HINT.protection_timing"] == [guard]
    g = project.graph()
    cell = next(n["name"] for n in g["graph"]["nets"] if f"{charger}.3" in n["pins"])
    g["graph"]["components"] += [{"designator": "R110", "type": "resistor", "lcsc": "C17414", "pins": {"1": "1", "2": "2"}},
                                 {"designator": "R111", "type": "resistor", "lcsc": "C17414", "pins": {"1": "1", "2": "2"}}]
    next(n for n in g["graph"]["nets"] if n["name"] == cell)["pins"].append("R110.1")
    next(n for n in g["graph"]["nets"] if n["name"] == "GND")["pins"].append("R111.2")
    project.free_pins(g, "U1.31")
    g["graph"]["nets"].append({"name": "VBAT_SENSE", "pins": ["R110.2", "R111.1", "U1.31"], "v": [0, 2.2]})
    project.save_graph(g)
    assert "HINT.power_path" not in hints(project)


def test_a_pd_sink_gets_the_negotiation_hint(project):
    pd_sink(project, 1e3, vbus_top=21.0)          # the CH224K with its cc pins suggests the domain usb
    assert hints(project) == {"HINT.pd_negotiation": ["U9"]}


def test_the_matchers_name_each_behaviour():
    from test_false_alarms import comp, design, lib
    parts = lib("C424093", "C351410", "C970725")
    d = design([comp("U1", "C424093", parts), comp("U2", "C351410", parts), comp("U3", "C970725", parts)], [], parts)
    assert hint.MATCHERS["charger"](d, None, None) == ["U1"]
    assert hint.MATCHERS["cell_protection"](d, None, None) == ["U2"]
    assert hint.MATCHERS["pd_sink"](d, None, None) == ["U3"]
    assert hint.MATCHERS["loaded_cell"](d, None, None) == []          # nothing on the cell's net


def not_simulated(project):
    d = Design.from_config(project.config())
    return [g for g in coverage(d, engines.profile(d, project.config())) if g.kind != "data"]


def test_the_coverage_lists_what_is_not_simulated(project):
    assert not_simulated(project) == []
    place(project, "lipo-charger")
    lines = [g.line() for g in not_simulated(project)]
    assert any(x.startswith("SIM.state: U") and "not simulated: the end of the charge cycle – termination at 7.5 %"
               in x and "(C424093)" in x for x in lines), lines
    assert any("not simulated: the release voltages and the delays" in x and "(C351410)" in x for x in lines), lines
    d = Design.from_config(project.config())
    line = summary(coverage(d, engines.profile(d, project.config())))
    assert "; not simulated over time: " in line and line.endswith(" – edakit check --coverage")


def test_the_coverage_lists_a_pd_sink(project):
    pd_sink(project, 1e3, vbus_top=21.0)
    lines = [g.line() for g in not_simulated(project)]
    assert lines == ["SIM.state: U9 – not simulated: the USB PD negotiation, PG and the CC lines – VBUS is the voltage "
                     "a scenario's source gives (HINT.pd_negotiation) (C970725)"]
