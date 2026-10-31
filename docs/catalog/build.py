"""The catalog as one page: every engine and code with its rule, why, fix and sources, the domains, the tables with
their sources, the parts schema, the reference circuits drawn by edakit schematic draw with their seeded faults, what
became of maker-coverage's candidates, and the check IDs of before.

    .venv/bin/python docs/catalog/build.py          writes docs/catalog/index.html and docs/catalog/circuits/*.svg

Everything comes from the catalog (edakit/catalog, edakit/domains), tests/reference.py and
docs/concepts/new/maker-coverage-status.toml; tests/test_catalog_page.py fails while the files here differ.
"""

from __future__ import annotations

import re
import sys
import tempfile
import tomllib
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from edakit import catalog, profile  # noqa: E402
from edakit.schema import kinds  # noqa: E402

OUT = Path(__file__).resolve().parent
STATUS = ROOT / "docs" / "concepts" / "new" / "maker-coverage-status.toml"
CIRCUITS = ["led-bar", "motors", "audio", "guitar", "power", "cables", "usb", "keyboard"]


def md(text):
    """The catalog's light markup – `code`, **bold** – as HTML, the rest escaped."""
    t = escape(str(text))
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)


def chip(sev, label=None):
    return f'<span class="chip {escape(sev)}">{escape(label or sev)}</span>'


# --- the reference circuits --------------------------------------------------------------------------------------------
def circuits():
    """[(name, about, domains, svg, faults)] – each built in a scratch directory and drawn."""
    import reference
    from edakit import config, engines
    from edakit.design import Design
    from edakit.schematic_draw import main as draw

    class Args:
        board = None
        force = False
        out = None
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in CIRCUITS:
            target = Path(tmp) / name
            reference.write_one(target, name)
            cfg = config.load(target / "edakit.toml")
            args = Args()
            args.out = str(target / "drawing.svg")
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                draw(cfg, args)
            svg = Path(args.out).read_text(encoding="utf-8")
            doms = ["core", *engines.profile(Design.from_config(cfg), cfg).enabled]
            about = (reference.REFERENCES[name].__doc__ if name in reference.REFERENCES else
                     "The example of the handbook: a Raspberry Pi Pico 2 drives eight LEDs through a TLC5916 "
                     "constant-current sink, 5 V through a JST PH connector and a reverse diode, one button. Every "
                     "reference circuit adds its domain's circuit to it.")
            out.append((name, " ".join(about.split()), doms, svg, reference.FAULTS.get(name, [])))
    return out


def svg_inline(svg):
    """The drawing, scaled by the page: width and height in mm dropped, the viewBox kept."""
    return re.sub(r'\swidth="[^"]+mm" height="[^"]+mm"', "", svg, count=1)


# --- sections ------------------------------------------------------------------------------------------------------------
def engines_section():
    per = Counter(catalog.engine_of(c) for c in catalog.codes())
    rows = "".join(f'<tr><td><a href="#engine-{e["prefix"]}"><code>{e["prefix"]}</code></a></td><td>{escape(name)}</td>'
                   f'<td>{md(e["decides"])}</td><td class="num">{per[name]}</td></tr>'
                   for name, e in catalog.engines().items())
    return ('<section id="engines"><h2>Engines</h2><p>Each engine decides one kind of relation; a finding\'s code is '
            '<code>ENGINE.relation</code>. Severities are the catalog\'s defaults – a project\'s domains may set others; '
            'a grade is a sub-case with its own severity, a topic the part of a code a domain switches on.</p>'
            '<div class="scroll"><table><thead><tr><th>Prefix</th><th>Engine</th><th>Decides</th><th class="num">Codes'
            f'</th></tr></thead><tbody>{rows}</tbody></table></div></section>')


def code_entry(name, e):
    grades = "".join(chip(s, f"{g}: {s}") for g, s in (e.get("grades") or {}).items())
    replaces = (f'<p class="meta">Replaces {", ".join(escape(x) for x in e["replaces"])}</p>'
                if e.get("replaces") else "")
    when = ""
    if e.get("when"):
        w = e["when"]
        when = ('<p class="meta">Applies where ' + "; ".join(
            ([f'kinds {", ".join(w["kinds"])}'] if w.get("kinds") else []) +
            ([f'matcher {w["match"]}'] if w.get("match") else [])) + "</p>")
    details = ("<ul class=\"details\">" + "".join(f"<li>{md(d)}</li>" for d in e["details"]) + "</ul>"
               if e.get("details") else "")
    sources = ("<ol class=\"sources\">" + "".join(f"<li>{md(s)}</li>" for s in e.get("sources", [])) + "</ol>"
               if e.get("sources") else '<p class="meta">No source listed.</p>')
    return (f'<article class="code" id="{escape(name)}" data-text="{escape((name + " " + e["title"] + " " + e["rule"]).lower())}">'
            f'<header><h4><code>{escape(name)}</code> {escape(e["title"])}</h4>'
            f'<div class="chips">{chip(e["severity"])}{grades}</div></header>'
            f'<p class="rule">{md(e["rule"])}</p>{details}'
            f'<dl><dt>Why</dt><dd>{md(e["why"])}</dd><dt>What to do</dt><dd>{md(e["fix"])}</dd>'
            f'<dt>Sources</dt><dd>{sources}</dd></dl>{when}{replaces}</article>')


def codes_section():
    parts = ['<section id="codes"><h2>Codes</h2><p class="filter"><label for="q">Filter codes</label> '
             '<input id="q" type="search" placeholder="LIM.range, pull-up, USB-C …" autocomplete="off"></p>']
    for eng, e in catalog.engines().items():
        names = [n for n in catalog.codes() if catalog.engine_of(n) == eng]
        label = f'<code>{e["prefix"]}</code>' + ("" if eng == e["prefix"] else f" {escape(eng)}")
        parts.append(f'<div class="engine" id="engine-{e["prefix"]}"><h3>{label} '
                     f'<span class="muted">– {md(e["decides"])}</span></h3>')
        parts += [code_entry(n, catalog.codes()[n]) for n in names]
        parts.append("</div>")
    retired = catalog.retired()
    if retired:
        parts.append("<h3>Retired</h3><ul>" + "".join(f"<li><code>{escape(k)}</code> – {md(v)}</li>"
                                                      for k, v in retired.items()) + "</ul>")
    return "".join(parts) + "</section>"


def domains_section():
    out = ['<section id="domains"><h2>Domains</h2><p>A project names its domains in <code>[project] domains</code>; '
           'without the key every domain the graph suggests is on. <code>core</code> is always on.</p><div class="cards">']
    for name, f in profile.domains().items():
        d = f.get("domain") or {}
        sug = d.get("suggested_by")
        rows = [("About", md(d.get("about", "")))]
        if sug:
            rows.append(("Suggested by", md("; ".join(f"{k} {', '.join(v) if isinstance(v, list) else v}"
                                                     for k, v in sug.items()))))
        if (f.get("switch") or {}).get("on"):
            rows.append(("Switches on", " ".join(f"<code>{escape(x)}</code>" for x in f["switch"]["on"])))
        sev = {k: v for k, v in (f.get("severity") or {}).items() if not isinstance(v, dict)}
        sev.update({f"{k} (purpose {p})": v for p, t in (f.get("severity") or {}).items() if isinstance(t, dict)
                    for k, v in t.items()})
        if sev:
            rows.append(("Severities", " ".join(f"<code>{escape(k)}</code> {chip(v)}" for k, v in sev.items())))
        facts = [f"{kind}: {', '.join(v)}" for table in (f.get("facts") or {}).values() for kind, v in table.items()]
        if facts:
            rows.append(("Facts required", md("; ".join(facts))))
        if (f.get("hints") or {}).get("apply"):
            rows.append(("Hints", " ".join(f'<a href="#{h}"><code>{h}</code></a>' for h in f["hints"]["apply"])))
        review = "".join(f"<li><strong>{escape(r)}:</strong> {md(q)}</li>" for r, qs in (f.get("review") or {}).items()
                         for q in qs)
        body = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
        out.append(f'<article class="card" id="domain-{name}"><h3><code>{name}</code></h3><dl>{body}</dl>'
                   + (f'<p class="meta">Reviewers\' questions</p><ul class="review">{review}</ul>' if review else "")
                   + "</article>")
    return "".join(out) + "</div></section>"


def leaves(node, path=""):
    """(key, value) of every number or string below node, its source and tag left out."""
    for k, v in node.items():
        if isinstance(v, dict):
            yield from leaves(v, f"{path}.{k}" if path else k)
        elif k not in ("source", "tag"):
            yield (f"{path}.{k}" if path else k), v


def sections(t, path=""):
    """[(section, node)] – every table of the file that holds values of its own, the nested ones after it."""
    out = []
    own = {k: v for k, v in t.items() if not isinstance(v, dict)}
    if path and set(own) - {"source", "tag"}:
        out.append((path, t))
    for k, v in t.items():
        if isinstance(v, dict) and k != "table":
            out += sections(v, f"{path}.{k}" if path else k)
    return out


def tables_section():
    out = ['<section id="tables"><h2>Tables</h2><p>The numbers the engines use. Each file names its source; a section '
           'with a source of its own shows it. Tag <code>r</code>: read from the source.</p>']
    for name in catalog.table_names():
        t = catalog.table(name)
        head = t.get("table") or {}
        body = []
        for sec, node in sections(t):
            src = node.get("source")
            body.append(f'<tr class="sec"><th colspan="2"><code>{escape(sec)}</code>'
                        + (f' <span class="src">{md(src)}' + (f' · tag {escape(node["tag"])}' if node.get("tag") else "")
                           + "</span>" if src else "") + "</th></tr>")
            body += [f'<tr><td><code>{escape(k)}</code></td><td class="val">{md(v)}</td></tr>'
                     for k, v in ((k, v) for k, v in node.items() if not isinstance(v, dict) and k not in ("source", "tag"))]
        out.append(f'<article class="table-card" id="table-{name}"><h3><code>tables/{name}.toml</code></h3>'
                   f'<p>{md(head.get("about", ""))}</p><p class="meta">Source: {md(head.get("source", "–"))}'
                   + (f' · tag {escape(head["tag"])}' if head.get("tag") else "")
                   + f'</p><div class="scroll"><table class="kv"><tbody>{"".join(body)}</tbody></table></div></article>')
    return "".join(out) + "</section>"


def kinds_section():
    k = kinds()

    def names(xs):
        return ", ".join(f"<code>{escape(x)}</code>" for x in xs) or "–"
    rows = [f'<tr><td>every kind</td><td>–</td><td>{names(k["common"]["limits"])}</td><td>–</td></tr>']
    rows += [f'<tr><td><code>{kind}</code></td><td>{names(d.get("roles", []))}</td><td>{names(d.get("limits", []))}'
             f'</td><td>{names(d.get("values", []))}</td></tr>' for kind, d in k["kinds"].items()]
    units = ", ".join(f"<code>_{u}</code> {escape(v)}" for u, v in k["units"].items())
    return ('<section id="schema"><h2>Parts schema</h2><p>What a parts entry of each kind may give; '
            '<code>edakit part lint</code> holds the entries to it. Every name ends in its unit: ' + units + '.</p>'
            '<div class="scroll"><table><thead><tr><th>Kind</th><th>Roles</th><th>Limits</th><th>Values</th></tr>'
            f'</thead><tbody>{"".join(rows)}</tbody></table></div><p>Per pin: {names(k["common"]["pin"])}; and '
            f'{names(k["free"]["pin"])}.</p></section>')


def circuits_section(items):
    out = ['<section id="circuits"><h2>Reference circuits</h2><p>edakit\'s own circuits, one per domain, each added to '
           'the example and drawn by <code>edakit schematic draw</code>. Each passes <code>edakit check</code> and '
           '<code>edakit sim</code> clean under its domains; each seeded fault raises exactly its codes '
           '(<code>tests/test_reference.py</code>). The values are chosen for the test, not taken from datasheets.</p>']
    for name, about, doms, svg, faults in items:
        rows = "".join(f'<tr><td>{escape(what)}</td><td>{" ".join(f"<a href=\"#{c}\"><code>{c}</code></a>" for c in sorted(codes))}</td></tr>'
                       for what, _, codes in faults)
        table = (f'<table class="faults"><thead><tr><th>Seeded fault</th><th>Codes it raises</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table>' if faults else "")
        out.append(f'<article class="circuit" id="circuit-{name}"><h3>{escape(name)}</h3><p>{md(about)}</p>'
                   f'<p class="meta">Domains on: {" ".join(f"<code>{d}</code>" for d in doms)} · '
                   f'<a href="circuits/{name}.svg">SVG</a></p><div class="drawing">{svg_inline(svg)}</div>{table}</article>')
    return "".join(out) + "</section>"


def candidates_section():
    s = tomllib.loads(STATUS.read_text(encoding="utf-8"))
    tiles, groups = [], []
    labels = {"features": "Features (FT)", "checks": "Checks (CK)", "hints": "Hints (HT)", "blocks": "Blocks (BL)",
              "review": "Reviewer questions"}
    for sec, label in labels.items():
        c = Counter(e["status"] for e in s[sec].values())
        tiles.append(f'<div class="tile"><span class="big">{c["built"]}</span><span class="of">of {len(s[sec])}</span>'
                     f'<span class="lbl">{label}</span><span class="sub">{c["partial"]} partial · {c["open"]} open</span>'
                     "</div>")
        rows = "".join(f'<tr><td><code>{escape(k)}</code></td><td>{chip(e["status"])}</td>'
                       f'<td>{md(e.get("where", ""))}</td><td>{md(e.get("missing", ""))}</td></tr>'
                       for k, e in s[sec].items())
        groups.append(f'<h3>{label}</h3><div class="scroll"><table class="cand"><thead><tr><th>ID</th><th>Status</th>'
                      f'<th>Where</th><th>Missing</th></tr></thead><tbody>{rows}</tbody></table></div>')
    pf = s["part_facts"]
    n = sum(len(e["parts"]) for e in pf.values())
    tiles.append(f'<div class="tile"><span class="big">0</span><span class="of">of {n}</span><span class="lbl">Part facts'
                 '</span><span class="sub">open decision 4 · datasheets</span></div>')
    groups.append("<h3>Part facts</h3><ul>" + "".join(f"<li><strong>{escape(k.replace('_', ' '))}:</strong> "
                                                       f"{escape(', '.join(e['parts']))}</li>" for k, e in pf.items())
                  + "</ul>")
    return ('<section id="candidates"><h2>maker-coverage candidates</h2><p>The candidates of '
            '<code>docs/concepts/new/maker-coverage.md</code> and what became of them '
            '(<code>maker-coverage-status.toml</code>). Open for lack of read datasheets or standards, or by an open '
            'decision.</p><div class="tiles">' + "".join(tiles) + "</div>" + "".join(groups) + "</section>")


def old_ids_section():
    def key(old):
        return "PGESLFH".index(old[0]), int(old[2:])
    rows = "".join(f'<tr><td>{escape(o)}</td><td>{" ".join(f"<a href=\"#{c}\"><code>{c}</code></a>" for c in new)}</td></tr>'
                   for o, new in sorted(catalog.old_map().items(), key=lambda x: key(x[0])))
    return ('<section id="before"><h2>Check IDs of before</h2><p>The IDs per stage before the restructuring and the '
            'codes that replace them; <code>edakit explain G-8</code> says the same.</p><div class="scroll"><table>'
            f'<thead><tr><th>Before</th><th>Now</th></tr></thead><tbody>{rows}</tbody></table></div></section>')


CSS = """
:root {
  /* a reference, read by section: a sidebar of contents, entries in one column, drawings full width */
  --bg: #f4f6f6; --surface: #ffffff; --ink: #1d2626; --muted: #5d6b6b; --line: #d5dddd; --accent: #0e6c6a;
  --err: #b42318; --warn: #a15c07; --pend: #6941c6; --note: #475467; --ok: #087443;
  --display: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif; --body: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #111717; --surface: #182020; --ink: #e3eaea; --muted: #97a6a6; --line: #2c3838; --accent: #5cc4c0;
  --err: #f97066; --warn: #fdb022; --pend: #b692f6; --note: #98a2b3; --ok: #47cd89; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #111717; --surface: #182020; --ink: #e3eaea; --muted: #97a6a6; --line: #2c3838; --accent: #5cc4c0;
  --err: #f97066; --warn: #fdb022; --pend: #b692f6; --note: #98a2b3; --ok: #47cd89; color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.55 var(--body); }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: 0.9em; }
.layout { display: grid; grid-template-columns: 15rem minmax(0, 1fr); gap: 2rem; max-width: 84rem; margin: 0 auto;
  padding: 1.5rem 1.25rem 4rem; }
nav { position: sticky; top: 1rem; align-self: start; max-height: calc(100vh - 2rem); overflow: auto; font-size: 0.9rem; }
nav ol { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.2rem; }
nav ol ol { padding-left: 0.9rem; margin: 0.2rem 0 0.4rem; }
nav a { text-decoration: none; color: var(--ink); }
nav a:hover, nav a:focus-visible { color: var(--accent); }
header.top h1 { font: 600 2rem/1.15 var(--display); margin: 0 0 0.4rem; text-wrap: balance; }
header.top p { color: var(--muted); max-width: 70ch; margin: 0; }
h2 { font: 600 1.45rem/1.2 var(--display); margin: 2.6rem 0 0.8rem; padding-top: 0.6rem; border-top: 2px solid var(--ink);
  text-wrap: balance; }
h3 { font: 600 1.1rem/1.3 var(--display); margin: 1.6rem 0 0.6rem; }
h4 { font: 600 1rem/1.3 var(--display); margin: 0; }
p, li, dd { max-width: 75ch; }
.muted, .meta { color: var(--muted); }
.meta { font-size: 0.85rem; margin: 0.4rem 0 0; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr)); gap: 0.75rem; margin: 1rem 0; }
.tile { background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 0.8rem; display: grid; }
.tile .big { font: 600 1.8rem/1 var(--display); font-variant-numeric: tabular-nums; }
.tile .of { color: var(--muted); font-size: 0.85rem; }
.tile .lbl { font-weight: 600; margin-top: 0.3rem; }
.tile .sub { color: var(--muted); font-size: 0.8rem; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; background: var(--surface); font-size: 0.9rem; }
th, td { text-align: left; vertical-align: top; padding: 0.45rem 0.6rem; border-bottom: 1px solid var(--line); }
th { font-weight: 600; background: color-mix(in srgb, var(--surface) 85%, var(--accent)); }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.chips { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.chip { display: inline-block; font-size: 0.75rem; line-height: 1.5; padding: 0 0.45rem; border-radius: 999px;
  border: 1px solid currentColor; white-space: nowrap; }
.chip.error { color: var(--err); } .chip.warning { color: var(--warn); } .chip.pending { color: var(--pend); }
.chip.note { color: var(--note); } .chip.built { color: var(--ok); } .chip.partial { color: var(--warn); }
.chip.open { color: var(--muted); }
.engine > h3 { border-bottom: 1px solid var(--line); padding-bottom: 0.3rem; }
article.code { background: var(--surface); border: 1px solid var(--line); border-left: 3px solid var(--accent);
  border-radius: 4px; padding: 0.8rem 1rem; margin: 0.7rem 0; }
article.code header { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; align-items: baseline; justify-content: space-between; }
article.code .rule { margin: 0.5rem 0; }
article.code dl, .card dl { display: grid; grid-template-columns: 7.5rem minmax(0, 1fr); gap: 0.3rem 0.8rem; margin: 0.4rem 0 0; }
dt { font-weight: 600; color: var(--muted); font-size: 0.85rem; }
dd { margin: 0; }
ul.details { margin: 0.3rem 0; padding-left: 1.2rem; font-size: 0.9rem; }
ol.sources, ul.sources { margin: 0; padding-left: 1.2rem; font-size: 0.85rem; }
.filter { display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; }
.filter input { font: inherit; padding: 0.35rem 0.6rem; border: 1px solid var(--line); border-radius: 4px;
  background: var(--surface); color: var(--ink); min-width: 16rem; }
.filter input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr)); gap: 1rem; }
.card, .table-card, article.circuit { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 0.9rem 1rem; }
.card h3, .table-card h3, article.circuit h3 { margin-top: 0; }
.table-card { margin: 0.8rem 0; }
ul.review { padding-left: 1.2rem; font-size: 0.88rem; }
article.circuit { margin: 1rem 0; }
.drawing { overflow-x: auto; background: #ffffff; border: 1px solid var(--line); border-radius: 4px; margin: 0.6rem 0; }
.drawing svg { display: block; width: 100%; min-width: 46rem; height: auto; }
table.faults { margin-top: 0.4rem; }
table.kv { width: auto; min-width: 24rem; }
table.kv tr.sec th { background: transparent; border-bottom: 1px solid var(--ink); padding-top: 0.9rem; }
table.kv .src { font-weight: 400; color: var(--muted); font-size: 0.85rem; margin-left: 0.5rem; }
table.kv td.val { font-variant-numeric: tabular-nums; }
table.cand td:first-child { white-space: nowrap; }
td, dd, li { overflow-wrap: anywhere; }
footer { color: var(--muted); font-size: 0.85rem; margin-top: 3rem; }
@media (max-width: 52rem) {
  .layout { grid-template-columns: minmax(0, 1fr); gap: 1rem; padding: 1rem 1rem 3rem; }
  nav { position: static; max-height: none; }
  nav > ol { display: flex; flex-wrap: wrap; gap: 0.3rem 0.9rem; }
  nav ol ol { display: none; }
  article.code dl, .card dl { grid-template-columns: minmax(0, 1fr); }
  .cards { grid-template-columns: minmax(0, 1fr); }
  table.kv { min-width: 0; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""

SCRIPT = """
const q = document.getElementById('q');
q.addEventListener('input', () => {
  const s = q.value.trim().toLowerCase();
  document.querySelectorAll('article.code').forEach(a => { a.hidden = s && !a.dataset.text.includes(s); });
  document.querySelectorAll('.engine').forEach(e => {
    e.hidden = s && !e.querySelector('article.code:not([hidden])');
  });
});
"""


def page(items):
    codes = catalog.codes()
    hints = [n for n in codes if n.startswith("HINT.")]
    grades = sum(len(e.get("grades") or {}) for e in codes.values())
    sources = len({s for e in codes.values() for s in e.get("sources", [])})
    nav_engines = "".join(f'<li><a href="#engine-{e["prefix"]}">{e["prefix"]}</a></li>' for e in catalog.engines().values())
    nav_circuits = "".join(f'<li><a href="#circuit-{n}">{n}</a></li>' for n, *_ in items)
    tiles = "".join(f'<div class="tile"><span class="big">{v}</span><span class="lbl">{k}</span></div>' for k, v in (
        ("Engines", len(catalog.engines())), ("Codes", len(codes)), ("Grades", grades), ("Hints", len(hints)),
        ("Domains", len(profile.domains())), ("Sources cited", sources), ("Reference circuits", len(items))))
    body = (f'<header class="top"><h1>edakit rule catalog</h1><p>Every rule edakit checks – engine, code, severity, '
            'rule, why, what to do and its sources –, the domains that switch rules on, the tables of numbers, the parts '
            'schema, the reference circuits with their seeded faults, and what became of the maker-coverage '
            'candidates. Generated from <code>edakit/catalog</code>, <code>edakit/domains</code> and '
            f'<code>tests/reference.py</code>.</p></header><div class="tiles">{tiles}</div>'
            + engines_section() + codes_section() + domains_section() + tables_section() + kinds_section()
            + circuits_section(items) + candidates_section() + old_ids_section()
            + '<footer>Written by <code>docs/catalog/build.py</code>; <code>tests/test_catalog_page.py</code> holds it to '
              'the catalog.</footer>')
    nav = ('<nav aria-label="Contents"><ol><li><a href="#engines">Engines</a></li><li><a href="#codes">Codes</a>'
           f'<ol>{nav_engines}</ol></li><li><a href="#domains">Domains</a></li><li><a href="#tables">Tables</a></li>'
           f'<li><a href="#schema">Parts schema</a></li><li><a href="#circuits">Reference circuits</a><ol>{nav_circuits}'
           '</ol></li><li><a href="#candidates">maker-coverage candidates</a></li><li><a href="#before">Check IDs of '
           'before</a></li></ol></nav>')
    return ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width, initial-scale=1"><title>edakit rule catalog</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" '
            'href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&display=swap">'
            f'<style>{CSS}</style></head><body><div class="layout">{nav}<main>{body}</main></div>'
            f'<script>{SCRIPT}</script></body></html>\n')


def build(out=OUT):
    """Write the page and the drawings into out; -> the files written."""
    out = Path(out)
    (out / "circuits").mkdir(parents=True, exist_ok=True)
    items = circuits()
    written = []
    for name, _, _, svg, _ in items:
        f = out / "circuits" / f"{name}.svg"
        f.write_text(svg, encoding="utf-8")
        written.append(f)
    f = out / "index.html"
    f.write_text(page(items), encoding="utf-8")
    return [f, *written]


if __name__ == "__main__":
    for f in build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT):
        print(f"written: {f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}")
