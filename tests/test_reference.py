"""The reference circuits per domain (tests/reference.py): each passes clean under its domains – no error, warning or
pending finding in edakit check, no failing row in the simulation –, and each seeded fault raises exactly its codes
and no other (concept rules-at-scale.md, section 7: the seeded-fault suite per domain and the overlap test)."""

import shutil

import pytest
from reference import FAULTS, REFERENCES, Project

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
    found |= {(r["id"], r["item"]) for r in out["checks"] if r["result"] == "fail"}
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
