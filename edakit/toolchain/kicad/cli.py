"""kicad-cli: what the KiCad tool chain cannot do with files (handbook 16.5) – KiCad 10, from KiCad's PPA for Ubuntu.

    version()                    "10.0.6"
    fill_zones(pcb)              pcb drc --refill-zones --save-board: the zones filled and saved in the file
    drc(pcb, out)                pcb drc, JSON report -> findings as EasyEDA's DRC gives them (drc.json, L-3)
    erc(sch, out)                sch erc, JSON report -> findings (S-3)
    netlist(sch, out)            sch export netlist -> {net: [ref.pin]}, {ref: fields} (S-2, F-1)
    gerbers(pcb, out)            pcb export gerbers: copper, mask, paste, silkscreen, outline
    drill(pcb, out)              pcb export drill: Excellon in mm, plated and not plated apart, slots as G85
    pos(pcb, out)                pcb export pos: CSV in mm, both sides
    pdf_schematic, pdf_pcb, render   documentation and the pictures of the layout review

The flags are those of KiCad 10's command-line reference; every call is printed with -v. KICAD_CLI (environment)
names another binary.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import sexp

MAJOR = 10                     # the version edakit writes for and is tested with (decision 4 of the concept)
GERBER_LAYERS = ("F.Cu", "B.Cu", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "Edge.Cuts")
TIMEOUT = 600


class CliError(Exception):
    pass


def binary():
    return os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "kicad-cli"


def run(*args, timeout=TIMEOUT, ok=(0,), verbose=False):
    cmd = [binary(), *map(str, args)]
    if verbose:
        print("  $ " + " ".join(cmd), flush=True)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise CliError(f"kicad-cli not found – install KiCad {MAJOR} (handbook 2: KiCad's PPA for Ubuntu) or name it "
                       "with KICAD_CLI") from None
    except subprocess.TimeoutExpired:
        raise CliError(f"kicad-cli {args[0]} {args[1] if len(args) > 1 else ''}: no answer after {timeout} s") from None
    if res.returncode not in ok:
        raise CliError(f"kicad-cli {' '.join(map(str, args[:3]))}: exit {res.returncode} – "
                       f"{(res.stderr or res.stdout).strip()[-400:]}")
    return res


def version():
    """The version kicad-cli reports, e.g. "10.0.6"."""
    out = run("version").stdout.strip()
    m = re.search(r"\d+\.\d+(?:\.\d+)?", out)
    return m.group(0) if m else out


def fill_zones(pcb, verbose=False):
    """Fill every zone of the PCB and save the file – kicad-cli's DRC with --refill-zones --save-board; its report
    goes to a file beside the PCB and is not read (drc() runs after)."""
    out = Path(pcb).with_suffix(".fill_drc.json")
    run("pcb", "drc", "--refill-zones", "--save-board", "--format", "json", "--output", out, pcb, ok=(0, 5),
        verbose=verbose)
    out.unlink(missing_ok=True)


def drc(pcb, out, parity=True, verbose=False):
    """KiCad's DRC with every severity, units mm, schematic parity when the schematic is beside the PCB -> findings
    in the form EasyEDA's DRC has in drc.json: {"errorType", "ruleName", "severity", "description", "items"}."""
    args = ["pcb", "drc", "--format", "json", "--units", "mm", "--severity-all", "--output", out]
    if parity and Path(pcb).with_suffix(".kicad_sch").exists():
        args.append("--schematic-parity")
    run(*args, pcb, ok=(0, 5), verbose=verbose)
    return findings(json.loads(Path(out).read_text(encoding="utf-8")))


def findings(report):
    """KiCad's DRC or ERC report (JSON) -> findings: violations, unconnected items and schematic parity, each with its
    type, severity and the items it names; exclusions and severity "ignore" left out."""
    out = []
    sheets = report.get("sheets")
    groups = [("violation", v) for s in sheets for v in s.get("violations", [])] if sheets is not None else []
    groups += [("violation", v) for v in report.get("violations", [])]
    groups += [("unconnected", v) for v in report.get("unconnected_items", [])]
    groups += [("parity", v) for v in report.get("schematic_parity", [])]
    for kind, v in groups:
        if v.get("excluded") or v.get("severity") == "ignore":
            continue
        out.append({"errorType": v.get("type", kind), "ruleName": kind, "severity": v.get("severity", "error"),
                    "description": v.get("description", ""),
                    "items": [i.get("description", "") for i in v.get("items", [])]})
    return out


def erc(sch, out, verbose=False):
    run("sch", "erc", "--format", "json", "--units", "mm", "--severity-all", "--output", out, sch, ok=(0, 5),
        verbose=verbose)
    return findings(json.loads(Path(out).read_text(encoding="utf-8")))


def netlist(sch, out, verbose=False):
    """The schematic's netlist -> ({net: [ref.pin]}, {ref: {field: value}}) – KiCad's own export (kicadsexpr), read
    without trusting edakit's writer."""
    run("sch", "export", "netlist", "--format", "kicadsexpr", "--output", out, sch, verbose=verbose)
    return read_netlist(Path(out).read_text(encoding="utf-8"))


def read_netlist(text):
    root = sexp.loads(text)
    nets, comps = {}, {}
    for comp in sexp.find(sexp.first(root, "components") or [], "comp"):
        ref = str(sexp.value(comp, "ref", ""))
        fields = {str(sexp.value(f, "name", "")): str(f[2]) if len(f) > 2 and not isinstance(f[2], list) else ""
                  for f in sexp.find(sexp.first(comp, "fields") or [], "field")}
        fields |= {str(sexp.value(p, "name", "")): str(sexp.value(p, "value", "")) for p in sexp.find(comp, "property")}
        fields["value"] = str(sexp.value(comp, "value", ""))
        fields["footprint"] = str(sexp.value(comp, "footprint", ""))
        comps[ref] = fields
    for net in sexp.find(sexp.first(root, "nets") or [], "net"):
        name = str(sexp.value(net, "name", ""))
        pins = [f"{sexp.value(n, 'ref')}.{sexp.value(n, 'pin')}" for n in sexp.find(net, "node")]
        if name.startswith("/"):            # KiCad prefixes labels of the root sheet with its path
            name = name[1:]
        nets[name] = pins
    return nets, comps


def gerbers(pcb, out, verbose=False):
    """Gerber files of the layers the manufacturer builds from, into the folder out (KiCad's names)."""
    Path(out).mkdir(parents=True, exist_ok=True)
    run("pcb", "export", "gerbers", "--output", f"{out}/", "--layers", ",".join(GERBER_LAYERS), "--exclude-value",
        "--no-protel-ext", pcb, verbose=verbose)
    return sorted(Path(out).glob("*.gbr"))


def drill(pcb, out, verbose=False):
    """Excellon drill files, mm, plated and not plated in files of their own, slots as G85 (gerber.parse_drills)."""
    Path(out).mkdir(parents=True, exist_ok=True)
    run("pcb", "export", "drill", "--output", f"{out}/", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "--excellon-oval-format", "alternate", "--drill-origin", "absolute", pcb,
        verbose=verbose)
    return sorted(Path(out).glob("*.drl"))


def pos(pcb, out, verbose=False):
    """The position file (CSV, mm, both sides) -> [{ref, val, package, x, y, rot, side}]; x, y in mm, y up – KiCad
    writes the board's y negated."""
    run("pcb", "export", "pos", "--output", out, "--format", "csv", "--units", "mm", "--side", "both", pcb,
        verbose=verbose)
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [{"ref": r.get("Ref", ""), "val": r.get("Val", ""), "package": r.get("Package", ""),
             "x": float(r.get("PosX", 0)), "y": float(r.get("PosY", 0)), "rot": float(r.get("Rot", 0)),
             "side": (r.get("Side") or "top").lower()} for r in rows]


def pdf_schematic(sch, out, verbose=False):
    run("sch", "export", "pdf", "--output", out, sch, verbose=verbose)
    return Path(out)


def pdf_pcb(pcb, out, verbose=False):
    run("pcb", "export", "pdf", "--output", out, "--layers", "F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts", pcb,
        verbose=verbose)
    return Path(out)


def render(pcb, out, side="top", verbose=False):
    """A 3D picture of the board from one side (pcb-reviewer)."""
    run("pcb", "render", "--output", out, "--side", side, "--width", "1600", "--height", "1200", pcb,
        verbose=verbose)
    return Path(out)
