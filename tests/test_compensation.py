"""The external compensation a part requires (maker-coverage CK-28): the NE5534 (TI SLOS070D) is compensated inside
for a gain of 3 or more; below that its config "compensated" holds it stable from 1 and its COMP pin needs CC ≥ 22 pF
to COMP/BAL – a pin need to another pin (needs.capacitor.to): REQ.missing/pin without it, REQ.value/gain without the
config."""

from test_configs import place

from helpers import check

from edakit.design import Design


def follower(project, config=None, cc=False):
    """NE5534P as U8 on +5V and GND, a follower (OUT on IN−) of BUF_IN; with cc a 100 pF C0G (C1790) across COMP and
    COMP/BAL."""
    nets = {"7": "+5V", "4": "GND", "3": "BUF_IN", "2": "BUF_OUT", "6": "BUF_OUT"}
    if cc:
        nets |= {"5": "CC_A", "8": "CC_B"}
    place(project, "NE5534P", "U8", nets, config=config, extra_nets={"BUF_IN": [1, 4], "BUF_OUT": [1, 4],
                                                                      "CC_A": [0, 5], "CC_B": [0, 5]})
    if cc:
        project.use_library_part("C1790")
        g = project.graph()
        g["graph"]["components"].append({"designator": "C8", "type": "capacitor", "lcsc": "C1790", "value": "100pF",
                                         "pins": {"1": "1", "2": "2"}})
        project.net(g, "CC_A")["pins"].append("C8.1")
        project.net(g, "CC_B")["pins"].append("C8.2")
        project.save_graph(g)


def found(project, code, grade):
    cfg = project.config()
    return [f for f in check(Design.from_config(cfg), cfg).findings
            if f.code == code and f.grade == grade and f.place.startswith("U8")]


def test_a_follower_below_the_internal_compensation(project):
    follower(project)
    gain = found(project, "REQ.value", "gain")
    assert [f.text for f in gain] == ["U8: closed-loop gain 1 – the part is stable from 3"]
    assert "its config 'compensated' – stable from 1" in gain[0].fix


def test_compensated_without_its_capacitor(project):
    follower(project, config="compensated")
    assert found(project, "REQ.value", "gain") == []
    missing = found(project, "REQ.missing", "pin")
    assert [f.place for f in missing] == ["U8.5 (COMP)"]
    assert "needs a capacitor of at least 22 pF" in missing[0].text


def test_compensated_with_its_capacitor(project):
    follower(project, config="compensated", cc=True)
    assert found(project, "REQ.missing", "pin") == [] and found(project, "REQ.value", "gain") == []
    assert found(project, "REQ.value", "pin") == []
