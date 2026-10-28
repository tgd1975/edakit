"""The rule set of EasyEDA's DRC (step 2.2): what [routing] of the board file asks of it, where the rule set EasyEDA
holds differs, and what edakit would write – on recorded data, without EasyEDA.

fixtures/easyeda/drc_rules_3.2.206.json is the rule configuration EasyEDA Pro 3.2.206 answered on the PCB of the
reference project (getCurrentRuleConfiguration, read with the bridge's return depth 12 on 2026-10-22), unchanged, and
its net rules and net classes in the form they came in, with the example's nets (POWER: VIN, +5V, GND; SUPPLY: 3V3).
The net classes are the netClass entries of the net rules (EasyEDA's editor bundle, handbook 9.4); which rules a class
made anew and a moved net get (FakeDrc) is an assumption until the live probe of step 2.2 has seen it."""

import copy
import json
from pathlib import Path

import pytest

from edakit import drc_rules, eda
from edakit.config import ConfigError

RECORDED = json.loads((Path(__file__).parent / "fixtures" / "easyeda" / "drc_rules_3.2.206.json").read_text())


def board_of(project, routing=None):
    """The example's board, its [routing] replaced by `routing` (TOML text) when given."""
    if routing is not None:
        f = project.root / "hardware" / "boards" / "main.toml"
        text = f.read_text()
        start, end = text.index("[routing]"), text.index("[[pours]]")
        f.write_text(text[:start] + routing + "\n" + text[end:])
    return project.config().board()


@pytest.fixture
def want(project):
    return drc_rules.wanted(project.config().board())


def recorded():
    return copy.deepcopy({k: v for k, v in RECORDED.items() if not k.startswith("_")})


def rounded(want):
    """The rule set of the board file to the µm, without the words."""
    return {"clearance": round(want["clearance"], 4), "edge": round(want["edge"], 4),
            "track": {k: round(v, 4) for k, v in want["track"].items()}, "via": tuple(round(v, 4) for v in want["via"]),
            "classes": want["classes"]}


# --- what the board file asks ---------------------------------------------------------------------------------------

def test_the_example_asks_for_its_routing_rules(want):
    assert rounded(want) == {
        "clearance": 0.1651, "edge": 0.4, "track": {"": 0.254, "POWER": 0.4572, "GND": 0.4572, "SUPPLY": 0.3048},
        "via": (0.6096, 0.3048), "classes": {"POWER": ["+5V", "VIN"], "GND": ["GND"], "SUPPLY": ["3V3"]}}
    assert want["why"] == {"clearance": "clearance_mil 6.5", "edge": "edge_clearance_um 400", "via": "via [24, 12]",
                           "": "signal_mil 10", "POWER": "width_mil 18", "GND": "width_mil 18",
                           "SUPPLY": "width_mil 12"}
    assert drc_rules.summary(want) == ("clearance 0.165 mm, edge 0.400 mm, tracks 0.254 mm (POWER 0.457, GND 0.457, "
                                       "SUPPLY 0.305 mm), via Ø 0.610 / drill 0.305 mm")


def test_without_routing_keys_the_routers_defaults(project):
    want = drc_rules.wanted(board_of(project, "[routing]\n"))
    assert rounded(want) == {"clearance": 0.1651, "edge": 0.4, "track": {"": 0.254}, "via": (0.6096, 0.3048),
                             "classes": {}}


def test_a_fixed_wire_narrower_than_its_class_lowers_its_width(project):
    """The board file prescribes the wire: EasyEDA's DRC has to take it."""
    want = drc_rules.wanted(board_of(project, """[routing]
classes = { POWER = { width_mil = 18, nets = ["VIN", "+5V"] } }

[[routing.fixed_wires]]
net = "+5V"
width_mil = 14
points = [[60, 12], [55, 12]]

[[routing.fixed_wires]]
net = "VIN"
width_mil = 12
points = [[80, 12], [70, 12]]

[[routing.fixed_wires]]
net = "BTN"
points = [[80, 25], [75, 25]]
"""))
    assert want["track"] == pytest.approx({"": 0.254, "POWER": 0.3048})    # BTN takes signal_mil: no change
    assert want["why"]["POWER"] == "width_mil 18, fixed wire VIN 12 mil"


def test_the_key_takes_check_only(project):
    assert drc_rules.mode(board_of(project)) is None                    # no key, no change
    assert drc_rules.mode(board_of(project, '[routing]\ndrc_rules = "check"\n')) == "check"
    with pytest.raises(ConfigError, match='routing.drc_rules must be "check".*not \'write\''):
        drc_rules.mode(board_of(project, '[routing]\ndrc_rules = "write"\n'))


# --- the recorded rule set against the example -----------------------------------------------------------------------

def test_the_recorded_rule_set_is_not_the_examples(want):
    """The recorded clearances (0.102 / 0.152 mm), classes and least via against the example's [routing]: every
    difference with both numbers and the board file's words."""
    at = "(Safe Spacing 'copperThickness1oz')"
    assert drc_rules.differences(want, recorded()) == [
        f"clearance Track–Track: EasyEDA 0.102 mm {at}, the board file 0.165 mm (clearance_mil 6.5)",
        "clearance Track–SMD Pad, Track–TH Pad, Track–Via, Via–SMD Pad, Via–TH Pad, Via–Via: EasyEDA 0.152 mm "
        f"{at}, the board file 0.165 mm (clearance_mil 6.5)",
        f"edge Track–Board Outline, Via–Board Outline: EasyEDA 0.300 mm {at}, the board file 0.400 mm "
        "(edge_clearance_um 400)",
        "track, nets without a class (14: BTN, LED0, LED1, LED2, LED3, LED4, …): EasyEDA min 0.127 mm (Track "
        "'copperThickness1oz'), the board file 0.254 mm (signal_mil 10)",
        "track POWER (+5V, VIN): EasyEDA min 0.400 mm (Track 'POWER'), the board file 0.457 mm (width_mil 18)",
        "track SUPPLY (3V3): EasyEDA min 0.300 mm (Track 'SUPPLY'), the board file 0.305 mm (width_mil 12)",
        "track GND (GND): EasyEDA min 0.400 mm (Track 'POWER'), the board file 0.457 mm (width_mil 18)",
        "via: EasyEDA min Ø 0.500 mm, drill 0.300 mm (Via Size 'viaSize'), the board file Ø 0.610 mm, drill 0.305 mm "
        "(via [24, 12])",
        "class POWER: EasyEDA's has GND too",
        "class GND (GND): in [routing.classes], not among EasyEDA's net classes"]


def test_the_recorded_values_are_read_in_their_unit(want):
    """A rule in mil compares like one in mm."""
    have = written(want)
    rule = have["configuration"]["config"]["Physics"]["Track"]["POWER"]
    rule["unit"] = "mil"
    for entry in rule["form"]["data"].values():
        entry.update({k: v / 0.0254 for k, v in entry.items()})
    assert drc_rules.differences(want, have) == []
    rule["unit"] = "furlong"
    assert drc_rules.differences(want, have) == ["Track 'POWER': unit 'furlong' not understood"]


# --- writing, read back -------------------------------------------------------------------------------------------

class FakeDrc:
    """EasyEDA's PCB_Drc on data: the rule set of `have`, the calls edakit makes, the answers as easyeda_api_call gives
    them. A change of the net classes regroups the net rules, whose netClass entries the classes are: a new class gets
    an entry with the default rules and its nets under "sub", a net that leaves its class goes back to the top level –
    each net keeping its own rules, an assumption until the live probe."""

    def __init__(self, have, refuse=None):
        self.have, self.refuse, self.calls = copy.deepcopy(have), refuse or {}, []

    def call(self, tool, timeout=130, **args):
        assert tool == "easyeda_api_call" and args.get("confirmWrite")
        method, a = args["path"].removeprefix("PCB_Drc."), args["args"]
        self.calls.append(method)
        h = self.have
        if method in self.refuse:                       # false, or null: the PCB tab counted as inactive
            return {"ok": True, "result": self.refuse[method]}
        read = {"getCurrentRuleConfiguration": "configuration", "getNetRules": "net_rules",
                "getAllNetClasses": "net_classes"}
        if method in read:
            return {"ok": True, "result": copy.deepcopy(h[read[method]])}
        classes = {c["name"]: c for c in h["net_classes"]}
        if method == "createNetClass":
            h["net_classes"].append({"name": a[0], "nets": list(a[1]), "color": a[2]})
        elif method == "deleteNetClass":
            h["net_classes"].remove(classes[a[0]])
        elif method == "addNetToNetClass":
            classes[a[0]]["nets"] += a[1]
        elif method == "removeNetFromNetClass":
            classes[a[0]]["nets"] = [n for n in classes[a[0]]["nets"] if n not in a[1]]
        elif method == "overwriteCurrentRuleConfiguration":
            h["configuration"] = {"config": copy.deepcopy(a[0]), "name": h["configuration"]["name"]}
            return {"ok": True, "result": True}
        elif method == "overwriteNetRules":
            h["net_rules"] = copy.deepcopy(a[0])
            return {"ok": True, "result": True}
        else:
            raise AssertionError(method)
        self.regroup()
        return {"ok": True, "result": True}

    def regroup(self):
        h = self.have
        nets = drc_rules.nets_of(h["net_rules"])
        old = {e["name"]: e for e in h["net_rules"] if e["type"] == "netClass"}
        proto = next(e for e in RECORDED["net_rules"] if e["type"] == "netClass")
        member = {n: c["name"] for c in h["net_classes"] for n in c["nets"]}
        rules = []
        for c in h["net_classes"]:
            entry = old.get(c["name"]) or {**{k: v if v is None else "default" for k, v in proto.items()},
                                           "type": "netClass", "name": c["name"]}
            rules.append({**entry, "sub": [nets[n] for n in c["nets"] if n in nets]})
        rules += [e for n, e in nets.items() if n not in member]
        h["net_rules"] = rules


def written(want, have=None):
    """The rule set EasyEDA holds after eda.write_drc_rules – on FakeDrc."""
    fake = FakeDrc(have or recorded())
    assert eda.write_drc_rules(fake, want) == []
    return fake.have


def test_what_edakit_writes_reads_back_as_the_board_files(want):
    have = written(want)
    assert drc_rules.differences(want, have) == []
    assert sorted(c["name"] for c in have["net_classes"]) == ["GND", "POWER", "SUPPLY"]
    tracks = have["configuration"]["config"]["Physics"]["Track"]
    assert tracks["GND"] == {"editName": "GND", "unit": "mm", "isSetDefault": False, "form": {"status": 1, "data": {
        layer: {"minValue": pytest.approx(0.4572), "defaultValue": pytest.approx(0.4572), "maxValue": 2.54}
        for layer in ("1", "2")}}}
    assert tracks["copperThickness1oz"]["form"]["data"]["1"] == pytest.approx(
        {"minValue": 0.254, "defaultValue": 0.254, "maxValue": 2.54})


def test_writing_changes_only_what_the_board_file_holds(want):
    """The other cells of the spacing table, the other rules and categories stay as EasyEDA had them."""
    before, after = recorded()["configuration"]["config"], written(want)["configuration"]["config"]
    for category in ("Plane", "Expansion"):
        assert after[category] == before[category]
    spacing_before, spacing_after = before["Spacing"]["Safe Spacing"], after["Spacing"]["Safe Spacing"]
    assert spacing_after["copperThickness2oz"] == spacing_before["copperThickness2oz"]
    rule = spacing_before["copperThickness1oz"]
    old, new = rule["tables"]["1"]["content"], spacing_after["copperThickness1oz"]["tables"]["1"]["content"]
    owned = {drc_rules.cell(rule, old, a, b) for a, b in drc_rules.CLEARANCE_CELLS + drc_rules.EDGE_CELLS}
    changed = {(r, c) for r, row in enumerate(old) for c, v in enumerate(row) if new[r][c] != v}
    assert changed == owned and len(owned) == 9
    via = after["Physics"]["Via Size"]["viaSize"]["form"]
    assert (via["viaOuterdiameterMin"], via["viaInnerdiameterMin"], via["viaOuterdiameterMax"]) == pytest.approx(
        (0.6096, 0.3048, 10.00000032))


def test_the_classes_change_before_the_rules(want):
    """Removals first – a net leaves its old class before it joins another –, nets the PCB lacks left out
    (createNetClass fails on them), a class of EasyEDA the board file does not know deleted."""
    have = recorded()
    have["net_classes"].append({"name": "HV", "nets": [], "color": None})
    want["classes"]["SUPPLY"] = ["3V3", "VBAT"]                           # VBAT: not in this PCB
    assert drc_rules.class_changes(want, have) == [
        ("deleteNetClass", "HV"), ("removeNetFromNetClass", "POWER", ["GND"]), ("createNetClass", "GND", ["GND"], None)]
    fake = FakeDrc(have)
    eda.write_drc_rules(fake, want)
    assert fake.calls == ["getCurrentRuleConfiguration", "getNetRules", "getAllNetClasses",
                          "deleteNetClass", "removeNetFromNetClass", "createNetClass",
                          "getCurrentRuleConfiguration", "getNetRules", "getAllNetClasses",
                          "overwriteCurrentRuleConfiguration",
                          "getCurrentRuleConfiguration", "getNetRules", "getAllNetClasses", "overwriteNetRules",
                          "getCurrentRuleConfiguration", "getNetRules", "getAllNetClasses"]


def test_a_refused_call_stops_the_writing(want):
    fake = FakeDrc(recorded(), refuse={"createNetClass": False})
    with pytest.raises(eda.MCPError, match=r'PCB_Drc.createNetClass returned false \(\["GND", \["GND"\], null\]\)'):
        eda.write_drc_rules(fake, want)
    assert "overwriteCurrentRuleConfiguration" not in fake.calls
    fake = FakeDrc(recorded(), refuse={"overwriteCurrentRuleConfiguration": None})
    with pytest.raises(eda.MCPError, match="PCB_Drc.overwriteCurrentRuleConfiguration returned null"):
        eda.write_drc_rules(fake, want)
    assert "overwriteNetRules" not in fake.calls


# --- one difference each ------------------------------------------------------------------------------------------

def spacing(have, a, b, mm):
    rule = have["configuration"]["config"]["Spacing"]["Safe Spacing"]["copperThickness1oz"]
    content = rule["tables"]["1"]["content"]
    r, c = drc_rules.cell(rule, content, a, b)
    content[r][c] = mm


def net(have, name):
    return drc_rules.nets_of(have["net_rules"])[name]


ONE = [
    ("within 1 µm counts as equal", lambda h: spacing(h, "Track", "Track", 0.165), None),
    ("an edge clearance", lambda h: spacing(h, "Via", "Board Outline", 0.3),
     "edge Via–Board Outline: EasyEDA 0.300 mm (Safe Spacing 'copperThickness1oz'), the board file 0.400 mm "
     "(edge_clearance_um 400)"),
    ("a net of a class on the default track rule", lambda h: net(h, "VIN").update(Track="default"),
     "track POWER (VIN): EasyEDA min 0.254 mm (Track 'copperThickness1oz'), the board file 0.457 mm (width_mil 18)"),
    ("a class rule narrower at its top end", lambda h: h["configuration"]["config"]["Physics"]["Track"]["POWER"][
        "form"]["data"]["2"].update(maxValue=0.3),
     "track POWER (+5V, VIN): EasyEDA max 0.300 mm (Track 'POWER'), below the board file's 0.457 mm (width_mil 18)"),
    ("another drill", lambda h: h["configuration"]["config"]["Physics"]["Via Size"]["viaSize"]["form"].update(
        viaInnerdiameterMin=0.3),
     "via: EasyEDA min Ø 0.610 mm, drill 0.300 mm (Via Size 'viaSize'), the board file Ø 0.610 mm, drill 0.305 mm "
     "(via [24, 12])"),
    ("a net on a spacing rule the configuration lacks", lambda h: net(h, "BTN").update({"Safe Spacing": "HV"}),
     "Safe Spacing 'HV': named by EasyEDA's net rules (BTN), not in its rule configuration"),
    ("no default track rule", lambda h: h["configuration"]["config"]["Physics"]["Track"]["copperThickness1oz"].update(
        isSetDefault=False),
     "Track: no rule of EasyEDA's configuration is the default (isSetDefault) – the nets on 'default' (BTN, LED0, "
     "LED1, LED2, LED3, LED4, …) have none"),
    ("a class of EasyEDA the board file does not know",
     lambda h: h["net_classes"].append({"name": "HV", "nets": ["LED0"], "color": None}),
     "class HV (LED0): EasyEDA's net class, not in [routing.classes]"),
]


@pytest.mark.parametrize("change, expected", [pytest.param(c, e, id=name) for name, c, e in ONE])
def test_one_difference_each(want, change, expected):
    have = written(want)
    change(have)
    assert drc_rules.differences(want, have) == ([expected] if expected else [])


def test_the_row_of_l3(project, tmp_path):
    """verdict: the rule set named, the differences – or why there is nothing to compare."""
    board = board_of(project, '[routing]\ndrc_rules = "check"\n')
    path = tmp_path / "drc_rules.json"
    assert drc_rules.verdict(board, path)[:2] == (
        False, "drc_rules.json missing (edakit fab without --offline reads it with the DRC)")
    path.write_text(json.dumps({"error": "PCB_Drc.getNetRules: timeout"}))
    assert drc_rules.verdict(board, path)[:2] == (False, "not read: PCB_Drc.getNetRules: timeout")
    path.write_text(json.dumps(recorded()))
    ok, actual, expected = drc_rules.verdict(board, path)
    assert not ok and actual.startswith("rule set 'Custom Config': clearance Track–Track: EasyEDA 0.102 mm")
    assert expected == "clearance 0.165 mm, edge 0.400 mm, tracks 0.254 mm, via Ø 0.610 / drill 0.305 mm"


# --- the thin calls -------------------------------------------------------------------------------------------------

def test_reading_takes_the_three_answers():
    fake = FakeDrc(recorded())
    assert eda.read_drc_rules(fake) == recorded()
    assert fake.calls == ["getCurrentRuleConfiguration", "getNetRules", "getAllNetClasses"]


def test_reading_through_the_original_bridge_is_cut_off():
    """With depth 5 the spacing table comes back as "[MaxDepth]" (seen on 2026-10-21 in the reference project)."""
    have = recorded()
    have["configuration"]["config"]["Spacing"]["Safe Spacing"]["copperThickness1oz"]["tables"] = "[MaxDepth]"
    with pytest.raises(eda.MCPError, match=r"cut off \(\[MaxDepth\]\) – import the patched bridge"):
        eda.read_drc_rules(FakeDrc(have))
    have["configuration"] = None                       # no configuration in the answer
    with pytest.raises(eda.MCPError, match="no DRC rule configuration"):
        eda.read_drc_rules(FakeDrc(have))
