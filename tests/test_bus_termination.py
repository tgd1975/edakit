"""RS-485 and CAN termination and idle bias (maker-coverage CK-17): one 120 Ω at each end of the bus, two across the
boards of the graph, and an RS-485 bias pair that holds at least 200 mV across the terminations – numbers read from
TI SLLA272D and SLOA101B (catalog/tables/buses.toml); grades termination and failsafe, warnings while new."""

from helpers import check
from reference import Project, add, resistor, wire

from edakit import catalog
from edakit.design import Design


def transceiver(p, key="C9100040", a="rs485_a", b="rs485_b"):
    p.save_part(key, {"lcsc": key, "mpn": "bus transceiver (test part)", "kind": "ic", "verified": {"by": "test"},
                      "pins": {"1": {"name": "VCC", "type": "power_in"}, "2": {"name": "GND", "type": "ground"},
                               "3": {"name": "A", "type": "bidirectional", "role": a},
                               "4": {"name": "B", "type": "bidirectional", "role": b}}})
    return key


def bus(p, terminations=(), bias=None, roles=("rs485_a", "rs485_b")):
    """Two transceivers U40, U41 on BUS_A/BUS_B; terminations: [ohm, …] across the pair; bias: (up, down) ohm."""
    key = transceiver(p, a=roles[0], b=roles[1])
    g = p.graph()
    for des in ("U40", "U41"):
        add(g, des, "ic", key, {"1": "VCC", "2": "GND", "3": "A", "4": "B"})
        wire(g, "+5V", f"{des}.1")
        wire(g, "GND", f"{des}.2")
        wire(g, "BUS_A", f"{des}.3", v=(0, 5))
        wire(g, "BUS_B", f"{des}.4", v=(0, 5))
    for i, ohm in enumerate(terminations):
        k = f"C91000{50 + i}"
        resistor(p, k, ohm)
        add(g, f"R{50 + i}", "resistor", k, {"1": "1", "2": "2"})
        wire(g, "BUS_A", f"R{50 + i}.1")
        wire(g, "BUS_B", f"R{50 + i}.2")
    if bias:
        for des, k, ohm, net, to in (("R60", "C9100060", bias[0], "BUS_A", "+5V"),
                                     ("R61", "C9100061", bias[1], "BUS_B", "GND")):
            resistor(p, k, ohm)
            add(g, des, "resistor", k, {"1": "1", "2": "2"})
            wire(g, net, f"{des}.1")
            wire(g, to, f"{des}.2")
    p.save_graph(g)


def found(p):
    cfg = p.config()
    rep = check(Design.from_config(cfg), cfg)
    return sorted((f.code, f.grade, f.severity) for f in rep.findings if f.grade in ("termination", "failsafe"))


def project(tmp_path):
    return Project.copy_of_example(tmp_path / "bus")


def test_the_numbers_come_from_ti():
    t = catalog.table("buses")
    assert t["rs485"]["termination_ohm"] == t["can"]["termination_ohm"] == 120
    assert t["rs485"]["idle_min_v"] == 0.2
    assert "SLLA272D" in t["rs485"]["source"] and "SLOA101B" in t["can"]["source"]


def test_two_terminations_of_120_ohm_are_quiet(tmp_path):
    p = project(tmp_path)
    bus(p, (120, 120))
    assert found(p) == []


def test_a_bus_without_both_terminations(tmp_path):
    p = project(tmp_path)
    bus(p, (120,))
    assert found(p) == [("REQ.missing", "termination", "warning")]


def test_a_third_termination_and_a_wrong_value(tmp_path):
    p = project(tmp_path)
    bus(p, (120, 120, 100))
    assert found(p) == [("REQ.forbidden", "termination", "warning"), ("REQ.value", "termination", "warning")]


def test_a_can_bus_is_held_the_same(tmp_path):
    p = project(tmp_path)
    bus(p, (), roles=("canh", "canl"))
    assert found(p) == [("REQ.missing", "termination", "warning")]


def test_rs485_bias_too_weak_for_200_mV(tmp_path):
    p = project(tmp_path)
    bus(p, (120, 120), bias=(10_000, 10_000))       # 5 V × 60 Ω / 20.06 kΩ ≈ 15 mV
    assert found(p) == [("REQ.value", "failsafe", "warning")]
    p = project(tmp_path / "strong")
    bus(p, (120, 120), bias=(560, 560))             # 5 V × 60 Ω / 1180 Ω ≈ 254 mV
    assert found(p) == []
