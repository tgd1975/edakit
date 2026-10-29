"""The radio of a part (compliance.radio, handbook 4.1 and 15): G-24 (#21) holds its e.i.r.p. to the limit of the band
– seen red in a copy of the example, whose Pico 2 (U1) gets the radio of a module for the test."""

import pytest

from edakit import checks
from edakit.design import Design

LEGAL = "(support, not legal advice: no claim to correctness, nothing legally guaranteed)"


def run(project):
    cfg = project.config()
    return checks.run(Design.from_config(cfg), cfg)


def found(rep, cid):
    return {"errors": [m for c, m in rep.errors if c == cid], "pending": [m for c, m in rep.pending if c == cid],
            "waived": [m for c, m, _ in rep.waived if c == cid]}


def give_radio(project, **radio):
    """U1's parts entry (the Pico 2, C41407547) with compliance.radio – as if it were a module that transmits."""
    part = project.part("C41407547")
    part["compliance"] = {"radio": radio}
    project.save_part("C41407547", part)


def test_g24_the_bells_t_display_is_within_the_limit(project):
    """The proposal's first case: 20.5 dBm at the RF port through a −4.32 dBi PCB antenna is 16.2 dBm e.i.r.p."""
    give_radio(project, bands_mhz=[[2402, 2480], [2412, 2484]], max_dbm=20.5, antenna_dbi=-4.32, doc=None)
    rep = run(project)
    assert found(rep, "G-24") == {"errors": [], "pending": [], "waived": []}
    assert rep.errors == [] and rep.pending == []


def test_g24_over_the_limit(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=0)
    rep = run(project)
    assert found(rep, "G-24")["errors"] == [
        "U1: 22.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 22 at the RF port + antenna_dbi 0) – the band allows at "
        f"most 100 mW (20.0 dBm) e.i.r.p. {LEGAL}"]
    assert {c for c, _ in rep.errors} == {"G-24"}
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=-2)      # repaired: exactly 20 dBm
    assert found(run(project), "G-24")["errors"] == []


def test_g24_without_the_antenna_gain_the_eirp_is_not_known(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5)
    rep = run(project)
    assert rep.errors == []
    assert found(rep, "G-24")["pending"] == [
        "U1: e.i.r.p. in 2400–2483.5 MHz not known – parts entry C41407547 has no antenna_dbi (the gain of its antenna, "
        "from the module's datasheet or a certificate) and no eirp_dbm (the e.i.r.p. a certificate states) " + LEGAL]
    give_radio(project, bands_mhz=[[2412, 2472]])
    assert found(run(project), "G-24")["pending"][0].startswith(
        "U1: e.i.r.p. in 2400–2483.5 MHz not known – parts entry C41407547 has no max_dbm (the conducted power at the "
        "RF port), no antenna_dbi (")


def test_g24_eirp_of_a_certificate_comes_first(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=10, antenna_dbi=0, eirp_dbm=21)
    assert found(run(project), "G-24")["errors"] == [
        "U1: 21.0 dBm e.i.r.p. in 2400–2483.5 MHz (eirp_dbm of the parts entry) – the band allows at most 100 mW "
        f"(20.0 dBm) e.i.r.p. {LEGAL}"]
    give_radio(project, bands_mhz=[[2412, 2472]], eirp_dbm=19)                    # no max_dbm needed with it
    assert found(run(project), "G-24") == {"errors": [], "pending": [], "waived": []}


@pytest.mark.parametrize("bands, over", [
    ([[5170, 5250]], ["5150–5350 MHz"]),            # 24 dBm over 200 mW (23.0 dBm)
    ([[5500, 5700]], []),                           # within 1 W
    ([[2412, 2472], [5180, 5320]], ["2400–2483.5 MHz", "5150–5350 MHz"]),
    ([[863, 870]], []),                             # an e.r.p. band: left to the regulatory review
    ([[433.05, 434.79]], []),
])
def test_g24_the_bands_with_an_eirp_limit(project, bands, over):
    give_radio(project, bands_mhz=bands, max_dbm=24, antenna_dbi=0)
    rep = run(project)
    assert [m.split(" (", 1)[0].split(" in ", 1)[1] for m in found(rep, "G-24")["errors"]] == over


def test_g24_a_band_without_an_eirp_limit_needs_no_power(project):
    give_radio(project, bands_mhz=[[868, 868.6]])
    assert found(run(project), "G-24") == {"errors": [], "pending": [], "waived": []}


def test_g24_waived_on_the_component(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=0)
    g = project.graph()
    project.comp(g, "U1")["waive"] = {"G-24": "firmware limits the power to 17 dBm (D-5)"}
    project.save_graph(g)
    rep = run(project)
    assert found(rep, "G-24")["errors"] == [] and len(found(rep, "G-24")["waived"]) == 1


def test_g24_every_radio_of_an_own_board(project):
    """The entry of an own board lists the radios of its parts (edakit part datasheet, 4.5)."""
    part = project.part("C41407547")
    part["compliance"] = {"radio": [{"part": "U1", "bands_mhz": [[2412, 2472]], "max_dbm": 20, "antenna_dbi": 3},
                                    {"part": "U3", "bands_mhz": [[868, 868.6]], "max_dbm": 14}]}
    project.save_part("C41407547", part)
    assert found(run(project), "G-24")["errors"] == [
        "U1: 23.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 20 at the RF port + antenna_dbi 3) – the band allows at "
        f"most 100 mW (20.0 dBm) e.i.r.p. {LEGAL}"]


def test_g24_radio_data_that_cannot_be_read(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm="20.5", antenna_dbi=-4.32)
    assert found(run(project), "G-24")["errors"] == [
        "U1: compliance.radio of parts entry C41407547: max_dbm '20.5' is no number"]
    give_radio(project, bands_mhz=[[2484, 2412]], max_dbm=20.5, antenna_dbi=-4.32)
    assert found(run(project), "G-24")["errors"] == [
        "U1: compliance.radio of parts entry C41407547: bands_mhz [[2484, 2412]] – a list of [from, to] in MHz, "
        "from <= to"]
    give_radio(project, max_dbm=20.5, antenna_dbi=-4.32)
    rep = run(project)
    assert rep.errors == [] and found(rep, "G-24")["pending"] == [
        "U1: compliance.radio of parts entry C41407547 states no bands_mhz – the bands it transmits in, [[from, to], "
        f"…] in MHz {LEGAL}"]


def test_g24_runs_in_the_gate_stage_g(project):
    from edakit.release import gate
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=0)
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    assert [(r["stage"], r["result"]) for r in rows if r["id"] == "G-24"] == [("G", "fail")]
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5, antenna_dbi=-4.32)
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    assert [(r["stage"], r["result"]) for r in rows if r["id"] == "G-24"] == [("G", "pass")]
