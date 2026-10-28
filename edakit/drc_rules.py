"""The rule set of EasyEDA's DRC as text: what the board file's [routing] asks of it, and where the rule set EasyEDA
holds differs (design-as-text decision 6, step 2.2 of the implementation plan).

L-3 asks for a DRC without findings – with the rules EasyEDA holds, set in its GUI (Design → Design Rule), which no
file shows. With `[routing] drc_rules = "check"` in the board file, stage L reads the rule set the DRC ran with
(eda.read_drc_rules, into drc_rules.json of the run) and L-3 compares it with the board file. Nothing here talks to
EasyEDA: eda.read_drc_rules and eda.write_drc_rules are the thin calls around these functions. Writing has not run
against EasyEDA yet – the live probe of step 2.2 decides whether edakit writes the rule set or only checks it
(handbook 9.4).

What the board file asks (route.Rules reads the same keys for the DSN; mil there, mm here):
    clearance   clearance_mil: track to track, pad and via, via to pad and via, of different nets – the cells of
                EasyEDA's Safe Spacing table between Track, SMD Pad, TH Pad and Via. Pads among themselves are left to
                the footprints: L-13 measures pads of different parts.
    edge        edge_clearance_um: track and via to the board outline
    tracks      the least width of a track: signal_mil for a net without a class, width_mil for the nets of a class
                of [routing.classes]; a fixed wire narrower than that lowers it – the board file prescribes the wire.
                With widths = "sim" the classes keep their width_mil here: wider tracks pass the DRC, and L-5 holds
                every track to its simulated current.
    via         via = [diameter, drill]: the least via
    classes     [routing.classes]: EasyEDA's net classes, each with its nets that are in the PCB

EasyEDA's side, as getCurrentRuleConfiguration, getNetRules and getAllNetClasses answer (EasyEDA Pro 3.2.206 with the
bridge's return depth 12; tests/fixtures/easyeda/drc_rules_3.2.206.json):
    configuration  {"name": "Custom Config", "config": {category: {kind: {rule name: rule}}}}, the categories
                   Spacing, Physics, Plane and Expansion. Every rule has "unit" ("mm") and "isSetDefault": the rule of
                   its kind that a net rule "default" means.
                   Spacing / Safe Spacing: "row" (13 kinds of object), "column" (12), "tables" {"1": {"content": the
                   lower triangle – content[r][c] for row[r] and column[c], c <= r}}
                   Physics / Track: "form" {"data": {"1": {"minValue", "defaultValue", "maxValue"}, "2": …}}
                   Physics / Via Size: "form" {"viaOuterdiameterMin", "…Max", "…Default", "viaInnerdiameterMin", …}
    net_rules      [{"type": "netClass", "name", "Track": rule name | "default", "Safe Spacing", "Via Size", …,
                   "sub": [the class's nets, each {"type": "net", "name", "Track", …}]}, {"type": "net", …}, …]
    net_classes    [{"name", "nets", "color"}]
The keys of "data" and "tables" are "1" in EasyEDA's own rules and "1", "2" in the class rules made in the GUI on a
two-layer board: copper layers, it seems. Every entry counts here; what a lone "1" covers is a question for the probe.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict

from .config import MIL_PER_MM, ConfigError

MODES = ("check",)       # [routing] drc_rules; "write" waits for the live probe of step 2.2
TOL_MM = 0.001           # EasyEDA keeps mm with float noise (0.15200122 for 0.152 mm): equal within 1 µm
MM_PER_UNIT = {"mm": 1.0, "mil": 0.0254, "inch": 25.4}
LAYERS = ("1", "2")      # the copper layers a class rule edakit writes has entries for (TOP, BOTTOM)
CLEARANCE_CELLS = (("Track", "Track"), ("Track", "SMD Pad"), ("Track", "TH Pad"), ("Track", "Via"),
                   ("Via", "SMD Pad"), ("Via", "TH Pad"), ("Via", "Via"))
EDGE_CELLS = (("Track", "Board Outline"), ("Via", "Board Outline"))
SHOWN_NETS = 6           # a message names this many nets of a group, then "…"


def mode(board):
    """[routing] drc_rules of the board file: None without the key (L-3 as before), or "check"."""
    m = board.routing.get("drc_rules")
    if m is not None and m not in MODES:
        raise ConfigError(f"board {board.name}: routing.drc_rules must be \"check\" (L-3: the rule set EasyEDA's DRC "
                          f"ran with = [routing]), not {m!r} – writing it waits for the live probe (handbook 9.4)")
    return m


def wanted(board):
    """The rule set the board file asks of EasyEDA's DRC, in mm: {"clearance", "edge", "track": {class: least width},
    "via": (diameter, drill), "classes": {class: [nets]}, "why": {key: the board file's words}} – track "" is every net
    without a class."""
    from .route import Rules, fixed_wires
    r = Rules(board)
    mm = 1 / MIL_PER_MM
    track = {"": r.signal * mm} | {name: w * mm for name, (w, _) in r.classes.items()}
    why = {"clearance": f"clearance_mil {r.clear:g}", "edge": f"edge_clearance_um {r.edge_um:g}",
           "via": f"via [{r.via[1]:g}, {r.via[2]:g}]", "": f"signal_mil {r.signal:g}"}
    why |= {name: f"width_mil {w:g}" for name, (w, _) in r.classes.items()}
    words = dict(why)
    for net, _, w, _ in fixed_wires(r):
        cls = next((name for name, (_, nets) in r.classes.items() if net in nets), "")
        if w * mm < track[cls] - 1e-9:
            track[cls], why[cls] = w * mm, f"{words[cls]}, fixed wire {net} {w:g} mil"
    return {"clearance": r.clear * mm, "edge": r.edge_um / 1000, "track": track, "via": (r.via[1] * mm, r.via[2] * mm),
            "classes": {name: sorted(nets) for name, (_, nets) in r.classes.items()}, "why": why}


def summary(want):
    """The rule set of the board file in one line, the expected value of L-3's row."""
    classes = ", ".join(f"{c} {w:.3f}" for c, w in want["track"].items() if c)
    return (f"clearance {want['clearance']:.3f} mm, edge {want['edge']:.3f} mm, tracks {want['track']['']:.3f} mm"
            + (f" ({classes} mm)" if classes else "")
            + f", via Ø {want['via'][0]:.3f} / drill {want['via'][1]:.3f} mm")


# --- EasyEDA's rule set as data -----------------------------------------------------------------------------------

def nets_of(net_rules):
    """net name -> its entry of the net rules, inside a class or not."""
    out = {}
    for e in net_rules or []:
        for n in ([e] if e.get("type") == "net" else e.get("sub") or []):
            out[n.get("name")] = n
    return out


def kind(config, category, name):
    """The rules of one kind, e.g. kind(config, "Physics", "Track") -> {rule name: rule}."""
    return ((config or {}).get(category) or {}).get(name) or {}


def rule_of(rules, name):
    """(rule name, rule) a net rule's name stands for – "default" (or none) is the rule with isSetDefault; rule None:
    the configuration has no such rule."""
    if name in (None, "default"):
        return next(((n, r) for n, r in rules.items() if r.get("isSetDefault")), ("default", None))
    return name, rules.get(name)


def factor(rule):
    """mm per unit of a rule; None for a unit edakit does not know."""
    return MM_PER_UNIT.get((rule or {}).get("unit", "mm"))


def cell(rule, content, a, b):
    """(r, c) of the Safe Spacing value between kinds a and b in a table's lower triangle, or None."""
    rows, cols = rule.get("row") or [], rule.get("column") or []
    for x, y in ((a, b), (b, a)):
        if x in rows and y in cols:
            r, c = rows.index(x), cols.index(y)
            if c <= r and r < len(content) and c < len(content[r]):
                return r, c
    return None


def used(rules, nets, field):
    """The rules of a kind that EasyEDA's nets use (their field), the default always: [(rule name, rule, nets)]."""
    by = defaultdict(list)
    by[rule_of(rules, "default")[0]] = []
    for net, e in sorted(nets.items()):
        by[rule_of(rules, e.get(field))[0]].append(net)
    return [(name, rule_of(rules, name)[1], members) for name, members in by.items()]


def shown(nets):
    return ", ".join(nets[:SHOWN_NETS]) + (", …" if len(nets) > SHOWN_NETS else "")


def differences(want, have):
    """Where the rule set EasyEDA holds (have, as eda.read_drc_rules returns it) differs from the board file's (want):
    one line each, [] = the board file's."""
    conf = (have.get("configuration") or {}).get("config") or {}
    nets = nets_of(have.get("net_rules"))
    why = want["why"]
    out = []

    def missing(what, name, members):
        if name == "default":
            return (f"{what}: no rule of EasyEDA's configuration is the default (isSetDefault)"
                    + (f" – the nets on 'default' ({shown(members)}) have none" if members else ""))
        return (f"{what} '{name}': " + (f"named by EasyEDA's net rules ({shown(members)}), " if members else "")
                + "not in its rule configuration")

    for name, rule, members in used(kind(conf, "Spacing", "Safe Spacing"), nets, "Safe Spacing"):
        if rule is None:
            out.append(missing("Safe Spacing", name, members))
            continue
        f = factor(rule)
        if f is None:
            out.append(f"Safe Spacing '{name}': unit {rule.get('unit')!r} not understood")
            continue
        tables = rule.get("tables") or {}
        if not tables:
            out.append(f"Safe Spacing '{name}' has no table of values")
        for key, table in tables.items():
            content = table.get("content") or []
            at = f"Safe Spacing '{name}'" + (f", table {key}" if len(tables) > 1 else "")
            for what, cells, value in (("clearance", CLEARANCE_CELLS, want["clearance"]),
                                       ("edge", EDGE_CELLS, want["edge"])):
                off = defaultdict(list)
                for a, b in cells:
                    rc = cell(rule, content, a, b)
                    v = None if rc is None else content[rc[0]][rc[1]] * f
                    if v is None or abs(v - value) > TOL_MM:
                        off[None if v is None else round(v, 3)].append(f"{a}–{b}")
                for v, pairs in off.items():
                    have_v = "no value" if v is None else f"{v:.3f} mm"
                    out.append(f"{what} {', '.join(pairs)}: EasyEDA {have_v} ({at}), the board file {value:.3f} mm "
                               f"({why[what]})")

    tracks = kind(conf, "Physics", "Track")
    cls_of = {n: c for c, members in want["classes"].items() for n in members}
    groups = defaultdict(list)                    # (class of the board file, EasyEDA's rule name) -> nets
    groups["", rule_of(tracks, "default")[0]] = []
    for net, e in sorted(nets.items()):
        groups[cls_of.get(net, ""), rule_of(tracks, e.get("Track"))[0]].append(net)
    for (cls, name), members in groups.items():
        w, rule = want["track"][cls], rule_of(tracks, name)[1]
        label = f"track {cls} ({shown(members)})" if cls else "track, nets without a class" + (
            f" ({len(members)}: {shown(members)})" if members else "")
        if rule is None:
            out.append(missing("Track", name, members))
            continue
        f = factor(rule)
        if f is None:
            out.append(f"Track '{name}': unit {rule.get('unit')!r} not understood")
            continue
        data = ((rule.get("form") or {}).get("data") or {}).values()
        mins = sorted({round(d["minValue"] * f, 3) for d in data if d.get("minValue") is not None
                       and abs(d["minValue"] * f - w) > TOL_MM})
        maxs = sorted({round(d["maxValue"] * f, 3) for d in data if d.get("maxValue") is not None
                       and d["maxValue"] * f < w - TOL_MM})
        if not data:
            out.append(f"{label}: Track '{name}' has no widths")
        for v in mins:
            out.append(f"{label}: EasyEDA min {v:.3f} mm (Track '{name}'), the board file {w:.3f} mm ({why[cls]})")
        for v in maxs:
            out.append(f"{label}: EasyEDA max {v:.3f} mm (Track '{name}'), below the board file's {w:.3f} mm "
                       f"({why[cls]})")

    d, drill = want["via"]
    for name, rule, members in used(kind(conf, "Physics", "Via Size"), nets, "Via Size"):
        if rule is None:
            out.append(missing("Via Size", name, members))
            continue
        f = factor(rule)
        if f is None:
            out.append(f"Via Size '{name}': unit {rule.get('unit')!r} not understood")
            continue
        form = rule.get("form") or {}
        get = {k: form.get(k) * f if isinstance(form.get(k), (int, float)) else None for k in
               ("viaOuterdiameterMin", "viaInnerdiameterMin", "viaOuterdiameterMax", "viaInnerdiameterMax")}
        lo_o, lo_i, hi_o, hi_i = get.values()
        if lo_o is None or lo_i is None or abs(lo_o - d) > TOL_MM or abs(lo_i - drill) > TOL_MM:
            have_v = "no value" if lo_o is None or lo_i is None else f"min Ø {lo_o:.3f} mm, drill {lo_i:.3f} mm"
            out.append(f"via: EasyEDA {have_v} (Via Size '{name}'), the board file Ø {d:.3f} mm, drill {drill:.3f} mm "
                       f"({why['via']})")
        if (hi_o is not None and hi_o < d - TOL_MM) or (hi_i is not None and hi_i < drill - TOL_MM):
            out.append(f"via: EasyEDA max Ø {hi_o:.3f} mm, drill {hi_i:.3f} mm (Via Size '{name}'), below the board "
                       f"file's Ø {d:.3f} mm, drill {drill:.3f} mm ({why['via']})")

    have_cls = {c.get("name"): set(c.get("nets") or []) for c in have.get("net_classes") or []}
    for name, members in want["classes"].items():
        members = set(members) & set(nets)       # a net the PCB does not have needs no rule
        if not members:
            continue
        if name not in have_cls:
            out.append(f"class {name} ({shown(sorted(members))}): in [routing.classes], not among EasyEDA's net "
                       "classes")
            continue
        if lacks := sorted(members - have_cls[name]):
            out.append(f"class {name}: EasyEDA's lacks {shown(lacks)}")
        if extra := sorted(have_cls[name] - members):
            out.append(f"class {name}: EasyEDA's has {shown(extra)} too")
    for name in sorted(set(have_cls) - set(want["classes"]), key=str):
        out.append(f"class {name} ({shown(sorted(have_cls[name]))}): EasyEDA's net class, not in [routing.classes]")
    return out


def name_of(have):
    return (have.get("configuration") or {}).get("name") or "?"


def verdict(board, path):
    """L-3 with [routing] drc_rules: (ok, actual, expected) of the row "EasyEDA's DRC rule set = [routing] of the board
    file", from drc_rules.json of the run (path)."""
    want = wanted(board)
    expected = summary(want)
    if not path.exists():
        return False, f"{path.name} missing (edakit fab without --offline reads it with the DRC)", expected
    have = json.loads(path.read_text())
    if have.get("error"):
        return False, f"not read: {have['error']}", expected
    if "[MaxDepth]" in json.dumps(have):
        return False, ("cut off at [MaxDepth] – the rule set needs the bridge's return depth 12 "
                       "(edakit/easyeda/bridge-extension-patch.sh)"), expected
    diff = differences(want, have)
    return not diff, f"rule set '{name_of(have)}': " + ("; ".join(diff) if diff else "the board file's"), expected


# --- writing: what eda.write_drc_rules sends – not run against EasyEDA yet (the live probe of step 2.2) -------------

def class_changes(want, have):
    """The calls that make EasyEDA's net classes those of [routing.classes], for the nets the PCB has (createNetClass
    fails as soon as one is missing, handbook 9.4): [(PCB_Drc method, *args)] – removals first, so that a net is out of
    its old class before it joins a new one."""
    pcb = set(nets_of(have.get("net_rules")))
    have_cls = {c.get("name"): set(c.get("nets") or []) for c in have.get("net_classes") or []}
    first, then = [], []
    for name in sorted(set(have_cls) - set(want["classes"]), key=str):
        first.append(("deleteNetClass", name))
    for name, members in want["classes"].items():
        members = set(members) & pcb
        if name not in have_cls:
            if members:
                then.append(("createNetClass", name, sorted(members), None))
            continue
        if extra := sorted(have_cls[name] - members):
            first.append(("removeNetFromNetClass", name, extra))
        if lacks := sorted(members - have_cls[name]):
            then.append(("addNetToNetClass", name, lacks))
    return first + then


def width_entry(w, old=None):
    """A Track rule's entry of one layer with the least width w (in the rule's unit): min and the width a new track
    gets, the max kept unless it is narrower."""
    old = old or {}
    return {**old, "minValue": w, "defaultValue": w, "maxValue": max(old.get("maxValue") or 0, w)}


def config_for(want, configuration):
    """The rule configuration to write – overwriteCurrentRuleConfiguration takes the inner "config" that
    getCurrentRuleConfiguration returns: EasyEDA's own, with the board file's values in the default rules (the clearance
    and edge cells of every table of Safe Spacing; the least width and the width of a new track of Track; the least via
    and the size of a new one of Via Size), and a Track rule in mm per class of [routing.classes], named after it, with
    an entry per copper layer. Every other rule stays as it was."""
    conf = copy.deepcopy(configuration["config"])
    spacing = rule_of(kind(conf, "Spacing", "Safe Spacing"), "default")[1]
    track = rule_of(kind(conf, "Physics", "Track"), "default")[1]
    via = rule_of(kind(conf, "Physics", "Via Size"), "default")[1]
    if spacing is None or track is None or via is None:
        raise ValueError("EasyEDA's rule configuration lacks a default rule of Safe Spacing, Track or Via Size")
    if None in (factor(spacing), factor(track), factor(via)):
        raise ValueError("a default rule of EasyEDA's configuration has a unit edakit does not know")
    f = factor(spacing)
    for table in (spacing.get("tables") or {}).values():
        content = table["content"]
        for cells, value in ((CLEARANCE_CELLS, want["clearance"]), (EDGE_CELLS, want["edge"])):
            for a, b in cells:
                if (rc := cell(spacing, content, a, b)) is None:
                    raise ValueError(f"EasyEDA's Safe Spacing table has no value for {a}–{b}")
                content[rc[0]][rc[1]] = value / f
    f = factor(track)
    data = track.setdefault("form", {}).setdefault("data", {})
    widest = max((e.get("maxValue") or 0) * f for e in data.values()) if data else 0     # mm
    for key, entry in data.items():
        data[key] = width_entry(want["track"][""] / f, entry)
    tracks = conf["Physics"]["Track"]
    for cls, w in want["track"].items():
        if cls:
            tracks[cls] = {"editName": cls, "unit": "mm", "isSetDefault": False,
                           "form": {"status": 1, "data": {k: width_entry(w, {"maxValue": widest}) for k in LAYERS}}}
    f = factor(via)
    form = via.setdefault("form", {})
    for part, value in (("Outer", want["via"][0]), ("Inner", want["via"][1])):
        form[f"via{part}diameterMin"] = form[f"via{part}diameterDefault"] = value / f
        form[f"via{part}diameterMax"] = max(form.get(f"via{part}diameterMax") or 0, value / f)
    return conf


def net_rules_for(want, net_rules):
    """The net rules to write (overwriteNetRules): EasyEDA's, with every class and net on the default Safe Spacing and
    Via Size – the board file has one clearance and one via – and on the Track rule of its class of [routing.classes],
    the default without one. EasyEDA's classes are the board file's by then (class_changes)."""
    cls_of = {n: c for c, members in want["classes"].items() for n in members}
    out = copy.deepcopy(net_rules)
    for e in out:
        nets = [e] if e.get("type") == "net" else e.get("sub") or []
        if e.get("type") == "netClass":
            e.update({"Track": e.get("name") if e.get("name") in want["classes"] else "default",
                      "Safe Spacing": "default", "Via Size": "default"})
        for n in nets:
            n.update({"Track": cls_of.get(n.get("name"), "default"), "Safe Spacing": "default", "Via Size": "default"})
    return out
