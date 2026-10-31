"""The command line: what needs no project runs anywhere."""

from edakit import cli


def test_block_list_show_and_rules_need_no_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    assert cli.main(["block", "list"]) == 0
    assert cli.main(["block", "show", "led"]) == 0
    assert cli.main(["rules", "STRUCT.pin"]) == 0
    out = capsys.readouterr().out
    assert "usb-c-sink" in out and "led: " in out and "STRUCT" in out
