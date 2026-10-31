"""The firmware contract's analog inputs (maker-coverage FT-10) and the devices on its I2C lines (FT-16, in part)."""

from test_firmware import contract, with_firmware

# values for the tests, not from datasheets
SENSOR = {"lcsc": "C9000701", "mpn": "test I2C sensor", "kind": "ic", "verified": {"by": "test"},
          "needs": {"decoupling": False}, "values": {"behavior": "none"},
          "address": {"base": 64, "pins": {"3": 1}},
          "pins": {"1": {"name": "SDA", "type": "bidirectional", "role": "sda"},
                   "2": {"name": "SCL", "type": "input", "role": "scl"},
                   "3": {"name": "A0", "type": "input"}, "4": {"name": "GND", "type": "ground"},
                   "5": {"name": "VDD", "type": "power_in"}}}


def resistors(g, *names):
    g["graph"]["components"] += [{"designator": n, "type": "resistor", "lcsc": "C17414", "value": "10k",
                                  "pins": {"1": "1", "2": "2"}} for n in names]


def test_a_divider_and_a_pull_up_in_front_of_adc_pins(project):
    with_firmware(project)
    project.use_library_part("C17414")
    g = project.graph()
    project.free_pins(g, "U1.31", "U1.32")
    resistors(g, "R8", "R9", "R10")
    project.net(g, "+5V")["pins"].append("R8.1")
    project.net(g, "GND")["pins"].append("R9.2")
    project.net(g, "3V3")["pins"].append("R10.1")
    g["graph"]["nets"] += [{"name": "VSENSE", "pins": ["R8.2", "R9.1", "U1.31"], "v": [0, 3.4], "fn": "adc"},
                           {"name": "TEMP", "pins": ["R10.2", "U1.32"], "v": [0, 3.4], "fn": "adc"}]
    project.save_graph(g)
    a = contract(project)["analog"]
    assert a["VSENSE"] == {"pin": "U1.31", "gpio": 26, "channel": "adc0", "pull_up_ohm": None, "pull_down_ohm": None,
                           "divider": {"from": "+5V", "top": "R8", "top_ohm": 10000.0, "bottom": "R9",
                                       "bottom_ohm": 10000.0, "ratio": 0.5}}
    assert a["TEMP"]["divider"] is None and a["TEMP"]["pull_up_ohm"] == 10000.0


def test_the_example_has_no_analog_input_and_no_i2c_device(project):
    """Its one bus device is the TLC5916 on the SPI bus LED (FT-16) – the fixture's entry gives no modes and no clock."""
    with_firmware(project)
    c = contract(project)
    assert c["analog"] == {} and c["devices"] == {"spi": [{"bus": "LED", "part": "U2", "modes": None,
                                                           "f_max_hz": None}]}


def test_a_device_on_the_i2c_lines_with_its_address(project):
    with_firmware(project)
    project.save_part(SENSOR["lcsc"], SENSOR)
    project.use_library_part("C17414")
    g = project.graph()
    project.free_pins(g, "U1.1", "U1.2")
    g["graph"]["components"].append({"designator": "U8", "type": "ic", "lcsc": SENSOR["lcsc"],
                                     "pins": {n: i["name"] for n, i in SENSOR["pins"].items()}})
    resistors(g, "R8", "R9")
    project.net(g, "3V3")["pins"] += ["R8.1", "R9.1", "U8.5"]
    project.net(g, "GND")["pins"] += ["U8.3", "U8.4"]
    g["graph"]["nets"] += [{"name": "SDA", "pins": ["U1.1", "U8.1", "R8.2"], "v": [0, 3.4], "fn": "i2c.sda"},
                           {"name": "SCL", "pins": ["U1.2", "U8.2", "R9.2"], "v": [0, 3.4], "fn": "i2c.scl"}]
    project.save_graph(g)
    c = contract(project)
    assert c["devices"]["i2c"] == [{"bus": "SDA", "address": "0x40", "part": "U8", "how": "A0 low", "f_max_hz": None}]
