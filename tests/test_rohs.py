"""PARTS.fact/rohs: every part the BOM lists states its RoHS status (compliance.rohs, handbook 4.1 and 15.3) – a check
candidate of the review at the order (implementation plan 5.5), built on the owner's word of 2026-11-01. Graded by
purpose.use as the radio statement (handbook 15.4): a warning for a board that is sold, information otherwise. The
example's parts state it (LCSC's product data); the tests take it out again. J1 is soldered by hand (bom: false) and is
the regulatory review's alone."""

import pytest

from test_radio import GRADES, found, purpose, run

BOM = ["C17414", "C17604", "C2297", "C318884", "C41407547", "C45783", "C49678", "C8678", "C90107"]   # without J1's


def rohs_of(project, value, keys=BOM):
    for key in keys:
        part = project.part(key)
        part.setdefault("compliance", {})["rohs"] = value
        project.save_part(key, part)


def unstated(project, keys=BOM):
    for key in keys:
        part = project.part(key)
        del part["compliance"]["rohs"]
        project.save_part(key, part)


def keys(messages):
    return sorted(m.split()[0] for m in messages if "states no RoHS status" in m)


@pytest.mark.parametrize("use, where", GRADES)
def test_a_bom_part_without_a_rohs_status(project, use, where):
    purpose(project, use)
    assert keys(sum(found(run(project), "PARTS.fact").values(), [])) == []    # the example states it
    unstated(project)
    rep = run(project)
    assert rep.errors == [] and rep.pending == []
    assert keys(found(rep, "PARTS.fact")[where]) == BOM                      # J1 (bom: false) is not asked
    assert "C2297 KT-0805G (D2, D3, D4, D5, D6, D7, D8, D9) states no RoHS status – compliance.rohs in its parts " \
           "entry: true, false or the exemption" in " ".join(found(rep, "PARTS.fact")[where])


def test_true_false_or_an_exemption_is_a_status(project):
    rohs_of(project, False, ["C2297"])                                        # not compliant: a status, M-6 judges it
    rohs_of(project, "6(c) – copper alloy with up to 4 % lead", ["C318884"])
    assert keys(sum(found(run(project), "PARTS.fact").values(), [])) == []


def test_waived_on_a_component_of_the_entry(project):
    unstated(project, ["C49678"])
    purpose(project, "sale")
    g = project.graph()
    project.comp(g, "C1")["accept"] = {"PARTS.fact": "test: the capacitor's RoHS statement is in the technical file"}
    project.save_graph(g)
    rep = run(project)
    assert keys(found(rep, "PARTS.fact")["warnings"]) == [] and found(rep, "PARTS.fact")["waived"]


def test_without_the_bom_flag_no_status_is_asked(project):
    unstated(project)
    g = project.graph()
    for c in g["graph"]["components"]:
        c["bom"] = False
    project.save_graph(g)
    assert keys(sum(found(run(project), "PARTS.fact").values(), [])) == []
