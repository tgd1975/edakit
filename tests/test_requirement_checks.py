"""Requirements in edakit check and the gate (handbook 3.6, 8.7): the checks G-20 to G-23 on the requirements file,
each requirement's evidence evaluated against the gate run, the acceptance steps on the list of section 6, the file
in the circuit hash – and no change for a project without [project] requirements."""

import json
import re

import pytest
from test_gate import ALL, decision, gate_run, rows, section
from test_requirements import LED_BAR, variant_of, with_requirements

from edakit import checks, cli, requirements
from edakit.design import Design
from edakit.release import gate

REQUIREMENT_CHECKS = ("G-20", "G-21", "G-22", "G-23")


def rewrite(project, old, new):
    """The requirements file with old replaced by new (once)."""
    path = project.root / "hardware" / "requirements.toml"
    text = path.read_text(encoding="utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def found(project):
    """(errors, warnings) of G-20 to G-23 in the example's edakit check, each as (ID, message)."""
    cfg = project.config()
    rep = checks.run(Design.from_config(cfg), cfg)
    mine = lambda items: [(c, m) for c, m in items if c in REQUIREMENT_CHECKS]   # noqa: E731
    return mine(rep.errors), mine(rep.warnings)


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
    assert [(c, m.split(" – ")[0]) for c, m in warnings] == [("G-23", "R-4: a draft")]
    rewrite(project, 'status = "draft"', 'status = "accepted"')
    assert found(project) == ([], [])


@pytest.mark.parametrize("old, new, message", [
    # from: a need or a requirement (N-…, R-…) of the file, a manual check (M-…) of the sign-off file
    ('from = ["N-1", "USB 2.0', 'from = ["N-9", "USB 2.0', "R-1: from N-9 – not in the requirements file"),
    ('from = ["N-2"]', 'from = ["N-2", "R-9"]', "R-3: from R-9 – not in the requirements file"),
    ('from = ["N-3"]', 'from = ["N-3", "M-9"]', "R-4: from M-9 – no manual check M-9 in hardware/signoff.json "
                                               "(M-1, M-6, M-5, M-2, M-4)"),
    # verify: the check a rows pattern starts with, a manual check, a project script
    ('{ rows = "G-10 *" }', '{ rows = "G-99 *" }', "R-2: verify rows 'G-99 *' – G-99 is not a check of the catalog"),
    ('{ rows = "G-10 *" }', '{ rows = "G-7 *" }', "R-2: verify rows 'G-7 *' – G-7 is retired (edakit rules G-7)"),
    ('{ signoff = "M-1" }', '{ signoff = "M-7" }', "R-4: verify signoff M-7 – no manual check M-7 in "
                                                  "hardware/signoff.json (M-1, M-6, M-5, M-2, M-4)"),
    ('{ rows = "G-10 *" }', '{ script = "rule-watcher" }', "R-2: verify script rule-watcher – no [scripts.rule-watcher] "
                                                          "of kind check and no [[release.stages]] id rule-watcher in "
                                                          "edakit.toml"),
])
def test_g20_every_reference_resolves(project, old, new, message):
    with_requirements(project)
    rewrite(project, old, new)
    errors, _ = found(project)
    assert errors == [("G-20", message)]
    rewrite(project, new, old)
    assert found(project)[0] == []


def test_g20_what_edakit_cannot_resolve_is_not_a_finding(project):
    """Decisions, standards and free text in from, a rows pattern that starts with a wildcard or a project stage's ID,
    another requirement in from: nothing to report."""
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-2", "D-8", "R-1", "IEC 62368-1", "M-6"]')
    rewrite(project, '{ rows = "G-10 *" }', '{ rows = "* reverse polarity" }, { rows = "K-1 enclosure *" }')
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
    rewrite(project, '{ rows = "G-10 *" }', '{ script = "pins" }')
    assert found(project)[0] == [("G-20", "R-2: verify script pins – [scripts.pins] is of kind derive; evidence "
                                          "comes from a check")]
    rewrite(project, '{ script = "pins" }', '{ script = "watch" }, { script = "K" }')
    assert found(project)[0] == []


def test_g20_from_a_dropped_need_warns(project):
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-2", "N-4"]')
    errors, warnings = found(project)
    assert errors == []
    assert ("G-20", "R-3: from N-4 – dropped: the TLC5916 and the Pico 2 want 5 V: a cell needs a boost converter, "
                    "which the example does not have") in warnings


def test_a_dropped_requirement_is_not_checked(project):
    """A dropped entry stays for the record: no evidence needed, its references are history."""
    with_requirements(project)
    rewrite(project, 'verify = [{ rows = "G-10 *" }]\nstatus = "accepted"',      # R-2: no evidence, a broken from
            'status = "dropped"\nreason = "D-2: no longer wanted"')
    rewrite(project, 'from = ["N-1"]\nbinding = "must"', 'from = ["N-9"]\nbinding = "must"')
    errors, warnings = found(project)
    assert errors == [] and [m.split(" – ")[0] for _, m in warnings] == ["R-4: a draft"]


def test_g21_every_accepted_need_has_a_requirement(project):
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-1"]')                       # R-3 was N-2's only requirement
    assert found(project)[0] == [("G-21", "N-2: accepted, but no requirement names it in from")]
    rewrite(project, 'from = ["N-1"]\nbinding = "should"', 'from = ["N-2"]\nbinding = "should"')
    assert found(project)[0] == []
    # a dropped requirement does not count
    rewrite(project, 'verify = [{ rows = "E-3 * D? LED current *" }]\nstatus = "accepted"',
            'verify = [{ rows = "E-3 * D? LED current *" }]\nstatus = "dropped"\nreason = "D-3: any brightness"')
    assert found(project)[0] == [("G-21", "N-2: accepted, but no requirement names it in from")]


def test_g21_only_for_accepted_needs(project):
    """A draft need without a requirement only warns as a draft; a dropped one needs none."""
    with_requirements(project)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-1"]')
    rewrite(project, 'source = "README.md"\nstatus = "accepted"', 'source = "README.md"\nstatus = "draft"')   # N-2
    errors, warnings = found(project)
    assert errors == [] and [m.split(" – ")[0] for _, m in warnings] == ["N-2: a draft", "R-4: a draft"]


def test_g22_every_requirement_has_evidence(project):
    with_requirements(project)
    rewrite(project, 'verify = [{ rows = "G-10 *" }]\n', "")
    assert found(project)[0] == [("G-22", "R-2: no evidence – verify names nothing that tests it")]
    rewrite(project, 'from = ["N-1"]\nbinding = "must"\nstatus', 'from = ["N-1"]\nbinding = "must"\nverify = []\nstatus')
    assert found(project)[0] == [("G-22", "R-2: no evidence – verify names nothing that tests it")]


def test_g23_drafts_warn(project):
    """A need or requirement without status is a draft too."""
    with_requirements(project)
    rewrite(project, 'source = "README.md"\nstatus = "accepted"\n', 'source = "README.md"\n')     # N-2
    errors, warnings = found(project)
    assert errors == []
    assert [m.split(" – ")[0] for c, m in warnings if c == "G-23"] == ["N-2: a draft", "R-4: a draft"]
    assert warnings[0][1] == ('N-2: a draft – the user has not approved it (status "accepted", or "dropped" with a '
                              'reason)')


def test_edakit_check_reports_and_explains_them(project, capsys):
    with_requirements(project)
    code, out, _ = check(project, capsys)
    assert code == 0                                                    # a draft only warns
    assert "WARNING G-23  R-4: a draft" in out
    assert re.search(r"\n\d+ components, .*; requirements: 4 needs, 4 requirements", out)
    rewrite(project, 'from = ["N-2"]', 'from = ["N-1"]')
    code, out, _ = check(project, capsys)
    assert code == 1
    assert "ERROR   G-21  N-2: accepted, but no requirement names it in from" in out
    assert "G-21 (accepted need has a requirement): " in out.split("What the failed checks are about")[1]


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


def evaluate(tmp_path, text, protocol_rows=(), manual=(), stages_run=ALL, warnings=()):
    signoff = {"manual": list(manual), "accepted_warnings": list(warnings)}
    return requirements.evaluate(entries(tmp_path, text), list(protocol_rows), signoff, set(stages_run)), signoff


def states(results):
    return [(r.entry.id, r.state, [state for _, _, state, _ in r.items]) for r in results]


def test_rows_pass_with_a_match_and_no_failure(tmp_path):
    current = [row("E-3", "current from the supply", "pass"), row("E-3", "current from the supply", "warn"),
               row("E-3", "LED current (LED0)", "fail", item="D2")]
    text = (requirement("must", ("rows", "E-3 * J1 current from the supply"), rid="R-1")
            + requirement("must", ("rows", "E-3 * D? LED current *"), rid="R-2")
            + requirement("must", ("rows", "E-9 *"), rid="R-3"))
    results, _ = evaluate(tmp_path, text, current)
    assert states(results) == [("R-1", "pass", ["pass"]), ("R-2", "fail", ["fail"]), ("R-3", "fail", ["fail"])]
    assert results[0].items[0][3] == "2 rows: 1 passed, 1 warning"
    assert results[1].items[0][3] == "1 row: 1 FAILED"
    assert results[2].items[0][3] == "no row of this run matches"


def test_a_rows_pattern_of_a_stage_that_did_not_run(tmp_path):
    results, _ = evaluate(tmp_path, requirement("must", ("rows", "L-5 main *")), stages_run="PGE")
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


def test_script_evidence_is_not_evaluated_yet_and_does_not_block(tmp_path):
    """Project scripts run in the gate from step 3.1 of the implementation plan on; until then a requirement whose
    evidence is a script warns as not evaluated, and that alone does not hold up the release."""
    text = requirement("must", ("rows", "E-3 *"), ("script", "rule-watcher"))
    results, signoff = evaluate(tmp_path, text, [row("E-3", "current from the supply", "pass")])
    assert states(results) == [("R-1", "unevaluated", ["pass", "unevaluated"])]
    assert results[0].items[1][3] == "not evaluated yet – the gate runs no project scripts so far"
    assert requirements.reasons(results, signoff) == []
    assert gate.decide(rows("pass"), [], signoff, ALL, gate.STAGES, results) == ("RELEASED", [])


def test_failing_evidence_also_fails_with_a_script_beside_it(tmp_path):
    text = requirement("must", ("rows", "E-3 *"), ("script", "rule-watcher"))
    results, _ = evaluate(tmp_path, text, [row("E-3", "current from the supply", "fail")])
    assert results[0].state == "fail"


@pytest.mark.parametrize("binding, state, reason", [
    ("must", "fail", "1 requirement(s) must without passing evidence: R-1 (section 11)"),
    ("should", "warn", "1 requirement(s) should without passing evidence, not accepted: R-1 (section 11)"),
    ("may", "info", None),
])
def test_binding_decides_what_missing_evidence_does(tmp_path, binding, state, reason):
    """must blocks the release, should warns until the owner accepts it, may informs."""
    results, signoff = evaluate(tmp_path, requirement(binding, ("rows", "E-3 * J1 *")),
                                [row("E-3", "current from the supply", "fail")])
    assert results[0].state == state
    d, reasons = gate.decide(rows("pass"), [], signoff, ALL, gate.STAGES, results)
    assert reasons == ([reason] if reason else []) and d == ("NOT RELEASED" if reason else "RELEASED")


def test_a_should_requirement_is_accepted_like_a_warning(tmp_path):
    accept = {"match": "R-1 *", "scope": "decision", "reason": "D-9: 7 mA is bright enough", "by": "owner",
              "date": "2026-10-28"}
    results, signoff = evaluate(tmp_path, requirement("should", ("rows", "E-3 * J1 *")),
                                [row("E-3", "current from the supply", "fail")], warnings=[accept])
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
            "  - rows `E-3 * J1 current from the supply` – 12 rows: 12 passed\n"
            "  - accept: on the USB port of a laptop: all eight LEDs on, the port stays on – after delivery: M-4 not "
            "signed yet (section 6)\n") in eleven
    assert "- **R-2** must, accepted: A supply plugged into J1 the wrong way round reaches only the anode of D1. → passed\n" \
           "  - rows `G-10 *` – 1 row: 1 passed\n" in eleven
    assert "  - rows `E-3 * D? LED current *` – 48 rows: 48 passed\n" in eleven
    assert ("- **R-4** must, draft: From power-up until the firmware drives LED_OE low, no LED carries more than "
            "10 µA. → **FAILED** – blocks the release\n"
            "  - rows `E-3 * D? LED dark` – 48 rows: 48 passed\n"
            "  - signoff M-1 – not signed for this state (section 6)\n") in eleven
    reasons = decision(text)
    assert "- 1 requirement(s) must without passing evidence: R-4 (section 11)" in reasons
    assert "- 1 warning(s) not accepted (section 3)" in reasons                     # G-23: R-4 is a draft
    assert "`G-23 R-4: a draft" in section(text, 3)
    assert "| SHA-256 circuit | `" in text and "` (graph, parts database, simulation config, requirements) |" in text
    out = capsys.readouterr().out
    assert "requirements: 2 passed, 1 open after the export, 1 FAILED (section 11 of the protocol)" in out


def test_a_requirement_passes_with_its_sign_off(project, monkeypatch):
    """M-1 signed for this circuit, its note naming R-4: the requirement passes, the reason is gone."""
    with_requirements(project)
    rewrite(project, 'status = "draft"', 'status = "accepted"')
    sign(project, ("M-1", "OK for this state. R-4: R2 holds LED_OE high until the firmware drives it"))
    text = gate_run(project, monkeypatch)
    assert "→ **FAILED**" not in section(text, 11)
    assert "  - signoff M-1 – signed by agent (2026-10-28), its note names R-4\n" in section(text, 11)
    assert "requirement(s)" not in decision(text)


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
    assert checks.executed(cfg) == checks.EXECUTED
    text = gate_run(project, monkeypatch)
    assert "## 11" not in text and "- [ ] R-" not in text and "requirement" not in decision(text)
    assert "` (graph, parts database, simulation config) |" in text
    assert "requirements:" not in capsys.readouterr().out
    assert section(text, 10).startswith("The rules behind the findings\n\nNo check of the catalog failed or warned.")


def test_with_the_key_the_requirement_checks_count_as_executed(project, monkeypatch):
    with_requirements(project)
    cfg = project.config()
    assert checks.executed(cfg) == checks.EXECUTED + list(REQUIREMENT_CHECKS)
    one = section(gate_run(project, monkeypatch), 1)
    assert "G-22 (requirement has evidence)" in one
    # 16 as before and G-20 to G-23 (a check that only warns counts as passed, as P-4 does); G-23 warns about R-4
    assert re.search(r"\| G Graph \| [^|]+ \| 20 \| 0 \| 1 \| 3 \| 0 \| passed with reservations \|", one)
