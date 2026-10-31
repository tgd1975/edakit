"""The library's drivers and transceivers in a graph: a winding on outputs that clamp it themselves needs no flyback
diode, on outputs without clamp diodes (the L298) it needs the bridge's diodes, not one across it; an unbiased RS-485
B line is told to take a pull-down."""

from helpers import check

from edakit import library
from edakit.design import Design


def add_part(project, key):
    project.save_part(key, library.entry(key))


def found(project, code):
    cfg = project.config()
    return [(f.grade, f.place, f.fix) for f in check(Design.from_config(cfg), cfg).findings if f.code == code]


def test_an_unbiased_rs485_b_line_is_told_to_take_a_pull_down(project):
    for key in ("C19738",):
        e = library.entry(key)
        assert e["pins"]["6"]["role"] == "rs485_a" and e["pins"]["7"]["role"] == "rs485_b"
    add_part(project, "C19738")
    g = project.graph()
    graph = g.get("graph", g)
    e = library.entry("C19738")
    graph["components"].append({"designator": "U9", "type": "ic", "lcsc": "C19738", "board": "main",
                                "pins": {n: p["name"] for n, p in e["pins"].items()},
                                "nc": [n for n in e["pins"] if n not in ("6", "7")]})
    graph["nets"] += [{"name": "RS_A", "pins": ["U9.6"], "v": [0, 5.5]}, {"name": "RS_B", "pins": ["U9.7"], "v": [0, 5.5]}]
    project.save_graph(g)
    fixes = {place: fix for grade, place, fix in found(project, "LVL.undefined") if grade == "open_drain"}
    assert fixes["RS_B"].startswith("a pull-down to ground") and fixes["RS_A"].startswith("a pull-up")


def winding_on(key, out_pins):
    """A design: library driver U9 (entry key) with a motor M9 between two of its outputs, nothing else."""
    import reference
    driver = library.entry(key)
    motor = dict(reference.MOTOR)
    parts = {key: driver, motor["lcsc"]: motor}
    graph = {"name": "t", "version": "1", "ground": "GND",
             "components": [{"designator": "U9", "type": "ic", "lcsc": key, "board": "main",
                             "pins": {n: p["name"] for n, p in driver["pins"].items()}},
                            {"designator": "M9", "type": "motor", "lcsc": motor["lcsc"], "board": "main",
                             "pins": {"1": "+", "2": "-"}}],
             "nets": [{"name": "MA", "pins": [f"U9.{out_pins[0]}", "M9.1"], "v": [0, 12]},
                      {"name": "MB", "pins": [f"U9.{out_pins[1]}", "M9.2"], "v": [0, 12]}]}
    return Design.from_data(graph, parts)


def flyback_findings(design):
    from edakit.engines.requires import flyback
    return [f.text for f in flyback(design)]


def test_outputs_that_clamp_themselves_need_no_flyback_diode():
    assert library.entry("C50506")["pins"]["2"]["clamp"] == "internal"       # DRV8833 AOUT1/AOUT2
    assert flyback_findings(winding_on("C50506", ("2", "4"))) == []
    assert flyback_findings(winding_on("C141517", ("1", "5"))) == []         # TB6612 AO1/AO2


def test_bridge_outputs_without_clamp_diodes_are_not_told_to_take_one_diode():
    assert library.entry("C19922")["pins"]["2"]["clamp"] == "none"           # L298 OUT1/OUT2
    assert flyback_findings(winding_on("C19922", ("2", "3"))) == []          # REQ.missing/clamp asks for the bridge's


def test_an_output_without_a_clamp_field_still_needs_the_diode():
    d = winding_on("C50506", ("2", "4"))
    for n in ("2", "4"):
        d.parts["C50506"]["pins"][n].pop("clamp")
    assert len(flyback_findings(d)) == 1
