---
max_turns: 80
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill]
---

You have never seen edakit. `site/` holds its documentation as the site shows it: the start page (`site/README.md`),
the pages under `site/docs/` and the handbook under `site/handbook/`. The current directory is an empty git repository.

Make a checked circuit of your own here from this idea: "a 9 V battery, a switch, two LEDs". A circuit only – no
board, no EasyEDA, no KiCad. Follow the documentation, and only the documentation: start at the start page and open
what it leads you to. On Linux pipe edakit's output: `edakit check 2>&1 | cat`.

Nobody is there to answer questions. Where the documentation or a skill would ask, take the recommended option
yourself, say which you took, and go on as if the answer and the OK had been given.

End with two lines:
`PAGES: <every documentation page you opened, in order, as paths under site/>`
`DONE: <the last line of your last edakit check>` – or `STOPPED: <where and why>` if you could not get there.
