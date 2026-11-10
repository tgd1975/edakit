"""The language server of the circuit language (T.25): `edakit lsp`, on pygls (the optional extra lsp), over the
reader and the compiler the command line uses.

    diagnostics(path, text)          the reader's and the compiler's errors, and the findings of the graph engines on
                                     the compiled graph located at their statements (locate.py)
    definition(path, text, line, col)   a pin word to its parts entry, a usage to its definition, a net to its first
                                     statement, an include to its file
    hover(path, text, line, col)     a part's entry – kind, limits, values –, a pin's number, name and role, a net's
                                     range and pins
    completion(path, text, line, col)   pin words after `DES.`, codes after `accept`, definitions after `use`, else
                                     keywords, designators and nets
    formatted(path, text)            the canonical layout (fmt.py)

Positions are 0-based, as the protocol counts them. The functions take the editor's text, saved or not. In a file
whose project has not switched the explorative DSL on ([beta] dsl = true, edakit/beta.py) the diagnostics are that
one line and the rest answers nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

from .compile import build_text, load_parts, project_of
from .reader import KEYWORDS, CompileError, read

WORD = re.compile(r'[^\s"#]+')


def _project(path):
    root, dirs = project_of(path)
    return root, dirs, load_parts(dirs)


def _rel(path, root):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def compiled(path, text):
    """(graph, SourceMap, Design, errors) of a text at a path – errors a list of LangError, the rest None on error."""
    root, dirs, parts = _project(path)
    try:
        graph, smap, design = build_text(text, Path(path), root, parts)
        return graph, smap, design, []
    except CompileError as e:
        return None, None, None, list(e.errors)


def _off(path):
    from ..beta import dsl_of
    return not dsl_of(path)


def diagnostics(path, text):
    """[{line, col, end, message, severity, code}] of a source."""
    if _off(path):
        from ..beta import refusal
        return [{"line": 0, "col": 0, "end": 0, "message": refusal(Path(path).name), "severity": "warning",
                 "code": ""}]
    root = project_of(path)[0]
    me = _rel(path, root)
    graph, smap, design, errors = compiled(path, text)
    out = []
    lines = text.splitlines()
    for e in errors:
        if e.file not in (me, Path(path).name, str(path)):
            continue
        ln = max(e.line - 1, 0)
        out.append({"line": ln, "col": 0, "end": len(lines[ln]) if ln < len(lines) else 0, "message": e.text,
                    "severity": "error", "code": ""})
    if errors or design is None:
        return out
    from .. import engines
    from .locate import locate
    try:
        from ..config import ConfigError, load
        cfg = load(root / "edakit.toml") if (root / "edakit.toml").is_file() else None
    except ConfigError:
        cfg = None
    if cfg is not None:                                 # the boards of the project, as edakit check sees them
        from ..graph_form import design_of
        design = design_of(Path(path), design.parts, list(cfg.boards), graph)
    report = engines.run(design, cfg)
    for f in report.findings:
        if f.accepted or f.severity not in ("error", "warning", "pending"):
            continue
        at = locate(smap, f)
        if at is None or at[0] != me:
            continue
        ln = at[1] - 1
        out.append({"line": ln, "col": 0, "end": len(lines[ln]) if ln < len(lines) else 0,
                    "message": f"{f.code}{'/' + f.grade if f.grade else ''}: {f.text}",
                    "severity": "warning" if f.severity != "error" else "error", "code": f.code})
    return out


def word_at(text, line, col):
    lines = text.splitlines()
    if line >= len(lines):
        return "", 0
    for m in WORD.finditer(lines[line]):
        if m.start() <= col <= m.end():
            return m.group(0), m.start()
    return "", col


def _entry_path(dirs, key):
    for d in dirs:
        p = Path(d) / f"{key}.json"
        if p.exists():
            return p
    from .blocks import PARTS
    p = PARTS / f"{key}.json"
    return p if p.exists() else None


def definition(path, text, line, col):
    """(file, 0-based line) the word at the position names, or None."""
    if _off(path):
        return None
    word, _ = word_at(text, line, col)
    root, dirs, _ = _project(path)
    src = read(text, _rel(path, root))
    lines = text.splitlines()
    head = lines[line].split() if line < len(lines) else []
    if head[:1] == ["include"] and len(head) > 1:
        target = (root / head[1]).resolve()
        return (str(target), 0) if target.exists() else None
    if head[:1] == ["use"] and len(head) > 1 and word == head[1]:
        for st in src.statements:
            if type(st).__name__ == "Def" and st.name == word:
                return str(path), st.line - 1
        from .blocks import sources
        blk = sources().get(word)
        return (str(blk), 0) if blk else None
    graph, smap, design, _ = compiled(path, text)
    if "." in word and design is not None:
        des = word.partition(".")[0]
        key = design.entry_key(des) if des in design.comps else None
        hit = _entry_path(dirs, key) if key else None
        return (str(hit), 0) if hit else None
    if smap is not None:
        for kind in ("nets", "components"):
            entry = getattr(smap, kind).get(word)
            if entry:
                return str((root / entry["file"]).resolve()), entry["line"] - 1
    return None


def hover(path, text, line, col):
    """Markdown for the word at the position, or None."""
    if _off(path):
        return None
    word, _ = word_at(text, line, col)
    graph, smap, design, _ = compiled(path, text)
    if design is None or not word:
        return None
    des, dot, pin = word.partition(".")
    if des in design.comps:
        part = design.part(des) or {}
        lines = [f"**{des}** – {design.comps[des].get('type', '')}, entry {design.entry_key(des) or 'none'}"
                 f" ({part.get('kind', '')})"]
        if dot:
            nums = design.resolve(des, pin)
            roles = design._roles(des)
            for n in nums:
                name = (design.comps[des].get("pins") or {}).get(n, "")
                lines.append(f"pin {n}: {name}" + (f", role {roles.get(n)}" if roles.get(n) else "") +
                             f" – net {design.pin_net.get(f'{des}.{n}', 'none')}")
        for k in ("limits", "values"):
            if part.get(k):
                lines.append(f"{k}: " + ", ".join(f"{a} = {b}" for a, b in part[k].items()))
        return "\n\n".join(lines)
    if word in design.nets:
        n = design.nets[word]
        v = n.get("v")
        rng = f"{v[0]:g} … {v[1]:g} V" if isinstance(v, list) and len(v) == 2 else "no range"
        return f"**{word}** – {rng}\n\n" + ", ".join(design.pin_text(r) for r in n["pins"])
    return None


def completion(path, text, line, col):
    """[label] for the position."""
    if _off(path):
        return []
    lines = text.splitlines()
    before = lines[line][:col] if line < len(lines) else ""
    graph, smap, design, _ = compiled(path, text)
    m = re.search(r"([A-Za-z_{][^\s.\"#]*)\.([^\s\"#]*)$", before)
    if m and design is not None and m.group(1) in design.comps:
        des = m.group(1)
        pins = design.comps[des].get("pins") or {}
        roles = design._roles(des)
        words = list(dict.fromkeys([*[str(v) for v in pins.values()], *[r for r in roles.values() if r], *pins]))
        return [w for w in words if w.startswith(m.group(2)) and not re.search(r'[\s"#]', w)]
    if re.search(r"\baccept\s+\S*$", before):
        from ..catalog import codes
        return sorted(codes())
    if re.match(r"\s*use\s+\S*$", before):
        from .blocks import sources
        own = [st.name for st in read(text, "x").statements if type(st).__name__ == "Def"]
        return sorted(set(own) | set(sources()))
    out = sorted(KEYWORDS)
    if design is not None:
        out += sorted(design.comps) + sorted(design.nets)
    return out


def formatted(path, text):
    from .fmt import format
    if _off(path):
        return None
    try:
        return format(text, str(path))
    except CompileError:
        return None


# --- the protocol -----------------------------------------------------------------------------------------------------
def serve():
    """Run the server over stdio; ImportError without pygls."""
    from lsprotocol import types as t
    from pygls.lsp.server import LanguageServer
    from pygls.uris import to_fs_path

    server = LanguageServer("edakit-circuit", "1")
    severity = {"error": t.DiagnosticSeverity.Error, "warning": t.DiagnosticSeverity.Warning}

    def publish(uri):
        doc = server.workspace.get_text_document(uri)
        path = to_fs_path(uri)
        diags = [t.Diagnostic(range=t.Range(t.Position(d["line"], d["col"]), t.Position(d["line"], d["end"])),
                              message=d["message"], severity=severity[d["severity"]], source="edakit",
                              code=d["code"] or None) for d in diagnostics(path, doc.source)]
        server.text_document_publish_diagnostics(t.PublishDiagnosticsParams(uri=uri, diagnostics=diags))

    @server.feature(t.TEXT_DOCUMENT_DID_OPEN)
    def did_open(ls, params):
        publish(params.text_document.uri)

    @server.feature(t.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls, params):
        publish(params.text_document.uri)

    @server.feature(t.TEXT_DOCUMENT_DID_SAVE)
    def did_save(ls, params):
        publish(params.text_document.uri)

    @server.feature(t.TEXT_DOCUMENT_DEFINITION)
    def go_to(ls, params):
        doc = server.workspace.get_text_document(params.text_document.uri)
        hit = definition(to_fs_path(params.text_document.uri), doc.source, params.position.line,
                         params.position.character)
        if hit is None:
            return None
        return t.Location(uri=Path(hit[0]).resolve().as_uri(), range=t.Range(t.Position(hit[1], 0),
                                                                              t.Position(hit[1], 0)))

    @server.feature(t.TEXT_DOCUMENT_HOVER)
    def on_hover(ls, params):
        doc = server.workspace.get_text_document(params.text_document.uri)
        text = hover(to_fs_path(params.text_document.uri), doc.source, params.position.line,
                     params.position.character)
        return t.Hover(contents=t.MarkupContent(kind=t.MarkupKind.Markdown, value=text)) if text else None

    @server.feature(t.TEXT_DOCUMENT_COMPLETION)
    def on_complete(ls, params):
        doc = server.workspace.get_text_document(params.text_document.uri)
        items = completion(to_fs_path(params.text_document.uri), doc.source, params.position.line,
                           params.position.character)
        return t.CompletionList(is_incomplete=False, items=[t.CompletionItem(label=x) for x in items])

    @server.feature(t.TEXT_DOCUMENT_FORMATTING)
    def on_format(ls, params):
        doc = server.workspace.get_text_document(params.text_document.uri)
        new = formatted(to_fs_path(params.text_document.uri), doc.source)
        if new is None or new == doc.source:
            return []
        end = len(doc.source.splitlines())
        return [t.TextEdit(range=t.Range(t.Position(0, 0), t.Position(end + 1, 0)), new_text=new)]

    server.start_io()


def main(args=None):
    try:
        serve()
    except ImportError:
        import sys
        print("edakit lsp: the language server needs pygls – install edakit with its extra lsp "
              "(uv tool install 'edakit[lsp]', or pip install 'pygls>=2.0')", file=sys.stderr)
        return 1
    return 0
