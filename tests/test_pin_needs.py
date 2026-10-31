"""What a pin needs from the circuit, from its parts entry (maker-coverage CK-13, CK-14): a capacitor to ground, a
pull-up or pull-down, a series resistor, each in a window; to be on ground, or never on it. REQ.missing, REQ.value and
REQ.forbidden with the grade pin – warnings while the mechanism is new."""

from helpers import check

from edakit import engines
from edakit.design import Design


def needs_on(project, num, needs, key="C90107"):
    """U2's (TLC5916, C90107) pin `num` gets `needs` – values for the test, not from its datasheet."""
    part = project.part(key)
    part["pins"][num]["needs"] = needs
    project.save_part(key, part)


def found(project, code):
    cfg = project.config()
    rep = engines.run(Design.from_config(cfg), cfg)
    return [(f.text, f.grade, f.severity) for f in rep.findings if f.code == code and f.grade == "pin"]


def test_a_capacitor_in_its_window(project):
    needs_on(project, "16", [{"what": "capacitor", "c_min_f": 47e-9, "c_max_f": 1e-6, "source": "test"}])
    assert found(project, "REQ.missing") == found(project, "REQ.value") == []      # C1 100 nF on 3V3
    needs_on(project, "16", [{"what": "capacitor", "c_min_f": 1e-6}])
    assert found(project, "REQ.value") == [
        ("U2.VDD (16): needs a capacitor of at least 1 µF to GND – C1 on 3V3: 100 nF", "pin", "warning")]


def test_a_pull_up_the_pin_lacks(project):
    needs_on(project, "4", [{"what": "pull_up", "r_min_ohm": 4.7e3, "r_max_ohm": 10e3}])     # LE(ED1): none on it
    assert found(project, "REQ.missing") == [
        ("U2.LE(ED1) (4): needs a pull up of 4.7 kΩ … 10 kΩ to a supply – LED_LE has none", "pin", "warning")]


def test_ground_and_never_ground(project):
    needs_on(project, "1", [{"what": "never_to_ground"}])                       # U2.1 is GND
    assert found(project, "REQ.forbidden") == [("U2.GND (1): must never be on ground, is on GND", "pin", "warning")]
    needs_on(project, "1", [{"what": "to_ground"}])
    assert found(project, "REQ.missing") == []


def test_a_needs_entry_of_the_wrong_form(project):
    needs_on(project, "4", [{"what": "pull_sideways"}, {"what": "pull_up", "r_min_ohm": "10k"}])
    cfg = project.config()
    texts = [f.text for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == "PARTS.schema"]
    assert any("what must be one of capacitor, pull_up" in t for t in texts)
    assert "C90107: pin 4 needs pull_up: r_min_ohm must be a number" in texts


def test_accepted_on_the_component(project):
    needs_on(project, "4", [{"what": "pull_up"}])
    g = project.graph()
    project.comp(g, "U2")["accept"] = {"REQ.missing/pin": "LE is driven by U1 from reset on"}
    project.save_graph(g)
    cfg = project.config()
    assert check(Design.from_config(cfg), cfg).errors == []
    rep = engines.run(Design.from_config(cfg), cfg)
    assert [f.accepted for f in rep.findings if f.code == "REQ.missing" and f.grade == "pin"] == [
        "LE is driven by U1 from reset on"]
