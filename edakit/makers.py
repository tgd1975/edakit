"""The makers a board can be ordered from, and [cart] of edakit.toml (handbook 8.4, 10.1).

A maker is a profile: one data file, edakit/makers/<maker>.toml, shipped with edakit – or the project's own, named in
[cart] profiles. It holds no code and no defaults of the board: the board is edakit's keys of [order] (config.py,
handbook 10.2), the same for every maker. The profile gives each key the words of the maker's form, and holds what the
maker takes and refuses:

    name, recorded     the maker's name; the date ordering step 0 recorded the form, false while it is provisional
    start, cart, never the page the skill cart opens, the one button it may press, buttons it must not touch
    files              what is uploaded: gerber, bom, bom_mpn, cpl, odb
    bom, cpl           the columns, and the key the maker matches parts by (bom.match: lcsc or mpn)
    fields             per key: section, label, words (edakit's value -> the form's word), unit, values; false: the
                       maker has no such field, and the key is left out of its job
    excludes, ignore   combinations the form refuses; fields of the page edakit does not set, each with its reason
    classes            the assembly classes – the values of [release] assembly.pcba
    rules              the form's limits F-6 checks: thicknesses_mm (and what they are for), remark_max, placeholder,
                       placeholder_min_mm, placeholder_gone (the maker reports its order number gone: F-6 warns about
                       the placeholder), silkscreen_on, tooling_min (per class), class_of_sides
    catalogue          whose parts catalogue P-4, F-2 and edakit stock ask ("jlcpcb"); none: the maker's matching at
                       the order (B-2)
    dnp                how a part not to place is marked: "omit" (left out of BOM and CPL); otherwise the job lists it
    seat, currency     where the maker sits (the regulatory review at the order), its currency
    fees               the fee table edakit cost prices with (edakit/fees/<fees>.json)

[cart] maker is the maker the board is planned for, [cart] makers every maker whose checks and files the gate runs
and writes. A check that holds a board to a maker (P-4, F-2, F-6, P-12, F-7) fails for the planned maker and warns for
every other one (result). Without [cart] the maker is JLCPCB and the makers are ["jlcpcb"]: every check as before.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DIR = Path(__file__).with_name("makers")
DEFAULT = "jlcpcb"
FILES = ("gerber", "bom", "bom_mpn", "cpl", "odb")   # what a maker takes: profile key files
UPLOAD = {"gerber": "gerber_{b}.zip", "bom": "bom_{b}.csv", "bom_mpn": "bom_{b}_mpn.csv", "cpl": "cpl_{b}.csv",
          "odb": "odb_{b}.zip"}
PROFILE_KEYS = ("name", "recorded", "start", "seat", "currency", "catalogue", "fees", "files", "classes", "dnp",
                "cart", "never", "ignore", "excludes", "bom", "cpl", "rules", "fields", "about", "sources")
FIELD_KEYS = ("section", "label", "words", "unit", "values")
RULE_KEYS = ("thicknesses_mm", "thicknesses_for", "remark_max", "placeholder", "placeholder_min_mm", "placeholder_gone",
             "silkscreen_on", "tooling_min", "class_of_sides")
SECTIONS = ("PCB", "PCBA", "Shipping")
CART_KEYS = ("maker", "makers", "ship_to", "shipping", "tolerance", "profiles")
TOLERANCE = 0.10                 # [cart] tolerance: per price line, in the maker's currency, before B-3 warns


class MakerError(Exception):
    pass


@dataclass
class Maker:
    key: str                     # the name in [cart]: jlcpcb
    path: Path
    data: dict = field(default_factory=dict)

    @property
    def name(self):
        return self.data.get("name", self.key)

    @property
    def recorded(self):
        """The date ordering step 0 recorded the form; None while the profile is provisional."""
        return self.data.get("recorded") or None

    @property
    def seat(self):
        return self.data.get("seat")

    @property
    def currency(self):
        return self.data.get("currency")

    @property
    def rules(self):
        return self.data.get("rules") or {}

    @property
    def classes(self):
        return list(self.data.get("classes") or [])

    @property
    def files(self):
        return list(self.data.get("files") or [])

    @property
    def catalogue(self):
        return self.data.get("catalogue")

    @property
    def matches_by(self):
        """The key the maker matches BOM parts by: "lcsc" or "mpn"; None when its parts come in another file (ODB++)."""
        return (self.data.get("bom") or {}).get("match")

    def field(self, key):
        """The profile's entry for a key of [order]: a table, False (the maker has no such field), or None (not
        recorded yet)."""
        f = (self.data.get("fields") or {}).get(key)
        return f if f is False or isinstance(f, dict) else None

    def has(self, key):
        return self.field(key) is not False

    def offered(self, key):
        """The values of a key the maker's form offers, in edakit's words; None when the profile does not say."""
        f = self.field(key) or {}
        if "words" in f:
            return [_value(k) for k in f["words"]]
        if "values" in f:
            return list(f["values"])
        if key == "thickness_mm" and "thicknesses_mm" in self.rules:
            return list(self.rules["thicknesses_mm"])
        return None

    def offers(self, key, value):
        """True, False, or None (the profile does not say)."""
        values = self.offered(key)
        if values is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return any(not isinstance(v, bool) and isinstance(v, (int, float)) and abs(v - value) < 1e-9 for v in values)
        return value in values

    def label(self, key):
        f = self.field(key) or {}
        return f.get("label", key)

    def section(self, key, default="PCB"):
        f = self.field(key) or {}
        return f.get("section", default)

    def word(self, key, value):
        """The form's word for edakit's value of a key: from words, a number with its unit, a size as the form shows it,
        else the value as text. A value words do not list keeps edakit's word (F-6 names it)."""
        f = self.field(key) or {}
        words = f.get("words") or {}
        token = _token(value)
        if token in words:
            return words[token]
        if key == "size_mm" and isinstance(value, (list, tuple)) and len(value) == 2:
            return f"{value[0]:.2f} x {value[1]:.2f} mm"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)):
            return f"{value:g}{f.get('unit', '')}"
        return str(value)

    def silkscreen_on(self, mask):
        """The print colour the maker puts on a mask colour; None when the profile does not say."""
        rule = self.rules.get("silkscreen_on")
        if not rule:
            return None
        return rule.get(mask, rule.get("other"))

    def class_of_sides(self, sides):
        """The assembly class of an order without [release] assembly.pcba: by the number of assembled sides, else the
        maker's first class."""
        rule = self.rules.get("class_of_sides") or {}
        n = "one" if len(sides) == 1 else "two"
        return rule.get(n) or (self.classes[0] if self.classes else None)

    def upload(self, board):
        """The names of the files the maker takes for a board, in the order of the profile."""
        return [UPLOAD[f].format(b=board) for f in self.files if f in UPLOAD]


def _token(value):
    """A value as a key of a words table: true/false for booleans, numbers as written."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value) if not isinstance(value, str) else value


def _value(token):
    return {"true": True, "false": False}.get(token, token)


def profile_path(key, profiles=None, root=None):
    """Where a maker's profile is: the project's own ([cart] profiles), else the shipped one."""
    own = (profiles or {}).get(key)
    if own:
        p = Path(own)
        return p if p.is_absolute() or root is None else Path(root) / p
    return DIR / f"{key}.toml"


def shipped():
    """The keys of the makers edakit ships a profile for."""
    return sorted(p.stem for p in DIR.glob("*.toml"))


def problems(key, data):
    """What is wrong with a profile's form: unknown keys, wrong types."""
    out = [f"maker {key}: unknown key '{k}' (known: {', '.join(PROFILE_KEYS)})" for k in data if k not in PROFILE_KEYS]
    for k in ("name", "start", "seat", "currency", "catalogue", "fees", "dnp", "cart"):
        if k in data and not isinstance(data[k], str):
            out.append(f"maker {key}: {k} must be a string")
    for k in ("files", "classes", "never"):
        if k in data and not (isinstance(data[k], list) and all(isinstance(v, str) for v in data[k])):
            out.append(f"maker {key}: {k} must be a list of strings")
    out += [f"maker {key}: files: unknown file '{f}' (known: {', '.join(FILES)})" for f in data.get("files", [])
            if f not in FILES]
    if "recorded" in data and data["recorded"] is not False and not isinstance(data["recorded"], str):
        out.append(f"maker {key}: recorded must be the date ordering step 0 recorded the form, or false")
    out += [f"maker {key}: rules: unknown key '{k}' (known: {', '.join(RULE_KEYS)})" for k in data.get("rules") or {}
            if k not in RULE_KEYS]
    for name, f in (data.get("fields") or {}).items():
        if f is False:
            continue
        if not isinstance(f, dict):
            out.append(f"maker {key}: fields.{name} must be a table or false")
            continue
        out += [f"maker {key}: fields.{name}: unknown key '{k}' (known: {', '.join(FIELD_KEYS)})" for k in f
                if k not in FIELD_KEYS]
        if f.get("section", "PCB") not in SECTIONS:
            out.append(f"maker {key}: fields.{name}: section must be one of {', '.join(SECTIONS)}")
        if "words" in f and not (isinstance(f["words"], dict) and all(isinstance(v, str) for v in f["words"].values())):
            out.append(f"maker {key}: fields.{name}: words must be a table of edakit's value = the form's word")
    for k in ("ignore",):
        if k in data and not (isinstance(data[k], dict) and all(isinstance(v, str) and v for v in data[k].values())):
            out.append(f"maker {key}: ignore must be a table of the page's field = the reason edakit does not set it")
    if "excludes" in data and not (isinstance(data["excludes"], list) and all(isinstance(e, dict) and e
                                                                               for e in data["excludes"])):
        out.append(f"maker {key}: excludes must be a list of tables, each a combination of keys the form refuses")
    return out


_CACHE = {}


def load(key, profiles=None, root=None):
    """The profile of a maker; MakerError when there is none or it is not valid."""
    path = profile_path(key, profiles, root)
    stamp = (path, path.stat().st_mtime_ns if path.exists() else None)
    if stamp in _CACHE:
        return _CACHE[stamp]
    if not path.exists():
        known = ", ".join(shipped())
        raise MakerError(f"maker {key}: no profile – edakit ships {known}; a project's own goes into [cart] profiles "
                         f"({path} not found)")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise MakerError(f"maker {key}: {path}: {e}") from None
    if bad := problems(key, data):
        raise MakerError("; ".join(bad))
    _CACHE[stamp] = Maker(key, path, data)
    return _CACHE[stamp]


# --- [cart] of edakit.toml ------------------------------------------------------------------------------------------

def cart(raw):
    """[cart] with its defaults: maker (jlcpcb), makers ([maker]), ship_to, shipping {maker: method}, tolerance,
    profiles {maker: path}. Returns (cart, problems)."""
    c = raw if raw is not None else {}
    if not isinstance(c, dict):
        return {}, ["[cart] must be a table"]
    out = [f"[cart]: unknown key '{k}' (known: {', '.join(CART_KEYS)})" for k in c if k not in CART_KEYS]
    maker = c.get("maker", DEFAULT)
    makers = c.get("makers", [maker])
    if not isinstance(maker, str) or not maker:
        out.append("[cart] maker must be the name of a maker, e.g. \"jlcpcb\"")
        maker = DEFAULT
    if not (isinstance(makers, list) and makers and all(isinstance(m, str) and m for m in makers)):
        out.append('[cart] makers must be a list of makers, e.g. ["jlcpcb", "eurocircuits"]')
        makers = [maker]
    elif maker not in makers:
        out.append(f"[cart] makers {makers} does not name [cart] maker {maker!r} – the planned maker is one of them")
    if len(set(makers)) != len(makers):
        out.append("[cart] makers names a maker twice")
    shipping = c.get("shipping", {})
    if not (isinstance(shipping, dict) and all(isinstance(v, str) for v in shipping.values())):
        out.append('[cart] shipping must be a table of maker = shipping method, e.g. { jlcpcb = "DHL Express" }')
        shipping = {}
    out += [f"[cart] shipping names {m}, which is not in [cart] makers" for m in shipping if m not in makers]
    if "ship_to" in c and not isinstance(c["ship_to"], str):
        out.append('[cart] ship_to must be the country the order goes to, e.g. "DE"')
    tol = c.get("tolerance", TOLERANCE)
    if isinstance(tol, bool) or not isinstance(tol, (int, float)) or tol < 0:
        out.append(f"[cart] tolerance must be a number >= 0, not {tol!r}")
        tol = TOLERANCE
    profiles = c.get("profiles", {})
    if not (isinstance(profiles, dict) and all(isinstance(v, str) and v for v in profiles.values())):
        out.append('[cart] profiles must be a table of maker = the path of its profile')
        profiles = {}
    return {"maker": maker, "makers": list(makers), "ship_to": c.get("ship_to"), "shipping": dict(shipping),
            "tolerance": float(tol), "profiles": dict(profiles), "given": raw is not None}, out


def of(cfg):
    """[cart] of the project with its defaults (the same without the table)."""
    return getattr(cfg, "cart", None) or cart(None)[0]


def planned(cfg):
    """The maker the boards are planned for: [cart] maker, jlcpcb without it."""
    return of(cfg)["maker"]


def listed(cfg):
    """Every maker whose checks and files the gate runs and writes: [cart] makers, [maker] without it."""
    return list(of(cfg)["makers"])


def get(cfg, key=None):
    """The profile of a maker of the project (default the planned one)."""
    c = of(cfg)
    return load(key or c["maker"], c["profiles"], getattr(cfg, "root", None))


def all_of(cfg):
    return [get(cfg, k) for k in listed(cfg)]


def result(cfg, key, ok, otherwise="fail"):
    """The result of a check that holds a board to maker key: pass; else fail (or otherwise) for the planned maker, a
    warning for every other one – a setting only a second maker lacks does not block the release for the first."""
    if ok:
        return "pass"
    return otherwise if key == planned(cfg) else "warn"


def pcba(cfg, key=None):
    """(class, why) of the assembly order at a maker: for the planned maker [release] assembly.pcba, else – and for every
    other maker – the class its profile gives the assembled sides (JLCPCB: one side Economic, two sides Standard)."""
    key = key or planned(cfg)
    a = cfg.release.get("assembly", {})
    if a.get("pcba") and key == planned(cfg):
        return a["pcba"], f'[release] assembly.pcba = "{a["pcba"]}"'
    sides = a.get("sides", ["top", "bottom"])
    m = get(cfg, key)
    cls = m.class_of_sides(sides) or "economic"
    if m.rules.get("class_of_sides"):
        return cls, f"[release] assembly.sides {' + '.join(sides)}: {'one side' if len(sides) == 1 else 'two sides'}"
    return cls, f"the first assembly class of {m.name}"


def placeholders(cfg=None):
    """{placeholder text: maker name} of every maker profile edakit ships and the project names – the texts a maker
    replaces by its order number, and every other maker prints as they are (F-6)."""
    keys = set(shipped()) | (set(listed(cfg)) if cfg is not None else set())
    out = {}
    for key in sorted(keys):
        try:
            m = get(cfg, key) if cfg is not None and key in listed(cfg) else load(key)
        except MakerError:
            continue
        if m.rules.get("placeholder"):
            out.setdefault(m.rules["placeholder"], m.name)
    return out


def with_catalogue(cfg, catalogue="jlcpcb"):
    """The makers of the project that order from that parts catalogue (P-4, F-2, edakit stock)."""
    return [k for k in listed(cfg) if get(cfg, k).catalogue == catalogue]
