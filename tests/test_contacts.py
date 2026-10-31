"""Contact fields (handbook 4.1): what a closed contact carries (i_contact_max_a), what it breaks when it opens
(i_switch_max_a, LIM.i/switching) and the least current it needs to close reliably (min_load_a, REQ.value/min_load)."""

import json

import pytest
from test_sim import simulate

from edakit.design import Design
from edakit.engines.quantities import fuse_currents


def resistor(project, key, ohm):
    """A test resistor entry of `ohm`, 1 W – the example's 10 kΩ with another value."""
    data = json.loads((project.root / "hardware" / "parts" / "C17414.json").read_text())
    data.update(lcsc=key, mpn=key)
    data["values"]["value_ohm"] = float(ohm)
    data["limits"]["p_max_w"] = 1.0
    project.save_part(key, data)


def load_on(project, ohm, b_to="GND"):
    """The library's DIP switch C126848 (25 mA 24 V DC for switching) as SW9, closed in every scenario, from 3V3
    through R9 (`ohm`) to b_to."""
    project.use_library_part("C126848")
    resistor(project, "R-TEST", ohm)
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "SW9", "type": "switch", "lcsc": "C126848", "pins": {"1": "A1", "2": "B1"}},
        {"designator": "R9", "type": "resistor", "lcsc": "R-TEST", "pins": {"1": "1", "2": "2"}}]
    project.net(g, "3V3")["pins"].append("SW9.1")
    project.net(g, b_to)["pins"].append("R9.2")
    g["graph"]["nets"].append({"name": "SW_R", "pins": ["SW9.2", "R9.1"], "v": [0, 3.4]})
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    for load in sim["loads"].values():
        load["dip_closed"] = {"SW9": [1]}
    return sim


def move_r9(project, b_to):
    g = project.graph()
    for n in g["graph"]["nets"]:
        if "R9.2" in n["pins"]:
            n["pins"].remove("R9.2")
    project.net(g, b_to)["pins"].append("R9.2")
    project.save_graph(g)


def rows(out, item, how):
    return [c for c in out["checks"] if c["item"] == item and c["check"].startswith(how)]


@pytest.mark.ngspice
def test_a_closed_contact_is_held_to_what_it_may_break(project):
    sim = load_on(project, 33)                                          # 100 mA through a 25 mA switching rating
    over = rows(simulate(project, sim), "SW9", "current it breaks when it opens")
    assert over and {c["result"] for c in over} == {"fail"} and {c["id"] for c in over} == {"LIM.i"}
    assert "of 25 mA" in over[0]["expected"]                          # derated as every current
    resistor(project, "R-TEST", 1000)                                   # 3.3 mA
    fine = rows(simulate(project, sim), "SW9", "current it breaks when it opens")
    assert fine and {c["result"] for c in fine} == {"pass"}


@pytest.mark.ngspice
def test_the_switching_rating_is_a_warning(project):
    from edakit import catalog
    from edakit.sim import run as simrun
    sim = load_on(project, 33)
    out = simrun.run_all(Design.from_config(project.config()), sim)
    found = [f for f in out["findings"] if f["place"] == "SW9" and f["code"] == "LIM.i"]
    assert found and {(f.get("grade"), f.get("severity")) for f in found} == {("switching", "warning")}
    assert catalog.code("LIM.i")["grades"]["switching"] == "warning"


@pytest.mark.ngspice
def test_a_closed_contact_below_its_minimum_load(project):
    """SW9 from 3V3 through 10 kΩ back to 3V3: no current – below the 10 µA a test entry asks for; to GND 330 µA."""
    sim = load_on(project, 10000, b_to="3V3")
    entry = json.loads((project.root / "hardware" / "parts" / "C126848.json").read_text())
    entry.setdefault("values", {})["min_load_a"] = 1e-05
    project.save_part("C126848", entry)
    low = rows(simulate(project, sim), "SW9", "current through a closed contact of SW9")
    assert low and {c["result"] for c in low} == {"fail"} and {c["id"] for c in low} == {"REQ.value"}
    assert low[0]["expected"] == "≥ 10 µA"
    move_r9(project, "GND")
    ok = rows(simulate(project, sim), "SW9", "current through a closed contact of SW9")
    assert ok and {c["result"] for c in ok} == {"pass"}
    entry["values"].pop("min_load_a")
    project.save_part("C126848", entry)
    assert rows(simulate(project, sim), "SW9", "current through a closed contact of SW9") == []


def supply_connector(project, contact_a, vin_pins=("1",)):
    """J1 (the example's supply connector) with i_contact_max_a; with more pins on VIN, the supply shares them."""
    entry = json.loads((project.root / "hardware" / "parts" / "C131337.json").read_text())
    entry.setdefault("limits", {})["i_contact_max_a"] = contact_a
    for num in vin_pins[1:]:
        entry["pins"][num] = dict(entry["pins"]["1"], name=f"VIN{num}")
    project.save_part("C131337", entry)
    g = project.graph()
    j1 = project.comp(g, "J1")
    for num in vin_pins[1:]:
        j1["pins"][num] = num
        project.net(g, "VIN")["pins"].append(f"J1.{num}")
    project.save_graph(g)


@pytest.mark.ngspice
def test_a_supply_at_a_connector_is_held_to_its_rating_per_contact(project):
    supply_connector(project, 0.001)
    one = rows(simulate(project), "J1", "current per contact")
    assert one and "fail" in {c["result"] for c in one} and {c["id"] for c in one} == {"LIM.i"}
    supply_connector(project, 0.001, vin_pins=("1", "3"))
    two = rows(simulate(project), "J1", "current per contact (2 contacts on the supply's net)")
    assert two and len(two) == len(one)


def test_a_fuse_is_held_to_a_connectors_rating_per_contact(project):
    """What a fuse lets pass against i_contact_max_a as against i_max_a (LIM.i, handbook 5.3): F1 holds 1.5 A, J1
    carries 1 A per contact."""
    from test_checks import fused_input
    fused_input(project)
    entry = json.loads((project.root / "hardware" / "parts" / "C131337.json").read_text())
    entry["limits"].pop("i_max_a")
    project.save_part("C131337", entry)
    assert [q for q in fuse_currents(Design.from_config(project.config())) if q.place == "J1"] == []
    entry["limits"]["i_contact_max_a"] = 1.0
    project.save_part("C131337", entry)
    qs = [q for q in fuse_currents(Design.from_config(project.config())) if q.place == "J1"]
    assert qs and {q.name for q in qs} == {"i_contact"}
    from edakit.engines.limits import judge_all
    d = Design.from_config(project.config())
    assert [f.text for f in judge_all(d, qs) if f.grade != "margin"] == [
        "F1: holds 1.5 A, above the 1 A of J1 – an overload in between never trips it"]


@pytest.mark.ngspice
def test_a_contact_in_a_signal_path_is_rated_for_signal_currents(project):
    """SW8 between two signal nets (test_switch_dc): an entry whose minimum load is 1 mA is no contact for a signal
    path; 10 µA is (maker-coverage CK-30). The DC through it is not compared – there is none by design."""
    from test_switch_dc import switched_signal
    switched_signal(project, "3V3")
    entry = json.loads((project.root / "hardware" / "parts" / "C318884.json").read_text())

    def rated(min_load_a):
        entry.setdefault("values", {})["min_load_a"] = min_load_a
        project.save_part("C318884", entry)
        out = simulate(project)
        assert not rows(out, "SW8", "current through a closed contact")
        return {c["result"] for c in rows(out, "SW8", "minimum load of SW8's contacts in the signal path")}
    assert rated(1e-3) == {"fail"}
    assert rated(1e-5) == {"pass"}
