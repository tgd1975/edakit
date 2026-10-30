"""The engines of the restructuring on small synthetic circuits (rules-at-scale.md, section 7): every relation fires on
its fault and on nothing else; LIMITS and PATHS hold their properties at random values; every finding names a code of
the catalog, a declared grade, a place and what was found. Parity with the checks of before: tests/parity.py."""

import random

import pytest

from edakit import catalog, engines
from edakit.design import Design
from edakit.engines import levels, limits, paths, requires
from edakit.engines.quantities import Limit, Quantity


def part(kind, pins, **kw):
    return {"kind": kind, "pins": pins, "limits": kw.pop("limits", {}), "values": kw.pop("values", {}), **kw}


def P(name, type_="passive", role=None, **kw):
    return {"name": name, "type": type_, **({"role": role} if role else {}), **kw}


def design(comps, nets, parts, **graph):
    g = {"components": [{"designator": d, "lcsc": key, "pins": {n: p["name"] for n, p in parts[key]["pins"].items()}}
                        for d, key in comps.items()],
         "nets": [{"name": n, "v": v, "pins": pins} for n, (v, pins) in nets.items()], **graph}
    return Design.from_data(g, parts)


CAP = part("capacitor", {"1": P("1", role="1"), "2": P("2", role="2")}, limits={"v_max_v": 10})
RES = part("resistor", {"1": P("1"), "2": P("2")}, values={"value_ohm": 10000})
IC = part("ic", {"1": P("VDD", "power_in"), "2": P("GND", "ground"), "3": P("IN", "input", v_max_v=3.6),
                 "4": P("OUT", "output")})
HOLDER = part("battery_holder", {"1": P("+", role="plus"), "2": P("-", role="minus")})
DIODE = part("diode", {"1": P("K", role="cathode"), "2": P("A", role="anode")}, limits={"vr_max_v": 40})


def codes(findings):
    return sorted(f.code for f in findings)


# --- LIMITS -----------------------------------------------------------------------------------------------------------
def test_limits_never_fire_inside_and_always_outside():
    rng = random.Random(7)
    for _ in range(2000):
        lim = rng.uniform(0.1, 100)
        factor, derate = rng.choice([1, 1.5]), rng.choice([1, 0.67, 0.8])
        value = rng.uniform(0, 2 * lim)
        q = Quantity("X1", "v", value)
        found = limits.judge(q, [Limit(max=lim, factor=factor, derate=derate, source="s")])
        assert bool(found) == (value * factor > lim * derate)
        lo = rng.uniform(-2 * lim, 2 * lim)
        found = limits.judge(Quantity("X1", "v", None, lo=lo), [Limit(min=-lim, source="s")])
        assert bool(found) == (lo < -lim)


def test_a_margin_is_dropped_where_the_limit_is_exceeded():
    hard = Quantity("J1", "i", 3.0, unit="A", limits=[Limit(max=2, source="s")], on=(("component", "F1"),))
    soft = Quantity("J1", "i", 4.0, unit="A", grade="margin", limits=[Limit(max=2, source="s")],
                    on=(("component", "F1"),))
    found = limits.judge_all(Design.from_data({"components": [], "nets": []}, {}), [hard, soft])
    assert [f.grade for f in found] == [""]
    assert [f.grade for f in limits.judge_all(Design.from_data({"components": [], "nets": []}, {}), [soft])] == ["margin"]


def test_limits_from_entry_pin_and_pin_type():
    d = design({"C1": "C", "U1": "U"}, {"VIN": ([0, 7.5], ["C1.1", "U1.3"]), "GND": ([0, 0], ["C1.2", "U1.2"]),
                                         "V": ([0, 3.3], ["U1.1", "U1.4"])}, {"C": CAP, "U": IC})
    found = limits.run(engines.context(d))
    assert codes(found) == ["LIM.v", "LIM.v"]
    by = {f.place: f for f in found}
    assert by["C1"].text == "C1: up to 7.5 V, rated 10 V (needs ×1.5)" and by["C1"].source == "v_max_v of C"
    assert by["U1.3"].source == "v_max_v of pin 3 (IN) of U" and by["U1.3"].stage == "G"


def test_a_negative_net_on_an_active_pin():
    d = design({"U1": "U"}, {"N": ([-1, 0], ["U1.3", "U1.4"]), "GND": ([0, 0], ["U1.2"]), "V": ([0, 3.3], ["U1.1"])},
               {"U": IC})
    found = [f for f in limits.run(engines.context(d)) if f.text.startswith("N down to -1 V")]
    assert {f.place for f in found} == {"U1.3", "U1.4"}


# --- LEVELS -----------------------------------------------------------------------------------------------------------
def test_levels_floating_input_contention_and_strap():
    mcu = part("module", {"1": P("GP0", "bidirectional", role="gpio"), "2": P("GPIO12", "bidirectional", strap="low"),
                          "3": P("GND", "ground"), "4": P("3V3", "power_output")})
    d = design({"U1": "M", "U2": "U", "U3": "U", "R1": "R"},
               {"A": ([0, 3.3], ["U1.1", "U2.3"]), "B": ([0, 3.3], ["U2.4", "U3.4"]),
                "S": ([0, 3.3], ["U1.2", "R1.1"]), "3V3": ([0, 3.3], ["U1.4", "R1.2", "U2.1", "U3.1"]),
                "GND": ([0, 0], ["U1.3", "U2.2", "U3.2"]), "C": ([0, 3.3], ["U3.3"])}, {"M": mcu, "U": IC, "R": RES})
    found = levels.run(engines.context(d))
    by = {(f.code, f.place) for f in found}
    assert ("LVL.undefined", "A") in by and ("LVL.undefined", "C") in by
    assert ("LVL.contention", "B") in by and ("LVL.boot", "U1.2") in by
    assert len(found) == 4


# --- REQUIRES ---------------------------------------------------------------------------------------------------------
def test_requires_decoupling_and_its_switch():
    d = design({"U1": "U"}, {"V": ([0, 3.3], ["U1.1", "U1.4"]), "GND": ([0, 0], ["U1.2", "U1.3"])}, {"U": IC})
    assert codes(requires.decoupling(d)) == ["REQ.missing"]
    d.parts["U"] = {**IC, "needs": {"decoupling": False}}
    assert requires.decoupling(d) == []


def test_requires_i2c_pull_up_window():
    sda = part("ic", {"1": P("VDD", "power_in"), "2": P("GND", "ground"), "3": P("SDA", "bidirectional", role="sda")})
    for ohm_, want in ((None, ["REQ.missing"]), (4700, []), (47000, ["REQ.value"]), (300, ["REQ.value"])):
        comps, nets = {"U1": "S"}, {"V": ([0, 3.3], ["U1.1"]), "GND": ([0, 0], ["U1.2"]), "SDA": ([0, 3.3], ["U1.3"])}
        parts = {"S": sda}
        if ohm_:
            comps["R1"], parts["R"] = "R", {**RES, "values": {"value_ohm": ohm_}}
            nets["SDA"][1].append("R1.1")
            nets["V"][1].append("R1.2")
        assert codes(requires.i2c(design(comps, nets, parts))) == want, ohm_


# --- PATHS ------------------------------------------------------------------------------------------------------------
def test_reverse_is_blocked_by_a_series_diode_and_never_leaks():
    chain = {"BT1": "H", "D1": "D", "U1": "U"}
    nets = {"BAT": ([0, 3], ["BT1.1", "D1.2"]), "VCC": ([0, 3], ["D1.1", "U1.1"]), "GND": ([0, 0], ["BT1.2", "U1.2"]),
            "X": ([0, 3], ["U1.3", "U1.4"])}
    d = design(chain, nets, {"H": HOLDER, "D": DIODE, "U": IC})
    assert paths.reverse(d, d) == []
    nets["BAT"] = ([0, 3], ["BT1.1", "D1.1", "U1.1"])          # diode turned round: the IC is on the source side
    nets["VCC"] = ([0, 3], ["D1.2"])
    found = paths.reverse(design(chain, nets, {"H": HOLDER, "D": DIODE, "U": IC}), d)
    assert [f.place for f in found] == ["D1.1", "U1.1"]       # a cathode on the reversed side blocks nothing
    assert {f.code for f in found} == {"PATH.reverse"}


def test_a_pass_through_set_reaches_exactly_its_closure():
    rng = random.Random(3)
    for _ in range(50):
        n = rng.randint(2, 8)
        links = [(i, rng.randrange(n)) for i in range(n) if rng.random() < 0.6]
        comps = {"BT1": "H", **{f"F{i}": "F" for i, _ in enumerate(links)}}
        nets = {f"N{i}": [] for i in range(n)}
        nets["N0"].append("BT1.1")
        nets.setdefault("GND", []).append("BT1.2")
        for k, (a, b) in enumerate(links):
            nets[f"N{a}"].append(f"F{k}.1")
            nets[f"N{b}"].append(f"F{k}.2")
        fuse = part("fuse", {"1": P("1"), "2": P("2")})
        d = design(comps, {k: ([0, 3], v) for k, v in nets.items() if v}, {"H": HOLDER, "F": fuse})
        seen, todo = {0}, [0]
        while todo:
            x = todo.pop()
            for a, b in links:
                for p, q in ((a, b), (b, a)):
                    if p == x and q not in seen:
                        seen.add(q)
                        todo.append(q)
        d.parts["X"] = IC
        assert paths.reverse(d, d) == []          # only holders and fuses: nothing to protect
        reached = {net for net in d.nets if net != "GND"} & {f"N{i}" for i in seen}
        assert reached == {f"N{i}" for i in seen if nets[f"N{i}"]}


def test_unfed_and_ground_pins():
    d = design({"U1": "U"}, {"V": ([0, 3.3], ["U1.1"]), "G2": ([0, 0], ["U1.2"]), "X": ([0, 3.3], ["U1.3", "U1.4"])},
               {"U": IC})
    found = paths.supply(d)
    assert codes(found) == ["PATH.ground", "PATH.unfed"]


# --- every finding ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("fault", ["clean", "floating", "overvoltage"])
def test_every_finding_is_well_formed(project, fault):
    g = project.graph()
    if fault == "floating":
        project.net(g, "LED_OE")["pins"].remove("R2.2")
        project.net(g, "3V3")["pins"].remove("R2.1")
        g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "R2"]
    if fault == "overvoltage":
        project.net(g, "BTN")["v"] = [0, 5.0]
    project.save_graph(g)
    cfg = project.config()
    rep = engines.run(Design.from_config(cfg), cfg)
    for f in rep.findings:
        e = catalog.code(f.code)
        assert e, f.code
        assert not f.grade or f.grade in (e.get("grades") or {}), (f.code, f.grade)
        assert f.stage in catalog.STAGES and f.place and f.text and f.severity in catalog.SEVERITIES
        if f.code.startswith("LIM."):
            assert f.source, f


def test_no_check_id_of_before_is_left_in_the_code():
    """Every finding, row and accept key in edakit names a code of the catalog; the check IDs of before stay only where
    the conversion reads them (convert.py, the catalog's replaces) – the manual checks M-… are no codes."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "edakit"
    left = {str(p.relative_to(root)): ids for p in root.rglob("*.py") if p.name != "convert.py"
            if (ids := set(re.findall(r'"([PGESLFH]-\d+)"', p.read_text(encoding="utf-8"))))}
    assert left == {}


def test_recorded_classes_and_grades():
    from edakit.engines.project import Recorder
    rec = Recorder()
    rec.add("pending", "PARTS.fact", "D1 C1: plated holes but no lead in the parts entry", grade="lead")
    rec.warnings.append(("PARTS.stock", "U1: thin stock"))
    rec.add("warning", "PARTS.verified", "X1: neither an LCSC part nor an EasyEDA device", "a test pad", grade="device")
    rec.drafts.append(("DOCS.evidence", "R-3: no evidence"))
    rec.error("GEO.hole", "J1 (pads 1): the hole is too small", {"GEO.hole": "a press-fit pin"})
    got = [(f.code, f.grade, f.place, f.accepted) for f in rec.findings]
    assert got == [("PARTS.fact", "lead", "D1", ""), ("PARTS.stock", "margin", "U1", ""),
                   ("PARTS.verified", "device", "X1", "a test pad"), ("DOCS.evidence", "draft", "R-3", ""),
                   ("GEO.hole", "", "J1", "a press-fit pin")]
