# Explorative DSL

!!! warning "A beta"
    The explorative DSL is not part of the released edakit: it lives on the branch `claude/friendly-mccarthy-n4kt6y`
    and works only in a project that switches it on. Its form may still change from one commit to the next.

The explorative DSL is the circuit language: a project's graph written as `.circuit` source – with definitions,
usages, loops, parameters, derivation rules and variants – instead of the JSON or TOML graph. The compiler turns it
into the resolved graph in today's JSON format, so the engines, the simulation, the gate, the schematic, the firmware
contract and the project's scripts read it unchanged. For you if a circuit repeats itself, comes in variants, or has
values that follow from a rule – an LED's series resistor, a divider, a pull-up.

## Switching it on

A project switches the DSL on in its edakit.toml, and names its source:

```toml
[project]
graph = "hardware/graph.circuit"

[beta]
dsl = true
```

Without `[beta] dsl = true` edakit is what it always was: a `.circuit` graph or requirements file and a list of parts
folders are refused with one line that names the switch, the commands of the DSL answer the same, `edakit lsp` shows
that line in the editor, and nothing of it is offered or checked – no SYNC.graph, no DEF, no word in the handbook or
the skills. With it, the session start tells Claude where the source is and points here.

The language is declarative and finite: definitions, usages, loops over integer ranges, named derivation rules and
variants as differences – no conditionals, no free expressions, no file access. A compile is a function from the
source and the parts entries to the resolved graph; the same input gives the same bytes. Behaviour stays in the parts
entries, layout in the board files, the checks in the engines: the language composes and decides nothing an engine
decides.

| File | Role |
| --- | --- |
| `hardware/graph.circuit` | the source, named by `[project] graph` |
| `hardware/graph.json` | the resolved graph, written by `edakit graph json --write`; in no hash |
| `edakit/blocks/<name>.circuit` | edakit's blocks as definitions; the JSON beside each is generated from it |

Encoding UTF-8, lines ending in LF, no tabs; `edakit graph fmt` writes lines of at most 118 characters.

## Moving a project

`edakit graph convert --to circuit [--dry-run]` moves a JSON or TOML project to `hardware/graph.circuit`: flat
statements, read back before anything is written, `[project] graph` and `edakit` set, the resolved graph.json beside
it, the sign-offs of scope circuit carried over. A converted project needs the edakit that reads the language:
`[project] edakit` names it, and an older plugin says so at the session start (STRUCT.edakit).

## The resolved graph and the hash

The resolved graph is the JSON graph of handbook 3.1 in every key, plus `derivations` where the source has
derivations. The circuit hash takes the compiled data as the TOML form takes a TOML graph's – arranged, `[release]
hash_ignore` applied, `purpose` whole –, so a comment, a blank line or a statement moved changes nothing, a changed
pin or value does. `graph_sha256` names the source's bytes. The generated `graph.json` is in no hash.

`edakit graph json --check` exits 2 and lists what differs when the committed file is not what the source compiles to;
`edakit hook` runs it before each commit (handbook 2.7). `edakit check` reports the same as SYNC.graph, an error of
stage G – in a project with the DSL switched on, for a TOML graph as for a language one; a generated file not written
yet is the hook's to report.

A graph in the circuit language counts with its compiled data, as a TOML graph with its data: a comment or a
statement moved changes nothing. A variant whose `[project] parts` is a list of folders counts the entries its graph
uses, each from the folder it is found in, so that a change of its base reaches its hash only where it reaches its
circuit; a project with one folder counts every entry of it, as before.

## Commands

| Command | What it does |
| --- | --- |
| `edakit graph json [--write\|--check] [--map FILE]` | the resolved graph; written beside the source; drift; the source map – where each part, net, lock and accept was written |
| `edakit graph fmt [--check] [FILE …]` | the canonical layout, comments kept; `--check` exits 2 at the first line that would change |
| `edakit graph convert --to circuit [--dry-run]` | a JSON or TOML project moved to `hardware/graph.circuit`: flat statements, read back before anything is written, `[project] graph` and `edakit` set, the circuit sign-offs carried over |
| `edakit graph derive [--write]` | every derivation record evaluated again |
| `edakit block add NAME … --set P=V [--part DES=KEY]` | a block's derivations run ([derivations](derivations.md)) |
| `edakit graph sysml\|kerml [--out DIR]` | the project as SysML v2 or KerML ([SysML v2 and KerML](sysml.md)) |
| `edakit lsp` | the language server over stdio, for an editor ([the editor](editor.md)) |

## The pages

| Page | What it holds |
| --- | --- |
| [The circuit language](language.md) | words, quantities, the statements, definitions, usages, loops, parameters, what the compiler does |
| [Derivations](derivations.md) | the rules, `block add --set`, the records and the engine DEF |
| [Variants and requirements](variants.md) | a variant as differences over its base, requirements in the notation |
| [SysML v2 and KerML](sysml.md) | the exports and their conformance test |
| [The editor](editor.md) | `edakit lsp` and the VS Code extension |

The notation in full, statement by statement, is the concept
[circuit-dsl-language.md](../concepts/new/circuit-dsl-language.md); why a language at all and on which basis,
[circuit-dsl.md](../concepts/new/circuit-dsl.md); how it was built and every decision on the way,
[circuit-dsl-toolchain.md](../concepts/new/circuit-dsl-toolchain.md). The regulatory review reads the resolved
graph's `purpose` as it reads a JSON graph's – support, not legal advice, nothing legally guaranteed (handbook 15).
