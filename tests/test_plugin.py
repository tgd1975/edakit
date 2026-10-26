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
