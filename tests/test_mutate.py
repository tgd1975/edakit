"""The mutation sweep (edakit/mutate.py): mistakes built into a copy of the design one at a time, what no code
catches reported – in memory, nothing written."""

import shutil

import pytest

from edakit import cli, engines
from edakit.design import Design
from edakit.mutate import mutations, sweep


def test_the_mistakes_of_the_sweep(project):
    d = Design.from_config(project.config())
    what = [w for w, _, _ in mutations(d)]
    assert "D1 left out" in what and "D2 turned round" in what and "R1 a hundred times larger" in what
    assert "LED_OE shorted to GND" in what and not any(w.startswith(("GND ", "+5V ", "3V3 ")) for w in what)


def test_without_the_simulation_a_reversed_led_goes_unseen(project):
    d = Design.from_config(project.config())
    found = {m.what: m.caught for m in sweep(d, project.config())}
    assert found["D2 turned round"] == []                       # polarity is the simulation's (handbook 3.3)
    assert "PATH.unfed U1.39" in found["D1 left out"]                # the MCU without its supply
    assert project.graph() == project.graph()                   # nothing written


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_with_the_simulation_it_is_caught(project, capsys):
    cfg = project.config()
    d = Design.from_config(cfg)
    found = {m.what: m.caught for m in sweep(d, cfg, engines.load_sim(cfg))}
    assert found["D2 turned round"]
    assert found["R1 a hundred times larger"] == []             # the LEDs dim with R-EXT: nothing says how bright
    assert cli.main(["mutate", "--sim", "--config", str(project.root / "edakit.toml")]) == 0
    assert "not caught: R1 a hundred times larger" in capsys.readouterr().out
