"""T.24 of circuit-dsl-toolchain.md: the source map, written on request, and a finding located in the source."""

import json

from lang_examples import LED_BAR
from test_lang_use import step

from edakit import cli
from edakit.findings import Finding
from edakit.lang.compile import resolved_of
from edakit.lang.locate import locate


def test_the_map_names_the_loop_s_statement_for_every_led(project_circuit, tmp_path):
    where = tmp_path / "map.json"
    assert cli.main(["graph", "json", "--map", str(where), "--config", str(project_circuit.root / "edakit.toml")]) == 0
    smap = json.loads(where.read_text())
    line = LED_BAR.splitlines().index("for n in 0..7") + 2
    assert {smap["components"][f"D{n}"]["line"] for n in range(2, 10)} == {line}
    assert smap["nets"]["VIN"]["line"] == LED_BAR.splitlines().index(
        next(ln for ln in LED_BAR.splitlines() if ln.startswith("net VIN"))) + 1


def test_a_usage_s_parts_name_the_usage_and_the_definition(project):
    _, smap = resolved_of(step(project))
    r4 = smap.components["R4"]
    assert r4["file"] == "hardware/graph.circuit" and "use" in r4 and "definition" in r4
    assert smap.usages["step1"]["line"] == int(r4["use"].rpartition(":")[2])


def test_locate_a_finding(project_circuit):
    _, smap = resolved_of(project_circuit.graph_file)
    on_part = Finding("LIM.v", "G", "U2", "U2: …", on=(("component", "U2"),))
    assert locate(smap, on_part) == ("hardware/graph.circuit", smap.components["U2"]["line"])
    on_net = Finding("LVL.undefined", "G", "LED_SDI", "LED_SDI: …")
    assert locate(smap, on_net)[1] == smap.nets["LED_SDI"]["line"]
    assert locate(smap.as_dict(), {"code": "STRUCT.pin", "place": "U1.GP3 (5)"})[1] == smap.components["U1"]["line"]
    assert locate(smap, Finding("PARTS.fact", "P", "C2297", "…")) is None
