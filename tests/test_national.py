"""The country of the purpose (proposal #94): purpose.country names the member state whose national rules the
regulatory review applies – the domain questions name its references from edakit/national.toml, edakit domains
--review regulatory adds a line with them; without the key the texts stay as they are, a country the table lacks gets
the EU rules and says so. Support, not legal advice."""

import pytest
from helpers import check

from edakit import cli, national, profile
from edakit.design import Design


def with_country(project, country, market="EU"):
    g = project.graph()
    g["graph"]["purpose"]["country"] = country
    if market is None:
        g["graph"]["purpose"].pop("market")
    else:
        g["graph"]["purpose"]["market"] = market
    project.save_graph(g)


def regulatory(project, capsys):
    assert cli.main(["domains", "--review", "regulatory", "--config", str(project.root / "edakit.toml")]) == 0
    return capsys.readouterr().out


def purpose_errors(project):
    cfg = project.config()
    return [m for c, m in check(Design.from_config(cfg), cfg).errors if c == "STRUCT.purpose"]


def test_without_country_the_questions_name_german_law_as_today(project, capsys):
    out = regulatory(project, capsys)
    assert "in Germany it must meet the EMC requirements in substance – EMVG § 6 covers putting into service and " \
           "passing on, a radio product FuAG § 7 – without the formalities of a sale" in out
    assert "National law" not in out


def test_austria_names_the_austrian_references(project, capsys):
    with_country(project, "AT")
    out = regulatory(project, capsys)
    assert "in Austria it must meet the EMC requirements in substance – EMVV 2015 § 5" in out
    assert "a radio product FMaG 2016 § 24" in out
    assert "EMVG" not in out and "FuAG" not in out
    line = next(x for x in out.splitlines() if x.startswith("National law (AT"))
    for want in ("EMVV 2015 § 5", "ChemG 1996 § 19 Abs. 5", "EAG-VO", "VerpackVO 2014", "ris.bka.gv.at"):
        assert want in line, want


def test_the_radio_question_sets_the_country_of_the_purpose(project, capsys):
    with_country(project, "AT")
    prof = profile.ProjectProfile(["radio"], "private", country="AT")
    assert any('esp_wifi_set_country_code("AT", false)' in q for q in prof.review["regulatory"])
    assert any('esp_wifi_set_country_code("DE", false)' in q
               for q in profile.ProjectProfile(["radio"], "private").review["regulatory"])


def test_a_member_state_without_references_gets_the_eu_rules(project, capsys):
    with_country(project, "FR")
    out = regulatory(project, capsys)
    assert "EMVG" not in out and "Germany" not in out
    assert "the EMC directive 2014/30/EU" in out
    line = next(x for x in out.splitlines() if x.startswith("National law (FR"))
    assert "edakit has no national references for FR" in line
    assert purpose_errors(project) == []


@pytest.mark.parametrize("country, market", [("CH", "EU"), ("at", "EU"), ("AUT", "EU"), ("AT", "US"), (49, "EU")])
def test_a_country_outside_the_market_is_an_error(project, country, market):
    with_country(project, country, market)
    errors = purpose_errors(project)
    assert len(errors) == 1 and errors[0].startswith("purpose.country")
    assert "member state of the EU" in errors[0]


@pytest.mark.parametrize("market", ["EU", None])
def test_austria_is_no_error(project, market):
    with_country(project, "AT", market)              # edakit knows one market, the EU: without market it is meant
    assert purpose_errors(project) == []


def test_the_table_is_complete_and_its_placeholders_known():
    assert national.lint() == []
    assert set(national.table()) >= {"EU", "DE", "AT"}
    for code in ("DE", "AT", "EU"):
        assert set(national.table()[code]["topics"]) == set(national.TOPICS)
        for entry in national.table()[code]["topics"].values():
            assert entry["name"] and entry["url"].startswith("https://")
