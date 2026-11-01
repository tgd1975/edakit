patch
- A project can say which edakit it needs: `edakit = ">=0.4"` under `[project]` in edakit.toml. When the
  running edakit does not meet it, `edakit check` notes STRUCT.edakit and the session hook says so; the working
  agreements' first line names the edakit that runs (handbook 2.3, 10.1).
