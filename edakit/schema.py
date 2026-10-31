"""The parts schema (catalog/kinds.toml) and `edakit part lint`: every parts entry held to the schema of its kind.

    edakit part lint [KEY ...]

Every name of limits, values and pins ends in its unit and is one the kind knows (or every kind: [common]); a number
where a unit says so, min <= max for a quantity with both, an enum's word, a pin type and – where the kind lists
them – a role it knows. An entry still in the form of before (ratings, params, vmax …) is named once: `edakit
convert` converts it. Each problem is a finding PARTS.schema with the entry's key as its place. Exit code 2 on
findings.
"""

from __future__ import annotations

import re
import tomllib
from functools import lru_cache

from . import catalog
from .findings import Finding

BOUND = re.compile(r"(.+)_(max|min)_([a-z_]+)$")
OLD_KEYS = ("ratings", "params")


@lru_cache(maxsize=1)
def kinds():
    return tomllib.loads((catalog.HERE / "kinds.toml").read_text(encoding="utf-8"))


def unit_of(name):
    """The unit suffix a name ends in ('vr_max_v' -> 'v', 'rth_ja_k_per_w' -> 'k_per_w'), or None."""
    for u in sorted(kinds()["units"], key=len, reverse=True):
        if name.endswith("_" + u):
            return u
    return None


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def numeric(x):
    """A value in a unit: a number, a list of them ([min, typ, max], null where the datasheet gives none) or a table
    of them by condition ({"-4.5": 0.06} – RDS(on) by VGS)."""
    if isinstance(x, list):
        return bool(x) and all(is_number(v) or v is None for v in x)
    if isinstance(x, dict):
        return bool(x) and all(is_number(v) for v in x.values())
    return is_number(x)


def allowed(kind, section):
    k = kinds()
    return set(k["common"].get(section, [])) | set((k["kinds"].get(kind) or {}).get(section, []))


def field_problems(kind, section, table, where):
    """Problems of one table of limits or values (per colour: the colour's own table)."""
    k, out = kinds(), []
    names = allowed(kind, section)
    per_color = (k["kinds"].get(kind) or {}).get("per_color", [])
    for name, v in (table or {}).items():
        at = f"{where}.{name}"
        if name in per_color and isinstance(v, dict):
            out += field_problems(kind, section, v, at)
            continue
        if name not in names and name not in k["free"].get(section, []):
            out.append(f"{at}: not a {section[:-1]} of kind {kind}" + _near(name, names))
            continue
        if name in k["enums"]:
            if v not in k["enums"][name] and not (name == "behavior" and isinstance(v, str)):   # plugin models
                out.append(f"{at}: {v!r} – one of {', '.join(k['enums'][name])}")
        elif name in k["free"].get(section, []):
            continue
        elif unit_of(name) and not numeric(v) and v is not None:
            out.append(f"{at}: {v!r} is no number in {k['units'][unit_of(name)]}")
    for name, v in (table or {}).items():
        m = BOUND.match(name)
        if m and m[2] == "min" and is_number(v):
            hi = (table or {}).get(f"{m[1]}_max_{m[3]}")
            if is_number(hi) and v > hi:
                out.append(f"{where}: {name} {v} above {m[1]}_max_{m[3]} {hi}")
    return out


def _near(name, names):
    stem = name.split("_")[0]
    near = sorted(n for n in names if n.split("_")[0] == stem)
    return f" (known: {', '.join(near)})" if near else ""


def problems(entry):
    """[text] for one parts entry."""
    k, out = kinds(), []
    kind = entry.get("kind")
    if kind not in k["kinds"]:
        return [f"kind: {kind!r} – one of {', '.join(k['kinds'])}"]
    if any(key in entry for key in OLD_KEYS) or any("vmax" in (p or {}) for p in (entry.get("pins") or {}).values()):
        return ["the form of before (ratings, params, vmax …) – edakit convert converts it"]
    for section in ("limits", "values"):
        out += field_problems(kind, section, entry.get(section), section)
    if "antenna" in entry:
        box = (entry["antenna"] or {}).get("keepout_mm") if isinstance(entry["antenna"], dict) else None
        if not (isinstance(box, list) and len(box) == 4 and all(is_number(x) for x in box)
                and box[0] < box[2] and box[1] < box[3]):
            out.append("antenna.keepout_mm: [x0, y0, x1, y1] in mm with x0 < x1 and y0 < y1 (the footprint's frame)")
    out += supply_order_problems(entry) + group_problems(entry)
    roles = (k["kinds"][kind]).get("roles", [])
    pin_names = allowed(kind, "pin") | set(k["free"]["pin"])
    for num, pin in (entry.get("pins") or {}).items():
        at = f"pins.{num}"
        if pin.get("type") not in k["pin_types"]["types"]:
            out.append(f"{at}.type: {pin.get('type')!r} – one of {', '.join(k['pin_types']['types'])}")
        if roles and "*" not in roles and pin.get("role") not in (None, *roles):
            out.append(f"{at}.role: {pin['role']!r} – kind {kind} knows {', '.join(roles)}")
        for name, v in pin.items():
            if name not in pin_names:
                out.append(f"{at}.{name}: not a pin field")
            elif unit_of(name) and not numeric(v) and not (name == "v_rel_max_v" and v is None):
                out.append(f"{at}.{name}: {v!r} is no number")
        names = {p.get("name") for p in (entry.get("pins") or {}).values()}
        if "ref" in pin and pin["ref"] not in names:
            out.append(f"{at}.ref: {pin['ref']!r} – the name of a pin of this part (the supply its relative limits and "
                       "threshold ratios refer to)")
        if pin.get("strap") not in (None, "high", "low"):
            out.append(f"{at}.strap: {pin['strap']!r} – high or low")
        if pin.get("pull") not in (None, "up", "down"):
            out.append(f"{at}.pull: {pin['pull']!r} – up or down")
        if pin.get("clamp") not in (None, "internal", "none"):
            out.append(f"{at}.clamp: {pin['clamp']!r} – internal or none (clamp diodes of the output's own)")
        ws = pin.get("windows")
        if ws is not None and not (isinstance(ws, list) and ws and all(
                isinstance(w, dict) and w.get("state") and set(w) <= {"state", "min_v", "max_v"}
                and any(k in w for k in ("min_v", "max_v")) and all(is_number(w[k]) for k in ("min_v", "max_v") if k in w)
                for w in ws)):
            out.append(f"{at}.windows: a list of {{state, min_v, max_v}} – the voltage windows the pin reads, each with "
                       "a state and at least one bound in V")
        lo, hi = pin.get("v_op_min_v"), pin.get("v_op_max_v")
        if is_number(lo) and is_number(hi) and lo > hi:
            out.append(f"{at}: v_op_min_v {lo} above v_op_max_v {hi}")
    return out


def supply_order_problems(entry):
    """supply_order: [[lower, higher], …] – pairs of pin names of the part."""
    order = entry.get("supply_order")
    if order is None:
        return []
    names = {p.get("name") for p in (entry.get("pins") or {}).values()}
    if not (isinstance(order, list) and order and all(isinstance(x, list) and len(x) == 2 for x in order)):
        return ["supply_order: [[lower pin, higher pin], …] – pin names, the first never above the second"]
    return [f"supply_order: {n!r} – no pin of this part has that name" for pair in order for n in pair if n not in names]


def group_problems(entry):
    """i_group_max_a: {group: {pins: [pin numbers], max: A}}."""
    groups = entry.get("i_group_max_a")
    if groups is None:
        return []
    pins = set((entry.get("pins") or {}))
    if not isinstance(groups, dict) or not groups:
        return ["i_group_max_a: {group: {pins = [numbers], max = A}} – the most current a group of pins carries"]
    out = []
    for name, g in groups.items():
        if not (isinstance(g, dict) and isinstance(g.get("pins"), list) and g["pins"] and is_number(g.get("max"))):
            out.append(f"i_group_max_a.{name}: {{pins = [numbers], max = A}}")
            continue
        out += [f"i_group_max_a.{name}: pin {n!r} – not a pin of this part" for n in g["pins"] if str(n) not in pins]
    return out


def lint(parts, keys=None):
    """PARTS.schema findings for the entries (all, or those of `keys`)."""
    return [Finding("PARTS.schema", "P", key, text) for key in sorted(keys or parts) if key in parts
            for text in problems(parts[key])]


def main_lint(cfg, args):
    from .design import load_parts
    from .findings import Report, format_findings
    parts = load_parts(cfg.parts)
    keys = [args.source, *([args.new] if args.new else [])] if args.source else None
    unknown = [k for k in keys or [] if k not in parts]
    rep = Report(lint(parts, keys)).resolve()
    print("\n".join(format_findings(rep.findings, shown=50)) or "every entry fits the schema of its kind")
    for k in unknown:
        print(f"{k}: no parts entry")
    print(f"{len(keys or parts) - len(unknown)} entries, {len(rep.findings)} problems")
    return 2 if rep.findings else (1 if unknown else 0)
