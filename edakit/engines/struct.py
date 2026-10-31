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
from ..circuit import (KINDS_OF_PREFIX, KINDS_OF_TYPE, PURPOSES, cable_problems, core_mpn, read_value, strip_problems,
                       value_problem)
from ..design import natural_key
from ..findings import Finding

LOCK_KEYS = ("pins", "doc_pin_table")


def run(ctx):
    d, cfg = ctx.design, ctx.cfg
    boards = set(cfg.boards) if cfg else set()
    unmade = {name: b.unmade for name, b in cfg.boards.items() if b.unmade} if cfg else {}
    return (structure(d, boards, unmade) + bought_panels(d, cfg) + refs(d) + locks(d, ctx.root) + entries(d, cfg)
            + configs_named(d) + states_named(d) + identity(d))


NOBODY = {"bought": "nobody assembles it", "hand-wired": "wired by hand, no assembler"}


def structure(d, boards, unmade=None):
    """unmade: {board: "bought" | "hand-wired"} – the boards nobody draws or assembles, whose parts have bom: false."""
    g, out, unmade = d.graph, [], unmade or {}

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
                add("STRUCT.pin", ref, f"net {net['name']}: {ref} names no pin of {des}")
            used[ref] += 1
    for des, c in d.comps.items():
        nc = {str(p) for p in c.get("nc", [])}
        for pin in c["pins"]:
            ref = f"{des}.{pin}"
            if pin in nc and used[ref]:
                add("STRUCT.pin", ref, f"{d.pin_text(ref)} is marked nc but used in net {d.pin_net[ref]}")
            elif pin not in nc and used[ref] == 0:
                add("STRUCT.pin", ref, f"{d.pin_text(ref)} is neither connected nor nc")
        for p in sorted(nc - set(c["pins"])):
            add("STRUCT.pin", f"{des}.{p}", f"{des}.{p} in nc but not a pin")
        if boards and c.get("board") not in boards:
            add("STRUCT.board", des, f"{des}: 'board' must be one of {sorted(boards)} (edakit.toml [boards])")
        if c.get("board") in unmade and c.get("bom") is not False:
            what = unmade[c["board"]]
            add("STRUCT.board", des, f"{des}: on the {what} board {c['board']} – {NOBODY[what]}: bom: false")
    for ref, n in used.items():
        if n > 1:
            add("STRUCT.pin", ref, f"{d.pin_text(ref)} used in {n} nets")
    unknown = set()
    for where, ref, why in getattr(d, "unresolved", ()):      # a pin word of locks.pins, layout.loops or a cable
        add("STRUCT.pin", ref, f"{where}: {why}")
        unknown.add(ref)
    for net in g["nets"]:
        v = net.get("v")
        if not (isinstance(v, list) and len(v) == 2 and v[0] <= v[1]):
            add("STRUCT.net", net["name"], f"net {net['name']}: missing or invalid voltage range 'v'")
    cable_pins = set()
    for cab in g.get("cables", []):
        for problem in cable_problems(cab):
            add("STRUCT.net", f"cable {cab.get('name')}", f"cable {cab.get('name')}: {problem}")
        if "at_m" in cab and not any((d.part(x) or {}).get("kind") == "led_strip" for x in (cab.get("from"), cab.get("to"))
                                     if x in d.comps):
            add("STRUCT.net", f"cable {cab.get('name')}", f"cable {cab.get('name')}: at_m – the place along an LED strip "
                                                          "its wires land, but neither end is an LED strip")
        for a, b in cab["pins"].items():
            ref_a, ref_b = f"{cab['from']}.{a}", f"{cab['to']}.{b}"
            cable_pins |= {ref_a, ref_b}
            if d.pin_net.get(ref_a) != d.pin_net.get(ref_b) and not {ref_a, ref_b} & unknown:
                add("STRUCT.net", f"cable {cab['name']}", f"cable {cab['name']}: {d.pin_text(ref_a)} and "
                                                          f"{d.pin_text(ref_b)} are on different nets")
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


def bought_panels(d, cfg):
    """STRUCT.board/wired (a note): a bought board none of whose parts is a module – parts wired by hand rather than
    one purchased assembly, which wired = true says (maker-coverage FT-2, rules-at-scale.md decision 22). bought = true
    keeps working for it; the note only names the key."""
    out = []
    for name, b in (cfg.boards.items() if cfg else ()):
        mine = [des for des, c in d.comps.items() if c.get("board") == name]
        if b.bought and mine and not any(d.comps[des].get("type") == "module" or (d.part(des) or {}).get("kind")
                                         == "module" for des in mine):
            out.append(Finding("STRUCT.board", "G", f"[boards.{name}]", f"[boards.{name}]: bought = true, but no part "
                               "on it is a bought module – a board of parts wired by hand says so with wired = true "
                               "(handbook 4.5)", grade="wired"))
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
    unknown = {ref for _, ref, _ in getattr(d, "unresolved", ())}     # STRUCT.pin's
    for ref, net in (lk.get("pins") or {}).items():
        if d.pin_net.get(ref) != net and ref not in unknown:
            add(ref, f"{d.pin_text(ref)} expected on net {net}, found {d.pin_net.get(ref)}")
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


def symbol_structure(cfg, symbol, entry):
    """[(pin numbers involved, text)]: what a cached library symbol does beyond its pin names that a schematic drawn
    from it would wire wrongly – a number it gives to two pins (they join on one pad), a pad of its footprint it has no
    pin for (left unconnected), a pin without a pad. Names and numbers on one side only are pin_differences' (against
    the graph's pins)."""
    from .. import part as parts
    norm = lambda t: "".join(str(t).split()).upper()  # noqa: E731
    names = {n: norm(p.get("name", "")) for n, p in (entry.get("pins") or {}).items()}
    out = []
    for num, dup in (symbol.get("duplicate_pins") or {}).items():
        others = {norm(x) for x in dup} - {names.get(num)}           # the pins the symbol numbers wrongly
        pins = {num} | {n for n, name in names.items() if name in others}
        out.append((pins, f"numbers {len(dup)} pins {num} ({', '.join(dup)}) – a schematic drawn from it joins them on "
                          f"pad {num}"))
    footprint = parts.cached_footprint(cfg, symbol.get("footprint"))
    if footprint:
        pads, have, fp = set(footprint.get("pads") or {}), set(symbol.get("pins") or {}), symbol.get("footprint")
        for n in sorted(pads - have, key=natural_key):
            if n in names:
                text = (f"has no pin for pad {n} of its footprint {fp} – a schematic drawn from it leaves pad {n} "
                        f"({entry['pins'][n].get('name', n)}) unconnected")
            else:
                text = (f"has no pin for pad {n} of its footprint {fp}, nor has the parts entry – a schematic drawn from "
                        "it leaves the pad unconnected")
            out.append(({n}, text))
        for n in sorted(have - pads, key=natural_key):
            out.append(({n}, f"has pin {n} ({symbol['pins'][n]}) without a pad in its footprint {fp}"))
    return out


def entries(d, cfg=None):
    """STRUCT.entry: an entry for every part, its pins = the graph's (and = the library symbol where cached – names
    and numbers; grade symbol: a number the symbol gives twice, a pad of its footprint without a pin), no supply pin in
    nc. Pins the entry's symbol_differs names follow the datasheet on purpose: left out of the comparison with the
    symbol and named in a note (grade declared)."""
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
        declared = {str(k): v for k, v in ((d.part(des) or {}).get("symbol_differs") or {}).items()}
        if symbol:
            where = cfg.relative(parts.library_file(cfg, c["lcsc"]))
            mine = {n: v for n, v in symbol["pins"].items() if n not in declared}
            if diffs := pin_differences(mine, {n: v for n, v in c["pins"].items() if n not in declared}):
                out.append(Finding("STRUCT.entry", "P", des, f"{des}: pins differ from the library symbol of {c['lcsc']} "
                                   f"({where}): {'; '.join(diffs)}", on=on))
            if odd := [t for pins, t in symbol_structure(cfg, symbol, d.part(des) or {}) if not pins <= set(declared)]:
                out.append(Finding("STRUCT.entry", "P", des, f"{des}: the library symbol of {c['lcsc']} ({where}) "
                                   + "; ".join(odd), grade="symbol", on=on))
        if declared:
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: the parts entry follows the datasheet where the library "
                               f"symbol of {c.get('lcsc') or c.get('part')} differs – "
                               + "; ".join(f"pin {n}: {why}" for n, why in sorted(declared.items(),
                                                                               key=lambda kv: natural_key(kv[0])))
                               + " – a schematic drawn from that symbol wires these pins otherwise", grade="declared",
                               on=on))
        part = d.part(des)
        if not part:
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: no parts entry " + (f"{c['lcsc']}.json" if c.get("lcsc")
                                                                            else f"with mpn {c['part']}")))
            continue
        want = {k: v["name"] for k, v in part["pins"].items()}
        if des not in d.entry_maps and c["pins"] != want:        # a map taken from the entry has nothing to compare
            only_g = {k: v for k, v in c["pins"].items() if want.get(k) != v}
            only_p = {k: v for k, v in want.items() if c["pins"].get(k) != v}
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: pins differ from parts entry {d.entry_key(des)}: graph "
                               f"{only_g} vs parts {only_p}"))
        for pin in c.get("nc", []):
            if part["pins"].get(str(pin), {}).get("type") == "power_in":
                out.append(Finding("STRUCT.entry", "P", f"{des}.{pin}", f"{d.pin_text(f'{des}.{pin}')} is a supply pin "
                                   "but marked nc", on=on))
        if part.get("kind") == "led_strip":       # its length (sim/strip.py)
            out += [Finding("STRUCT.entry", "P", des, f"{des}: {p}", grade="strip", on=on) for p in strip_problems(c)]
    return out


def configs_named(d):
    """STRUCT.entry: a component's `config` is one of its parts entry's `configs` (handbook 4.1) – a config the entry
    does not know would leave the component on the entry's own values without anyone noticing."""
    out = []
    for des, c in sorted(d.comps.items(), key=lambda x: natural_key(x[0])):
        key = d.entry_key(des)
        if not c.get("config") or key is None:
            continue
        known = sorted(d.parts[key].get("configs") or {})
        if c["config"] not in known:
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: config {c['config']!r} – parts entry {key} knows "
                               + (", ".join(known) if known else "no configs"), on=(("component", des),)))
    return out


def states_named(d):
    """STRUCT.entry: a component's `states` – where behaviour logic holds its outputs in the simulation (handbook
    3.1) – name output or bidirectional pins of its entry, by number or name, each with high, low or off; an
    open-drain output cannot drive high. A state that names nothing would leave the pin at its default unnoticed."""
    from ..schema import STATES
    out = []
    for des, c in sorted(d.comps.items(), key=lambda x: natural_key(x[0])):
        given, part = c.get("states"), d.part(des)
        if given is None or part is None:
            continue
        on = (("component", des),)
        if not isinstance(given, dict):
            out.append(Finding("STRUCT.entry", "P", des, f"{des}: states {given!r} – {{pin: high | low | off}}", on=on))
            continue
        pins = part.get("pins") or {}
        for key, word in given.items():
            num = key if key in pins else next((n for n, p in pins.items() if p.get("name") == key), None)
            info = pins.get(num) or {}
            text = (f"states {key} – parts entry {d.entry_key(des)} has no such pin" if num is None else
                    f"states {key} {word!r} – high, low or off" if word not in STATES else
                    f"states {key} – pin {num} ({info.get('name', num)}) is no output"
                    if info.get("type") not in ("output", "bidirectional") else
                    f"states {key} 'high' – an open-drain output cannot drive high (low or off)"
                    if word == "high" and info.get("drive") == "open_drain" else None)
            if text:
                out.append(Finding("STRUCT.entry", "P", des, f"{des}: {text}", on=on))
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
