"""The requirements file (handbook 3.6, 10.4): what the circuit must do, needs N-… and requirements R-…, read by
`edakit req`. Whether the evidence passes is not evaluated – `edakit req` shows verify as written."""

import re

import pytest

from edakit import cli

# Only the circuit of led-bar: what the firmware does stays in the project's documents.
LED_BAR = """\
[[need]]
id = "N-1"
text = "The bar runs from a USB charger or from the USB port of a laptop."
who = "whoever uses the bar"
source = "README.md, sim.json J1"
status = "accepted"

[[need]]
id = "N-2"
text = "The LEDs can be read in a lit room."
who = "whoever looks at the bar"
source = "README.md"
status = "accepted"

[[need]]
id = "N-3"
text = "No LED flashes when the bar is plugged in."
who = "whoever looks at the bar"
source = "README.md: R2 keeps the LEDs dark until the firmware runs"
status = "accepted"

[[need]]
id = "N-4"
text = "The bar also runs from one Li-ion cell."
who = "whoever uses the bar"
status = "dropped"
reason = "the TLC5916 and the Pico 2 want 5 V: a cell needs a boost converter, which the example does not have"

[[requirement]]
id = "R-1"
text = "With all eight LEDs on, the board draws at most 500 mA from J1 at 4.75 to 5.25 V."
source = "sim.json: the note of source J1"
from = ["N-1", "USB 2.0: 500 mA per port"]
binding = "must"
verify = [{ rows = "LIM.i * J1 current from the supply" },
          { accept = "on the USB port of a laptop: all eight LEDs on, the port stays on" }]
status = "accepted"

[[requirement]]
id = "R-2"
text = "A supply plugged into J1 the wrong way round reaches only the anode of D1."
from = ["N-1"]
binding = "must"
verify = [{ rows = "PATH.reverse *" }]
status = "accepted"

[[requirement]]
id = "R-3"
text = "Every LED that is on carries at least 7.5 mA (80 % of the 9.45 mA R1 sets) at 4.75 to 5.25 V."
from = ["N-2"]
binding = "should"
verify = [{ rows = "SIM.state * D? LED current *" }]
status = "accepted"

[[requirement]]
id = "R-4"
text = "From power-up until the firmware drives LED_OE low, no LED carries more than 10 µA."
from = ["N-3"]
binding = "must"
verify = [{ rows = "SIM.state * D? LED dark" }, { signoff = "M-1" }]
status = "draft"
"""

REQUIREMENT = '[[requirement]]\nid = "R-1"\ntext = "t"\nbinding = "must"\nstatus = "accepted"\n'
NEED = '[[need]]\nid = "N-1"\ntext = "t"\nstatus = "accepted"\n'


def with_requirements(project, text=LED_BAR, key='"hardware/requirements.toml"'):
    """The example with a requirements file, named in [project] requirements; returns its edakit.toml."""
    (project.root / "hardware" / "requirements.toml").write_text(text, encoding="utf-8")
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace("[project]\n", f"[project]\nrequirements = {key}\n"))
    return toml


def req(toml, *ids):
    return cli.main(["req", *ids, "--config", str(toml)])


def problems(tmp_path, text):
    from edakit import requirements
    path = tmp_path / "requirements.toml"
    path.write_text(text, encoding="utf-8")
    return requirements.read(path)[1]


def test_req_lists_needs_and_requirements_with_status_binding_and_evidence(project, capsys):
    toml = with_requirements(project)
    assert req(toml) == 0
    out = capsys.readouterr().out
    assert "hardware/requirements.toml: 4 needs, 4 requirements" in out
    assert re.search(r"N-1 +accepted +The bar runs from a USB charger", out)
    assert re.search(r"N-4 +dropped +The bar also runs from one Li-ion cell", out)
    assert "a cell needs a boost converter" in out                         # a dropped entry stays with its reason
    assert re.search(r"R-1 +accepted +must +With all eight LEDs on", out)
    assert re.search(r"R-3 +accepted +should +Every LED that is on", out)
    assert re.search(r"R-4 +draft +must +From power-up", out)
    for evidence in ("rows LIM.i * J1 current from the supply", "accept on the USB port of a laptop", "rows PATH.reverse *",
                     "signoff M-1"):
        assert evidence in out                                              # verify as written
    assert "not evaluated" in out and "passed" not in out and "FAILED" not in out
    assert out.index("N-4") < out.index("R-1")                              # needs first, then requirements


def test_req_id_shows_the_chain_from_where_it_comes_from_to_what_verifies_it(project, capsys):
    toml = with_requirements(project)
    assert req(toml, "R-1") == 0
    out = capsys.readouterr().out
    origin, text = out.index("The bar runs from a USB charger"), out.index("With all eight LEDs on")
    evidence = out.index("LIM.i * J1 current from the supply")
    assert origin < text < evidence and "USB 2.0: 500 mA per port" in out
    assert "on the USB port of a laptop" in out and "not evaluated" in out
    assert "R-2" not in out and "N-2" not in out                            # only the chain of R-1


def test_req_need_shows_the_requirements_that_follow_from_it(project, capsys):
    toml = with_requirements(project)
    assert req(toml, "N-1") == 0
    out = capsys.readouterr().out
    assert "The bar runs from a USB charger" in out and "R-1" in out and "R-2" in out and "PATH.reverse *" in out
    assert "R-3" not in out
    assert req(toml, "N-4") == 0
    assert "no requirement names it in from" in capsys.readouterr().out


def test_req_unknown_id(project, capsys):
    toml = with_requirements(project)
    assert req(toml, "R-1", "R-9") == 1
    out = capsys.readouterr().out
    assert "R-9: not in the requirements file" in out and "With all eight LEDs on" in out


def test_without_the_key_there_is_no_requirements_file(project, capsys):
    """No key, no change: the example as it is reads no requirements file, and edakit req says how to name one."""
    assert project.config().requirements == []
    assert req(project.root / "edakit.toml") == 1
    assert "[project] requirements" in capsys.readouterr().err


def test_a_file_named_in_the_key_must_exist(project, capsys):
    toml = with_requirements(project)
    (project.root / "hardware" / "requirements.toml").unlink()
    assert req(toml) == 1
    assert "hardware/requirements.toml: not found" in capsys.readouterr().err


def test_the_example_reads_without_problems(project):
    from edakit import requirements
    with_requirements(project)
    entries = requirements.load(project.config())
    assert [e.id for e in entries] == ["N-1", "N-2", "N-3", "N-4", "R-1", "R-2", "R-3", "R-4"]
    r1 = next(e for e in entries if e.id == "R-1")
    assert r1.kind == "requirement" and r1.binding == "must" and r1.status == "accepted"
    assert r1.from_ == ["N-1", "USB 2.0: 500 mA per port"] and r1.source == "sim.json: the note of source J1"
    assert r1.verify == [("rows", "LIM.i * J1 current from the supply"),
                         ("accept", "on the USB port of a laptop: all eight LEDs on, the port stays on")]
    n4 = next(e for e in entries if e.id == "N-4")
    assert n4.kind == "need" and n4.status == "dropped" and n4.reason.startswith("the TLC5916")


def test_a_requirement_names_where_it_was_found(project, capsys):
    """source on a requirement: where it was found, as on a need; from stays where it comes from."""
    toml = with_requirements(project)
    assert req(toml) == 0
    assert re.search(r"R-1 +accepted +must +With all eight LEDs on.*\n +source: sim.json: the note of source J1\n"
                     r" +from: N-1, USB 2.0: 500 mA per port\n", capsys.readouterr().out)
    assert req(toml, "R-1") == 0
    assert re.search(r"\n  source +sim.json: the note of source J1\n  from +N-1 ", capsys.readouterr().out)


def test_a_missing_status_is_a_draft(project, tmp_path, capsys):
    """Only the user sets accepted: an entry without status is a draft; a status that is written is still checked."""
    text = LED_BAR.replace('source = "README.md"\nstatus = "accepted"\n', 'source = "README.md"\n')    # N-2
    assert text != LED_BAR
    toml = with_requirements(project, text)
    assert req(toml) == 0
    assert re.search(r"N-2 +draft +The LEDs can be read in a lit room", capsys.readouterr().out)
    assert req(toml, "N-2") == 0
    assert "N-2  need, draft" in capsys.readouterr().out
    assert problems(tmp_path, REQUIREMENT.replace('status = "accepted"\n', "")) == []


@pytest.mark.parametrize("kind", ["rows", "signoff", "script", "accept"])
def test_every_kind_of_evidence_reads(tmp_path, kind):
    assert problems(tmp_path, REQUIREMENT + f'verify = [{{ {kind} = "x" }}]\n') == []


@pytest.mark.parametrize("binding", ["must", "should", "may"])
def test_every_binding_reads(tmp_path, binding):
    assert problems(tmp_path, REQUIREMENT.replace('"must"', f'"{binding}"')) == []


@pytest.mark.parametrize("text, problem", [
    # unknown keys are errors, at the top and in an entry – each level has its own fields
    ('[[needs]]\nid = "N-1"\n', "unknown key 'needs' (known: need, requirement)"),
    ('[need]\nid = "N-1"\n', "need must be an array of tables: [[need]]"),
    (NEED + 'binding = "must"\n', "N-1: unknown key 'binding' (known: id, text, who, source, status, reason)"),
    (NEED + 'verify = [{ rows = "LIM.i *" }]\n', "N-1: unknown key 'verify'"),
    (REQUIREMENT + 'who = "the user"\n', "R-1: unknown key 'who' (known: id, text, source, from, binding, verify, "
                                         "status, reason)"),
    (REQUIREMENT + "source = 3\n", "R-1: source must be a text"),
    (REQUIREMENT + 'form = ["N-1"]\n', "R-1: unknown key 'form'"),
    # IDs: N-<n> for a need, R-<n> for a requirement
    (NEED.replace('"N-1"', '"R-1"'), "[[need]] 1: id 'R-1' – a need is N-<n>, e.g. N-1"),
    (REQUIREMENT.replace('"R-1"', '"R4"'), "[[requirement]] 1: id 'R4' – a requirement is R-<n>, e.g. R-1"),
    (REQUIREMENT.replace('"R-1"', '"R-01"'), "[[requirement]] 1: id 'R-01'"),
    (REQUIREMENT.replace('id = "R-1"\n', ""), "[[requirement]] 1: id is missing"),
    (REQUIREMENT + REQUIREMENT, "R-1: twice in this file"),
    # only known values
    (REQUIREMENT.replace('"must"', '"shall"'), "R-1: binding must be must, should or may, not 'shall'"),
    (REQUIREMENT.replace('binding = "must"\n', ""), "R-1: binding is missing (must, should or may)"),
    (NEED.replace('"accepted"', '"approved"'), "N-1: status must be draft, accepted or dropped, not 'approved'"),
    (NEED.replace('"accepted"', '""'), "N-1: status must be draft, accepted or dropped, not ''"),
    (REQUIREMENT + 'verify = [{ test = "x" }]\n', "R-1: verify 1: unknown kind 'test' (known: rows, signoff, script, "
                                                  "accept)"),
    (REQUIREMENT + 'verify = [{ rows = "LIM.i *", accept = "x" }]\n', "R-1: verify 1: one kind per entry"),
    (REQUIREMENT + 'verify = [{ rows = "" }]\n', "R-1: verify 1: rows needs a text"),
    (REQUIREMENT + 'verify = { rows = "LIM.i *" }\n', 'R-1: verify must be a list, e.g. [{ rows = "LIM.i * J1 *" }]'),
    (REQUIREMENT + 'from = "N-1"\n', 'R-1: from must be a list of texts, e.g. ["N-2", "D-8"]'),
    (REQUIREMENT + 'from = ["N-1", ""]\n', "R-1: from must be a list of texts"),
    (NEED.replace('text = "t"\n', ""), "N-1: text is missing"),
    (NEED.replace('text = "t"', 'text = " "'), "N-1: text is missing"),
    (NEED + "who = 3\n", "N-1: who must be a text"),
    # a dropped entry stays with its reason
    (NEED.replace('"accepted"', '"dropped"'), "N-1: dropped – it needs a reason"),
    (REQUIREMENT.replace('"accepted"', '"dropped"'), "R-1: dropped – it needs a reason"),
    ('[[need]\nid = "N-1"\n', "not valid TOML: "),
])
def test_mistakes_in_the_file(tmp_path, text, problem):
    found = problems(tmp_path, text)
    assert any(problem in p for p in found), found


def test_entries_without_an_id_are_not_twice(tmp_path):
    found = problems(tmp_path, (REQUIREMENT + REQUIREMENT).replace('id = "R-1"\n', ""))
    assert found == ["[[requirement]] 1: id is missing (R-<n>)", "[[requirement]] 2: id is missing (R-<n>)"]


def test_a_dropped_entry_with_its_reason_reads(tmp_path):
    assert problems(tmp_path, NEED.replace('"accepted"', '"dropped"') + 'reason = "D-47: no cells"\n') == []
    assert problems(tmp_path, NEED + 'reason = "the user asked for it"\n') == []   # a reason is allowed anyway


def test_an_empty_file_has_no_entries(project, capsys):
    toml = with_requirements(project, text="# nothing yet\n")
    assert req(toml) == 0
    assert "hardware/requirements.toml: no needs, no requirements" in capsys.readouterr().out


def test_mistakes_stop_edakit_req_with_every_problem(project, capsys):
    toml = with_requirements(project, LED_BAR.replace('binding = "should"', 'binding = "shall"')
                             .replace('status = "draft"', 'status = "approved"'))
    assert req(toml) == 1
    err = capsys.readouterr().err
    assert "hardware/requirements.toml" in err and "R-3: binding" in err and "R-4: status" in err


def variant_of(project, own):
    """A variant next to the example, as the bell has them: variants/v with its own edakit.toml and requirements file,
    naming the main project's file and its own."""
    with_requirements(project)
    variant = project.root / "variants" / "v"
    (variant / "hardware").mkdir(parents=True)
    (variant / "hardware" / "requirements.toml").write_text(own, encoding="utf-8")
    toml = variant / "edakit.toml"
    toml.write_text('[project]\nname = "led-bar"\n'
                    'requirements = ["../../hardware/requirements.toml", "hardware/requirements.toml"]\n'
                    '[boards.v]\n', encoding="utf-8")
    return toml


def test_a_variant_reads_the_main_projects_file_and_its_own(project, capsys):
    own = ('[[requirement]]\nid = "R-5"\ntext = "The variant draws at most 300 mA from J1."\nfrom = ["N-1"]\n'
           'binding = "must"\nverify = [{ rows = "LIM.i * J1 current from the supply" }]\nstatus = "draft"\n')
    toml = variant_of(project, own)
    assert req(toml) == 0
    out = capsys.readouterr().out
    assert "../../hardware/requirements.toml: 4 needs, 4 requirements" in out
    assert "\nhardware/requirements.toml: no needs, 1 requirement" in out
    assert out.index("R-4") < out.index("R-5")                               # the main project's file first
    assert req(toml, "R-5") == 0
    assert "The bar runs from a USB charger" in capsys.readouterr().out      # its need is in the main project's file


def test_ids_are_unique_across_the_files_of_a_variant(project, capsys):
    toml = variant_of(project, REQUIREMENT)                                  # R-1 again, in the variant's own file
    assert req(toml) == 1
    err = capsys.readouterr().err
    assert "hardware/requirements.toml:\n  R-1: already in ../../hardware/requirements.toml" in err
