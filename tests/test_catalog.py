"""The catalog of the restructuring (rules-at-scale.md, step 1): codes, tables, parts schema, conversion, findings."""

import argparse
import glob
import json
from pathlib import Path

import pytest

from edakit import catalog, convert, schema
from edakit.findings import Finding, Profile, Report, format_findings

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_lint_is_clean():
    assert catalog.lint() == []


def test_every_check_and_hint_of_before_has_a_code():
    """The 66 checks and 9 hints of before the restructuring (G-7 was retired), and the ten that came with ordering at
    the maker on main meanwhile (P-12, F-7, B-1 to B-7), each name the codes that replace them."""
    old = {f"{s}-{n}" for s, last in (("P", 12), ("G", 25), ("E", 5), ("H", 9), ("B", 7)) for n in range(1, last + 1)}
    old |= {"S-2"} | {f"L-{n}" for n in range(1, 21) if n != 6} | {f"F-{n}" for n in range(1, 8)}
    assert old - {"G-7"} == set(catalog.old_map())


def test_every_code_names_its_engine():
    for name in catalog.codes():
        assert catalog.engine_of(name), name


def test_lint_finds_what_is_missing(monkeypatch):
    bad = {"engines": catalog.engines(), "codes": {"LIM.x": {"title": "t", "rule": "", "why": "w", "fix": "f",
                                                            "severity": "fatal", "replaces": ["G8"]},
                                                  "lim.v": {"title": "t", "rule": "r", "why": "w", "fix": "f",
                                                            "severity": "error"}}}
    monkeypatch.setattr(catalog, "data", lambda: bad)
    problems = "\n".join(catalog.lint())
    assert "LIM.x: no rule" in problems and "severity 'fatal'" in problems and "replaces 'G8'" in problems
    assert "lim.v: not ENGINE.relation" in problems


def test_table_rows_need_a_read_source():
    assert catalog.table_problems({"table": {"source": "s", "tag": "r"}, "x": {"a": 1, "tag": "v"}}) == \
        ["x: tag 'v' – a table row is read from its source (r) before it is used"]
    assert catalog.table_problems({"x": {"a": 1}})[0] == "[table] needs source and tag"
    assert catalog.table("radio_eu")["eirp"][0]["limit_mw"] == 100


def test_explain_a_code_and_an_old_id():
    lines = catalog.explain("LIM.v")
    assert lines[0].startswith("LIM.v (voltage within its limit): ")
    assert any(x.strip().startswith("source: ") for x in lines)
    assert catalog.explain("G-8") == ["G-8: replaced by LIM.v (edakit explain LIM.v)"]
    assert catalog.explain("XYZ.q") == []


def test_explain_command(capsys):
    assert catalog.main_explain(argparse.Namespace(ids=["REQ.missing"])) == 0
    assert "what to do:" in capsys.readouterr().out
    assert catalog.main_explain(argparse.Namespace(ids=["REQ.nothing"])) == 1
    assert "REQ.missing" in capsys.readouterr().out


def test_rules_lists_the_codes(capsys):
    assert catalog.main_rules(argparse.Namespace(ids=[])) == 0
    out = capsys.readouterr().out
    assert "LIMITS – every quantity within its limit" in out and "LIM.v" in out
    assert catalog.main_rules(argparse.Namespace(ids=["G-8"])) == 0
    assert "G-8: replaced by LIM.v" in capsys.readouterr().out


# --- parts schema and conversion -------------------------------------------------------------------------------------
PARTS = sorted(glob.glob(str(ROOT / "edakit" / "parts" / "*.json"))
               + glob.glob(str(ROOT / "tests" / "fixtures" / "led-bar" / "hardware" / "parts" / "*.json")))


@pytest.mark.parametrize("path", PARTS, ids=lambda p: Path(p).stem)
def test_every_entry_is_converted_and_fits_its_schema(path):
    entry = json.loads(Path(path).read_text(encoding="utf-8"))
    assert convert.part(entry) == entry
    assert schema.problems(entry) == []


def test_conversion_renames_by_unit():
    old = {"kind": "diode", "pins": {"1": {"name": "K", "type": "passive", "role": "cathode", "vmax": 5,
                                           "v_op": [1.8, 3.6]}},
           "ratings": {"vrrm": 40, "if_avg_a": 1}, "params": {"vf_v": 0.5}}
    new = convert.part(old)
    assert new["limits"] == {"vr_max_v": 40, "if_max_a": 1} and new["values"] == {"vf_v": 0.5}
    assert new["pins"]["1"] == {"name": "K", "type": "passive", "role": "cathode", "v_max_v": 5, "v_op_min_v": 1.8,
                                "v_op_max_v": 3.6}
    rgb = convert.part({"kind": "led_rgb", "pins": {}, "ratings": {"red": {"vr_max": 5}}, "params": {"red": {"vf_typ": 2}}})
    assert rgb["limits"] == {"red": {"vr_max_v": 5}} and rgb["values"] == {"red": {"vf_typ_v": 2}}


def test_schema_names_what_does_not_fit():
    entry = {"kind": "capacitor", "pins": {"1": {"name": "+", "type": "pasive", "role": "plus", "vmx": 3}},
             "limits": {"v_max": 10, "v_max_v": "ten"}, "values": {"dielectric": "X9Z", "value_f": 1e-6}}
    p = schema.problems(entry)
    assert "limits.v_max: not a limit of kind capacitor (known: v_max_v)" in p
    assert "limits.v_max_v: 'ten' is no number in V" in p
    assert any(x.startswith("values.dielectric: 'X9Z'") for x in p)
    assert any(x.startswith("pins.1.type: 'pasive'") for x in p) and "pins.1.vmx: not a pin field" in p
    assert schema.problems({"kind": "diode", "pins": {}, "ratings": {}}) == [
        "the form of before (ratings, params, vmax …) – edakit convert converts it"]
    assert schema.problems({"kind": "ic", "pins": {}, "limits": {"vdd_op_min_v": 5, "vdd_op_max_v": 3}}) == [
        "limits: vdd_op_min_v 5 above vdd_op_max_v 3"]


def test_part_lint_and_convert_commands(project, capsys):
    from edakit import cli
    assert cli.main(["part", "lint", "--config", str(project.root / "edakit.toml")]) == 0
    assert cli.main(["convert", "--config", str(project.root / "edakit.toml")]) == 0
    assert capsys.readouterr().out.strip().endswith("0 files – edakit convert --write converts them")
    p = project.part("C8678")
    p["ratings"] = p.pop("limits")       # a parts entry of before
    project.save_part("C8678", p)
    assert cli.main(["part", "lint", "--config", str(project.root / "edakit.toml")]) == 2
    assert "edakit convert converts it" in capsys.readouterr().out
    assert cli.main(["check", "--config", str(project.root / "edakit.toml")]) == 1
    assert "the form of before the restructuring; edakit convert --write" in capsys.readouterr().err
    assert cli.main(["convert", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    assert "converted: hardware/parts/C8678.json" in capsys.readouterr().out
    assert project.part("C8678")["limits"]["vr_max_v"] == 40


def test_conversion_of_graph_and_signoff():
    g = {"graph": {"components": [{"designator": "J1", "waive": {"P-1": "free"}}, {"designator": "F1"}],
                   "nets": [{"name": "OE", "waive": {"G-4": "held by U1"}}],
                   "hints": {"H-1": "C1 next to J1"},
                   "checks": {"pin_locks": {"U1.4": "CLK"}, "reverse_protect": ["J1"]}}}
    new = convert.graph(g)["graph"]
    assert new["components"][0] == {"designator": "J1", "accept": {"STRUCT.entry": "free"}, "source": "reversible"}
    assert new["nets"][0]["accept"] == {"LVL.undefined": "held by U1"}
    assert new["accept"] == {"HINT.bulk": "C1 next to J1"} and new["locks"] == {"pins": {"U1.4": "CLK"}}
    assert "checks" not in new and convert.graph(convert.graph(g)) == convert.graph(g)
    conv = convert.graph({"graph": {"conventions": {"v": "ranges", "waive": "per net: {check id: reason}"}}})
    assert conv["graph"]["conventions"] == {"v": "ranges", "accept": convert.ACCEPT_NOTE}
    s = convert.signoff({"accepted_warnings": [{"match": "P-5 U1 *", "by": "x"}]})
    assert s["accept"] == [{"match": "PARTS.supplier U1 *", "by": "x", "converted_from": "P-5 U1 *"}]


# --- findings --------------------------------------------------------------------------------------------------------
def test_severity_comes_from_the_profile_and_its_purpose():
    f = Finding("LIM.eirp", "G", "U1", "21 dBm")
    assert Profile().of(f) == "note"
    p = Profile(by_purpose={"sale": {"LIM.eirp": "warning"}}, purpose="sale")
    assert p.of(f) == "warning"
    m = Finding("LIM.i", "G", "F1", "trips at 3 A", grade="margin")
    assert Profile().of(m) == "warning" and Profile({"LIM.i/margin": "error"}).of(m) == "error"
    assert Profile({"LIM.i": "note"}).of(m) == "note"


def test_accept_on_net_component_and_graph():
    graph = {"nets": [{"name": "OE", "accept": {"LVL.undefined": "held"}}],
             "components": [{"designator": "F1", "accept": {"LIM.i/margin": "short trips fast"}}],
             "accept": {"HINT.bulk J1": "C1 next to J1"}}
    rep = Report([Finding("LVL.undefined", "G", "OE", "x", on=(("net", "OE"),)),
                  Finding("LIM.i", "G", "F1", "holds", on=(("component", "F1"),)),
                  Finding("LIM.i", "G", "F1", "trips", grade="margin", on=(("component", "F1"),)),
                  Finding("HINT.bulk", "G", "J1", "no bulk"), Finding("HINT.bulk", "G", "J2", "no bulk"),
                  Finding("PARTS.verified", "P", "C1", "not verified")]).resolve(graph)
    assert [f.text for f in rep.errors] == ["holds"]
    assert {f.text for f in rep.accepted} == {"x", "trips", "no bulk"}
    assert [f.place for f in rep.notes] == ["J2"] and len(rep.pending) == 1
    assert rep.counts() == {"error": 1, "accepted": 3, "note": 1, "pending": 1}


def test_format_groups_by_code():
    fs = [Finding("LIM.v", "G", f"C{i}", f"{i} V across, rated 6.3 V", source="limits.v_max_v of C1",
                  fix="a 16 V part", severity="error") for i in range(7)]
    lines = format_findings(fs)
    assert lines[0] == "LIM.v – voltage within its limit: 7 error"
    assert lines[1] == "  G  C0: 0 V across, rated 6.3 V   (limits.v_max_v of C1)   → a 16 V part"
    assert "  … 2 more (--json)" in lines and any(x.startswith("  LIM.v: A part with a higher") for x in lines)


def test_the_handbook_lists_what_the_catalog_holds():
    """The handbook's lists of codes, the parts schema and the map of before are generated from the catalog: a change
    to codes.toml or kinds.toml without python -m edakit.catalog.handbook --write fails here."""
    from edakit.catalog import handbook
    assert handbook.stale() == []
    shown = "".join(p.read_text(encoding="utf-8") for p in handbook.ROOT.glob("*.md"))
    assert all(f"**`{name}`**" in shown for name in catalog.codes())          # every code in one of the lists
    assert all(f"`{kind}`" in shown for kind in schema.kinds()["kinds"])


def test_a_detail_belongs_to_one_code():
    seen = {}
    for name, e in catalog.codes().items():
        for d in e.get("details", []):
            assert d not in seen, f"{name} repeats a detail of {seen.get(d)}"
            seen[d] = name


def test_the_generator_renders_a_section_anew(tmp_path):
    from edakit.catalog import handbook
    page = tmp_path / "x.md"
    page.write_text("before\n<!-- edakit:generated codes FILES -->\nold text\n<!-- edakit:end -->\nafter\n")
    assert handbook.stale(tmp_path) == [page]
    new = handbook.update(page.read_text())
    assert "old text" not in new and "**`FILES.sheet`**" in new and new.startswith("before\n")
    assert new.endswith("<!-- edakit:end -->\nafter\n")
    page.write_text(new)
    assert handbook.stale(tmp_path) == []


def test_a_retired_code_explains_itself_and_stays_taken(monkeypatch):
    data = dict(catalog.data(), retired={"GEO.old": "GEO.spacing holds it now"})
    monkeypatch.setattr(catalog, "data", lambda: data)
    assert catalog.explain("GEO.old") == ["GEO.old: retired – GEO.spacing holds it now"]
    assert catalog.lint() == []
    data["retired"] = {"GEO.hole": "taken again"}
    assert catalog.lint() == ["GEO.hole: retired and still a code – a name once retired is not used again"]


def test_convert_carries_the_circuit_sign_offs_of_the_signed_files(project, capsys):
    """The files were the signed ones: the new circuit hash goes into the sign-off file, both into rehashed. Signed for
    another state: nothing is carried over."""
    from edakit import cli
    from edakit.release import gate
    cfg = project.config()
    p = project.part("C8678")
    p["ratings"] = p.pop("limits")
    project.save_part("C8678", p)
    signed = gate.state_hash(cfg)
    s = json.loads(cfg.signoff.read_text())
    cfg.signoff.write_text(json.dumps({**s, "state_sha256": signed}, indent=2) + "\n")
    assert cli.main(["convert", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    assert "the sign-offs of scope 'circuit' keep counting" in capsys.readouterr().out
    s = json.loads(cfg.signoff.read_text())
    assert s["state_sha256"] == gate.state_hash(cfg) != signed
    assert s["rehashed"][-1]["state_sha256"] == [signed, s["state_sha256"]] and s["rehashed"][-1]["by"] == "edakit convert"
    p = project.part("C8678")
    p["ratings"] = p.pop("limits")
    project.save_part("C8678", p)
    assert cli.main(["convert", "--write", "--config", str(project.root / "edakit.toml")]) == 0
    assert "keep counting" not in capsys.readouterr().out          # signed for the state before this one
    assert json.loads(cfg.signoff.read_text())["state_sha256"] == s["state_sha256"]
