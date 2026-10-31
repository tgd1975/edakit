"""The BME280's interfaces as configs (schema-gaps.md D3, F1): CSB tied to VDDIO selects I²C, and only there SDO – the
address LSB – must not float and the I²C address and roles hold; in 4-wire SPI CSB is a chip select and SDO a
tri-state data output, in 3-wire SPI SDO is not connected (Bosch BST-BME280-DS001-24 rev 1.24, 6.1–6.3, Table 35,
Figures 17–19). The library entry C92489, config_default i2c."""

from test_configs import findings, place

from edakit import library, schema
from edakit.design import configured

KEY = "C92489"
SUPPLY = {"8": "3V3", "6": "3V3", "1": "GND", "7": "GND"}


def csb(project):
    return [t for _, t in findings(project, "REQ.missing", "U9") if "CSB" in t]


def sdo(project, des="U9"):
    return [f"{g} {t}" for g, t in findings(project, "LVL.undefined", des) if "SDO" in t]


def test_the_configs_give_each_interface_its_pins():
    e = library.entry(KEY)
    assert schema.problems(e) == [] and e["config_default"] == "i2c"
    i2c, spi4, spi3 = (configured(e, c) for c in ("i2c", "spi4", "spi3"))
    assert (i2c["pins"]["3"]["role"], i2c["pins"]["4"]["role"], i2c["address"]["base"]) == ("sda", "scl", 0x76)
    assert i2c["pins"]["2"]["needs"][0]["what"] == "tie" and i2c["pins"]["5"]["float_ok"] is False
    assert "address" not in spi4 and "role" not in spi4["pins"]["3"] and spi4["pins"]["3"]["type"] == "input"
    assert (spi4["pins"]["5"]["type"], spi4["pins"]["5"]["drive"]) == ("output", "tristate")
    assert not spi4["pins"]["2"].get("needs") and not spi3["pins"]["2"].get("needs")
    assert spi3["pins"]["5"]["type"] == "no_connect" and spi3["pins"]["3"]["drive"] == "tristate"


def test_in_i2c_csb_is_tied_to_vddio(project):
    """CSB on a pin of its own fails in I²C (Figure 17: 'A direct connection between CSB and VDDIO is required');
    on VDDIO's net it passes."""
    place(project, KEY, "U9", {**SUPPLY, "2": "CS9", "5": "GND"})
    assert csb(project) == ["U9.2 (CSB): must be tied to U9.6 (VDDIO) (3V3), is on CS9"]
    place(project, KEY, "U8", {**SUPPLY, "2": "3V3", "5": "GND"})
    assert [t for _, t in findings(project, "REQ.missing", "U8") if "CSB" in t] == []


def test_in_spi_csb_is_a_chip_select(project):
    place(project, KEY, "U9", {**SUPPLY, "2": "CS9", "5": "MISO9"}, config="spi4")
    assert csb(project) == []
    place(project, KEY, "U8", {**SUPPLY, "2": "CS8"}, config="spi3")
    assert [t for _, t in findings(project, "REQ.missing", "U8") if "CSB" in t] == []


def test_in_i2c_sdo_must_not_float(project):
    """'The SDO pin cannot be left floating; if left floating, the I²C address will be undefined' (6.2) – in nc it is
    LVL.undefined/nc in I²C; in 4-wire SPI SDO is an output and in 3-wire SPI not connected, nc is right there."""
    place(project, KEY, "U9", {**SUPPLY, "2": "3V3"})
    assert sdo(project) == ["nc U9.5 (SDO): an input left open (nc) – it floats"]
    for des, config in (("U8", "spi4"), ("U7", "spi3")):
        place(project, KEY, des, {**SUPPLY, "2": f"CS{des}"}, config=config)
        assert sdo(project, des) == [], config


def test_the_i2c_address_counts_only_in_i2c(project):
    """Two BME280 with SDO on ground share 0x76 on an I²C bus; the same two in SPI have no address."""
    from helpers import check

    from edakit.design import Design
    for des in ("U8", "U9"):
        place(project, KEY, des, {**SUPPLY, "2": "3V3", "5": "GND", "3": "SDA9", "4": "SCL9"})
    cfg = project.config()

    def clash():
        return [f for f in check(Design.from_config(cfg), cfg).findings if f.code == "REQ.forbidden" and
                f.grade == "address"]
    assert clash()
    g = project.graph()
    for des in ("U8", "U9"):
        project.comp(g, des)["config"] = "spi4"
    project.save_graph(g)
    assert not clash()
