"""The pcb reviewer's questions of the domains (maker-coverage review topics pcb-rf and pcb-thermal-pads): exposed pads
from core for every board, antenna areas from radio where the domain is on."""

from edakit import cli


def pcb_questions(project, capsys):
    assert cli.main(["domains", "--review", "pcb", "--config", str(project.root / "edakit.toml")]) == 0
    return capsys.readouterr().out


def test_every_board_gets_the_question_on_exposed_pads(project, capsys):
    out = pcb_questions(project, capsys)
    assert "Exposed pads: under every part with a thermal or exposed pad" in out
    assert "Antenna areas" not in out


def test_the_domain_radio_adds_the_antenna_areas(project, capsys):
    g = project.graph()
    g["graph"].setdefault("purpose", {})["radio"] = "off"
    project.save_graph(g)
    out = pcb_questions(project, capsys)
    assert "Antenna areas: for every part with a printed or chip antenna" in out
