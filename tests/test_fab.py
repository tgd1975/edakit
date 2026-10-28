"""Pieces of stages L and F that work on files: hole vs lead (L-9), loop length (L-11), Gerber parsing (L-2)."""

import json

import pytest

from edakit import gerber
from edakit.release import fab


def test_hole_fits_nominal_lead():
    lead = {"shape": "square", "a_mm": 0.5, "b_mm": 0.5, "tol_mm": None}
    ok, tight, _ = fab.hole_ok(lead, 0.9, 0.9)          # diagonal 0.71, worst case 0.82
    assert ok and not tight


def test_hole_too_small_fails():
    lead = {"shape": "square", "a_mm": 0.5, "b_mm": 0.5}
    ok, _, text = fab.hole_ok(lead, 0.7, 0.7)
    assert not ok and "worst case" in text


def test_hole_tight_in_worst_case_warns():
    lead = {"shape": "round", "a_mm": 0.6, "tol_mm": 0.05}
    ok, tight, _ = fab.hole_ok(lead, 0.65, 0.65)
    assert ok and tight


def test_manufacturer_recommendation_counts():
    lead = {"shape": "square", "a_mm": 0.64, "b_mm": 0.64, "hole_rec_mm": 0.9}
    ok, tight, _ = fab.hole_ok(lead, 0.9, 0.9)
    assert ok and not tight


def test_loop_length_over_tracks():
    data = {"components": [{"designator": "L1", "pads": [{"PadNumber": "2", "X": 0, "Y": 0, "Net": "SW", "Layer": 1}]},
                           {"designator": "U1", "pads": [{"PadNumber": "1", "X": 1000, "Y": 0, "Net": "SW", "Layer": 1}]}],
            "lines": [{"Net": "SW", "Layer": 1, "StartX": 0, "StartY": 0, "EndX": 500, "EndY": 500, "LineWidth": 20},
                      {"Net": "SW", "Layer": 1, "StartX": 500, "StartY": 500, "EndX": 1000, "EndY": 0, "LineWidth": 20}]}
    mm = fab.loop_length_mm(data, "L1.2", "U1.1")
    assert mm == pytest.approx(2 * 707.1 * 0.0254, abs=0.2)
    data["lines"].pop()
    assert fab.loop_length_mm(data, "L1.2", "U1.1") is None


GTL = """%FSLAX46Y46*%
%MOMM*%
%ADD10C,1.000000*%
%ADD11R,1.000000X1.000000*%
%ADD12C,0.300000*%
D11*
X0Y0D03*
X5000000Y0D03*
X20000000Y0D03*
D12*
X0Y0D02*
X5000000Y0D01*
M02*
"""


def test_copper_connectivity_from_gerber(tmp_path):
    (tmp_path / gerber.FILES["top"]).write_text(GTL)
    (tmp_path / gerber.FILES["bottom"]).write_text("%FSLAX46Y46*%\n%MOMM*%\nM02*\n")
    (tmp_path / gerber.FILES["pth"]).write_text("M48\nT01C0.300\n%\nT01\nX30.0Y30.0\nM30\n")
    fields = ["PIN_NAME", "PIN_X", "PIN_Y", "NET_NAME", "PIN_TYPE", "LAYER", "PAD_SIZEX", "PAD_SIZEY"]
    mil = 1 / 0.0254
    rows = [["R1_1", 0, 0, "N1", "SMD", "T", 39, 39], ["R2_1", 5 * mil, 0, "N1", "SMD", "T", 39, 39],
            ["R3_1", 20 * mil, 0, "N1", "SMD", "T", 39, 39]]
    (tmp_path / gerber.FILES["probe"]).write_text(json.dumps({"pins": {"fields": fields, "rows": rows}}))
    cu = gerber.Copper(tmp_path, {"R1.1": "A", "R2.1": "A", "R3.1": "A"})
    groups = cu.net_groups("A")
    assert len(groups) == 2 and ["R1_1", "R2_1"] in groups      # R3 is not connected: the net is open
    assert cu.shorts == []


def test_merge_bom_counts_every_designator_once():
    entries = [{"reference": "C1, C1", "lcsc": "C439782", "quantity": 2},
               {"reference": "R1, R2, R1, R2", "lcsc": "C17630", "quantity": 4},
               {"reference": "R3", "lcsc": "C17630", "quantity": 1}]
    merged = {e["lcsc"]: e for e in fab.merge_bom(entries)}
    assert merged["C439782"]["reference"] == "C1" and merged["C439782"]["quantity"] == 1
    assert merged["C17630"]["reference"] == "R1, R2, R3" and merged["C17630"]["quantity"] == 3


def test_drills_keep_the_ends_of_a_slot(tmp_path):
    f = tmp_path / "Drill_PTH_Through.DRL"
    f.write_text("M48\nT01C1.000\nT02C0.600\n%\nT01\nX3.0Y9.0\nT02\nX1.0Y1.0G85X1.0Y2.0\nM30\n")
    assert gerber.parse_drills(f) == [(3.0, 9.0, 3.0, 9.0, 1.0), (1.0, 1.0, 1.0, 2.0, 0.6)]
    assert gerber.parse_holes(f) == [(3.0, 9.0, 1.0, 1.0), (1.0, 1.5, 0.6, 1.6)]      # centre, width, overall length


def test_annular_ring_is_the_copper_around_the_hole():
    pad = ("flash", (("C", 1.4, 1.4), 0.0, 0.0))
    track = ("draw", (("C", 0.6, 0.6), [(0.0, 0.0), (5.0, 0.0)]))
    parts = [(a.bounds, a) for a in (gerber.shape([op], 64) for op in (pad, track))]
    assert fab.ring_mm(parts, (0.0, 0.0, 0.0, 0.0, 1.0)) == pytest.approx(0.2, abs=1e-4)    # the track leaves it
    assert fab.ring_mm(parts, (0.0, -0.375, 0.0, 0.375, 0.45)) == pytest.approx(0.1, abs=1e-4)   # a slot along y
    assert fab.ring_mm(parts, (3.0, 2.0, 3.0, 2.0, 0.3)) is None                         # no copper there
