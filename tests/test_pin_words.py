"""Pins by name or role (docs/concepts/new/circuit-language-plan.md, L.1 and L.2; the rules table of
docs/concepts/done/circuit-language.md): the Design reads every pin word of the graph once – the number first, then
the name of one pin, then the role of one pin, then a name or role several pins share, which stands for all of them –
and everything after it reads numbers as before. A finding names a pin by the word rule, the number in brackets where
it differs. A component without `pins` takes its parts entry's map."""

import json

from helpers import check

from edakit import engines, firmware
from edakit.design import Design
from edakit.sim import netlist
from edakit.sim import run as simrun

# led-bar's nets, nc and locks as a person writes them with the datasheet at hand: the Pico's and the TLC5916's names
# (U1.GP2, U2.OUT0), the LEDs' and the diode's roles (anode, cathode), a role on an IC where it says more (U2.oe_n,
# U2.rext), the eight GND pins of the Pico as one shared name; what says no more than the number stays a number (R1.1,
# J1.1 – role pin1); TP1 "GND (USB)" is no word and stays TP1.
LEDS = [f"D{n}" for n in range(2, 10)]
NAMED_NETS = {
    "VIN": ["J1.1", "D1.anode"],
    "+5V": ["D1.cathode", "U1.VSYS", "C2.1", *[f"{d}.anode" for d in LEDS]],
    "GND": ["J1.2", "U2.GND", "R1.2", "C1.2", "C2.2", "SW1.C", "U1.GND", "U1.AGND"],
    "3V3": ["U1.3V3(OUT)", "U2.VDD", "C1.1", "R2.1"],
    "LED_SDI": ["U1.GP3", "U2.SDI"],
    "LED_CLK": ["U1.GP2", "U2.CLK"],
    "LED_LE": ["U1.GP4", "U2.LE(ED1)"],
    "LED_OE": ["U1.GP5", "U2.oe_n", "R2.2"],
    "BTN": ["U1.GP6", "SW1.A"],
    "REXT": ["U2.rext", "R1.1"],
    **{f"LED{i}": [f"U2.OUT{i}", f"{d}.cathode"] for i, d in enumerate(LEDS)},
}
NAMED_NC = {
    "U1": ["GP0", "GP1", "GP7", "GP8", "GP9", "GP10", "GP11", "GP12", "GP13", "GP14", "GP15", "GP16", "GP17", "GP18",
           "GP19", "GP20", "GP21", "GP22", "RUN", "GP26_ADC0", "GP27_ADC1", "GP28_ADC2", "ADC_VREF", "3V3_EN", "VBUS",
           "SWCLK", "SWDIO", "TP1", "USB DM", "USB DP", "GPIO23/SMPS PS", "GPIO25/LED", "BOOTSEL"],
    "U2": ["SDO"],
    "SW1": ["B", "D"],
}
NAMED_LOCKS = {"U1.GP2": "LED_CLK", "U1.GP3": "LED_SDI", "U1.GP4": "LED_LE", "U1.GP5": "LED_OE", "U1.GP6": "BTN"}


def findings(project):
    cfg = project.config()
    rep = engines.run_all(Design.from_config(cfg), cfg)
    return sorted((f.code, f.place, f.text, f.severity, f.accepted) for f in rep.findings)


def named(project, maps=True):
    """led-bar with NAMED_NETS, NAMED_NC and NAMED_LOCKS; without `maps` its components without `pins` (L.2)."""
    g = project.graph()
    for net in g["graph"]["nets"]:
        net["pins"] = NAMED_NETS[net["name"]]
    for c in g["graph"]["components"]:
        if c["designator"] in NAMED_NC:
            c["nc"] = NAMED_NC[c["designator"]]
        if not maps:
            del c["pins"]
    g["graph"]["locks"]["pins"] = NAMED_LOCKS
    project.save_graph(g)
    return Design.from_config(project.config())


def same_design(a, b):
    """The resolved graphs connect the same pins: the pins of a net compared sorted (U1.GND stands for its pins in
    the entry's order), nc, locks, the pin maps."""
    assert {n: sorted(x["pins"]) for n, x in a.nets.items()} == {n: sorted(x["pins"]) for n, x in b.nets.items()}
    assert a.pin_net == b.pin_net
    def nc(design):
        return {d: sorted(c.get("nc", [])) for d, c in design.comps.items()}
    assert nc(a) == nc(b)
    assert {d: c["pins"] for d, c in a.comps.items()} == {d: c["pins"] for d, c in b.comps.items()}
    assert a.graph["locks"] == b.graph["locks"]


def netlists(project):
    cfg = project.config()
    sim = json.loads(cfg.sim_config.read_text())
    return [netlist.build(Design.from_config(cfg), sim, sc)[0] for sc in simrun.scenarios(sim)]


def contract(project):
    cfg = project.config()
    return {k: v for k, v in firmware.contract(cfg, Design.from_config(cfg)).items() if k != "state_sha256"}


# --- L.1: led-bar by names and roles ---------------------------------------------------------------------------------

def test_led_bar_by_names_and_roles_is_the_same_design_with_the_same_findings(project):
    numbers, before = Design.from_config(project.config()), findings(project)
    nets, fw = netlists(project), contract(project)
    words = named(project)
    same_design(words, numbers)
    assert findings(project) == before
    assert netlists(project) == nets                 # the simulation reads numbers
    assert contract(project) == fw                   # the firmware contract too


def test_a_json_graph_with_numbers_is_read_as_it_is(project):
    """Nothing is rewritten in a graph of numbers: the resolved graph is the file's."""
    g = project.graph()["graph"]
    d = Design.from_config(project.config())
    assert d.graph["nets"] == g["nets"] and d.graph["locks"] == g["locks"]
    assert [c.get("nc") for c in d.graph["components"]] == [c.get("nc") for c in g["components"]]
    assert d.entry_maps == set() and d.unresolved == []


def test_a_word_that_names_no_pin_is_struct_pin_and_the_rest_is_checked(project):
    g = project.graph()
    project.net(g, "BTN")["pins"] = ["U1.GP66", "SW1.A"]          # a typo: GP6
    project.save_graph(g)
    cfg = project.config()
    rep = check(Design.from_config(cfg), cfg)
    assert ("STRUCT.pin", "net BTN: U1.GP66 names no pin of U1") in rep.errors
    assert ("STRUCT.pin", "U1.GP6 (9) is neither connected nor nc") in rep.errors
    assert ("STRUCT.lock", "U1.GP6 (9) expected on net BTN, found None") in rep.errors
    assert {c for c, _ in rep.errors} == {"STRUCT.pin", "STRUCT.lock"}      # no loading error, every engine ran


def test_words_in_locks_loops_and_cables_resolve_and_a_bad_one_is_struct_pin():
    """Two boards joined by a cable W1 from J1 to J2, an LED on the second."""
    parts = {"C1": {"kind": "connector", "pins": {"1": {"name": "VCC", "role": "pin1"}, "2": {"name": "GND"},
                                                  "3": {"name": "GND"}}},
             "C2": {"kind": "led", "pins": {"1": {"name": "A", "role": "anode"},
                                            "2": {"name": "K", "role": "cathode"}}}}
    graph = {"components": [{"designator": "J1", "lcsc": "C1", "board": "a"},
                            {"designator": "J2", "lcsc": "C1", "board": "b"},
                            {"designator": "D1", "lcsc": "C2", "board": "b"}],
             "nets": [{"name": "VCC", "pins": ["J1.VCC", "J2.pin1", "D1.anode"], "v": [0, 5]},
                      {"name": "GND", "pins": ["J1.GND", "J2.GND", "D1.cathode"], "v": [0, 0]}],
             "cables": [{"name": "W1", "from": "J1", "to": "J2", "pins": {"VCC": "pin1", "2": "3", "GND": "GND"}}],
             "layout": {"loops": [{"a": "D1.anode", "b": "J2.VCC", "max_mm": 5}, {"a": "D1.cathode", "b": "J2.GND",
                                                                               "max_mm": 5}]},
             "locks": {"pins": {"D1.anode": "VCC", "J2.GND": "GND", "D1.gate": "VCC"}}}
    d = Design.from_data(graph, parts, ["a", "b"])
    assert d.nets["VCC"]["pins"] == ["J1.1", "J2.1", "D1.1"]
    assert d.nets["GND"]["pins"] == ["J1.2", "J1.3", "J2.2", "J2.3", "D1.2"]          # a shared name: all of them
    assert d.graph["cables"][0]["pins"] == {"1": "1", "2": "3", "GND": "GND"}
    assert d.graph["layout"]["loops"][0] | {"max_mm": 5} == {"a": "D1.1", "b": "J2.1", "max_mm": 5}
    assert d.graph["locks"]["pins"] == {"D1.1": "VCC", "J2.2": "GND", "J2.3": "GND", "D1.gate": "VCC"}
    texts = {f.text for f in engines.run(d).findings if f.code == "STRUCT.pin"}
    assert texts == {"cable W1: J1.GND names 2 pins (2, 3) – a wire lands on one pin",
                     "cable W1: J2.GND names 2 pins (2, 3) – a wire lands on one pin",
                     "layout.loops: J2.GND names 2 pins (2, 3) – a loop end is one pin",
                     "locks.pins: D1.gate names no pin of D1 (locked to net VCC)"}
    assert not [f for f in engines.run(d).findings if f.code == "STRUCT.lock" or "is no connected pin" in f.text]


# --- the rules table of the concept ----------------------------------------------------------------------------------

def design(project):
    return Design.from_config(project.config())


def test_the_number_comes_first():
    parts = {"X": {"kind": "connector", "pins": {"1": {"name": "2"}, "2": {"name": "1"}}}}
    d = Design.from_data({"components": [{"designator": "J1", "lcsc": "X"}], "nets": []}, parts)
    assert d.resolve("J1", "1") == ["1"] and d.resolve("J1", 2) == ["2"]


def test_a_name_of_one_pin_then_a_role_of_one_pin_then_a_shared_name_then_a_shared_role():
    parts = {"X": {"kind": "ic", "pins": {"1": {"name": "GND"}, "2": {"name": "GND", "role": "out"},
                                          "3": {"name": "SENSE", "role": "GND"}, "4": {"name": "OUT", "role": "x"},
                                          "5": {"name": "B", "role": "out"}, "6": {"name": "C", "role": "x"}}}}
    d = Design.from_data({"components": [{"designator": "U1", "lcsc": "X"}], "nets": []}, parts)
    assert d.resolve("U1", "OUT") == ["4"]           # the name of one pin before the role "out" of pins 2 and 5
    assert d.resolve("U1", "GND") == ["3"]           # the role of one pin before the name two pins share
    assert d.resolve("U1", "out") == ["2", "5"]      # a role several pins share: all of them
    assert d.resolve("U1", "x") == ["4", "6"]
    assert d.resolve("U1", "nothing") == []


def test_a_shared_name_stands_for_all_its_pins(project):
    d = design(project)
    assert d.resolve("U1", "GND") == ["3", "8", "13", "18", "23", "28", "38", "42"]     # not AGND, not TP1
    assert d.word("U1", "3") == "3" and d.pin_text("U1.3") == "U1.3"                     # one of them: its number


def test_a_shared_role_stands_for_all_its_pins(project):
    d = design(project)
    assert d.resolve("SW1", "a") == ["1", "2"] and d.resolve("SW1", "b") == ["3", "4"]
    assert d.word("SW1", "1") == "A"                 # the role is shared, the symbol's name is not


def test_a_word_that_says_no_more_than_the_number_is_written_as_the_number(project):
    d = design(project)
    assert d.word("J1", "1") == "1" and d.word("R1", "2") == "2"         # role pin1, name "1"
    assert d.resolve("J1", "pin2") == ["2"]                             # still read
    parts = {"X": {"kind": "connector", "pins": {str(n): {"name": f"P{n}", "role": f"pin{n}"} for n in (1, 2, 3)}}}
    j = Design.from_data({"components": [{"designator": "J1", "lcsc": "X"}], "nets": []}, parts)
    assert j.word("J1", "3") == "P3" and j.resolve("J1", "pin3") == ["3"]


def test_a_name_that_is_no_word_is_written_as_the_number(project):
    d = design(project)
    assert d.word("U1", "TP1") == "TP1" and d.pin_text("U1.TP1") == "U1.TP1"     # "GND (USB)"
    assert d.resolve("U1", "GND (USB)") == ["TP1"]                              # read all the same
    assert d.word("U1", "TP5") == "GPIO25/LED"


def test_the_nanos_swapped_labels_are_read_as_the_symbol_has_them():
    """The bell's Nano: the symbol labels pin 14 PB4 and pin 15 PB3, the chip has D11 = PB3 on pin 14. The graph
    names the symbol's pins; no alias corrects them (decision 6) – a comment in the graph says it."""
    pins = {"9": {"name": "PD6", "role": "gpio"}, "14": {"name": "PB4", "role": "gpio"},
            "15": {"name": "PB3", "role": "gpio"}, "4": {"name": "GND"}, "29": {"name": "GND"}}
    d = Design.from_data({"components": [{"designator": "U1", "part": "Nano"}],
                          "nets": [{"name": "MOSI", "pins": ["U1.PB4"]}]}, {"N": {"mpn": "Nano", "kind": "module",
                                                                                  "pins": pins}})
    assert d.nets["MOSI"]["pins"] == ["U1.14"]
    assert d.word("U1", "14") == "PB4" and d.word("U1", "9") == "PD6"
    assert d.resolve("U1", "GND") == ["4", "29"] and d.resolve("U1", "gpio") == ["9", "14", "15"]


def test_a_role_is_the_one_of_the_config_the_part_runs_in():
    """The SSD1306 panel C2890596: D0 (pin 18) is scl in I2C and sck in 4-wire SPI (its configs)."""
    from edakit import library
    parts = {"C2890596": library.entry("C2890596")}

    def panel(config):
        return Design.from_data({"components": [{"designator": "U5", "lcsc": "C2890596", "config": config}],
                                 "nets": []}, parts)
    assert panel("i2c").resolve("U5", "scl") == ["18"] and panel("i2c").resolve("U5", "sda") == ["19", "20"]
    assert panel("spi4").resolve("U5", "sck") == ["18"] and panel("spi4").resolve("U5", "scl") == []


def test_the_word_rule(project):
    """The role first on parts that are no IC or module, the name first on them; every word reads back as its pin."""
    d = design(project)
    assert [d.pin_text(r) for r in ("D2.1", "D1.1", "U1.9", "U1.39", "U2.13", "U2.15", "R1.1", "SW1.3")] == [
        "D2.anode (1)", "D1.cathode (1)", "U1.GP6 (9)", "U1.VSYS (39)", "U2.OE(ED2) (13)", "U2.R-EXT (15)", "R1.1",
        "SW1.C (3)"]
    for des, c in d.comps.items():
        for num in c["pins"]:
            assert d.resolve(des, d.word(des, num)) == [num], (des, num)


def test_a_finding_names_its_pin_by_the_word_rule(project):
    g = project.graph()
    project.net(g, "BTN")["pins"].remove("SW1.1")
    project.save_graph(g)
    cfg = project.config()
    found = [f for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == "STRUCT.pin"]
    assert [(f.place, f.text, f.line()) for f in found] == [
        ("SW1.1", "SW1.A (1) is neither connected nor nc", "G  SW1.A (1) is neither connected nor nc")]


# --- L.2: the pin map from the parts entry ---------------------------------------------------------------------------

def test_a_component_without_pins_takes_the_map_of_its_entry(project):
    numbers, before = design(project), findings(project)
    g = project.graph()
    del project.comp(g, "U1")["pins"]
    project.save_graph(g)
    d = design(project)
    assert d.comps["U1"]["pins"] == {n: p["name"] for n, p in project.part("C41407547")["pins"].items()}
    assert d.entry_maps == {"U1"}
    same_design(d, numbers)
    assert findings(project) == before


def test_led_bar_without_maps_and_by_names_is_the_same_design(project):
    numbers, before = design(project), findings(project)
    same_design(named(project, maps=False), numbers)
    assert findings(project) == before


def test_a_component_with_pins_keeps_them(project):
    g = project.graph()
    project.comp(g, "U2")["pins"]["14"] = "DOUT"           # differs from the entry: compared as before
    project.save_graph(g)
    cfg = project.config()
    rep = check(Design.from_config(cfg), cfg)
    assert any(c == "STRUCT.entry" and "U2: pins differ from parts entry C90107" in m for c, m in rep.errors)


def test_a_part_without_entry_and_map_is_struct_entry_and_nothing_else(project):
    g = project.graph()
    g["graph"]["components"].append({"designator": "R9", "type": "resistor", "part": "RC0805FR-0710KL",
                                     "lcsc": "C9999991", "value": "10k"})
    project.net(g, "3V3")["pins"].append("R9.1")
    project.net(g, "BTN")["pins"].append("R9.2")
    project.save_graph(g)
    cfg = project.config()
    d = Design.from_config(cfg)
    assert d.comps["R9"]["pins"] == {"1": "1", "2": "2"}
    found = [(f.code, f.text) for f in engines.run_all(d, cfg).findings if f.place.split(".")[0] == "R9"]
    assert found == [("STRUCT.entry", "R9: no parts entry C9999991.json")]
