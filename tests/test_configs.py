"""Configs of a part (handbook 4.1): an entry's `configs` hold what a part looks like in one way of using it – its
supply mode, its interface –, a component names the one it uses with `config`, and a pin need with `when` holds only
in that config (or only where the pin is connected). Entries from the parts library, each config read from its
datasheet."""

from helpers import check

from edakit import library, schema
from edakit.design import Design, configured


def place(project, key, des, nets, config=None, extra_nets=()):
    """Library entry `key` as component `des` in the example; nets {pin: net} (a net the example lacks is made, with
    the range of extra_nets {name: [min, max]}); every other pin in nc."""
    entry = library.entry(key)
    project.save_part(key, entry)
    g = project.graph()
    graph = g["graph"]
    comp = {"designator": des, "type": "ic", "lcsc": key, "board": "main",
            "pins": {n: p["name"] for n, p in entry["pins"].items()}, "nc": [n for n in entry["pins"] if n not in nets]}
    if config:
        comp["config"] = config
    graph["components"].append(comp)
    by_name = {n["name"]: n for n in graph["nets"]}
    for pin, net in nets.items():
        if net in by_name:
            by_name[net]["pins"].append(f"{des}.{pin}")
        else:
            by_name[net] = {"name": net, "pins": [f"{des}.{pin}"], "v": dict(extra_nets).get(net, [0, 3.4])}
            graph["nets"].append(by_name[net])
    project.save_graph(g)


def findings(project, code, des):
    cfg = project.config()
    return [(f.grade, f.text) for f in check(Design.from_config(cfg), cfg).findings
            if f.code == code and f.place.split(".")[0].split(" ")[0] == des]


def test_a_component_sees_its_config_and_without_one_the_entry():
    entry = library.entry("C84681")                                        # CH340C
    assert configured(entry, "3v3")["limits"]["vdd_op_max_v"] == 3.6
    assert configured(entry, "5v")["limits"]["vdd_op_min_v"] == 4.0
    assert "needs" not in configured(entry, "3v3")["pins"]["4"]               # V3 joined to VCC, no capacitor of its own
    assert configured(entry, "5v")["pins"]["4"]["needs"][0]["what"] == "capacitor"   # V3 only to its capacitor
    assert configured(entry, None)["limits"]["vdd_op_min_v"] == 3.1       # the entry's own union
    cp = configured(library.entry("C6568"), "bypassed")                    # CP2102 configuration 3
    assert "behavior" not in cp["values"] and "vin_min_v" not in cp["limits"] and cp["pins"]["6"]["type"] == "power_in"
    assert "address" not in configured(library.entry("C2890596"), "spi4")
    assert configured(library.entry("C2890596"), "i2c")["pins"]["18"]["role"] == "scl"


def test_a_config_the_entry_does_not_know_is_struct_entry(project):
    place(project, "C84681", "U9", {"16": "3V3", "1": "GND", "4": "3V3"}, config="3v")
    assert findings(project, "STRUCT.entry", "U9") == [("", "U9: config '3v' – parts entry C84681 knows 3v3, 5v")]
    place(project, "C6568", "U8", {"3": "GND"}, config="regulator")
    assert [t for _, t in findings(project, "STRUCT.entry", "U8") if "config" in t] == []


def test_the_supply_mode_holds_the_pins_to_its_own_range(project):
    """A CH340C told it runs at 5 V but on 3.3 V: V3 stays a capacitor pin, the 5 V range does not fit the rail."""
    place(project, "C84681", "U9", {"16": "3V3", "1": "GND", "4": "3V3"}, config="3v3")
    assert findings(project, "LIM.range", "U9") == []
    g = project.graph()
    project.comp(g, "U9")["config"] = "5v"
    project.save_graph(g)
    cfg = project.config()
    d = Design.from_config(cfg)
    assert d.part("U9")["limits"]["vdd_op_min_v"] == 4.0 and d.part("U9")["pins"]["4"]["needs"]


def test_a_need_with_when_holds_only_in_its_config(project):
    """DS3231 VBAT: backup needs nothing, primary a 0.1 µF capacitor, unused it goes to ground (19-5170 Rev 10)."""
    nets = {"2": "3V3", "13": "GND", "14": "VBAT9", **{str(n): "GND" for n in range(5, 13)}}    # N.C. 5–12 on ground
    place(project, "C9866", "U9", nets, extra_nets={"VBAT9": [0, 3.4]})

    def vbat():
        return [t for _, t in findings(project, "REQ.missing", "U9") if "VBAT" in t]
    assert vbat() == []                                                    # config_default backup
    g = project.graph()
    project.comp(g, "U9")["config"] = "vbat_primary"
    project.save_graph(g)
    assert vbat() == ["U9.14 (VBAT): needs a capacitor of at least 100 nF to GND – VBAT9 has none"]
    project.comp(g, "U9")["config"] = "no_battery"
    project.save_graph(g)
    assert vbat() == ["U9.14 (VBAT): must be on ground (GND), is on VBAT9"]


def test_parasite_power_puts_vdd_on_ground(project):
    """DS18B20: in parasite power VDD must be grounded (19-7487 Rev 6) – a VDD on 3V3 is reported there only."""
    place(project, "C9753", "U9", {"1": "GND", "2": "OW", "3": "3V3"}, config="parasite")
    assert ("pin", "U9.3 (VDD): must be on ground (GND), is on 3V3") in findings(project, "REQ.missing", "U9")
    g = project.graph()
    project.comp(g, "U9")["config"] = "external"
    project.save_graph(g)
    assert not [t for _, t in findings(project, "REQ.missing", "U9") if "U9.3" in t]


def test_a_need_when_connected_leaves_an_unused_pin_alone(project):
    """INA226 Alert (SBOS547C 8.2.1.2): a pull-up where it is used, nothing where it is in nc."""
    place(project, "C49851", "U9", {"6": "3V3", "7": "GND"})
    assert not [t for _, t in findings(project, "REQ.missing", "U9") if "Alert" in t]
    place(project, "C49851", "U8", {"6": "3V3", "7": "GND", "3": "ALERT8"})
    assert [t for _, t in findings(project, "REQ.missing", "U8") if "Alert" in t] == [
        "U8.3 (Alert): needs a pull up to a supply – ALERT8 has none"]


def test_the_interface_config_gives_the_pins_their_roles(project):
    """SSD1306 panel: in i2c D0 is SCL and wants its pull-up; in spi4 the same net is a clock and no I2C line."""
    place(project, "C2890596", "U9", {"8": "GND", "9": "3V3", "18": "OLED_CLK"}, config="i2c")
    i2c = [t for _, t in findings(project, "REQ.missing", "OLED_CLK")]
    assert i2c and "pull" in i2c[0]
    g = project.graph()
    project.comp(g, "U9")["config"] = "spi4"
    project.save_graph(g)
    assert findings(project, "REQ.missing", "OLED_CLK") == []


def test_the_schema_holds_configs_and_when():
    e = library.entry("C9866")
    assert schema.problems(e) == []
    bad = {**e, "config_default": "solar"}
    assert "config_default: 'solar' – not one of configs (backup, vbat_primary, no_battery)" in schema.problems(bad)
    bad = {**e, "configs": {**e["configs"], "x": {"pins": {"99": {"type": "input"}}, "colour": "red"}}}
    probs = schema.problems(bad)
    assert "configs.x.pins.99: no pin 99 in the entry" in probs and any("configs.x.colour" in p for p in probs)
    pins = {**e["pins"], "14": {**e["pins"]["14"], "needs": [{"what": "to_ground", "when": "sunny"}]}}
    assert any("when 'sunny'" in p for p in schema.problems({**e, "pins": pins}))
    pins = {**e["pins"], "14": {**e["pins"]["14"], "type": "sideways"}}
    assert any(p.startswith("configs.backup: pins.14.type") for p in schema.problems({**e, "pins": pins}))
