"""HINT.usb_budget and HINT.usb_inrush (maker-coverage HT-2, HT-3; domain usb): what a USB port gives a device, and
the 10 µF a device may show on VBUS at attach – numbers read from the USB 2.0 and Type-C specifications
(catalog/tables/usb.toml)."""

from helpers import check

from edakit import catalog, cli
from edakit.design import Design


def add_usb(project, monkeypatch):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["block", "add", "usb-c-sink", "--as", "USB", "--connect", "vbus=USB_5V"]) == 0


def hints(project):
    cfg = project.config()
    rep = check(Design.from_config(cfg), cfg)
    return {(f.code, f.place) for f in rep.findings if f.code in ("HINT.usb_budget", "HINT.usb_inrush")}


def capacitor_on(project, net, value_f, des="C30", key="C9100030"):
    project.save_part(key, {"lcsc": key, "mpn": f"{value_f * 1e6:g} uF test capacitor", "kind": "capacitor",
                            "limits": {"v_max_v": 16}, "values": {"value_f": value_f},
                            "pins": {"1": {"name": "1", "type": "passive"}, "2": {"name": "2", "type": "passive"}},
                            "verified": {"by": "test"}})
    g = project.graph()
    gg = g.get("graph", g)
    gg["components"].append({"designator": des, "type": "capacitor", "lcsc": key, "pins": {"1": "1", "2": "2"},
                             "board": gg["components"][0].get("board", "main")})
    next(n for n in gg["nets"] if n["name"] == net)["pins"].append(f"{des}.1")
    next(n for n in gg["nets"] if n["name"] == gg.get("ground", "GND"))["pins"].append(f"{des}.2")
    project.save_graph(g)


def test_the_numbers_are_read_from_the_specifications():
    t = catalog.table("usb")
    assert (t["budget"]["unit_load_a"], t["budget"]["high_power_a"]) == (0.1, 0.5)
    assert (t["typec_current"]["rp_1a5_a"], t["typec_current"]["rp_3a0_a"]) == (1.5, 3.0)
    assert t["attach"]["c_max_f"] == 10e-6
    assert all("usb.org" in t[k]["source"] for k in ("budget", "typec_current", "attach"))


def test_a_board_without_a_usb_port_gets_neither(project):
    assert hints(project) == set()          # the example's J1 is a JST power input, no USB port


def test_a_usb_receptacle_gets_the_budget_hint(project, monkeypatch):
    add_usb(project, monkeypatch)
    assert {c for c, _ in hints(project)} == {"HINT.usb_budget"}


def test_more_than_10_uF_on_vbus_gets_the_inrush_hint(project, monkeypatch):
    add_usb(project, monkeypatch)
    g = project.graph()
    vbus = next(n["name"] for n in g.get("graph", g)["nets"] if any(p.endswith(".A9") for p in n["pins"]))
    capacitor_on(project, vbus, 10e-6)                       # at the limit: no hint
    assert {c for c, _ in hints(project)} == {"HINT.usb_budget"}
    capacitor_on(project, vbus, 4.7e-6, "C31", "C9100031")    # 14.7 µF directly on VBUS
    assert {c for c, _ in hints(project)} == {"HINT.usb_budget", "HINT.usb_inrush"}
