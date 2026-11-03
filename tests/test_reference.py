"""The reference circuits per domain (tests/reference.py): each passes clean under its domains – no error, warning or
pending finding in edakit check, no row of the simulation that fails or warns –, and each seeded fault raises exactly its codes
and no other (concept rules-at-scale.md, section 7: the seeded-fault suite per domain and the overlap test)."""

import json
import re
import shutil

import pytest
from reference import EXAMPLE, FAULTS, LIBRARY, REFERENCES, WHY, Project

from edakit import engines
from edakit.design import Design
from edakit.sim import run as simrun

ngspice = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def reference(tmp_path, name):
    p = Project.copy_of_example(tmp_path / name)
    REFERENCES[name](p)
    return p


def codes(p):
    """The codes of every error, warning and pending finding of check and simulation, with their places."""
    cfg = p.config()
    d = Design.from_config(cfg)
    found = {(f.code, f.place) for f in engines.run(d, cfg).findings if f.severity in ("error", "warning", "pending")
             and not f.accepted}
    out = simrun.run_all(Design.from_config(cfg), p.sim())
    found |= {(r["id"], r["item"]) for r in out["checks"] if r["result"] in ("fail", "warn")}   # warn: a warning
    return found


@ngspice
@pytest.mark.parametrize("name", sorted(REFERENCES))
def test_the_reference_circuit_is_clean(tmp_path, name):
    p = reference(tmp_path, name)
    assert codes(p) == set()
    domains = engines.profile(Design.from_config(p.config()), p.config()).enabled
    if name != "keyboard":
        assert name in domains, domains


@ngspice
@pytest.mark.parametrize("name, what", [(n, w) for n, faults in sorted(FAULTS.items()) for w, _, _ in faults])
def test_the_seeded_fault_raises_exactly_its_codes(tmp_path, name, what):
    p = reference(tmp_path, name)
    _, change, expected = next(f for f in FAULTS[name] if f[0] == what)
    change(p)
    got = {code for code, _ in codes(p)}
    assert got == expected, sorted(codes(p))


def test_every_domain_has_a_reference_circuit():
    from edakit import profile
    # radio: a transmitter's facts, no circuit of its own; mains: recognised, not checked – its fault is the one
    # test_hazardous.py builds into the example (decision 7)
    assert set(profile.names()) - {"radio", "mains"} <= set(REFERENCES), "a domain without a reference circuit"


def test_every_reference_circuit_says_what_it_is_and_why():
    """Admission rule 6 (handbook 19.7): the function's docstring says what the circuit is, WHY why it stands for its
    domain – handbook 19.4 and the catalog's pages show both."""
    assert set(WHY) == set(REFERENCES)
    for name, build in REFERENCES.items():
        assert len((build.__doc__ or "").split()) >= 10, f"{name}: no docstring"
        assert len(WHY[name].split()) >= 10, f"{name}: no why"


@pytest.mark.parametrize("name", sorted(REFERENCES))
def test_a_test_entry_is_marked_as_one(tmp_path, name):
    """Admission rule 3 (handbook 19.7): a parts entry the circuit adds beyond the block library and the example is a
    test entry – numbered C91000xx, verified by "reference circuit", its source saying it is not from a datasheet –,
    so that nobody takes it for a part to order."""
    p = reference(tmp_path, name)
    known = {f.stem for f in LIBRARY.glob("*.json")} | {f.stem for f in (EXAMPLE / "hardware" / "parts").glob("*.json")}
    for f in sorted((p.root / "hardware" / "parts").glob("*.json")):
        if f.stem in known:
            continue
        e = json.loads(f.read_text(encoding="utf-8"))
        assert re.fullmatch(r"C91000\d\d", f.stem), f"{name}: test entry {f.stem}"
        assert e["lcsc"] == f.stem and e["verified"] == {"by": "reference circuit"}, f"{name}: {f.stem}"
        assert e["sources"] == ["values for the reference circuit, not from a datasheet"], f"{name}: {f.stem}"
