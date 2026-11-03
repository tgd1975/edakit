"""The circuit language: a project's hardware graph written as `.circuit` source.

The language composes – definitions with parameters, usages, loops over integer ranges, named derivation rules and
variants as differences – and decides nothing an engine decides. Its compiler turns the source into the resolved
graph, today's JSON graph plus the key `derivations`, which every reader of the graph sees unchanged
(docs/concepts/done/circuit-dsl-language.md; the build: circuit-dsl-toolchain.md).

    units.py     quantities with units, ranges and tolerances (language 4)
    series.py    the E-series of IEC 60063 (catalog/tables/series.toml)

The compiler's phases (language 6): read, namespace, variant chain, parameters, loops, usages, parts entries and
pins, derivations, assembly, source map. A compile is a function from the source files and the parts entries to
the resolved graph: the same input gives the same bytes.
"""
