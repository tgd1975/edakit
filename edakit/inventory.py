"""The maker's parts on hand: an inventory table read and compared, never written (docs/concepts/done/parts-on-hand.md).

    edakit inventory [QUERY ...]          every hand-soldered part and extra against the inventory; with QUERY the rows
                                          whose ID, name or description hold every word
    edakit inventory template FILE        a new empty inventory (.md, .xlsx, .ods), named in edakit.local.toml

The inventory is named in edakit.local.toml beside edakit.toml – this checkout's, in .gitignore, never in a repository:

    [inventory]
    files = ["~/Teile/inventory.xlsx", "~/Teile/inventory_*.md"]   one path or a list of paths and globs
    lcsc_map = "~/Teile/lcsc.csv"                                  optional: ID -> LCSC, the inventory left as it is
    [inventory.columns]                                            optional: the maker's own column names
    id = "Teil"
    quantity = "Anzahl"

A file is .md (every pipe table), .html/.htm (every <table>), .csv (the file), .xlsx or .ods (every sheet); a table
counts when its header row – the first row, in a sheet the first non-empty one – has the columns ID and Quantity
(compared without case and surrounding blanks); other tables, sheets and columns are ignored. LCSC, Name, Description
and Link are read where present. A row is a part when its LCSC number – the column, else the map by ID – is the line's,
or else its ID is the line's MPN, case and blanks ignored; the same part in several rows or files is summed.

Not set: nothing changes. A file that is not there, a glob that matches nothing, a file without a matching table, a
quantity that is no whole number >= 0, an ID mapped to two LCSC numbers: InventoryError, and edakit order stops before
it writes a cart.
"""

from __future__ import annotations

import csv
import datetime as dt
import glob
import io
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

LOCAL = "edakit.local.toml"
COLUMNS = ("id", "name", "lcsc", "quantity", "description", "link")   # the template's order
DEFAULT_NAMES = {"id": "ID", "name": "Name", "lcsc": "LCSC", "quantity": "Quantity", "description": "Description",
                 "link": "Link"}
REQUIRED = ("id", "quantity")
INVENTORY_KEYS = ("files", "lcsc_map", "columns")
READS = (".md", ".html", ".htm", ".csv", ".xlsx", ".ods")
TEMPLATES = (".md", ".xlsx", ".ods")


class InventoryError(Exception):
    pass


# --- settings ---------------------------------------------------------------------------------------------------------

@dataclass
class Settings:
    local: Path                       # edakit.local.toml
    files: list = field(default_factory=list)    # [Path], globs resolved
    lcsc_map: Path | None = None
    names: dict = field(default_factory=lambda: dict(DEFAULT_NAMES))   # column -> its name in the files
    raw_files: list = field(default_factory=list)

    def show(self, p: Path) -> str:
        return shown(p, self.local.parent)


def shown(p: Path, base: Path) -> str:
    """A path as the maker reads it: relative to the project, else from ~, else absolute."""
    for root, head in ((base, ""), (Path.home(), "~/")):
        try:
            return head + p.relative_to(root).as_posix()
        except ValueError:
            pass
    return p.as_posix()


def norm(text) -> str:
    """A cell compared: blanks gone, case folded."""
    return re.sub(r"\s+", "", str(text or "")).casefold()


def _resolve(base: Path, text: str) -> Path:
    p = Path(os.path.expanduser(text))
    return p if p.is_absolute() else base / p


def settings(cfg) -> Settings | None:
    """The [inventory] of edakit.local.toml beside the project's edakit.toml; None when there is none."""
    base = cfg.path.parent
    local = base / LOCAL
    if not local.exists():
        return None
    try:
        data = tomllib.loads(local.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise InventoryError(f"{LOCAL}: {e}") from None
    bad = [f"unknown table or key '{k}'" for k in data if k != "inventory"]
    inv = data.get("inventory")
    if inv is None:
        if bad:
            raise InventoryError(f"{LOCAL}: " + "; ".join(bad) + " – it knows [inventory]")
        return None
    if not isinstance(inv, dict):
        raise InventoryError(f"{LOCAL}: inventory must be a table")
    bad += [f"unknown key 'inventory.{k}'" for k in inv if k not in INVENTORY_KEYS]
    files = inv.get("files", [])
    if isinstance(files, str):
        files = [files]
    if not isinstance(files, list) or not all(isinstance(f, str) and f for f in files):
        bad.append("inventory.files must be a path or a list of paths")
        files = []
    names = dict(DEFAULT_NAMES)
    cols = inv.get("columns", {})
    if not isinstance(cols, dict):
        bad.append("inventory.columns must be a table")
        cols = {}
    for k, v in cols.items():
        if k not in DEFAULT_NAMES:
            bad.append(f"unknown column 'inventory.columns.{k}' (known: {', '.join(COLUMNS)})")
        elif not isinstance(v, str) or not v.strip():
            bad.append(f"inventory.columns.{k} must be a column name")
        else:
            names[k] = v.strip()
    taken = {}
    for k, v in names.items():
        if norm(v) in taken:
            bad.append(f"columns {taken[norm(v)]} and {k} have the same name '{v}'")
        taken[norm(v)] = k
    lmap = inv.get("lcsc_map")
    if lmap is not None and not (isinstance(lmap, str) and lmap):
        bad.append("inventory.lcsc_map must be a path")
        lmap = None
    if bad:
        raise InventoryError(f"{LOCAL}: " + "; ".join(bad))
    s = Settings(local=local, names=names, raw_files=list(files),
                 lcsc_map=_resolve(base, lmap) if lmap else None)
    if not files:
        return s
    for f in files:
        p = _resolve(base, f)
        if any(ch in f for ch in "*?["):
            hits = sorted(Path(x) for x in glob.glob(str(p)) if Path(x).is_file())
            if not hits:
                raise InventoryError(f"inventory: {f} matches no file ({LOCAL})")
            s.files += [h for h in hits if h not in s.files]
        else:
            if not p.is_file():
                raise InventoryError(f"inventory: {f} not found ({LOCAL})")
            if p not in s.files:
                s.files.append(p)
    return s


def tracked(cfg) -> bool:
    """Whether git tracks edakit.local.toml – then the inventory's paths are in the repository after all."""
    try:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", LOCAL], cwd=cfg.path.parent,
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


# --- reading the formats ----------------------------------------------------------------------------------------------
# A table: (where, [(row number, [cell, ...]), ...]) – where names the table or sheet, the row number is the file's
# line (.md, .html, .csv) or the sheet's row (.xlsx, .ods). A cell is a string, an int or a float.

LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def _md_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells = re.split(r"(?<!\\)\|", s)
    return [LINK.sub(r"\1", c.replace("\\|", "|")).strip() for c in cells]


SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def read_md(text):
    tables, lines, i, fence = [], text.splitlines(), 0, False
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and "|" in line and i + 1 < len(lines) and SEPARATOR.match(lines[i + 1]):
            rows = [(i + 1, _md_cells(line))]
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append((j + 1, _md_cells(lines[j])))
                j += 1
            tables.append((f"table at line {i + 1}", rows))
            i = j
            continue
        i += 1
    return tables


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack = [], []        # stack: [where, rows, row, cell]

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append([f"table at line {self.getpos()[0]}", [], None, None])
        elif not self.stack:
            return
        elif tag == "tr":
            self.stack[-1][2] = (self.getpos()[0], [])
        elif tag in ("td", "th") and self.stack[-1][2] is not None:
            self.stack[-1][3] = []
        elif tag == "br" and self.stack[-1][3] is not None:
            self.stack[-1][3].append(" ")

    def handle_endtag(self, tag):
        if not self.stack:
            return
        t = self.stack[-1]
        if tag in ("td", "th") and t[3] is not None:
            t[2][1].append(" ".join("".join(t[3]).split()))
            t[3] = None
        elif tag == "tr" and t[2] is not None:
            t[1].append(t[2])
            t[2] = None
        elif tag == "table":
            self.stack.pop()
            self.tables.append((t[0], t[1]))

    def handle_data(self, data):
        if self.stack and self.stack[-1][3] is not None:
            self.stack[-1][3].append(data)


def read_html(text):
    p = _Html()
    p.feed(text)
    p.close()
    return p.tables


def decode(raw: bytes) -> str:
    """UTF-8 (with or without BOM), else Windows-1252 – what a German Excel writes as 'CSV'."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def read_csv(raw: bytes):
    text = decode(raw)
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    delim = max(";,\t", key=first.count) if any(d in first for d in ";,\t") else ","
    rows = [(n, row) for n, row in enumerate(csv.reader(io.StringIO(text), delimiter=delim), 1)]
    return [("the file", rows)]


def read_xlsx(path: Path):
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:      # openpyxl raises zipfile, KeyError and its own errors for a broken file
        raise InventoryError(f"inventory: {path} is no readable .xlsx ({e})") from None
    tables = []
    try:
        for ws in wb.worksheets:
            rows = [(n, ["" if v is None else v for v in r]) for n, r in enumerate(ws.iter_rows(values_only=True), 1)]
            tables.append((f"sheet '{ws.title}'", rows))
    finally:
        wb.close()
    return tables


def formula(path: Path, where: str, row: int, col: int):
    """The formula in an .xlsx cell whose saved value is empty – a file no office program has saved yet."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
        ws = wb[where.split("'")[1]]
        v = ws.cell(row=row, column=col + 1).value
        wb.close()
    except Exception:
        return None
    return v if isinstance(v, str) and v.startswith("=") else None


NS = {"table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
      "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
      "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}


def _q(prefix, name):
    return f"{{{NS[prefix]}}}{name}"


def _ods_walk(node):
    out = [node.text or ""]
    for ch in node:
        if ch.tag == _q("text", "s"):
            out.append(" " * int(ch.get(_q("text", "c"), "1")))
        elif ch.tag == _q("text", "tab"):
            out.append("\t")
        elif ch.tag == _q("text", "line-break"):
            out.append("\n")
        else:
            out.append(_ods_walk(ch))
        out.append(ch.tail or "")
    return "".join(out)


def _ods_text(cell):
    return "\n".join(_ods_walk(p) for p in cell.findall(_q("text", "p")))


def _ods_value(cell):
    kind = cell.get(_q("office", "value-type"))
    if kind in ("float", "percentage", "currency"):
        v = float(cell.get(_q("office", "value")))
        return int(v) if v.is_integer() else v
    return _ods_text(cell).strip()


def read_ods(path: Path):
    try:
        with zipfile.ZipFile(path) as z:
            root = ET.fromstring(z.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise InventoryError(f"inventory: {path} is no readable .ods ({e})") from None
    tables = []
    for t in root.iter(_q("table", "table")):
        rows, n = [], 0
        for r in t.iter(_q("table", "table-row")):
            rep = int(r.get(_q("table", "number-rows-repeated"), "1"))
            cells, col = {}, 0
            for c in r:
                if c.tag not in (_q("table", "table-cell"), _q("table", "covered-table-cell")):
                    continue
                crep = int(c.get(_q("table", "number-columns-repeated"), "1"))
                v = _ods_value(c)
                if v != "":
                    for k in range(crep):
                        cells[col + k] = v
                col += crep
            if cells:
                row = [cells.get(k, "") for k in range(max(cells) + 1)]
                for k in range(rep):
                    rows.append((n + k + 1, list(row)))
            n += rep
        tables.append((f"sheet '{t.get(_q('table', 'name'))}'", rows))
    return tables


def read_tables(path: Path):
    ext = path.suffix.lower()
    if ext not in READS:
        raise InventoryError(f"inventory: {path.name} – edakit reads {', '.join(READS)}")
    if ext == ".xlsx":
        return read_xlsx(path)
    if ext == ".ods":
        return read_ods(path)
    raw = path.read_bytes()
    if ext == ".csv":
        return read_csv(raw)
    text = decode(raw)
    return read_md(text) if ext == ".md" else read_html(text)


# --- the inventory ----------------------------------------------------------------------------------------------------

@dataclass
class Row:
    file: Path
    where: str
    line: int
    id: str
    quantity: int
    lcsc: str = ""
    name: str = ""
    description: str = ""
    link: str = ""

    def place(self, base):
        return f"{shown(self.file, base)}, {self.where}, row {self.line}"

    def text(self):
        words = " – ".join(x for x in (self.name, self.description) if x)
        return f"{self.id}" + (f" ({words})" if words else "")


def _cell(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    return str(v).strip() if v is not None else ""


def quantity(v):
    """A whole number >= 0 from a cell, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if v >= 0 else None
    if isinstance(v, float):
        return int(v) if v.is_integer() and v >= 0 else None
    s = str(v).strip()
    if re.fullmatch(r"\d+", s):
        return int(s)
    if re.fullmatch(r"\d+[.,]0+", s):
        return int(re.split(r"[.,]", s)[0])
    return None


def lcsc_code(text) -> str:
    s = re.sub(r"\s+", "", str(text or "")).upper()
    return s


def header(rows):
    """The header row of a table: its first row with a cell that is not empty."""
    for k, (n, cells) in enumerate(rows):
        if any(_cell(c) for c in cells):
            return k, n, cells
    return None, None, []


def columns(cells, names, need):
    """{column: index} of a header row, or None when one of `need` is missing."""
    index = {norm(_cell(c)): i for i, c in reversed(list(enumerate(cells)))}
    found = {k: index[norm(v)] for k, v in names.items() if norm(v) in index}
    return found if all(k in found for k in need) else None


def _tables_of(path, names, need, what, show=str):
    """[(where, {column: index}, [(row number, cells)])] of every table of a file with the columns `need`."""
    out, seen = [], []
    for where, rows in read_tables(path):
        k, n, cells = header(rows)
        if k is None:
            continue
        cols = columns(cells, names, need)
        if cols is None:
            seen.append(f"{where}: {', '.join(_cell(c) for c in cells if _cell(c)) or '–'}")
            continue
        out.append((where, cols, rows[k + 1:]))
    if not out:
        want = ", ".join(names[k] for k in need)
        raise InventoryError(f"{what}: {show(path)} has no table with the columns {want}"
                             + (" – found " + "; ".join(seen[:8]) + (" …" if len(seen) > 8 else "") if seen
                                else " – it has no table at all"))
    return out


def read_map(path: Path, names, show=str) -> dict:
    """ID (normalized) -> LCSC number from the LCSC map."""
    if not path.is_file():
        raise InventoryError(f"inventory: the LCSC map {show(path)} not found ({LOCAL})")
    out, first = {}, {}
    for where, cols, rows in _tables_of(path, names, ("id", "lcsc"), "the LCSC map", show):
        for n, cells in rows:
            get = lambda k: _cell(cells[cols[k]]) if cols[k] < len(cells) else ""   # noqa: E731
            key, code = norm(get("id")), lcsc_code(get("lcsc"))
            if not key or not code:
                continue
            if key in out and out[key] != code:
                raise InventoryError(f"the LCSC map: {get('id')} is mapped to {out[key]} ({first[key]}) and to {code} "
                                     f"({show(path)}, {where}, row {n})")
            out[key], first[key] = code, f"{where}, row {n}"
    return out


def read(s: Settings) -> list[Row]:
    """Every row of every inventory file; InventoryError for a file without a matching table or a bad quantity."""
    lmap = read_map(s.lcsc_map, s.names, s.show) if s.lcsc_map else {}
    out, bad = [], []
    for path in s.files:
        for where, cols, rows in _tables_of(path, s.names, REQUIRED, "inventory", s.show):
            for n, cells in rows:
                get = lambda k: (cells[cols[k]] if k in cols and cols[k] < len(cells) else "")   # noqa: E731
                ident, raw = _cell(get("id")), get("quantity")
                if not ident and not _cell(raw):
                    continue          # a blank row
                q = quantity(raw)
                if not ident:
                    bad.append(f"{s.show(path)}, {where}, row {n}: no {s.names['id']}")
                    continue
                if q is None:
                    why = f"'{_cell(raw)}' is no whole number >= 0" if _cell(raw) else "empty"
                    if not _cell(raw) and path.suffix.lower() == ".xlsx":
                        f = formula(path, where, n, cols["quantity"])
                        if f:
                            why = (f"the formula {f} has no saved value – open the file in Excel or LibreOffice and "
                                   "save it")
                    bad.append(f"{s.show(path)}, {where}, row {n} ({ident}): {s.names['quantity']} {why}")
                    continue
                code = lcsc_code(_cell(get("lcsc"))) or lmap.get(norm(ident), "")
                out.append(Row(path, where, n, ident, q, code, _cell(get("name")), _cell(get("description")),
                               _cell(get("link"))))
    if bad:
        raise InventoryError("inventory: " + "; ".join(bad[:10]) + (f" (and {len(bad) - 10} more)" if len(bad) > 10
                                                                     else ""))
    return out


class Stock:
    """What is left on hand while lines take from it: LCSC number first, else the MPN; one row is never counted twice."""

    def __init__(self, rows):
        self.rows = rows
        self.left = {id(r): r.quantity for r in rows}

    def matches(self, lcsc, mpn):
        by_lcsc = [r for r in self.rows if lcsc and r.lcsc and r.lcsc == lcsc_code(lcsc)]
        if by_lcsc:
            return by_lcsc
        return [r for r in self.rows if mpn and norm(r.id) == norm(mpn)]

    def on_hand(self, lcsc, mpn):
        return sum(self.left[id(r)] for r in self.matches(lcsc, mpn))

    def take(self, lcsc, mpn, n):
        """Takes up to n pieces; [(row, pieces)]."""
        got = []
        for r in self.matches(lcsc, mpn):
            k = min(self.left[id(r)], n - sum(p for _, p in got))
            if k > 0:
                self.left[id(r)] -= k
                got.append((r, k))
        return got


def load(cfg):
    """(Settings, Stock) of the project, or (None, None) when edakit.local.toml names no inventory."""
    s = settings(cfg)
    if s is None or not s.files:
        return s, None
    return s, Stock(read(s))


# --- the template -----------------------------------------------------------------------------------------------------

MD_TEMPLATE = """# Inventory

The parts on hand – read by edakit (edakit inventory, edakit order), never written. One row per part and place;
{quantity} a whole number. {lcsc} or an MPN as {id} lets edakit match a row to a part.

| {cols} |
| {seps} |
"""

ODS_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
"""


def _xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def ods_bytes(head):
    cells = "".join(f'<table:table-cell office:value-type="string"><text:p>{_xml(h)}</text:p></table:table-cell>'
                    for h in head)
    content = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               f'<office:document-content xmlns:office="{NS["office"]}" xmlns:table="{NS["table"]}" '
               f'xmlns:text="{NS["text"]}" office:version="1.2"><office:body><office:spreadsheet>'
               f'<table:table table:name="Inventory"><table:table-column table:number-columns-repeated="{len(head)}"/>'
               f'<table:table-row>{cells}</table:table-row></table:table></office:spreadsheet></office:body>'
               '</office:document-content>\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.spreadsheet",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", ODS_MANIFEST, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def write_template(path: Path, names):
    head = [names[k] for k in COLUMNS]
    ext = path.suffix.lower()
    if ext == ".md":
        path.write_text(MD_TEMPLATE.format(cols=" | ".join(head), seps=" | ".join("---" for _ in head),
                                           **{k: f"`{names[k]}`" for k in ("quantity", "lcsc", "id")}),
                        encoding="utf-8")
    elif ext == ".xlsx":
        import openpyxl
        from openpyxl.styles import Font
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Inventory"
        ws.append(head)
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for col, w in zip("ABCDEF", (16, 24, 12, 10, 40, 40)):
            ws.column_dimensions[col].width = w
        wb.save(path)
    else:
        path.write_bytes(ods_bytes(head))


def name_in_local(base: Path, text: str):
    """Writes files = [text] into edakit.local.toml unless it names files already; (written, note)."""
    local = base / LOCAL
    line = f"files = [{_toml_str(text)}]   # the parts on hand (edakit inventory, edakit order)\n"
    if not local.exists():
        local.write_text("# this checkout's settings – in .gitignore, never in a repository (handbook 10.1)\n"
                         "[inventory]\n" + line, encoding="utf-8")
        return True, f"{LOCAL}: written"
    text_now = local.read_text(encoding="utf-8")
    data = tomllib.loads(text_now)
    inv = data.get("inventory")
    if inv and inv.get("files"):
        return False, f"{LOCAL} names other files already – add {text} to inventory.files by hand"
    if inv is None:
        local.write_text(text_now.rstrip("\n") + ("\n\n" if text_now.strip() else "") + "[inventory]\n" + line,
                         encoding="utf-8")
    else:
        local.write_text(re.sub(r"^\[inventory\][^\n]*\n", lambda m: m.group(0) + line, text_now, count=1,
                                flags=re.M), encoding="utf-8")
    tomllib.loads(local.read_text(encoding="utf-8"))
    return True, f"{LOCAL}: inventory.files set"


def _toml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ignore(base: Path, name: str) -> bool:
    """Adds `name` to the .gitignore beside edakit.toml unless a line names it already; True when written."""
    gi = base / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if any(ln.strip() in (name, "/" + name) for ln in text.splitlines()):
        return False
    gi.write_text(text + ("" if not text or text.endswith("\n") else "\n") + f"/{name}\n", encoding="utf-8")
    return True


def template(cfg, target: str):
    base = cfg.path.parent
    path = Path(os.path.expanduser(target))
    path = (Path.cwd() / path).resolve() if not path.is_absolute() else path
    if path.suffix.lower() not in TEMPLATES:
        raise InventoryError(f"template: {target} – a template is {', '.join(TEMPLATES)}")
    if path.exists():
        raise InventoryError(f"template: {target} is there already – edakit never overwrites an inventory")
    s = settings(cfg)
    names = s.names if s else dict(DEFAULT_NAMES)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_template(path, names)
    print(f"{path}: an empty inventory, columns {', '.join(names[k] for k in COLUMNS)}")
    _, said = name_in_local(base, shown(path, base))
    print(said)
    if ignore(base, LOCAL):
        print(f".gitignore: /{LOCAL}")
    try:
        inside = path.relative_to(base)
    except ValueError:
        inside = None
    if inside is not None and ignore(base, inside.as_posix()):
        print(f".gitignore: /{inside.as_posix()} – the inventory is yours, not the repository's")
    return 0


# --- edakit inventory -------------------------------------------------------------------------------------------------

def dated(s: Settings, base):
    out = []
    for f in s.files:
        when = dt.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        out.append(f"{shown(f, base)} ({when})")
    return out


def note_tracked(cfg):
    if tracked(cfg):
        print(f"note: git tracks {LOCAL} – it names your inventory; git rm --cached {LOCAL} and put it into "
              ".gitignore", file=sys.stderr)


def query(rows, words):
    words = [w.casefold() for w in words]
    return [r for r in rows if all(w in f"{r.id} {r.name} {r.description} {r.lcsc}".casefold() for w in words)]


def report(cfg, design, s, stock):
    """The project's hand-soldered parts and extras against the inventory: (rows of text, number short)."""
    from . import order
    found, _ = order.carts(cfg, design)
    lines = [g for sup in found.values() for g in sup]
    head = ("Part", "LCSC", "For", "Needed", "On hand", "To order", "Inventory rows")
    table, short = [], 0
    for g in lines:
        want = g["want"]
        rows = stock.matches(g.get("lcsc"), g.get("mpn"))
        have = stock.on_hand(g.get("lcsc"), g.get("mpn"))
        taken = sum(k for _, k in stock.take(g.get("lcsc"), g.get("mpn"), want))
        rest = want - taken
        short += rest > 0
        table.append((g["item"] or g["code"], g.get("lcsc") or "–", " ".join(g["designators"]) or "per set",
                      f"{g['need']} + {want - g['need']}", str(have), str(rest) if rest else "–",
                      "; ".join(f"{r.text()} × {r.quantity}" for r in rows) or "–"))
    return head, table, short


def _print_table(head, rows):
    widths = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    for r in [head, tuple("-" * w for w in widths), *rows]:
        print("  ".join(str(x).ljust(w) for x, w in zip(r, widths)).rstrip())


def main(cfg, args):
    words = list(args.words or [])
    try:
        if words[:1] == ["template"]:
            if len(words) != 2:
                print("edakit inventory template FILE – FILE ends in .md, .xlsx or .ods", file=sys.stderr)
                return 1
            return template(cfg, words[1])
        s, stock = load(cfg)
    except (InventoryError, OSError) as e:
        print(f"edakit inventory: {e}", file=sys.stderr)
        return 1
    if stock is None:
        print(f"edakit inventory: {LOCAL} names no inventory – edakit inventory template FILE creates one",
              file=sys.stderr)
        return 1
    note_tracked(cfg)
    base = cfg.path.parent
    print("Inventory: " + ", ".join(dated(s, base)) + f" – {len(stock.rows)} rows")
    if words:
        hits = query(stock.rows, words)
        if not hits:
            print(f"no row holds {' '.join(words)}")
            return 1
        _print_table(("ID", "Quantity", "LCSC", "Name / description", "Where"),
                     [(r.id, str(r.quantity), r.lcsc or "–", " – ".join(x for x in (r.name, r.description) if x)
                       or "–", r.place(base)) for r in hits])
        return 0
    from .design import Design
    try:
        head, table, short = report(cfg, Design.from_config(cfg), s, stock)
    except Exception as e:      # order.OrderError for a bad spare
        print(f"edakit inventory: {e}", file=sys.stderr)
        return 1
    if not table:
        print("Nothing is soldered by hand and no item is off the board – the inventory has nothing to give.")
        return 0
    print(f"{cfg.project}, {cfg.quantity} sets – needed is need + spares, before the supplier's minimum")
    _print_table(head, table)
    print(f"{len(table) - short} of {len(table)} lines on hand in full" + (f", {short} to order" if short else ""))
    return 0
