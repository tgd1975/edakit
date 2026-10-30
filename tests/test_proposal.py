from edakit import cli, proposal

FILLED = """## hole fits the lead

### Kind
relation

### Rule
Every plated hole of a THT footprint is at least 0.2 mm larger than the lead it takes.

### Why
Header tails of 0.64 mm square need 0.9 mm diagonal plus plating – 0.9 mm holes do not take them.

### Finding
U1 (Nano footprint): holes 0.9 mm, header tails 0.64 mm square (0.91 mm diagonal); commit 3a613ed.

### Fix
A footprint with 1.0–1.1 mm holes.

### Sources
- IPC-2222A, section 9.2.1
- handbook 13.6

### Origin
- project: tgd1975/automatic_christmas_bell
- decision: D-17 in docs/decisions.md
- commit: 3a613ed
"""

FEATURE = """## zero-ohm bridges join their nets

### Kind
feature

### Capability
A 0 Ω resistor (value_ohm 0) joins its two nets for the checks and the simulation, as copper would.

### Gap
`edakit check` on the origin: LVL.undefined on TLC_OE (pull-up behind R35) and REQ.missing on V_LED (capacitors behind R55), both
false; `edakit sim` stops with ZeroDivisionError in stress().

### Reference
pytree hardware/graph/check_graph.py bridged() at 9d9efad: nets joined through parts with value_ohm 0 count as one
for LVL.undefined and REQ.missing; run_sims.py uses r_max_ohm instead of 0.

### Interface
none – a parts entry with value_ohm 0 is enough.

### Test
The example gets a 0 Ω bridge between the button's pull-up and 3V3: today LVL.undefined fires and sim crashes, then neither.

### Origin
- project: pytree (private)
- decision: EK-2 in docs/concepts/offen/edakit.md
- commit: 9d9efad
"""


def test_template_is_not_sealed_unfilled():
    body, problems = proposal.seal(proposal.template())
    assert body is None
    assert len(problems) == 1 + len(proposal.SECTIONS)      # the title and every section


def test_sealed_text_verifies():
    body, problems = proposal.seal(FILLED)
    assert problems == []
    assert proposal.SEAL.match(body.rstrip().split("\n")[-1])
    assert proposal.verify(body) == []


def test_changed_text_fails_the_checksum():
    body, _ = proposal.seal(FILLED)
    problems = proposal.verify(body.replace("0.2 mm", "0.1 mm"))
    assert problems == ["the checksum does not match: the text was changed after it was sealed"]


def test_round_trip_through_github_keeps_the_checksum():
    body, _ = proposal.seal(FILLED)
    assert proposal.verify(body.replace("\n", "  \r\n").rstrip()) == []


def test_sealing_again_replaces_the_seal():
    body, _ = proposal.seal(FILLED)
    again, problems = proposal.seal(body.replace("0.2 mm", "0.25 mm"))
    assert problems == [] and again.count("edakit-proposal v") == 1
    assert proposal.verify(again) == []


def test_unsealed_missing_and_unknown():
    text = FILLED.replace("### Fix\nA footprint with 1.0–1.1 mm holes.\n", "").replace("relation\n", "rule\n", 1)
    problems = proposal.verify(text)
    assert problems[0].startswith("no seal")
    assert any("section 'Fix' is missing" in p for p in problems)
    assert any(p.startswith("kind 'rule'") for p in problems)


def test_kinds_of_the_restructuring_and_of_before():
    """fact, relation, domain, block, retire; a proposal sealed before the restructuring (check, hint, part) still
    verifies – the triage reads check and hint as relation, part as fact."""
    assert "one of: fact, relation, domain, block, retire" in proposal.template()
    for kind in (*proposal.RULE_KINDS, *proposal.OLD_KINDS):
        body, problems = proposal.seal(FILLED.replace("relation\n", f"{kind}\n", 1))
        assert problems == [] and proposal.verify(body) == [], kind


def test_cli(tmp_path, capsys):
    draft, body = tmp_path / "draft.md", tmp_path / "body.md"
    draft.write_text(FILLED)
    assert cli.main(["proposal", "seal", str(draft), "--out", str(body)]) == 0
    assert cli.main(["proposal", "verify", str(body)]) == 0
    body.write_text(body.read_text().replace("U1", "U2"))
    assert cli.main(["proposal", "verify", str(body)]) == 2
    assert "checksum does not match" in capsys.readouterr().out


def test_feature_template_has_its_kind_and_its_sections():
    text = proposal.template(proposal.FEATURE)
    assert "### Kind\nfeature" in text and "### Gap" in text and "### Rule" not in text
    body, problems = proposal.seal(text)
    assert body is None
    assert len(problems) == len(proposal.FEATURE_SECTIONS)     # the title and every section but Kind


def test_feature_proposal_verifies_with_its_own_sections():
    body, problems = proposal.seal(FEATURE)
    assert problems == [] and proposal.verify(body) == []
    body, problems = proposal.seal(FEATURE.replace("### Interface", "### Fix"))
    assert body is None and any("section 'Interface' is missing" in p for p in problems)


def test_rule_sections_do_not_make_a_feature():
    problems = proposal.check(FILLED.replace("relation\n", "feature\n", 1))
    assert any("section 'Capability' is missing" in p for p in problems)
    assert not any("kind" in p for p in problems)


def test_cli_feature_template(capsys):
    assert cli.main(["proposal", "template", "--feature"]) == 0
    assert "### Capability" in capsys.readouterr().out
