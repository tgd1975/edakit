"""edakit's parts library (rules-at-scale.md, decision 8): edakit/parts/, `edakit part add` copies an entry with the
version it was taken from, `edakit part sign` is the owner's signature, PARTS.library notes a newer version and a
draft. The signatures file is redirected into tmp_path – the tests sign nothing in the library itself."""

import json

import pytest

from helpers import check

from edakit import cli, library
from edakit.design import Design


@pytest.fixture
def signed(tmp_path, monkeypatch):
    f = tmp_path / "signed.toml"
    f.write_text("[signed]\n", encoding="utf-8")
    monkeypatch.setattr(library, "SIGNED", f)
    return f


def run(project, monkeypatch, *argv):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(list(argv))


def notes(project):
    cfg = project.config()
    return [(f.grade, f.text) for f in check(Design.from_config(cfg), cfg).findings if f.code == "PARTS.library"]


def test_the_library_lists_its_entries_signed_or_draft(project, monkeypatch, capsys, signed):
    assert "C2297" in library.keys() and len(library.keys()) >= 15
    assert run(project, monkeypatch, "part", "add") == 0
    out = capsys.readouterr().out
    assert "C2297" in out and "draft" in out and "0 signed" in out
    library.sign("C2297", "Owner")
    assert library.signature("C2297")["by"] == "Owner"
    assert run(project, monkeypatch, "part", "add") == 0
    assert "1 signed" in capsys.readouterr().out


def test_a_signature_holds_for_the_entry_as_signed(signed, monkeypatch):
    library.sign("C2297", "Owner")
    e = library.entry("C2297")
    assert library.signature("C2297", e)
    changed = {**e, "mpn": e["mpn"] + "-X"}
    assert library.signature("C2297", changed) is None          # changed after its signature: a draft again
    assert library.sha({**e, "library": {"key": "C2297"}}) == library.sha(e)   # the provenance is not the version
    with pytest.raises(library.LibraryError):
        library.sign("C2297", " ")


def test_part_add_copies_with_its_version_and_keeps_a_project_entry(project, monkeypatch, capsys, signed):
    target = project.root / "hardware" / "parts" / "C15127.json"
    assert not target.exists()
    assert run(project, monkeypatch, "part", "add", "C15127") == 0
    copy = json.loads(target.read_text(encoding="utf-8"))
    lib = library.entry("C15127")
    assert copy["library"]["key"] == "C15127" and copy["library"]["sha256"] == library.sha(lib)
    assert copy["library"]["signed"] is False and "a draft" in capsys.readouterr().out
    assert {k: v for k, v in copy.items() if k != "library"} == lib
    assert run(project, monkeypatch, "part", "add", "C15127") == 1          # the project's entry stays
    assert "has an entry already" in capsys.readouterr().err
    assert run(project, monkeypatch, "part", "add", "C0") == 1
    assert "not in the library" in capsys.readouterr().err


def test_parts_library_notes_a_newer_version_and_a_draft(project, monkeypatch, signed):
    key = "C2297"                                       # an entry the example's graph uses
    design = Design.from_config(project.config())
    assert key in {design.entry_key(d) for d in design.comps}
    assert notes(project) == []                          # the example's own entry names no library version
    assert run(project, monkeypatch, "part", "add", key, "--update") == 0
    found = notes(project)
    assert [g for g, _ in found] == ["draft"] and f"library entry {key} is not signed by the owner" in found[0][1]
    library.sign(key, "Owner")
    assert notes(project) == []
    f = project.root / "hardware" / "parts" / f"{key}.json"
    e = json.loads(f.read_text(encoding="utf-8"))
    e["library"]["sha256"] = "0" * 64                    # taken from an older version of the library entry
    f.write_text(json.dumps(e, indent=1), encoding="utf-8")
    found = notes(project)
    assert [g for g, _ in found] == ["newer"] and f"edakit part add {key} --update" in found[0][1]


def test_part_add_update_takes_the_library_version_on_purpose(project, monkeypatch, capsys, signed):
    key = "C2297"
    f = project.root / "hardware" / "parts" / f"{key}.json"
    mine = json.loads(f.read_text(encoding="utf-8"))
    mine["mpn"] = mine.get("mpn", "") + " (project)"
    f.write_text(json.dumps(mine, indent=1), encoding="utf-8")
    assert run(project, monkeypatch, "part", "add", key, "--update") == 0
    out = capsys.readouterr().out
    assert "replaced the project's entry" in out and "changed:" in out and "mpn" in out
    assert json.loads(f.read_text(encoding="utf-8"))["library"]["key"] == key


def test_block_add_copies_from_the_library_with_the_version(project, monkeypatch, signed):
    parts = project.root / "hardware" / "parts"
    before = {p.stem for p in parts.glob("*.json")}
    assert run(project, monkeypatch, "block", "add", "reverse-pmos", "--as", "RP",
               "--connect", "in=+5V", "--connect", "out=RP_OUT") == 0
    new = {p.stem for p in parts.glob("*.json")} - before
    assert new, "the block brought entries the example lacks"
    for key in new:
        e = json.loads((parts / f"{key}.json").read_text(encoding="utf-8"))
        assert e["library"]["key"] == key and e["library"]["sha256"] == library.sha(library.entry(key))


def test_sign_needs_a_name(project, monkeypatch, capsys, signed):
    assert run(project, monkeypatch, "part", "sign", "C2297") == 1
    assert "--by" in capsys.readouterr().err
    assert run(project, monkeypatch, "part", "sign", "C2297", "--by", "Owner") == 0
    assert 'C2297 = { by = "Owner"' in signed.read_text(encoding="utf-8")
