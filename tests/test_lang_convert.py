"""T.6 of circuit-dsl-toolchain.md: edakit graph convert --to circuit – a JSON or TOML graph as flat statements, read
back before anything is written, the sign-offs of scope circuit carried over, [project] edakit set."""

import json
import tomllib

from lang_examples import LED_BAR
from lang_project import fixture_graph, flat
from test_graph_toml import to_toml

from edakit import __version__, cli
from edakit.design import load_graph
from edakit.graph_form import canonical, converted, design_of, needs_edakit
from edakit.lang.compile import compile_path, resolved_of
from edakit.lang.convert import to_circuit
from edakit.release import gate


def run(project, *argv):
    return cli.main(["graph", *argv, "--config", str(project.root / "edakit.toml")])


def test_led_bar_converted_compiles_to_its_graph_and_checks_the_same(project, capsys):
    want = converted(fixture_graph(project))              # the convention pin_reference of the word rule
    args = ["check", "--config", str(project.root / "edakit.toml")]
    code = cli.main(args)
    before = capsys.readouterr().out
    assert run(project, "convert", "--to", "circuit") == 0
    out = capsys.readouterr().out
    assert "hardware/graph.circuit written" in out and "hardware/graph.json written" in out
    cfg = project.config()
    assert cfg.graph == project.root / "hardware" / "graph.circuit"
    assert canonical(resolved_of(cfg.graph)[0]) == canonical(want)
    assert canonical(json.loads(project.graph_file.read_text())["graph"]) == canonical(want)
    assert cli.main(args) == code
    assert capsys.readouterr().out == before
    assert run(project, "json", "--check") == 0


def test_the_converted_text_is_language_11_s_up_to_the_loop(project):
    source = load_graph(project.graph_file)
    from edakit.design import load_parts
    cfg = project.config()
    text = to_circuit(source, design_of(cfg.graph, load_parts(cfg.parts), list(cfg.boards), source))
    loop = LED_BAR[LED_BAR.index("for n in 0..7"):LED_BAR.index("\nset cables")]
    outside = [ln for ln in LED_BAR.replace(loop, "").splitlines() if ln.strip()]
    got = [ln for ln in text.splitlines() if ln.strip()]
    # the loop's parts and nets stand among the others; +5V has every anode; the Pico's grounds by their shared name
    rest = [ln for ln in got if not ln.startswith(("part D2 ", "part D3", "part D4", "part D5", "part D6", "part D7",
                                                   "part D8", "part D9", "net LED0 ", "net LED1", "net LED2",
                                                   "net LED3", "net LED4", "net LED5", "net LED6", "net LED7"))]
    def norm(lines):
        return [ln for ln in lines if not ln.startswith(("net +5V", "net GND"))]
    assert norm(rest) == norm(outside)
    assert "net GND 0 V J1.2 U2.GND R1.2 C1.2 C2.2 SW1.C U1.GND U1.AGND" in got
    flat_text = flat(LED_BAR)
    (project.root / "hardware" / "graph.circuit").write_text(flat_text)
    (project.root / "hardware" / "converted.circuit").write_text(text)
    a = resolved_of(project.root / "hardware" / "graph.circuit")[0]
    b = resolved_of(project.root / "hardware" / "converted.circuit")[0]
    assert canonical(a) == canonical(b)


def test_the_round_trip_compile_convert_compile(project):
    path = project.root / "hardware" / "graph.circuit"
    path.write_text(flat(LED_BAR))
    first, _ = resolved_of(path)
    from edakit.design import load_parts
    cfg = project.config()
    g = compile_path(path)
    design = design_of(path, load_parts(cfg.parts), list(cfg.boards), g)
    again = project.root / "hardware" / "again.circuit"
    again.write_text(to_circuit(g, design))
    assert canonical(resolved_of(again)[0]) == canonical(first)


def test_a_toml_project_converts_the_same_way(project, capsys):
    want = converted(fixture_graph(project))
    to_toml(project)
    assert run(project, "convert", "--to", "circuit") == 0
    out = capsys.readouterr().out
    assert "hardware/graph.toml is no longer read" in out
    cfg = project.config()
    assert canonical(resolved_of(cfg.graph)[0]) == canonical(want)
    assert (project.root / "hardware" / "graph.toml").exists()


def test_the_circuit_sign_offs_are_carried_over(project, capsys):
    cfg = project.config()
    signed = gate.state_hash(cfg)
    s = json.loads(cfg.signoff.read_text())
    cfg.signoff.write_text(json.dumps({**s, "state_sha256": signed}, indent=2) + "\n")
    assert run(project, "convert", "--to", "circuit") == 0
    assert "the sign-offs of scope 'circuit' keep counting" in capsys.readouterr().out
    cfg = project.config()
    s = json.loads(cfg.signoff.read_text())
    assert s["state_sha256"] == gate.state_hash(cfg) != signed
    assert s["rehashed"][-1]["by"] == "edakit graph convert --to circuit"
    assert "hardware/graph.circuit" in s["rehashed"][-1]["why"]


def test_project_edakit_is_set_and_a_higher_one_kept(project):
    text = (project.root / "edakit.toml").read_text()
    base = __version__.split("+")[0]
    got = tomllib.loads(needs_edakit(text, __version__))["project"]["edakit"]
    assert got == f">={base}"
    higher = needs_edakit(needs_edakit(text, "99.0.0"), __version__)
    assert tomllib.loads(higher)["project"]["edakit"] == ">=99.0.0"
    assert run(project, "convert", "--to", "circuit") == 0
    assert project.config().edakit == f">={base}"


def test_an_existing_target_is_refused_and_dry_run_writes_nothing(project, capsys):
    files = {p: p.read_bytes() for p in project.root.rglob("*") if p.is_file()}
    assert run(project, "convert", "--to", "circuit", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "part U1 microcontroller" in out and "would write hardware/graph.circuit" in out
    assert {p: p.read_bytes() for p in project.root.rglob("*") if p.is_file()} == files
    (project.root / "hardware" / "graph.circuit").write_text("# there\n")
    assert run(project, "convert", "--to", "circuit") == 1
    assert "is there already" in capsys.readouterr().err


def test_a_circuit_graph_has_nothing_to_convert(project, capsys):
    assert run(project, "convert", "--to", "circuit") == 0
    capsys.readouterr()
    assert run(project, "convert", "--to", "circuit") == 0
    assert "is the circuit language already" in capsys.readouterr().out
    assert run(project, "convert") == 0
    assert "is the circuit language already" in capsys.readouterr().out


def test_convert_without_to_is_as_before(project, capsys):
    assert run(project, "convert") == 0
    assert project.config().graph.suffix == ".toml"
