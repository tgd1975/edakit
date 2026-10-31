"""AC analysis, opt-in (rules-at-scale.md, decision 9; sim/ac.py): sim.json `ac` checked, a run only where it names an
expectation and only with the domain audio or guitar on, the gain and the −3 dB corners against the expectation
(SIM.response), a note where nothing ran."""

import json
import math
import shutil
import tempfile

import pytest
from reference import write_one

from edakit.design import Design
from edakit.sim import ac
from edakit.sim import run as simrun

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
RUN = {"input": "LED_SDI", "output": "LED_CLK", "expect": {"gain_db": [{"at_hz": 1000, "min": -1}]}}


def runs(project, sim_ac, names=("usb-nom/idle/vf-min",)):
    cfg = project.config()
    return ac.runs(Design.from_config(cfg), {"ac": sim_ac}, list(names))


@pytest.mark.parametrize("run, words", [
    ({"input": "LED_SDI", "output": "LED_CLK"}, "without an expectation nothing runs"),
    ({**RUN, "expect": {}}, "without an expectation nothing runs"),
    ({**RUN, "input": "NOPE"}, "input 'NOPE' is no net"),
    ({**RUN, "output": "GND"}, "ground excluded"),
    ({**RUN, "output": "LED_SDI"}, "the same net"),
    ({**RUN, "scenario": "nowhere"}, "scenario 'nowhere' is no scenario"),
    ({**RUN, "expect": {"low_hz": {"min": 50, "max": 10}}}, "min 50 above max 10"),
    ({**RUN, "expect": {"gain_db": [{"min": 0}]}}, "gain_db – a list of {at_hz, min, max}"),
    ({**RUN, "source_ohm": -1}, "source_ohm"),
    ({**RUN, "points": 1}, "points per decade"),
    ({**RUN, "from_hz": 100, "to_hz": 10}, "from_hz below to_hz"),
    ({**RUN, "colour": "red"}, "a run with"),
])
def test_the_config_is_checked(project, run, words):
    with pytest.raises(ac.ACError) as e:
        runs(project, {"r": run})
    assert words in str(e.value)


def test_a_valid_run_and_its_default_sweep(project):
    assert list(runs(project, {"r": RUN})) == ["r"]
    assert ac.sweep(RUN) == (100, 10000)                                   # a decade beyond 1 kHz on each side
    assert ac.sweep({"expect": {"low_hz": {"max": 10}, "high_hz": {"min": 20000}}}) == (1, 200000)
    assert ac.sweep({**RUN, "from_hz": 5, "to_hz": 50}) == (5, 50)


def test_interpolation_and_corners_on_a_known_low_pass():
    fc = 1000.0
    freqs = [10 ** (k / 40) for k in range(0, 241)]                        # 1 Hz … 1 MHz, 40 points per decade
    gains = [20 * math.log10(1 / math.sqrt(1 + (f / fc) ** 2)) for f in freqs]
    low, high, peak = ac.corners(freqs, gains)
    assert low is None and abs(high - fc) / fc < 0.01 and abs(peak) < 1e-3
    assert abs(ac.interpolate(freqs, gains, 1000) - (-3.0103)) < 0.01
    assert ac.interpolate(freqs, gains, 0.5) is None                      # outside the sweep


class Scene:
    def __init__(self):
        self.rows = []

    def check(self, code, place, what, actual, expected, ok, **kw):
        self.rows.append((what, actual, ok, kw.get("grade")))


@pytest.mark.parametrize("bound, ok", [({"max": 10}, True), ({"min": 1}, False), ({"max": 0.5}, False)])
def test_a_corner_below_the_sweep_meets_a_max_it_reaches_not_a_min(bound, ok):
    freqs = [1, 10, 100, 1000]
    s = Scene()
    ac.judge(s, "r", {"input": "A", "output": "B", "expect": {"low_hz": bound}}, freqs, [0, 0, 0, 0])
    (what, actual, got, grade), = s.rows
    assert got is ok and actual == "below 1 Hz" and grade == "corner"


@ngspice
def test_without_audio_or_guitar_nothing_runs_and_a_note_says_so(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    sim["ac"] = {"r": RUN}
    cfg = project.config()
    out = simrun.run_all(Design.from_config(cfg), sim)
    assert "ac" not in out and not [r for r in out["checks"] if r["id"] == "SIM.response"]
    notes = [f for f in out["findings"] if f["code"] == "SIM.config"]
    assert len(notes) == 1 and notes[0]["severity"] == "note" and notes[0]["grade"] == "off"
    assert "r not run" in notes[0]["text"] and "audio or guitar" in notes[0]["text"]


@ngspice
def test_the_guitar_buffer_answers_as_its_parts_say():
    with tempfile.TemporaryDirectory() as t:
        p = write_one(f"{t}/guitar", "guitar")
        out = simrun.run_all(Design.from_config(p.config()), p.sim())
        curve = out["ac"]["output_coupling"]
        assert curve["input"] == "GTR_IN" and curve["output"] == "BUF_OUT" and len(curve["freq_hz"]) > 50
        low, _, _ = ac.corners(curve["freq_hz"], curve["gain_db"])
        assert abs(low - 1 / (2 * math.pi * 100e3 * 1e-6)) < 0.05           # C22 / R24: 1.59 Hz
        assert {r["result"] for r in out["checks"] if r["id"] == "SIM.response"} == {"pass"}
        assert any(s.get("ac") for s in out["scenarios"])


@ngspice
def test_a_source_model_resonates_with_its_load():
    """FT-18: `source` as R and L in series with C across (a magnetic pickup's coil) – values chosen for the test, not a
    product's: L = 1 H, C = 1 nF resonate at 1 / (2π√(LC)) = 5.03 kHz, a peak the buffer's 2.2 MΩ hardly damps."""
    with tempfile.TemporaryDirectory() as t:
        p = write_one(f"{t}/guitar", "guitar")
        sim = p.sim()
        sim["ac"]["output_coupling"].update(source={"r_ohm": 5000, "l_h": 1.0, "c_f": 1e-9}, to_hz=100000)
        sim["ac"]["output_coupling"]["expect"] = {"gain_db": [{"at_hz": 100, "min": -0.5, "max": 0.5}]}
        out = simrun.run_all(Design.from_config(p.config()), sim)
        curve = out["ac"]["output_coupling"]
        f, g = curve["freq_hz"], curve["gain_db"]
        peak = max(range(len(g)), key=g.__getitem__)
        assert abs(f[peak] - 1 / (2 * math.pi * math.sqrt(1.0 * 1e-9))) / 5033 < 0.1 and g[peak] > 3


def test_source_or_source_ohm_not_both(project):
    with pytest.raises(ac.ACError, match="not both"):
        runs(project, {"r": {**RUN, "source_ohm": 10, "source": {"r_ohm": 10}}})
    with pytest.raises(ac.ACError, match="R and L in series"):
        runs(project, {"r": {**RUN, "source": {"l": 1}}})
