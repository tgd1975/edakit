"""edakit release publish: what is ordered, as a GitHub release – the upload files of every board's current release with
its polarity sheet and manifest, and notes edakit writes (handbook 8.3). Gate runs are build output; the release keeps
the files of a state that goes to the maker, the repository keeps what released it – the sign-offs with their hashes.

    edakit release publish              the release: tag = today (YYYY-MM-DD), a pre-release on HEAD
    edakit release publish --draft      a draft only the account sees – no tag, no guards: a test
    edakit release publish --dry-run    staging and notes, nothing uploaded
    edakit release publish --tag T      another tag than today's date
    edakit release publish --built T    a board of release T has been built and works: no longer a pre-release (M-4)

1. Guards (not with --draft): the working tree is clean and HEAD is on its remote branch – the tag names the state the
   files were made from.
2. Per project – this one and every variant below it, a folder with an edakit.toml of its own (handbook 10.4; [release]
   publish.variants = false: this one alone): the current release as `release current` has it, and `release verify` on
   the upload files of every made board – JLCPCB's gerber_<b>.zip, bom_<b>.csv, cpl_<b>.csv, with [cart] makers the
   files of every maker. A file refused or a project without a current release: exit 2, nothing staged, gh not called.
3. Staging in build/publish/<tag>/: those files, polarity_<b>.png, the run's manifest as manifest_<b>.json, the order
   form as order_<b>.md where the run has one, SHA256SUMS over all of them – the folder to upload to the maker from –,
   and notes.md, the release notes.
4. The notes: the commit; per board the gate run, the git state of its manifest, the fab hash, and whether the board
   changed since the previous release – its fab layers against those of its manifest there (the Gerber ZIP's own
   bytes change with every export), without them the SHA-256 of its upload files against SHA256SUMS there; the
   decisions since the previous release ([release] publish.decisions: the headings "## D-…" of the decision log); the
   purpose of the graph with the note that the regulatory review M-6 is support, not legal advice; how to order. Every
   link is absolute, into the commit – relative links do not work in release notes.
5. gh release create <tag> --prerelease --target <HEAD> with the files of the staging; a tag the remote has already
   gets -2, -3, …

The previous release is the newest one publish made (its title "Manufacturing files …"), drafts left out. Needs the
GitHub CLI gh, logged in (gh auth login); the repository is the one gh sees from the project. Firmware is not
published. Exit 0; 2: release verify refused a file, or a project has no current release; 1: an error (a guard, git,
gh).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as configmod
from . import gate

STAGING = Path("build") / "publish"   # below the project: build/publish/<tag>/
TITLE = "Manufacturing files"         # the title of every release publish makes – how the next one finds it
SUMS = "SHA256SUMS"
NOTES = "notes.md"
NOT_SEARCHED = ("build", "node_modules", "__pycache__")   # folders no variant is looked for in, besides hidden ones
USE = {"private": "built for oneself", "gift": "given away", "sale": "sold"}   # purpose.use (handbook 3.1)
DECISION = re.compile(r"^## (D-\d+)\b.*$", re.M)   # a decision of the log: its heading


class PublishError(Exception):
    """What stops publish: code 2 when release verify refused or a project has no current release, 1 otherwise."""

    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


@dataclass
class Board:
    name: str
    folder: str               # the project's folder below this one; "." for this project
    cfg: configmod.Config
    run: str
    manifest: dict
    files: list               # the upload files in the run
    extra: dict = field(default_factory=dict)   # {file in the run: its name in the staging}

    @property
    def label(self):
        return self.name if self.folder == "." else f"{self.name} ({self.folder})"

    def names(self):
        return [f.name for f in self.files] + list(self.extra.values())


def sh(cwd, *cmd, check=True):
    """Runs git or gh in cwd. check: a failure raises PublishError with what the command said last."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        raise PublishError(f"{cmd[0]} not found") from None
    except subprocess.TimeoutExpired:
        raise PublishError(f"{' '.join(cmd[:3])}: no answer after 15 minutes") from None
    if check and p.returncode != 0:
        said = (p.stderr.strip() or p.stdout.strip()).splitlines()
        raise PublishError(f"{' '.join(cmd[:3])} failed" + (f": {said[-1]}" if said else f" (exit {p.returncode})"))
    return p


def options(cfg):
    """[release] publish with its defaults: variants true, decisions none."""
    p = cfg.release.get("publish", {})
    return {"variants": p.get("variants", True), "decisions": p.get("decisions")}


# --- 1. the guards ------------------------------------------------------------------------------------------------

def logged_in(root):
    if sh(root, "gh", "auth", "status", check=False).returncode != 0:
        raise PublishError("gh is not logged in – gh auth login")


def guards(root):
    """HEAD's SHA, once the working tree is clean and HEAD is on its remote branch."""
    if sh(root, "git", "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise PublishError("uncommitted changes – commit them first: the tag must name the state the files were made "
                           "from")
    up = sh(root, "git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False)
    if up.returncode != 0:
        raise PublishError("the branch has no remote branch – push it first (git push -u): the tag must name a state "
                           "the remote has")
    sh(root, "git", "fetch", "--quiet", "--tags")
    head = sh(root, "git", "rev-parse", "HEAD").stdout.strip()
    if sh(root, "git", "merge-base", "--is-ancestor", head, "@{upstream}", check=False).returncode != 0:
        raise PublishError(f"HEAD is not on {up.stdout.strip()} – push first: the tag must name a state the remote has")
    print(f"guards: working tree clean, HEAD {head[:7]} on {up.stdout.strip()}")
    return head


# --- 2. the projects and their current releases --------------------------------------------------------------------

def variants(cfg):
    """The edakit.toml of every variant below the project, sorted: each folder with an edakit.toml of its own – hidden
    folders, build/, node_modules/ and the project's artifacts and reports left out with what lies below them."""
    skip = {cfg.artifacts.resolve(), cfg.reports.resolve()}
    found = []
    for d, dirs, files in os.walk(cfg.root):
        here = Path(d)
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in NOT_SEARCHED
                         and (here / x).resolve() not in skip)
        if here != cfg.root and "edakit.toml" in files:
            found.append(here / "edakit.toml")
    return sorted(found)


def projects(cfg):
    """[(folder, Config)]: this project ("."), then its variants – unless [release] publish.variants = false."""
    out = [(".", cfg)]
    if options(cfg)["variants"]:
        for toml in variants(cfg):
            try:
                out.append((toml.parent.relative_to(cfg.root).as_posix(), configmod.load(toml)))
            except configmod.ConfigError as e:
                raise PublishError(str(e)) from None
    return out


def no_release(pcfg):
    """Why a project has no current release, as `release current` says it."""
    last = next((f"{run} {gate.status(d)}" for run, _, d in reversed(gate.runs(pcfg)) if d.get("decision") == "RELEASED"),
                None)
    return "no current release" + (f" (newest released run: {last})" if last else " – edakit gate --easyeda releases one")


def collect(projs):
    """The boards to publish, every upload file checked by release verify against its project's current release.
    PublishError with code 2 names every project without a current release and every file refused."""
    boards, refused = [], []
    for folder, pcfg in projs:
        where = pcfg.project + ("" if folder == "." else f" ({folder})")
        try:
            cur = gate.current(pcfg)
        except gate.ReleaseError as e:
            raise PublishError(f"{where}: {e}") from None
        if not cur:
            refused.append(f"{where}: {no_release(pcfg)}")
            print(f"FAIL {refused[-1]}")
            continue
        run, manifest = cur
        print(f"{where}: current release {run}, git {manifest.get('git') or '?'}")
        fab = pcfg.reports / run / "fab"
        for b in pcfg.made():
            files = [fab / b / name for name in gate.upload(pcfg, b)]
            try:
                _, found = gate.verify(pcfg, files)
            except gate.ReleaseError as e:      # a file not there
                refused.append(f"{where}, board {b}: {e}")
                print(f"FAIL {refused[-1]}")
                continue
            bad = [(f, what) for f, ok, what in found if not ok]
            print(f"  {b}: {len(found) - len(bad)} of {len(found)} file(s) of the current release"
                  + "".join(f"\n  FAIL {f.name}: {what}" for f, what in bad))
            if bad:
                refused += [f"{where}, board {b}: {f.name} refused by release verify" for f, _ in bad]
                continue
            extra = {fab / "manifest.json": f"manifest_{b}.json"}
            for f, name in ((fab / f"polarity_{b}.png", f"polarity_{b}.png"), (fab / b / "order.md", f"order_{b}.md")):
                if f.is_file():
                    extra[f] = name
                elif name.startswith("polarity_"):
                    print(f"  {name}: not in the run – not published")
            boards.append(Board(b, folder, pcfg, run, manifest, files, extra))
    if refused:
        raise PublishError(f"not published – {len(refused)} refused: " + "; ".join(refused), code=2)
    twice = [n for n, k in Counter(n for b in boards for n in b.names()).items() if k > 1]
    if twice:
        raise PublishError(f"two boards have the same name – their files would overwrite each other: {', '.join(twice)}")
    return boards


# --- 3. the staging -----------------------------------------------------------------------------------------------

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(boards, dest):
    """The files of every board into dest, emptied first, and SHA256SUMS over them: {name: SHA-256}."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for b in boards:
        for f in b.files:
            shutil.copy2(f, dest / f.name)
        for f, name in b.extra.items():
            shutil.copy2(f, dest / name)
    sums = {f.name: sha(f) for f in sorted(dest.iterdir())}
    (dest / SUMS).write_text("".join(f"{d}  {n}\n" for n, d in sums.items()), encoding="utf-8")
    return sums


# --- 4. the notes -------------------------------------------------------------------------------------------------

def free_tag(root, wanted):
    """wanted, or wanted-2, -3, … when the remote has that tag already."""
    p = sh(root, "gh", "api", f"repos/{{owner}}/{{repo}}/git/matching-refs/tags/{wanted}", "--jq", ".[].ref")
    taken = {r.removeprefix("refs/tags/") for r in p.stdout.split()}
    tag, n = wanted, 1
    while tag in taken:
        n += 1
        tag = f"{wanted}-{n}"
    return tag


def previous(root):
    """The tag of the newest release publish made (title "Manufacturing files …"), drafts left out – or None."""
    p = sh(root, "gh", "release", "list", "--exclude-drafts", "--json", "tagName,name,createdAt", "--limit", "100")
    try:
        rels = json.loads(p.stdout or "[]")
    except json.JSONDecodeError:
        raise PublishError("gh release list: its answer is no JSON") from None
    ours = [r for r in rels if str(r.get("name") or "").startswith(f"{TITLE} ")]
    return max(ours, key=lambda r: r.get("createdAt") or "")["tagName"] if ours else None


def previous_files(root, tag):
    """(SHA256SUMS as {name: SHA-256}, {board: manifest}) of the previous release – what it has of them."""
    sums, manifests = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        sh(root, "gh", "release", "download", tag, "--pattern", SUMS, "--pattern", "manifest_*.json", "--dir", tmp,
           check=False)
        t = Path(tmp)
        if (t / SUMS).is_file():
            for line in (t / SUMS).read_text(encoding="utf-8").splitlines():
                digest, _, name = line.partition("  ")
                if name:
                    sums[name.lstrip("*")] = digest
        for f in t.glob("manifest_*.json"):
            try:
                manifests[f.stem.removeprefix("manifest_")] = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    return sums, manifests


def change(b, sums, prev, prev_sums, prev_manifests):
    """Since the previous release: by what the maker builds from – the board's fab layers in both manifests, made with
    the same method –, else by the SHA-256 of its upload files in both SHA256SUMS."""
    if not prev:
        return "first release"
    old = prev_manifests.get(b.name) or {}
    now_layers = (b.manifest.get("fab_layers") or {}).get(b.name)
    old_layers = (old.get("fab_layers") or {}).get(b.name)
    names = [f.name for f in b.files]
    if now_layers and old_layers and b.manifest.get("fab_method") == old.get("fab_method"):
        same = now_layers == old_layers
    elif any(n in prev_sums for n in names):
        same = all(prev_sums.get(n) == sums[n] for n in names)
    else:
        return f"new since {prev}"
    return f"{'unchanged' if same else 'changed'} since {prev}"


def decisions(cfg, prev):
    """The headings "## D-…" of the decision log ([release] publish.decisions) at HEAD that the log at the previous
    release's tag lacks – none without the key or a previous release."""
    log = options(cfg)["decisions"]
    if not log or not prev:
        return []
    if sh(cfg.root, "git", "rev-parse", "--verify", "--quiet", f"{prev}^{{commit}}", check=False).returncode != 0:
        sh(cfg.root, "git", "fetch", "--quiet", "--tags", check=False)
        if sh(cfg.root, "git", "rev-parse", "--verify", "--quiet", f"{prev}^{{commit}}", check=False).returncode != 0:
            print(f"decisions since {prev}: the tag is not in the local repository (git fetch --tags) – none listed")
            return []

    def headings(rev):
        p = sh(cfg.root, "git", "show", f"{rev}:./{Path(log).as_posix()}", check=False)
        return {m.group(1): m.group(0)[3:].strip() for m in DECISION.finditer(p.stdout)} if p.returncode == 0 else {}
    old = headings(prev)
    return [text for d, text in headings("HEAD").items() if d not in old]


def purpose(pcfg):
    """purpose of the project's graph (handbook 3.1): {use, market, notes, radio} – {} without one."""
    try:
        return (json.loads(pcfg.graph.read_text(encoding="utf-8")).get("graph") or {}).get("purpose") or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return {}


def commit(repo, git):
    """The git state of a manifest ("1a2b3c4", "1a2b3c4 + uncommitted changes") with the commit linked."""
    m = re.match(r"([0-9a-f]{7,40})(.*)", git or "")
    return f"[{m.group(1)}]({repo}/commit/{m.group(1)}){m.group(2)}" if m else (git or "?")


def notes(cfg, tag, head, repo, boards, projs, changes, prev, new, draft):
    top = Path(sh(cfg.root, "git", "rev-parse", "--show-toplevel").stdout.strip()).resolve()

    def link(path):       # into the commit the tag names – relative links do not work in release notes
        return f"{repo}/blob/{head}/{Path(os.path.relpath(Path(path).resolve(), top)).as_posix()}"
    L = []
    if draft:
        L += [f"**Draft: a test of `edakit release publish` – delete it: `gh release delete {tag} --yes`.**", ""]
    L += [f"Manufacturing files of {cfg.project} at git [{head[:7]}]({repo}/commit/{head}). Every board is the current "
          "release of its project: edakit's release gate decided RELEASED, with the circuit review M-1, the layout "
          "review M-5 and the regulatory review M-6 signed for its hashes.",
          "",
          "**Pre-release** until a board of this state has been built and works.",
          "",
          "| Board | Gate run | Git of the run | fab hash | Since the previous release |",
          "|---|---|---|---|---|"]
    for b in boards:
        fab = b.manifest.get("fab_sha256")
        L.append(f"| {b.label} | {b.run} | {commit(repo, b.manifest.get('git'))} | "
                 + (f"`{fab[:12]}…`" if fab else "–") + f" | {changes[b.label]} |")
    log = options(cfg)["decisions"]
    if log and prev:
        L += ["", f"Decisions since {prev} ([{Path(log).as_posix()}]({link(cfg.root / log)})):", ""]
        L += [f"- {d}" for d in new] or ["- none"]
    stated = [(folder, pcfg, purpose(pcfg)) for folder, pcfg in projs]
    if len({json.dumps([p.get("use"), p.get("notes")]) for _, _, p in stated}) == 1:
        stated = stated[:1]          # the same purpose everywhere: one line

    def said(pcfg, p):
        use = p.get("use")
        return ((f"{use} – {USE[use]}" if use in USE else "not stated") + f" ([purpose in the graph]({link(pcfg.graph)}))"
                + (f": {str(p['notes']).rstrip('.')}." if p.get("notes") else "."))
    if len(stated) == 1:
        L += ["", f"Purpose: {said(stated[0][1], stated[0][2])}"]
    else:
        L += ["", "Purpose, per project:", ""]
        L += [f"- {pcfg.project if folder == '.' else folder}: {said(pcfg, p)}" for folder, pcfg, p in stated]
    L += ["",
          "The regulatory review M-6 is support, not legal advice: no claim to correctness, nothing legally guaranteed.",
          "",
          "**To order:** per board its upload files – at JLCPCB `gerber_<board>.zip`, with assembly also "
          "`bom_<board>.csv` and `cpl_<board>.csv`; `order_<board>.md`, where there is one, lists every field of the "
          "order form with its value. `polarity_<board>.png` shows every polarised part with pad, role and net – for "
          "the check of the maker's assembly preview (M-2) and for hand soldering. `manifest_<board>.json` is edakit's "
          "record of the gate run with the SHA-256 of its files; `SHA256SUMS` covers every file here "
          "(`sha256sum -c SHA256SUMS`).",
          ""]
    return "\n".join(L)


# --- the command --------------------------------------------------------------------------------------------------

def main(cfg, args):
    try:
        return publish(cfg, args)
    except PublishError as e:
        print(f"edakit release publish: {e}", file=sys.stderr)
        return e.code


def publish(cfg, args):
    root = cfg.root
    if args.items:
        raise PublishError("publish takes no run and no file – it publishes the current release of every project")
    if not shutil.which("gh"):
        raise PublishError("gh not found – install the GitHub CLI and log in (gh auth login)")
    if args.built:
        logged_in(root)
        p = sh(root, "gh", "release", "edit", args.built, "--prerelease=false")
        print(f"{args.built}: no longer a pre-release – a board of this state has been built and works"
              + (f" ({p.stdout.strip()})" if p.stdout.strip() else ""))
        return 0
    log = options(cfg)["decisions"]
    if log and not (root / log).is_file():
        raise PublishError(f"[release] publish.decisions: {log} not found")
    head = sh(root, "git", "rev-parse", "HEAD").stdout.strip() if args.draft else guards(root)
    projs = projects(cfg)
    boards = collect(projs)                 # every file verified before gh is called or anything is staged
    logged_in(root)
    date = dt.date.today().isoformat()
    tag = args.tag or (f"draft-{date}" if args.draft else date)
    if not args.draft:
        wanted, tag = tag, free_tag(root, tag)
        if tag != wanted:
            print(f"tag {wanted}: the remote has it – {tag}")
    repo = sh(root, "gh", "repo", "view", "--json", "url", "-q", ".url").stdout.strip()
    prev = previous(root)
    prev_sums, prev_manifests = previous_files(root, prev) if prev else ({}, {})
    dest = root / STAGING / tag
    sums = stage(boards, dest)
    changes = {b.label: change(b, sums, prev, prev_sums, prev_manifests) for b in boards}
    (dest / NOTES).write_text(notes(cfg, tag, head, repo, boards, projs, changes, prev, decisions(cfg, prev),
                                    args.draft), encoding="utf-8")
    print(f"staged in {cfg.relative(dest)}/: {len(sums)} files and {SUMS}; the notes in {NOTES}")
    for b in boards:
        fab = b.manifest.get("fab_sha256")
        print(f"  {b.label}: {b.run}" + (f", fab {fab[:12]}…" if fab else "") + f", {changes[b.label]}")
    if args.dry_run:
        print(f"dry run: nothing uploaded – {dest}")
        return 0
    cmd = ["gh", "release", "create", tag, "--title", f"{TITLE} {tag}", "--notes-file", str(dest / NOTES),
           "--prerelease"]
    cmd += ["--draft"] if args.draft else ["--target", head]
    cmd += [str(dest / n) for n in [*sums, SUMS]]
    out = sh(root, *cmd).stdout.strip()
    if not args.draft:
        sh(root, "git", "fetch", "--quiet", "--tags", check=False)    # the new tag, for the next release's decisions
    print(f"published: {out.splitlines()[-1] if out else tag}" + (" (draft)" if args.draft else " (pre-release)"))
    print(f"upload to the maker from: {dest}")
    if args.draft:
        print(f"a draft for a test – delete it: gh release delete {tag} --yes")
    else:
        print(f"once a board of this state has been built and works (M-4): edakit release publish --built {tag}")
    return 0
