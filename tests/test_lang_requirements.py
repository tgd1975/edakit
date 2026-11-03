"""T.15 of circuit-dsl-toolchain.md: requirements in the notation (language 5.11) – a .circuit requirements file read
to the entries of the TOML form; subject, require and satisfied_by; DOCS.ref on subject, satisfies and decision."""

import hashlib

from helpers import check
from lang_examples import REQUIREMENTS
from test_lang_use import HEAD, step

from edakit import cli
from edakit.design import Design
from edakit.release import gate
from edakit.requirements import read

TOML = '''[[need]]
id = "N-1"
text = "The countdown is visible across the room."
who = "owner"
status = "accepted"

[[requirement]]
id = "R-3"
text = "Every countdown LED carries 2 to 15 mA while its step is on."
from = ["N-1"]
binding = "must"
subject = "led"
require = "D.i within 2 mA .. 15 mA"
verify = [{ rows = "LIM.i *" }, { rows = "SIM.state *" }]
status = "accepted"

[[requirement]]
id = "R-7"
text = "A USB power bank stays on: the circuit draws at least 100 mA."
from = ["D-8"]
binding = "should"
subject = "+5V"
verify = [{ signoff = "M-1" }]
'''


def project_with(project, reqs=REQUIREMENTS, head=HEAD + "net +5V 0..5.5 V\n"):
    step(project, None, head)
    (project.root / "hardware" / "requirements.circuit").write_text(reqs, encoding="utf-8")
    toml = project.root / "edakit.toml"
    text = toml.read_text().replace('graph = "hardware/graph.json"', 'graph = "hardware/graph.circuit"')
    if "requirements = " not in text:
        text = text.replace("[project]\n", '[project]\nrequirements = "hardware/requirements.circuit"\n', 1)
    toml.write_text(text)
    return project.config()


def plain(entries):
    return [(e.kind, e.id, e.text, e.status, e.who, e.from_, e.binding, e.verify, e.subject, e.require)
            for e in entries]


def test_the_notation_reads_to_the_toml_form_s_entries(tmp_path):
    (tmp_path / "r.circuit").write_text(REQUIREMENTS)
    (tmp_path / "r.toml").write_text(TOML)
    a, pa = read(tmp_path / "r.circuit")
    b, pb = read(tmp_path / "r.toml")
    assert pa == pb == [] and plain(a) == plain(b)


def test_edakit_req_lists_subject_and_require(project, capsys):
    project_with(project)
    assert cli.main(["req", "--config", str(project.root / "edakit.toml")]) == 0
    out = capsys.readouterr().out
    assert "subject: led" in out and "require: D.i within 2 mA .. 15 mA" in out


def docs_ref(cfg):
    rep = check(Design.from_config(cfg), cfg)
    return [m for c, m in rep.errors + rep.warnings + rep.drafts if c == "DOCS.ref"]


def test_a_subject_of_the_graph_resolves_and_one_of_nothing_does_not(project):
    cfg = project_with(project)
    assert not [m for m in docs_ref(cfg) if "subject" in m]
    cfg = project_with(project, REQUIREMENTS.replace("subject +5V", "subject +12V"))
    assert any("R-7: subject +12V – no part, net, usage or definition" in m for m in docs_ref(cfg))


def test_a_require_of_no_form(project):
    cfg = project_with(project, REQUIREMENTS.replace("require D.i within 2 mA .. 15 mA", "require D.i is fine"))
    assert any("R-3: require 'D.i is fine' – a quantity reference" in m for m in docs_ref(cfg))


def test_satisfies_and_decision_on_the_graph(project):
    head = HEAD.replace('"Arduino Nano"', '"Arduino Nano"\n  satisfies R-3 R-9\n  decision D-8 D-99') + \
        "net +5V 0..5.5 V\n"
    cfg = project_with(project, head=head)
    found = docs_ref(cfg)
    assert any("U1: satisfies R-9 – no requirement R-9" in m for m in found)
    assert not any("decision" in m for m in found)                           # no decision log: unchecked
    (project.root / "docs").mkdir(exist_ok=True)
    (project.root / "docs" / "decisions.md").write_text("# Decisions\n\n## D-8 The LEDs\n")
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[release]\n", '[release]\npublish = { decisions = "docs/decisions.md" }\n'))
    found = docs_ref(project.config())
    assert any('U1: decision D-99 – no heading "## D-99"' in m for m in found)
    assert not any("D-8" in m and "decision" in m for m in found)
    from edakit.requirements import load
    from edakit.requirements import graph_refs
    entries = load(project.config())
    by_id = {e.id: e for e in entries}
    graph_refs(project.config(), [e for e in entries if e.kind == "requirement"], by_id)
    assert by_id["R-3"].satisfied_by == ["U1"]


def test_the_hash_takes_the_file_s_bytes(project):
    cfg = project_with(project)
    path = project.root / "hardware" / "requirements.circuit"
    assert path in gate.state_files(cfg)
    h = gate.state_hash(cfg)
    path.write_text(REQUIREMENTS + "# a comment\n")
    assert gate.state_hash(project.config()) != h
    assert hashlib.sha256(path.read_bytes()).hexdigest()
