"""Source models of the audio band with the makers' values (maker-coverage FT-18, rules-at-scale.md decision 20;
sim/ac.py, catalog/tables/audio_sources.toml): a pickup named by its row – the maker's DC resistance, the project's
inductance where the maker states none –, a piezo disc behind its capacitance, an electret capsule as a current source
into its load resistor, and a cable's capacitance per metre on the instrument input (the loading of CK-27).

The circuit is the guitar reference (tests/reference.py): the jack J20 on GTR_IN, R20 to VREF as the input's bias,
U20 a follower, C22 / R24 onto BUF_OUT – flat from a few hertz on. The inductances and the pickup's own capacitance
are values chosen for the test, not a product's: no maker reachable states either."""

import math
import shutil
import tempfile

import pytest
from reference import _resistor_to, add, resistor, wire, write_one

from edakit import catalog
from edakit.design import Design
from edakit.sim import ac, netlist
from edakit.sim import run as simrun

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
L_H, C_F = 2.5, 500e-12                 # the project's own values for the test (decision 20), not a maker's
SD = "Seymour Duncan SH-1 '59 Model neck"
PIEZO = "Murata 7BB-20-6L0"
MIC = "CUI CMA-4544PF-W"
RUN = {"input": "LED_SDI", "output": "LED_CLK", "expect": {"gain_db": [{"at_hz": 1000, "min": -1}]}}  # led-bar's nets


def rows(kind):
    return catalog.table("audio_sources")[kind]


def coil_db(f, r, ind, c, r_load):
    """|V_out / V_source| of R and L in series into C ∥ r_load – the pickup into its load, in dB."""
    w = 2 * math.pi * f
    z = 1 / (1 / r_load + 1j * w * c)
    return 20 * math.log10(abs(z / (z + r + 1j * w * ind)))


def f0(ind, c):
    return 1 / (2 * math.pi * math.sqrt(ind * c))


def runs(project, source, **run):
    cfg = project.config()
    return ac.runs(Design.from_config(cfg), {"ac": {"r": {**RUN, **run, "source": source}}}, ["usb-nom/idle/vf-min"])


# --- the table ------------------------------------------------------------------------------------------------------
def test_every_row_states_what_its_model_takes_with_its_source():
    assert not [p for p in catalog.table_problems(catalog.table("audio_sources"))]
    assert all(r["r_ohm"] > 1000 and r["source"] for r in rows("pickup").values())
    assert all(0 < r["c_f"] < 1e-6 for r in rows("piezo").values())
    assert all(r["rl_ohm"] > 0 for r in rows("microphone").values())
    makers = {name.split(" ")[0] for name in rows("pickup")}
    assert {"Seymour", "DiMarzio", "Mojotone"} <= makers
    assert not [n for n, r in rows("pickup").items() if "l_h" in r]       # no maker reachable states an inductance


# --- the config -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("source, words", [
    ({"pickup": "Seymour Duncan SH-1 neck"}, "is no row of catalog/tables/audio_sources.toml"),
    ({"pickup": SD, "l_h": L_H, "r_ohm": 8000}, "r_ohm – the row"),
    ({"pickup": SD, "l_h": L_H, "c_series_f": 1e-9}, "one model"),
    ({"piezo": PIEZO, "c_series_f": 1e-9}, "c_series_f – the row"),
    ({"piezo": "Murata 7BB-99"}, "is no row"),
    ({"c_series_f": 0}, "c_series_f"),
    ({"microphone": MIC, "rl_ohm": 1000}, "rl_ohm – the row"),
    ({"rl_ohm": -1}, "rl_ohm"),
    ({"pickup": 3}, "is no row"),
])
def test_a_named_source_is_checked(project, source, words):
    with pytest.raises(ac.ACError) as e:
        runs(project, source)
    assert words in str(e.value)


def test_a_near_name_is_offered(project):
    with pytest.raises(ac.ACError) as e:
        runs(project, {"pickup": "Seymour Duncan SH-1 59 Model neck", "l_h": L_H})
    assert SD in str(e.value)


def test_a_pickup_row_without_inductance_stops_with_the_reason(project):
    """The makers state DC resistance and, Seymour Duncan, a resonant peak without its load: no inductance is derived
    from it – the project gives l_h (decision 20)."""
    with pytest.raises(ac.ACError) as e:
        runs(project, {"pickup": SD})
    text = str(e.value)
    assert SD in text and "no inductance" in text and "l_h" in text and "decision 20" in text
    assert "7.43 kΩ" in text and "6.8 kHz" in text                         # what the maker does state


def test_the_model_takes_the_row_and_the_project_value():
    assert ac.model({"source": {"pickup": SD, "l_h": L_H}}) == {"kind": "pickup", "row": SD, "r_ohm": 7430,
                                                                "l_h": L_H}
    assert ac.model({"source": {"piezo": PIEZO}}) == {"kind": "piezo", "row": PIEZO, "c_series_f": 10e-9}
    assert ac.model({"source": {"microphone": MIC}}) == {"kind": "microphone", "row": MIC, "rl_ohm": 2200}
    assert ac.model({"source": {"r_ohm": 5000, "l_h": 1}}) == {"kind": "pickup", "r_ohm": 5000, "l_h": 1}
    assert ac.model({"source_ohm": 600}) == {"kind": "resistance", "r_ohm": 600}
    assert ac.model({}) == {"kind": "resistance", "r_ohm": 0}


def test_the_source_lines_per_model():
    piezo = ac.source_lines({"kind": "piezo", "c_series_f": 1e-8}, "n_in")
    assert piezo == ["V_AC_IN x_ac_src 0 DC 0 AC 1", "C_AC_SRC x_ac_src n_in 1e-08"]
    mic = ac.source_lines({"kind": "microphone", "rl_ohm": 2000}, "n_in")
    assert mic == ["I_AC_IN 0 n_in DC 0 AC 0.0005"]                       # 1 V / RL into the input, no DC


# --- the guitar buffer with its sources (ngspice) --------------------------------------------------------------------
def guitar(t, input_ohm=None):
    p = write_one(f"{t}/guitar", "guitar")
    if input_ohm:
        _resistor_to(p, "R20", "C9100031", input_ohm, f"{input_ohm / 1000:g}k")
    return p


def with_guitar_board(p, pot_ohm, cable=None):
    """A second board, the guitar (bought): its jack J30 on GTR_IN and GND, its volume pot as R30 from GTR_IN to its
    ground – wired to J20 by cable W30 of 3 m."""
    toml = p.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[boards.guitar]\ntitle = "Guitar"\nbought = true\n')
    resistor(p, "C9100030", pot_ohm)
    g = p.graph()
    for c in g["graph"]["components"]:
        c.setdefault("board", "main")
    add(g, "J30", "connector", "C131337", {"1": "1", "2": "2"}, bom=False, board="guitar")
    add(g, "R30", "resistor", "C9100030", {"1": "1", "2": "2"}, value=f"{pot_ohm / 1000:g}k", board="guitar")
    wire(g, "GTR_IN", "J30.1", "R30.1")
    wire(g, "GND", "J30.2", "R30.2")
    g["graph"]["cables"].append({"name": "W30", "from": "J30", "to": "J20", "pins": {"1": "1", "2": "2"},
                                 "length_m": 3, "awg": 24, **(cable or {})})
    p.save_graph(g)
    return p


def curve(p, source, expect, **run):
    sim = p.sim()
    sim["ac"] = {"r": {"input": "GTR_IN", "output": "BUF_OUT", "source": source, "expect": expect,
                       "from_hz": 100, "to_hz": 100000, "points": 100, **run}}
    out = simrun.run_all(Design.from_config(p.config()), sim)
    rows_ = [r for r in out["checks"] if r["id"] == "SIM.response"]
    return out["ac"]["r"], rows_


def peak(c):
    i = max(range(len(c["gain_db"])), key=c["gain_db"].__getitem__)
    return c["freq_hz"][i], c["gain_db"][i]


def at(c, f):
    return ac.interpolate(c["freq_hz"], c["gain_db"], f)


@ngspice
@pytest.mark.parametrize("pot_ohm, result", [(250e3, "fail"), (500e3, "pass")])
def test_a_named_pickup_resonates_with_its_load(pot_ohm, result):
    """Seymour Duncan's DC resistance, the project's inductance and capacitance, into a volume pot of 250 or 500 kΩ
    and a 1 MΩ input: the resonance where the coil's formula puts it, as high as R ∥ load lets it – 9.9 dB with
    500 kΩ, 6.7 dB with 250 kΩ, so an expectation of 8 dB at the resonance holds with the one only (SIM.response)."""
    with tempfile.TemporaryDirectory() as t:
        p = with_guitar_board(guitar(t, 1e6), pot_ohm)
        load = 1 / (1 / pot_ohm + 1 / 1e6)
        f_res = f0(L_H, C_F)
        want = coil_db(f_res, 7430, L_H, C_F, load)
        c, checks = curve(p, {"pickup": SD, "l_h": L_H, "c_f": C_F}, {"gain_db": [{"at_hz": f_res, "min": 8}]})
        fp, gp = peak(c)
        assert abs(fp - f_res) / f_res < 0.1 and gp > 5
        assert abs(at(c, f_res) - want) < 0.3                                # the simulation is the formula
        assert abs(at(c, 300) - coil_db(300, 7430, L_H, C_F, load)) < 0.3
        assert c["source"] == {"kind": "pickup", "row": SD, "r_ohm": 7430, "l_h": L_H, "c_f": C_F}
        (row,) = checks
        assert row["result"] == result and row["check"].startswith("gain at")


@ngspice
def test_a_pickup_row_without_inductance_stops_the_simulation():
    with tempfile.TemporaryDirectory() as t:
        p = guitar(t)
        sim = p.sim()
        sim["ac"]["output_coupling"]["source"] = {"pickup": "DiMarzio DP100 Super Distortion"}
        with pytest.raises(simrun.SimError, match="no inductance"):
            simrun.run_all(Design.from_config(p.config()), sim)


@ngspice
def test_a_cable_shifts_the_resonance_down():
    """W30's capacitance, c_pf_per_m × length_m = 300 pF, joins the pickup's own: the resonance falls by
    √(C / (C + C_cable)), and an expectation met without the cable is missed with it (SIM.response)."""
    with tempfile.TemporaryDirectory() as t:
        found = {}
        for name, cable in (("bare", None), ("cable", {"c_pf_per_m": 100})):
            p = with_guitar_board(guitar(f"{t}/{name}", 1e6), 500e3, cable)
            found[name] = curve(p, {"pickup": SD, "l_h": L_H, "c_f": C_F},
                                {"gain_db": [{"at_hz": f0(L_H, C_F), "min": 6}]})
        (bare, (b,)), (cabled, (k,)) = found["bare"], found["cable"]
        ratio = peak(cabled)[0] / peak(bare)[0]
        assert abs(ratio - math.sqrt(C_F / (C_F + 300e-12))) < 0.03
        assert abs(peak(cabled)[0] - f0(L_H, C_F + 300e-12)) / f0(L_H, C_F + 300e-12) < 0.1
        assert b["result"] == "pass" and k["result"] == "fail"


def test_a_cable_without_a_wire_on_ground_or_capacitance_adds_none():
    """Only in an AC run, only between a wire and the cable's wire on ground."""
    with tempfile.TemporaryDirectory() as t:
        p = with_guitar_board(guitar(t), 500e3, {"c_pf_per_m": 100})
        d = Design.from_config(p.config())
        netlist.split_boards(d)
        assert ac.cable_lines(d) == ["C_CBL_W30_1 n_gtr_in__guitar n_gnd__guitar 3e-10"]
        g = p.graph()
        g["graph"]["cables"][0]["pins"] = {"1": "1"}
        p.comp(g, "J30")["nc"] = ["2"]
        p.net(g, "GND")["pins"].remove("J30.2")
        p.save_graph(g)
        d = Design.from_config(p.config())
        netlist.split_boards(d)
        assert ac.cable_lines(d) == []


@ngspice
@pytest.mark.parametrize("input_ohm, ok", [(None, True), (100e3, False)])
def test_a_piezo_into_a_low_input_impedance_loses_its_bass(input_ohm, ok):
    """Murata's 7BB-20-6L0, 10 nF, behind its capacitance: into 2.2 MΩ the corner is 7.2 Hz, into 100 kΩ 159 Hz –
    the expectation of a corner below 20 Hz fails there (SIM.response, corner)."""
    with tempfile.TemporaryDirectory() as t:
        p = guitar(t, input_ohm)
        r = input_ohm or 2.2e6
        c, (row,) = curve(p, {"piezo": PIEZO}, {"low_hz": {"max": 20}}, from_hz=0.5, to_hz=20000)
        low, _, _ = ac.corners(c["freq_hz"], c["gain_db"])
        if input_ohm:
            assert abs(low - 1 / (2 * math.pi * r * 10e-9)) / low < 0.05
        assert row["result"] == ("pass" if ok else "fail") and "lower −3 dB corner" in row["check"]


@ngspice
@pytest.mark.parametrize("rl_ohm, db", [(2200, 0.0), (4700, 20 * math.log10(4700 / 2200))])
def test_an_electret_capsule_into_its_load_resistor(rl_ohm, db):
    """CUI's CMA-4544PF-W, measured with RL = 2.2 kΩ: with that RL in the graph (to VREF) 0 dB is the capsule's output
    into it; a larger RL gives more."""
    with tempfile.TemporaryDirectory() as t:
        p = guitar(t)
        resistor(p, "C9100032", rl_ohm)
        g = p.graph()
        add(g, "R31", "resistor", "C9100032", {"1": "1", "2": "2"}, value=f"{rl_ohm / 1000:g}k")
        wire(g, "GTR_IN", "R31.1")
        wire(g, "VREF", "R31.2")
        p.save_graph(g)
        c, _ = curve(p, {"microphone": MIC}, {"gain_db": [{"at_hz": 1000, "min": -1}]}, from_hz=100, to_hz=10000)
        rl = 1 / (1 / rl_ohm + 1 / 2.2e6)                                  # RL ∥ R20
        assert abs(at(c, 1000) - 20 * math.log10(rl / 2200)) < 0.1 and abs(at(c, 1000) - db) < 0.2


def test_a_capsule_needs_its_load_resistor():
    """Without a resistor chain to a fixed level the capsule's FET has no bias – the run stops with the reason."""
    with tempfile.TemporaryDirectory() as t:
        p = guitar(t)
        g = p.graph()
        p.net(g, "GTR_IN")["pins"].remove("R20.1")
        p.comp(g, "R20")["nc"] = ["1"]
        p.save_graph(g)
        with pytest.raises(ac.ACError, match="load resistor"):
            runs(p, {"microphone": MIC}, input="GTR_IN", output="BUF_OUT")
