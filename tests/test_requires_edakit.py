"""A project states the edakit it needs (TD-50, docs/concepts/done/versioning.md V.7): `edakit = ">=0.4"` under
[project] in edakit.toml. edakit check notes STRUCT.edakit when the running edakit does not meet it, and the
SessionStart hook names the edakit that runs – so a plugin and a command line pinned apart do not drift unnoticed."""

import pytest
from test_agreements import context, led_bar, run_hook

from edakit import __version__, config, engines
from edakit.design import Design
from edakit.version import meets


def set_edakit(project, required):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("[project]\n", f"[project]\nedakit = {required!r}\n", 1)
                    .replace("'", '"'))


def findings(project):
    cfg = project.config()
    return [f for f in engines.run(Design.from_config(cfg), cfg).findings if f.code == "STRUCT.edakit"]


@pytest.mark.parametrize("required, have, ok", [
    (">=0.4", "0.4.11", True), (">=0.4", "0.3.9", False), (">=0.4, <0.5", "0.5.0", False),
    ("==0.4.11", "0.4.11", True), ("<1", "0.9.9", True), (">0.4.11", "0.4.11", False), ("<=0.4", "0.4.0", True),
])
def test_meets(required, have, ok):
    assert meets(required, have) is ok


@pytest.mark.parametrize("bad", ["0.4", ">= x", "~=0.4", ">=0.4,", ""])
def test_a_requirement_edakit_cannot_read_is_an_error(project, bad):
    set_edakit(project, bad)
    with pytest.raises(config.ConfigError, match=r"\[project\] edakit"):
        project.config()


def test_an_edakit_too_old_is_noted(project):
    set_edakit(project, ">=99")
    [f] = findings(project)
    assert f.severity == "note" and __version__ in f.text and ">=99" in f.text


def test_an_edakit_that_meets_it_and_a_project_without_the_key_say_nothing(project):
    assert findings(project) == []
    set_edakit(project, f"=={__version__}")
    assert findings(project) == []


def test_the_session_hook_names_the_edakit_that_runs(tmp_path):
    first = context(run_hook(led_bar(tmp_path))).splitlines()[0]
    assert first.startswith(f"edakit project (edakit {__version__}")


def test_the_session_hook_says_when_it_does_not_meet_the_project(tmp_path):
    out = context(run_hook(led_bar(tmp_path, replace=("[project]\n", '[project]\nedakit = ">=99"\n'))))
    assert f"edakit {__version__} runs here" in out and '[project] edakit asks for ">=99"' in out
