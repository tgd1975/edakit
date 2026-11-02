"""T.20 to T.23 of circuit-dsl-toolchain.md: the electrical library and the exports – SysML v2 and KerML, textual and
as JSON – with the conformance test against a standard reader (language 9 and 10)."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from test_lang_use import step
from test_lang_variants import variant

from edakit import cli
from edakit.lang.export import json as as_json
from edakit.lang.export import kerml, sysml
from edakit.lang.export.model import build, name

LIBRARY = Path(__file__).resolve().parents[1] / "edakit" / "lang" / "library" / "Electrical.sysml"
# names of the SysML v2 standard library the electrical library imports (ISQ, SI, ScalarValues)
STANDARD = {"ScalarQuantityValue", "ElectricPotentialDifferenceValue", "ElectricCurrentValue", "ResistanceValue",
            "CapacitanceValue", "InductanceValue", "FrequencyValue", "LengthValue", "DurationValue", "Real",
            "String", "Boolean", "Integer"}


def reader():
    """The syster CLI of systree: SYSTER_CLI, else on the PATH, else systree's own; None without one."""
    if os.environ.get("SYSTER_CLI"):
        return os.environ["SYSTER_CLI"]
    if shutil.which("syster"):
        return shutil.which("syster")
    try:
        import systree
        return str(systree.find_cli())
    except Exception:
        return None


def analyze(path):
    """(parse errors, other errors) of a file or folder by the standard reader – with the standard library where
    SYSML_STDLIB names it, else without: then an undefined name of the standard library is no error."""
    cli_ = reader()
    args = [cli_, "--json", str(path)]
    stdlib = os.environ.get("SYSML_STDLIB")
    args[1:1] = ["--stdlib-path", stdlib] if stdlib else ["--no-stdlib"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=300)
    raw = r.stdout + r.stderr
    parse = [ln for ln in raw.splitlines() if ln.startswith("parse error")]
    data = json.loads(raw[raw.index("{"):]) if "{" in raw else {"diagnostics": []}
    other = [d for d in data.get("diagnostics", []) if d.get("severity") == "error"]
    if not stdlib:
        other = [d for d in other if not re.fullmatch(r"undefined reference: '(\w+)'", d["message"])
                 or re.fullmatch(r"undefined reference: '(\w+)'", d["message"]).group(1) not in STANDARD]
    return parse, other


sysml_reader = pytest.mark.skipif(reader() is None, reason="no SysML v2 reader: the optional group sysml (systree)")


def export_of(cfg):
    return build(cfg)


# --- structure ------------------------------------------------------------------------------------------------------
def test_every_component_a_part_and_every_net_a_connection(project_circuit):
    text = sysml.text(export_of(project_circuit.config()))
    for des in ("J1", "U1", "U2", "R1", "D2", "D9"):
        assert re.search(rf"\n        part {des} : \w+ {{\n            :>> designator = \"{des}\";", text), des
    assert "connection '+5V' : Net connect (D1.K, U1.VSYS, C2.'1', D2.A" in text
    assert "connection LED_SDI : Net connect (U1.GP3, U2.SDI)" in text
    assert ":>> v = VoltageRange(min = 0 [SI::V], max = 3.4 [SI::V]);" in text
    assert "@Lock { net = \"LED_SDI\"; }" in text and "@Accept { code = \"LVL.undefined\";" in text
    assert "@Layout { fixed = (\"SW1\", \"D2\"" in text and "part def LedBar :> Circuit {" in text
    assert text.count("part D") == 9                                        # the loop expanded: D1 and D2 … D9


def test_reserved_names_are_quoted():
    assert name("in") == "'in'" and name("+5V") == "'+5V'" and name("3V3(OUT)") == "'3V3(OUT)'"
    assert name("GND") == "GND" and name("private") == "'private'"


def test_a_definition_and_its_usage(project):
    path = step(project)
    cfg = project.config()
    cfg.graph = path
    text = sysml.text(build(cfg))
    assert "part def Led :> Block {" in text and "attribute i : ElectricCurrentValue default 0.01 [SI::A];" in text
    assert "part step1 : Led {" in text and "part :>> R {\n" in text and ':>> designator = "R4";' in text
    assert "connection LED_G1 : Net connect (step1.R.'1', U1.D6)" in text
    assert '@Derivation { rule = "SeriesResistor";' in text


def base_is_circuit(project):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('graph = "hardware/graph.json"', 'graph = "hardware/graph.circuit"'))


def test_a_variant_specializes_its_base(project):
    path = variant(project, "  part R3 value 470Ω\n")
    base_is_circuit(project)
    from edakit import config
    vcfg = config.load(path.parents[1] / "edakit.toml")
    text = sysml.text(build(vcfg))
    assert "package 'bell-step-smd' {" in text and "private import 'bell-step'::*;" in text
    assert "part def BellStepSmd :> 'bell-step'::BellStep {" in text
    assert "part :>> R3 : Resistor {" in text and ':>> value = "470Ω";' in text
    assert text.index("package 'bell-step' {") < text.index("package 'bell-step-smd' {")


def test_the_requirements_export(project):
    from test_lang_requirements import project_with
    head = '''graph bell-step
part U1 module A000005 lcsc A000005 "Arduino Nano"
  alias led1 = D6 led2 = D5
  satisfies R-3
net GND 0 V U1.GND
net +5V 0..5.5 V
'''
    cfg = project_with(project, head=head)
    text = sysml.text(build(cfg))
    assert "requirement 'R-3' : CircuitRequirement {" in text and ":>> 'binding' = Binding::must;" in text
    assert "require constraint { doc /* D.i within 2 mA .. 15 mA */ }" in text
    assert "satisfy 'R-3' by U1;" in text and "requirement 'N-1' : Need {" in text
    assert "dependency 'N-1_R-3' from 'R-3' to 'N-1';" in text


# --- JSON -----------------------------------------------------------------------------------------------------------
def test_the_json_ids_are_stable_and_every_reference_resolves(project_circuit):
    a = as_json.elements(export_of(project_circuit.config()))
    b = as_json.elements(export_of(project_circuit.config()))
    assert [x["@id"] for x in a] == [x["@id"] for x in b]
    assert as_json.problems(a) == []
    types = {x["@type"] for x in a}
    assert {"Package", "PartDefinition", "PartUsage", "PortUsage", "ConnectionUsage", "OwningMembership",
            "FeatureTyping"} <= types
    k = as_json.elements(export_of(project_circuit.config()), "kerml")
    assert as_json.problems(k) == [] and {"Structure", "Feature", "Connector"} <= {x["@type"] for x in k}


def test_the_commands_write_their_files(project_circuit, tmp_path, capsys):
    toml = str(project_circuit.root / "edakit.toml")
    assert cli.main(["graph", "sysml", "--out", str(tmp_path / "s"), "--config", toml]) == 0
    assert sorted(p.name for p in (tmp_path / "s").iterdir()) == ["Electrical.sysml", "led-bar.json", "led-bar.sysml"]
    assert cli.main(["graph", "kerml", "--out", str(tmp_path / "k"), "--config", toml]) == 0
    assert sorted(p.name for p in (tmp_path / "k").iterdir()) == ["Electrical.kerml", "led-bar.kerml",
                                                                  "led-bar.kerml.json"]
    kt = (tmp_path / "k" / "led-bar.kerml").read_text()
    assert "struct LedBar :> Circuit {" in kt and "connector LED_SDI : Net (U1.GP3, U2.SDI)" in kt
    assert "struct Component" in (tmp_path / "k" / "Electrical.kerml").read_text()


# --- conformance ----------------------------------------------------------------------------------------------------
@pytest.mark.sysml
@sysml_reader
def test_the_library_reads_without_error():
    parse, other = analyze(LIBRARY)
    assert parse == [] and other == []


@pytest.mark.sysml
@sysml_reader
@pytest.mark.parametrize("view", ["sysml", "kerml"])
def test_the_export_of_led_bar_reads_without_error(project_circuit, tmp_path, view):
    assert cli.main(["graph", view, "--out", str(tmp_path), "--config", str(project_circuit.root / "edakit.toml")]) == 0
    parse, other = analyze(tmp_path)
    assert parse == [] and other == []


@pytest.mark.sysml
@sysml_reader
def test_the_export_of_a_definition_a_variant_and_requirements_reads(project, tmp_path):
    path = variant(project, "  part R3 value 470Ω\n")
    base_is_circuit(project)
    from edakit import config
    vcfg = config.load(path.parents[1] / "edakit.toml")
    (tmp_path / "v.sysml").write_text(sysml.text(build(vcfg)))
    shutil.copy(LIBRARY, tmp_path / "Electrical.sysml")
    parse, other = analyze(tmp_path)
    assert parse == [] and other == []
    assert kerml.text(build(vcfg)).startswith("package 'bell-step' {")
