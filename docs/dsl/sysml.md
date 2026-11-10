# SysML v2 and KerML

!!! warning "A beta"
    The explorative DSL is a beta: it works only in a project that switches it on with `[beta] dsl = true` in
    edakit.toml, and its form may still change from one version to the next.

```bash
edakit graph sysml [--out DIR]     # <artifacts>/sysml/: <project>.sysml, <project>.json, Electrical.sysml
edakit graph kerml [--out DIR]     # <artifacts>/kerml/: <project>.kerml, <project>.kerml.json, Electrical.kerml
```

The exports write a project in the standard's terms, for a SysML tool of its reader's own: a package with the circuit
as a part definition specializing `Electrical::Circuit`, every component a part usage with its pins as ports – named
by the entry's names, with number and role –, every net an n-ary connection between them with its range, cables,
accepts, locks, the layout and derivation records as metadata, the definitions of the source as part definitions of
`Block`, their usages as part usages typed by them, a variant as a specialization of its base's circuit with what
differs redefined, and the requirements as requirement usages with `satisfy`.

A requirement's `from` is a `#derivation connection` of the standard's RequirementDerivation library, one per
original with its derived requirements as the other ends; KerML, which has not that library, writes a `dependency`
per pair.

Quantities are written in base SI units, `0.01 [SI::A]`; a name that is no identifier or a keyword is quoted, `'+5V'`.

`edakit/lang/library/Electrical.sysml` is the electrical library every export imports: pins, components by type,
nets, cables, blocks, the circuit, its metadata, requirements and the rules as calculation definitions. The kernel
view, KerML, writes the same tree with KerML's keywords; it has no requirement, so a requirement is a feature there.
The JSON beside each is an array of elements with a stable `@id` (UUID 5 of the project and the qualified name),
`@type` and their relationships.

The library and the exports are read by a standard reader in a test of their own (`pytest -m sysml`, the optional
dependency group `sysml` with Syster's `systree`), against the standard library of SysML v2 where `SYSML_STDLIB` names
its folder `sysml.library`, an optional job of the CI that loads the release 2025-12; a graphical tool's import is no
test of edakit's. That reader resolves types, not imports, metadata names or the ends of a derivation – the test
holds those names to the standard library's text.
