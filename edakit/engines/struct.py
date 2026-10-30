"""STRUCT: the graph is well-formed and names what exists (concept rules-at-scale.md, section 2).

Unique names (STRUCT.name), every pin in one net or nc (STRUCT.pin), nets with two pins, a range and copper between
boards (STRUCT.net), every part on a board (STRUCT.board), settings that name what exists (STRUCT.ref), the purpose
(STRUCT.purpose), pins where the firmware expects them (STRUCT.lock), the graph's pins = the parts entry
(STRUCT.entry), graph and entry naming the same part (STRUCT.identity, STRUCT.prefix).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .. import handover
from ..circuit import KINDS_OF_PREFIX, KINDS_OF_TYPE, PURPOSES, core_mpn, read_value, value_problem
from ..design import natural_key
from ..findings import Finding

LOCK_KEYS = ("pins", "doc_pin_table")


def run(ctx):
    d, cfg = ctx.design, ctx.cfg
    boards = set(cfg.boards) if cfg else set()
    bought = boards - set(cfg.made()) if cfg else set()
    return structure(d, boards, bought) + refs(d) + locks(d, ctx.root) + entries(d, cfg) + identity(d)


def structure(d, boards, bought=()):
    g, out = d.graph, []

    def add(code, place, text, on=()):
        out.append(Finding(code, "G", place, text, on=on))
    for des, n in Counter(c["designator"] for c in g["components"]).items():
        if n > 1:
            add("STRUCT.name", des, f"duplicate designator {des}")
    for name, n in Counter(n["name"] for n in g["nets"]).items():
        if n > 1:
            add("STRUCT.name", name, f"duplicate net {name}")
    used = Counter()
    for net in g["nets"]:
        if len(net["pins"]) < 2:
            add("STRUCT.net", net["name"], f"net {net['name']} has fewer than two pins", on=(("net", net["name"]),))
        for ref in net["pins"]:
            des, _, pin = ref.partition(".")
            if des not in d.comps:
                add("STRUCT.pin", ref, f"net {net['name']}: unknown component {des}")
            elif pin not in d.comps[des]["pins"]:
                add("STRUCT.pin", ref, f"net {net['name']}: {des} has no pin {pin}")
            used[ref] += 1
    for des, c in d.comps.items():
        nc = {str(p) for p in c.get("nc", [])}
        for pin in c["pins"]:
            ref = f"{des}.{pin}"
            if pin in nc and used[ref]:
                add("STRUCT.pin", ref, f"{ref} is marked nc but used in net {d.pin_net[ref]}")
            elif pin not in nc and used[ref] == 0:
                add("STRUCT.pin", ref, f"{ref} ({c['pins'][pin]}) is neither connected nor nc")
        for p in sorted(nc - set(c["pins"])):
            add("STRUCT.pin", f"{des}.{p}", f"{des}.{p} in nc but not a pin")
        if boards and c.get("board") not in boards:
            add("STRUCT.board", des, f"{des}: 'board' must be one of {sorted(boards)} (edakit.toml [boards])")
        if c.get("board") in bought and c.get("bom") is not False:
            add("STRUCT.board", des, f"{des}: on the bought board {c['board']} – nobody assembles it: bom: false")
    for ref, n in used.items():
        if n > 1:
            add("STRUCT.pin", ref, f"{ref} used in {n} nets")
    for net in g["nets"]:
        v = net.get("v")
        if not (isinstance(v, list) and len(v) == 2 and v[0] <= v[1]):
            add("STRUCT.net", net["name"], f"net {net['name']}: missing or invalid voltage range 'v'")
    cable_pins = set()
    for cab in g.get("cables", []):
        for a, b in cab["pins"].items():
            ref_a, ref_b = f"{cab['from']}.{a}", f"{cab['to']}.{b}"
            cable_pins |= {ref_a, ref_b}
            if d.pin_net.get(ref_a) != d.pin_net.get(ref_b):
                add("STRUCT.net", f"cable {cab['name']}", f"cable {cab['name']}: {ref_a} and {ref_b} are on different nets")
    for net in g["nets"]:
        on = {d.comps[r.partition(".")[0]].get("board") for r in net["pins"] if r.partition(".")[0] in d.comps}
        if len(on) > 1 and not cable_pins & set(net["pins"]):
            add("STRUCT.net", net["name"], f"net {net['name']} spans several boards without a cable")
    for problem in handover.problems(d):
        add("STRUCT.ref", "layout", problem)
    if "purpose" in g and (g["purpose"] or {}).get("use") not in PURPOSES:
        add("STRUCT.purpose", "purpose.use", f"purpose.use must be one of {', '.join(PURPOSES)} – the regulatory review "
                                             "(M-6) starts there")
    return out


def refs(d):
    """STRUCT.ref: the ground net and the settings of the graph name what it has."""
    g, out = d.graph, []

    def add(place, text):
        out.append(Finding("STRUCT.ref", "G", place, text))
    if "ground" in g and g["ground"] not in d.nets:
        add("ground", f"ground: no net {g['ground']} in the graph")
    left = g.get("checks") or {}
    for k in left:
        if k != "reverse_protect":
            add("checks", f"checks: unknown key '{k}' (the graph's settings: locks.{', locks.'.join(LOCK_KEYS)}, "
                          "\"source\": \"reversible\" on a component)")
    for des in left.get("reverse_protect") or []:
        add("checks.reverse_protect", f"checks.reverse_protect: no part {des} in the graph")
    lk = g.get("locks") or {}
    for k in lk:
        if k not in LOCK_KEYS:
            add("locks", f"locks: unknown key '{k}' (known: {', '.join(LOCK_KEYS)})")
    for ref in lk.get("pins") or {}:
        if ref.partition(".")[0] not in d.comps:
            add("locks.pins", f"locks.pins: no part {ref.partition('.')[0]} in the graph")
    if (t := lk.get("doc_pin_table")) and t.get("component") not in d.comps:
        add("locks.doc_pin_table", f"locks.doc_pin_table: no part {t.get('component')} in the graph")
    return out


def locks(d, root):
    """STRUCT.lock: every pin of locks.pins on its net; the pin table of a document lists the connected pins."""
    lk, out = d.graph.get("locks") or {}, []

    def add(place, text):
        out.append(Finding("STRUCT.lock", "G", place, text))
    for ref, net in (lk.get("pins") or {}).items():
        if d.pin_net.get(ref) != net:
            add(ref, f"{ref} expected on net {net}, found {d.pin_net.get(ref)}")
    table = lk.get("doc_pin_table")
    if not table or table.get("component") not in d.comps:
        return out
    doc = Path(root) / table["file"]
    comp, prefix = table["component"], table.get("prefix", "GP")
    regex = re.compile(table.get("regex", r"^\|.*?\|\s*\*\*" + re.escape(prefix) + r"(\d+)"), re.M)
    used = {int(m.group(1)) for num, name in d.comps[comp]["pins"].items()
            if (m := re.match(re.escape(prefix) + r"(\d+)", name)) and f"{comp}.{num}" in d.pin_net}
    if not doc.exists():
        add(table["file"], f"pin table {table['file']} not found")
        return out
    listed = {int(n) for n in regex.findall(doc.read_text(encoding="utf-8"))}
    for n in sorted(used - listed):
        add(f"{prefix}{n}", f"{prefix}{n} is connected in the graph but missing in the pin table of {table['file']}")
    for n in sorted(listed - used):
        add(f"{prefix}{n}", f"{prefix}{n} is in the pin table of {table['file']} but not connected in the graph")
    return out


def entries(d, cfg=None):
    """STRUCT.entry: an entry for every part, its pins = the graph's (and = the library symbol where cached), no
    supply pin in nc."""
    from .. import part as parts
    from ..footprint import own_symbol
    from ..schematic import pin_differences
    out = []
    for des, c in d.comps.items():
        if not c.get("lcsc") and not c.get("part"):
            continue
        on = (("component", des),)
        symbol = parts.cached(cfg, c.get("lcsc")) if cfg else None
        if symbol and own_symbol(d.part(des)):
            symbol = None
        if symbol and (diffs := pin_differences(symbol["pins"], c["pins"])):
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: pins differ from the library symbol of {c['lcsc']} "
                               f"({cfg.relative(parts.library_file(cfg, c['lcsc']))}): {'; '.join(diffs)}", on=on))
        part = d.part(des)
        if not part:
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: no parts entry " + (f"{c['lcsc']}.json" if c.get("lcsc")
                                                                            else f"with mpn {c['part']}")))
            continue
        want = {k: v["name"] for k, v in part["pins"].items()}
        if c["pins"] != want:
            only_g = {k: v for k, v in c["pins"].items() if want.get(k) != v}
            only_p = {k: v for k, v in want.items() if c["pins"].get(k) != v}
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: pins differ from parts entry {d.entry_key(des)}: graph "
                               f"{only_g} vs parts {only_p}"))
        for pin in c.get("nc", []):
            if part["pins"].get(str(pin), {}).get("type") == "power_in":
                out.append(Finding("STRUCT.entry", "P", f"{des}.{pin}", f"{des}.{pin} ({part['pins'][str(pin)]['name']}) "
                                   "is a supply pin but marked nc", on=on))
    return out


def identity(d):
    """STRUCT.identity: the component and its parts entry name the same part; STRUCT.prefix: the designator's letters
    fit the entry's kind."""
    out, users = [], defaultdict(list)
    for des in sorted(d.comps, key=natural_key):
        if (key := d.entry_key(des)) is not None:
            users[key].append(des)
    for key, dess in sorted(users.items()):
        lcsc = d.parts[key].get("lcsc")
        if lcsc and lcsc != key:
            out.append(Finding("STRUCT.identity", "P", f"{key}.json", f"{key}.json: lcsc {lcsc} – the file is named {key} "
                               f"({', '.join(dess)})"))
    for key, dess in users.items():
        part = d.parts[key]
        for des in dess:
            c, on = d.comps[des], (("component", des),)

            def add(text):
                out.append(Finding("STRUCT.identity", "P", des, f"{des}: {text}", on=on))
            if str(c.get("lcsc") or "").startswith("C99") and c.get("bom") is not False:
                add(f"lcsc {c['lcsc']} is a part of an EasyEDA user library – nobody sells it (handbook 4.2)")
            mpn = core_mpn(part.get("mpn") or "")
            if c.get("part") and mpn:
                if read_value(c["part"]):
                    if problem := value_problem(c["part"], part, key, "part"):
                        add(problem)
                elif not re.search(r"(?<![A-Za-z0-9])" + re.escape(mpn).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9])",
                                   c["part"], re.I):
                    add(f"part {c['part']} does not name {mpn}, the mpn of parts entry {key}")
            if c.get("value") not in (None, "") and (problem := value_problem(c["value"], part, key, "value")):
                add(problem)
            kind = part.get("kind")
            if not kind:
                continue
            if c.get("type") and kind not in KINDS_OF_TYPE.get(c["type"], (c["type"],)):
                add(f"type {c['type']} does not fit kind {kind} of parts entry {key}")
            prefix = re.match(r"[A-Za-z]*", des).group(0).upper()
            if prefix in KINDS_OF_PREFIX and kind not in KINDS_OF_PREFIX[prefix]:
                usual = next((p for p, kinds in KINDS_OF_PREFIX.items() if kind in kinds), None)
                out.append(Finding("STRUCT.prefix", "P", des, f"{des}: designator prefix {prefix}, but parts entry {key} is a "
                                   f"{kind}" + (f" ({usual})" if usual else "")))
    return out
