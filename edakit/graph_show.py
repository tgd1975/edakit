"""What the graph says about one part or one net, and what edakit check finds on it (maker-coverage FT-23).

    edakit graph show NAME [--json FILE]

NAME is a designator (U1) or a net name (LED_CLK). For a part: type, board, label, LCSC number or part number, its
parts entry (key, kind, value, the limits and values it gives), every pin with its name, role and net, the accepts of
the component; for a net: its voltage range, fn, accepts, the cables that carry it, every pin on it with the part's
kind and the pin's role. Then the findings of `edakit check` on it – those whose place is NAME or whose accept may sit
on it. Read-only; an exact name, a designator before a net of the same name.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .design import Design, natural_key


def findings_on(report, name, kind):
    """The findings of a report whose place is name or that name it as where an accept may sit."""
    out = []
    for f in report.findings:
        if f.place == name or (kind, name) in tuple(f.on) or f.text.startswith((f"{name}:", f"{name} ")):
            out.append(f)
    return out


def part_view(design, des):
    c = design.comps[des]
    entry = design.part(des) or {}
    pins = []
    for num, p in sorted((entry.get("pins") or {}).items(), key=lambda x: natural_key(x[0])):
        pins.append({"pin": num, "name": p.get("name", ""), "role": p.get("role", ""),
                     "net": design.pin_net.get(f"{des}.{num}") or ("nc" if num in (c.get("nc") or []) else "")})
    if not pins:      # no entry: the graph's own pin names
        pins = [{"pin": num, "name": name, "role": "", "net": design.pin_net.get(f"{des}.{num}", "")}
                for num, name in sorted((c.get("pins") or {}).items(), key=lambda x: natural_key(x[0]))]
    return {"designator": des, "type": c.get("type", ""), "board": c.get("board") or "", "label": c.get("label", ""),
            "lcsc": c.get("lcsc", ""), "part": c.get("part", ""), "bom": c.get("bom", True),
            "entry": design.entry_key(des) or "", "kind": entry.get("kind", ""),
            "value": c.get("value") or entry.get("value", ""), "limits": entry.get("limits") or {},
            "values": entry.get("values") or {}, "pins": pins, "accept": c.get("accept") or {}}


def net_view(design, name):
    n = design.nets[name]
    pins = []
    for ref in sorted(n["pins"], key=natural_key):
        des, _, num = ref.partition(".")
        info = design.pin_info(ref)
        pins.append({"pin": ref, "kind": (design.part(des) or {}).get("kind") or design.comps[des].get("type", ""),
                     "name": info.get("name", ""), "role": info.get("role", "")})
    cables = [w.get("name", "") for w in design.graph.get("cables") or []
              if any(f"{w.get('from')}.{a}" in n["pins"] or f"{w.get('to')}.{b}" in n["pins"]
                     for a, b in (w.get("pins") or {}).items())]
    return {"net": name, "v": n.get("v"), "fn": n.get("fn", ""), "notes": n.get("notes", ""),
            "accept": n.get("accept") or {}, "cables": cables, "pins": pins,
            "ground": name == design.ground, "matrix": n.get("matrix", "")}


def text(view, found):
    lines = []
    if "designator" in view:
        v = view
        what = " ".join(x for x in (v["type"], f"on {v['board']}" if v["board"] else "", f"– {v['label']}"
                                    if v["label"] else "") if x)
        lines.append(f"{v['designator']}  {what}")
        ident = v["lcsc"] or v["part"] or "no part number"
        lines.append(f"  part      {ident}" + (f", entry {v['entry']} ({v['kind']})" if v["entry"] else
                                               ", no parts entry") + ("" if v["bom"] else ", bom: false"))
        if v["value"]:
            lines.append(f"  value     {v['value']}")
        for key in ("limits", "values"):
            if v[key]:
                lines.append(f"  {key:<9} " + ", ".join(f"{k} = {x}" for k, x in v[key].items()))
        lines.append("  pins")
        lines += [f"    {p['pin']:<4} {p['name']:<12} {p['role']:<10} {p['net']}" for p in v["pins"]]
    else:
        v = view
        rng = f"{v['v'][0]:g} … {v['v'][1]:g} V" if isinstance(v.get("v"), list) and len(v["v"]) == 2 else "no range"
        extra = ", ".join(x for x in (f"fn {v['fn']}" if v["fn"] else "", "ground" if v["ground"] else "",
                                      f"matrix {v['matrix']}" if v["matrix"] else "",
                                      f"cables {', '.join(v['cables'])}" if v["cables"] else "") if x)
        lines.append(f"{v['net']}  {rng}" + (f"  ({extra})" if extra else ""))
        if v["notes"]:
            lines.append(f"  notes     {v['notes']}")
        lines.append("  pins")
        lines += [f"    {p['pin']:<8} {p['kind']:<14} {p['name']:<12} {p['role']}" for p in v["pins"]]
    for k, reason in (view.get("accept") or {}).items():
        lines.append(f"  accept    {k}: {reason}")
    if found:
        lines.append(f"  findings  {len(found)}")
        lines += [f"    {f.severity:<8} {f.code}{'/' + f.grade if f.grade else ''}  {f.text}"
                  + (f"  (accepted: {f.accepted})" if f.accepted else "") for f in found]
    else:
        lines.append("  findings  none")
    return "\n".join(lines)


def show(cfg, name):
    """(view, findings) of one part or net; KeyError when the graph has neither."""
    from . import engines
    design = Design.from_config(cfg)
    if name in design.comps:
        view, kind = part_view(design, name), "component"
    elif name in design.nets:
        view, kind = net_view(design, name), "net"
    else:
        raise KeyError(name)
    return view, findings_on(engines.run_all(design, cfg), name, kind)


def main(cfg, args):
    try:
        view, found = show(cfg, args.name)
    except KeyError:
        d = Design.from_config(cfg)
        near = [x for x in list(d.comps) + list(d.nets) if x.lower().startswith(args.name.lower()[:2])][:8]
        print(f"edakit graph show: no part or net {args.name} in the graph"
              + (f" – similar: {', '.join(near)}" if near else ""), file=sys.stderr)
        return 1
    print(text(view, found))
    if args.json:
        view = {**view, "findings": [{"code": f.code, "grade": f.grade, "severity": f.severity, "text": f.text,
                                      "accepted": f.accepted} for f in found]}
        Path(args.json).write_text(json.dumps(view, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0
