"""National references of the regulatory review (proposal #94, handbook 15.6): the graph's purpose.country names the
member state whose national rules the review applies. The domains' review questions name them through placeholders
{national.<topic>}, {national.country} and {national.code}, filled from edakit/national.toml; `edakit domains
--review regulatory` adds one line with the country's references and their sources, the agent regulatory-reviewer's
map of national law. Without purpose.country the questions name DE's references, as before, and no line is added; a
member state without a table gets the EU rules and the line says so. Support, not legal advice – nothing here is
legally guaranteed, without any claim to correctness.
"""

from __future__ import annotations

import re
import tomllib
from functools import lru_cache
from pathlib import Path

from .radio import NOT_LEGAL_ADVICE

FILE = Path(__file__).with_name("national.toml")
DEFAULT = "DE"                     # what the questions named before purpose.country existed
TOPICS = {"emc": "EMC", "radio": "radio", "product_safety": "product safety", "product_liability": "product liability",
          "scip": "SCIP", "weee": "WEEE", "batteries": "batteries", "packaging": "packaging"}
# The member states of the EU, ISO 3166-1 alpha-2 (Greece: GR, as ISO has it, not the EU's EL).
MEMBERS = {"AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany",
           "DK": "Denmark", "EE": "Estonia", "ES": "Spain", "FI": "Finland", "FR": "France", "GR": "Greece",
           "HR": "Croatia", "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg",
           "LV": "Latvia", "MT": "Malta", "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
           "SE": "Sweden", "SI": "Slovenia", "SK": "Slovakia"}
PLACEHOLDER = re.compile(r"\{national\.(\w+)\}")


@lru_cache(maxsize=1)
def table():
    """{"EU" | member state: {country, checked, topics: {topic: {name, url, note?}}}}."""
    return tomllib.loads(FILE.read_text(encoding="utf-8"))


def problem(purpose):
    """The text of STRUCT.purpose for purpose.country, None where it is fine or absent: an ISO 3166-1 alpha-2 code of
    a member state of the market – the EU, the one market edakit knows (purpose.market "EU" or none)."""
    purpose = purpose or {}
    if "country" not in purpose:
        return None
    c, market = purpose["country"], purpose.get("market", "EU")
    if isinstance(c, str) and c in MEMBERS and market == "EU":
        return None
    beyond = f"; purpose.market is {market!r}, and edakit knows the member states of the EU only" \
        if market != "EU" else ""
    return (f"purpose.country {c!r}: the ISO 3166-1 alpha-2 code of a member state of the EU ({', '.join(MEMBERS)})"
            f"{beyond} – the regulatory review (M-6) takes its national law from it")


def country(purpose):
    """The member state of a valid purpose.country, else None (STRUCT.purpose reports a wrong one)."""
    return None if problem(purpose) else (purpose or {}).get("country")


def refs(code):
    """The references for a member state (None: the default, DE): (country name, known, {topic: entry}) – known False
    for a member state without a table, whose entries are the EU rules with its name filled in."""
    code = code or DEFAULT
    known = code in table() and code != "EU"
    t = table()[code if known else "EU"]
    name = MEMBERS.get(code, code)
    topics = {k: {**e, "name": e["name"].replace("{country}", name)} for k, e in t["topics"].items()}
    return name, known, topics


def fill(text, code=None):
    """A review question with its placeholders filled for the member state (None: DE, as before)."""
    name, _, topics = refs(code)
    values = {"country": name, "code": code or DEFAULT, **{k: e["name"] for k, e in topics.items()}}
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], text)


def line(code):
    """The line `edakit domains --review regulatory` adds for purpose.country: the references with their sources."""
    name, known, topics = refs(code)
    items = "; ".join(f"{TOPICS[k]}: {e['name']}" + (f" ({e['note']})" if e.get("note") else "") + f" <{e['url']}>"
                      for k, e in topics.items())
    at = f"National law ({code}, {name}"
    if not known:
        return (f"{at}): edakit has no national references for {code} – the review finds the transposition of the EU "
                f"rules itself. The EU rules: {items}. A map, {NOT_LEGAL_ADVICE}.")
    return (f"{at} – edakit/national.toml, checked {table()[code]['checked']}; check every reference against its "
            f"source): {items}. A map, {NOT_LEGAL_ADVICE}.")


def lint(questions=()):
    """Problems of the table and of the placeholders in review questions: every table has every topic with a name and
    an https URL, a member state or EU as its key; every placeholder names a topic, country or code. -> [text]"""
    out = []
    for code, t in table().items():
        at = f"national.toml [{code}]"
        if code != "EU" and code not in MEMBERS:
            out.append(f"{at}: no member state of the EU (ISO 3166-1 alpha-2)")
        if not t.get("country") or not t.get("checked"):
            out.append(f"{at}: needs country and checked")
        topics = t.get("topics") or {}
        for k in sorted(set(TOPICS) - set(topics)):
            out.append(f"{at}: topic {k} missing")
        for k, e in topics.items():
            if k not in TOPICS:
                out.append(f"{at}: topic {k} – one of {', '.join(TOPICS)}")
            if not e.get("name") or not str(e.get("url", "")).startswith("https://"):
                out.append(f"{at}: topic {k} needs name and an https url")
    for where, q in questions:
        for key in PLACEHOLDER.findall(q):
            if key not in TOPICS and key not in ("country", "code"):
                out.append(f"{where}: {{national.{key}}} – one of country, code, {', '.join(TOPICS)}")
    return out
