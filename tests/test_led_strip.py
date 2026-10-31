"""maker-coverage FT-13: an addressable LED strip – parts kind led_strip – as a ladder in the simulation: the copper of
its +V and GND rails between its pixels, each pixel a current load between them (sim/strip.py). The supply of every
pixel against the pixel IC's range (LIM.range/strip, a warning while new), the current of every feed, through the
connectors and cables it runs (LIM.i). The strip of the tests is the library's Pololu WS2812B strip
(edakit/parts/Pololu_2549.json): 60 LEDs/m, 50 mA per pixel at full white, 0.2 Ω/m per rail – derived from Pololu's
measurement –, 3.5–5.3 V from the WS2812B data sheet."""

import json
import shutil

import pytest
from helpers import check

from edakit.design import Design
from edakit.sim import netlist
from edakit.sim import run as simrun

KEY = "Pololu_2549"
PINS = {"1": "5V", "2": "DIN", "3": "GND", "4": "5V", "5": "DOUT", "6": "GND"}
XH = "C158012"          # JST XH, 3 A per contact (library entry)
SCENARIO = "usb-nom/all_on/vf-max"
needs_ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def strip(project, length, ends=(0,), wires=None, share=1.0, volts=5.0, **comp):
    """The example with a 5 V supply J5 for the LEDs (net VLED) and the strip DS1 of `length` metres. `ends` – 0 the
    start, 1 the far end – are joined to VLED and GND directly; `wires` instead feeds through cables from JST XH
    connectors J10, J11 … on the board: per cable its place along the strip ("start", "end" or metres), its
    length_m, awg and i_max_a (optional); the strip then sits on a board of its own, strip (bought – nobody makes it).
    The load all_on lights the strip at `share` of full white. -> the simulation config."""
    project.use_library_part(KEY)
    g = project.graph()
    graph = g["graph"]
    graph["components"].append({"designator": "J5", "type": "connector", "lcsc": "C131337", "board": "main",
                                "bom": False, "pins": {"1": "1", "2": "2"}})
    ds = {"designator": "DS1", "type": "led_strip", "part": "Pololu 2549", "board": "main", "bom": False,
          "pins": dict(PINS), "nc": ["2", "5"], "strip": {"length_m": length}, **comp}
    graph["components"].append(ds)
    vled, gnd = ["J5.1"], project.net(g, "GND")["pins"]
    gnd.append("J5.2")
    named = {end: ("4", "6") if end else ("1", "3") for end in ends}     # the strip's pins on VLED and GND
    if wires is not None:
        toml = project.root / "edakit.toml"
        if "[boards.strip]" not in toml.read_text():
            toml.write_text(toml.read_text() + '\n[boards.strip]\ntitle = "LED strip"\nbought = true\n')
        for c in graph["components"]:
            c["board"] = "main"
        ds["board"] = "strip"
        project.use_library_part(XH)
        graph["cables"], named = [], {}
        for k, w in enumerate(wires):
            j = f"J{10 + k}"
            graph["components"].append({"designator": j, "type": "connector", "lcsc": XH, "board": "main",
                                        "pins": {"1": "1", "2": "2"}})
            vled.append(f"{j}.1")
            gnd.append(f"{j}.2")
            at = w.get("at", "start")
            named[1 if at == "end" else 0] = pins = ("4", "6") if at == "end" else ("1", "3")
            cable = {"name": f"W{10 + k}", "from": j, "to": "DS1", "pins": {"1": pins[0], "2": pins[1]},
                     **{x: w[x] for x in ("length_m", "awg", "i_max_a") if x in w}}
            if not isinstance(at, str):         # a feed along the strip: its wires land on the rails of the pins
                cable["at_m"] = at
            graph["cables"].append(cable)
    for end in (0, 1):
        if end in named:
            vled.append(f"DS1.{named[end][0]}")
            gnd.append(f"DS1.{named[end][1]}")
        else:
            ds["nc"] += ["4", "6"] if end else ["1", "3"]
    graph["nets"].append({"name": "VLED", "pins": vled, "v": [0, 5.25]})
    project.save_graph(g)
    path = project.root / "hardware" / "sim.json"
    sim = json.loads(path.read_text())
    sim["sources"]["J5"] = {"plus": "1", "minus": "2", "r_ohm": 0.001}
    for s in sim["supplies"].values():
        s["J5"] = volts
    sim["loads"]["all_on"]["strips"] = {"DS1": share}
    path.write_text(json.dumps(sim, indent=1))
    return sim


def simulate(project, sim):
    return simrun.run_all(Design.from_config(project.config()), sim)


def rows(out, item_start, code=None, scenario=SCENARIO):
    return [r for r in out["checks"] if r["scenario"] == scenario and r["item"].startswith(item_start)
            and (code is None or r["id"] == code)]


def strip_findings(out, scenario=SCENARIO):
    return [f for f in out["findings"] if f["code"] == "LIM.range" and f.get("grade") == "strip"
            and f.get("scenario") == scenario]


def pixel_range(out):
    """The row of LIM.range/strip of DS1 in the scenario."""
    (row,) = [r for r in rows(out, "DS1", "LIM.range") if r["item"] == "DS1"]
    return row


def lowest(out):
    return float(pixel_range(out)["actual"].split(" V")[0])


# --- the model ---------------------------------------------------------------------------------------------------------

def test_the_netlist_lumps_a_long_strip_into_sections(project):
    """Up to 50 pixels every pixel is a section of its own; 300 pixels are 50 sections of six, each at the mean place
    of its pixels; the rails run from the pins through every section."""
    sim = strip(project, 0.5)
    sc = next(s for s in simrun.scenarios(sim) if s["name"] == SCENARIO)
    text, meta = netlist.build(Design.from_config(project.config()), sim, sc)
    m = meta["strips"]["DS1"]
    assert m["pixels"] == 30 and len(m["sections"]) == 30 and m["sections"][0]["x_m"] == pytest.approx(1 / 120)
    assert m["share"] == 1.0 and m["i_pixel_a"] == 0.05
    assert sum(line.startswith("B_DS1_P") for line in text.splitlines()) == 30
    sim = strip(project, 5)
    text, meta = netlist.build(Design.from_config(project.config()), sim, sc)
    secs = meta["strips"]["DS1"]["sections"]
    assert len(secs) == 50 and {s["n"] for s in secs} == {6} and secs[-1]["x_m"] == pytest.approx(4.95)
    lines = text.splitlines()
    assert any(line.startswith("V_DS1_F1 n_vled x_ds1_vs 0") for line in lines)
    assert any(line.startswith("R_DS1_V0 x_ds1_vs x_ds1_v0 0.01") for line in lines)     # 0.05 m × 0.2 Ω/m
    assert any(line.startswith("B_DS1_P0 x_ds1_v0 x_ds1_g0 I = 0.3*") for line in lines)  # six pixels × 50 mA


@needs_ngspice
def test_one_metre_fed_at_one_end_drops_what_pololu_measured(project):
    """60 pixels at 50 mA, both rails 0.4 Ω/m: the last pixel sits 0.6 V below the feed – Pololu's 3.0 A and 0.6 V,
    from which the entry's resistance is derived, come back out of the model."""
    out = simulate(project, strip(project, 1))
    first = float(rows(out, "DS1 first pixel")[0]["actual"].split()[0])
    last = float(rows(out, "DS1 last pixel")[0]["actual"].split()[0])
    assert first - last == pytest.approx(0.59, abs=0.005)      # 0.4/60 Ω × 50 mA × (1 + … + 59)
    assert pixel_range(out)["result"] == "pass" and "pixels 59–60, 0.98 m" in pixel_range(out)["actual"]
    (feed,) = rows(out, "DS1.1")
    assert float(feed["actual"].split()[0]) == pytest.approx(3.0, abs=0.01)


# --- LIM.range/strip ------------------------------------------------------------------------------------------------------

@needs_ngspice
def test_five_metres_fed_at_one_end_fail_at_the_far_end(project):
    """300 pixels, 15 A at full white: the far end gets nothing like the 3.5 V a WS2812B needs (Pololu feeds at most
    180 LEDs from one point)."""
    out = simulate(project, strip(project, 5))
    row = pixel_range(out)
    assert row["result"] == "fail" and row["expected"] == "3.5 … 5.3 V"
    assert "pixels 295–300, 4.95 m" in row["actual"].split("…")[0]
    (f,) = strip_findings(out)
    assert f["place"] == "DS1" and f["severity"] == "warning"
    assert f["text"].startswith("supply of every pixel (300 at 100% of full white, 50 mA per pixel) inside the pixel's "
                                "operating range: ")
    assert "vdd_op_min_v … vdd_op_max_v of Pololu_2549" in f["source"]


@needs_ngspice
def test_two_metres_fail_from_one_end_and_pass_from_both(project):
    """120 pixels, 6 A: from one end the last pixels sit 2.4 V low; fed at both ends the middle sags 0.6 V."""
    out = simulate(project, strip(project, 2))
    assert 2.5 < lowest(out) < 2.7 and strip_findings(out)
    out = simulate(project, strip(project, 2, ends=(0, 1)))
    assert 4.3 < lowest(out) < 4.45 and not strip_findings(out)
    assert "pixels 59–61" in pixel_range(out)["actual"] or "pixels 58–60" in pixel_range(out)["actual"]


@needs_ngspice
def test_five_metres_need_a_feed_in_the_middle(project):
    """Fed at both ends the middle of 5 m still sags below 3.5 V; a third feed at 2.5 m, through a short thick
    cable, lifts every pixel above it."""
    out = simulate(project, strip(project, 5, ends=(0, 1)))
    assert strip_findings(out) and lowest(out) < 3.5
    thick = {"length_m": 0.1, "awg": 14}
    out = simulate(project, strip(project, 5, wires=[{"at": "start", **thick}, {"at": "end", **thick},
                                                      {"at": 2.5, **thick}]))
    assert not strip_findings(out) and lowest(out) > 3.5
    taps = {r["check"]: float(r["actual"].split()[0]) for r in rows(out, "cable W12")}
    assert taps["current into DS1 through W12_1 at 2.5 m"] == pytest.approx(7.5, abs=0.05)    # half of each side
    assert taps["current out of DS1 through W12_2 at 2.5 m"] == pytest.approx(7.5, abs=0.05)


@needs_ngspice
def test_a_dark_strip_draws_nothing_and_passes(project):
    out = simulate(project, strip(project, 5, share=0.0))
    assert not strip_findings(out) and lowest(out) == pytest.approx(5.0, abs=0.01)


# --- the current of each feed ----------------------------------------------------------------------------------------

@needs_ngspice
def test_one_feed_overloads_its_connector_two_share_the_current(project):
    """1 m, 3 A through one JST XH contact (3 A, derated by the example's 0.8 to 2.4 A): LIM.i on its connector; fed
    from both ends 1.5 A per connector passes. The cable's own i_max_a holds its wires the same way."""
    wire = {"length_m": 1, "awg": 20}
    out = simulate(project, strip(project, 1, wires=[{"at": "start", **wire, "i_max_a": 2}]))
    contact = [f for f in out["findings"] if f["code"] == "LIM.i" and f["place"] == "J10" and f.get("scenario") == SCENARIO]
    assert any("current per contact" in f["text"] for f in contact)
    cable = [f for f in out["findings"] if f["code"] == "LIM.i" and f["place"] == "cable W10"
             and f.get("scenario") == SCENARIO]
    assert len(cable) == 2 and "current through wire W10_1 (to DS1)" in cable[0]["text"]
    out = simulate(project, strip(project, 1, wires=[{"at": "start", **wire, "i_max_a": 2}, {"at": "end", **wire,
                                                                                             "i_max_a": 2}]))
    assert not [f for f in out["findings"] if f["code"] == "LIM.i" and f.get("scenario") == SCENARIO
                and f["place"] in ("J10", "J11", "cable W10", "cable W11")]
    feeds = {r["item"]: float(r["actual"].split()[0]) for r in rows(out, "DS1.")}
    assert feeds["DS1.1"] == pytest.approx(1.5, abs=0.05) and feeds["DS1.4"] == pytest.approx(1.5, abs=0.05)


@needs_ngspice
def test_a_rated_strip_pin_holds_its_feed(project):
    """A strip whose entry rates a pin (its lead or connector: i_max_a) holds the feed there to it – 3 A at the start
    of the metre against 2 A, LIM.i/strip; the board's renamed node of the pin stops no other check."""
    sim = strip(project, 1, wires=[{"at": "start", "length_m": 0.5, "awg": 20}])
    entry = project.part(KEY)
    entry["pins"]["1"]["i_max_a"] = 2.0
    project.save_part(KEY, entry)
    out = simulate(project, sim)
    (f,) = [f for f in out["findings"] if f["place"] == "DS1.1" and f.get("scenario") == SCENARIO]
    assert f["code"] == "LIM.i" and f["grade"] == "strip" and f["severity"] == "warning"
    assert f["text"].startswith("current into DS1 at 5V (pin 1, 0 m) 3")


@needs_ngspice
def test_the_feed_wire_drops_the_strip_with_it(project):
    """The same metre behind 1 m of AWG 28 (0.212 Ω per wire): its start sits 3 A × 0.425 Ω = 1.27 V below VLED."""
    out = simulate(project, strip(project, 1, wires=[{"at": "start", "length_m": 1, "awg": 28}]))
    first = float(rows(out, "DS1 first pixel")[0]["actual"].split()[0])
    assert first == pytest.approx(4.997 - 3.0 * 2 * 0.2124, abs=0.02)


@needs_ngspice
def test_a_chained_strip_is_fed_through_the_first(project):
    """DS2 plugged into the output of DS1 (Pololu: chaining): its supply comes through DS1's rails – PATH.unfed and
    PATH.ground follow the rails (catalog/paths.toml), and the simulation puts DS2 below the end of DS1."""
    sim = strip(project, 1)
    g = project.graph()
    ds1 = project.comp(g, "DS1")
    ds1["nc"] = ["2"]
    g["graph"]["components"].append({"designator": "DS2", "type": "led_strip", "part": "Pololu 2549", "board": "main",
                                     "bom": False, "pins": dict(PINS), "nc": ["4", "5", "6"],
                                     "strip": {"length_m": 1}})
    g["graph"]["nets"] += [{"name": "VJ", "pins": ["DS1.4", "DS2.1"], "v": [0, 5.25]},
                           {"name": "GJ", "pins": ["DS1.6", "DS2.3"], "v": [0, 5.25]},
                           {"name": "DJ", "pins": ["DS1.5", "DS2.2"], "v": [0, 5.25]}]
    project.save_graph(g)
    cfg = project.config()
    assert not [f for f in check(Design.from_config(cfg), cfg).errors if f[0].startswith("PATH.")]
    sim["loads"]["all_on"]["strips"] = {"DS1": 1, "DS2": 1}
    out = simulate(project, sim)
    first = {des: float(rows(out, f"{des} first pixel")[0]["actual"].split()[0]) for des in ("DS1", "DS2")}
    last = {des: float(rows(out, f"{des} last pixel")[0]["actual"].split()[0]) for des in ("DS1", "DS2")}
    assert last["DS1"] > first["DS2"] > last["DS2"] and first["DS1"] - last["DS2"] > 2


# --- what the graph and the entry must give --------------------------------------------------------------------------

def test_at_m_is_a_place_along_a_strip(project):
    """A cable with at_m that reaches no strip is STRUCT.net; a place beyond the strip's end stops its scenarios."""
    strip(project, 1, wires=[{"at": "start", "length_m": 0.2, "awg": 18}, {"at": 1.5, "length_m": 0.2, "awg": 18}])
    g = project.graph()
    g["graph"]["cables"].append({"name": "W1", "from": "J10", "to": "J5", "pins": {"1": "1"}, "at_m": 0.5})
    project.save_graph(g)
    cfg = project.config()
    found = [t for c, t in check(Design.from_config(cfg), cfg).errors if c == "STRUCT.net"]
    assert "cable W1: at_m – the place along an LED strip its wires land, but neither end is an LED strip" in found
    g["graph"]["cables"].pop()
    project.save_graph(g)
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simulate(project, sim)
    conv = [r for r in out["checks"] if r["id"] == "SIM.converge" and r["scenario"] == SCENARIO]
    assert "cable W11: at_m 1.5 – a place along DS1, 0 … 1 m" in conv[0]["actual"]


def test_a_strip_without_its_length_is_a_finding(project):
    strip(project, 1, strip={"pixels": 60, "length_m": 1})
    cfg = project.config()
    found = [t for c, t in check(Design.from_config(cfg), cfg).warnings if c == "STRUCT.entry"]
    assert found == ["DS1: strip: length_m or pixels, one of the two"]


def test_a_strip_entry_without_its_rail_resistance_is_a_finding(project):
    """The resistance of the rails is in no LED data sheet: an entry without it is PARTS.fact (a warning), and the
    simulation does not guess – the strip's scenario stops with the reason."""
    strip(project, 1)
    entry = project.part(KEY)
    del entry["values"]["r_gnd_ohm_per_m"]
    project.save_part(KEY, entry)
    cfg = project.config()
    found = [t for c, t in check(Design.from_config(cfg), cfg).warnings if c == "PARTS.fact"]
    assert found == ["Pololu_2549 Pololu 2549 (DS1) states no values.r_gnd_ohm_per_m"]
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simulate(project, sim)
    conv = [r for r in out["checks"] if r["id"] == "SIM.converge" and r["scenario"] == SCENARIO]
    assert "gives no r_gnd_ohm_per_m" in conv[0]["actual"]


@needs_ngspice
def test_a_load_that_names_no_strip_is_a_config_finding(project):
    sim = strip(project, 0.5)
    sim["loads"]["all_on"]["strips"] = {"DS1": 1.5, "R1": 1}
    out = simulate(project, sim)
    cfg_rows = [r for r in rows(out, "", "SIM.config")]
    assert {r["item"] for r in cfg_rows} == {"DS1", "R1"} and all(r["result"] == "fail" for r in cfg_rows)


@needs_ngspice
def test_three_volt_data_into_the_strip_is_undefined(project):
    """The strip's DIN holds its VIH of 0.7 × VDD (WS2812B data sheet p. 3): a Pico 2 output's 3.3 V at a 5 V strip
    is LVL.threshold – the generic level check, from the entry's pin."""
    strip(project, 0.5)
    g = project.graph()
    project.free_pins(g, "U1.10")
    project.comp(g, "DS1")["nc"].remove("2")
    g["graph"]["nets"].append({"name": "LED_DATA", "pins": ["U1.10", "DS1.2"], "v": [0, 3.4]})
    project.save_graph(g)
    path = project.root / "hardware" / "sim.json"
    sim = json.loads(path.read_text())
    sim["mcu"]["U1"]["outputs"].append("LED_DATA")
    out = simulate(project, sim)
    lvl = [r for r in rows(out, "U1 LED_DATA", "LVL.threshold")]
    assert lvl and lvl[0]["check"] == "output high level reaches VIH of DS1 DIN" and lvl[0]["result"] == "fail"
