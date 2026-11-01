# Changelog

What changed in each version of edakit, newest first – for a maker who updates the plugin. Every merge that changes
edakit is a version of its own: the minor number goes up when a project must act, and its lines begin with **When
updating:**; the patch number goes up otherwise; the major number marks a milestone of edakit itself. Each section is written
once, by `.github/merge.py`, from the fragments in [changes/](changes/README.md) – the rule is in
[versioning.md](docs/concepts/new/versioning.md). Update with `claude plugin marketplace update edakit && claude plugin
update edakit@edakit`, then `/reload-plugins` or a new session; `edakit --version` names the version that runs.
