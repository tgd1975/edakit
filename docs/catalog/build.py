"""The catalog as pages: index.html with the counters, the engines and every code in one filterable list; one page per
engine (<prefix lower case>.html) with each code's rule, why, fix and sources; the domains, the tables with their
sources, the parts schema, the reference circuits drawn by edakit schematic draw with their seeded faults (a page each),
the published open designs with every finding judged (a page each), what became of maker-coverage's candidates, and the
check IDs of before. PAGES names them in navigation order; docs/pages.py puts them into the site's navigation.

    .venv/bin/python docs/catalog/build.py          writes docs/catalog/*.html and docs/catalog/circuits/*.svg

Everything comes from the catalog (edakit/catalog, edakit/domains), tests/reference.py, tests/open_designs/ and
docs/concepts/done/maker-coverage-status.toml; tests/test_catalog_page.py fails while the files here differ.
"""

from __future__ import annotations

import contextlib
import io
import re
import shutil
import sys
import tempfile
import tomllib
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from edakit import catalog, national, profile  # noqa: E402
from edakit.schema import kinds  # noqa: E402

OUT = Path(__file__).resolve().parent
STATUS = ROOT / "docs" / "concepts" / "done" / "maker-coverage-status.toml"
OPEN = ROOT / "tests" / "open_designs"
CIRCUITS = ["led-bar", "motors", "audio", "guitar", "power", "cables", "usb", "keyboard"]


def md(text):
    """The catalog's light markup – `code`, **bold** – as HTML, the rest escaped."""
    t = escape(str(text))
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)


def page_of(name):
    """The page of a code's engine – the name handbook.page_of links to from the handbook."""
    return f"{name.split('.')[0].lower()}.html"


def href(name):
    return f"{page_of(name)}#{name}"


def code_links(codes):
    return " ".join(f'<a href="{href(c)}"><code>{c}</code></a>' for c in codes)


def engine_title(name, e):
    """The short title of an engine's page: its prefix, and its name where that differs – "LIM – limits"."""
    return e["prefix"] + ("" if name == e["prefix"] else f" – {name.lower()}")


ENGINE_PAGES = [(f'{e["prefix"].lower()}.html', engine_title(n, e)) for n, e in catalog.engines().items()]
PAGES = [("index.html", "Overview"), *ENGINE_PAGES, ("domains.html", "Domains"), ("tables.html", "Tables"),
         ("schema.html", "Parts schema"), ("circuits.html", "Reference circuits"), ("open-designs.html", "Open designs"),
         ("candidates.html", "maker-coverage candidates"), ("before.html", "Check IDs of before")]


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


def open_designs():
    """[(name, title, source, svg, judged)] of tests/open_designs/<name>/ – each copied to a scratch directory and drawn;
    source the README's **Source:** paragraph, judged its findings.toml."""
    from edakit import config
    from edakit.schematic_draw import main as draw

    class Args:
        board = None
        force = False
        out = None
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for d in sorted(p for p in OPEN.iterdir() if (p / "edakit.toml").is_file()):
            target = Path(tmp) / d.name
            shutil.copytree(d, target, ignore=shutil.ignore_patterns("build"))
            args = Args()
            args.out = str(target / "drawing.svg")
            with contextlib.redirect_stdout(io.StringIO()):
                draw(config.load(target / "edakit.toml"), args)
            readme = (d / "README.md").read_text(encoding="utf-8")
            title = readme.splitlines()[0].lstrip("# ").split(" – ")[0]
            source = " ".join(readme.split("**Source:**", 1)[1].split("\n\n", 1)[0].split())
            judged = tomllib.loads((d / "findings.toml").read_text(encoding="utf-8"))
            out.append((d.name, title, source, Path(args.out).read_text(encoding="utf-8"), judged))
    return out


def svg_inline(svg):
    """The drawing, scaled by the page: width and height in mm dropped, the viewBox kept."""
    return re.sub(r'\swidth="[^"]+mm" height="[^"]+mm"', "", svg, count=1)


# --- sections ------------------------------------------------------------------------------------------------------------
ENGINES_ABOUT = ('Each engine decides one kind of relation; a finding\'s code is <code>ENGINE.relation</code>. '
                 'Severities are the catalog\'s defaults – a project\'s domains may set others; a grade is a sub-case '
                 'with its own severity, a topic the part of a code a domain switches on.')


BOARD_ENGINES = ("SYNC", "GEO", "FILES", "ORDER")     # the rest decide on the circuit


def severities(names):
    """'5 errors · 4 warnings · 1 note' – the catalog's default severities of these codes."""
    n = Counter(catalog.codes()[c]["severity"] for c in names)
    words = {"error": "error", "warning": "warning", "note": "note", "pending": "pending"}
    return " · ".join(f"{k} {words.get(s, s)}{'s' if k > 1 and s != 'pending' else ''}" for s, k in
                      sorted(n.items(), key=lambda x: ["error", "warning", "pending", "note"].index(x[0])
                             if x[0] in ("error", "warning", "pending", "note") else 9))


def engines_section():
    """The engines as cards in two groups – on the circuit, on the board and the order –, each linking its page with
    what it decides, its number of codes and their severities; the old anchor engine-<prefix> on its card."""
    def card(name, e):
        names = [c for c in catalog.codes() if catalog.engine_of(c) == name]
        label = "" if name == e["prefix"] else f' <span class="muted">{escape(name)}</span>'
        return (f'<a class="ecard" id="engine-{e["prefix"]}" href="{e["prefix"].lower()}.html">'
                f'<span class="ehead"><code>{e["prefix"]}</code>{label}<span class="ecount">{len(names)}</span></span>'
                f'<span class="edecides">{md(e["decides"])}</span><span class="esev">{severities(names)}</span></a>')
    groups = []
    for title, board in (("On the circuit", False), ("On the board and the order", True)):
        cards = "".join(card(n, e) for n, e in catalog.engines().items() if (n in BOARD_ENGINES) == board)
        groups.append(f'<h3>{title}</h3><div class="ecards">{cards}</div>')
    return f'<section id="engines"><h2>Engines</h2><p>{ENGINES_ABOUT}</p>{"".join(groups)}</section>'


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
    return (f'<article class="code" id="{escape(name)}" data-text="{text_of(name, e)}">'
            f'<header><h4><code>{escape(name)}</code> {escape(e["title"])}</h4>'
            f'<div class="chips">{chip(e["severity"])}{grades}</div></header>'
            f'<p class="rule">{md(e["rule"])}</p>{details}'
            f'<dl><dt>Why</dt><dd>{md(e["why"])}</dd><dt>What to do</dt><dd>{md(e["fix"])}</dd>'
            f'<dt>Sources</dt><dd>{sources}</dd></dl>{when}{replaces}</article>')


FILTER = ('<p class="filter"><label for="q">Filter codes</label> '
          '<input id="q" type="search" placeholder="LIM.range, pull-up, USB-C …" autocomplete="off"></p>')


def text_of(name, e):
    return escape((name + " " + e["title"] + " " + e["rule"]).lower())


def codes_section():
    """Every code, folded by engine – code, title, severity –, each row with the code as its id (the old anchors of the
    one page land here and open their engine) and linking the entry on its engine's page; the filter opens what it
    finds."""
    groups = []
    for eng, e in catalog.engines().items():
        names = [n for n in catalog.codes() if catalog.engine_of(n) == eng]
        rows = "".join(f'<tr id="{escape(n)}" data-text="{text_of(n, catalog.codes()[n])}"><td><a href="{href(n)}">'
                       f'<code>{escape(n)}</code></a></td><td>{escape(catalog.codes()[n]["title"])}</td>'
                       f'<td>{chip(catalog.codes()[n]["severity"])}</td></tr>' for n in names)
        groups.append(f'<details class="group"><summary><code>{e["prefix"]}</code> <span class="muted">– '
                      f'{md(e["decides"])} · {len(names)}</span></summary><div class="scroll"><table class="codes">'
                      f'<tbody>{rows}</tbody></table></div></details>')
    retired = catalog.retired()
    old = ("<h3>Retired</h3><ul>" + "".join(f"<li><code>{escape(k)}</code> – {md(v)}</li>" for k, v in retired.items())
           + "</ul>" if retired else "")
    return (f'<section id="codes"><h2>Codes</h2><p>Folded by engine; the filter opens what it finds.</p>{FILTER}'
            f'{"".join(groups)}{old}</section>')


def engine_body(eng, e):
    """An engine's page: what it decides, and each of its codes with rule, why, fix and sources."""
    names = [n for n in catalog.codes() if catalog.engine_of(n) == eng]
    lead = e["decides"][:1].upper() + e["decides"][1:]
    return (f'<p class="lead">{md(lead)} – {len(names)} codes.</p><p>{ENGINES_ABOUT}</p>{FILTER}'
            + "".join(code_entry(n, catalog.codes()[n]) for n in names))


DOMAINS_ABOUT = ('A project names its domains in <code>[project] domains</code>; without the key every domain the graph '
                 'suggests is on. <code>core</code> is always on.')


def domains_section():
    out = ['<div class="cards">']
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
        facts = [f"{kind}: {', '.join(v)}" for by, table in (f.get("facts") or {}).items()
                 for kind, v in (table.items() if isinstance(table, dict) else [(f"every {by.upper()} part", table)])]
        if facts:
            rows.append(("Facts required", md("; ".join(facts))))
        if (f.get("hints") or {}).get("apply"):
            rows.append(("Hints", code_links(f["hints"]["apply"])))
        review = "".join(f"<li><strong>{escape(r)}:</strong> {md(national.fill(q))}</li>"   # without purpose.country
                         for r, qs in (f.get("review") or {}).items() for q in qs)
        body = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
        out.append(f'<article class="card" id="domain-{name}"><h3><code>{name}</code></h3><dl>{body}</dl>'
                   + (f'<p class="meta">Reviewers\' questions</p><ul class="review">{review}</ul>' if review else "")
                   + "</article>")
    return "".join(out) + "</div>"


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
    out = []
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
    return "".join(out)


TABLES_ABOUT = ('The numbers the engines use. Each file names its source; a section with a source of its own shows it. '
                'Tag <code>r</code>: read from the source.')


def kinds_section():
    k = kinds()

    def names(xs):
        return ", ".join(f"<code>{escape(x)}</code>" for x in xs) or "–"
    rows = [f'<tr><td>every kind</td><td>–</td><td>{names(k["common"]["limits"])}</td><td>–</td></tr>']
    rows += [f'<tr><td><code>{kind}</code></td><td>{names(d.get("roles", []))}</td><td>{names(d.get("limits", []))}'
             f'</td><td>{names(d.get("values", []))}</td></tr>' for kind, d in k["kinds"].items()]
    units = ", ".join(f"<code>_{u}</code> {escape(v)}" for u, v in k["units"].items())
    return ('<p>What a parts entry of each kind may give; <code>edakit part lint</code> holds the entries to it. Every '
            'name ends in its unit: ' + units + '.</p>'
            '<div class="scroll"><table><thead><tr><th>Kind</th><th>Roles</th><th>Limits</th><th>Values</th></tr>'
            f'</thead><tbody>{"".join(rows)}</tbody></table></div><p>Per pin: {names(k["common"]["pin"])}; and '
            f'{names(k["free"]["pin"])}.</p>')


CIRCUITS_ABOUT = ('edakit\'s own circuits, one per domain, each added to the example and drawn by <code>edakit schematic '
                  'draw</code>. Each passes <code>edakit check</code> and <code>edakit sim</code> clean under its domains; '
                  'each seeded fault raises exactly its codes (<code>tests/test_reference.py</code>). The values are '
                  'chosen for the test, not taken from datasheets.')


def domains_on(doms):
    return " ".join(f"<code>{d}</code>" for d in doms)


def circuits_section(items):
    """The list of the reference circuits, each linking its page."""
    out = ['<div class="cards">']
    for name, about, doms, _, faults in items:
        out.append(f'<article class="card" id="circuit-{name}"><h3><a href="circuit-{name}.html">{escape(name)}</a></h3>'
                   f'<p>{md(about)}</p><p class="meta">Domains on: {domains_on(doms)} · {len(faults)} seeded faults · '
                   f'<a href="circuits/{name}.svg">SVG</a></p></article>')
    return "".join(out) + "</div>"


def circuit_body(name, about, doms, svg, faults):
    """A reference circuit's page: the drawing and its seeded faults."""
    rows = "".join(f'<tr><td>{escape(what)}</td><td>{code_links(sorted(codes))}</td></tr>' for what, _, codes in faults)
    table = (f'<table class="faults"><thead><tr><th>Seeded fault</th><th>Codes it raises</th></tr></thead>'
             f'<tbody>{rows}</tbody></table>' if faults else "")
    return (f'<article class="circuit" id="circuit-{name}"><p>{md(about)}</p><p class="meta">Domains on: '
            f'{domains_on(doms)} · <a href="circuits/{name}.svg">SVG</a></p><div class="drawing">{svg_inline(svg)}</div>'
            f'{table}</article>')


JUDGED_CHIP = {"real": "warning", "lacks": "note", "criterion": "pending", "known gap": "open"}


def links(html_text):
    """<https://…> of a README, escaped by md, as links; *words* in italics."""
    html_text = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<em>\1</em>", html_text)
    return re.sub(r"&lt;(https?://[^&\s]+)&gt;", r'<a href="\1">\1</a>', html_text)


OPEN_ABOUT = ('Real designs, transcribed from their published schematics into edakit projects '
              '(<code>tests/open_designs/</code>, maker-coverage FT-21), with parts entries from the parts\' datasheets. '
              'Every finding of <code>edakit check</code> and <code>edakit sim</code> is judged: <em>real</em> – a point '
              'of the design, <em>lacks</em> – a fact the transcription or the datasheets lack, <em>criterion</em> – '
              'edakit\'s yardstick, not the design\'s, <em>known gap</em> – edakit judges it wrong, not fixed yet. The '
              'false alarms the designs showed are fixed (<code>tests/test_open_designs.py</code>, '
              '<code>tests/test_open_design_fixes.py</code>).')


def open_designs_section(designs):
    """The list of the open designs, each linking its page."""
    out = ['<div class="cards">']
    for name, title, source, _, j in designs:
        judged = Counter(f["judged"] for key in ("check", "sim") for f in j.get(key, []))
        counts = (" ".join(chip(JUDGED_CHIP.get(k, "open"), f"{v} {k}") for k, v in judged.items())
                  or "nothing beyond notes")
        out.append(f'<article class="card" id="open-{name}"><h3><a href="open-{name}.html">{escape(title)}</a></h3>'
                   f'<p class="meta">{links(md(source))}</p><p class="meta">Findings judged: {counts}</p></article>')
    return "".join(out) + "</div>"


def open_design_body(name, title, source, svg, j):
    """An open design's page: the drawing and every finding judged."""
    rows = "".join(
        f'<tr><td>{stage}</td><td><a href="{href(f["code"])}"><code>{escape(f["code"])}</code></a>'
        + (f'/{escape(f["grade"])}' if f.get("grade") else "") + f'</td><td>{escape(f["place"])}</td>'
        f'<td>{chip(JUDGED_CHIP.get(f["judged"], "open"), f["judged"])}</td><td>{md(f["why"])}</td></tr>'
        for stage, key in (("check", "check"), ("sim", "sim")) for f in j.get(key, []))
    table = (f'<div class="scroll"><table class="faults"><thead><tr><th>Stage</th><th>Code</th><th>Where</th>'
             f'<th>Judged</th><th>Why</th></tr></thead><tbody>{rows}</tbody></table></div>' if rows
             else "<p>edakit raises nothing beyond notes.</p>")
    fixed = "".join(f"<li>{md(f['what'])}</li>" for f in j.get("fixed", []))
    return (f'<article class="circuit" id="open-{name}"><p class="meta">{links(md(source))} · '
            f'<a href="circuits/open-{name}.svg">SVG</a></p><div class="drawing">{svg_inline(svg)}</div>{table}'
            + (f'<p class="meta">edakit\'s false alarms on this design, fixed</p><ul>{fixed}</ul>' if fixed else "")
            + "</article>")


def candidates_section():
    s = tomllib.loads(STATUS.read_text(encoding="utf-8"))
    tiles, groups = [], []
    labels = {"features": "Features (FT)", "checks": "Checks (CK)", "hints": "Hints (HT)", "blocks": "Blocks (BL)",
              "review": "Reviewer questions"}
    for sec, label in labels.items():
        c = Counter(e["status"] for e in s[sec].values())
        tiles.append(f'<div class="tile"><span class="big">{c["built"]}</span><span class="of">of {len(s[sec])}</span>'
                     f'<span class="lbl">{label}</span><span class="sub">{c["partial"]} partial · {c["open"]} open'
                     + (f' · {c["out"]} out' if c["out"] else "") + '</span>'
                     "</div>")
        rows = "".join(f'<tr><td><code>{escape(k)}</code></td><td>{chip(e["status"])}</td>'
                       f'<td>{md(e.get("where", ""))}</td><td>{md(e.get("missing", ""))}</td></tr>'
                       for k, e in s[sec].items())
        groups.append(f'<h3>{label}</h3><div class="scroll"><table class="cand"><thead><tr><th>ID</th><th>Status</th>'
                      f'<th>Where</th><th>Missing</th></tr></thead><tbody>{rows}</tbody></table></div>')
    pf = s["part_facts"]
    n = sum(len(e["parts"]) for e in pf.values())
    from edakit import library
    keys = library.keys()
    drafts = [k for k in keys if "library draft" in str((library.entry(k).get("verified") or {}).get("by", ""))]
    signed = sum(1 for k in keys if library.signature(k))
    tiles.append(f'<div class="tile"><span class="big">{signed}</span><span class="of">of {len(keys)} signed</span>'
                 f'<span class="lbl">Parts library</span><span class="sub">{len(drafts)} drafts for {n} part facts · '
                 'the owner signs</span></div>')
    rows = "".join(f'<tr><td>{escape(k.replace("_", " "))}</td><td>{chip(e["status"])}</td><td>{md(e.get("where", ""))}'
                   f'</td><td>{md(e.get("missing", ""))}</td></tr>' for k, e in pf.items())
    groups.append('<h3>Part facts – the parts library</h3><div class="scroll"><table class="cand"><thead><tr><th>Group</th>'
                  f'<th>Status</th><th>Entries</th><th>Missing</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return '<div class="tiles">' + "".join(tiles) + "</div>" + "".join(groups)


CANDIDATES_ABOUT = ('The candidates of <code>docs/concepts/done/maker-coverage.md</code> and what became of them '
                    '(<code>maker-coverage-status.toml</code>). Open where a datasheet or standard could not be read, or '
                    'where the change was not a contained one.')


def old_ids_section():
    def key(old):
        return "PGESLFHB".index(old[0]), int(old[2:])
    rows = "".join(f'<tr><td>{escape(o)}</td><td>{code_links(new)}</td></tr>'
                   for o, new in sorted(catalog.old_map().items(), key=lambda x: key(x[0])))
    return ('<div class="scroll"><table><thead><tr><th>Before</th><th>Now</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


BEFORE_ABOUT = ('The IDs per stage before the restructuring and the codes that replace them; <code>edakit explain G-8'
                '</code> says the same.')


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
nav a[aria-current="page"] { color: var(--accent); font-weight: 600; }
nav .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }
nav ol.engines { display: flex; flex-wrap: wrap; gap: 0.2rem 0.7rem; }
nav ol.engines > li:has(ol.sub) { flex-basis: 100%; }
header.top h1 { font: 600 2rem/1.15 var(--display); margin: 0 0 0.4rem; text-wrap: balance; }
header.top p { color: var(--muted); max-width: 70ch; margin: 0; }
header.top p.brand { margin-bottom: 0.6rem; }
p.lead { font-size: 1.05rem; }
:target { scroll-margin-top: 1rem; }
tr:target td, tr:target th { background: color-mix(in srgb, var(--surface) 80%, var(--accent)); }
article:target { outline: 2px solid var(--accent); outline-offset: 2px; }
ul.inline { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 0.3rem 1rem; max-width: none; }
table.codes tr.sec th { background: transparent; border-bottom: 1px solid var(--ink); padding-top: 0.9rem; font-weight: 400; }
table.codes td:first-child { white-space: nowrap; }
.card h3 a { text-decoration: none; }
h2 { font: 600 1.45rem/1.2 var(--display); margin: 2.6rem 0 0.8rem; padding-top: 0.6rem; border-top: 2px solid var(--ink);
  text-wrap: balance; }
h3 { font: 600 1.1rem/1.3 var(--display); margin: 1.6rem 0 0.6rem; }
h4 { font: 600 1rem/1.3 var(--display); margin: 0; }
p, li, dd { max-width: 75ch; }
.muted, .meta { color: var(--muted); }
.brand a { display: inline-flex; align-items: center; gap: 0.5rem; }
.brand img { display: block; }
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
.chip.open { color: var(--muted); } .chip.out { color: var(--muted); text-decoration: line-through; }
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
.ecards { display: grid; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); gap: .75rem; margin: .5rem 0 1.5rem; }
.ecard { display: flex; flex-direction: column; gap: .35rem; padding: .8rem .9rem; border: 1px solid var(--line);
  border-radius: 8px; background: var(--surface); color: var(--ink); text-decoration: none; }
.ecard:hover, .ecard:focus-visible { border-color: var(--accent); }
.ehead { display: flex; align-items: baseline; gap: .4rem; font-weight: 600; }
.ehead code { font-size: 1.05rem; color: var(--accent); }
.ecount { margin-left: auto; font-size: 1.3rem; font-weight: 700; }
.edecides { font-size: .92rem; }
.esev { font-size: .8rem; color: var(--muted); }
details.group { border-top: 1px solid var(--line); padding: .4rem 0; }
details.group > summary { cursor: pointer; padding: .3rem 0; font-weight: 600; }
details.group table { margin-top: .4rem; }
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
  nav ol ol.sub { display: none; }
  article.code dl, .card dl { grid-template-columns: minmax(0, 1fr); }
  .cards { grid-template-columns: minmax(0, 1fr); }
  table.kv { min-width: 0; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
"""

SCRIPT = """
const q = document.getElementById('q');
if (q) q.addEventListener('input', () => {
  const s = q.value.trim().toLowerCase();
  document.querySelectorAll('[data-text]').forEach(a => { a.hidden = s && !a.dataset.text.includes(s); });
  document.querySelectorAll('.group').forEach(g => {
    g.hidden = s && !g.querySelector('[data-text]:not([hidden])');
    if (g.tagName === 'DETAILS') g.open = !!s && !g.hidden;
  });
});
function openTarget() {
  const id = decodeURIComponent(location.hash.slice(1));
  const el = id && document.getElementById(id);
  const d = el && el.closest('details');
  if (d) { d.open = true; el.scrollIntoView(); }
}
window.addEventListener('hashchange', openTarget);
openTarget();
"""

BRAND = ('<p class="meta brand"><a href="../"><picture><source media="(prefers-color-scheme: dark)" '
         'srcset="../brand/edakit-mark-dark.svg"><img src="../brand/edakit-mark.svg" width="28" height="28" alt="">'
         '</picture>edakit documentation</a></p>')


def nav(current, sub=()):
    """The catalog's pages, the same on each: current marked, under it sub – [(href, label, is it this page)]."""
    def item(f, title, label=None):
        here = f == current
        current_attr = ' aria-current="page"'
        inner = "".join(f'<li><a href="{h}"{current_attr if c else ""}>{escape(t)}</a></li>'
                        for h, t, c in sub) if here and sub else ""
        mark = ' aria-current="page"' if here and not any(c for *_, c in sub) else ""
        return (f'<li><a href="{f}"{mark} title="{escape(title)}">{escape(label or title)}</a>'
                + (f'<ol class="sub">{inner}</ol>' if inner else "") + "</li>")
    engines = "".join(item(f, t, t.split(" – ")[0]) for f, t in ENGINE_PAGES)
    names = {f for f, _ in ENGINE_PAGES}
    rest = [(f, t) for f, t in PAGES if f not in names]
    return ('<nav aria-label="Rule catalog"><ol>' + item(*rest[0])
            + f'<li><span class="label">Engines</span><ol class="engines">{engines}</ol></li>'
            + "".join(item(f, t) for f, t in rest[1:]) + "</ol></nav>")


def page(current, title, intro, body, sub=(), h1=None):
    """A page of the catalog: the brand, the navigation, its title and intro, its body."""
    head = title if title == "edakit rule catalog" else f"{title} – edakit rule catalog"
    return ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>{escape(head)}</title>'
            '<link rel="icon" type="image/svg+xml" href="../brand/edakit-favicon.svg">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" '
            'href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&display=swap">'
            f'<style>{CSS}</style></head><body><div class="layout">{nav(current, sub)}<main>'
            f'<header class="top">{BRAND}<h1>{h1 or escape(title)}</h1>' + (f'<p>{intro}</p>' if intro else "")
            + f'</header>{body}<footer>Written by <code>docs/catalog/build.py</code>; <code>tests/test_catalog_page.py'
            '</code> holds it to the catalog.</footer></main></div>'
            f'<script>{SCRIPT}</script></body></html>\n')


def index_body(items, designs):
    """The index: the counters, the engines, every code in one list, and the rest of the catalog by name – every
    anchor of the one page before (a code, engine-, domain-, table-, circuit-, open-) lands on a row here."""
    codes = catalog.codes()
    grades = sum(len(e.get("grades") or {}) for e in codes.values())
    sources = len({s for e in codes.values() for s in e.get("sources", [])})
    tiles = "".join(f'<div class="tile"><span class="big">{v}</span><span class="lbl">{k}</span></div>' for k, v in (
        ("Engines", len(catalog.engines())), ("Codes", len(codes)), ("Grades", grades),
        ("Hints", sum(1 for n in codes if n.startswith("HINT."))), ("Domains", len(profile.domains())),
        ("Sources cited", sources), ("Reference circuits", len(items)), ("Open designs", len(designs))))

    def row(label, f, entries):
        return (f'<h3><a href="{f}">{label}</a></h3><ul class="inline">'
                + "".join(f'<li id="{i}"><a href="{h}">{t}</a></li>' for i, h, t in entries) + "</ul>")
    more = ('<section id="more"><h2>The rest of the catalog</h2>'
            + row("Domains", "domains.html", [(f"domain-{n}", f"domains.html#domain-{n}", f"<code>{n}</code>")
                                              for n in profile.domains()])
            + row("Tables", "tables.html", [(f"table-{n}", f"tables.html#table-{n}", f"<code>{n}</code>")
                                            for n in catalog.table_names()])
            + '<p><a href="schema.html">Parts schema</a> – what a parts entry of each kind may give.</p>'
            + row("Reference circuits", "circuits.html", [(f"circuit-{n}", f"circuit-{n}.html", escape(n))
                                                          for n, *_ in items])
            + row("Published open designs", "open-designs.html", [(f"open-{n}", f"open-{n}.html", escape(t))
                                                                 for n, t, *_ in designs])
            + '<p><a href="candidates.html">maker-coverage candidates</a> – what became of them; '
              '<a href="before.html">check IDs of before</a> – the codes that replace them.</p></section>')
    return f'<div class="tiles">{tiles}</div>' + engines_section() + codes_section() + more


INDEX_ABOUT = ('Every rule edakit checks – engine, code, severity, rule, why, what to do and its sources –, the domains '
               'that switch rules on, the tables of numbers, the parts schema, the reference circuits with their seeded '
               'faults, published open designs with every finding judged, and what became of the maker-coverage '
               'candidates. Generated from <code>edakit/catalog</code>, <code>edakit/domains</code>, '
               '<code>tests/reference.py</code> and <code>tests/open_designs/</code>.')


def pages(items, designs):
    """{file name: html} of every page."""
    titles = dict(PAGES)
    out = {"index.html": page("index.html", "edakit rule catalog", INDEX_ABOUT, index_body(items, designs))}
    for eng, e in catalog.engines().items():
        f = f'{e["prefix"].lower()}.html'
        names = [n for n in catalog.codes() if catalog.engine_of(n) == eng]
        out[f] = page(f, titles[f], "", engine_body(eng, e), [(f"#{n}", n, False) for n in names],
                      h1=f'<code>{e["prefix"]}</code>' + ("" if eng == e["prefix"] else f" {escape(eng.lower())}"))
    out["domains.html"] = page("domains.html", "Domains", DOMAINS_ABOUT, domains_section())
    out["tables.html"] = page("tables.html", "Tables", TABLES_ABOUT, tables_section(),
                              [(f"#table-{n}", n, False) for n in catalog.table_names()])
    out["schema.html"] = page("schema.html", "Parts schema", "", kinds_section())
    circuit_nav = [(f"circuit-{n}.html", n, False) for n, *_ in items]
    out["circuits.html"] = page("circuits.html", "Reference circuits", CIRCUITS_ABOUT, circuits_section(items),
                                circuit_nav)
    for it in items:
        n = it[0]
        out[f"circuit-{n}.html"] = page("circuits.html", f"{n} – reference circuit", "", circuit_body(*it),
                                        [(h, t, t == n) for h, t, _ in circuit_nav],
                                        h1=f'{escape(n)} <span class="muted">– reference circuit</span>')
    open_nav = [(f"open-{n}.html", t, False) for n, t, *_ in designs]
    out["open-designs.html"] = page("open-designs.html", "Published open designs", OPEN_ABOUT,
                                    open_designs_section(designs), open_nav)
    for d in designs:
        n, t = d[0], d[1]
        out[f"open-{n}.html"] = page("open-designs.html", t, "", open_design_body(*d),
                                     [(h, x, h == f"open-{n}.html") for h, x, _ in open_nav])
    out["candidates.html"] = page("candidates.html", "maker-coverage candidates", CANDIDATES_ABOUT,
                                  candidates_section())
    out["before.html"] = page("before.html", "Check IDs of before", BEFORE_ABOUT, old_ids_section())
    return out


def build(out=OUT):
    """Write the pages and the drawings into out; -> the files written."""
    out = Path(out)
    (out / "circuits").mkdir(parents=True, exist_ok=True)
    items, designs = circuits(), open_designs()
    written = []
    for name, html in pages(items, designs).items():
        f = out / name
        f.write_text(html, encoding="utf-8")
        written.append(f)
    for name, _, _, svg, _ in items:
        f = out / "circuits" / f"{name}.svg"
        f.write_text(svg, encoding="utf-8")
        written.append(f)
    for name, _, _, svg, _ in designs:
        f = out / "circuits" / f"open-{name}.svg"
        f.write_text(svg, encoding="utf-8")
        written.append(f)
    return written


if __name__ == "__main__":
    for f in build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT):
        print(f"written: {f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}"
              f" ({f.stat().st_size // 1024} KB)")
