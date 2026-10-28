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
    files = section(ROOT / "skills" / "new-project" / "SKILL.md", "3. Files")
    assert "hardware/requirements.toml" in files and "optional" in files and "skill requirements" in files


# The interview of the setup (concept project-setup): each topic and the keys its answer sets.
INTERVIEW = {
    "board": ("[boards.<name>]", "title", "board file"),
    "boards": ("bought = true",),
    "variants": ("variants/<v>/edakit.toml",),
    "assembly": ("[release] assembly", "sides", "pcba", "smd_only"),
    "order": ("[project] quantity", "[order]", "thickness_mm"),
    "money": ("[cost]", "budget", "currency"),
    "purpose": ("purpose", "use", "market", "m-6"),
    "requirements": ("skill requirements", "[project] requirements"),
    "firmware": ("[firmware]", "edakit firmware --check"),
    "documents": ("[docs] files",),
    "own tools": ("[scripts.<name>]", "[agents.<name>]"),
}


def test_new_project_has_two_ways_and_sets_every_key_from_an_answer():
    """Step 3.7: one entry point with two ways – new, and moving with the inventory of project-surveyor and
    requirements-engineer first –, the interview as a form where the tool offers one (AskUserQuestion, up to four
    questions per call), otherwise one decision round in text, and per topic the keys its answer sets. It writes after
    the user's OK and ends with a report that lists the project's own skills, deleting none."""
    path = ROOT / "skills" / "new-project" / "SKILL.md"
    way = section(path, "0. Which way")
    assert "**new:**" in way and "**moving:**" in way and "no `edakit.toml`" in way
    inventory = section(path, "1. Inventory (moving)")
    assert "**project-surveyor**" in inventory and "**requirements-engineer**" in inventory
    interview = section(path, "2. Interview")
    for words in ("one round", "askuserquestion", "up to four questions per call", "decision round in text",
                  "the inventory's answer", "stays open with its default", "decision log"):
        assert words in interview, words
    rows = dict(re.findall(r"^\| ([a-z ]+) \| (.*)$", section(path, "2. Interview", raw=True), re.M))
    assert set(rows) == set(INTERVIEW), set(rows) ^ set(INTERVIEW)
    for topic, keys in INTERVIEW.items():
        missing = [key for key in keys if key not in flat(rows[topic])]
        assert not missing, (topic, missing)
    text = flat(path.read_text(encoding="utf-8"))
    assert "only after the user's ok" in text and "no silent change" in text
    guard = section(path, "4. Guard rails")
    for words in ("edakit check", "edakit sim", "edakit firmware --check", "edakit docs", "--no-verify", ".mcp.json",
                  "edakit@edakit"):
        assert words in guard, words
    hand_over = section(path, "5. First run and hand-over")
    for words in ("skill requirements", "circuit-design", "start skill", "createproject", "edakit scripts"):
        assert words in hand_over, words
    report = section(path, "Report")
    for words in ("open", "skill by skill", "deletes none", "next"):
        assert words in report, words


def units(path):
    """Paragraphs, list items and table rows of a skill or agent – each says one thing."""
    out, current = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or re.match(r"\s*(\||- |\d+\. )", line):
            if current:
                out.append(flat(" ".join(current)))
            current = [line] if line.strip() else []
        else:
            current.append(line)
    return out + ([flat(" ".join(current))] if current else [])


def test_where_the_setup_speaks_of_the_purpose_and_m6_the_review_is_support_not_legal_advice():
    """The user's wording wherever regulation comes up: the regulatory review is support, not legal advice – nothing
    in it is legally guaranteed, and it claims no correctness. In the skill: the purpose of the interview and the
    report; in the agent: the purpose among the interview's answers."""
    for path, least in ((ROOT / "skills" / "new-project" / "SKILL.md", 2), (ROOT / "agents" / "project-surveyor.md", 1)):
        speaking = [u for u in units(path) if "purpose" in u and "m-6" in u]
        assert len(speaking) >= least, path.name
        for unit in speaking:
            for words in ("support, not legal advice", "nothing in it is legally guaranteed", "claims no correctness"):
                assert words in unit, (path.name, words, unit[:80])


def test_the_project_surveyor_reads_a_repository_and_changes_nothing():
    """Step 3.7: the agent has no tool that writes and runs nothing of the project; it returns numbered lists per
    edakit place – the places of the concept's inventory, each candidate with where it was found, the proposal and its
    reason, the interview's answers –, then contradictions, what it could not read and a count per place."""
    path = ROOT / "agents" / "project-surveyor.md"
    assert {t.strip() for t in frontmatter(path)["tools"].split(",")} == {"Read", "Grep", "Glob", "Bash"}
    text = flat(path.read_text(encoding="utf-8"))
    assert "change no files" in text and "run nothing of the project" in text
    places = section(path, "The places", raw=True)
    numbered = re.findall(r"^(\d+)\. \*\*(.+?)\*\*(.*?)(?=^\d+\. \*\*|^Each candidate|\Z)", places, re.M | re.S)
    assert [int(n) for n, _, _ in numbered] == list(range(1, len(numbered) + 1))
    place = {name.lower(): flat(body) for _, name, body in numbered}
    for name in ("hardware data", "easyeda project and released runs", "scripts", "agents", "skills",
                 "documents with values", "decisions", "guard rails", "the interview's answers", "requirements"):
        assert name in place, name
    for words in ("`[scripts.<name>]`", "`kind`", "`reads`", "`writes`", "`about`", "the project's business"):
        assert words in place["scripts"], words
    for words in ("`[agents.<name>]`", "`signs`", "`replaces`"):
        assert words in place["agents"], words
    for words in ("counterpart", "not registered", "the user's decision, skill by skill"):
        assert words in place["skills"], words
    assert "`[docs] files`" in place["documents with values"] and "requirements-engineer" in place["requirements"]
    form = flat(places)
    assert all(f"**{field}**" in form for field in ("found", "proposal", "reason"))
    result = section(path, "Result")
    for words in ("**contradictions**", "**not read**", "**count**"):
        assert words in result, words


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


def test_the_skills_start_the_projects_agents_where_edakit_scripts_says():
    """Step 3.2: a project agent ([agents.<name>], handbook 8.6) reviews at its hook point, and one with replaces in
    place of the edakit agent it replaces – the skills that start reviewers learn from edakit scripts who reviews where,
    and the gate counts a project agent's sign-off only when done_by names it."""
    skills = ROOT / "skills"
    places = {
        "circuit review": section(skills / "circuit-design" / "SKILL.md", "7. Hand over"),
        "circuit review, again": section(skills / "hardware-change" / "SKILL.md", "3. Hand-over to the layout"),
        "round review": step(section(skills / "pcb-round" / "SKILL.md", "Round", raw=True), 5),
        "layout review": step(section(skills / "release" / "SKILL.md", "Procedure", raw=True), 5),
    }
    for place, text in places.items():
        for words in ("[agents.<name>]", "edakit scripts", "who reviews where", "in place of", "replaces"):
            assert words in text, (place, words)
    assert "done_by" in places["layout review"] and "names" in places["layout review"]
    delivery = flat((skills / "release" / "SKILL.md").read_text(encoding="utf-8").split("After delivery:")[1])
    assert "project agents of phase acceptance" in delivery


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
