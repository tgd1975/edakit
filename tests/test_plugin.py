"""The plugin's agents and skills: a profile for every distributor the part search names, agents that load."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
