#!/usr/bin/env python3
"""Prototype of step 4.3: the hardware graph as a language of its own (.circuit) and as TOML with pin names.

    python3 translate.py circuit hardware/graph.json         the graph as a language, on stdout
    python3 translate.py toml    hardware/graph.json         the graph as TOML with pin names
    python3 translate.py json    bell.circuit --parts DIR    a form back to graph JSON (also a .toml file)

Both forms write a pin by role or name and resolve it through the parts entries (--parts, default: parts/ beside
the file). The rules are in ../../circuit-language.md. A prototype: stdlib only, not edakit code.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

BARE = re.compile(r'[^\s"#=]+')                       # a word that needs no quotes
NUMBER = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")
PLAIN = re.compile(r"\d+|pin\d+")                     # roles and names that say no more than the number
WIDTH = 118


class TranslateError(ValueError):
    pass


def load_parts(directory):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(directory).glob("*.json"))
            if p.name != "README.json"}


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def num(s):
    if not NUMBER.fullmatch(s):
        raise ValueError(s)
    return float(s) if re.search(r"[.eE]", s) else int(s)


def raw(v):
    return json.dumps(v, ensure_ascii=False)


def strings(d):
    return isinstance(d, dict) and d and all(isinstance(t, str) for t in d.values())


# --- pins by number, name or role ------------------------------------------------------------------------------------

class Pins:
    """Pin maps (the graph's, else the parts entry's) and roles (the parts entry's) of the components."""

    def __init__(self, parts):
        self.parts, self.by_mpn, self.map, self.role, self.kind = parts, {}, {}, {}, {}
        for key, entry in parts.items():
            self.by_mpn.setdefault(str(entry.get("mpn") or key), key)

    def entry(self, comp):
        """As edakit's Design.entry_key: by LCSC number, without one by `part` = the entry's mpn."""
        if comp.get("lcsc"):
            return self.parts.get(comp["lcsc"])
        return self.parts.get(self.by_mpn.get(str(comp.get("part") or "")))

    def entry_names(self, comp):
        pins = (self.entry(comp) or {}).get("pins")
        return {n: p.get("name") for n, p in pins.items()} if isinstance(pins, dict) else None

    def add(self, comp, pin_map):
        des, entry = comp["designator"], self.entry(comp) or {}
        self.map[des] = pin_map
        self.role[des] = {n: p.get("role") for n, p in (entry.get("pins") or {}).items()}
        self.kind[des] = entry.get("kind")

    def resolve(self, des, tok):
        """The pins `tok` names on `des`: its number; the name or role of one pin; else every pin sharing it."""
        pins, roles = self.map[des], self.role[des]
        if tok in pins:
            return [tok]
        named = [n for n in pins if pins[n] == tok]
        roled = [n for n in pins if roles.get(n) == tok]
        return next((h for h in (named, roled) if len(h) == 1), named or roled)

    def words(self, des, num_=None):
        """Names and roles worth writing, in the order a writer tries them: the name first on ICs and modules (their
        names are the datasheet's), the role first elsewhere (anode, cathode – a name may mislead)."""
        pins, roles = self.map[des], self.role[des]
        names, rls = ([pins.get(num_)], [roles.get(num_)]) if num_ else (list(pins.values()), list(roles.values()))
        return [t for t in (names + rls if self.kind.get(des) in ("ic", "module") else rls + names)
                if isinstance(t, str) and BARE.fullmatch(t) and not PLAIN.fullmatch(t) and t not in pins]

    def token(self, des, num_):
        """The word for one pin: the first that names only this pin, else its number."""
        return next((t for t in self.words(des, num_) if self.resolve(des, t) == [num_]), num_)

    def tokens(self, pins, prefix=True, marked=()):
        """Words for a list of pins [(des, num)]: one for a run that is every pin of a shared name or role (U1.GND),
        else one per pin; a pin in `marked` gets ' (locked)'."""
        out, i = [], 0
        while i < len(pins):
            des, num_ = pins[i]
            for tok in dict.fromkeys(self.words(des)):
                run = [(des, n) for n in self.resolve(des, tok)]
                if len(run) > 1 and pins[i:i + len(run)] == run and not set(run) & set(marked):
                    break
            else:
                tok, run = self.token(des, num_), [pins[i]]
            out.append((f"{des}.{tok}" if prefix else tok) + (" (locked)" if pins[i] in marked else ""))
            i += len(run)
        return out

    def split(self, ref, where):
        des, dot, num_ = str(ref).partition(".")
        if not dot or des not in self.map or num_ not in self.map[des]:
            raise TranslateError(f"{where}: '{ref}' names no pin of the graph (G-1 reports it) – fix the graph first")
        return des, num_

    def named(self, ref, where):
        des, num_ = self.split(ref, where)
        return f"{des}.{self.token(des, num_)}"

    def read(self, tok, where, des=None):
        """The references 'DES.NUM' a written word stands for."""
        if des is None:
            des, dot, tok = tok.partition(".")
            if not dot or des not in self.map:
                raise TranslateError(f"{where}: '{des}.{tok}': no part {des}")
        hits = self.resolve(des, tok)
        if not hits:
            raise TranslateError(f"{where}: '{des}.{tok}': no pin of that number, name or role on {des}")
        return [f"{des}.{n}" for n in hits]


def setup(g, parts):
    """The pins of a graph to write; refuses what neither form can hold – a graph G-1 rejects."""
    if not (isinstance(g.get("components"), list) and isinstance(g.get("nets"), list)):
        raise TranslateError("the graph has no lists 'components' and 'nets'")
    pins = Pins(parts)
    for c in g["components"]:
        des = c.get("designator")
        if not (isinstance(des, str) and BARE.fullmatch(des) and "." not in des and des not in pins.map
                and isinstance(c.get("pins"), dict)):
            raise TranslateError(f"component {des!r}: designator missing, doubled or not a word, or no pin map")
        pins.add(c, c["pins"])
    names = [n.get("name") for n in g["nets"]]
    if len(set(names)) != len(names) or not all(isinstance(n, str) and isinstance(x.get("pins"), list)
                                                for n, x in zip(names, g["nets"])):
        raise TranslateError("a net without name or pin list, or a name twice (G-1 reports it)")
    return pins


def explicit_map(pins, comp):
    """The pin map a form must state: none where it equals the parts entry's names."""
    return None if pins.entry_names(comp) == comp["pins"] else comp["pins"]


# --- the language: writing -------------------------------------------------------------------------------------------

def word(s):
    return s if BARE.fullmatch(s) and s != "-" else raw(s)


def text(s, start, indent="    "):
    """A quoted string, wrapped at single spaces before the width; a line break inside quotes reads as one space."""
    lines, line = [], '"'
    for chunk in re.split(r"(?<=\S) (?=\S)", raw(s)[1:-1]):
        if line != '"' and start + len(line) + len(chunk) + 2 > WIDTH:
            lines.append(line)
            line, start = indent, 0
        line += ("" if line in ('"', indent) else " ") + chunk
    return "\n".join(lines + [line + '"'])


def flow(head, words, indent="  ", repeat=False):
    """`head` and words in lines up to the width; with `repeat` every line starts with the head's keyword."""
    out, line = [], head
    for w in words:
        if len(line) + 1 + len(w) > WIDTH and line != head:
            out.append(line)
            line = indent + (head.strip() + " " if repeat else "") + w
        else:
            line += " " + w
    return out + [line]


def tail(el, done):
    """The lines every element ends with: waivers, verify, notes, and `set KEY JSON` for what no form took."""
    out = []
    if strings(el.get("waive")):
        out += [f"  waive {word(k)} " + text(t, 9 + len(word(k))) for k, t in el["waive"].items()]
        done.add("waive")
    for key in ("verify", "notes"):
        if isinstance(el.get(key), str):
            out.append(f"  {key} " + text(el[key], 3 + len(key)))
            done.add(key)
    return out + [f"  set {word(k)} {raw(v)}" for k, v in el.items() if k not in done]


def to_circuit(data, parts):
    g = data.get("graph", data)
    pins = setup(g, parts)
    out = ["# The hardware graph as a language (.circuit), written by translate.py: pins by role or name through the",
           "# parts entries, nets with their voltage range. Rules: docs/concepts/done/circuit-language.md"]
    done = {"components", "nets"} | {k for k in ("name", "version", "date", "description") if isinstance(g.get(k), str)}
    out.append(" ".join(["graph", word(g["name"]) if "name" in done else "-"]
                        + [f"{k} {word(g[k])}" for k in ("version", "date") if k in done]))
    if "description" in done:
        out.append("description " + text(g["description"], 12))
    p = g.get("purpose")
    if strings(p) and set(p) <= {"use", "market", "notes"}:
        out.append(" ".join(["purpose", word(p["use"]) if "use" in p else "-"]
                            + ([f"market {word(p['market'])}"] if "market" in p else [])))
        out += ["  notes " + text(p["notes"], 8)] if "notes" in p else []
        done.add("purpose")
    for key, kw in (("conventions", "convention"), ("hints", "hint")):
        if strings(g.get(key)):
            out += [f"{kw} {word(k)} " + text(t, len(kw) + len(word(k)) + 2) for k, t in g[key].items()]
            done.add(key)
    if isinstance(g.get("ground"), str):
        out.append("ground " + word(g["ground"]))
        done.add("ground")
    if isinstance(g.get("grounds"), list) and g["grounds"] and all(isinstance(n, str) for n in g["grounds"]):
        out.append(" ".join(["grounds", *map(word, g["grounds"])]))
        done.add("grounds")

    out.append("")
    for c in g["components"]:
        out += part_lines(c, pins)

    checks = g.get("checks")
    locks = checks.get("pin_locks") if isinstance(checks, dict) else None
    locks = locks if strings(locks) else {}
    marked = set()
    out.append("")
    for n in g["nets"]:
        refs = [pins.split(r, f"net {n['name']}") for r in n["pins"]]
        mark = [(d, k) for d, k in refs if locks.get(f"{d}.{k}") == n["name"]]
        marked |= {f"{d}.{k}" for d, k in mark}
        out += net_lines(n, refs, mark, pins)

    if isinstance(checks, dict) and checks and all(BARE.fullmatch(k) and "." not in k for k in checks):
        for key, v in checks.items():
            if key == "pin_locks" and locks:
                out += [f"lock {pins.named(r, 'checks.pin_locks')} {word(n)}" for r, n in v.items() if r not in marked]
            elif key == "reverse_protect" and isinstance(v, list) and v and all(isinstance(d, str) for d in v):
                out.append(" ".join(["reverse_protect", *map(word, v)]))
            else:
                out.append(f"set checks.{key} {raw(v)}")
        done.add("checks")
    cables = g.get("cables")
    if cables == []:
        out.append("set cables []")
        done.add("cables")
    elif isinstance(cables, list) and all(lines := [cable_lines(c, pins) for c in cables]):
        out += [x for c in lines for x in c]
        done.add("cables")
    lay = g.get("layout")
    if isinstance(lay, dict) and lay and all(BARE.fullmatch(k) and "." not in k for k in lay):
        out += layout_lines(lay, pins)
        done.add("layout")
    out += [f"set {word(k) if '.' not in k else raw(k)} {raw(v)}" for k, v in g.items() if k not in done]
    return "\n".join(out) + "\n"


def part_lines(c, pins):
    des = c["designator"]
    first = ["part", des] + [word(c[k]) if isinstance(c.get(k), str) else "-" for k in ("type", "part")]
    done = {"designator", "pins"} | {k for k in ("type", "part", "lcsc", "value", "board", "supplier", "label")
                                     if isinstance(c.get(k), str)}
    first += [f"{k} {word(c[k])}" for k in ("lcsc", "value", "board", "supplier") if k in done]
    if c.get("bom") is False:
        first.append("no-bom")
        done.add("bom")
    if isinstance(c.get("spare"), int) and not isinstance(c["spare"], bool):
        first.append(f"spare {c['spare']}")
        done.add("spare")
    line, rest = " ".join(first), []
    if "label" in done:
        if len(line) + 1 + len(raw(c["label"])) <= WIDTH:
            line += " " + raw(c["label"])
        else:
            rest.append("  label " + text(c["label"], 8))
    own = explicit_map(pins, c)
    if own and all(BARE.fullmatch(n) and isinstance(v, str) for n, v in own.items()):
        rest += flow("  pins", [f"{n}={word(v)}" for n, v in own.items()], repeat=True)
    elif own is not None:
        done.discard("pins")                            # an empty or odd map goes as `set pins JSON`
    if isinstance(c.get("nc"), list) and c["nc"]:
        nc = [pins.split(f"{des}.{n}", f"{des}.nc") for n in c["nc"]]
        rest += flow("  nc", pins.tokens(nc, prefix=False), repeat=True)
        done.add("nc")
    return [line, *rest, *tail(c, done)]


def net_lines(n, refs, mark, pins):
    head, done = f"net {word(n['name'])}", {"name", "pins"}
    v = n.get("v")
    if isinstance(v, list) and len(v) == 2 and all(map(number, v)):
        lo, hi = map(repr, v)
        head += f" {lo} V" if lo == hi else f" {lo}..{hi} V"
        done.add("v")
    lines = flow(head, pins.tokens(refs, marked=mark), indent="    ")
    fn = [f"{k} {word(n[k])}" for k in ("fn", "fn_bus", "bus") if isinstance(n.get(k), str)]
    fn += [f"pwm_hz {n['pwm_hz']!r}"] if number(n.get("pwm_hz")) else []
    done |= {k for k in ("fn", "fn_bus", "bus", "pwm_hz") if any(f.startswith(k + " ") for f in fn)}
    return lines + (["  " + " ".join(fn)] if fn else []) + tail(n, done)


def cable_lines(c, pins):
    """A cable statement, or None where the cable does not fit one (then the whole list goes as JSON)."""
    if not (isinstance(c, dict) and all(isinstance(c.get(k), str) for k in ("name", "from", "to"))
            and c["from"] in pins.map and c["to"] in pins.map and isinstance(c.get("pins"), dict)):
        return None
    if not all(a in pins.map[c["from"]] and b in pins.map[c["to"]] for a, b in c["pins"].items()):
        return None
    pairs = [f"{pins.token(c['from'], a)}={pins.token(c['to'], b)}" for a, b in c["pins"].items()]
    done = {"name", "from", "to", "pins"} | {k for k in ("r_ohm_per_wire", "i_max_a") if number(c.get(k))}
    line = " ".join(["cable", word(c["name"]), word(c["from"]), word(c["to"]), *pairs]
                    + [f"{k} {c[k]!r}" for k in ("r_ohm_per_wire", "i_max_a") if k in done])
    return [line, *tail(c, done)]


def layout_lines(lay, pins):
    out = []
    for key, v in lay.items():
        words = isinstance(v, list) and v and all(isinstance(d, str) for d in v)
        if key in ("fixed", "edge") and words:
            out.append(" ".join(["layout", key, *map(word, v)]))
        elif key == "notes" and words:
            out += ["layout note " + text(t, 12) for t in v]
        elif key == "near" and isinstance(v, dict) and v and all(
                isinstance(h, str) or (isinstance(h, list) and len(h) > 1 and all(isinstance(x, str) for x in h))
                for h in v.values()):
            out += [" ".join(["layout near", word(d), *map(word, [h] if isinstance(h, str) else h)]) for d, h in v.items()]
        elif key == "loops" and isinstance(v, list) and v and all(
                isinstance(lp, dict) and set(lp) <= {"a", "b", "max_mm", "what"} and "a" in lp and "b" in lp
                and number(lp.get("max_mm", 0)) and isinstance(lp.get("what", ""), str) for lp in v):
            out += [" ".join(["layout loop", pins.named(lp["a"], "layout.loops"), pins.named(lp["b"], "layout.loops")]
                             + ([f"max_mm {lp['max_mm']!r}"] if "max_mm" in lp else [])
                             + ([raw(lp["what"])] if "what" in lp else [])) for lp in v]
        else:
            out.append(f"set layout.{key} {raw(v)}")
    return out


# --- the language: reading -------------------------------------------------------------------------------------------

SCAN = re.compile(r'(?P<tok>[^\s"#]*"(?:[^"\\]|\\.)*"|[^\s"#]+)|(?P<nl>\n)|(?P<skip>[ \t\r]+|#[^\n]*)|(?P<bad>.)',
                  re.S)
WORDS, STRINGS = ("lcsc", "value", "board", "supplier", "fn", "fn_bus", "bus"), ("label", "notes", "verify")
NUMBERS = ("spare", "pwm_hz", "r_ohm_per_wire", "i_max_a")


class Tok:
    def __init__(self, m, line, col):
        self.raw, self.start, self.end, self.line, self.col = m.group(), m.start(), m.end(), line, col
        q = self.raw.find('"')
        self.prefix = self.raw[:q] if q >= 0 else None          # None: a bare word; "": a quoted string
        body = re.sub(r"\n[ \t]*", " ", self.raw[q + 1:-1]) if q >= 0 else None
        self.string = json.loads(f'"{body}"', strict=False) if q >= 0 else None
        self.word = self.string if self.prefix == "" else self.raw

    def keyword(self, *kws):
        return self.prefix is None and self.raw in kws


def statements(src):
    """Statements: a line that starts at column 0 and the indented lines below it, each as a list of token lines."""
    out, line, col0, first = [], 1, 0, True
    for m in SCAN.finditer(src):
        if m.lastgroup == "bad":
            raise TranslateError(f"line {line}: unclosed string")
        if m.lastgroup == "nl":
            line, col0, first = line + 1, m.end(), True
        elif m.lastgroup == "tok":
            try:
                t = Tok(m, line, m.start() - col0)
            except json.JSONDecodeError as e:
                raise TranslateError(f"line {line}: a string that is no JSON string: {e.msg}") from None
            if t.col == 0:
                out.append([[t]])
            elif not out:
                raise TranslateError(f"line {line}: an indented line before the first statement")
            elif first:
                out[-1].append([t])
            else:
                out[-1][-1].append(t)
            first = False
            if "\n" in m.group():
                line += m.group().count("\n")
                col0 = m.start() + m.group().rfind("\n") + 1
    return out


class Reader:
    """Reads a .circuit file into the graph; every pin is resolved once all parts are known."""

    def __init__(self, src, parts):
        self.src, self.pins = src, Pins(parts)
        self.g, self.comps, self.nets, self.later = {}, {}, {}, []

    def fail(self, tok, msg):
        raise TranslateError(f"line {tok.line}: {msg}")

    def arg(self, ln, i, kind="word"):
        """Argument i of a line: a word, a quoted string or a number."""
        if i >= len(ln):
            self.fail(ln[-1], f"'{ln[0].raw}': a value is missing")
        if kind == "string" and ln[i].prefix != "":
            self.fail(ln[i], f"'{ln[i].raw}': a quoted string expected")
        if kind == "number":
            try:
                return num(ln[i].raw)
            except ValueError:
                self.fail(ln[i], f"'{ln[i].raw}': a number expected")
        return ln[i].word

    def set_key(self, target, ln, i):
        """`set KEY JSON` from token i, the JSON to the end of the line; a bare KEY with a dot reaches one level down
        (checks.pin_locks)."""
        key = self.arg(ln, i)
        if ln[i].prefix is None and "." in key:
            head, key = key.split(".", 1)
            target = target.setdefault(head, {})
        if i + 1 >= len(ln):
            self.fail(ln[i], "a JSON value is missing")
        try:
            target[key] = json.loads(self.src[ln[i + 1].start:ln[-1].end])
        except json.JSONDecodeError as e:
            self.fail(ln[i + 1], f"no valid JSON: {e}")

    def attrs(self, el, ln, i=0, other=None):
        """The attributes of a line from token i on; `other(ln, i)` takes what no attribute is and returns where to
        go on."""
        while i < len(ln):
            t = ln[i]
            if t.keyword(*WORDS, *STRINGS, *NUMBERS):
                kind = "word" if t.raw in WORDS else "string" if t.raw in STRINGS else "number"
                el[t.raw], i = self.arg(ln, i + 1, kind), i + 2
            elif t.keyword("no-bom"):
                el["bom"], i = False, i + 1
            elif t.keyword("waive"):
                el.setdefault("waive", {})[self.arg(ln, i + 1)] = self.arg(ln, i + 2, "string")
                i += 3
            elif t.keyword("set"):
                return self.set_key(el, ln, i + 1)
            elif other:
                i = other(ln, i)
            else:
                self.fail(t, f"unknown '{t.raw}'")

    def read(self):
        for st in statements(self.src):
            kw = st[0][0]
            handler = getattr(self, "st_" + kw.raw, None) if kw.prefix is None else None
            if handler is None:
                self.fail(kw, f"unknown statement '{kw.raw}'")
            handler(st, [t for ln in st for t in ln])
        self.g["components"], self.g["nets"] = list(self.comps.values()), list(self.nets.values())
        for c in self.g["components"]:
            self.pins.add(c, c["pins"])
        for job in self.later:
            job()
        return {"graph": self.g}

    def one(self, tok, net=None):
        refs = self.pins.read(tok.raw, f"line {tok.line}")
        if len(refs) != 1:
            self.fail(tok, f"'{tok.raw}' names several pins; here only one")
        if net is not None:
            self.g.setdefault("checks", {}).setdefault("pin_locks", {})[refs[0]] = net
        return refs[0]

    # the graph as a whole
    def st_graph(self, st, ts):
        if len(ts) > 1 and not ts[1].keyword("-"):
            self.g["name"] = ts[1].word
        for i in range(2, len(ts), 2):
            if not ts[i].keyword("version", "date"):
                self.fail(ts[i], "graph NAME [version V] [date D]")
            self.g[ts[i].raw] = self.arg(ts, i + 1)

    def st_description(self, st, ts):
        self.g["description"] = self.arg(ts, 1, "string")

    def st_purpose(self, st, ts):
        p = self.g["purpose"] = {}
        if len(ts) > 1 and not ts[1].keyword("-"):
            p["use"] = ts[1].word
        for i in range(2, len(ts), 2):
            if not ts[i].keyword("market", "notes"):
                self.fail(ts[i], "purpose USE [market MARKET] [notes \"…\"]")
            p[ts[i].raw] = self.arg(ts, i + 1, "string" if ts[i].raw == "notes" else "word")

    def st_convention(self, st, ts):
        self.g.setdefault("conventions", {})[self.arg(ts, 1)] = self.arg(ts, 2, "string")

    def st_hint(self, st, ts):
        self.g.setdefault("hints", {})[self.arg(ts, 1)] = self.arg(ts, 2, "string")

    def st_ground(self, st, ts):
        self.g["ground"] = self.arg(ts, 1)

    def st_grounds(self, st, ts):
        self.g.setdefault("grounds", []).extend(t.word for t in ts[1:])

    def st_set(self, st, ts):
        self.set_key(self.g, st[0], 1)

    def st_reverse_protect(self, st, ts):
        self.g.setdefault("checks", {}).setdefault("reverse_protect", []).extend(t.word for t in ts[1:])

    def st_lock(self, st, ts):
        net = self.arg(ts, 2)
        self.later.append(lambda: self.one(ts[1], net))

    # parts
    def st_part(self, st, ts):
        if len(ts) < 4:
            self.fail(ts[0], "part DESIGNATOR TYPE PART …")
        des = ts[1].word
        if des in self.comps:
            self.fail(ts[1], f"part {des} twice")
        c = self.comps[des] = {"designator": des}
        c.update({k: t.word for k, t in (("type", ts[2]), ("part", ts[3])) if not t.keyword("-")})
        nc, own = [], {}

        def other(ln, i):
            t = ln[i]
            if t.keyword("nc"):
                nc.extend(ln[i + 1:])
            elif t.keyword("pins"):
                for p in ln[i + 1:]:
                    k, eq, v = (p.prefix or p.raw).partition("=")
                    if not eq:
                        self.fail(p, "pins NUMBER=NAME …")
                    own[k] = p.string if p.prefix else v
            elif t.prefix == "" and "label" not in c:
                c["label"] = t.string
                return i + 1
            else:
                self.fail(t, f"part {des}: unknown '{t.raw}'")
            return len(ln)

        for ln in [st[0][4:], *st[1:]]:
            self.attrs(c, ln, 0, other)
        if own or "pins" not in c:
            c["pins"] = own or self.pins.entry_names(c)
        if c["pins"] is None:
            self.fail(ts[1], f"part {des}: no parts entry and no line 'pins'")
        if nc:
            self.later.append(lambda: c.__setitem__("nc", [
                r.split(".", 1)[1] for t in nc for r in self.pins.read(t.word, f"line {t.line}", des)]))

    # nets
    def st_net(self, st, ts):
        """A net; a later statement of the same net adds pins, and attributes it does not have yet."""
        ln = st[0]
        name = self.arg(ln, 1)
        n = self.nets.setdefault(name, {"name": name, "pins": []})
        new, i = {}, 2
        if len(ln) > 3 and ln[3].keyword("V"):
            lo, _, hi = ln[2].raw.partition("..")
            try:
                new["v"], i = [num(lo), num(hi or lo)], 4
            except ValueError:
                self.fail(ln[2], f"net {name}: '{ln[2].raw} V' is no voltage range")
        pins = list(ln[i:])
        for more in st[1:]:
            if more[0].prefix is None and "." in more[0].raw:
                pins += more
            else:
                self.attrs(new, more)
        twice = [k for k in new if k in n and (k != "waive" or set(new[k]) & set(n[k]))]
        if twice:
            self.fail(ln[0], f"net {name}: {', '.join(twice)} given twice")
        n.update({k: {**n.get(k, {}), **v} if k == "waive" else v for k, v in new.items()})
        self.later.append(lambda: self.net_pins(n, pins))

    def net_pins(self, n, toks):
        for k, t in enumerate(toks):
            if t.keyword("(locked)"):
                continue
            if k + 1 < len(toks) and toks[k + 1].keyword("(locked)"):
                n["pins"].append(self.one(t, n["name"]))
            else:
                n["pins"] += self.pins.read(t.raw, f"line {t.line}")

    # cables and the hand-over to the layout
    def st_cable(self, st, ts):
        c = {"name": self.arg(ts, 1), "from": self.arg(ts, 2), "to": self.arg(ts, 3), "pins": {}}
        self.g.setdefault("cables", []).append(c)
        pairs = []
        for ln in [st[0][4:], *st[1:]]:
            self.attrs(c, ln, 0, lambda ln, i: pairs.append(ln[i]) or i + 1)

        def resolve():
            for p in pairs:
                a, _, b = p.raw.partition("=")
                ra = self.pins.read(a, f"line {p.line}", c["from"])
                rb = self.pins.read(b, f"line {p.line}", c["to"])
                c["pins"][ra[0].split(".", 1)[1]] = rb[0].split(".", 1)[1]
        self.later.append(resolve)

    def st_layout(self, st, ts):
        lay, what = self.g.setdefault("layout", {}), ts[1].raw if len(ts) > 1 else ""
        if what in ("fixed", "edge"):
            lay.setdefault(what, []).extend(t.word for t in ts[2:])
        elif what == "note":
            lay.setdefault("notes", []).append(self.arg(ts, 2, "string"))
        elif what == "near":
            hosts = [t.word for t in ts[3:]]
            lay.setdefault("near", {})[self.arg(ts, 2)] = hosts[0] if len(hosts) == 1 else hosts
        elif what == "loop":
            lp, rest = {}, ts[4:]
            lay.setdefault("loops", []).append(lp)
            if rest and rest[0].keyword("max_mm"):
                lp["max_mm"], rest = self.arg(rest, 1, "number"), rest[2:]
            if rest:
                lp["what"] = self.arg(rest, 0, "string")
            self.later.append(lambda: lp.update(a=self.one(ts[2]), b=self.one(ts[3])))
        else:
            self.fail(ts[0], "layout fixed|edge|near|loop|note …")


def from_circuit(src, parts):
    return Reader(src, parts).read()


# --- TOML with names -------------------------------------------------------------------------------------------------

TKEY = re.compile(r"[A-Za-z0-9_-]+")
ORDER = ("type", "label", "part", "lcsc", "value", "bom", "board", "supplier", "spare", "v", "pins", "nc", "waive",
         "verify", "notes")


def tkey(k):
    return k if TKEY.fullmatch(k) else raw(k)


def tval(v, start=0):
    """A TOML value starting at column `start`: a long string as a multi-line string wrapped with a line-ending
    backslash, a long array over several lines."""
    if v is None:
        raise TranslateError("TOML has no null – the graph holds one")
    if isinstance(v, bool):
        return "true" if v else "false"
    if number(v):
        return repr(v)
    if isinstance(v, str):
        if start + len(raw(v)) <= WIDTH:
            return raw(v)
        lines, line = [], "  "
        for chunk in re.split(r"(?<=\S) (?=\S)", raw(v)[1:-1]):
            if line != "  " and len(line) + len(chunk) + 3 > WIDTH:
                lines.append(line + " \\")
                line = "  "
            line += ("" if line == "  " else " ") + chunk
        return '"""\\\n' + "\n".join(lines + [line + '"""'])
    if isinstance(v, list):
        items = [tval(x) for x in v]
        if start + 2 + len(", ".join(items)) <= WIDTH or any("\n" in x for x in items):
            return "[" + ", ".join(items) + "]"
        lines, line = [], "["
        for k, x in enumerate(items):
            piece = x + ("]" if k == len(items) - 1 else ",")
            if line != "[" and (0 if lines else start) + len(line) + 1 + len(piece) > WIDTH:
                lines.append(line)
                line = " " * (start + 1) + piece
            else:
                line += ("" if line == "[" else " ") + piece
        return "\n".join(lines + [line])
    if isinstance(v, dict):
        return "{" + ", ".join(f"{tkey(k)} = {tval(x)}" for k, x in v.items()) + "}" if v else "{}"
    raise TranslateError(f"no TOML for {v!r}")


def tline(key, v, prefix=""):
    head = f"{prefix}{tkey(key)} = "
    return head + tval(v, len(head))


def table(header, body):
    """A table: in a part, net or cable the keys in ORDER and waivers as dotted keys (waive.P-1); elsewhere the keys
    as they come and a non-empty table in it as [header.key]. No header for a table that only holds tables."""
    element = header.startswith(("[components.", "[nets.", "[cables."))
    keys = sorted(body, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER)) if element else list(body)
    nested = [k for k in keys if isinstance(body[k], dict) and body[k] and not element and "." not in header]
    out = []
    for k in keys:
        if element and k == "waive" and isinstance(body[k], dict) and body[k]:
            out += [tline(w, t, "waive.") for w, t in body[k].items()]
        elif k not in nested:
            out.append(tline(k, body[k]))
    out = ["", header] + out if out or not nested else []
    for k in nested:
        out += table(f"{header[:-1]}.{tkey(k)}]", body[k])
    return out


def to_toml(data, parts):
    g = data.get("graph", data)
    pins = setup(g, parts)
    out = ["# The hardware graph as TOML, written by translate.py: today's graph with pins by role or name through the",
           "# parts entries; components, nets and cables keyed. Rules: docs/concepts/done/circuit-language.md"]
    tables = [k for k, v in g.items() if (isinstance(v, dict) or k in ("components", "nets", "cables")) and v]
    out += [tline(k, v) for k, v in g.items() if k not in tables]
    for key in tables:
        if key == "components":
            for c in g[key]:
                body = {k: x for k, x in c.items() if k not in ("designator", "pins")}
                if explicit_map(pins, c) is not None:
                    body["pins"] = c["pins"]
                if isinstance(c.get("nc"), list):
                    body["nc"] = pins.tokens([pins.split(f"{c['designator']}.{n}", "nc") for n in c["nc"]], False)
                out += table(f"[components.{tkey(c['designator'])}]", body)
        elif key == "nets":
            for n in g[key]:
                body = {**{k: x for k, x in n.items() if k != "name"},
                        "pins": pins.tokens([pins.split(r, f"net {n['name']}") for r in n["pins"]])}
                out += table(f"[nets.{tkey(n['name'])}]", body)
        elif key == "cables":
            names = [c.get("name") if isinstance(c, dict) else None for c in g[key]]
            if not all(isinstance(x, str) for x in names) or len(set(names)) != len(names):
                raise TranslateError("cables: a name missing or doubled")
            for c in g[key]:
                body = {k: x for k, x in c.items() if k != "name"}
                if isinstance(c.get("pins"), dict) and c.get("from") in pins.map and c.get("to") in pins.map:
                    body["pins"] = {pins.named(f"{c['from']}.{a}", "cable").split(".", 1)[1]:
                                    pins.named(f"{c['to']}.{b}", "cable").split(".", 1)[1] for a, b in c["pins"].items()}
                out += table(f"[cables.{tkey(c['name'])}]", body)
        else:
            body = dict(g[key])
            if key == "layout" and isinstance(body.get("loops"), list):
                body["loops"] = [{**lp, **{e: pins.named(lp[e], "layout.loops") for e in "ab" if e in lp}}
                                 for lp in body["loops"]]
            if key == "checks" and isinstance(body.get("pin_locks"), dict):
                body["pin_locks"] = {pins.named(r, "checks.pin_locks"): n for r, n in body["pin_locks"].items()}
            out += table(f"[{tkey(key)}]", body)
    return "\n".join(out) + "\n"


def from_toml(src, parts):
    try:
        g = tomllib.loads(src)
    except tomllib.TOMLDecodeError as e:
        raise TranslateError(str(e)) from None
    for key, name in (("components", "designator"), ("nets", "name"), ("cables", "name")):
        if isinstance(g.get(key), dict):
            g[key] = [{name: k, **v} for k, v in g[key].items()]
    pins = Pins(parts)

    def read(tok, des=None):
        """A name resolved; an error names the line where the word first stands."""
        pos = src.find(raw(tok))
        return pins.read(tok, f"line {src.count(chr(10), 0, pos) + 1 if pos >= 0 else '?'}", des)

    def one(tok, des=None):
        return read(tok, des)[0] if des is None else read(tok, des)[0].split(".", 1)[1]

    for c in g.get("components", []):
        c["pins"] = c["pins"] if "pins" in c else pins.entry_names(c)
        if c["pins"] is None:
            raise TranslateError(f"[components.{c['designator']}]: no parts entry and no key 'pins'")
        pins.add(c, c["pins"])
    for c in g.get("components", []):
        if isinstance(c.get("nc"), list):
            c["nc"] = [r.split(".", 1)[1] for t in c["nc"] for r in read(t, c["designator"])]
    for n in g.get("nets", []):
        if isinstance(n.get("pins"), list):
            n["pins"] = [r for t in n["pins"] for r in read(t)]
    checks = g.get("checks") or {}
    if isinstance(checks.get("pin_locks"), dict):
        checks["pin_locks"] = {one(t): net for t, net in checks["pin_locks"].items()}
    for lp in (g.get("layout") or {}).get("loops") or []:
        lp.update({e: one(lp[e]) for e in "ab" if e in lp})
    for c in g.get("cables") or []:
        if isinstance(c.get("pins"), dict) and c.get("from") in pins.map and c.get("to") in pins.map:
            c["pins"] = {one(a, c["from"]): one(b, c["to"]) for a, b in c["pins"].items()}
    return {"graph": g}


# --- command line ----------------------------------------------------------------------------------------------------

def to_json(path, parts):
    src = Path(path).read_text(encoding="utf-8")
    return from_toml(src, parts) if str(path).endswith(".toml") else from_circuit(src, parts)


def canonical(data):
    """The comparison of the round trip: JSON with sorted keys – the order of keys aside, lists in their order."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("to", choices=["circuit", "toml", "json"])
    ap.add_argument("file")
    ap.add_argument("--parts", help="the parts entries (default: parts/ beside the file)")
    args = ap.parse_args(argv)
    parts = load_parts(args.parts or Path(args.file).parent / "parts")
    try:
        if args.to == "json":
            sys.stdout.write(json.dumps(to_json(args.file, parts), indent=1, ensure_ascii=False) + "\n")
        else:
            data = json.loads(Path(args.file).read_text(encoding="utf-8"))
            sys.stdout.write((to_circuit if args.to == "circuit" else to_toml)(data, parts))
    except TranslateError as e:
        sys.exit(f"{args.file}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
