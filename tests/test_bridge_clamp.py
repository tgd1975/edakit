"""REQ.missing/clamp (maker-coverage CK-15): an output without clamp diodes of its own (pin clamp = "none", the
L298's bridges – ST datasheet, section 3) that drives a winding or a connector needs a diode to the supply and one from
ground."""

from helpers import check
from reference import Project, add, wire

from edakit import schema
from edakit.design import Design

DIODE = "C8678"      # SS34 in the example's parts


def driver(p, key="C9100070"):
    p.save_part(key, {"lcsc": key, "mpn": "bridge driver without clamp diodes (test part)", "kind": "ic",
                      "verified": {"by": "test"},
                      "pins": {"1": {"name": "VS", "type": "power_in"}, "2": {"name": "GND", "type": "ground"},
                               "3": {"name": "OUT1", "type": "output", "clamp": "none"},
                               "4": {"name": "OUT2", "type": "output", "clamp": "none"}}})
    return key


def bridge(p, diodes=()):
    """U70's outputs OUT1/OUT2 on connector J70 (a motor off the board); diodes: [(des, anode net, cathode net)]."""
    key = driver(p)
    g = p.graph()
    add(g, "U70", "ic", key, {"1": "VS", "2": "GND", "3": "OUT1", "4": "OUT2"})
    add(g, "J70", "connector", "C131337", {"1": "1", "2": "2"}, bom=False)
    wire(g, "+5V", "U70.1")
    wire(g, "GND", "U70.2")
    wire(g, "M_A", "U70.3", "J70.1")
    wire(g, "M_B", "U70.4", "J70.2")
    for des, a, c in diodes:
        add(g, des, "diode", DIODE, {"1": "K", "2": "A"})
        wire(g, c, f"{des}.1")
        wire(g, a, f"{des}.2")
    p.save_graph(g)


def clamps(p):
    cfg = p.config()
    rep = check(Design.from_config(cfg), cfg)
    return sorted((f.place, f.severity) for f in rep.findings if f.code == "REQ.missing" and f.grade == "clamp")


def test_outputs_without_clamp_diodes_at_a_connector(tmp_path):
    p = Project.copy_of_example(tmp_path / "b")
    bridge(p)
    assert clamps(p) == [("U70.3", "warning"), ("U70.4", "warning")]


def test_four_diodes_quiet_it_and_one_missing_is_named(tmp_path):
    p = Project.copy_of_example(tmp_path / "b")
    bridge(p, [("D70", "M_A", "+5V"), ("D71", "GND", "M_A"), ("D72", "M_B", "+5V"), ("D73", "GND", "M_B")])
    assert clamps(p) == []
    p = Project.copy_of_example(tmp_path / "c")
    bridge(p, [("D70", "M_A", "+5V"), ("D71", "GND", "M_A"), ("D72", "M_B", "+5V")])
    assert clamps(p) == [("U70.4", "warning")]


def test_the_field_is_internal_or_none():
    entry = {"kind": "ic", "pins": {"1": {"name": "OUT", "type": "output", "clamp": "yes"}}}
    assert any("clamp" in t for t in schema.problems(entry))
    entry["pins"]["1"]["clamp"] = "internal"
    assert not [t for t in schema.problems(entry) if "clamp" in t]
