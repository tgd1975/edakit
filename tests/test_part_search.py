"""edakit part search (#37): JLCPCB's public parts catalogue searched without EasyEDA – C99… dropped, Basic first,
then by stock, an LCSC number only as the exact hit.

fixtures/catalogue/ holds the catalogue's answers (selectSmtComponentList, 2026-10-27, pageSize 25) to "RGB LED 5mm
common cathode" and to "C2297", trimmed to the fields edakit reads. No test goes to the network: `part.catalogue_search`
answers from them."""

import json
import urllib.error
from pathlib import Path

import pytest

from edakit import cli, part

ANSWERS = Path(__file__).resolve().parent / "fixtures" / "catalogue"


def hit(code, mpn, library, stock, preferred=False):
    return {"componentCode": code, "componentModelEn": mpn, "componentBrandEn": "Maker", "componentTypeEn": "LEDs",
            "componentSpecificationEn": "0805", "componentLibraryType": library, "preferredComponentFlag": preferred,
            "stockCount": stock}


FIVE = [hit("C100", "EXT-LOW", "expand", 120), hit("C9900005314", "USER-LIB", "expand", 0),
        hit("C200", "BASIC", "base", 50), hit("C300", "EXT-EMPTY", "expand", 0), hit("C400", "EXT-HIGH", "expand", 900)]


@pytest.fixture
def catalogue(monkeypatch):
    """keyword -> hits; the keywords asked for, in order."""
    answers, asked = {}, []

    def search(keyword, page_size=25):
        asked.append((keyword, page_size))
        a = answers[keyword]
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(part, "catalogue_search", search)
    answers["RGB LED 5mm common cathode"] = json.loads((ANSWERS / "rgb-led-5mm-common-cathode.json").read_text())
    answers["C2297"] = json.loads((ANSWERS / "C2297.json").read_text())
    answers["five"] = FIVE
    return answers, asked


def run(project, *args):
    return cli.main(["part", "search", *args, "--config", str(project.root / "edakit.toml")])


def codes(out):
    return [line.split()[0] for line in out.splitlines() if line.startswith("C")]


def test_one_query_finds_the_rgb_leds(project, catalogue, capsys):
    """pytree: about 30 searches over 45 min until C6751358 – one query to the catalogue lists it."""
    assert run(project, "RGB LED 5mm common cathode") == 0
    out = capsys.readouterr().out
    assert "C6751358" in codes(out) and "C7371894" in codes(out)
    assert codes(out)[:3] == ["C51933351", "C330759", "C7371894"]          # all Extended: by stock, 24694 … 4239
    assert "WP154A4SUREQBFZGC" in out and "Kingbright" in out and "Plugin,D=5mm" in out
    assert 'JLCPCB catalogue, "RGB LED 5mm common cathode"' in out


def test_listing_order_and_filters(project, catalogue, capsys):
    assert run(project, "five") == 0
    out = capsys.readouterr().out
    assert codes(out) == ["C200", "C400", "C100", "C300"]                  # no C99…; Basic, then stock
    assert "1 C99… number dropped" in out
    assert run(project, "five", "--basic") == 0
    assert codes(capsys.readouterr().out) == ["C200"]
    assert run(project, "five", "--min-stock", "100") == 0
    assert codes(capsys.readouterr().out) == ["C400", "C100"]


def test_preferred_extended_counts_as_basic(project, catalogue, capsys):
    answers, _ = catalogue
    answers["pref"] = [hit("C1", "EXT", "expand", 999), hit("C2", "PREF", "expand", 5, preferred=True)]
    assert run(project, "pref", "--basic") == 0
    out = capsys.readouterr().out
    assert codes(out) == ["C2"] and "Extended, preferred" in out


def test_an_lcsc_number_gives_only_its_exact_hit(project, catalogue, capsys):
    """Full text: C2297 also finds MIC2297, LTC2297, XC2297 … – F-2 takes the exact number only, so does search."""
    assert run(project, "C2297") == 0
    assert codes(capsys.readouterr().out) == ["C2297"]


def test_nothing_found(project, catalogue, capsys):
    answers, _ = catalogue
    answers["nothing"] = []
    assert run(project, "nothing") == 2
    assert "no hits" in capsys.readouterr().out


def test_network_error(project, catalogue, capsys):
    answers, _ = catalogue
    answers["offline"] = urllib.error.URLError("Name or service not known")
    assert run(project, "offline") == 1
    assert "edakit part: the catalogue did not answer" in capsys.readouterr().err


def test_limit_and_json(project, catalogue, tmp_path):
    _, asked = catalogue
    out = tmp_path / "hits.json"
    assert run(project, "five", "--limit", "10", "--json", str(out)) == 0
    assert asked[-1] == ("five", 10)
    data = json.loads(out.read_text())
    assert data["query"] == "five" and [h["lcsc"] for h in data["hits"]] == ["C200", "C400", "C100", "C300"]
    assert data["hits"][0] == {"lcsc": "C200", "mpn": "BASIC", "manufacturer": "Maker", "category": "LEDs",
                               "package": "0805", "class": "Basic", "stock": 50}
