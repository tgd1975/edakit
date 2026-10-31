"""A block's own graph keys, optional parts and ports, accepts that name a place (handbook 14.5), and an accept on a net
or component keyed by "code place" (handbook 3)."""

import json

import pytest

from edakit import block
from edakit.findings import Finding, accepted_in_graph


def signals(project, *names):
    g = project.graph()
    for name, ref in (("SIG", "U1.10"), ("SIG2", "U1.11")):
        if name in names:
            project.free_pins(g, ref)
            g["graph"]["nets"].append({"name": name, "pins": [ref], "v": [0, 3.4]})
    project.save_graph(g)


def test_an_optional_part_is_left_out_and_only_an_optional_one(project):
    signals(project, "SIG")
    _, comps, *_ = block.add(project.config(), "nmos-switch", "SW", {"in": "SIG", "vplus": "+5V"}, without=["D1"])
    assert not [c for c in comps if c["type"] == "diode"]
    g = project.graph()["graph"]
    assert not [r for n in g["nets"] for r in n["pins"] if r.split(".")[0] in {c["designator"] for c in comps}
                and r.split(".")[0].startswith("D")]
    with pytest.raises(block.BlockError, match="Q1 is no optional part"):
        block.add(project.config(), "nmos-switch", "SW2", {"in": "SIG", "vplus": "+5V"}, without=["Q1"])


def test_an_unconnected_optional_port_puts_its_lone_pin_into_nc(project):
    """addressable-led-input without R3: dout, left open, is R1's pin 2 alone – it goes into R1's nc, no net of one
    pin (STRUCT.net)."""
    signals(project, "SIG")
    _, comps, new_nets, *_ = block.add(project.config(), "addressable-led-input", "PIX", {"in": "SIG", "vcc": "+5V"},
                                      without=["R3"])
    r1 = next(c for c in comps if "330" in c["label"])
    assert r1["nc"] == ["2"] and not [n for n in new_nets if n["name"] == "PIX_DOUT"]
    signals(project)
    _, comps, new_nets, *_ = block.add(project.config(), "addressable-led-input", "PIX2", {"in": "SIG", "vcc": "+5V"})
    assert [n for n in new_nets if n["name"] == "PIX2_DOUT"]                 # with R3 the port keeps its net


def test_a_block_brings_its_grounds(project):
    """lipo-charger: the cell's-minus net joins the project's grounds – the DW01A's own ground (Rev B p. 3)."""
    block.add(project.config(), "lipo-charger", "CHG", {"vbus": "+5V"})
    assert "CHG_CELL_N" in project.graph()["graph"]["grounds"]
    b = block.load("lipo-charger")
    assert not [n for n in b["nets"] if n["name"] in ("cell_n", "vcc_dw") and n.get("accept")]


def test_an_accept_naming_a_place_follows_the_renamed_designator(project, tmp_path):
    f = tmp_path / "b.json"
    b = block.load("nmos-switch")
    load = next(n for n in b["nets"] if n["name"] == "load")
    load["accept"] = {"LIM.v D1": "test: only the diode's finding", "LIM.i": "test: every finding of the code"}
    f.write_text(json.dumps(b), encoding="utf-8")
    signals(project, "SIG")
    _, comps, new_nets, *_ = block.add(project.config(), None, "SW", {"in": "SIG", "vplus": "+5V"}, file=str(f))
    diode = next(c["designator"] for c in comps if c["type"] == "diode")
    acc = next(n for n in new_nets if n["name"] == "SW_LOAD")["accept"]
    assert acc == {f"LIM.v {diode}": "test: only the diode's finding", "LIM.i": "test: every finding of the code"}


def test_a_net_accept_keyed_by_place_takes_only_that_finding():
    graph = {"nets": [{"name": "VBUS", "pins": ["J1.1", "U1.5"], "accept": {"LIM.v J1": "rated 5.0 V, USB-C 5.5 V"}}],
             "components": []}
    at_j1 = Finding("LIM.v", "G", "J1.1", "J1.1: 5.5 V", on=(("net", "VBUS"),))
    at_u1 = Finding("LIM.v", "G", "U1.5", "U1.5: 5.5 V", on=(("net", "VBUS"),))
    assert accepted_in_graph(at_j1, graph) == "rated 5.0 V, USB-C 5.5 V"
    assert accepted_in_graph(at_u1, graph) is None
    graph["nets"][0]["accept"] = {"LIM.v": "every one"}
    assert accepted_in_graph(at_u1, graph) == "every one"
    graph["nets"][0]["accept"] = {"LIM.v U1.5": "the pin only"}
    assert accepted_in_graph(at_u1, graph) == "the pin only" and accepted_in_graph(at_j1, graph) is None
