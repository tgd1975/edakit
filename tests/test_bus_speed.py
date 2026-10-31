"""Bus parameters (maker-coverage FT-16): per SPI device its modes and highest SCK, per I2C device its highest SCL, in
the firmware contract with the clock a net sets (clock_hz) and the speed an I2C bus's pull-ups allow (NXP UM10204
Rev. 7.0, 7.1: tr = 0.8473 · Rp · Cb); a clock above what a device or the pull-ups allow is LIM.range/clock."""

import copy

from helpers import check
from test_firmware import contract, with_firmware
from test_firmware_analog import SENSOR, resistors

from edakit import buses, firmware, schema
from edakit.circuit import cable_problems
from edakit.design import Design

# values for the tests, not from datasheets
SPI_DEVICE = {"lcsc": "C9000702", "mpn": "test SPI device", "kind": "ic", "verified": {"by": "test"},
              "needs": {"decoupling": False}, "values": {"behavior": "none", "spi_modes": [3]},
              "limits": {"f_sck_max_hz": 10e6},
              "pins": {"1": {"name": "SCK", "type": "input"}, "2": {"name": "SDI", "type": "input"},
                       "3": {"name": "GND", "type": "ground"}, "4": {"name": "VDD", "type": "power_in"}}}


def clock_findings(project, place=None):
    cfg = project.config()
    return [f for f in check(Design.from_config(cfg), cfg).findings
            if f.code == "LIM.range" and f.grade == "clock" and (place is None or f.place == place)]


def led_driver(project, modes=None, f_max=None):
    """The example's TLC5916 (U2, on the SPI bus LED: LED_SDI, LED_CLK) with modes and a highest SCK for the test."""
    part = project.part("C90107")
    part["values"].pop("spi_modes", None)
    part.setdefault("limits", {}).pop("f_sck_max_hz", None)
    if modes is not None:
        part["values"]["spi_modes"] = modes
    if f_max is not None:
        part["limits"]["f_sck_max_hz"] = f_max
    project.save_part("C90107", part)


def second_spi_device(project):
    project.save_part(SPI_DEVICE["lcsc"], SPI_DEVICE)
    g = project.graph()
    g["graph"]["components"].append({"designator": "U8", "type": "ic", "lcsc": SPI_DEVICE["lcsc"],
                                     "pins": {n: i["name"] for n, i in SPI_DEVICE["pins"].items()}})
    project.net(g, "LED_CLK")["pins"].append("U8.1")
    project.net(g, "LED_SDI")["pins"].append("U8.2")
    project.net(g, "GND")["pins"].append("U8.3")
    project.net(g, "3V3")["pins"].append("U8.4")
    project.save_graph(g)


def test_spi_devices_with_their_modes_and_clocks_in_the_contract(project):
    """U2 in mode 0 up to 30 MHz and U8 in mode 3 up to 10 MHz on the bus LED: both in devices.spi, the bus limited to
    10 MHz by U8, no mode both run in – the console says the firmware switches the mode per chip select."""
    with_firmware(project)
    led_driver(project, modes=[0], f_max=30e6)
    second_spi_device(project)
    c = contract(project)
    assert c["devices"]["spi"] == [{"bus": "LED", "part": "U2", "modes": [0], "f_max_hz": 30e6},
                                   {"bus": "LED", "part": "U8", "modes": [3], "f_max_hz": 10e6}]
    assert c["bus_speed"]["LED"] == {"kind": "spi", "sck": "LED_CLK", "clock_hz": None, "f_max_hz": 10e6, "by": "U8",
                                     "modes": []}
    cfg = project.config()
    assert any(line.startswith("LED: no SPI mode all its devices run in (U2 [0]; U8 [3])")
               for line in firmware.gaps(Design.from_config(cfg), c))
    led_driver(project, modes=[0, 3], f_max=30e6)
    assert contract(project)["bus_speed"]["LED"]["modes"] == [3]


def test_a_spi_clock_above_a_device_s_highest_sck(project):
    """LED_CLK at 20 MHz (clock_hz, carried into the contract): U2 with f_sck_max_hz 10 MHz is LIM.range/clock, with
    30 MHz it passes; without clock_hz nothing is judged."""
    with_firmware(project)
    led_driver(project, f_max=10e6)
    assert clock_findings(project) == []
    g = project.graph()
    project.net(g, "LED_CLK")["clock_hz"] = 20e6
    project.save_graph(g)
    found = clock_findings(project)
    assert [(f.place, f.stage) for f in found] == [("U2", "G")]
    assert "SCK on LED_CLK at 20 MHz (clock_hz), above its highest clock 10 MHz" in found[0].text
    assert found[0].source == "f_sck_max_hz of C90107"
    c = contract(project)
    assert c["pins"]["LED_CLK"]["clock_hz"] == 20e6 and c["bus_speed"]["LED"]["clock_hz"] == 20e6
    led_driver(project, f_max=30e6)
    assert clock_findings(project) == []


def i2c_sensor(project, pull="C17414", f_max=None, c_in=50e-12):
    """The I2C sensor of test_firmware_analog (U8 at 0x40 on SDA/SCL, pull-ups R8/R9) with an input capacitance of 50 pF
    on SDA and SCL – values for the test."""
    sensor = copy.deepcopy(SENSOR)
    for num in ("1", "2"):
        sensor["pins"][num]["c_in_f"] = c_in
    if f_max:
        sensor["limits"] = {"f_scl_max_hz": f_max}
    project.save_part(sensor["lcsc"], sensor)
    project.use_library_part(pull)
    g = project.graph()
    project.free_pins(g, "U1.1", "U1.2")
    g["graph"]["components"].append({"designator": "U8", "type": "ic", "lcsc": sensor["lcsc"],
                                     "pins": {n: i["name"] for n, i in sensor["pins"].items()}})
    resistors(g, "R8", "R9")
    for r in ("R8", "R9"):
        project.comp(g, r)["lcsc"] = pull
    project.net(g, "3V3")["pins"] += ["R8.1", "R9.1", "U8.5"]
    project.net(g, "GND")["pins"] += ["U8.3", "U8.4"]
    g["graph"]["nets"] += [{"name": "SDA", "pins": ["U1.1", "U8.1", "R8.2"], "v": [0, 3.4], "fn": "i2c.sda"},
                           {"name": "SCL", "pins": ["U1.2", "U8.2", "R9.2"], "v": [0, 3.4], "fn": "i2c.scl",
                            "clock_hz": 400e3}]
    project.save_graph(g)


def test_the_bus_speed_the_pull_ups_allow(project):
    """10 kΩ pull-ups and 50 pF known on each line (U8's c_in_f; the MCU's pins give none, tracks are not counted): tr =
    0.8473 × 10 kΩ × 50 pF = 424 ns – above Fast-mode's 300 ns, within Standard-mode's 1000 ns: 100 kHz, and SCL at
    400 kHz is LIM.range/clock. With 4.7 kΩ tr = 199 ns: Fast-mode, 400 kHz passes."""
    with_firmware(project)
    i2c_sensor(project)
    c = contract(project)
    assert c["devices"]["i2c"] == [{"bus": "SDA", "address": "0x40", "part": "U8", "how": "A0 low", "f_max_hz": None}]
    speed = c["bus_speed"]["SDA"]
    pulls = speed["pull_ups"]
    assert (speed["scl"], speed["clock_hz"], speed["f_max_hz"], speed["by"]) == ("SCL", 400e3, 100e3, "pull-ups")
    assert (pulls["pull_up_ohm"], pulls["rise_ns"], pulls["mode"]) == (10000.0, 423.7, "standard")
    assert pulls["c_bus"].startswith("U8.") and "not known: U1." in pulls["c_bus"] and "tracks not counted" in \
        pulls["c_bus"]
    found = clock_findings(project, "SCL")
    assert len(found) == 1 and "the pull-ups allow 100 kHz (standard)" in found[0].text
    assert "UM10204" in found[0].source


def test_fast_mode_with_stronger_pull_ups(project):
    with_firmware(project)
    i2c_sensor(project, pull="C17673")
    pulls = contract(project)["bus_speed"]["SDA"]["pull_ups"]
    assert (pulls["mode"], pulls["f_max_hz"], pulls["rise_ns"]) == ("fast", 400e3, 199.1)
    assert clock_findings(project) == []


def test_an_i2c_device_slower_than_the_bus_clock(project):
    """U8 with f_scl_max_hz 100 kHz on SCL at 400 kHz: LIM.range/clock at U8 (and in the contract as the slowest)."""
    with_firmware(project)
    i2c_sensor(project, pull="C17673", f_max=100e3)
    assert [f.place for f in clock_findings(project)] == ["U8"]
    speed = contract(project)["bus_speed"]["SDA"]
    assert (speed["f_max_hz"], speed["by"]) == (100e3, "U8")


def test_without_a_known_capacitance_the_pull_ups_are_not_judged(project):
    with_firmware(project)
    i2c_sensor(project, c_in=None)
    pulls = contract(project)["bus_speed"]["SDA"]["pull_ups"]
    assert pulls["f_max_hz"] is None and "no capacitance known" in pulls["why"]
    assert clock_findings(project) == []


def test_a_cable_s_capacitance_counts():
    """A cable with c_pf_per_m × length_m adds to the bus capacitance; c_pf_per_m without length_m is wrong."""
    graph = {"ground": "GND", "components": [
        {"designator": "J1", "type": "connector", "lcsc": "CJ", "pins": {"1": "1"}},
        {"designator": "J2", "type": "connector", "lcsc": "CJ", "pins": {"1": "1"}},
        {"designator": "U1", "type": "ic", "lcsc": "CU", "pins": {"1": "SCL"}},
        {"designator": "U2", "type": "ic", "lcsc": "CU", "pins": {"1": "SCL"}}],
        "nets": [{"name": "SCL_A", "pins": ["J1.1", "U1.1"], "v": [0, 3.3]},
                 {"name": "SCL_B", "pins": ["J2.1", "U2.1"], "v": [0, 3.3]}],
        "cables": [{"name": "W1", "from": "J1", "to": "J2", "pins": {"1": "1"}, "length_m": 2, "c_pf_per_m": 50}]}
    parts = {"CJ": {"kind": "connector", "pins": {"1": {"name": "1", "type": "passive"}}},
             "CU": {"kind": "ic", "pins": {"1": {"name": "SCL", "type": "bidirectional", "role": "scl",
                                                 "c_in_f": 10e-12}}}}
    d = Design.from_data(graph, parts)
    cb, held, unknown = buses.capacitance(d, "SCL_A")
    assert round(cb * 1e12, 6) == 110 and held == ["U1.1 10 pF", "cable W1 2 m × 50 pF/m"] and unknown == []
    assert cable_problems({"c_pf_per_m": 50, "r_ohm_per_wire": 0.1}) == ["c_pf_per_m needs the cable's length_m"]


def test_the_schema_holds_spi_modes():
    entry = {"kind": "ic", "values": {"spi_modes": [0, 3]}, "limits": {"f_sck_max_hz": 1e7, "f_scl_max_hz": 4e5},
             "pins": {"1": {"name": "SCL", "type": "input", "c_in_f": 1e-11}}}
    assert schema.problems(entry) == []
    entry["values"]["spi_modes"] = [4]
    assert schema.problems(entry) == ["values.spi_modes: a list of the SPI modes 0–3 (CPOL × 2 + CPHA) the part runs "
                                      "in, not [4]"]


def test_clock_hz_of_the_wrong_form(project):
    g = project.graph()
    project.net(g, "LED_CLK")["clock_hz"] = "fast"
    project.save_graph(g)
    cfg = project.config()
    assert [f.text for f in check(Design.from_config(cfg), cfg).findings if f.code == "STRUCT.net"] == [
        "LED_CLK: clock_hz must be the bus clock in Hz, not 'fast'"]
