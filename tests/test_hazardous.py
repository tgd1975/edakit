"""LIM.hazardous (rules-at-scale.md, decision 7): a net beyond the ES1 limit of IEC 62368-1 is hazardous voltage –
recognised, not checked: an error a project accepts on purpose; the domain mains is suggested and carries the
reviewers' questions."""

from helpers import check

from edakit import catalog, profile
from edakit.design import Design


def hazardous(project):
    cfg = project.config()
    rep = check(Design.from_config(cfg), cfg)
    return [(f.place, f.severity, bool(f.accepted), f.text) for f in rep.findings if f.code == "LIM.hazardous"]


def with_vin(project, v, accept=None):
    g = project.graph()
    net = next(n for n in (g.get("graph", g))["nets"] if n["name"] == "VIN")
    net["v"] = v
    if accept:
        net["accept"] = {"LIM.hazardous": accept}
    project.save_graph(g)


def test_safety_extra_low_voltage_raises_nothing(project):
    assert catalog.table("iec62368")["es1"]["dc_v"] == 60
    assert hazardous(project) == []
    with_vin(project, [0, 60])                     # at the limit: still ES1
    assert hazardous(project) == []


def test_a_net_beyond_es1_is_an_error_naming_what_edakit_does_not_check(project):
    with_vin(project, [-325, 325])                 # mains peak, judged against the DC limit
    found = hazardous(project)
    assert [(p, s, a) for p, s, a, _ in found] == [("VIN", "error", False)]
    assert "325 V" in found[0][3] and "ES1 limit of IEC 62368-1 (60 V DC)" in found[0][3]
    assert "spacing and isolation edakit does not check" in found[0][3]


def test_the_finding_is_accepted_on_the_net_with_its_reason(project):
    with_vin(project, [0, 72], accept="72 V only on the bought supply's terminals, enclosure closed")
    assert [(p, s, a) for p, s, a, _ in hazardous(project)] == [("VIN", "error", True)]


def test_the_domain_mains_is_suggested_and_asks_the_reviewers(project):
    cfg = project.config()
    assert "mains" not in profile.suggested(Design.from_config(cfg))
    with_vin(project, [0, 120])
    cfg = project.config()
    assert "mains" in profile.suggested(Design.from_config(cfg))
    review = profile.domains()["mains"]["review"]
    assert review["pcb"] and review["electrical"] and review["regulatory"]
