"""Every graph rule seen red once: build the fault into a copy of the example and expect exactly that check."""

from edakit import checks
from edakit.design import Design


def run(project):
    cfg = project.config()
    return checks.run(Design.from_config(cfg), cfg)


def ids(rep):
    return {c for c, _ in rep.errors}


def test_example_is_clean(project):
    rep = run(project)
    assert rep.errors == []
    assert rep.pending == []
    assert {c for c, _, _ in rep.waived} == {"G-4"}


def test_g1_unconnected_pin(project):
    g = project.graph()
    net = project.net(g, "BTN")
    net["pins"].remove("SW1.1")
    project.save_graph(g)
    assert "G-1" in ids(run(project))


def test_g1_pin_in_two_nets(project):
    g = project.graph()
    project.net(g, "BTN")["pins"].append("R2.1")
    project.save_graph(g)
    assert any("used in 2 nets" in m for c, m in run(project).errors)


def test_g2_pin_lock(project):
    g = project.graph()
    project.net(g, "LED_CLK")["pins"].remove("U1.5")
    project.net(g, "BTN")["pins"].append("U1.5")
    project.save_graph(g)
    assert "G-2" in ids(run(project))


def test_g3_voltage_above_pin_limit(project):
    g = project.graph()
    project.net(g, "BTN")["v"] = [0, 5.0]   # 5 V on a 3.63-V GPIO
    project.save_graph(g)
    assert "G-3" in ids(run(project))


def test_g4_floating_input(project):
    g = project.graph()
    oe = project.net(g, "LED_OE")
    oe["pins"].remove("R2.2")
    project.net(g, "3V3")["pins"].remove("R2.1")
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "R2"]
    project.save_graph(g)
    assert any("LED_OE" in m for c, m in run(project).errors if c == "G-4")


def test_g5_two_outputs(project):
    g = project.graph()
    sdo = {"name": "CLASH", "pins": ["U2.14", "U1.10"], "v": [0, 3.4]}
    project.comp(g, "U2")["nc"].remove("14")
    project.comp(g, "U1")["nc"].remove("10")
    g["graph"]["nets"].append(sdo)
    project.save_graph(g)
    rep = run(project)
    # U1.10 is bidirectional, U2.14 an output: one output – no G-5; make the MCU pin an output too
    part = project.part("C41407547")
    part["pins"]["10"]["type"] = "output"
    project.save_part("C41407547", part)
    rep = run(project)
    assert "G-5" in ids(rep)


def test_g6_missing_decoupling(project):
    g = project.graph()
    project.net(g, "3V3")["pins"].remove("C1.1")
    project.net(g, "GND")["pins"].remove("C1.2")
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "C1"]
    project.save_graph(g)
    assert "G-6" in ids(run(project))


def test_g8_capacitor_rating(project):
    part = project.part("C45783")
    part["ratings"]["v_max"] = 6.3   # 22 µF on a 5.5-V rail needs 8.25 V
    project.save_part("C45783", part)
    assert "G-8" in ids(run(project))


def test_g10_reverse_protection_bypassed(project):
    g = project.graph()
    project.net(g, "VIN")["pins"] += ["U1.39"]          # VSYS directly at the connector
    project.net(g, "+5V")["pins"].remove("U1.39")
    project.save_graph(g)
    assert any("U1.39" in m for c, m in run(project).errors if c == "G-10")


def test_p1_pin_name_differs(project):
    g = project.graph()
    project.comp(g, "U2")["pins"]["2"] = "DATA"
    project.save_graph(g)
    assert "P-1" in ids(run(project))


def test_p1_missing_parts_entry(project):
    (project.root / "hardware" / "parts" / "C17414.json").unlink()
    assert "P-1" in ids(run(project))


def test_g9_unverified_part_is_pending(project):
    part = project.part("C2297")
    part["verified"] = None
    project.save_part("C2297", part)
    rep = run(project)
    assert not rep.errors
    assert any(c == "G-9" for c, _ in rep.pending)


def test_waive_needs_reason_and_is_reported(project):
    g = project.graph()
    project.net(g, "LED_CLK").pop("waive")
    project.save_graph(g)
    assert "G-4" in ids(run(project))
