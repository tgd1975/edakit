# Editors for the circuit language

The circuit language's sources – `hardware/graph.circuit` and the files it includes, `edakit/blocks/*.circuit` – are
plain text; any editor reads them. For VS Code:

- `vscode/syntaxes/circuit.tmLanguage.json` – a TextMate grammar (scope `source.circuit`): comments, strings, the
  statement keywords at the start of a line, the keywords inside statements, attribute keys, pin words (`U1.GP3`),
  designators, quantities with units (`0..5.5 V`, `4k7`), codes (`LIM.v`), `(locked)` and `{n}` in a loop.
- `vscode/language-configuration.json` – `#` line comments, brackets, quotes closed as they are opened.

The grammar is generated from the reader's keywords and the attribute table; `tests/test_lang_grammar.py` holds it
to them. GitHub shows `.circuit` files as plain text: a project may lend them another language's colours with a line
in its `.gitattributes` (`*.circuit linguist-language=…`).
