"""REQ.value/switch (maker-coverage CK-30): no DC across a switch whose sides are both in a signal path – the pop."""

import pytest
from test_sim import simulate


def switched_signal(project, b_to):
    """SW8 (the example's button part, open in every scenario) between SIG_A, 10 kΩ from 3V3, and SIG_B, 10 kΩ from
    b_to – both nets marked signal."""
    project.use_library_part("C17414")
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "SW8", "type": "button", "lcsc": "C318884",
         "pins": {"1": "A", "2": "B (internal to A)", "3": "C", "4": "D (internal to C)"},
         "nc": ["2", "4"]},
        {"designator": "R8", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}},
        {"designator": "R9", "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}]
    project.net(g, "3V3")["pins"].append("R8.1")
    project.net(g, b_to)["pins"].append("R9.2")
    g["graph"]["nets"] += [{"name": "SIG_A", "pins": ["R8.2", "SW8.1"], "v": [0, 3.4], "signal": True},
                           {"name": "SIG_B", "pins": ["R9.1", "SW8.3"], "v": [0, 3.4], "signal": True}]
    project.save_graph(g)


def rows(out):
    return [c for c in out["checks"] if c["id"] == "REQ.value" and c["item"] == "SW8"]


@pytest.mark.ngspice
def test_a_dc_step_across_a_switch_in_a_signal_path(project):
    switched_signal(project, "GND")
    found = rows(simulate(project))
    assert found and {c["result"] for c in found} == {"fail"}
    assert found[0]["check"].startswith("DC across SW8 in the signal path (SIG_B 0 V, SIG_A 3.3 V)")
    assert found[0]["expected"] == "≤ 10 mV"


@pytest.mark.ngspice
def test_both_sides_at_one_level_pass(project):
    switched_signal(project, "3V3")
    found = rows(simulate(project))
    assert found and {c["result"] for c in found} == {"pass"}


@pytest.mark.ngspice
def test_nets_not_marked_as_signal_are_left_alone(project):
    switched_signal(project, "GND")
    g = project.graph()
    for n in g["graph"]["nets"]:
        n.pop("signal", None)
    project.save_graph(g)
    assert rows(simulate(project)) == []
