"""Polarized capacitors (maker-coverage CK-7): LIM.v holds the reverse voltage across them to vr_max_v in stages G and
E, and PATH.reverse no longer counts them as harmless – both with the grade polarized, warnings while new."""

import shutil

import pytest
from test_sim import simulate

from edakit import engines
from edakit.design import Design


def electrolytic(project, plus="1", vr_max=0.5):
    """C2 (C45783, on +5V and GND, pin 1 on +5V) as a polarized capacitor with its plus at `plus` – values for the test,
    not from its datasheet."""
    part = project.part("C45783")
    part["values"]["polarized"] = True
    for num in part["pins"]:
        part["pins"][num]["role"] = "plus" if num == plus else "minus"
    if vr_max is not None:
        part["limits"]["vr_max_v"] = vr_max
    project.save_part("C45783", part)


def findings(project, code):
    cfg = project.config()
    return [(f.text, f.grade) for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == code
            and f.grade == "polarized"]


def test_the_right_way_round_passes(project):
    electrolytic(project)
    assert findings(project, "LIM.v") == []


def test_turned_round_it_is_reverse_biased_in_the_graph(project):
    electrolytic(project, plus="2")                                       # plus on GND
    assert findings(project, "LIM.v") == [("C2: reverse up to 5.5 V, allowed 0.5 V", "polarized")]


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_turned_round_it_is_reverse_biased_in_the_simulation(project):
    electrolytic(project, plus="2")
    bad = [c for c in simulate(project)["checks"] if c["item"] == "C2" and c["check"] == "reverse voltage"
           and c["result"] == "warn"]                                    # LIM.v/polarized, a warning
    assert bad and all(c["id"] == "LIM.v" for c in bad)


def test_without_its_reverse_limit_it_is_a_gap(project):
    from edakit.engines.coverage import coverage
    electrolytic(project, vr_max=None)
    d = Design.from_config(project.config())
    assert "LIM.v: C2 – no vr_max_v – its reverse voltage is not held to a limit (C45783)" in [
        g.line() for g in coverage(d)]


def test_a_reversed_source_reaching_it(project):
    """C2 moved to VIN, in front of the reverse diode D1: a reversed J1 reverse-biases it."""
    electrolytic(project)
    g = project.graph()
    project.net(g, "+5V")["pins"].remove("C2.1")
    project.net(g, "VIN")["pins"].append("C2.1")
    project.save_graph(g)
    assert findings(project, "PATH.reverse") == [
        ("C2.1 on VIN: a reversed source reaches the polarized capacitor C2 – it is reverse biased", "polarized")]
