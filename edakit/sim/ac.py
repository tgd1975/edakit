"""AC analysis, opt-in (rules-at-scale.md, decision 9; maker-coverage FT-12): ngspice .ac around a DC operating point,
only where sim.json names an expectation, only with the domain audio or guitar on.

    "ac": {
      "input_filter": {
        "about": "the PWM DAC's RC low-pass in front of the amplifier",
        "scenario": "usb-nom/idle/vf-min",          the operating point it linearises around; default the first
        "input": "AUDIO_PWM",                        the net driven with 1 V AC (through 1 F: its DC stays its own)
        "output": "AUDIO_IN",                        the net measured, against its board's ground
        "source_ohm": 0,                             the AC source's own resistance (a microphone's output)
        "source": {"r_ohm", "l_h", "c_f"},           or a source model (FT-18): R and L in series, C across –
                                                     a magnetic pickup's coil; the project's values, with their source
        "expect": {
          "gain_db": [{"at_hz": 1000, "min": -0.5, "max": 0.5}],
          "low_hz": {"max": 20},                     the lower −3 dB corner, below the passband's peak
          "high_hz": {"min": 10000, "max": 25000}    the upper −3 dB corner
        },
        "from_hz": 1, "to_hz": 1e6, "points": 20     the sweep (optional): per decade; default a decade beyond the
      }                                              expectation's frequencies on each side
    }

The gain is 20·log10 |V(output) / V(source)|, the source being 1 V AC behind source_ohm – with a source resistance the
gain includes what the input's load does to it. A corner is where the gain falls 3.01 dB below its largest value in
the sweep, found by interpolation in log f; a corner outside the sweep is reported as beyond it. Each expectation is a
row; a missed one is SIM.response (gain or corner), a warning while new. The op-amp model has no gain-bandwidth: an
upper corner comes from the passive parts only.
"""

from __future__ import annotations

import math
import re

from ..engines import sim as esim
from ..findings import Finding
from . import netlist

RUN_KEYS = {"scenario", "input", "output", "source_ohm", "source", "expect", "from_hz", "to_hz", "points", "about",
            "note"}
SOURCE_KEYS = {"r_ohm", "l_h", "c_f", "about", "note"}
EXPECT_KEYS = {"gain_db", "low_hz", "high_hz"}
DB3 = 20 * math.log10(math.sqrt(2))         # 3.0103 dB: half the power
SERIES_F = 1.0                              # the capacitor that keeps the input net's DC its own


class ACError(ValueError):
    pass


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def bounds(at, x, unit):
    """{min, max} – at least one, numbers, min <= max."""
    if not isinstance(x, dict) or not x or set(x) - {"min", "max"} or not all(map(number, x.values())):
        raise ACError(f"{at}: {{min, max}} in {unit} expected, at least one of them, not {x!r}")
    if "min" in x and "max" in x and x["min"] > x["max"]:
        raise ACError(f"{at}: min {x['min']} above max {x['max']}")
    return x


def runs(design, sim, names):
    """The runs of `ac`, {name: run}, checked; names: the DC scenarios a run may linearise around."""
    out = sim.get("ac") or {}
    if not isinstance(out, dict):
        raise ACError(f"ac: a map from each run's name to the run expected, not {out!r}")
    for name, r in out.items():
        at = f"ac {name}"
        if not isinstance(r, dict) or set(r) - RUN_KEYS:
            raise ACError(f"{at}: a run with {', '.join(sorted(RUN_KEYS - {'about', 'note'}))} expected, not {r!r}")
        for key in ("input", "output"):
            net = r.get(key)
            if net not in design.nets or net == design.ground:
                raise ACError(f"{at}: {key} {net!r} is no net of the graph (ground excluded)")
        if r["input"] == r["output"]:
            raise ACError(f"{at}: input and output are the same net")
        if "scenario" in r and r["scenario"] not in names:
            raise ACError(f"{at}: scenario {r['scenario']!r} is no scenario of the simulation (known: "
                          f"{', '.join(names[:6])}{' …' if len(names) > 6 else ''})")
        if not number(r.get("source_ohm", 0)) or r.get("source_ohm", 0) < 0:
            raise ACError(f"{at}: source_ohm, the source's own resistance in Ω (≥ 0), expected")
        if "source" in r:
            m = r["source"]
            if "source_ohm" in r:
                raise ACError(f"{at}: source_ohm or source, not both")
            if (not isinstance(m, dict) or set(m) - SOURCE_KEYS or not set(m) & {"r_ohm", "l_h", "c_f"}
                    or not all(number(m[k]) and m[k] >= 0 for k in ("r_ohm", "l_h", "c_f") if k in m)):
                raise ACError(f"{at}: source – {{r_ohm, l_h, c_f}}, numbers ≥ 0 (R and L in series, C across), not "
                              f"{m!r}")
        e = r.get("expect")
        if not isinstance(e, dict) or not e or set(e) - EXPECT_KEYS:
            raise ACError(f"{at}: expect with gain_db, low_hz and/or high_hz expected – without an expectation "
                          f"nothing runs (decision 9), not {e!r}")
        gains = e.get("gain_db", [])
        if not isinstance(gains, list) or not all(isinstance(g, dict) and number(g.get("at_hz")) and g["at_hz"] > 0
                                                 for g in gains):
            raise ACError(f"{at}: gain_db – a list of {{at_hz, min, max}} expected, not {gains!r}")
        for g in gains:
            bounds(f"{at} gain_db at {g['at_hz']:g} Hz", {k: v for k, v in g.items() if k != "at_hz"}, "dB")
        for key in ("low_hz", "high_hz"):
            if key in e:
                b = bounds(f"{at} {key}", e[key], "Hz")
                if any(v <= 0 for v in b.values()):
                    raise ACError(f"{at} {key}: frequencies above 0 Hz expected")
        f0, f1 = sweep(r)
        if not (0 < f0 < f1):
            raise ACError(f"{at}: from_hz below to_hz, both above 0 Hz, expected")
        if not isinstance(r.get("points", 20), int) or not 2 <= r.get("points", 20) <= 1000:
            raise ACError(f"{at}: points per decade, a whole number from 2 to 1000, expected")
    return out


def sweep(r):
    """(from_hz, to_hz): as given, else a decade beyond the expectation's frequencies on each side."""
    e = r.get("expect") or {}
    freqs = [g["at_hz"] for g in e.get("gain_db", []) if number(g.get("at_hz"))]
    freqs += [v for key in ("low_hz", "high_hz") for v in (e.get(key) or {}).values() if number(v)]
    lo, hi = (min(freqs), max(freqs)) if freqs else (20.0, 20000.0)
    return r.get("from_hz", max(lo / 10, 0.01)), r.get("to_hz", min(hi * 10, 1e9))


def netlist_text(design, sim, sc, run, models, data_file):
    """The operating point's netlist with the AC source on the input net and an .ac control block instead of .op."""
    text, meta = netlist.build(design, sim, sc, models)
    inp = netlist.net_nodes(design, run["input"])[0]
    out = netlist.net_nodes(design, run["output"])[0]
    gnd = netlist.node(netlist.local_ground(design, run["output"]), design.ground)
    source = "".join(f"{line}\n" for line in source_lines(run, inp))
    f0, f1 = sweep(run)
    vector = f"mag(v({out}))" if gnd == "0" else f"mag(v({out})-v({gnd}))"
    control = (f".control\nac dec {run.get('points', 20)} {f0:.6g} {f1:.6g}\nset wr_singlescale\nset wr_vecnames\n"
               f"wrdata {data_file} {vector}\n.endc\n")
    text = text.replace("\n.options ", "\n" + source + ".options ", 1)
    text, n = re.subn(r"\.control\n.*?\.endc\n", lambda _: control, text, count=1, flags=re.S)
    if n != 1:
        raise ACError("the operating point's netlist has no control block to replace")
    return text, meta


def source_lines(run, inp):
    """The AC source: 1 V behind source_ohm, or behind the model of `source` – R and L in series, C across its output
    to ground (a magnetic pickup: coil resistance, inductance, winding and cable capacitance) –, coupled onto the input
    net through SERIES_F."""
    m = run.get("source") or {"r_ohm": run.get("source_ohm", 0)}
    lines, at = ["V_AC_IN x_ac_src 0 DC 0 AC 1"], "x_ac_src"
    lines.append(f"R_AC_IN {at} x_ac_r {max(m.get('r_ohm', 0), 1e-3):.6g}")
    at = "x_ac_r"
    if m.get("l_h"):
        lines.append(f"L_AC_IN {at} x_ac_l {m['l_h']:.6g}")
        at = "x_ac_l"
    if m.get("c_f"):
        lines.append(f"C_AC_SRC {at} 0 {m['c_f']:.6g}")
    lines.append(f"C_AC_IN {at} {inp} {SERIES_F:g}")
    return lines


def interpolate(freqs, gains, f):
    """The gain at f, linear in log f between the sweep's points; None outside the sweep."""
    if not freqs or f < freqs[0] or f > freqs[-1]:
        return None
    for (fa, ga), (fb, gb) in zip(zip(freqs, gains), zip(freqs[1:], gains[1:])):
        if fa <= f <= fb:
            t = 0 if fb == fa else (math.log10(f) - math.log10(fa)) / (math.log10(fb) - math.log10(fa))
            return ga + t * (gb - ga)
    return gains[-1]


def corners(freqs, gains):
    """(low, high, peak): the −3 dB corners around the largest gain – None where the gain stays above the corner up to
    the sweep's end on that side."""
    peak_i = max(range(len(gains)), key=gains.__getitem__)
    level = gains[peak_i] - DB3

    def cross(i, j):
        fa, fb, ga, gb = freqs[i], freqs[j], gains[i], gains[j]
        t = (level - ga) / (gb - ga) if gb != ga else 0
        return 10 ** (math.log10(fa) + t * (math.log10(fb) - math.log10(fa)))
    low = next((cross(i, i + 1) for i in range(peak_i - 1, -1, -1) if gains[i] < level), None)
    high = next((cross(i - 1, i) for i in range(peak_i + 1, len(gains)) if gains[i] < level), None)
    return low, high, gains[peak_i]


def hz(f):
    return f"{f / 1000:.4g} kHz" if f >= 1000 else f"{f:.4g} Hz"


def judge(s, name, run, freqs, gains):
    """The rows of one run's expectations on the Scene s; a missed one is SIM.response (gain or corner)."""
    e, what = run["expect"], f"{run['input']} → {run['output']}"
    src = f"ac.{name} of the simulation config"
    for g in e.get("gain_db", []):
        x = interpolate(freqs, gains, g["at_hz"])
        lo, hi = g.get("min", -math.inf), g.get("max", math.inf)
        expected = (f"{g['min']:g} … {g['max']:g} dB" if "min" in g and "max" in g else
                    f"≥ {g['min']:g} dB" if "min" in g else f"≤ {g['max']:g} dB")
        s.check("SIM.response", what, f"gain at {hz(g['at_hz'])}", "outside the sweep" if x is None else f"{x:.2f} dB",
                expected, x is not None and lo <= x <= hi, source=src, grade="gain")
    low, high, peak = corners(freqs, gains)
    for key, f, beyond in (("low_hz", low, f"below {hz(freqs[0])}"), ("high_hz", high, f"above {hz(freqs[-1])}")):
        if key not in e:
            continue
        b = e[key]
        word = "lower" if key == "low_hz" else "upper"
        expected = (f"{hz(b['min'])} … {hz(b['max'])}" if "min" in b and "max" in b else
                    f"≥ {hz(b['min'])}" if "min" in b else f"≤ {hz(b['max'])}")
        if f is None and key == "low_hz":     # below the sweep: within a max that reaches the sweep, a min unknown
            ok, actual = "min" not in b and b.get("max", math.inf) >= freqs[0], beyond
        elif f is None:                       # above the sweep: within a min below its end, a max unknown
            ok, actual = "max" not in b and b.get("min", 0) <= freqs[-1], beyond
        else:
            ok = b.get("min", 0) <= f <= b.get("max", math.inf)
            actual = hz(f)
        s.check("SIM.response", what, f"{word} −3 dB corner (peak {peak:.2f} dB)", actual, expected, ok, source=src,
                grade="corner")


def run_one(design, new, sim, name, run, sc, ngspice_tran, keep=None, models=None):
    """One run of `ac` -> (row of the scenario table, rows, findings, curve)."""
    row = {"name": f"ac {name}", "supply": sc["supply_name"], "load": sc["load_name"], "corner": sc["corner"],
           "ac": True}
    s = esim.Scene(design, new, sim, {}, {}, f"ac {name}", False)
    data = re.sub(r"[^\w.-]", "_", f"ac_{name}") + ".dat"
    try:
        text, _ = netlist_text(design, sim, sc, run, models or {}, data)
        freqs, cols = ngspice_tran(text, data, keep, f"ac {name}")
        mags = cols[0]
    except Exception as e:           # a run ngspice cannot take: SIM.converge, as every other scenario
        s.check("SIM.converge", "circuit", "ac run", f"{type(e).__name__}: {str(e).replace('transient', 'ac')}",
                "converges", False)
        row["status"] = "error"
        return (row, *s.finish(), None)
    s.check("SIM.converge", "circuit", "ac run", "converged", "converges", True)
    gains = [20 * math.log10(max(m, 1e-30)) for m in mags]
    judge(s, name, run, freqs, gains)
    rows, found = s.finish()
    row["status"] = "ok" if all(r["result"] != "fail" for r in rows) else "fail"
    return row, rows, found, {"input": run["input"], "output": run["output"], "scenario": sc["name"],
                              "freq_hz": freqs, "gain_db": gains}


def off_note(runs_):
    """The note when ac names runs and neither audio nor guitar is on: nothing ran."""
    return Finding("SIM.config", "E", "ac", f"ac: {', '.join(runs_)} not run – AC analysis runs with the domain audio "
                   "or guitar on (decision 9)", grade="off")
