"""The library of checked parts entries (rules-at-scale.md, decision 8): edakit/parts/<key>.json, the entries popular
parts and the building blocks use, each written from its datasheet and counting once the owner has signed it.

    edakit part add                  the library's entries, signed or draft
    edakit part add KEY [KEY …]      copy entries into the project's parts folder, each naming its library version
    edakit part add KEY --update     take the library's newer version over a copy (on purpose; the old one is shown)
    edakit part sign KEY --by NAME   the owner signs an entry as it is now (edakit/parts/signed.toml)

A project's copy carries "library": {"key", "sha256", "signed", "date"} – the version it was taken from. PARTS.library
notes a copy whose library entry has changed since (grade newer) and a copy of an entry not signed (grade draft); the
copy itself belongs to the project and is checked like every entry. The version is the SHA-256 of the entry without
its own "library" field, so it needs no number to keep up.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

LIBRARY = Path(__file__).with_name("parts")
SIGNED = LIBRARY / "signed.toml"


class LibraryError(Exception):
    pass


def keys():
    return sorted(p.stem for p in LIBRARY.glob("*.json"))


def entry(key):
    """The library's entry, or None."""
    path = LIBRARY / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def sha(e):
    """The version of an entry: SHA-256 of its canonical JSON without the "library" field."""
    body = {k: v for k, v in e.items() if k != "library"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def signatures():
    if not SIGNED.is_file():
        return {}
    return (tomllib.loads(SIGNED.read_text(encoding="utf-8")).get("signed") or {})


def signature(key, e=None):
    """The owner's signature of the entry as it is now, or None (unsigned, or changed since it was signed)."""
    e = entry(key) if e is None else e
    s = signatures().get(key)
    return s if e is not None and s and s.get("sha256") == sha(e) else None


def provenance(key, e, today=None):
    sig = signature(key, e)
    return {"key": key, "sha256": sha(e), "signed": bool(sig), "date": (today or dt.date.today()).isoformat()}


def copy_into(parts_dir, key, update=False, today=None):
    """Copy the library's entry into the project's parts folder with its provenance; -> (path, old entry or None)."""
    e = entry(key)
    if e is None:
        raise LibraryError(f"{key}: not in the library (edakit/parts/) – edakit part add lists it")
    out = Path(parts_dir) / f"{key}.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
    if old is not None and not update:
        raise LibraryError(f"{key}: the project has an entry already – --update takes the library's version over it")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**e, "library": provenance(key, e, today)}, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    return out, old


def sign(key, by, today=None):
    """Write the owner's signature of the entry as it is now into signed.toml."""
    e = entry(key)
    if e is None:
        raise LibraryError(f"{key}: not in the library")
    if not by.strip():
        raise LibraryError("--by: the name of the owner who signs")
    line = (f'{key} = {{ by = {json.dumps(by.strip(), ensure_ascii=False)}, date = '
            f'"{(today or dt.date.today()).isoformat()}", sha256 = "{sha(e)}" }}')
    text = SIGNED.read_text(encoding="utf-8") if SIGNED.is_file() else "[signed]\n"
    pattern = re.compile(rf"^{re.escape(key)} = .*$", re.M)
    text = pattern.sub(line, text) if pattern.search(text) else text.rstrip("\n") + "\n" + line + "\n"
    SIGNED.write_text(text, encoding="utf-8")
    return line


def check(design, rep):
    """PARTS.library: a copy whose library entry changed since it was taken (newer), a copy of an unsigned entry
    (draft) – notes; the copy itself is the project's."""
    for key in sorted({design.entry_key(des) for des in design.comps} - {None}):
        mine = design.parts.get(key) or {}
        lib = mine.get("library")
        if not isinstance(lib, dict) or not lib.get("key"):
            continue
        now = entry(lib["key"])
        who = f"{', '.join(des for des in design.comps if design.entry_key(des) == key)} {key}"
        if now is None:
            rep.add("note", "PARTS.library", f"{who}: taken from the library entry {lib['key']}, which the library no "
                                             "longer holds", grade="newer")
            continue
        if lib.get("sha256") != sha(now):
            rep.add("note", "PARTS.library", f"{who}: the library holds another version of {lib['key']} than the one "
                                             f"taken on {lib.get('date', '?')} – edakit part add {lib['key']} --update "
                                             "takes it over", grade="newer")
        if not signature(lib["key"], now):
            rep.add("note", "PARTS.library", f"{who}: the library entry {lib['key']} is not signed by the owner – a "
                                             "draft; the copy counts as the project's own entry", grade="draft")


def main_add(cfg, args):
    names = [n for n in (args.source, args.new) if n]
    if not names:
        sig = signatures()
        for key in keys():
            e = entry(key)
            state = "signed" if signature(key, e) else ("changed since signed" if key in sig else "draft")
            print(f"{key:<10} {e.get('kind', ''):<12} {e.get('mpn', ''):<24} {state}")
        print(f"{len(keys())} entries in edakit/parts/, {sum(1 for k in keys() if signature(k))} signed")
        return 0
    for key in names:
        out, old = copy_into(cfg.parts, key, update=args.update)
        e = entry(key)
        state = "signed" if signature(key, e) else "a draft – not signed by the owner"
        print(f"{cfg.relative(out)}: {e.get('mpn', key)} from the library ({state})"
              + (" – replaced the project's entry" if old is not None else ""))
        if old is not None:
            changed = sorted(k for k in set(old) | set(e) if k != "library" and old.get(k) != e.get(k))
            print(f"  changed: {', '.join(changed) or 'nothing but the provenance'}")
    return 0


def main_sign(cfg, args):
    if not args.source:
        print("edakit part sign: which entry (edakit part sign C2297 --by NAME)", file=sys.stderr)
        return 1
    print(sign(args.source, args.by or ""))
    return 0
