"""One current release (#64): a RELEASED gate run supersedes the earlier ones, a run can be withdrawn, and the files
about to be uploaded are checked against the current release – `edakit release current|withdraw|verify`."""

import json

from edakit import cli, part
from edakit.release import gate

OLD, NEW = "20261025-205344", "20261025-232212"


def head(run, state="s1"):
    return {"time": run, "git_commit": "abc", "git_dirty": False, "graph_sha256": "g", "state_sha256": state,
            "layout_sha256": "l", "graph_version": "1.0"}


def gate_run(cfg, run, decision="RELEASED", gerber=None, state="s1"):
    """The files of one gate run and its manifest, as gate.main leaves them after stage F."""
    out = cfg.reports / run
    d = out / "fab" / "main"
    d.mkdir(parents=True)
    (d / "gerber_main.zip").write_bytes(gerber or f"gerber of {run}".encode())
    (d / "bom_main.csv").write_text("Comment,Designator,Footprint,LCSC Part #\n22uF,C2,C0805,C45783\n")
    (d / "cpl_main.csv").write_text(f"Designator,Mid X,Mid Y,Layer,Rotation\nC2,20,9,Top,{run[-1]}\n")
    gate.write_manifest(cfg, out, head(run, state), decision)
    return d


def manifest(cfg, run):
    return json.loads((cfg.reports / run / "fab" / "manifest.json").read_text())


def release(cfg, *args):
    return cli.main(["release", *args, "--config", str(cfg.root / "edakit.toml")])


def test_a_released_run_supersedes_the_earlier_ones(project, capsys):
    cfg = project.config()
    gate_run(cfg, "20261023-000107")
    gate_run(cfg, "20261025-204229", "NOT RELEASED")
    gate_run(cfg, OLD)
    gate_run(cfg, NEW)
    old, new = manifest(cfg, OLD), manifest(cfg, NEW)
    assert (old["released"], old["status"], old["superseded_by"], old["decision"]) == (False, "superseded", NEW,
                                                                                        "RELEASED")
    assert manifest(cfg, "20261023-000107")["superseded_by"] == OLD    # superseded when OLD was released
    assert (new["released"], new["status"]) == (True, "released") and "superseded_by" not in new
    assert "status" not in manifest(cfg, "20261025-204229")             # not released: nothing to supersede
    assert gate.current(cfg)[0] == NEW
    assert release(cfg, "current") == 0
    out = capsys.readouterr().out
    assert f"current release: {NEW}" in out and "graph 1.0" in out and "fab/main/gerber_main.zip" in out


def test_withdraw_leaves_no_current_release(project, capsys):
    cfg = project.config()
    gate_run(cfg, OLD)
    gate_run(cfg, NEW)
    assert part.latest_release(cfg, "s1")["time"] == NEW
    assert release(cfg, "withdraw", NEW, "--reason", "back copper missing") == 0
    m = manifest(cfg, NEW)
    assert (m["released"], m["status"], m["withdrawn"]["reason"]) == (False, "withdrawn", "back copper missing")
    assert m["withdrawn"]["by"] and m["withdrawn"]["date"]
    assert manifest(cfg, OLD)["status"] == "superseded"                 # stays superseded
    assert gate.current(cfg) is None
    assert part.latest_release(cfg, "s1") is None
    capsys.readouterr()
    assert release(cfg, "current") == 2
    assert "current release: none" in capsys.readouterr().out


def test_withdraw_needs_a_released_run_and_a_reason(project, capsys):
    cfg = project.config()
    gate_run(cfg, OLD, "NOT RELEASED")
    assert release(cfg, "withdraw", OLD, "--reason", "x") == 1
    assert release(cfg, "withdraw", "20990101-000000", "--reason", "x") == 1
    gate_run(cfg, NEW)
    assert release(cfg, "withdraw", NEW) == 1
    assert manifest(cfg, NEW)["released"] is True


def test_verify_checks_the_upload_against_the_current_release(project, capsys, tmp_path):
    cfg = project.config()
    old = gate_run(cfg, OLD)
    new = gate_run(cfg, NEW)
    assert release(cfg, "verify", str(new)) == 0                        # a folder: its .zip and .csv files
    assert release(cfg, "verify", *(str(new / f) for f in ("gerber_main.zip", "bom_main.csv", "cpl_main.csv"))) == 0
    capsys.readouterr()
    assert release(cfg, "verify", str(old / "gerber_main.zip")) == 2
    assert f"gerber_main.zip: from run {OLD} (superseded by {NEW})" in capsys.readouterr().out
    edited = tmp_path / "cpl_main.csv"
    edited.write_text((new / "cpl_main.csv").read_text().replace(",20,", ",21,"))
    assert release(cfg, "verify", str(new / "gerber_main.zip"), str(edited)) == 2
    assert "cpl_main.csv: unknown" in capsys.readouterr().out
    assert release(cfg, "verify", str(tmp_path / "nothing.zip")) == 1


def test_verify_without_a_current_release(project, capsys):
    cfg = project.config()
    new = gate_run(cfg, NEW)
    release(cfg, "withdraw", NEW, "--reason", "boost loop 61 mm")
    capsys.readouterr()
    assert release(cfg, "verify", str(new / "gerber_main.zip")) == 2
    assert "withdrawn: boost loop 61 mm" in capsys.readouterr().out


def test_manifests_without_status_read_as_before(project, capsys):
    """Manifests written before #64: every RELEASED run still says released; the newest one is current, and reading
    rewrites nothing."""
    cfg = project.config()
    for run in (OLD, NEW):
        d = cfg.reports / run / "fab"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"released": True, "decision": "RELEASED", "time": run, "git": "",
                                                     "graph_sha256": "g", "state_sha256": "s1",
                                                     "layout_sha256": "l", "files": {}}))
    before = {r: (cfg.reports / r / "fab" / "manifest.json").read_text() for r in (OLD, NEW)}
    assert release(cfg, "current") == 0
    assert f"current release: {NEW}" in capsys.readouterr().out
    assert release(cfg, "verify", str(cfg.reports)) == 1                 # no upload files there
    assert {r: (cfg.reports / r / "fab" / "manifest.json").read_text() for r in (OLD, NEW)} == before
    # withdrawing the newest one must not make the older one current again
    assert release(cfg, "withdraw", NEW, "--reason", "x") == 0
    assert gate.current(cfg) is None and manifest(cfg, OLD)["superseded_by"] == NEW
