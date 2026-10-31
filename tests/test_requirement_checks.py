"""Requirements in edakit check and the gate (handbook 3.6, 8.7): the checks G-20 to G-23 on the requirements file,
each requirement's evidence evaluated against the gate run, the acceptance steps on the list of section 6, the file
in the circuit hash – and no change for a project without [project] requirements."""

import json
import re
import sys

import pytest
from test_gate import ALL, decision, gate_run, rows, section
from test_requirements import LED_BAR, variant_of, with_requirements

from helpers import check as engines_check

from edakit import engines, cli, requirements, scripts
from edakit.design import Design
from edakit.release import gate

REQUIREMENT_CHECKS = ("DOCS.ref", "DOCS.need", "DOCS.evidence", "DOCS.draft")


def rewrite(project, old, new):
    """The requirements file with old replaced by new (once)."""
    path = project.root / "hardware" / "requirements.toml"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def found(project):
    """(errors, warnings) of G-20 to G-23 in the example's edakit check, each as (ID, message) – the warnings as edakit
    check prints them, the findings about a draft included."""
    cfg = project.config()
    rep = engines_check(Design.from_config(cfg), cfg)
    mine = lambda items: [(c, m) for c, m in items if c in REQUIREMENT_CHECKS]   # noqa: E731
    return mine(rep.errors), mine(rep.warnings + rep.drafts)


def check(project, capsys):
    """`edakit check` on the example: (exit code, stdout, stderr)."""
    code = cli.main(["check", "--config", str(project.root / "edakit.toml")])
    out = capsys.readouterr()
    return code, out.out, out.err


# --- the checks G-20 to G-23 in edakit check (and in the gate's stage G) ----------------------------------------------

def test_the_example_is_clean_but_for_its_draft(project):
    """LED_BAR: every reference resolves, every accepted need has a requirement, every requirement evidence; R-4 is a
    draft and warns until the user accepts it."""
    with_requirements(project)
    errors, warnings = found(project)
    assert errors == []
    assert [(c, m.split(" – ")[0]) for c, m in warnings] == [("DOCS.draft", "R-4: a draft")]
    rewrite(project, 'status = "draft"', 'status = "accepted"')
    assert found(project) == ([], [])


@pytest.mark.parametrize("old, new, message", [
    # from: a need or a requirement (N-…, R-…) of the file, a manual check (M-…) of the sign-off file
    ('from = ["N-1", "USB 2.0', 'from = ["N-9", "USB 2.0', "R-1: from N-9 – not in the requirements file"),
    ('from = ["N-2"]', 'from = ["N-2", "R-9"]', "R-3: from R-9 – not in the requirements file"),
    ('from = ["N-3"]', 'from = ["N-3", "M-9"]', "R-4: from M-9 – no manual check M-9 in hardware/signoff.json "
                                               "(M-1, M-6, M-5, M-2, M-4)"),
    # verify: the check a rows pattern starts with, a manual check, a project script
    ('{ rows = "PATH.reverse *" }', '{ rows = "XYZ.nope *" }', "R-2: verify rows 'XYZ.nope *' – XYZ.nope is not a code of the "
                                                            "catalog (edakit rules)"),
    ('{ rows = "PATH.reverse *" }', '{ rows = "G-10 *" }', "R-2: verify rows 'G-10 *' – G-10 is a check ID of before the "
                                                        "restructuring – now PATH.reverse"),
    ('{ signoff = "M-1" }', '{ signoff = "M-7" }', "R-4: verify signoff M-7 – no manual check M-7 in "
                                                  "hardware/signoff.json (M-1, M-6, M-5, M-2, M-4)"),
    ('{ rows = "PATH.reverse *" }', '{ script = "rule-watcher" }', "R-2: verify script rule-watcher – no [scripts.rule-watcher] "
                                                          "of kind check and no [[release.stages]] id rule-watcher in "
                                                          "edakit.toml"),
])
def test_g20_every_reference_resolves(project, old, new, message):
    with_requirements(project)
    rewrite(project, 'status = "draft"', 'status = "accepted"')                 # R-4: a draft only warns
    rewrite(project, old, new)
    errors, _ = found(project)
    assert errors == [("DOCS.ref", message)]
    rewrite(project, new, old)
    assert found(project)[0] == []


def test_g20_what_edakit_cannot_resolve_is_not_a_finding(project):
    """Decisions, standards and free text in from, a rows pattern that starts with a wildcard or a project stage's ID,
    another requirement in from: nothing to report."""
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-2", "D-8", "R-1", "IEC 62368-1", "M-6"]')
    rewrite(project, '{ rows = "PATH.reverse *" }', '{ rows = "* reverse polarity" }, { rows = "K-1 enclosure *" }')
    assert found(project)[0] == []


def test_g20_a_script_must_be_a_check(project):
    """verify script names a [scripts.<name>] of kind check, or the id of a [[release.stages]]."""
    with_requirements(project)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + '\n[scripts.pins]\nkind = "derive"\ncmd = ["python3", "pins.py"]\n'
                    'about = "pin table"\nwrites = ["firmware/pins.h"]\n'
                    '\n[scripts.watch]\nkind = "check"\ncmd = ["python3", "watch.py"]\nabout = "rule watcher"\n'
                    'id = "W"\nphase = "export"\n'
                    '\n[[release.stages]]\nid = "K"\nname = "Mechanics"\ncmd = ["python3", "-c", "print(1)"]\n')
    rewrite(project, '{ rows = "PATH.reverse *" }', '{ script = "pins" }')
    assert found(project)[0] == [("DOCS.ref", "R-2: verify script pins – [scripts.pins] is of kind derive; evidence "
                                          "comes from a check")]
    rewrite(project, '{ script = "pins" }', '{ script = "watch" }, { script = "K" }')
    assert found(project)[0] == []


def test_g20_from_a_dropped_need_warns(project):
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-2", "N-4"]')
    errors, warnings = found(project)
    assert errors == []
    assert ("DOCS.ref", "R-3: from N-4 – dropped: the TLC5916 and the Pico 2 want 5 V: a cell needs a boost converter, "
                    "which the example does not have") in warnings


def test_a_dropped_requirement_is_not_checked(project):
    """A dropped entry stays for the record: no evidence needed, its references are history."""
    with_requirements(project)
    rewrite(project, 'verify = [{ rows = "PATH.reverse *" }]\nstatus = "accepted"',      # R-2: no evidence, a broken from
            'status = "dropped"\nreason = "D-2: no longer wanted"')
    rewrite(project, 'from = ["N-1"]\nbinding = "must"', 'from = ["N-9"]\nbinding = "must"')
    errors, warnings = found(project)
    assert errors == [] and [m.split(" – ")[0] for _, m in warnings] == ["R-4: a draft"]


def test_g21_every_accepted_need_has_a_requirement(project):
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-1"]')                       # R-3 was N-2's only requirement
    assert found(project)[0] == [("DOCS.need", "N-2: accepted, but no requirement names it in from")]
    rewrite(project, 'from = ["N-1"]\nbinding = "should"', 'from = ["N-2"]\nbinding = "should"')
    assert found(project)[0] == []
    # a dropped requirement does not count
    rewrite(project, 'verify = [{ rows = "SIM.state * D? LED current *" }]\nstatus = "accepted"',
            'verify = [{ rows = "SIM.state * D? LED current *" }]\nstatus = "dropped"\nreason = "D-3: any brightness"')
    assert found(project)[0] == [("DOCS.need", "N-2: accepted, but no requirement names it in from")]


def test_g21_only_for_accepted_needs(project):
    """A draft need without a requirement only warns as a draft; a dropped one needs none."""
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-1"]')
    rewrite(project, 'source = "README.md"\nstatus = "accepted"', 'source = "README.md"\nstatus = "draft"')   # N-2
    errors, warnings = found(project)
    assert errors == [] and [m.split(" – ")[0] for _, m in warnings] == ["N-2: a draft", "R-4: a draft"]


def test_g22_every_requirement_has_evidence(project):
    with_requirements(project)
    rewrite(project, 'verify = [{ rows = "PATH.reverse *" }]\n', "")
    assert found(project)[0] == [("DOCS.evidence", "R-2: no evidence – verify names nothing that tests it")]
    rewrite(project, 'from = ["N-1"]\nbinding = "must"\nstatus', 'from = ["N-1"]\nbinding = "must"\nverify = []\nstatus')
    assert found(project)[0] == [("DOCS.evidence", "R-2: no evidence – verify names nothing that tests it")]


def test_g23_drafts_warn(project):
    """A need or requirement without status is a draft too."""
    with_requirements(project)
    rewrite(project, 'source = "README.md"\nstatus = "accepted"\n', 'source = "README.md"\n')     # N-2
    errors, warnings = found(project)
    assert errors == []
    assert [m.split(" – ")[0] for c, m in warnings if c == "DOCS.draft"] == ["N-2: a draft", "R-4: a draft"]
    assert warnings[0][1] == ('N-2: a draft – the user has not approved it (status "accepted", or "dropped" with a '
                              'reason)')


def test_edakit_check_reports_and_explains_them(project, capsys):
    with_requirements(project)
    code, out, _ = check(project, capsys)
    assert code == 0                                                    # a draft only warns
    assert "DOCS.draft – draft not approved: 1 warning" in out and "  G  R-4: a draft" in out
    assert re.search(r"\n\d+ components, .*; requirements: 4 needs, 4 requirements", out)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-1"]')
    code, out, _ = check(project, capsys)
    assert code == 1
    assert "DOCS.need – accepted need has a requirement: 1 error" in out
    assert "  G  N-2: accepted, but no requirement names it in from" in out
    assert "  DOCS.need: Write the requirement" in out.split("What to do")[1]


DRAFT = " (draft: an error once accepted)"


@pytest.mark.parametrize("old, new, finding", [
    # G-22: a draft without evidence yet – the file is unfinished, and the pre-commit hook lets it pass
    ('verify = [{ rows = "SIM.state * D? LED dark" }, { signoff = "M-1" }]\n', "",
     "R-4: no evidence – verify names nothing that tests it"),
    # G-20: a draft's reference that does not resolve, in verify and in from
    ('{ signoff = "M-1" }', '{ signoff = "M-7" }',
     "R-4: verify signoff M-7 – no manual check M-7 in hardware/signoff.json (M-1, M-6, M-5, M-2, M-4)"),
    ('from = ["N-3"]', 'from = ["N-3", "N-9"]', "R-4: from N-9 – not in the requirements file"),
])
def test_a_finding_about_a_draft_only_warns(project, capsys, old, new, finding):
    """Decided 2026-10-28: a draft never blocks. What is an error for an accepted requirement is a warning while it is
    a draft – edakit check exits 0. Once the user accepts it, it is an error."""
    with_requirements(project)
    rewrite(project, old, new)
    code, out, _ = check(project, capsys)
    assert code == 0 and f"  G  {finding}{DRAFT}\n" in out and " error" not in out.splitlines()[-1]
    assert "  G  R-4: a draft" in out
    rewrite(project, 'status = "draft"', 'status = "accepted"')
    code, out, _ = check(project, capsys)
    assert code == 1 and f"  G  {finding}\n" in out and "DOCS.draft" not in out


def test_findings_about_a_draft_are_information_in_the_gate(project):
    """In the gate's stage G a finding about a draft is information: it needs no acceptance and fails nothing – a
    draft's reference to a dropped need included. graph_checks.json keeps them as edakit check reports them."""
    with_requirements(project)
    rewrite(project, '{ signoff = "M-1" }', '{ signoff = "M-7" }')                 # R-4, a draft
    rewrite(project, 'from = ["N-3"]', 'from = ["N-3", "N-4"]')
    cfg = project.config()
    rows, raw = gate.stage_graph(cfg, Design.from_config(cfg))
    mine = [(r["id"], r["result"], r["check"].split(" – ")[0]) for r in rows
            if r["id"] in REQUIREMENT_CHECKS and r["result"] != "pass"]
    assert sorted(mine) == [("DOCS.draft", "info", "R-4: a draft"), ("DOCS.ref", "info", "R-4: from N-4"),
                            ("DOCS.ref", "info", "R-4: verify signoff M-7")]
    assert sorted(f["code"] for f in raw["findings"] if f["code"] in REQUIREMENT_CHECKS
                  and f.get("data", {}).get("draft")) == ["DOCS.draft", "DOCS.ref", "DOCS.ref"]
    assert gate.decide(rows, [], {"manual": [], "accept": []}, ALL, gate.STAGES) == ("RELEASED", [])


def test_a_broken_or_missing_file_stops_check_and_gate(project, capsys, monkeypatch):
    """A file that [project] requirements names stops edakit check and the gate when it is not valid or not there –
    the gate before it writes a run."""
    with_requirements(project, LED_BAR.replace('binding = "should"', 'binding = "shall"'))
    code, out, err = check(project, capsys)
    assert code == 1 and "ERROR" not in out
    assert "edakit check: hardware/requirements.toml:\n  R-3: binding must be must, should or may, not 'shall'" in err
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["gate"]) == 1
    assert "edakit gate: hardware/requirements.toml:\n  R-3: binding" in capsys.readouterr().err
    assert not (project.root / "build" / "release").exists()
    (project.root / "hardware" / "requirements.toml").unlink()
    code, _, err = check(project, capsys)
    assert code == 1 and "hardware/requirements.toml: not found – named in [project] requirements" in err
    assert cli.main(["gate"]) == 1 and "not found" in capsys.readouterr().err


# --- each requirement's evidence in the gate --------------------------------------------------------------------------

def entries(tmp_path, text):
    path = tmp_path / "requirements.toml"
    path.write_text(text, encoding="utf-8")
    read, bad = requirements.read(path)
    assert not bad, bad
    return read


def requirement(binding, *verify, rid="R-1"):
    items = ", ".join(f'{{ {kind} = "{text}" }}' for kind, text in verify)
    return f'[[requirement]]\nid = "{rid}"\ntext = "t"\nbinding = "{binding}"\nverify = [{items}]\nstatus = "accepted"\n'


def row(cid, check, result, scenario="usb-min/all_on/vf-min", item="J1"):
    return {"stage": cid[0], "id": cid, "scenario": scenario, "item": item, "check": check, "result": result}


def evaluate(tmp_path, text, protocol_rows=(), manual=(), stages_run=ALL, warnings=(), checks=()):
    signoff = {"manual": list(manual), "accept": list(warnings)}
    return requirements.evaluate(entries(tmp_path, text), list(protocol_rows), signoff, set(stages_run),
                                 list(checks)), signoff


def states(results):
    return [(r.entry.id, r.state, [state for _, _, state, _ in r.items]) for r in results]


def test_rows_pass_with_a_match_and_no_failure(tmp_path):
    current = [row("LIM.i", "current from the supply", "pass"), row("LIM.i", "current from the supply", "warn"),
               row("SIM.state", "LED current (LED0)", "fail", item="D2")]
    text = (requirement("must", ("rows", "LIM.i * J1 current from the supply"), rid="R-1")
            + requirement("must", ("rows", "SIM.state * D? LED current *"), rid="R-2")
            + requirement("must", ("rows", "E-9 *"), rid="R-3"))
    results, _ = evaluate(tmp_path, text, current)
    assert states(results) == [("R-1", "pass", ["pass"]), ("R-2", "fail", ["fail"]), ("R-3", "fail", ["fail"])]
    assert results[0].items[0][3] == "2 rows: 1 passed, 1 warning"
    assert results[1].items[0][3] == "1 row: 1 FAILED"
    assert results[2].items[0][3] == "no row of this run matches"


def test_a_rows_pattern_of_a_stage_that_did_not_run(tmp_path):
    results, _ = evaluate(tmp_path, requirement("must", ("rows", "GEO.width main *")), stages_run="PGE")
    assert results[0].items[0][2:] == ("fail", "no row of this run matches – stage L did not run")


def test_an_advisory_row_is_no_passing_evidence(tmp_path):
    """A project stage's advisory finding does not block the release, but it did not pass."""
    results, _ = evaluate(tmp_path, requirement("must", ("rows", "K-1 *")), [row("K-1", "door fits", "advisory")])
    assert states(results) == [("R-1", "fail", ["fail"])]


SIGNED = {"done_by": "agent electrical-reviewer", "date": "2026-10-28"}


@pytest.mark.parametrize("m1, state, what", [
    ({**SIGNED, "note": "OK for state 1a2d…; R-1: LED_OE is held high by R2 until the firmware runs"}, "pass",
     "signed by agent electrical-reviewer (2026-10-28), its note names R-1"),
    ({**SIGNED, "note": "OK for state 1a2d…; R-12 holds"}, "fail",
     "signed by agent electrical-reviewer (2026-10-28), but its note does not name R-1 (section 6)"),
    ({"done_by": None, "note": "R-1 holds"}, "fail", "not signed for this state (section 6)"),
])
def test_signoff_evidence_is_signed_for_this_state_and_names_the_requirement(tmp_path, m1, state, what):
    """The note of the manual check names the requirement's ID: the reviewer judged it and signed for this state."""
    manual = [{"id": "M-1", "phase": "export", "scope": "circuit", **m1}]
    results, _ = evaluate(tmp_path, requirement("must", ("signoff", "M-1")), manual=manual)
    assert results[0].items[0][2:] == (state, what)
    assert results[0].state == state


def test_signoff_evidence_of_a_later_phase_does_not_block(tmp_path):
    manual = [{"id": "M-2", "phase": "order", "scope": "fab", "done_by": None}]
    results, signoff = evaluate(tmp_path, requirement("must", ("signoff", "M-2")), manual=manual)
    assert results[0].items[0][2:] == ("later", "not signed yet – after uploading to the manufacturer, before paying")
    assert results[0].state == "later" and requirements.reasons(results, signoff) == []


def test_accept_passes_once_m4_is_signed(tmp_path):
    step = ("accept", "on a power bank: press start, the bell rings")
    m4 = {"id": "M-4", "phase": "acceptance", "scope": "layout", "done_by": None}
    results, signoff = evaluate(tmp_path, requirement("must", step), manual=[m4])
    assert results[0].items[0][2:] == ("later", "after delivery: M-4 not signed yet (section 6)")
    assert results[0].state == "later" and requirements.reasons(results, signoff) == []
    results, _ = evaluate(tmp_path, requirement("must", step), manual=[{**m4, **SIGNED}])
    assert results[0].items[0][2:] == ("pass", "M-4 signed by agent electrical-reviewer (2026-10-28)")
    assert results[0].state == "pass"


def gate_check(name, cid, phase="export", at="before S", advisory=False):
    """A project check as the gate takes it (scripts.gate_checks)."""
    return scripts.Check(name, cid, name, "the rule watcher", ["python3", "watch.py"], phase,
                         at if phase == "export" else "", advisory, scripts.TIMEOUT)


WATCHER = gate_check("rule-watcher", "W")


@pytest.mark.parametrize("results, state, what", [
    (["pass"], "pass", "check W: 1 row: 1 passed"),
    (["pass", "fail"], "fail", "check W: 2 rows: 1 passed, 1 FAILED"),
    (["advisory"], "fail", "check W: 1 row: 1 advisory"),           # listed, not blocking – but it did not pass
])
def test_script_evidence_passes_when_its_check_passed_in_this_run(tmp_path, results, state, what):
    """Step 3.1: the gate runs the project's checks – a requirement's script passes when its check passed, every row of
    its stage."""
    protocol = [row("W-1", "no LED before the firmware", r, scenario="", item="rule-watcher") for r in results]
    found, _ = evaluate(tmp_path, requirement("must", ("script", "rule-watcher")), protocol + [row("SIM.state", "x", "fail")],
                        stages_run=ALL | {"W"}, checks=[WATCHER])
    assert found[0].items[0][2:] == (state, what) and found[0].state == state


@pytest.mark.parametrize("binding, reason", [
    ("must", "1 requirement(s) must without passing evidence: R-1 (section 11)"),
    ("should", "1 requirement(s) should without passing evidence, not accepted: R-1 (section 11)"),
])
def test_a_failed_check_blocks_a_must_and_warns_a_should(tmp_path, binding, reason):
    results, signoff = evaluate(tmp_path, requirement(binding, ("script", "rule-watcher")),
                                [row("W-1", "no LED before the firmware", "fail")], stages_run=ALL | {"W"},
                                checks=[WATCHER])
    assert gate.decide(rows("pass"), [], signoff, ALL, gate.STAGES, results) == ("NOT RELEASED", [reason])


def test_a_check_that_did_not_run_is_no_passing_evidence(tmp_path):
    """A check after F in the offline gate; a name that is no check of this run – stage G says why."""
    gerber = gate_check("gerber", "X", at="after F")
    text = requirement("must", ("script", "gerber"), rid="R-1") + requirement("must", ("script", "pins"), rid="R-2")
    results, _ = evaluate(tmp_path, text, stages_run="PGE", checks=[gerber])
    assert [r.items[0][2:] for r in results] == [
        ("fail", "check X did not run – it runs after stage F, in edakit gate --easyeda"),
        ("fail", "no check pins in this run – stage G says why (scripts, DOCS.ref)")]


def test_a_release_stage_is_named_by_its_id(tmp_path):
    stage = scripts.Check("K", "K", "Mechanics", "mech/check.py", ["mech/check.py"], "export", "before S", False, 900)
    results, _ = evaluate(tmp_path, requirement("must", ("script", "K")), [row("K", "mech/check.py", "pass")],
                          stages_run=ALL | {"K"}, checks=[stage])
    assert results[0].items[0][2:] == ("pass", "check K: 1 row: 1 passed")


@pytest.mark.parametrize("phase, sid, title", [
    ("acceptance", "M-4", "after delivery, per board"),
    ("order", "M-2", "after uploading to the manufacturer, before paying"),
])
def test_a_check_after_the_export_counts_like_an_acceptance_step(tmp_path, phase, sid, title):
    """It is a line of its phase's list in section 6: open after the export until the manual check that works through
    that list is signed – M-4 after delivery, M-2 at JLCPCB."""
    camera = gate_check("camera", "A", phase=phase)
    m = {"id": sid, "phase": phase, "scope": "layout", "done_by": None}
    for manual, found in [
            ([], ("later", f"{title}: {sid} is not in the sign-off file – check A is a line of its list (section 6)")),
            ([m], ("later", f"{title}: {sid} not signed yet – check A is a line of its list (section 6)")),
            ([{**m, **SIGNED}], ("pass", f"{sid} signed by agent electrical-reviewer (2026-10-28)"))]:
        results, signoff = evaluate(tmp_path, requirement("must", ("script", "camera")), manual=manual,
                                    checks=[camera])
        assert results[0].items[0][2:] == found
        assert requirements.reasons(results, signoff) == []


@pytest.mark.parametrize("binding, state, reason", [
    ("must", "fail", "1 requirement(s) must without passing evidence: R-1 (section 11)"),
    ("should", "warn", "1 requirement(s) should without passing evidence, not accepted: R-1 (section 11)"),
    ("may", "info", None),
])
def test_binding_decides_what_missing_evidence_does(tmp_path, binding, state, reason):
    """must blocks the release, should warns until the owner accepts it, may informs."""
    results, signoff = evaluate(tmp_path, requirement(binding, ("rows", "LIM.i * J1 *")),
                                [row("LIM.i", "current from the supply", "fail")])
    assert results[0].state == state
    d, reasons = gate.decide(rows("pass"), [], signoff, ALL, gate.STAGES, results)
    assert reasons == ([reason] if reason else []) and d == ("NOT RELEASED" if reason else "RELEASED")


def test_a_should_requirement_is_accepted_like_a_warning(tmp_path):
    accept = {"match": "R-1 *", "scope": "decision", "reason": "D-9: 7 mA is bright enough", "by": "owner",
              "date": "2026-10-28"}
    results, signoff = evaluate(tmp_path, requirement("should", ("rows", "LIM.i * J1 *")),
                                [row("LIM.i", "current from the supply", "fail")], warnings=[accept])
    assert requirements.reasons(results, signoff) == []
    lines = requirements.section(results, signoff, ["hardware/requirements.toml"])
    assert any(line.startswith("- **R-1** should, accepted: t → **warning** – accepted by owner (2026-10-28): D-9: 7 mA")
               for line in lines)


def test_without_evidence_a_requirement_does_not_pass(tmp_path):
    results, signoff = evaluate(tmp_path, requirement("must"))
    assert states(results) == [("R-1", "fail", [])]
    assert requirements.reasons(results, signoff) == [
        "1 requirement(s) must without passing evidence: R-1 (section 11)"]


def test_a_dropped_requirement_is_listed_not_evaluated(tmp_path):
    text = requirement("must", ("rows", "E-9 *")).replace('status = "accepted"', 'status = "dropped"\nreason = "D-4"')
    results, signoff = evaluate(tmp_path, text)
    assert states(results) == [("R-1", "dropped", [])] and requirements.reasons(results, signoff) == []
    assert requirements.section(results, signoff, ["r.toml"])[1:] == ["- **R-1** must, dropped: t → dropped: D-4"]
    assert requirements.acceptance(results) == []


@pytest.mark.parametrize("binding, state", [("must", "fail"), ("should", "warn")])
def test_a_draft_never_blocks_the_release(tmp_path, binding, state):
    """Decided 2026-10-28: a draft is evaluated and listed, but its binding counts only once the user accepts it – no
    reason against the release, no acceptance needed."""
    text = requirement(binding, ("rows", "LIM.i * J1 *")).replace('status = "accepted"', 'status = "draft"')
    results, signoff = evaluate(tmp_path, text, [row("LIM.i", "current from the supply", "fail")])
    assert states(results) == [("R-1", state, ["fail"])]                       # its evidence as evaluated
    assert requirements.reasons(results, signoff) == []
    assert gate.decide(rows("pass"), [], signoff, ALL, gate.STAGES, results) == ("RELEASED", [])
    assert requirements.section(results, signoff, ["r.toml"])[1:] == [
        f"- **R-1** {binding}, draft: t → draft, not binding yet – no passing evidence",
        "  - rows `LIM.i * J1 *` – 1 row: 1 FAILED"]
    assert requirements.summary(results) == "requirements: 1 draft (section 11 of the protocol)"


def test_a_draft_with_passing_evidence_says_so(tmp_path):
    text = requirement("must", ("rows", "LIM.i * J1 *")).replace('status = "accepted"', 'status = "draft"')
    results, signoff = evaluate(tmp_path, text, [row("LIM.i", "current from the supply", "pass")])
    assert requirements.verdict(results[0], signoff) == "draft, not binding yet – passed"


# --- the gate run: section 11, the acceptance list, the decision ------------------------------------------------------

def sign(project, *manual):
    """The sign-off file signed for the current circuit and layout hash: {id: note} for the manual checks given."""
    cfg = project.config()
    head = gate.header(cfg)
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s.update(state_sha256=head["state_sha256"], layout_sha256=head["layout_sha256"])
    notes = dict(manual)
    for m in s["manual"]:
        if m["id"] in notes:
            m.update(done_by="agent", date="2026-10-28", note=notes[m["id"]])
    path.write_text(json.dumps(s, indent=2))
    return head


def test_the_protocol_lists_each_requirement_with_its_evidence(project, monkeypatch, capsys):
    with_requirements(project)
    text = gate_run(project, monkeypatch)
    eleven = section(text, 11)
    assert eleven.startswith("Requirements\n\nFrom `hardware/requirements.toml`, each requirement with its evidence "
                             "in this run")
    assert ("- **R-1** must, accepted: With all eight LEDs on, the board draws at most 500 mA from J1 at 4.75 to "
            "5.25 V. → open after the export – does not block the release\n"
            "  - rows `LIM.i * J1 current from the supply` – 12 rows: 12 passed\n"
            "  - accept: on the USB port of a laptop: all eight LEDs on, the port stays on – after delivery: M-4 not "
            "signed yet (section 6)\n") in eleven
    assert "- **R-2** must, accepted: A supply plugged into J1 the wrong way round reaches only the anode of D1. → passed\n" \
           "  - rows `PATH.reverse *` – 1 row: 1 passed\n" in eleven
    assert "  - rows `SIM.state * D? LED current *` – 48 rows: 48 passed\n" in eleven
    # R-4 is a draft: listed with its evidence as evaluated, it binds nothing yet – no reason, no acceptance (G-23)
    assert ("- **R-4** must, draft: From power-up until the firmware drives LED_OE low, no LED carries more than "
            "10 µA. → draft, not binding yet – no passing evidence\n"
            "  - rows `SIM.state * D? LED dark` – 48 rows: 48 passed\n"
            "  - signoff M-1 – not signed for this state (section 6)\n") in eleven
    reasons = decision(text)
    assert "requirement(s)" not in reasons and "warning(s) not accepted" not in reasons
    assert "DOCS.draft" not in section(text, 3)
    assert "| SHA-256 circuit | `" in text and "` (graph, parts database, simulation config, requirements) |" in text
    out = capsys.readouterr().out
    assert "requirements: 2 passed, 1 open after the export, 1 draft (section 11 of the protocol)" in out


def test_a_requirement_passes_with_its_sign_off(project, monkeypatch):
    """M-1 signed for this circuit, its note naming R-4: the requirement passes, the reason is gone."""
    with_requirements(project)
    rewrite(project, 'status = "draft"', 'status = "accepted"')
    sign(project, ("M-1", "OK for this state. R-4: R2 holds LED_OE high until the firmware drives it"))
    text = gate_run(project, monkeypatch)
    assert "→ **FAILED**" not in section(text, 11)
    assert "  - signoff M-1 – signed by agent (2026-10-28), its note names R-4\n" in section(text, 11)
    assert "requirement(s)" not in decision(text)


WATCH = ('"""The rule watcher of the tests: its verdict from the first argument."""\nimport json, sys\n'
         'print(json.dumps([["W-1", "no LED before the firmware", "0 uA", "<= 10 uA", sys.argv[1] == "pass"]]))\n')
R5 = ('\n[[requirement]]\nid = "R-5"\ntext = "Until the firmware drives LED_OE low, no LED lights."\nfrom = ["N-3"]\n'
      'binding = "must"\nverify = [{ script = "rule-watcher" }]\nstatus = "accepted"\n')


@pytest.mark.parametrize("verdict, result", [
    ("pass", "→ passed\n  - script `rule-watcher` – check W: 1 row: 1 passed\n"),
    ("fail", "→ **FAILED** – blocks the release\n  - script `rule-watcher` – check W: 1 row: 1 FAILED\n"),
])
def test_a_requirement_names_a_check_of_the_gate(project, monkeypatch, verdict, result):
    """R-5 is verified by the project's rule watcher, a check of phase export: the gate runs it, and its result is the
    requirement's evidence."""
    with_requirements(project, LED_BAR + R5)
    (project.root / "hardware" / "watch.py").write_text(WATCH)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + f'\n[scripts.rule-watcher]\nkind = "check"\nid = "W"\nphase = "export"\n'
                    f'cmd = ["{sys.executable}", "hardware/watch.py", "{verdict}"]\n'
                    'about = "The rule watcher: no LED lights before the firmware drives LED_OE"\n')
    text = gate_run(project, monkeypatch)
    r5 = "- **R-5** must, accepted: Until the firmware drives LED_OE low, no LED lights. "
    assert r5 + result in section(text, 11)
    assert ("R-5 (section 11)" in decision(text)) == (verdict == "fail")


def test_accept_steps_join_the_acceptance_list(project, monkeypatch):
    """Decision 8: an accept step is an unchecked line under "after delivery, per board", with its ID, after M-4."""
    with_requirements(project)
    six = section(gate_run(project, monkeypatch), 6)
    after = six.split("**after delivery, per board**\n")[1].split("\n\n")[0]
    assert after.splitlines() == [
        "", "- [ ] M-4 Acceptance test of every delivered board: visual check, supply current, every LED, the button",
        "- [ ] R-1: on the USB port of a laptop: all eight LEDs on, the port stays on"]


# --- the circuit hash -------------------------------------------------------------------------------------------------

def test_the_requirements_file_counts_in_the_circuit_hash(project):
    with_requirements(project)
    cfg = project.config()
    assert gate.state_files(cfg)[-1] == project.root / "hardware" / "requirements.toml"
    h = gate.header(cfg)
    rewrite(project, "at most 500 mA", "at most 400 mA")
    h2 = gate.header(project.config())
    assert h2["state_sha256"] != h["state_sha256"] and h2["layout_sha256"] == h["layout_sha256"]


def test_a_changed_requirement_voids_m1_and_m6(project):
    """The reviews read the file: a changed requirement voids M-1 and M-6, as a new purpose does; M-4 (scope layout)
    keeps counting."""
    with_requirements(project)
    head = sign(project, ("M-1", "OK, R-4 judged"), ("M-6", "OK"), ("M-4", "OK"))
    loaded, _ = gate.load_signoff(project.config(), head)
    assert {m["id"] for m in loaded["manual"] if m["done_by"]} == {"M-1", "M-6", "M-4"}
    rewrite(project, 'source = "README.md"\n', 'source = "README.md, D-2"\n')
    loaded, notes = gate.load_signoff(project.config(), gate.header(project.config()))
    assert {m["id"] for m in loaded["manual"] if m["done_by"]} == {"M-4"}
    assert any("scope 'circuit' belong to another state" in n for n in notes)


def test_hash_ignore_does_not_reach_into_the_requirements_file(project):
    """[release] hash_ignore leaves documentation keys out of graph and parts entries; the requirements file stays
    bytes – a changed source or reason still changes the hash."""
    with_requirements(project)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[release]\n", '[release]\nhash_ignore = ["source", "reason", "text"]\n'))
    h = gate.header(project.config())["state_sha256"]
    rewrite(project, 'source = "README.md"\n', 'source = "README.md, D-2"\n')
    assert gate.header(project.config())["state_sha256"] != h


def test_a_variant_counts_the_main_projects_file(project):
    toml = variant_of(project, '[[need]]\nid = "N-5"\ntext = "t"\nstatus = "accepted"\n')
    from edakit import config
    cfg = config.load(toml)
    assert gate.state_files(cfg)[-2:] == cfg.requirements
    h = gate.state_hash(cfg)
    rewrite(project, "at most 500 mA", "at most 400 mA")                    # the main project's file
    assert gate.state_hash(config.load(toml)) != h


def test_the_firmware_contract_drifts_with_the_requirements(project, monkeypatch, capsys):
    """The contract carries the circuit hash: a changed requirements file asks for edakit firmware again."""
    from test_firmware import with_firmware
    with_requirements(project)
    with_firmware(project)
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["firmware"]) == 0 and cli.main(["firmware", "--check"]) == 0
    capsys.readouterr()
    rewrite(project, "at most 500 mA", "at most 400 mA")
    assert cli.main(["firmware", "--check"]) == 2
    out = capsys.readouterr().out
    assert "drift" in out and "state_sha256" in out


# --- no key, no change ------------------------------------------------------------------------------------------------

def test_without_the_key_nothing_changes(project, monkeypatch, capsys):
    """A project without [project] requirements: the same files in the circuit hash, the same checks, the same
    protocol – no section 11, no requirement in section 6, the circuit line as before."""
    cfg = project.config()
    parts = sorted((project.root / "hardware" / "parts").glob("*.json"))
    assert gate.state_files(cfg) == [cfg.graph, cfg.sim_config, *parts]
    text = gate_run(project, monkeypatch)
    assert "## 11" not in text and "- [ ] R-" not in text and "requirement" not in decision(text)
    assert "` (graph, parts database, simulation config) |" in text
    assert "requirements:" not in capsys.readouterr().out
    assert section(text, 10).startswith("The rules behind the findings\n\nNo code of the catalog failed or warned.")


def test_with_the_key_the_requirement_checks_count_as_executed(project, monkeypatch):
    with_requirements(project)
    cfg = project.config()
    prof = engines.profile(Design.from_config(cfg), cfg)
    assert gate.executed(prof, cfg)[-4:] == list(REQUIREMENT_CHECKS)
    one = section(gate_run(project, monkeypatch), 1)
    assert "DOCS.evidence" in one
    # every code of stage G the profile has on, DOCS.ref to DOCS.draft among them (a code that only warns counts as
    # passed); DOCS.draft about the draft R-4 is information in the gate, no warning to accept
    assert re.search(r"\| G Graph \| [^|]+ \| 35 \| 0 \| 0 \| 3 \| 0 \| passed \|", one)
