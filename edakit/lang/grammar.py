"""The TextMate grammar of the circuit language for editors (T.9), generated from the reader's keywords and the
attribute table, so that the colours follow the language.

    python -m edakit.lang.grammar            lists the files that differ from what is generated
    python -m edakit.lang.grammar --write    writes editors/vscode/syntaxes/circuit.tmLanguage.json and
                                             editors/vscode/language-configuration.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import schema
from .reader import INNER, STATEMENTS

ROOT = Path(__file__).resolve().parents[2] / "editors" / "vscode"
GRAMMAR = ROOT / "syntaxes" / "circuit.tmLanguage.json"
CONFIG = ROOT / "language-configuration.json"
UNITS = "Ω|ohms?|V|A|W|F|H|Hz|°C|s|%"
NUMBER = r"-?[0-9]+(?:\.[0-9]+)?(?:[pnuµμmkKMGR][0-9]*)?"


def _alt(words):
    return "|".join(re.escape(w) for w in sorted(words, key=lambda w: (-len(w), w)))


def attributes():
    return sorted({k for t in (schema.COMPONENT, schema.NET, schema.CABLE) for k in t} - set(STATEMENTS) - set(INNER))


def grammar():
    inner = sorted(set(INNER) - {"(locked)"})
    end = r"(?=[\s),=]|$)"
    before = r"(?<![^\s(,])"
    one = rf"{NUMBER}(?:\s?(?:{UNITS}))?"
    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "edakit circuit",
        "scopeName": "source.circuit",
        "fileTypes": ["circuit"],
        "patterns": [{"include": f"#{k}"} for k in ("comment", "string", "statement", "locked", "brace", "code",
                                                     "pin", "quantity", "keyword", "attribute", "designator",
                                                     "group")],
        "repository": {
            "comment": {"name": "comment.line.number-sign.circuit", "match": "#.*$"},
            "string": {"name": "string.quoted.double.circuit", "begin": '"', "end": '"',
                       "patterns": [{"name": "constant.character.escape.circuit", "match": r'\\["\\]'},
                                    {"include": "#brace"}]},
            "statement": {"match": rf"^\s*({_alt(STATEMENTS)})(?=\s|$)",
                          "captures": {"1": {"name": "keyword.control.circuit"}}},
            "keyword": {"name": "keyword.other.circuit", "match": rf"{before}({_alt(inner)}){end}"},
            "attribute": {"name": "variable.parameter.circuit", "match": rf"{before}({_alt(attributes())}){end}"},
            "locked": {"name": "storage.modifier.circuit", "match": r"\(locked\)"},
            "brace": {"name": "variable.other.loop.circuit", "match": r"\{[A-Za-z_][A-Za-z0-9_]*(?:[-+*][0-9]+)?\}"},
            "code": {"name": "support.constant.code.circuit",
                     "match": r'(?<![^\s"])[A-Z]+\.[a-z][a-z0-9_]*(?:[/:][a-z0-9_]+)?(?=[\s"]|$)'},
            "pin": {"name": "entity.name.tag.pin.circuit", "match": r'(?<![^\s(=])[A-Za-z_{][^\s."#]*\.[^\s"#]+'},
            "quantity": {"name": "constant.numeric.circuit",
                         "match": rf"(?<![^\s(=,]){one}(?:\s?\.\.\s?{one})?(?=[\s),]|$)"},
            "designator": {"name": "entity.name.type.designator.circuit",
                           "match": r"(?<![^\s(=])[A-Z]{1,3}[0-9]+(?=[\s)=]|$)"},
            "group": {"begin": r"\(", "end": r"\)",
                      "patterns": [{"include": "#string"}, {"include": "#quantity"}, {"include": "#keyword"}]},
        },
    }


def configuration():
    return {"comments": {"lineComment": "#"}, "brackets": [["(", ")"], ["{", "}"], ["[", "]"]],
            "autoClosingPairs": [{"open": '"', "close": '"', "notIn": ["string"]}, {"open": "(", "close": ")"},
                                 {"open": "{", "close": "}"}, {"open": "[", "close": "]"}],
            "surroundingPairs": [['"', '"'], ["(", ")"], ["{", "}"], ["[", "]"]],
            "indentationRules": {"increaseIndentPattern": r"^\s*(def|for|variant)\b.*$", "decreaseIndentPattern": "^$"}}


def files():
    return {GRAMMAR: json.dumps(grammar(), indent=1, ensure_ascii=False) + "\n",
            CONFIG: json.dumps(configuration(), indent=1, ensure_ascii=False) + "\n"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    stale = [p for p, text in files().items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    for p in stale:
        if args.write:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(files()[p], encoding="utf-8")
            print(f"written: {p.relative_to(ROOT.parents[1])}")
        else:
            print(f"differs: {p.relative_to(ROOT.parents[1])} – python -m edakit.lang.grammar --write")
    return 1 if stale and not args.write else 0


if __name__ == "__main__":
    sys.exit(main())
