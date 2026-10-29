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
    assert {c for c, _ in rep.errors} <= {"G-25"} and rep.pending == []          # G-25: its channel 14


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


# --- G-25 (#22): a transmitter stays in the EU bands, or the graph says how it is used --------------------------------

ESP32 = {"bands_mhz": [[2402, 2480], [2412, 2484]], "max_dbm": 20.5, "antenna_dbi": -4.32, "doc": None}


def state_use(project, **use):
    """purpose.radio of the example's graph: how the firmware uses the radio of each part."""
    g = project.graph()
    g["graph"]["purpose"]["radio"] = use
    project.save_graph(g)


def test_g25_the_bells_t_display_reaches_channel_14(project):
    """The proposal's finding: bands_mhz up to 2484 MHz, and edakit check reported nothing."""
    give_radio(project, **ESP32)
    rep = run(project)
    assert found(rep, "G-25")["errors"] == [
        "U1: transmits in 2412–2484 MHz (bands_mhz of parts entry C41407547) – beyond the EU band 2400–2483.5 MHz: "
        f"state the bands the firmware keeps in purpose.radio, or choose a part made for the EU bands {LEGAL}"]
    assert {c for c, _ in rep.errors} == {"G-25"}
    state_use(project, U1={"bands_mhz": [[2412, 2472]], "notes": "Wi-Fi channels 1–13: country DE, 802.11d off"})
    rep = run(project)
    assert rep.errors == [] and rep.pending == []


def test_g25_a_radio_that_stays_off(project):
    give_radio(project, bands_mhz=[[2412, 2484]], max_dbm=22, antenna_dbi=3)     # over in band and power …
    state_use(project, U1="off")                                                # … and never switched on
    rep = run(project)
    assert found(rep, "G-25")["errors"] == [] and found(rep, "G-24")["errors"] == []


def test_g25_a_lora_chip_for_the_us_band(project):
    give_radio(project, bands_mhz=[[902, 928]], max_dbm=20)
    assert found(run(project), "G-25")["errors"] == [
        "U1: transmits in 902–928 MHz (bands_mhz of parts entry C41407547) – in no EU licence-exempt band "
        "(433.05–434.79, 863–870, 2400–2483.5, 5150–5350, 5470–5725 MHz): state the bands the firmware keeps in "
        f"purpose.radio, or choose a part made for the EU bands {LEGAL}"]


def test_g25_a_wide_chip_kept_to_868_mhz(project):
    give_radio(project, bands_mhz=[[137, 1020]], max_dbm=20)                     # SX1276: the synthesizer's range
    assert len(found(run(project), "G-25")["errors"]) == 1
    state_use(project, U1={"bands_mhz": [[863, 870]]})
    assert found(run(project), "G-25")["errors"] == []


def test_g25_a_stated_band_outside_the_eu_counts_too(project):
    give_radio(project, **ESP32)
    state_use(project, U1={"bands_mhz": [[2412, 2484]]})
    assert [m.split(" – ", 1)[0] for m in found(run(project), "G-25")["errors"]] == [
        "U1: transmits in 2412–2484 MHz (purpose.radio)"]


@pytest.mark.parametrize("use, msg", [
    ({"U1": {"bands_mhz": [[868, 870]]}},
     "purpose.radio U1: 868–870 MHz is no band of parts entry C41407547 (bands_mhz 2402–2480, 2412–2484 MHz)"),
    ({"U9": "off"}, "purpose.radio: no part U9 in the graph"),
    ({"U2": "off"}, "purpose.radio U2: parts entry C90107 states no bands_mhz to keep to"),
    ({"U1": "on"}, 'purpose.radio U1: "off" or {"bands_mhz": [[from, to], …] in MHz, from <= to, "max_dbm": a number '
                   '(optional)}'),
    ({"U1": {"bands_mhz": [[2412, 2472]], "max_dbm": "17"}},
     'purpose.radio U1: "off" or {"bands_mhz": [[from, to], …] in MHz, from <= to, "max_dbm": a number (optional)}'),
])
def test_g25_a_statement_that_does_not_fit(project, use, msg):
    give_radio(project, **ESP32)
    state_use(project, **use)
    assert msg in found(run(project), "G-25")["errors"]


def test_g25_a_statement_that_cannot_be_read_holds_the_entrys_bands(project):
    give_radio(project, **ESP32)
    state_use(project, U1={"bands_mhz": "2412-2472"})
    assert sorted(m.split(" – ", 1)[0] for m in found(run(project), "G-25")["errors"]) == [
        "U1: transmits in 2412–2484 MHz (bands_mhz of parts entry C41407547)",
        'purpose.radio U1: "off" or {"bands_mhz": [[from, to], …] in MHz, from <= to, "max_dbm": a number (optional)}']


def test_g25_the_power_the_firmware_keeps_counts_for_g24(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5, antenna_dbi=3)
    assert len(found(run(project), "G-24")["errors"]) == 1                      # 23.5 dBm e.i.r.p.
    state_use(project, U1={"bands_mhz": [[2412, 2472]], "max_dbm": 17})
    rep = run(project)
    assert found(rep, "G-24")["errors"] == [] and found(rep, "G-25")["errors"] == []
    state_use(project, U1={"bands_mhz": [[2412, 2472]], "max_dbm": 18})        # 21 dBm: over again, and said how
    assert found(run(project), "G-24")["errors"] == [
        "U1: 21.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 18 kept by the firmware (purpose.radio) + antenna_dbi 3) – "
        f"the band allows at most 100 mW (20.0 dBm) e.i.r.p. {LEGAL}"]


def test_g25_waived_for_a_licensed_use(project):
    give_radio(project, bands_mhz=[[880, 915], [1710, 1785]], max_dbm=33)       # a GSM module: the operator's licence
    g = project.graph()
    project.comp(g, "U1")["waive"] = {"G-25": "GSM 900/1800 under the mobile operator's licence"}
    project.save_graph(g)
    rep = run(project)
    assert found(rep, "G-25")["errors"] == [] and len(found(rep, "G-25")["waived"]) == 2


def test_g25_runs_in_the_gate_stage_g(project):
    from edakit.release import gate
    give_radio(project, **ESP32)
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    assert [(r["stage"], r["result"]) for r in rows if r["id"] in ("G-24", "G-25")] == [("G", "fail"), ("G", "pass")]


# --- P-11 (#23): modules and microcontrollers state their radio -------------------------------------------------------

def test_p11_a_module_that_states_nothing_is_open_for_the_release(project):
    """The example's Pico 2 states "none"; without it the release waits for the statement, like an unsigned part."""
    part = project.part("C41407547")
    del part["compliance"]
    project.save_part("C41407547", part)
    rep = run(project)
    assert rep.errors == []
    assert found(rep, "P-11")["pending"] == [
        "C41407547 Raspberry Pi Pico 2 (U1) states no radio – compliance.radio in its parts entry: its bands and power, "
        'or "none" when it does not transmit; the regulatory review (M-6) reads it']
    g = project.graph()
    project.comp(g, "U1")["type"] = "module"                                    # a module the same
    project.save_graph(g)
    assert len(found(run(project), "P-11")["pending"]) == 1


def test_p11_none_or_a_radio_is_a_statement(project):
    assert found(run(project), "P-11") == {"errors": [], "pending": [], "waived": []}      # "none"
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5, antenna_dbi=-4.32)
    assert found(run(project), "P-11") == {"errors": [], "pending": [], "waived": []}


def test_p11_other_parts_state_it_only_when_they_transmit(project):
    """U2, the TLC5916 (type ic), and the passives state nothing and are not asked for it."""
    assert "compliance" not in project.part("C90107")
    assert found(run(project), "P-11")["pending"] == []


@pytest.mark.parametrize("radio", ["no", [], 5, ["none"]])
def test_p11_a_statement_of_another_shape(project, radio):
    part = project.part("C41407547")
    part["compliance"]["radio"] = radio
    project.save_part("C41407547", part)
    assert found(run(project), "P-11")["errors"] == [
        f"C41407547 (U1): compliance.radio {radio!r} – \"none\", or its bands and power: {{\"bands_mhz\": [[from, to], "
        "…], \"max_dbm\": …, \"antenna_dbi\": …, \"doc\": …}"]


def test_p11_holds_the_release_in_the_gate_stage_p(project):
    from edakit.release import gate
    part = project.part("C41407547")
    del part["compliance"]
    project.save_part("C41407547", part)
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    assert [(r["stage"], r["result"]) for r in rows if r["id"] == "P-11"] == [("P", "pending")]
    decision, reasons = gate.decide(rows, [], {"manual": []}, "PGESLF", gate.STAGES)
    assert decision == "NOT RELEASED" and "1 open sign-off(s) (section 5)" in reasons
