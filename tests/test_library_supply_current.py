"""Library drafts with behaviour logic and icc_a (schema-gaps.md E1): the simulation draws the datasheet's supply
current at the part's supply pin – the DS18B20 (C9753, 1.5 mA active) on the example's 3V3 adds that much to the
source's current; without the behaviour it drew nothing."""

import json
import shutil

import pytest

from edakit import library
from edakit.design import Design
from edakit.sim import run as simrun


def with_ds18b20(project, behaviour=True):
    entry = library.entry("C9753")
    if not behaviour:
        entry["values"].pop("behavior")
        entry["values"].pop("icc_a")
    project.save_part("C9753", entry)
    g = project.graph()
    pins = {n: p["name"] for n, p in entry["pins"].items()}
    gnd = next(n for n, p in entry["pins"].items() if p["type"] == "ground")
    vdd = next(n for n, p in entry["pins"].items() if p["type"] == "power_in")
    dq = next(n for n in entry["pins"] if n not in (gnd, vdd))
    g["graph"]["components"].append({"designator": "U9", "type": "ic", "lcsc": "C9753", "board": "main", "pins": pins})
    for net in g["graph"]["nets"]:
        if net["name"] == "GND":
            net["pins"].append(f"U9.{gnd}")
        if net["name"] == "3V3":
            net["pins"].append(f"U9.{vdd}")
    g["graph"]["nets"].append({"name": "DQ", "pins": [f"U9.{dq}"], "v": [0, 3.4]})
    project.save_graph(g)


def source_current(project):
    sim = json.loads((project.root / "hardware" / "sim.json").read_text())
    out = simrun.run_all(Design.from_config(project.config()), sim)
    return {r["name"]: sum(r["sources"].values()) for r in out["scenarios"]}


@pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")
def test_the_ds18b20_draws_its_active_current(project):
    e = library.entry("C9753")
    assert (e["values"]["behavior"], e["values"]["icc_a"]) == ("logic", 0.0015)
    with_ds18b20(project, behaviour=False)
    without = source_current(project)
    with_ds18b20(project)
    added = {name: i - without[name] for name, i in source_current(project).items()}
    # 3V3 comes from the Pico 2's switching regulator: 1.5 mA at 3.3 V reaches the 5 V source as about 1.3 mA
    assert added and all(0.001 < a < 0.0015 for a in added.values()), added
