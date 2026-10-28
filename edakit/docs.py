"""Values that documents and schematic notes quote from the design data – and G-19 for the ones gone stale.

    edakit docs            every quoted value against its source: G-19 for each that differs, exit 2
    edakit docs --write    fill in the current values

Markdown files listed in [docs] files of edakit.toml hold value blocks, invisible when rendered:

    LED current <!--edakit sim:max E-3 * D2 LED current*-->9.45 mA<!--/edakit--> per output

The notes of the schematic file ([layout.notes]) hold placeholders that `schematic draw` and `schematic layout` fill
in when they draw: `I_OUT = {sim:max E-3 * D2 LED current*}`. Only braces that start with a source are read.

Sources:
    graph:<key>                       a key of the graph itself: graph:version, graph:date
    graph:<part|net|cable>.<key>      graph:R1.value, graph:+5V.v, graph:W1.r_ohm_per_wire (dotted further)
    part:<parts entry>.<dotted path>  part:C90107.params.vrext_v – the unit follows the key (_v, _a, _ohm, _w, …)
    sim:<max|min|one> <pattern>       the numeric actual of the simulation rows whose "ID scenario item check" matches
                                      the fnmatch pattern – the key the sign-off file's `match` uses; the result is the
                                      one `edakit sim` saved while its inputs are unchanged, else a new run
    req:<ID>                          the text of a need or requirement of [project] requirements (N-2, R-4), on one
                                      line; a draft as it stands. A dropped entry is G-19: it no longer holds
A FORMAT after the source, e.g. "%.2f mA", formats the number (scaled to the prefix written after it); without one:
three significant digits and the unit of the source (4.02 mA). [docs] decimal = "," writes numbers with a decimal comma. Documents and the schematic file are in no hash, so
correcting a quoted number voids no sign-off. G-19 also runs in the gate's stage G, on the gate's own simulation.
Exit codes: 0 = every value current (or written), 2 = G-19 findings, 1 = error.
"""

from __future__ import annotations

import json
import re
import sys
from fnmatch import fnmatch

BLOCK = re.compile(r"<!--edakit\s+(.*?)\s*-->(.*?)<!--/edakit-->")
PLACEHOLDER = re.compile(r"\{((?:graph|part|sim|req):[^{}]*)\}")
FORMAT = re.compile(r"\s(%[-+ 0#]*\d*(?:\.\d+)?[diouxXeEfFgGs].*)$")
NUMBER = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(\S*)\s*$")
PREFIXES = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")]
SCALE = {p: f for f, p in PREFIXES} | {"u": 1e-6}
SI_UNITS = ("V", "A", "W", "Ω", "F", "H", "Hz", "s")
KEY_UNITS = {"_v": "V", "_a": "A", "_ohm": "Ω", "_w": "W", "_f": "F", "_h": "H", "_hz": "Hz", "_c": "°C", "_mm": "mm",
             "_s": "s"}


class QuoteError(Exception):
    pass


def engineering(x, unit="", decimal="."):
    """Three significant digits; an SI unit gets its prefix (0.004021 A -> 4.02 mA)."""
    if unit in SI_UNITS and x != 0:
        for f, p in PREFIXES:
            if abs(x) >= f * 0.9995 or f == PREFIXES[-1][0]:
                return f"{x / f:.3g}".replace(".", decimal) + f" {p}{unit}"
    return (f"{x:.3g}".replace(".", decimal) + f" {unit}").strip()


def formatted(value, unit, fmt, decimal="."):
    if fmt is None:
        if isinstance(value, bool) or value is None:
            return json.dumps(value)
        if isinstance(value, (int, float)):
            return engineering(value, unit, decimal)
        if isinstance(value, list):
            return " … ".join(formatted(v, "", None, decimal) for v in value) + (f" {unit}" if unit else "")
        if isinstance(value, dict):
            raise QuoteError("not a single value (a table)")
        return str(value)
    m = re.match(r"(%[-+ 0#]*\d*(?:\.\d+)?[diouxXeEfFgGs])(.*)$", fmt)
    spec, rest = m.group(1), m.group(2)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and unit:
        word = rest.strip().split(" ")[0] if rest.strip() else ""
        if word != unit and word.endswith(unit) and word[:-len(unit)] in SCALE:
            value = value / SCALE[word[:-len(unit)]]
    try:
        number = spec % value
        return (number.replace(".", decimal) if isinstance(value, (int, float)) else number) + rest
    except (TypeError, ValueError) as e:
        raise QuoteError(f"format {fmt!r}: {e}") from None


def dotted(entry, path, what):
    for key in path:
        if not isinstance(entry, dict) or key not in entry:
            raise QuoteError(f"{what}: no key {key}")
        entry = entry[key]
    return entry


class Sources:
    """The values a quote can name. A prefix is one entry of `self.prefixes` – a registry of project scripts could add
    its own (a script printing {name: value}, quoted as <script id>:<name>)."""

    def __init__(self, cfg, design, sim=None):
        self.cfg, self.d, self._sim = cfg, design, sim
        self.decimal = cfg.docs_decimal
        self.prefixes = {"graph": self.graph, "part": self.part, "sim": self.sim, "req": self.req}
        self._entries = None     # req: the needs and requirements by ID, read once – or why the files do not read

    def graph(self, rest):
        name, dot, path = rest.partition(".")
        if not dot:
            if name not in self.d.graph or isinstance(self.d.graph[name], (list, dict)):
                raise QuoteError(f"no key {name} in the graph")
            return self.d.graph[name], ""
        cables = {c.get("name"): c for c in self.d.graph.get("cables") or []}
        entry = self.d.comps.get(name) or self.d.nets.get(name) or cables.get(name)
        if entry is None:
            raise QuoteError(f"no part, net or cable {name} in the graph")
        keys = path.split(".")
        value = dotted(entry, keys, name)
        return value, "V" if keys == ["v"] and name in self.d.nets else ""

    def part(self, rest):
        key, dot, path = rest.partition(".")
        if key not in self.d.parts:
            raise QuoteError(f"no parts entry {key}")
        keys = path.split(".") if dot else []
        value = dotted(self.d.parts[key], keys, key)
        last = keys[-1] if keys else ""
        return value, next((u for suffix, u in KEY_UNITS.items() if last.endswith(suffix)), "")

    def rows(self):
        if self._sim is None:
            from .sim import run as simrun
            self._sim = simrun.current_result(self.cfg)
        return self._sim["checks"]

    def sim(self, rest):
        from .release.gate import key_of
        how, _, pattern = rest.strip().partition(" ")
        if how not in ("max", "min", "one") or not pattern.strip():
            raise QuoteError("sim:max, sim:min or sim:one, then the pattern of the rows")
        found = []
        for row in self.rows():
            if fnmatch(key_of(row), pattern.strip()):
                m = NUMBER.match(str(row.get("actual", "")))
                if not m:
                    raise QuoteError(f"{key_of(row)}: its actual value {row.get('actual')!r} is not a number")
                found.append((float(m.group(1)), m.group(2)))
        if not found:
            raise QuoteError(f"no simulation row matches {pattern.strip()!r}")
        if how == "one" and len(found) > 1:
            raise QuoteError(f"{len(found)} rows match, 'one' wants exactly one")
        units = {u for _, u in found}
        if len(units) > 1:
            raise QuoteError(f"the rows have different units: {', '.join(sorted(units))}")
        value = (max if how == "max" else min)(x for x, _ in found)
        return value, units.pop()

    def req(self, rest):
        """A need or requirement by its ID: its text, its white space on one line – a block is one line. A draft as it
        stands; a dropped entry no longer holds, like a part gone from the graph – its text stays in the file for the
        history, where edakit req shows it."""
        from . import requirements
        eid, cfg = rest.strip(), self.cfg
        if not cfg.requirements:
            raise QuoteError("no [project] requirements in edakit.toml – req: quotes the requirements file it names "
                             "(handbook 3.6)")
        if not requirements.ENTRY_ID.fullmatch(eid):
            raise QuoteError(f"{eid!r} is no ID of a need or requirement (N-<n>, R-<n>)")
        if self._entries is None:
            try:
                self._entries = {e.id: e for e in requirements.load(cfg)}
            except requirements.RequirementsError as e:
                self._entries = " ".join(str(e).split())
        if isinstance(self._entries, str):
            raise QuoteError(f"the requirements file does not read: {self._entries}")
        entry = self._entries.get(eid)
        if entry is None:
            raise QuoteError(f"no need or requirement {eid} in {', '.join(map(cfg.relative, cfg.requirements))}")
        if entry.status == "dropped":
            raise QuoteError(f"{eid} is dropped: {entry.reason} – quote the entry that holds now, or drop the quote")
        return " ".join(entry.text.split()), ""

    def text(self, source, fmt=None):
        prefix, colon, rest = source.partition(":")
        if not colon or prefix not in self.prefixes:
            raise QuoteError(f"unknown source {source!r} ({', '.join(f'{p}:' for p in self.prefixes)})")
        value, unit = self.prefixes[prefix](rest)
        return formatted(value, unit, fmt, self.decimal)

    def quote(self, spec):
        """The current text of a quote 'SOURCE [FORMAT]'."""
        m = FORMAT.search(spec)
        return self.text(spec[:m.start()].strip(), m.group(1)) if m else self.text(spec.strip())


def doc_blocks(cfg):
    """(file, line number, spec, written text) of every block in the listed files; a listed file missing: spec None."""
    out = []
    for name in cfg.docs:
        path = cfg.resolve(name)
        if not path.exists():
            out.append((path, 0, None, None))
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            out += [(path, i, m.group(1), m.group(2)) for m in BLOCK.finditer(line)]
    return out


def note_quotes(cfg):
    """(block title, spec) of every placeholder in the notes of the schematic file."""
    notes = (cfg.schematic.get("layout") or {}).get("notes") or {}
    return [(title, m.group(1)) for title, lines in notes.items() for line in lines
            for m in PLACEHOLDER.finditer(str(line))]


def findings(cfg, design, sim=None):
    """(G-19 findings, number of quotes)."""
    src, out = Sources(cfg, design, sim), []
    blocks, notes = doc_blocks(cfg), note_quotes(cfg)
    for path, line, spec, written in blocks:
        where = f"{cfg.relative(path)}:{line}"
        if spec is None:
            out.append(f"{cfg.relative(path)}: listed in [docs] files but not found")
            continue
        try:
            now = src.quote(spec)
        except QuoteError as e:
            out.append(f"{where}: {spec}: {e}")
            continue
        if now != written.strip():
            out.append(f"{where}: {spec}: written {written.strip() or '(empty)'}, now {now}")
    for title, spec in notes:
        try:
            src.quote(spec)
        except QuoteError as e:
            out.append(f"{cfg.relative(cfg.schematic_file)} [layout.notes] \"{title}\": {{{spec}}}: {e}")
    return out, len(blocks) + len(notes)


def write(cfg, design):
    """Fill every block with its current value; (files changed, blocks changed, problems)."""
    src, changed, blocks, problems = Sources(cfg, design), [], 0, []
    for name in cfg.docs:
        path = cfg.resolve(name)
        if not path.exists():
            problems.append(f"{name}: listed in [docs] files but not found")
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        n = 0
        for i, line in enumerate(lines):
            def fill(m):
                nonlocal n
                try:
                    now = src.quote(m.group(1))
                except QuoteError as e:
                    problems.append(f"{cfg.relative(path)}:{i + 1}: {m.group(1)}: {e}")
                    return m.group(0)
                n += now != m.group(2).strip()
                return f"<!--edakit {m.group(1)}-->{now}<!--/edakit-->"
            lines[i] = BLOCK.sub(fill, line)
        if n:
            path.write_text("\n".join(lines), encoding="utf-8")
            changed.append(cfg.relative(path))
            blocks += n
    return changed, blocks, problems


def fill_notes(cfg, design, notes, warn=print):
    """The notes with their placeholders filled in; one that cannot be filled stays as written, with a warning."""
    if not any(PLACEHOLDER.search(str(line)) for lines in notes.values() for line in lines):
        return notes
    src = Sources(cfg, design)

    def fill(m):
        try:
            return src.quote(m.group(1))
        except QuoteError as e:
            warn(f"  ! note {{{m.group(1)}}}: {e} – left as written")
            return m.group(0)
    return {title: [PLACEHOLDER.sub(fill, str(line)) for line in lines] for title, lines in notes.items()}


def stage_rows(cfg, design, sim):
    """G-19 in the gate's stage G, on the gate's own simulation result; no quotes, no rows."""
    from . import rules
    found, n = findings(cfg, design, sim)
    if not n and not found:
        return []
    rows = [{"stage": "G", "id": "G-19", "item": "", "check": f, "result": "fail"} for f in found]
    return rows or [{"stage": "G", "id": "G-19", "item": "", "check": f"{rules.title('G-19')}: {n} quoted values",
                     "result": "pass"}]


def main(cfg, args):
    from . import rules
    from .design import Design
    from .sim.run import SimError
    design = Design.from_config(cfg)
    try:
        if args.write:
            changed, n, problems = write(cfg, design)
            for f in changed:
                print(f"written: {f}")
            for p in problems:
                print(f"G-19  {p}")
            print(f"{n} quoted values brought up to date" + (f", {len(problems)} not resolvable" if problems else ""))
            return 2 if problems else 0
        found, n = findings(cfg, design)
    except SimError as e:
        print(f"edakit docs: {e}", file=sys.stderr)
        return 1
    if not n and not found:
        print("nothing quoted: no [docs] files and no placeholders in the schematic notes (handbook 6.6)")
        return 0
    for f in found:
        print(f"G-19  {f}")
    print(f"{n} quoted values, {len(found)} stale or unresolvable" + (" – edakit docs --write fills in the current "
                                                                       "values" if found else ""))
    if found:
        print("\n  " + "\n  ".join(rules.explain("G-19")))
    return 2 if found else 0

