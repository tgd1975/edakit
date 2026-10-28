"""The plugin's agents and skills: a profile for every distributor the part search names, agents that load."""

import json
import re
from pathlib import Path

import pytest

from edakit.requirements import ENTRY_ID

ROOT = Path(__file__).resolve().parents[1]
REVIEWERS = {"electrical-reviewer": "M-1", "pcb-reviewer": "M-5", "regulatory-reviewer": "M-6"}   # agent: its sign-off


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    head = text.split("---", 2)[1]
    return dict(re.findall(r"^(\w[\w-]*): (.+)$", head, re.M))


def test_every_distributor_of_the_part_search_has_a_profile():
    skill = (ROOT / "skills" / "part-search" / "SKILL.md").read_text(encoding="utf-8")
    named = re.search(r"\(`lcsc`[^)]*\)", skill).group(0)
    names = re.findall(r"`(\w+)`", named)
    assert names == ["lcsc", "rs", "farnell", "mouser", "digikey", "reichelt"]
    profiles = {p.stem for p in (ROOT / "skills" / "part-search" / "distributors").glob("*.md")}
    assert profiles == set(names)


def test_agents_have_name_description_and_tools():
    for path in sorted((ROOT / "agents").glob("*.md")):
        meta = frontmatter(path)
        assert meta.get("name") == path.stem, path
        assert len(meta.get("description", "")) > 80, path
        assert "tools" not in meta or "Read" in meta["tools"], path


def test_skills_have_name_and_description():
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        meta = frontmatter(path)
        assert meta.get("name") == path.parent.name, path
        assert len(meta.get("description", "")) > 80, path


def test_every_skill_and_agent_is_listed():
    """What the plugin brings is in the table of handbook 11.1 and in the README: every skill as /edakit:<name>, every
    agent by its name."""
    chapter = (ROOT / "handbook" / "11-working-with-claude.md").read_text(encoding="utf-8")
    table = chapter.split("## 11.1 ")[1].split("## 11.2 ")[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")):
        assert f"`/edakit:{name}`" in table and f"`/edakit:{name}`" in readme, name
    for name in sorted(p.stem for p in (ROOT / "agents").glob("*.md")):
        assert f"`edakit:{name}`" in table and f"`{name}`" in readme, name


def flat(text):
    """Lower case, line breaks as spaces: a sentence wrapped over two lines still reads as one."""
    return " ".join(text.lower().split())


def section(path, heading, raw=False):
    """The text under the heading `## <heading>` of a skill or agent, up to the next one of that level."""
    text = path.read_text(encoding="utf-8")
    found = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert found, f"{path.name}: no section '{heading}'"
    return found.group(1) if raw else flat(found.group(1))


def test_the_electrical_review_asks_what_no_check_answers_yet():
    look = section(ROOT / "agents" / "electrical-reviewer.md", "What you look at")
    assert "not covered by a check yet" in look
    classes = [("back-feed",), ("switch-over",), ("pwm slice",), ("header",), ("supply range", "vih"),
               ("clock edge", "spi mode"), ("touch temperature",), ("off-board module",)]
    missing = [words for words in classes if not any(w in look for w in words)]
    assert not missing, missing



def test_the_reviewers_name_the_checks_that_now_answer_part_of_a_class():
    """A question a check covers in part names that check, and every ID a reviewer names is in the catalogue – or is
    one of the reviewers' sign-offs, or a need N-… or requirement R-… of a project's requirements file (handbook 3.6),
    which the catalogue never names: it has no check of the letters N and R."""
    rules = json.loads((ROOT / "edakit" / "rules.json").read_text(encoding="utf-8"))
    known = {*rules["checks"], *rules["hints"], *REVIEWERS.values()}
    look = section(ROOT / "agents" / "electrical-reviewer.md", "What you look at")
    sources = look.split("**several sources**")[1].split("**mcu pin functions**")[0]
    supply = look.split("**supply range")[1].split("**read-back")[0]
    assert "e-5" in sources and "transients" in sources and "`copper`" in supply
    pcb = section(ROOT / "agents" / "pcb-reviewer.md", "What you look at")
    assert all(cid in pcb for cid in ("l-15", "l-16", "l-17", "l-18"))
    for agent in REVIEWERS:
        named = set(re.findall(r"\b[A-Z]-\d+\b", (ROOT / "agents" / f"{agent}.md").read_text(encoding="utf-8")))
        foreign = {cid for cid in named - known if not ENTRY_ID.fullmatch(cid)}
        assert not foreign, (agent, foreign)


@pytest.mark.parametrize("agent, signoff", REVIEWERS.items())
def test_each_reviewer_judges_the_requirements_its_sign_off_verifies(agent, signoff):
    """With [project] requirements a reviewer reads the file, judges the requirements whose verify names its sign-off,
    and gives the IDs of the ones it found met for the note – the gate counts an ID in the note as passing evidence
    (handbook 8.7), so one not met is a finding and stays out of it."""
    path = ROOT / "agents" / f"{agent}.md"
    sources = section(path, "Sources")
    assert "[project] requirements" in sources and "edakit req" in sources, agent
    sign = section(path, f"For the {signoff} sign-off")
    for words in (f'signoff = "{signoff.lower()}"', "note", "requirements met", "finding"):
        assert words in sign, (agent, words)


def test_for_the_electrical_review_the_file_replaces_what_the_firmware_relies_on():
    """The requirements file takes the place of the requirements the firmware relies on – those stay its source in a
    project without one."""
    sources = section(ROOT / "agents" / "electrical-reviewer.md", "Sources")
    assert "requirements file" in sources and "without one" in sources


def test_circuit_design_reads_the_requirements_file_instead_of_asking():
    """§1 reads the file when [project] requirements names one; what it lacks goes to the skill requirements, a new
    function starts with its requirement, and the report says which parts meet which requirement."""
    path = ROOT / "skills" / "circuit-design" / "SKILL.md"
    first = section(path, "1. Requirements")
    for words in ("[project] requirements", "edakit req", "instead of asking", "skill requirements",
                  "a new function starts with its requirement"):
        assert words in first, words
    assert "which parts meet which requirement" in section(path, "Report")


def test_the_requirements_skill_drafts_and_the_user_accepts():
    """The skill requirements, in the conversation: the agent's inventory first, the questions of the concept in one
    decision round, its four rules, drafts in the file that only the user accepts – the file and the decision log
    are all it writes, and only for the circuit."""
    path = ROOT / "skills" / "requirements" / "SKILL.md"
    text = flat(path.read_text(encoding="utf-8"))
    for words in ("hardware/requirements.toml", "agent requirements-engineer", "inventory", "skill decision-round",
                  'status = "draft"', "only the user", "agreement 4", "never the graph", "decision log",
                  "only the circuit", "firmware", "mechanics", "edakit req", "edakit check", "second opinion"):
        assert words in text, words
    asked = section(path, "1. Ask")
    for topic in ("people", "course", "surroundings", "operation", "limits", "frame", "non-goals"):
        assert f"| {topic} |" in asked, topic
    for rule in ("vague words become numbers", "contradictions become questions", "stays open",
                 "every requirement gets evidence"):
        assert rule in asked, rule
    evidence = section(path, "3. Evidence")
    assert all(f"`{kind}`" in evidence for kind in ("rows", "signoff", "accept", "script"))


def test_the_requirements_engineer_reads_everything_and_changes_nothing():
    """The agent has no tool that writes, and returns what the skill turns into a decision round: candidates with
    the place they were found, contradictions, vague words, requirements without evidence."""
    path = ROOT / "agents" / "requirements-engineer.md"
    tools = {t.strip() for t in frontmatter(path)["tools"].split(",")}
    assert "Read" in tools and not tools & {"Write", "Edit", "NotebookEdit"}
    assert "change no files" in flat(path.read_text(encoding="utf-8"))
    result = section(path, "Result")
    for words in ("candidates", "`source`", "contradictions", "vague words", "without evidence",
                  "left to the project's documents"):
        assert words in result, words


def test_a_new_project_may_have_a_requirements_file():
    files = section(ROOT / "skills" / "new-project" / "SKILL.md", "1. Files")
    assert "hardware/requirements.toml" in files and "optional" in files and "skill requirements" in files


def test_circuit_design_reads_pin_functions_and_header_pins():
    pins = section(ROOT / "skills" / "circuit-design" / "SKILL.md", "3. Parts and pins")
    for words in ("pwm slice", "peripheral instance", "adc", "header", "errata", "supply range", "vih"):
        assert words in pins, words


def step(text, number):
    """Item `<number>.` of a numbered list, up to the next item or the end."""
    found = re.search(rf"^{number}\. (.*?)(?=^\d+\. |\Z)", text, re.M | re.S)
    assert found, f"no step {number}"
    return flat(found.group(1))


def test_every_layout_round_and_circuit_hand_over_ends_with_its_review():
    round_ = step(section(ROOT / "skills" / "pcb-round" / "SKILL.md", "Round", raw=True), 5)
    for words in ("pcb-reviewer", "placement", "routing", "pours", "before the gate", "silkscreen"):
        assert words in round_, words
    hand_over = section(ROOT / "skills" / "hardware-change" / "SKILL.md", "3. Hand-over to the layout")
    for words in ("electrical-reviewer", "power path", "before"):
        assert words in hand_over, words


def test_the_layout_review_reads_the_rounds_copper_per_layer():
    sources = section(ROOT / "agents" / "pcb-reviewer.md", "Sources")
    assert "gerber_<board>" in sources and "silk apply" in sources
    assert "copper of every layer" in sources
    look = section(ROOT / "agents" / "pcb-reviewer.md", "What you look at")
    assert "bare" in look and "floating copper" in look


def test_both_reviewers_weigh_every_finding_by_probability_and_cost():
    for agent in ("pcb-reviewer", "electrical-reviewer"):
        result = section(ROOT / "agents" / f"{agent}.md", "Result")
        for words in ("probability", "cost", "without a realistic consequence"):
            assert words in result, (agent, words)


def test_session_start_hook_runs_the_agreements_digest():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    commands = [h["command"] for entry in hooks.get("SessionStart", []) for h in entry["hooks"]]
    assert commands == ['python3 "${CLAUDE_PLUGIN_ROOT}/edakit/agreements.py"']
    assert hooks["PreToolUse"], "the EasyEDA claim stays"


def test_the_lcsc_profile_searches_the_catalogue_first_and_three_routes_before_not_available():
    """#37: a false "does not exist" after one route cost the reference project 45 minutes."""
    text = (ROOT / "skills" / "part-search" / "distributors" / "lcsc.md").read_text(encoding="utf-8")
    steps = re.findall(r"^(\d)\. \*\*(.+?)\*\*(.*)$", text, re.M)
    assert [n for n, _, _ in steps] == ["1", "2", "3"]
    assert "edakit part search" in steps[0][2] and "easyeda_schematic_search_device" in steps[1][2]
    assert "series name" in steps[2][1]
    order = text.index("**Search in this order.**")
    assert "not available only after all three routes" in text[order:text.index("1. **")]
    agent = (ROOT / "agents" / "part-selector.md").read_text(encoding="utf-8")
    assert "edakit part search" in agent and "three routes" in agent
