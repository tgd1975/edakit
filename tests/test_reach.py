"""PARTS.fact/reach (#95): every part of a board that is given away or sold states its SVHC – compliance.reach, the
supplier's REACH statement. A gift is placing on the market too (REACH Art. 3(12)), and Art. 33(2) asks to name a
substance of very high concern above 0.1 % to a consumer who asks. Graded by purpose (handbook 15.3): information for
a gift, a warning for a sale, nothing for a board built for oneself or without a purpose."""

import pytest

from helpers import check

from edakit import profile
from edakit.design import Design


def run(project):
    cfg = project.config()
    return check(Design.from_config(cfg), cfg)


def reach(rep):
    """{severity: [the keys of the entries PARTS.fact/reach names]}"""
    out = {}
    for f in rep.findings:
        if f.code == "PARTS.fact" and f.grade == "reach":
            out.setdefault(rep.report.profile.of(f), []).append(f.place)
    return out


def purpose(project, use):
    g = project.graph()
    if use is None:
        del g["graph"]["purpose"]
    else:
        g["graph"]["purpose"]["use"] = use
    project.save_graph(g)


def used(project):
    d = Design.from_config(project.config())
    return sorted({d.entry_key(x) for x in d.comps} - {None})


def state_all(project, but=()):
    for key in used(project):
        if key in but:
            continue
        part = project.part(key)
        part.setdefault("compliance", {})["reach"] = "none above 0.1 % (the maker's REACH declaration)"
        project.save_part(key, part)


@pytest.mark.parametrize("use", ["private", None])
def test_a_board_for_oneself_is_not_asked(project, use):
    purpose(project, use)
    assert reach(run(project)) == {}


@pytest.mark.parametrize("use, severity", [("gift", "note"), ("sale", "warning")])
def test_a_board_given_away_or_sold_names_every_part_without_a_statement(project, use, severity):
    purpose(project, use)
    keys = used(project)
    without = [k for k in keys if not ((project.part(k).get("compliance") or {}).get("reach"))]
    assert without                                             # the example's passives state nothing
    assert reach(run(project)) == {severity: without}
    state_all(project, but=[without[0]])
    rep = run(project)
    assert reach(rep) == {severity: [without[0]]}
    msg = next(m for f in rep.findings if f.grade == "reach" for m in [f.text])
    assert "states no SVHC – compliance.reach" in msg and ("a board given away" if use == "gift" else "a board that is sold") in msg
    state_all(project)
    assert reach(run(project)) == {}


def test_an_empty_statement_is_none(project):
    purpose(project, "sale")
    state_all(project)
    key = used(project)[0]
    part = project.part(key)
    part["compliance"]["reach"] = ""
    project.save_part(key, part)
    assert reach(run(project)) == {"warning": [key]}


def test_accepted_on_a_component_of_the_entry(project):
    purpose(project, "gift")
    state_all(project)
    d = Design.from_config(project.config())
    des = sorted(d.comps)[0]
    key = d.entry_key(des)
    part = project.part(key)
    del part["compliance"]["reach"]
    project.save_part(key, part)
    g = project.graph()
    for x in [x for x in d.comps if d.entry_key(x) == key]:
        project.comp(g, x)["accept"] = {"PARTS.fact": "the dealer's statement is asked for"}
    project.save_graph(g)
    rep = run(project)
    assert [(c, m) for c, m, _ in rep.waived if "states no SVHC" in m]
    assert reach(rep) == {"note": [key]}       # still found, but accepted: not among the notes
    assert not [m for c, m in rep.notes if "states no SVHC" in m]


def test_lint_holds_facts_per_purpose_to_the_purposes(monkeypatch):
    files = dict(profile.domains())
    files["core"] = {**files["core"], "facts": {**files["core"]["facts"], "purpose": {"present": ["compliance.reach"]}}}
    monkeypatch.setattr(profile, "domains", lambda: files)
    assert "domains/core.toml: facts.purpose.present – a purpose: private, gift or sale" in profile.lint()
