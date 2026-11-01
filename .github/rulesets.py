"""The protection of main as text (docs/concepts/done/versioning.md): the rulesets in .github/rulesets/*.json and the
repository's merge settings in .github/rulesets/settings.json, held against what GitHub has.

    python3 .github/rulesets.py           what differs between the files and GitHub – exit 1 if anything does
    python3 .github/rulesets.py apply     make GitHub as the files say – a ruleset no file names is removed –, only
                                          on the owner's word

Every session acts as the owner's account, so the rules guard against slips and against the Actions, not against a
session: the owner's OK for code stays a working rule. A change to the rules is a pull request like any other, applied
after its merge. In an emergency the owner switches a ruleset off in the repository's settings and on again.
"""

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent / "rulesets"
REPO = "tgd1975/edakit"


def gh(*args, payload=None):
    r = subprocess.run(["gh", "api", *args, *(["--input", "-"] if payload is not None else [])],
                       input=json.dumps(payload) if payload is not None else None, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"gh api {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def wanted():
    """{name: ruleset} from the files, and the settings."""
    rulesets = {}
    for p in sorted(HERE.glob("*.json")):
        if p.name != "settings.json":
            data = json.loads(p.read_text())
            rulesets[data["name"]] = data
    return rulesets, json.loads((HERE / "settings.json").read_text())


def subset(live, want):
    """live cut down to what want names – GitHub adds ids, links and defaults; rules compared by type."""
    if isinstance(want, dict) and isinstance(live, dict):
        return {k: subset(live.get(k), w) for k, w in want.items()}
    if isinstance(want, list) and isinstance(live, list):
        if all(isinstance(w, dict) and "type" in w for w in want):
            by_type = {r.get("type"): r for r in live if isinstance(r, dict)}
            extra = sorted(set(by_type) - {w["type"] for w in want})
            return [subset(by_type.get(w["type"]), w) for w in want] + [{"type": t, "not in the file": True}
                                                                         for t in extra]
        if all(isinstance(w, dict) for w in want) and len(live) == len(want):
            return [subset(lv, w) for lv, w in zip(live, want)]
        return live
    return live


def differences(live_rulesets, live_settings, rulesets, settings):
    """[(what, wanted, live)] – what GitHub has against what the files say."""
    out = []
    for name, want in rulesets.items():
        live = live_rulesets.get(name)
        got = subset(live, want) if live else None
        if got != want:
            out.append((f"ruleset {name}", want, got))
    for name in sorted(set(live_rulesets) - set(rulesets)):
        out.append((f"ruleset {name}", None, "on GitHub, not in .github/rulesets/"))
    got = {k: live_settings.get(k) for k in settings}
    if got != settings:
        out.append(("settings", settings, got))
    return out


def live():
    rulesets = {r["name"]: gh(f"repos/{REPO}/rulesets/{r['id']}") for r in gh(f"repos/{REPO}/rulesets") or []}
    return rulesets, gh(f"repos/{REPO}")


def main(argv):
    rulesets, settings = wanted()
    live_rulesets, live_settings = live()
    if argv == ["apply"]:
        for name, want in rulesets.items():
            if name in live_rulesets:
                gh("-X", "PUT", f"repos/{REPO}/rulesets/{live_rulesets[name]['id']}", payload=want)
                print(f"ruleset {name}: updated")
            else:
                gh("-X", "POST", f"repos/{REPO}/rulesets", payload=want)
                print(f"ruleset {name}: created")
        for name in sorted(set(live_rulesets) - set(rulesets)):
            gh("-X", "DELETE", f"repos/{REPO}/rulesets/{live_rulesets[name]['id']}")
            print(f"ruleset {name}: removed")
        gh("-X", "PATCH", f"repos/{REPO}", payload=settings)
        print("settings: set")
        live_rulesets, live_settings = live()
    elif argv:
        print(__doc__, file=sys.stderr)
        return 2
    diff = differences(live_rulesets, live_settings, rulesets, settings)
    for what, want, got in diff:
        print(f"{what} differs\n  file:   {json.dumps(want, sort_keys=True)}\n  GitHub: {json.dumps(got, sort_keys=True)}")
    if not diff:
        print("GitHub has what .github/rulesets/ says")
    return 1 if diff else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
