---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---

The current directory is an edakit project without a requirements file. Make the inventory for the requirements
file with edakit's agent requirements-engineer (prompt "inventory") and give its result: the candidates for needs and
requirements, each with its source, and what is already checked by edakit. Write no file.
