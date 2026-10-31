"""The domains audio and guitar: bridge-tied outputs (maker-coverage CK-8), the load on an instrument input (CK-27),
stable gain (CK-28), and their hints (HT-8, HT-13, HT-15–HT-19)."""

from edakit import engines, profile
from edakit.design import Design

# values for the tests, not from datasheets
AMP = {"lcsc": "C9000601", "mpn": "test class-D amplifier", "kind": "ic", "verified": {"by": "test"},
       "needs": {"decoupling": False}, "values": {"behavior": "none"},
       "pins": {"1": {"name": "OUT+", "type": "output", "role": "out_p"}, "2": {"name": "OUT-", "type": "output",
                                                                              "role": "out_n"},
                "3": {"name": "IN", "type": "analog"}, "4": {"name": "GND", "type": "ground"},
                "5": {"name": "VDD", "type": "power_in"}}}
SPEAKER = {"lcsc": "C9000602", "mpn": "test speaker", "kind": "speaker", "verified": {"by": "test"},
           "values": {"impedance_ohm": 8},
           "pins": {"1": {"name": "+", "type": "passive", "role": "plus"}, "2": {"name": "-", "type": "passive",
                                                                              "role": "minus"}}}
OPAMP = {"lcsc": "C9000603", "mpn": "test op-amp", "kind": "ic", "verified": {"by": "test"},
         "needs": {"decoupling": False}, "values": {"behavior": "opamp", "gain_min_ratio": 10},
         "pins": {"1": {"name": "OUT", "type": "output", "role": "out"}, "2": {"name": "-IN", "type": "input",
                                                                              "role": "in_n"},
                  "3": {"name": "+IN", "type": "input", "role": "in_p", "z_in_ohm": 1e12},
                  "4": {"name": "GND", "type": "ground", "role": "gnd"}, "5": {"name": "VCC", "type": "power_in",
                                                                               "role": "vcc"}}}


def add_net(g, name, *pins, v=(0, 5.5), **extra):
    existing = [n for n in g["graph"]["nets"] if n["name"] == name]
    if existing:
        existing[0]["pins"] += list(pins)
    else:
        g["graph"]["nets"].append({"name": name, "pins": list(pins), "v": list(v), **extra})


def found(project, code, grade=None):
    cfg = project.config()
    return [f for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == code
            and (grade is None or f.grade == grade)]


def amplifier(project, out_n="SPK_N", speaker=True):
    project.save_part("C9000601", AMP)
    project.save_part("C9000602", SPEAKER)
    g = project.graph()
    g["graph"]["components"].append({"designator": "U8", "type": "ic", "lcsc": "C9000601",
                                     "pins": {n: i["name"] for n, i in AMP["pins"].items()}, "nc": ["3"]})
    add_net(g, "GND", "U8.4")
    add_net(g, "+5V", "U8.5")
    add_net(g, "SPK_P", "U8.1")
    add_net(g, out_n, "U8.2")
    if speaker:
        g["graph"]["components"].append({"designator": "LS1", "type": "audio", "lcsc": "C9000602",
                                         "pins": {"1": "+", "2": "-"}})
        add_net(g, "SPK_P", "LS1.1")
        add_net(g, out_n, "LS1.2")
    project.save_graph(g)
    return g


# --- audio -------------------------------------------------------------------------------------------------------------
def test_a_bridge_tied_output_with_its_speaker_is_clean(project):
    amplifier(project)
    assert "audio" in profile.suggested(Design.from_config(project.config()))
    assert found(project, "REQ.forbidden", "btl") == []


def test_a_bridge_tied_output_on_ground(project):
    amplifier(project, out_n="GND")
    assert [f.text for f in found(project, "REQ.forbidden", "btl")] == [
        "U8.2 (out_n): a bridge-tied output on GND – it is never ground"]


def test_audio_hints(project):
    g = amplifier(project)
    project.comp(g, "U8")["nc"] = []
    add_net(g, "AUDIO_IN", "U8.3", v=(0, 3.4))
    g["graph"]["components"].append({"designator": "C8", "type": "capacitor", "lcsc": "C49678", "value": "100nF",
                                     "pins": {"1": "1", "2": "2"}})
    add_net(g, "AUDIO_IN", "C8.1")
    add_net(g, "GND", "C8.2")
    project.save_graph(g)
    part = project.part("C49678")
    part["values"]["dielectric"] = "X7R"
    project.save_part("C49678", part)
    hints = {(f.code, f.place) for f in found(project, "HINT.signal_ceramic") + found(project, "HINT.audio_ground")}
    assert hints == {("HINT.signal_ceramic", "C8"), ("HINT.audio_ground", "LS1")}


# --- guitar ------------------------------------------------------------------------------------------------------------
def preamp(project, bias_ohm=470e3, follower=True):
    """U8 as an op-amp on +5V: +IN on the instrument input GTR_IN (a pickup that wants at least 1 MΩ), biased by R8
    to GND; a follower (OUT joined to -IN), or a gain of 2 with R9/R10."""
    project.save_part("C9000603", OPAMP)
    project.use_library_part("C17414")
    r = project.part("C17414")
    r.update(lcsc="C9000604", mpn=f"test {bias_ohm:g}")
    r["values"]["value_ohm"] = bias_ohm
    project.save_part("C9000604", r)
    g = project.graph()
    g["graph"]["components"] += [
        {"designator": "U8", "type": "ic", "lcsc": "C9000603", "pins": {n: i["name"] for n, i in OPAMP["pins"].items()}},
        {"designator": "R8", "type": "resistor", "lcsc": "C9000604", "value": "470k", "pins": {"1": "1", "2": "2"}}]
    add_net(g, "GTR_IN", "U8.3", "R8.1", instrument="pickup", load_min_ohm=1e6)
    add_net(g, "GND", "R8.2", "U8.4")
    add_net(g, "+5V", "U8.5")
    if follower:
        add_net(g, "PRE_OUT", "U8.1", "U8.2")
    else:
        g["graph"]["components"] += [
            {"designator": d, "type": "resistor", "lcsc": "C17414", "value": "10k", "pins": {"1": "1", "2": "2"}}
            for d in ("R9", "R10")]
        add_net(g, "PRE_OUT", "U8.1", "R9.1")
        add_net(g, "PRE_FB", "U8.2", "R9.2", "R10.1")
        add_net(g, "GND", "R10.2")
    project.save_graph(g)
    return g


def test_the_pickup_is_loaded_too_much(project):
    preamp(project)
    assert "guitar" in profile.suggested(Design.from_config(project.config()))
    assert [f.text for f in found(project, "REQ.value", "instrument")] == [
        "GTR_IN: the pickup sees 470 kΩ – it wants at least 1 MΩ"]
    preamp_ok = project.part("C9000604")
    preamp_ok["values"]["value_ohm"] = 2.2e6
    project.save_part("C9000604", preamp_ok)
    assert found(project, "REQ.value", "instrument") == []


def test_below_the_stable_gain(project):
    preamp(project)                                          # a follower: gain 1 against 10
    assert [f.text for f in found(project, "REQ.value", "gain")] == [
        "U8: closed-loop gain 1 – the part is stable from 10"]


def test_a_gain_of_two_is_still_below(project):
    preamp(project, follower=False)
    assert [f.text for f in found(project, "REQ.value", "gain")] == [
        "U8: closed-loop gain 2 – the part is stable from 10"]


def test_guitar_hints(project):
    preamp(project)
    places = {(f.code, f.place) for f in found(project, "HINT.string_ground") + found(project, "HINT.pedal_supply")}
    assert ("HINT.string_ground", "GTR_IN") in places and ("HINT.pedal_supply", "J1") in places
