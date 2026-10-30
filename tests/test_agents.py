"""Project agents (handbook 8.6): [agents.<name>] of edakit.toml. An agent signs a sign-off of its own, or takes over one
of edakit's reviews with replaces (decision 10). The reference project's elektrotechniker and pcb-pruefer and an agent
with a sign-off of its own green; every rule of the concept about agents (docs/concepts/new/project-scripts.md, "Checking
the TOML": R7, R9, R10, R11) seen red once – one fault per copy, as the concept's prototype did
(docs/concepts/new/prototypes/project-scripts/test_agents.py). The gate requires their sign-offs, each held to its
agent; the skills learn from edakit scripts who reviews at each hook point."""

import argparse
import json

import pytest
import test_gate as tg
import test_script_stamps as tss

from edakit import checks, requirements, scripts
from edakit.release import gate

# The reference project's two reviewers, as the concept registers them
PYTREE = """
[agents.elektrotechniker]
file     = ".claude/agents/elektrotechniker.md"
about    = "Checks circuit and hand-over with the project's knowledge: graph, parts, simulation, datasheets"
signs    = "M-1"
replaces = "electrical-reviewer"
phase    = "export"

[agents.pcb-pruefer]
file     = ".claude/agents/pcb-pruefer.md"
about    = "Checks the tree board for manufacturability, mechanics, operation and looks"
signs    = "M-5"
replaces = "pcb-reviewer"
phase    = "export"
"""
OPTIK = "Looks of the visible side: calm, symmetric, few tracks"
KAMERA = "Camera test of every delivered board: each LED at its place, the chain in order"


def agent(name, **fields):
    """An entry [agents.<name>]; a field given as None is left out."""
    return f"\n[agents.{name}]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in fields.items() if v is not None)


def own(name="optik", **more):
    """An agent with a sign-off of its own: M-7 on the layout hash, before the release."""
    return agent(name, **{"file": f".claude/agents/{name}.md", "about": OPTIK, "signs": "M-7", "scope": "layout",
                          "phase": "export", **more})


KAMERA_AGENT = agent("kamera", file=".claude/agents/kamera.md", about=KAMERA, signs="M-8", scope="fab",
                     phase="acceptance")


def agent_file(project, name, front=None):
    """A Claude Code agent file in the project, its name in the front matter."""
    tss.write(project, f".claude/agents/{name}.md", f"---\nname: {front or name}\ndescription: reviews the board for "
                                                     "the project\ntools: Read, Bash\n---\n\nYou review.\n")


def with_agents(project, entries, files=("elektrotechniker", "pcb-pruefer", "optik", "optik2", "kamera", "a", "b",
                                         "pcb-reviewer")):
    for name in files:
        agent_file(project, name)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + entries)
    return project.config()


def found(cfg):
    return [(f.rule, f.msg) for f in scripts.agents(cfg).findings]


# --- green ------------------------------------------------------------------------------------------------------------
def test_no_agents_no_change(project):
    """Without [agents] edakit's agents review where they always did, and nothing is found."""
    review = scripts.agents(project.config())
    assert review.findings == [] and review.signers == {}
    assert review.at == {
        "circuit": [("edakit:electrical-reviewer", "M-1: the circuit and its hand-over"),
                    ("edakit:regulatory-reviewer", "M-6: circuit and parts against the rules for the purpose")],
        "round": [("edakit:pcb-reviewer", "the round's Gerber export – findings, no sign-off")],
        "release": [("edakit:electrical-reviewer", "M-1: the critical parts again, with the polarity sheet"),
                    ("edakit:pcb-reviewer", "M-5: the gate run's manufacturing files")],
        "delivery": []}


def test_the_reference_projects_agents_take_over_two_reviews(project):
    """Red before step 3.2: [agents] was an unknown key. elektrotechniker and pcb-pruefer review where
    electrical-reviewer and pcb-reviewer would – pcb-pruefer the rounds too, which is no sign-off (#73)."""
    review = scripts.agents(with_agents(project, PYTREE))
    assert review.findings == []
    assert {sid: (a.name, a.replaces) for sid, a in review.signers.items()} == {
        "M-1": ("elektrotechniker", "electrical-reviewer"), "M-5": ("pcb-pruefer", "pcb-reviewer")}
    assert review.at == {
        "circuit": [("elektrotechniker", "M-1: the circuit and its hand-over – in place of electrical-reviewer"),
                    ("edakit:regulatory-reviewer", "M-6: circuit and parts against the rules for the purpose")],
        "round": [("pcb-pruefer", "the round's Gerber export – findings, no sign-off – in place of pcb-reviewer")],
        "release": [("elektrotechniker", "M-1: the critical parts again, with the polarity sheet – in place of "
                                         "electrical-reviewer"),
                    ("pcb-pruefer", "M-5: the gate run's manufacturing files – in place of pcb-reviewer")],
        "delivery": []}


def test_an_agent_with_a_sign_off_of_its_own(project):
    """By its scope: circuit at the circuit review, layout at the round review, fab between the two gate runs; phase
    acceptance after delivery. after orders it behind another agent of its hook point."""
    review = scripts.agents(with_agents(project, PYTREE + own(after=["pcb-pruefer"]) + KAMERA_AGENT))
    assert review.findings == []
    m7, m8 = review.signers["M-7"], review.signers["M-8"]
    assert (m7.name, m7.replaces, m7.scope, m7.phase, m7.hooks) == ("optik", "", "layout", "export", ("round",))
    assert (m8.name, m8.scope, m8.phase, m8.hooks) == ("kamera", "fab", "acceptance", ("delivery",))
    assert review.at["round"] == [
        ("pcb-pruefer", "the round's Gerber export – findings, no sign-off – in place of pcb-reviewer"),
        ("optik", "M-7 on the layout hash, after pcb-pruefer")]
    assert review.at["delivery"] == [("kamera", "M-8 on the fab hash")]
    for scope, hook in (("circuit", "circuit"), ("fab", "release")):
        toml = project.root / "edakit.toml"
        toml.write_text(toml.read_text().replace('scope = "layout"', f'scope = "{scope}"').replace(
            'scope = "circuit"', f'scope = "{scope}"'))
        assert scripts.agents(project.config()).signers["M-7"].hooks == (hook,)


def test_after_orders_agents_of_one_hook_point(project):
    """optik2 reviews after optik, whatever the order in edakit.toml."""
    cfg = with_agents(project, own("optik2", signs="M-8", after=["optik"]) + own())
    assert [who for who, _ in scripts.agents(cfg).at["round"]] == ["edakit:pcb-reviewer", "optik", "optik2"]


def test_after_an_agent_that_reviews_earlier_holds(project):
    """optik reviews the layout; elektrotechniker reviewed the circuit before it – the order holds by itself."""
    cfg = with_agents(project, PYTREE + own(after=["elektrotechniker"]))
    assert scripts.agents(cfg).findings == []


# --- every rule seen red ----------------------------------------------------------------------------------------------
FAULTS = {
    # R10: file (it exists), about, signs, phase export or acceptance; with an ID of its own also scope
    "file missing": (10, own(file=".claude/agents/fehlt.md"), "optik: file .claude/agents/fehlt.md does not exist"),
    "fields missing": (10, agent("optik", file=".claude/agents/optik.md", signs="M-7", scope="layout"),
                       "optik: about, phase missing – an agent needs file, about, signs and phase"),
    "phase unknown": (10, own(phase="later"), 'optik: phase = "later" – export or acceptance'),
    "phase order": (10, own(phase="order"), 'optik: phase = "order" – export or acceptance; in phase order the owner '
                                            "checks at the manufacturer, no agent gets there"),
    "scope missing": (10, agent("optik", file=".claude/agents/optik.md", about=OPTIK, signs="M-7", phase="export"),
                      "optik: scope missing – a sign-off of its own is bound to the hash of its scope: circuit, layout "
                      "or fab"),
    "scope unknown": (10, own(scope="board"), 'optik: scope = "board" – circuit, layout or fab'),
    "scope with an edakit review": (10, PYTREE.replace('replaces = "pcb-reviewer"',
                                                       'replaces = "pcb-reviewer"\nscope    = "layout"'),
                                    "pcb-pruefer: scope belongs to a sign-off of its own – M-5 keeps the scope the "
                                    "sign-off file gives it"),
    "an edakit review after delivery": (10, PYTREE.replace('replaces = "pcb-reviewer"\nphase    = "export"',
                                                           'replaces = "pcb-reviewer"\nphase    = "acceptance"'),
                                        'pcb-pruefer: M-5 is a review before the release – phase = "export"'),
    "another agent's file": (10, own(file=".claude/agents/pcb-pruefer.md"),
                             "optik: .claude/agents/pcb-pruefer.md is the agent pcb-pruefer (name in its front matter)"),
    "the name of an edakit agent": (10, own("pcb-reviewer"),
                                    "pcb-reviewer: the name of edakit's agent – a project agent needs a name of its "
                                    "own"),
    # R11: signs once per project; edakit's review only with replaces = the agent that signs it; never a human's
    "M-5 without replaces": (11, own(signs="M-5", scope=None),
                             'optik: signs M-5, edakit\'s layout review – only with replaces = "pcb-reviewer"'),
    "replaces the wrong agent": (11, own(signs="M-5", replaces="electrical-reviewer", scope=None),
                                 'optik: signs M-5, edakit\'s layout review – only with replaces = "pcb-reviewer", the '
                                 'agent that signs it otherwise (replaces = "electrical-reviewer")'),
    "a sign-off of the owner": (11, own(signs="M-2"), "optik: signs M-2 – the owner's check at the manufacturer, after "
                                                      "uploading: no agent signs it"),
    "the owner's acceptance": (11, own(signs="M-4"), "optik: signs M-4 – the owner's acceptance test after delivery: "
                                                     "no agent signs it"),
    "two agents, one sign-off": (11, own() + own("optik2"), "optik, optik2: both sign M-7 – a sign-off has one agent"),
    "replaces with a sign-off of its own": (11, own(replaces="pcb-reviewer"),
                                            'optik: replaces = "pcb-reviewer", but M-7 is no review of edakit – '
                                            "replaces goes with M-1, M-5 or M-6"),
    "no sign-off ID": (11, own(signs="optik"), 'optik: signs = "optik" – a sign-off is M-<number>, e.g. M-7'),
    # R9: after names other registered agents
    "after an unknown agent": (9, own(after=["optiker"]), "optik: after names optiker – there is no [agents.optiker]"),
    "after itself": (9, own(after=["optik"]), "optik: after names itself"),
    # R7: the agents' after make no cycle, also with the order of the hook points
    "after in a cycle": (7, own("a", after=["b"]) + own("b", signs="M-8", after=["a"]),
                         "a: in a cycle at the round review – a –[after]→ b –[after]→ a"),
    "after an agent that reviews later": (7, PYTREE + own(scope="circuit", after=["pcb-pruefer"]),
                                          "optik: after pcb-pruefer, which reviews later – pcb-pruefer first at the "
                                          "round review, optik at the circuit review"),
}


@pytest.mark.parametrize("fault", FAULTS)
def test_every_rule_seen_red(project, fault):
    rule, extra, msg = FAULTS[fault]
    got = found(with_agents(project, extra))
    assert {r for r, _ in got} == {rule}, got
    assert any(m.startswith(msg) for _, m in got), got


def test_a_flawed_entry_signs_nothing(project):
    """What the gate cannot bind – two agents for one sign-off, a human's sign-off – it requires of no agent; stage G
    fails on the finding instead."""
    review = scripts.agents(with_agents(project, own() + own("optik2") + own("a", signs="M-2")))
    assert review.signers == {}


# --- edakit check and the gate's stage G -----------------------------------------------------------------------------
def test_edakit_check_reports_the_agents(project, capsys):
    with_agents(project, own(file=".claude/agents/fehlt.md"))
    assert checks.main(project.config(), argparse.Namespace(release=False, json=None)) == 1
    out = capsys.readouterr().out
    assert "SYNC.agents – project agents complete: 1 error\n  G  optik: file .claude/agents/fehlt.md does not exist" in out
    assert "  SYNC.agents: Correct the entry in edakit.toml or add the agent file (handbook 8.6)." in out


def test_edakit_check_without_findings(project, capsys):
    with_agents(project, PYTREE + own())
    assert checks.main(project.config(), argparse.Namespace(release=False, json=None)) == 0
    assert not [line for line in capsys.readouterr().out.splitlines() if line.split()[1:2] == ["agents"]]


def test_stage_g_fails_on_the_agents_findings_and_passes_the_rest(project):
    cfg = with_agents(project, PYTREE)
    assert [(r["stage"], r["id"], r["result"], r["check"]) for r in scripts.agent_rows(cfg)] == [
        ("G", "SYNC.agents", "pass", "elektrotechniker: signs M-1 in place of electrical-reviewer – Checks circuit and "
                                "hand-over with the project's knowledge: graph, parts, simulation, datasheets"),
        ("G", "SYNC.agents", "pass", "pcb-pruefer: signs M-5 in place of pcb-reviewer – Checks the tree board for "
                                "manufacturability, mechanics, operation and looks")]
    (project.root / ".claude" / "agents" / "pcb-pruefer.md").unlink()
    rows = scripts.agent_rows(project.config())
    assert [(r["result"], r["check"]) for r in rows if r["result"] != "pass"] == [
        ("fail", "pcb-pruefer: file .claude/agents/pcb-pruefer.md does not exist")]


def test_without_agents_no_rows(project):
    assert scripts.agent_rows(project.config()) == []


# --- the gate requires their sign-offs, each held to its agent --------------------------------------------------------
HEAD = tg.HEAD


def signoff_file(project, *extra, signed=True, by=None):
    """The example's sign-off file for HEAD, every check signed (by its agent, or by `by`), plus extra entries."""
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s.update(HEAD)
    s["manual"] = [{**m, "done_by": (by or f"agent {m['id']}") if signed else None, "date": "2026-10-28"}
                   for m in s["manual"]] + list(extra)
    path.write_text(json.dumps(s))


def manual(project, sid):
    loaded, notes = gate.load_signoff(project.config(), HEAD)
    return next(m for m in loaded["manual"] if m["id"] == sid), loaded, notes


def test_a_sign_off_of_its_own_is_required(project):
    """M-7 is not in the sign-off file: open, in the phase and scope of the agent – the release waits for it."""
    with_agents(project, own())
    signoff_file(project)
    m7, loaded, notes = manual(project, "M-7")
    assert (m7["phase"], m7["scope"], m7["done_by"], m7["agent"]) == ("export", "layout", None, "optik")
    assert m7["text"] == f"{OPTIK} – the project agent optik, in its own session"
    assert "signoff.json: M-7 is missing – added as open, the project agent optik signs it ([agents.optik])" in notes
    d, reasons = gate.decide(tg.rows("pass"), [], loaded, tg.ALL, gate.STAGES)
    assert d == "NOT RELEASED" and reasons == ["1 manual check(s) before the export open: M-7 (section 6)"]


def test_a_sign_off_of_its_own_counts_for_its_hash_signed_by_its_agent(project):
    with_agents(project, own())
    m7 = {"id": "M-7", "phase": "export", "scope": "layout", "text": OPTIK, "done_by": "agent optik (own session)",
          "date": "2026-10-28", "note": "M-7: OK for layout hash l"}
    signoff_file(project, m7)
    got, loaded, _ = manual(project, "M-7")
    assert got["done_by"] == "agent optik (own session)"
    assert gate.decide(tg.rows("pass"), [], loaded, tg.ALL, gate.STAGES) == ("RELEASED", [])
    other = gate.load_signoff(project.config(), {**HEAD, "layout_sha256": "other"})[0]      # another layout
    assert next(m for m in other["manual"] if m["id"] == "M-7")["done_by"] is None


def test_a_sign_off_of_its_own_signed_by_another_does_not_count(project):
    with_agents(project, own())
    signoff_file(project, {"id": "M-7", "phase": "export", "scope": "layout", "text": OPTIK, "done_by": "owner",
                           "date": "2026-10-28"})
    m7, loaded, notes = manual(project, "M-7")
    assert m7["done_by"] is None
    assert ("signoff.json: M-7 is signed by owner – [agents.optik]: the project agent optik signs it; it does not count"
            in notes)
    assert gate.decide(tg.rows("pass"), [], loaded, tg.ALL, gate.STAGES)[0] == "NOT RELEASED"


def test_a_sign_off_for_another_scope_does_not_count(project):
    """The agent's entry binds its sign-off: signed for the circuit, it does not count for the layout."""
    with_agents(project, own())
    signoff_file(project, {"id": "M-7", "phase": "export", "scope": "circuit", "text": OPTIK, "done_by": "agent optik",
                           "date": "2026-10-28"})
    m7, _, notes = manual(project, "M-7")
    assert (m7["scope"], m7["done_by"]) == ("layout", None)
    assert ("signoff.json: M-7 has phase export and scope circuit, [agents.optik] phase export and scope layout – "
            "signed for another binding, it does not count") in notes


def test_replaces_holds_edakits_review_to_the_project_agent(project):
    """M-5 stays required; signed by edakit's pcb-reviewer it does not count once pcb-pruefer takes its place – the
    reference project's own wording counts."""
    with_agents(project, PYTREE)
    signoff_file(project, by="agent pcb-reviewer")
    m5, loaded, notes = manual(project, "M-5")
    assert (m5["done_by"], m5["agent"], m5["replaces"]) == (None, "pcb-pruefer", "pcb-reviewer")
    assert ("signoff.json: M-5 is signed by agent pcb-reviewer – [agents.pcb-pruefer]: the project agent pcb-pruefer "
            "signs it in place of pcb-reviewer; it does not count") in notes
    assert manual(project, "M-6")[0]["done_by"] == "agent pcb-reviewer"             # M-6: edakit's, as before
    d, reasons = gate.decide(tg.rows("pass"), [], loaded, tg.ALL, gate.STAGES)
    assert reasons == ["2 manual check(s) before the export open: M-1, M-5 (section 6)"]
    signoff_file(project, by="Agent pcb-pruefer (Claude, eigene Sitzung) – nach Vorgabe des Nutzers")
    assert manual(project, "M-5")[0]["done_by"].startswith("Agent pcb-pruefer")
    assert manual(project, "M-1")[0]["done_by"] is None                             # elektrotechniker's


def test_replaces_keeps_the_scope_of_the_sign_off_file(project):
    """An older M-5 with scope layout stays so, also with pcb-pruefer in place of pcb-reviewer."""
    with_agents(project, PYTREE)
    path = project.root / "hardware" / "signoff.json"
    signoff_file(project, by="agent pcb-pruefer")
    s = json.loads(path.read_text())
    next(m for m in s["manual"] if m["id"] == "M-5")["scope"] = "layout"
    path.write_text(json.dumps(s))
    m5 = gate.load_signoff(project.config(), {"state_sha256": "s", "layout_sha256": "l"})[0]
    assert next(m for m in m5["manual"] if m["id"] == "M-5")["done_by"] == "agent pcb-pruefer"


def test_a_required_review_the_file_lacks_names_the_agent_that_signs_it(project):
    with_agents(project, PYTREE)
    path = project.root / "hardware" / "signoff.json"
    s = json.loads(path.read_text())
    s["manual"] = [m for m in s["manual"] if m["id"] != "M-5"]
    path.write_text(json.dumps(s))
    m5, _, notes = manual(project, "M-5")
    assert (m5["scope"], m5["agent"], m5["replaces"]) == ("fab", "pcb-pruefer", "pcb-reviewer")
    assert "signoff.json: M-5 is missing – added as open, every release needs it" in notes


def test_the_gate_lists_who_signs_and_the_acceptance_agent(project, monkeypatch):
    """Offline: M-7 and the replaced M-1 open in section 6 with the project agent that signs them; kamera's M-8 is a
    line of the acceptance list after delivery and does not hold up the release."""
    with_agents(project, PYTREE + own() + KAMERA_AGENT)
    text = tg.gate_run(project, monkeypatch)
    six = tg.section(text, 6)
    assert ("- [ ] M-1 Critical parts (U1, U2, D1, the LEDs, J1) checked a second time against the datasheet, "
            "independently – e.g. by the agent electrical-reviewer in its own session – the project agent "
            "elektrotechniker signs it, in place of electrical-reviewer") in six
    assert f"- [ ] M-7 {OPTIK} – the project agent optik, in its own session\n" in six
    after = six.split("**after delivery, per board**\n")[1].split("\n\n")[0]
    assert after.splitlines()[1:] == [
        "- [ ] M-4 Acceptance test of every delivered board: visual check, supply current, every LED, the button",
        f"- [ ] M-8 {KAMERA} – the project agent kamera, in its own session"]
    reasons = tg.decision(text)
    assert "M-1, M-6, M-5, M-7 (section 6)" in reasons and "M-8" not in reasons
    one = tg.section(text, 1)
    assert "| G Graph |" in one
    assert "| G | SYNC.agents" not in tg.section(text, 2)                                # the entries resolve


def test_the_gate_fails_on_the_agents_findings(project, monkeypatch):
    with_agents(project, own(signs="M-5", scope=None))
    text = tg.gate_run(project, monkeypatch)
    assert ('| G | SYNC.agents (project agents complete) |  |  | optik: signs M-5, edakit\'s layout review – only with replaces = "pcb-reviewer"'
            in tg.section(text, 2))
    assert "check(s) failed (section 2)" in tg.decision(text)


# --- the skills learn who reviews where: edakit scripts ---------------------------------------------------------------
def test_edakit_scripts_lists_the_agents_and_who_reviews_where(project, monkeypatch, capsys):
    with_agents(project, PYTREE + own(after=["pcb-pruefer"]))
    code, out = tss.edakit(project, monkeypatch, capsys, "scripts")
    assert code == 0, out
    agents = out.split("The project's agents – [agents.<name>] of edakit.toml (handbook 8.6)\n\n")[1]
    lines = agents.splitlines()
    pad = " " * 18
    assert lines[:9] == [
        "elektrotechniker  signs M-1 in place of electrical-reviewer, phase export",
        pad + "Checks circuit and hand-over with the project's knowledge: graph, parts, simulation, datasheets",
        pad + ".claude/agents/elektrotechniker.md",
        "pcb-pruefer       signs M-5 in place of pcb-reviewer, phase export",
        pad + "Checks the tree board for manufacturability, mechanics, operation and looks",
        pad + ".claude/agents/pcb-pruefer.md",
        "optik             signs M-7 on the layout hash, phase export; after pcb-pruefer",
        pad + OPTIK,
        pad + ".claude/agents/optik.md"]
    who = agents.split("Who reviews where")[1]
    assert ("  round review – after a layout round that changed placement, routing or pours (skill pcb-round)\n"
            "    pcb-pruefer                 the round's Gerber export – findings, no sign-off – in place of "
            "pcb-reviewer\n"
            "    optik                       M-7 on the layout hash, after pcb-pruefer\n") in who
    assert "    edakit:regulatory-reviewer  M-6: circuit and parts against the rules for the purpose\n" in who
    assert who.rstrip().endswith("after delivery – a line of the acceptance list, which M-4 works through (section 6 "
                                 "of the protocol)\n    none")


def test_edakit_scripts_names_what_keeps_the_agents_from_resolving(project, monkeypatch, capsys):
    with_agents(project, own(after=["optiker"]))
    code, out = tss.edakit(project, monkeypatch, capsys, "scripts")
    assert code == 2
    assert ("The agents' entries do not resolve (edakit check, handbook 8.6):\n"
            "  optik: after names optiker – there is no [agents.optiker]") in out
    assert "Who reviews where" not in out


def test_edakit_scripts_without_agents_as_before(project, monkeypatch, capsys):
    code, out = tss.edakit(project, monkeypatch, capsys, "scripts")
    assert code == 0 and "agents" not in out


# --- what a requirement may name ---------------------------------------------------------------------------------------
def test_a_requirement_may_name_an_agents_sign_off(project):
    """DOCS.ref: signoff = "M-7" resolves once an agent signs M-7, before the sign-off file lists it."""
    with_agents(project, own())
    assert "M-7" in requirements.manual_checks(project.config())[0]


@pytest.mark.parametrize("done_by, name, named", [
    ("agent pcb-pruefer", "pcb-pruefer", True),
    ("Agent elektrotechniker (Claude, unabhängige Sitzung)", "elektrotechniker", True),
    ("AGENT OPTIK", "optik", True),
    ("agent pcb-reviewer", "pcb-pruefer", False),
    ("agent pcb-pruefer-2", "pcb-pruefer", False),
    ("agent pcb-reviewer", "pcb", False),
    ("owner", "optik", False),
    (None, "optik", False)])
def test_done_by_names_the_agent(done_by, name, named):
    """Its name as a word, in any case – not a part of another name."""
    assert scripts.names_agent(done_by, name) is named
