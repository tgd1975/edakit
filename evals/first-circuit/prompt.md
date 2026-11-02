---
max_turns: 80
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill]
---

You have never seen edakit. `site/` holds its documentation as the site shows it: the start page (`site/README.md`),
the pages under `site/docs/` and the handbook under `site/handbook/`. The current directory is an empty git repository.

Make a checked circuit of your own here from this idea: "a 9 V battery, a switch, two LEDs". A circuit only – no
board, no EasyEDA, no KiCad. Follow the documentation, and only the documentation: start at the start page and open
what it leads you to, a page with the Read tool. The plugin's own `handbook/` is the same text as `site/handbook/`.
Its skills (`/edakit:…`) and its commands are there to be used, as the documentation says; do not read edakit's code –
the plugin's `edakit/` – to find out how something works: where the documentation does not say, stop there, or go on
and name what was missing. On Linux pipe edakit's output: `edakit check 2>&1 | cat`. There is no network here:
`edakit part search`, `edakit stock` and `edakit cost` cannot reach the shop.

Nobody is there to answer questions. Where the documentation or a skill would ask, take the recommended option
yourself, say which you took, and go on as if the answer and the OK had been given.

End with three lines:
`PAGES: <every documentation page you opened, in order, each as its path beginning with site/ – a page of the plugin's
handbook as its twin under site/handbook/>`
`MISSING: <what the documentation did not tell you, or "nothing">`
`DONE: <the last line of your last edakit check>` – or `STOPPED: <where and why>` if you could not get there.
