"""Stage E with the routed copper: tracks and vias of chosen nets as resistors between the pads (sim.json copper)."""

import json
import shutil

import pytest

from edakit import cli
from edakit.design import Design
from edakit.sim import copper, netlist
from edakit.sim import run as simrun
from test_sim import failing

pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

MIL = 1 / 0.0254
RANGE = "net voltage inside the declared range"
LOADS = ["U1.39", "C2.1"] + [f"D{i}.1" for i in range(2, 10)]      # every +5V pin but D1's


def pad(ref, x, y, net, layer=1, size=30):
    des, num = ref.split(".")
    return {"id": f"{des}e{num}", "ref": des, "num": num, "net": net, "x": x, "y": y, "rot": 0, "layer": layer,
            "shape": ["RECT", size, size], "hole": None, "hole_off": [0, 0]}


def wire(layer, width_mm, points):
    return f"(wire (path {layer} {width_mm * MIL * 100:.1f} " + " ".join(f"{x * 100:.1f} {y * 100:.1f}" for x, y in points) \
        + "))"


def routed(project, nets, vias=None):
    """Board json and session of `edakit route` in the project's artifacts: nets = {net: (pads, wires)} in mil."""
    cfg = project.config()
    pads = [p for ps, _ in nets.values() for p in ps]
    cfg.artifact("route", "main_board.json").write_text(json.dumps({"pcb": "main", "components": [], "pads": pads,
                                                                     "outlines": []}))
    body = "\n".join(f'  (net "{n}" ' + " ".join(ws) + " ".join(f"(via via24 {x * 100:.1f} {y * 100:.1f})"
                                                                for x, y in (vias or {}).get(n, [])) + ")"
                     for n, (_, ws) in nets.items())
    cfg.artifact("route", "main.ses").write_text(f"(session t (routes (resolution mil 100) (parser) (network_out\n{body}\n)))")
    return cfg


def vin_track():
    """VIN: 100 mm × 0.25 mm on TOP from J1.1 to D1.2."""
    return [pad("J1.1", 0, -1000, "VIN"), pad("D1.2", 100 * MIL, -1000, "VIN")], \
        [wire("TOP", 0.25, [(0, -1000), (100 * MIL, -1000)])]


def plus5v_track(layer="TOP"):
    """+5V: 200 mm × 0.15 mm from D1.1 to the loads, which sit 50 mil apart on the same track."""
    far = 200 * MIL
    pads = [pad("D1.1", 0, 0, "+5V")] + [pad(ref, far + 50 * k, 0, "+5V") for k, ref in enumerate(LOADS)]
    return pads, [wire(layer, 0.15, [(0, 0)] + [(far + 50 * k, 0) for k in range(len(LOADS))])]


def sim_config(project, **copper_spec):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    if copper_spec:
        sim["copper"] = copper_spec
    return sim


def simulate(project, sim, cfg=None):
    cfg = cfg or project.config()
    routing = copper.load_routing(cfg) if sim.get("copper") else None
    return simrun.run_all(Design.from_config(cfg), sim, routing=routing)


def narrow_5v(project):
    g = project.graph()
    project.net(g, "+5V")["v"] = [4.45, 5.5]               # tolerance 0.05 V: 4.40 V at the lowest pin
    project.save_graph(g)


def test_a_track_is_a_resistor_between_its_pads(project):
    cfg = routed(project, {"VIN": vin_track()})
    design = Design.from_config(cfg)
    sim = sim_config(project, nets=["VIN"])
    cu = copper.annotate(design, sim, copper.load_routing(cfg))
    assert cu["notes"] == []
    (_, a, b, r), = cu["elements"]
    assert abs(r / (0.0172 * 0.1 / (0.25 * 0.035)) - 1) < 1e-4            # ρ·L/(w·t) = 0.1966 Ω
    j1, d1 = cu["pads"]["J1.1"], cu["pads"]["D1.2"]
    assert {a, b} == {j1, d1} and cu["nets"]["VIN"] == sorted([j1, d1])
    sc = next(s for s in simrun.scenarios(sim) if s["name"] == "usb-min/all_on/vf-max")
    text, meta = netlist.build(design, sim, sc)
    res = simrun.ngspice(text)
    i = -res[meta["sources"]["J1"]["branch"]]
    assert abs((res[j1] - res[d1]) - i * r) <= 0.01 * i * r                  # I × R within 1 %
    assert f"R_J1_SRC x_j1_src {j1} " in text and f"D_D1 {d1} n__5v " in text


def test_the_drop_reaches_the_far_pins(project):
    narrow_5v(project)
    cfg = routed(project, {"+5V": plus5v_track()})
    assert not failing(simulate(project, sim_config(project), cfg))                      # 4.443 V: passes
    out = simulate(project, sim_config(project, nets=["+5V"]), cfg)
    bad = failing(out)
    assert {(c["id"], c["item"], c["check"]) for c in bad} == {("LIM.declared", "+5V", RANGE)}
    low = next(c for c in bad if c["scenario"] == "usb-min/all_on/vf-max")
    lo, hi = (float(x.split(" V")[0]) for x in low["actual"].split(" … "))
    assert 4.35 < lo < 4.38 and 4.43 < hi < 4.45                              # about 4.37 V at the far pins
    assert "(D9.1)" in low["actual"] and "(D1.1)" in low["actual"]
    assert {c["scenario"].split("/")[0] for c in bad} == {"usb-min"}
    row = next(s for s in out["scenarios"] if s["name"] == "usb-min/all_on/vf-max")
    assert abs(row["nets"]["+5V"] - lo) < 1e-3                                 # the report: the lowest pin
    assert not [c for c in out["checks"] if c["id"] == "SIM.converge" and c["result"] != "pass"]
    u1 = next(c for c in out["checks"] if c["item"] == "U1" and c["check"] == "supply voltage"
              and c["scenario"] == "usb-min/all_on/vf-max")
    assert u1["actual"].startswith("4.3")                                     # the MCU at its own pin


def test_sim_and_gate_read_the_routing(project, capsys):
    narrow_5v(project)
    routed(project, {"+5V": plus5v_track()})
    (project.root / "hardware" / "sim.json").write_text(json.dumps(sim_config(project, nets=["+5V"])))
    toml = str(project.root / "edakit.toml")
    assert cli.main(["sim", "--config", toml]) == 2
    assert "net voltage inside the declared range: 4.365 V (D9.1) … 4.442 V (D1.1)" in capsys.readouterr().out
    assert cli.main(["gate", "--config", toml]) == 2
    protocol = next((project.root / "build" / "release").glob("*/protocol.md")).read_text()
    assert "| +5V | net voltage inside the declared range | 4.365 V (D9.1) … 4.442 V (D1.1) |" in protocol


def test_net_currents_stay_on_the_net(project):
    cfg = routed(project, {"+5V": plus5v_track()})
    before = simulate(project, sim_config(project), cfg)["net_currents"]
    after = simulate(project, sim_config(project, nets=["+5V"]), cfg)["net_currents"]
    assert set(after) == set(before)
    assert abs(after["+5V"]["i_max_a"] - before["+5V"]["i_max_a"]) < 0.005


def test_a_pour_counts_as_ideal(project):
    narrow_5v(project)
    board = project.root / "hardware" / "boards" / "main.toml"
    board.write_text(board.read_text() + '\n[[pours]]\nnet = "+5V"\nlayers = ["TOP"]\n')
    cfg = routed(project, {"+5V": plus5v_track()})
    out = simulate(project, sim_config(project, nets=["+5V"]), cfg)
    assert not failing(out)
    pads, wires = plus5v_track("BOTTOM")                                     # the same track on the other layer
    for p in pads:
        p["layer"] = 2
    cfg = routed(project, {"+5V": (pads, wires)})
    assert failing(simulate(project, sim_config(project, nets=["+5V"]), cfg))


def test_a_via_joins_the_layers(project):
    pads, _ = vin_track()
    half = 50 * MIL
    wires = [wire("TOP", 0.25, [(0, -1000), (half, -1000)]), wire("BOTTOM", 0.25, [(half, -1000), (100 * MIL, -1000)])]
    pads[1]["layer"] = 12                                                     # D1.2 through-hole: both layers
    cfg = routed(project, {"VIN": (pads, wires)}, vias={"VIN": [(half, -1000)]})
    cu = copper.annotate(Design.from_config(cfg), sim_config(project, nets=["VIN"], via_ohm=0.002),
                         copper.load_routing(cfg))
    assert cu["notes"] == [] and sorted(round(r, 4) for *_, r in cu["elements"]) == [0.002, 0.0983, 0.0983]


def test_a_net_without_routing_stays_ideal(project):
    sim = sim_config(project, nets=["+5V"])
    out = simulate(project, sim)
    notes = [c for c in out["checks"] if c["id"] == "SIM.copper" and c["result"] == "info"]
    assert [(c["scenario"], c["item"], c["check"]) for c in notes] == [("copper", "+5V", "copper not annotated")]
    assert "no routing of board main" in notes[0]["actual"]
    plain = simulate(project, sim_config(project))
    assert [c for c in out["checks"] if c not in notes] == plain["checks"]


def test_sim_names_a_net_it_could_not_annotate(project, capsys):
    (project.root / "hardware" / "sim.json").write_text(json.dumps(sim_config(project, nets=["+5V"])))
    assert cli.main(["sim", "--config", str(project.root / "edakit.toml")]) == 0
    assert "INFO  E-1 copper                         +5V          copper not annotated: no routing of board main" \
        in capsys.readouterr().out
    assert not (project.root / "build" / "edakit" / "route").exists()        # reading the routing creates nothing


def test_an_open_net_stays_ideal(project):
    pads, wires = plus5v_track()
    cfg = routed(project, {"+5V": (pads, [wire("TOP", 0.15, [(0, 0), (100 * MIL, 0)])])})   # ends short of the loads
    out = simulate(project, sim_config(project, nets=["+5V"]), cfg)
    note, = [c for c in out["checks"] if c["result"] == "info" and c["id"] == "SIM.copper"]
    assert "not connected" in note["actual"] and "U1.39" in note["actual"]
    assert not failing(out)


@pytest.mark.parametrize("spec,match", [
    ({"nets": ["NOPE"]}, "copper: NOPE is no net"),
    ({"nets": ["GND"]}, "copper: GND is the ground net"),
    ({"nets": ["+5V"], "oz": 0}, "copper: oz"),
    ({"nets": ["+5V"], "via_ohm": -1}, "copper: via_ohm"),
    ({"nets": ["+5V"], "width": 1}, "copper: width"),
    ({"nets": "+5V"}, "copper: nets"),
])
def test_copper_says_what_is_wrong(project, spec, match):
    sim = sim_config(project)
    sim["copper"] = spec
    with pytest.raises(simrun.SimError, match=match):
        simulate(project, sim)
