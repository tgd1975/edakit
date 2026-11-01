minor
- **When updating:** a project without `[project] requirements` writes its requirements file with `/edakit:requirements` and names it in `edakit.toml` before its next release – DOCS.file is open until then: `edakit check` passes, `edakit check --release` and the gate do not release (handbook 3.6, 8.7).
