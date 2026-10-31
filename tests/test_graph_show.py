"""edakit graph show (maker-coverage FT-23): one part or net – what the graph and its parts entry say, the findings on
it."""

import json

from edakit import cli


def show(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(["graph", "show", *args])


def test_a_part_with_its_entry_pins_and_nets(project, monkeypatch, capsys):
    assert show(project, monkeypatch, "U2") == 0
    out = capsys.readouterr().out
    assert out.startswith("U2  ic on main – TLC5916")
    assert "entry C90107 (ic)" in out and "vdd_max_v = 7" in out
    assert "13   OE(ED2)      oe_n       LED_OE" in out and "14   SDO                     nc" in out
    assert out.rstrip().endswith("findings  none")


def test_a_net_with_its_pins_accept_and_finding(project, monkeypatch, capsys, tmp_path):
    assert show(project, monkeypatch, "LED_CLK", "--json", str(tmp_path / "v.json")) == 0
    out = capsys.readouterr().out
    assert out.startswith("LED_CLK  0 … 3.4 V  (fn spi.sck)")
    assert "U2.3     ic             CLK" in out
    assert "accept    LVL.undefined: Floating until the firmware runs" in out
    view = json.loads((tmp_path / "v.json").read_text())
    assert [(f["code"], bool(f["accepted"])) for f in view["findings"]] == [("LVL.undefined", True)]


def test_a_finding_shows_where_it_is(project, monkeypatch, capsys):
    """Without R2 nothing holds LED_OE: the finding on the net is in its view."""
    g = project.graph()
    project.net(g, "LED_OE")["pins"].remove("R2.2")
    project.net(g, "3V3")["pins"].remove("R2.1")
    g["graph"]["components"] = [c for c in g["graph"]["components"] if c["designator"] != "R2"]
    project.save_graph(g)
    assert show(project, monkeypatch, "LED_OE") == 0
    out = capsys.readouterr().out
    assert "LVL.undefined  LED_OE:" in out and "findings  none" not in out


def test_an_unknown_name(project, monkeypatch, capsys):
    assert show(project, monkeypatch, "LED_XX") == 1
    assert "no part or net LED_XX in the graph – similar: " in capsys.readouterr().err
