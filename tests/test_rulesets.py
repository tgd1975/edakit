"""The protection of main as text (.github/rulesets/, .github/rulesets.py, docs/concepts/new/versioning.md): the
checks main requires are the ones merge.py waits for, nobody may bypass main or move a version's tag, only the
admin role merges, and the comparison with GitHub ignores what GitHub adds."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    sys.path.insert(0, str(ROOT / ".github"))
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / ".github" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


rs = _load("rulesets")
merge = _load("merge")
RULESETS, SETTINGS = rs.wanted()


def rules(name):
    return {r["type"]: r.get("parameters", {}) for r in RULESETS[name]["rules"]}


def test_main_requires_the_checks_merge_waits_for_not_strict():
    checks = rules("main")["required_status_checks"]
    assert [c["context"] for c in checks["required_status_checks"]] == list(merge.REQUIRED)
    assert checks["strict_required_status_checks_policy"] is False


def test_main_takes_pull_requests_only_and_nobody_bypasses_it():
    main = rules("main")
    assert {"deletion", "non_fast_forward", "pull_request"} <= set(main)
    assert main["pull_request"]["required_approving_review_count"] == 0   # the sessions are the owner
    assert RULESETS["main"]["bypass_actors"] == [] and RULESETS["tags"]["bypass_actors"] == []


def test_no_ruleset_bypasses_and_none_needs_a_flag_to_merge():
    # main-updates went on 2026-11-01: its bypass needs --admin on every merge, which auto mode refuses
    assert set(RULESETS) == {"main", "tags"}
    assert all(not r["bypass_actors"] for r in RULESETS.values())


def test_a_version_once_out_is_never_moved():
    assert RULESETS["tags"]["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]
    assert {"deletion", "update", "non_fast_forward"} == set(rules("tags"))     # creating stays open


def test_merge_commits_only_and_head_branches_deleted():
    assert SETTINGS == {"allow_merge_commit": True, "allow_squash_merge": False, "allow_rebase_merge": False,
                        "delete_branch_on_merge": True}


def test_the_comparison_ignores_what_github_adds():
    live = json.loads(json.dumps(RULESETS["main"]))
    live.update(id=7, source="tgd1975/edakit", node_id="x", _links={})
    live["rules"] = list(reversed(live["rules"]))
    live["rules"][0]["parameters"]["do_not_enforce_on_create"] = False
    live["rules"][1]["parameters"]["allowed_merge_methods"] = ["merge", "squash", "rebase"]
    want = {"main": RULESETS["main"]}
    assert rs.differences({"main": live}, dict(SETTINGS, id=1), want, SETTINGS) == []


def test_the_comparison_names_what_differs():
    live = json.loads(json.dumps(RULESETS["main"]))
    live["rules"] = [r for r in live["rules"] if r["type"] != "deletion"] + [{"type": "creation"}]
    found = rs.differences({"main": live, "old": {}}, dict(SETTINGS, allow_squash_merge=True),
                           {"main": RULESETS["main"], "tags": RULESETS["tags"]}, SETTINGS)
    assert [w for w, _, _ in found] == ["ruleset main", "ruleset tags", "ruleset old", "settings"]


def test_merge_numbers_again_only_a_version_whose_main_moved():
    assert merge.again("0.3.1", "0.3.0", "0.3.1")
    assert not merge.again("0.3.1", "0.3.0", "0.3.0")
    assert not merge.again(None, "0.3.0", "0.3.1")      # no version: merges onto any main


def test_the_scripts_merge_plainly():
    assert merge.MERGE == ("--merge",)
    for script in ("merge.py", "notes.py"):
        assert "--admin" not in (ROOT / ".github" / script).read_text()
