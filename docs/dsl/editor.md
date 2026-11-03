# The editor

!!! warning "A beta"
    The explorative DSL is a beta: it works only in a project that switches it on with `[beta] dsl = true` in
    edakit.toml, and its form may still change from one version to the next.

`edakit lsp` is the language server, over stdio, for a person in an editor – a model edits through the command line
and `graph show` and needs none of it. It answers the reader's and the compiler's errors as they are typed, the
findings of the graph engines at the statements they come from (through the compiler's source map, `--map`), go to
definition – a pin word to its parts entry, a usage to its definition, a net to its first statement, an include to
its file –, hover with a part's entry, a pin's number and role and a net's range, completion of pin words after
`DES.`, of codes after `accept` and of definitions after `use`, and formatting.

It needs edakit's extra `lsp` (`pygls`); without it the command says so.

`editors/vscode/` is the extension for VS Code: the TextMate grammar and the language configuration – generated
from the reader's keywords, `python -m edakit.lang.grammar --write` –, the server's client, format on save through the
server, and the commands `graph json --write`, `graph json --check`, `graph show` for the word under the cursor and
`graph fmt`, the two graph commands also as tasks. The setting `edakit.command` names the executable. It is not
published; `npm ci && npm run compile && npx @vscode/vsce package` builds it, `code --install-extension` installs it,
and an optional job of the CI compiles it.

In a file whose project has not switched the DSL on, the server shows the one line that names the switch and answers
nothing else.
