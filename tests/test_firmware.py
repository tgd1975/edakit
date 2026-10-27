"""edakit firmware: the board's firmware contract from the graph and the parts entries, and its drift (handbook 3.5)."""

import json

import pytest

from edakit import cli, firmware
from edakit.design import Design
from edakit.sim import run as simrun

FIRMWARE = '\n[firmware]\nmcu = "U1"\nout = "hardware/firmware.json"\n'


def chain_roles(project, first_bit_to=None):
    """The TLC5916 entry with the roles a chain needs: sdi, sdo and its outputs numbered out0 … out7."""
    p = project.part("C90107")
    p["pins"]["2"]["role"] = "sdi"
    p["pins"]["14"]["role"] = "sdo"
    for i, pin in enumerate(range(5, 13)):
        p["pins"][str(pin)]["role"] = f"out{i}"
    if first_bit_to:
        p["params"]["first_bit_to"] = first_bit_to
    project.save_part("C90107", p)


def with_firmware(project, first_bit_to=None):
    chain_roles(project, first_bit_to)
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text() + FIRMWARE)
    return project.config()


def contract(project):
    cfg = project.config()
    return firmware.contract(cfg, Design.from_config(cfg))


def test_contract_of_the_example(project):
    with_firmware(project, first_bit_to="out7")
    c = contract(project)
    pins = c["pins"]
    assert c["mcu"] == "U1" and c["graph_version"] == "1.0" and len(c["state_sha256"]) == 64
    assert {pins["LED_SDI"]["gpio"], pins["LED_CLK"]["gpio"]} == {2, 3}   # G-15 (#43) swaps the two in the example
    assert pins["LED_LE"] == {"pin": "U1.6", "name": "GP4", "gpio": 4, "dir": "out", "pull": None, "idle": None,
                              "active": None}
    oe = {k: v for k, v in pins["LED_OE"].items() if k not in ("fn", "fn_bus", "pwm_hz")}   # G-15 (#43) adds fn
    assert oe == {"pin": "U1.7", "name": "GP5", "gpio": 5, "dir": "out",
                  "pull": {"dir": "up", "by": ["R2"], "ohm": 10000.0}, "idle": 1, "active": 0}
    assert pins["BTN"] == {"pin": "U1.9", "name": "GP6", "gpio": 6, "dir": "in",
                           "pull": {"dir": "up", "by": "internal"}, "idle": 1, "active": 0}
    assert c["inputs"] == [{"part": "SW1", "kind": "button", "net": "BTN", "gpio": 6, "active": 0}]
    assert c["chains"] == [{"data": "LED_SDI", "parts": ["U2"], "read_back": None, "first_bit_to": "out7",
                            "common": ["LED_CLK", "LED_LE", "LED_OE"]}]
    assert [(ch["channel"], ch["driver"], ch["output"], ch["net"], ch["leds"]) for ch in c["channels"]] == \
        [(k, "U2", k, f"LED{k}", [{"des": f"D{k + 2}", "color": "green"}]) for k in range(8)]
    assert c["channels"][0]["pin"] == "U2.5" and c["channels"][0]["chain"] == 0
    assert "format" not in c                                        # rendering is the project's job


def test_first_bit_to_unknown_without_the_part_fact(project):
    with_firmware(project)
    assert contract(project)["chains"][0]["first_bit_to"] == "unknown"


def test_roles_not_names(project):
    """An LED whose cathode pin is named "A" (pytree D-39): the contract follows the role."""
    with_firmware(project)
    before = contract(project)["channels"]
    led = project.part("C2297")
    led["pins"]["1"]["name"], led["pins"]["2"]["name"] = "K", "A"   # names swapped, roles as they are
    project.save_part("C2297", led)
    g = project.graph()
    for d in range(2, 10):
        project.comp(g, f"D{d}")["pins"] = {"1": "K", "2": "A"}
    project.save_graph(g)
    assert contract(project)["channels"] == before


def test_leds_behind_bridges_and_balancing_resistors(project):
    """Traced as E-3/E-4 trace them: D2 behind a 0 Ω bridge, D3 and a second LED behind balancing resistors."""
    with_firmware(project)
    project.use_library_part("C17513")    # 1 kΩ as balancing resistor
    zero = project.part("C17414") | {"lcsc": "C99000", "params": {"value_ohm": 0}}
    project.save_part("C99000", zero)
    g = project.graph()
    comps, nets = g["graph"]["components"], g["graph"]["nets"]
    comps.append({"designator": "R9", "type": "resistor", "lcsc": "C99000", "pins": {"1": "1", "2": "2"}, "value": "0"})
    project.net(g, "LED0")["pins"] = ["U2.5", "R9.1"]
    nets.append({"name": "LED0_B", "pins": ["R9.2", "D2.2"], "v": [0, 5.5]})
    project.net(g, "LED1")["pins"] = ["U2.6", "R10.1", "R11.1"]
    comps += [{"designator": r, "type": "resistor", "lcsc": "C17513", "pins": {"1": "1", "2": "2"}, "value": "1k"}
              for r in ("R10", "R11")]
    comps.append({**project.comp(g, "D3"), "designator": "D10"})
    nets += [{"name": "LED1_K", "pins": ["R10.2", "D3.2"], "v": [0, 5.5]},
             {"name": "LED1_K2", "pins": ["R11.2", "D10.2"], "v": [0, 5.5]}]
    project.net(g, "+5V")["pins"].append("D10.1")
    project.save_graph(g)
    ch = contract(project)["channels"]
    assert ch[0]["leds"] == [{"des": "D2", "color": "green"}] and ch[0]["net"] == "LED0"
    assert [x["des"] for x in ch[1]["leds"]] == ["D3", "D10"]


def test_led_on_a_gpio_and_a_dip_switch(project):
    """An LED on a GPIO through its series resistor lights high (anode side); DIP bits in the order a1 … aN."""
    with_firmware(project)
    project.use_library_part("C17513")
    project.save_part("C99001", {"lcsc": "C99001", "mpn": "DIP-2", "kind": "dip_switch", "params": {"positions": 2},
                                 "pins": {"1": {"name": "A1", "type": "passive", "role": "a1"},
                                          "2": {"name": "A2", "type": "passive", "role": "a2"},
                                          "3": {"name": "B2", "type": "passive", "role": "b2"},
                                          "4": {"name": "B1", "type": "passive", "role": "b1"}}})
    g = project.graph()
    project.free_pins(g, "U1.10", "U1.11", "U1.12")    # GP7, GP8, GP9
    comps, nets = g["graph"]["components"], g["graph"]["nets"]
    comps += [{"designator": "R9", "type": "resistor", "lcsc": "C17513", "pins": {"1": "1", "2": "2"}, "value": "1k"},
              {**project.comp(g, "D2"), "designator": "D10"},
              {"designator": "SW2", "type": "switch", "lcsc": "C99001",
               "pins": {"1": "A1", "2": "A2", "3": "B2", "4": "B1"}}]
    nets += [{"name": "STATUS", "pins": ["U1.10", "R9.1"], "v": [0, 3.4]},
             {"name": "STATUS_A", "pins": ["R9.2", "D10.1"], "v": [0, 3.4]},
             {"name": "DIP_HI", "pins": ["U1.12", "SW2.3"], "v": [0, 3.4]},     # switch 2
             {"name": "DIP_LO", "pins": ["U1.11", "SW2.4"], "v": [0, 3.4]}]     # switch 1
    project.net(g, "GND")["pins"] += ["D10.2", "SW2.1", "SW2.2"]
    project.save_graph(g)
    c = contract(project)
    assert c["pins"]["STATUS"]["dir"] == "out" and c["pins"]["STATUS"]["active"] == 1
    assert c["pins"]["STATUS"]["leds"] == [{"des": "D10", "color": "green", "side": "anode"}]
    assert c["pins"]["DIP_LO"]["pull"] == {"dir": "up", "by": "internal"}
    assert c["inputs"][-1] == {"part": "SW2", "kind": "dip_switch", "active": 0,
                               "bits": [{"switch": 1, "net": "DIP_LO", "gpio": 8},
                                        {"switch": 2, "net": "DIP_HI", "gpio": 9}]}


def test_numbered_outputs_without_a_chain_role_and_unnumbered_ones(project):
    """Outputs numbered out0 … outN are channels of their driver even outside a chain; a chain of drivers whose
    outputs are only "out" has no channel order – an error, never a guess from pin names."""
    with_firmware(project)
    p = project.part("C90107")
    for pin in range(5, 13):
        p["pins"][str(pin)]["role"] = "out"
    project.save_part("C90107", p)
    with pytest.raises(firmware.ContractError, match=r"U2: its outputs have the role out without a number"):
        contract(project)


def test_sim_reads_numbered_outputs_as_out(project):
    cfg = project.config()
    sim, _ = simrun.load_sim_config(cfg)
    before = simrun.run_all(Design.from_config(cfg), sim)["checks"]
    chain_roles(project)
    after = simrun.run_all(Design.from_config(project.config()), sim)["checks"]
    assert after == before and len(after) > 700


def test_cli_writes_and_check_finds_drift(project, monkeypatch, capsys):
    with_firmware(project)
    monkeypatch.chdir(project.root)
    out = project.root / "hardware" / "firmware.json"
    assert cli.main(["firmware", "--check"]) == 2 and "not written yet" in capsys.readouterr().out
    assert cli.main(["firmware"]) == 0 and out.exists()
    assert cli.main(["firmware", "--check"]) == 0
    g = project.graph()                       # two LED nets swapped: D2 on OUT1, D3 on OUT0
    project.net(g, "LED0")["pins"] = ["U2.5", "D3.2"]
    project.net(g, "LED1")["pins"] = ["U2.6", "D2.2"]
    project.save_graph(g)
    text = out.read_text()
    capsys.readouterr()
    assert cli.main(["firmware", "--check"]) == 2
    report = capsys.readouterr().out
    assert "drift" in report and "channels[0].leds" in report and "D2" in report and "D3" in report
    assert out.read_text() == text            # --check writes nothing
    assert json.loads(text)["channels"][0]["leds"][0]["des"] == "D2"


def test_opt_in(project, monkeypatch, capsys):
    monkeypatch.chdir(project.root)
    assert cli.main(["firmware"]) == 1 and "no [firmware] table" in capsys.readouterr().err
    assert cli.main(["check"]) == 0          # G-2 with pin_locks as before
