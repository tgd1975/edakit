"""The radio of a part (compliance.radio, handbook 4.1 and 15): LIM.eirp (#21) compares its e.i.r.p. with the limit of the
band, LIM.band (#22) its bands with the EU's, PARTS.fact (#23) asks modules and microcontrollers for the statement – seen in a copy
of the example, whose Pico 2 (U1) gets the radio of a module for the test.

Graded by purpose.use (the owner's decision of 2026-10-29): what the firmware or the data can settle is a warning for a
board that is sold and information otherwise; an error only where data cannot be read, or where a part can transmit in
no EU band at all (LIM.band)."""

import pytest

from helpers import check

from edakit import checks
from edakit.design import Design
from edakit.release import gate

LEGAL = "(support, not legal advice: no claim to correctness, nothing legally guaranteed)"
NOTHING = {"errors": [], "pending": [], "waived": [], "warnings": [], "notes": []}


def run(project):
    cfg = project.config()
    return check(Design.from_config(cfg), cfg)


def found(rep, *codes):
    return {"errors": [m for c, m in rep.errors if c in codes], "pending": [m for c, m in rep.pending if c in codes],
            "waived": [m for c, m, _ in rep.waived if c in codes], "warnings": [m for c, m in rep.warnings if c in codes],
            "notes": [m for c, m in rep.notes if c in codes]}


def give_radio(project, **radio):
    """U1's parts entry (the Pico 2, C41407547) with compliance.radio – as if it were a module that transmits."""
    part = project.part("C41407547")
    part["compliance"] = {"radio": radio}
    project.save_part("C41407547", part)


def purpose(project, use):
    """purpose.use of the example's graph; None: no purpose at all."""
    g = project.graph()
    if use is None:
        del g["graph"]["purpose"]
    else:
        g["graph"]["purpose"]["use"] = use
    project.save_graph(g)


def state_use(project, **use):
    """purpose.radio of the example's graph: how the firmware uses the radio of each part."""
    g = project.graph()
    g["graph"]["purpose"]["radio"] = use
    project.save_graph(g)


def gate_rows(project, cid):
    cfg = project.config()
    rows, _ = gate.stage_graph(cfg, Design.from_config(cfg))
    return rows, [(r["stage"], r["result"]) for r in rows if r["id"] == cid]


GRADES = [("private", "notes"), ("gift", "notes"), (None, "notes"), ("sale", "warnings")]


# --- LIM.eirp (#21): radio power within the band's limit ------------------------------------------------------------------

def test_g24_the_bells_t_display_is_within_the_limit(project):
    """The proposal's first case: 20.5 dBm at the RF port through a −4.32 dBi PCB antenna is 16.2 dBm e.i.r.p."""
    give_radio(project, bands_mhz=[[2402, 2480], [2412, 2484]], max_dbm=20.5, antenna_dbi=-4.32, doc=None)
    rep = run(project)
    assert found(rep, "LIM.eirp", "PARTS.schema") == NOTHING
    assert rep.errors == [] and rep.pending == []


@pytest.mark.parametrize("use, where", GRADES)
def test_g24_over_the_limit_is_the_firmwares_to_keep(project, use, where):
    """Over the limit: information for a board built for oneself or given away, a warning for one that is sold."""
    purpose(project, use)
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=0)
    rep = run(project)
    assert found(rep, "LIM.eirp")[where] == [
        "U1: 22.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 22 at the RF port + antenna_dbi 0) – the band allows at "
        f"most 100 mW (20.0 dBm) e.i.r.p.: the firmware must keep the conducted power at or below 20.0 dBm {LEGAL}"]
    assert rep.errors == [] and rep.pending == []
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=-2)      # within: exactly 20 dBm
    assert found(run(project), "LIM.eirp") == NOTHING


@pytest.mark.parametrize("use, where", GRADES)
def test_g24_without_the_antenna_gain_the_eirp_is_not_known(project, use, where):
    purpose(project, use)
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5)
    rep = run(project)
    assert rep.errors == [] and rep.pending == []
    assert found(rep, "LIM.eirp")[where] == [
        "U1: e.i.r.p. in 2400–2483.5 MHz not known – parts entry C41407547 has no antenna_dbi (the gain of its antenna, "
        "from the module's datasheet or a certificate) and no eirp_dbm (the e.i.r.p. a certificate states) " + LEGAL]
    give_radio(project, bands_mhz=[[2412, 2472]])
    assert found(run(project), "LIM.eirp")[where][0].startswith(
        "U1: e.i.r.p. in 2400–2483.5 MHz not known – parts entry C41407547 has no max_dbm (the conducted power at the "
        "RF port), no antenna_dbi (")


def test_g24_eirp_of_a_certificate_comes_first(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=10, antenna_dbi=0, eirp_dbm=21)
    assert found(run(project), "LIM.eirp")["notes"] == [
        "U1: 21.0 dBm e.i.r.p. in 2400–2483.5 MHz (eirp_dbm of the parts entry) – the band allows at most 100 mW "
        f"(20.0 dBm) e.i.r.p.: the firmware must lower the power by at least 1.0 dB {LEGAL}"]
    give_radio(project, bands_mhz=[[2412, 2472]], eirp_dbm=19)                    # no max_dbm needed with it
    assert found(run(project), "LIM.eirp") == NOTHING


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
    assert [m.split(" (", 1)[0].split(" in ", 1)[1] for m in found(rep, "LIM.eirp")["notes"]] == over


def test_g24_a_band_without_an_eirp_limit_needs_no_power(project):
    give_radio(project, bands_mhz=[[868, 868.6]])
    assert found(run(project), "LIM.eirp", "PARTS.schema") == NOTHING


def test_g24_waived_on_the_component(project):
    purpose(project, "sale")
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=0)
    g = project.graph()
    project.comp(g, "U1")["accept"] = {"LIM.eirp": "firmware limits the power to 17 dBm (D-5)"}
    project.save_graph(g)
    assert found(run(project), "LIM.eirp") == {**NOTHING, "waived": [
        "U1: 22.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 22 at the RF port + antenna_dbi 0) – the band allows at "
        f"most 100 mW (20.0 dBm) e.i.r.p.: the firmware must keep the conducted power at or below 20.0 dBm {LEGAL}"]}


def test_g24_every_radio_of_an_own_board(project):
    """The entry of an own board lists the radios of its parts (edakit part datasheet, 4.5)."""
    part = project.part("C41407547")
    part["compliance"] = {"radio": [{"part": "U1", "bands_mhz": [[2412, 2472]], "max_dbm": 20, "antenna_dbi": 3},
                                    {"part": "U3", "bands_mhz": [[868, 868.6]], "max_dbm": 14}]}
    project.save_part("C41407547", part)
    assert found(run(project), "LIM.eirp")["notes"] == [
        "U1: 23.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 20 at the RF port + antenna_dbi 3) – the band allows at "
        f"most 100 mW (20.0 dBm) e.i.r.p.: the firmware must keep the conducted power at or below 17.0 dBm {LEGAL}"]


def test_g24_radio_data_that_cannot_be_read_is_an_error(project):
    purpose(project, "private")
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm="20.5", antenna_dbi=-4.32)
    assert found(run(project), "LIM.eirp", "PARTS.schema")["errors"] == [
        "U1: compliance.radio of parts entry C41407547: max_dbm '20.5' is no number"]
    give_radio(project, bands_mhz=[[2484, 2412]], max_dbm=20.5, antenna_dbi=-4.32)
    assert found(run(project), "LIM.eirp", "PARTS.schema")["errors"] == [
        "U1: compliance.radio of parts entry C41407547: bands_mhz [[2484, 2412]] – a list of [from, to] in MHz, "
        "from <= to"]
    give_radio(project, max_dbm=20.5, antenna_dbi=-4.32)                       # no bands: not wrong, only missing
    rep = run(project)
    assert rep.errors == [] and rep.pending == [] and found(rep, "LIM.eirp", "PARTS.schema")["notes"] == [
        "U1: compliance.radio of parts entry C41407547 states no bands_mhz – the bands it transmits in, [[from, to], "
        f"…] in MHz {LEGAL}"]


def test_g24_in_the_gate_information_or_a_warning_to_accept(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=22, antenna_dbi=0)
    rows, g24 = gate_rows(project, "LIM.eirp")
    assert g24 == [("G", "info"), ("G", "pass")]
    assert gate.decide(rows, [], {"manual": []}, "PGESLF", gate.STAGES) == ("RELEASED", [])
    purpose(project, "sale")
    rows, g24 = gate_rows(project, "LIM.eirp")
    assert g24 == [("G", "warn"), ("G", "pass")]
    assert gate.decide(rows, [], {"manual": []}, "PGESLF", gate.STAGES)[1] == ["1 warning(s) not accepted (section 3)"]
    signoff = {"manual": [], "accept": [{"match": "LIM.eirp U1: *", "scope": "decision",
                                                    "reason": "D-5: the firmware keeps 17 dBm"}]}
    assert gate.decide(rows, [], signoff, "PGESLF", gate.STAGES) == ("RELEASED", [])


# --- LIM.band (#22): a transmitter stays in the EU bands, or the graph says how it is used --------------------------------

ESP32 = {"bands_mhz": [[2402, 2480], [2412, 2484]], "max_dbm": 20.5, "antenna_dbi": -4.32, "doc": None}
REACHES_14 = ("U1: 2412–2484 MHz (bands_mhz of parts entry C41407547) reaches beyond the EU band 2400–2483.5 MHz – the "
              "firmware must keep to 2400–2483.5 MHz (for Wi-Fi: channels 1–13); purpose.radio can state that it does "
              + LEGAL)


@pytest.mark.parametrize("use, where", GRADES)
def test_g25_the_bells_t_display_reaches_channel_14(project, use, where):
    """The proposal's finding: bands_mhz up to 2484 MHz. The firmware keeps to channels 1–13 – information for the
    bell (private), a warning for a board that is sold; with the statement in the graph, nothing."""
    purpose(project, use)
    give_radio(project, **ESP32)
    rep = run(project)
    assert found(rep, "LIM.band") == {**NOTHING, where: [REACHES_14]}
    assert rep.errors == [] and rep.pending == []
    if use is None:
        return                                                                  # no purpose: no purpose.radio either
    state_use(project, U1={"bands_mhz": [[2412, 2472]], "notes": "Wi-Fi channels 1–13: country DE, 802.11d off"})
    rep = run(project)
    assert found(rep, "LIM.band") == NOTHING and found(rep, "LIM.eirp", "PARTS.schema") == NOTHING


def test_g25_a_radio_that_stays_off(project):
    give_radio(project, bands_mhz=[[2412, 2484]], max_dbm=22, antenna_dbi=3)     # over in band and power …
    state_use(project, U1="off")                                                # … and never switched on
    rep = run(project)
    assert found(rep, "LIM.band", "STRUCT.purpose", "STRUCT.ref") == NOTHING and found(rep, "LIM.eirp", "PARTS.schema") == NOTHING


@pytest.mark.parametrize("use", ["private", "sale"])
def test_g25_a_lora_chip_for_the_us_band_is_an_error(project, use):
    """No firmware makes a part comply that transmits in no EU band at all: an error, whatever the purpose."""
    purpose(project, use)
    give_radio(project, bands_mhz=[[902, 928]], max_dbm=20)
    assert found(run(project), "LIM.band") == {**NOTHING, "errors": [
        "U1: transmits only in 902–928 MHz (bands_mhz of parts entry C41407547), in no EU licence-exempt band "
        "(433.05–434.79, 863–870, 2400–2483.5, 5150–5350, 5470–5725 MHz) – no firmware makes it comply: choose a part "
        f"made for the EU bands, keep it off (purpose.radio), or accept LIM.band with the allocation of a licensed use {LEGAL}"]}
    state_use(project, U1="off")                                                # kept off: the firmware's to keep
    assert found(run(project), "LIM.band")["notes" if use == "private" else "warnings"] == [
        "U1: transmits only in 902–928 MHz (bands_mhz of parts entry C41407547), in no EU licence-exempt band – "
        f"purpose.radio keeps it off: the firmware must never switch it on {LEGAL}"]


def test_g25_waived_for_a_licensed_use(project):
    give_radio(project, bands_mhz=[[880, 915], [1710, 1785]], max_dbm=33)       # a GSM module: the operator's licence
    g = project.graph()
    project.comp(g, "U1")["accept"] = {"LIM.band": "GSM 900/1800 under the mobile operator's licence"}
    project.save_graph(g)
    rep = run(project)
    assert found(rep, "LIM.band")["errors"] == [] and len(found(rep, "LIM.band")["waived"]) == 1


def test_g25_a_wide_chip_kept_to_868_mhz(project):
    give_radio(project, bands_mhz=[[137, 1020]], max_dbm=20)                     # SX1276: the synthesizer's range
    assert found(run(project), "LIM.band")["notes"] == [
        "U1: 137–1020 MHz (bands_mhz of parts entry C41407547) reaches beyond the EU bands 433.05–434.79 MHz and "
        "863–870 MHz – the firmware must keep to 433.05–434.79 MHz or 863–870 MHz; purpose.radio can state that it does "
        + LEGAL]
    state_use(project, U1={"bands_mhz": [[863, 870]]})
    assert found(run(project), "LIM.band") == NOTHING
    state_use(project, U1={"bands_mhz": [[902, 928]]})                         # the US band stated: the firmware's
    assert found(run(project), "LIM.band")["notes"] == [
        "U1: purpose.radio states 902–928 MHz, in no EU licence-exempt band – the firmware must keep to "
        f"433.05–434.79 MHz or 863–870 MHz {LEGAL}"]


def test_g25_a_stated_band_outside_the_eu_counts_too(project):
    purpose(project, "sale")
    give_radio(project, **ESP32)
    state_use(project, U1={"bands_mhz": [[2412, 2484]]})
    assert found(run(project), "LIM.band") == {**NOTHING, "warnings": [
        "U1: purpose.radio states 2412–2484 MHz, beyond the EU band 2400–2483.5 MHz – the firmware must keep to "
        f"2400–2483.5 MHz (for Wi-Fi: channels 1–13) {LEGAL}"]}


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
def test_g25_a_statement_that_does_not_fit_is_an_error(project, use, msg):
    give_radio(project, **ESP32)
    state_use(project, **use)
    assert msg in found(run(project), "LIM.band", "STRUCT.purpose", "STRUCT.ref")["errors"]


def test_g25_a_statement_that_cannot_be_read_holds_the_entrys_bands(project):
    give_radio(project, **ESP32)
    state_use(project, U1={"bands_mhz": "2412-2472"})
    rep = run(project)
    assert found(rep, "LIM.band", "STRUCT.purpose", "STRUCT.ref")["errors"] == [
        'purpose.radio U1: "off" or {"bands_mhz": [[from, to], …] in MHz, from <= to, "max_dbm": a number (optional)}']
    assert found(rep, "LIM.band", "STRUCT.purpose", "STRUCT.ref")["notes"] == [REACHES_14]


def test_g25_the_power_the_firmware_keeps_counts_for_g24(project):
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5, antenna_dbi=3)
    assert len(found(run(project), "LIM.eirp")["notes"]) == 1                       # 23.5 dBm e.i.r.p.
    state_use(project, U1={"bands_mhz": [[2412, 2472]], "max_dbm": 17})
    rep = run(project)
    assert found(rep, "LIM.eirp") == NOTHING and found(rep, "LIM.band", "STRUCT.purpose", "STRUCT.ref") == NOTHING
    state_use(project, U1={"bands_mhz": [[2412, 2472]], "max_dbm": 18})        # 21 dBm: over again, and said how
    assert found(run(project), "LIM.eirp")["notes"] == [
        "U1: 21.0 dBm e.i.r.p. in 2400–2483.5 MHz (max_dbm 18 kept by the firmware (purpose.radio) + antenna_dbi 3) – "
        f"the band allows at most 100 mW (20.0 dBm) e.i.r.p.: the firmware must keep the conducted power at or below "
        f"17.0 dBm {LEGAL}"]


def test_g25_in_the_gate(project):
    give_radio(project, **ESP32)
    assert gate_rows(project, "LIM.band")[1] == [("G", "info"), ("G", "pass")]       # the bell: information
    purpose(project, "sale")
    assert gate_rows(project, "LIM.band")[1] == [("G", "warn"), ("G", "pass")]
    give_radio(project, bands_mhz=[[902, 928]], max_dbm=20)
    assert gate_rows(project, "LIM.band")[1] == [("G", "fail")]


# --- PARTS.fact (#23): modules and microcontrollers state their radio -------------------------------------------------------

P11_PICO = ("C41407547 Raspberry Pi Pico 2 (U1) states no radio – compliance.radio in its parts entry: its bands and "
            'power, or "none" when it does not transmit; the regulatory review (M-6) reads it')


def no_statement(project):
    part = project.part("C41407547")
    del part["compliance"]
    project.save_part("C41407547", part)


@pytest.mark.parametrize("use, where", GRADES)
def test_p11_a_module_that_states_nothing(project, use, where):
    """The example's Pico 2 states "none"; without it: information, or a warning for a board that is sold."""
    purpose(project, use)
    no_statement(project)
    rep = run(project)
    assert rep.errors == [] and rep.pending == []
    assert found(rep, "PARTS.fact") == {**NOTHING, where: [P11_PICO]}
    g = project.graph()
    project.comp(g, "U1")["type"] = "module"                                    # a module the same
    project.save_graph(g)
    assert found(run(project), "PARTS.fact")[where] == [P11_PICO]


def test_p11_none_or_a_radio_is_a_statement(project):
    assert found(run(project), "PARTS.fact", "PARTS.schema") == NOTHING                              # "none"
    give_radio(project, bands_mhz=[[2412, 2472]], max_dbm=20.5, antenna_dbi=-4.32)
    assert found(run(project), "PARTS.fact", "PARTS.schema") == NOTHING


def test_p11_other_parts_state_it_only_when_they_transmit(project):
    """U2, the TLC5916 (type ic), and the passives state nothing and are not asked for it."""
    assert "compliance" not in project.part("C90107")
    assert found(run(project), "PARTS.fact", "PARTS.schema") == NOTHING


def test_p11_waived_on_a_component_of_the_entry(project):
    no_statement(project)
    g = project.graph()
    project.comp(g, "U1")["accept"] = {"PARTS.fact": "a Pico 2 without the W: no radio on the board"}
    project.save_graph(g)
    assert found(run(project), "PARTS.fact") == {**NOTHING, "waived": [P11_PICO]}


@pytest.mark.parametrize("radio", ["no", [], 5, ["none"]])
def test_p11_a_statement_of_another_shape_is_an_error(project, radio):
    part = project.part("C41407547")
    part["compliance"]["radio"] = radio
    project.save_part("C41407547", part)
    assert found(run(project), "PARTS.schema")["errors"] == [
        f"C41407547 (U1): compliance.radio {radio!r} – \"none\", or its bands and power: {{\"bands_mhz\": [[from, to], "
        "…], \"max_dbm\": …, \"antenna_dbi\": …, \"doc\": …}"]


def test_p11_in_the_gate_stage_p(project):
    no_statement(project)
    rows, p11 = gate_rows(project, "PARTS.fact")
    assert p11 == [("P", "info"), ("P", "pass")]
    assert gate.decide(rows, [], {"manual": []}, "PGESLF", gate.STAGES) == ("RELEASED", [])
    purpose(project, "sale")
    rows, p11 = gate_rows(project, "PARTS.fact")
    assert p11 == [("P", "warn"), ("P", "pass")]
    assert gate.decide(rows, [], {"manual": []}, "PGESLF", gate.STAGES)[1] == ["1 warning(s) not accepted (section 3)"]
    signoff = {"manual": [], "accept": [{"match": "PARTS.fact C41407547 *", "scope": "decision",
                                                    "reason": "D-2: a Pico 2 without radio"}]}
    assert gate.decide(rows, [], signoff, "PGESLF", gate.STAGES) == ("RELEASED", [])
