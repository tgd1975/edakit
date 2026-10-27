"""The plugin's agents and skills: a profile for every distributor the part search names, agents that load."""

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


def section(path, heading):
    """The text under the heading `## <heading>` of a skill or agent, up to the next one of that level – in lower case,
    with line breaks as spaces."""
    text = path.read_text(encoding="utf-8")
    found = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert found, f"{path.name}: no section '{heading}'"
    return " ".join(found.group(1).lower().split())


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
