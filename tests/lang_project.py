"""Helpers of the language's tests: led-bar's source written out (the loop expanded by hand) and a project copy whose
[project] graph is a .circuit file."""

import json
import re

from lang_examples import LED_BAR

PIN_REFERENCE = "'<designator>.<pin>' with the pin numbers of the EasyEDA/LCSC symbol"


def flat(text=LED_BAR):
    """led-bar's source with the `for` written out, as a source without loops states it."""
    head, _, rest = text.partition("for n in 0..7\n")
    body, _, tail = rest.partition("\n\n")
    out = []
    for n in range(8):
        for ln in body.splitlines():
            s = re.sub(r"\{n\+(\d+)\}", lambda m: str(n + int(m.group(1))), ln[2:])
            out.append(s.replace("{n}", str(n)))
    return head + "\n".join(out) + "\n\n" + tail


def as_fixture(text):
    """The source with the fixture's convention pin_reference – the converter writes the word rule's (language 5.1)."""
    return re.sub(r'convention pin_reference "[^"]*"', f'convention pin_reference "{PIN_REFERENCE}"', text)


def to_circuit(project, text=None):
    """The example with its graph as hardware/graph.circuit, named by [project] graph; graph.json gone."""
    (project.root / "hardware" / "graph.circuit").write_text(text or as_fixture(flat()), encoding="utf-8")
    project.graph_file.unlink()
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('graph = "hardware/graph.json"', 'graph = "hardware/graph.circuit"'))
    return project.config()


def fixture_graph(project):
    return json.loads(project.graph_file.read_text(encoding="utf-8"))["graph"]
