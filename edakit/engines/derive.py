"""DEF: every derived value is the value its record derives (circuit-dsl-language.md section 7, T.8). The engine
reads the graph's `derivations` – records the compiler of the circuit language and `edakit block add --set` write –
and compares numbers only; it never evaluates a rule.

    DEF.derive          a part's value outside its record's window – another part of the series, or accept with the
                        reason
    DEF.derive/inputs   a number of the record's inputs is not what its source says now – an entry's vf_typ_v, a
                        net's range: edakit graph json --write for a language source, edakit graph derive --write for a
                        JSON graph
"""

from __future__ import annotations

from ..circuit import VALUE_PARAMS, read_value, si, values
from ..findings import Finding
from ..lang.rules import in_window, inputs_differ

UNIT_PARAM = {unit: key for key, (unit, _) in VALUE_PARAMS.items()}


def part_value(d, des, unit):
    """The value of a part in `unit` as STRUCT.identity reads it: its entry's value parameter, else its text."""
    key = UNIT_PARAM.get(unit)
    entry = d.part(des)
    if key and entry is not None and isinstance(values(entry).get(key), (int, float)):
        return float(values(entry)[key])
    got = read_value((d.comps.get(des) or {}).get("value"))
    return got[0] if got and got[1] in (None, unit) else None


def _inputs(rec):
    shown = []
    for row in rec.get("inputs") or []:
        if row.get("unit") and row["name"] in ("i", "v_on", "v_in", "v", "v_out", "c_bus", "t_rise", "f_c"):
            shown.append(f"{row['name']} {si(row['value'], row['unit'])}")
    return ", ".join(shown)


def run(ctx):
    d = ctx.design
    out = []
    for rec in d.graph.get("derivations") or []:
        if not isinstance(rec, dict) or rec.get("part") not in d.comps:
            continue
        des, unit = rec["part"], (rec.get("derived") or {}).get("unit", "Ω")
        on = (("component", des),)
        value = part_value(d, des, unit)
        ser = rec.get("series") or {}
        if value is not None and ser.get("window") and not in_window(rec, value):
            lo, hi = ser["window"]
            text = (f"{des}: value {si(value, unit)}, derived {si(rec['derived']['value'], unit)} by {rec['rule']} "
                    f"({ser.get('name')} {si(ser.get('nearest'), unit)}, window {si(lo, unit)}…{si(hi, unit)})"
                    + (f" – {_inputs(rec)}" if _inputs(rec) else "") + f" ({rec.get('from')})")
            out.append(Finding("DEF.derive", "G", des, text, f"derivation {rec['rule']}, {rec.get('from')}",
                               data={"value": value, "window": [lo, hi]}, on=on))
        if diffs := inputs_differ(rec, d):
            out.append(Finding("DEF.derive", "G", des, f"{des}: the derivation by {rec['rule']} ({rec.get('from')}) "
                                                       f"read {'; '.join(diffs)}",
                               f"derivation {rec['rule']}, {rec.get('from')}", grade="inputs", on=on))
    return out
