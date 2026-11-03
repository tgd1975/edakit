"""The maker's inventory (docs/concepts/done/parts-on-hand.md): a table in .md, .html, .csv, .xlsx or .ods, named in
edakit.local.toml, read and never written – edakit order takes from it first and orders the rest. The example's J1
(C131337, B2B-PH-K-S(LF)(SN), bom: false) is soldered by hand: 5 sets, 5 pieces.
"""

import csv
import json
import subprocess
import zipfile

import pytest

from edakit import cli, inventory


def run(project, monkeypatch, *args):
    monkeypatch.chdir(project.root)
    monkeypatch.delenv("EDAKIT_CONFIG", raising=False)
    return cli.main(list(args))


def out_dir(project):
    return project.root / "build" / "edakit" / "order"


def cart(project):
    path = out_dir(project) / "cart_lcsc.csv"
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))[1:]


def local(project, text):
    (project.root / "edakit.local.toml").write_text(text, encoding="utf-8")


def md_inventory(project, rows, name="inventory.md", head="| ID | Name | LCSC | Quantity |"):
    lines = ["# My parts", "", "Some prose with a [link](other.md).", "", head, "|" + " --- |" * (head.count("|") - 1)]
    lines += [f"| {' | '.join(map(str, r))} |" for r in rows]
    (project.root / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return name


def test_without_settings_nothing_changes(project, monkeypatch):
    assert run(project, monkeypatch, "order") == 0
    assert cart(project) == [["C131337", "5", "B2B-PH-K-S(LF)(SN): J1 (5 + 0)"]]
    assert "From" not in (out_dir(project) / "hand_assembly.md").read_text()


def test_the_cart_takes_what_is_on_hand_first(project, monkeypatch, capsys):
    md_inventory(project, [("JST-PH2", "JST PH 2-pin", "C131337", 3), ("NE555N", "timer", "", 4)])
    local(project, '[inventory]\nfiles = "inventory.md"\n')
    assert run(project, monkeypatch, "order") == 0
    assert cart(project) == [["C131337", "2", "B2B-PH-K-S(LF)(SN): J1 (5 + 0, 3 on hand)"]]
    hand = (out_dir(project) / "hand_assembly.md").read_text()
    assert "| Designator | Part | Side | Supplier | From |" in hand and "| on hand + cart |" in hand
    assert "## Out of the drawer" in hand and "| JST-PH2 (JST PH 2-pin) – inventory.md, table at line 5, row 7 | J1 |" in hand
    basket = json.loads((out_dir(project) / "basket.json").read_text())
    assert basket["suppliers"]["lcsc"][0]["on_hand"] == 3 and basket["suppliers"]["lcsc"][0]["qty"] == 2
    assert "inventory: 3 pieces on 1 line from the drawer" in capsys.readouterr().out
    assert "| JST-PH2 | JST PH 2-pin | C131337 | 3 |" in (project.root / "inventory.md").read_text()   # never written


def test_enough_on_hand_writes_no_cart_line(project, monkeypatch):
    md_inventory(project, [("JST-PH2", "", "C131337", 7)])
    local(project, '[inventory]\nfiles = ["inventory.md"]\n')
    assert run(project, monkeypatch, "order") == 0
    assert cart(project) is None
    assert "lcsc" not in json.loads((out_dir(project) / "basket.json").read_text())["suppliers"]
    assert "| on hand |" in (out_dir(project) / "hand_assembly.md").read_text()


def test_spares_and_minimum_count_before_and_after_the_inventory(project, monkeypatch):
    """need plus spares is what the inventory is asked for; the rest is rounded to moq and step."""
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace("quantity = 5 ", "quantity = 5\nspare_pct = 10 ", 1))
    md_inventory(project, [("x", "", "C131337", 6)])
    local(project, '[inventory]\nfiles = "inventory.md"\n')
    assert run(project, monkeypatch, "order") == 0
    assert cart(project) is None                       # 5 + 1 spare, 6 on hand
    part = project.part("C131337")
    part["order"] = {"lcsc": {"moq": 10}}
    project.save_part("C131337", part)
    md_inventory(project, [("x", "", "C131337", 3)])
    assert run(project, monkeypatch, "order") == 0
    assert cart(project) == [["C131337", "10", "B2B-PH-K-S(LF)(SN): J1 (5 + 8, 3 on hand)"]]


def test_the_id_as_mpn_and_the_lcsc_map(project, monkeypatch):
    md_inventory(project, [("b2b-ph-k-s (lf)(sn)", "", "", 2)])
    local(project, '[inventory]\nfiles = "inventory.md"\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "3"]
    md_inventory(project, [("JST-PH2", "", "", 4)])
    (project.root / "map.csv").write_text("ID;LCSC\nJST-PH2;c131337\n", encoding="utf-8")
    local(project, '[inventory]\nfiles = "inventory.md"\nlcsc_map = "map.csv"\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "1"]


def test_rows_in_several_files_and_tables_are_summed(project, monkeypatch):
    md_inventory(project, [("JST-PH2", "drawer 1", "C131337", 1)], name="inventory_a.md")
    md_inventory(project, [("JST-PH2", "drawer 2", "C131337", 2)], name="inventory_b.md")
    local(project, '[inventory]\nfiles = ["inventory_*.md"]\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "2"]
    hand = (out_dir(project) / "hand_assembly.md").read_text()
    assert "inventory_a.md" in hand and "inventory_b.md" in hand


def test_a_basket_takes_from_the_inventory_once(project, monkeypatch):
    md_inventory(project, [("JST-PH2", "", "C131337", 6)])
    local(project, '[inventory]\nfiles = "inventory.md"\n')
    assert run(project, monkeypatch, "order", "--with", str(project.root / "edakit.toml")) == 0
    rows = cart(project)
    assert rows[0][:2] == ["C131337", "4"] and rows[0][2].endswith(" | 6 on hand")


def test_the_maker_s_own_column_names(project, monkeypatch):
    md_inventory(project, [("JST-PH2", "C131337", 5, "Fach 3")], head="| Teil | LCSC-Nr. | Anzahl | Ort |")
    local(project, '[inventory]\nfiles = "inventory.md"\n[inventory.columns]\nid = "Teil"\nquantity = "anzahl"\n'
                   'lcsc = "LCSC-Nr."\n')
    run(project, monkeypatch, "order")
    assert cart(project) is None


# --- the formats ------------------------------------------------------------------------------------------------------

def test_csv_with_semicolons_in_windows_1252(project, monkeypatch):
    (project.root / "teile.csv").write_bytes("Fach;ID;Quantity;Description\n3;C131337-ish;1;Stecker für Akku\n"
                                             "4;B2B-PH-K-S(LF)(SN);2;JST\n".encode("cp1252"))
    local(project, '[inventory]\nfiles = "teile.csv"\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "3"]
    rows = inventory.read(inventory.settings(project.config()))
    assert rows[0].description == "Stecker für Akku"


def test_html_reads_every_table_with_the_columns(project, monkeypatch):
    (project.root / "inv.html").write_text(
        "<html><body><table><tr><th>Shelf</th><th>Notes</th></tr><tr><td>A</td><td>x</td></tr></table>"
        "<table><tr><th>ID</th><th>LCSC</th><th>Quantity</th></tr>"
        "<tr><td><a href='x'>JST</a></td><td>C131337</td><td> 4 </td></tr></table></body></html>", encoding="utf-8")
    local(project, '[inventory]\nfiles = "inv.html"\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "1"]


def test_xlsx_every_sheet_with_the_columns(project, monkeypatch):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "Notes"
    wb.active.append(["just", "notes"])
    ws = wb.create_sheet("Connectors")
    ws.append([])
    ws.append(["Fach", "id", "LCSC", "QUANTITY"])
    ws.append(["3", "JST", "C131337", 2.0])
    ws.append([None, None, None, None])
    wb.create_sheet("Leds").append(["ID", "Quantity"])
    wb.save(project.root / "inv.xlsx")
    local(project, '[inventory]\nfiles = "inv.xlsx"\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "3"]
    assert "sheet 'Connectors', row 3" in (out_dir(project) / "hand_assembly.md").read_text()


def test_xlsx_formula_without_a_saved_value(project, monkeypatch, capsys):
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["ID", "Quantity"])
    wb.active.append(["JST", "=2+2"])
    wb.save(project.root / "inv.xlsx")
    local(project, '[inventory]\nfiles = "inv.xlsx"\n')
    assert run(project, monkeypatch, "order") == 1
    assert "the formula =2+2 has no saved value" in capsys.readouterr().err


ODS_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
<office:body><office:spreadsheet>
<table:table table:name="Teile">
 <table:table-row table:number-rows-repeated="2"><table:table-cell table:number-columns-repeated="16384"/></table:table-row>
 <table:table-row>
  <table:table-cell office:value-type="string"><text:p>ID</text:p></table:table-cell>
  <table:table-cell table:number-columns-repeated="2"/>
  <table:table-cell office:value-type="string"><text:p>LCSC</text:p></table:table-cell>
  <table:table-cell office:value-type="string"><text:p>Quan<text:span>tity</text:span></text:p></table:table-cell>
  <table:table-cell office:value-type="string"><text:p>Name</text:p></table:table-cell>
  <table:table-cell table:number-columns-repeated="16378"/>
 </table:table-row>
 <table:table-row>
  <table:table-cell office:value-type="string"><text:p>JST</text:p></table:table-cell>
  <table:table-cell table:number-columns-repeated="2"/>
  <table:table-cell office:value-type="string"><text:p>C131337</text:p></table:table-cell>
  <table:table-cell office:value-type="float" office:value="4"><text:p>4</text:p></table:table-cell>
  <table:table-cell office:value-type="string"><text:p>PH<text:s/>2<text:s text:c="2"/>pin</text:p></table:table-cell>
 </table:table-row>
 <table:table-row table:number-rows-repeated="1048570"><table:table-cell table:number-columns-repeated="16384"/></table:table-row>
</table:table>
</office:spreadsheet></office:body></office:document-content>
"""


def write_ods(path, content):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", content)


def test_ods_with_repeated_rows_and_columns(project, monkeypatch):
    write_ods(project.root / "inv.ods", ODS_CONTENT)
    local(project, '[inventory]\nfiles = "inv.ods"\n')
    run(project, monkeypatch, "order")
    assert cart(project)[0][:2] == ["C131337", "1"]
    row = inventory.read(inventory.settings(project.config()))[0]
    assert (row.line, row.name, row.quantity) == (4, "PH 2  pin", 4)


def test_md_tables_in_a_code_fence_are_text(project):
    tables = inventory.read_md("```\n| ID | Quantity |\n| --- | --- |\n| x | 1 |\n```\n\n| ID | Quantity |\n|:---|---:|\n"
                               "| [a \\| b](p.md) | 2 |\n")
    assert len(tables) == 1 and tables[0][1][1] == (9, ["a | b", "2"])


# --- the errors -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("files, setup, message", [
    ('"nowhere.md"', None, "inventory: nowhere.md not found (edakit.local.toml)"),
    ('["inv_*.md"]', None, "inventory: inv_*.md matches no file"),
    ('"inv.md"', "| Part | Qty |\n| --- | --- |\n| x | 1 |\n",
     "inventory: inv.md has no table with the columns ID, Quantity – found table at line 1: Part, Qty"),
    ('"inv.md"', "# nothing\n", "has no table at all"),
    ('"inv.md"', "| ID | Quantity |\n| --- | --- |\n| R1 | ~10 |\n", "row 3 (R1): Quantity '~10' is no whole number >= 0"),
    ('"inv.md"', "| ID | Quantity |\n| --- | --- |\n| R1 |  |\n", "row 3 (R1): Quantity empty"),
    ('"inv.md"', "| ID | Quantity |\n| --- | --- |\n|  | 3 |\n", "row 3: no ID"),
    ('"inv.txt"', "x", "edakit reads .md, .html, .htm, .csv, .xlsx, .ods"),
])
def test_a_named_inventory_edakit_cannot_read_stops_the_order(project, monkeypatch, capsys, files, setup, message):
    if setup is not None:
        name = files.strip('"[]')
        (project.root / name).write_text(setup, encoding="utf-8")
    local(project, f"[inventory]\nfiles = {files}\n")
    assert run(project, monkeypatch, "order") == 1
    err = capsys.readouterr().err
    assert message in err and "edakit order stops" in err
    assert not out_dir(project).exists()


@pytest.mark.parametrize("text, message", [
    ("[inventory]\nfile = 'x.md'\n", "unknown key 'inventory.file'"),
    ("[stock]\n", "unknown table or key 'stock'"),
    ("[inventory]\nfiles = 'x.md'\n[inventory.columns]\nqty = 'Anzahl'\n", "unknown column 'inventory.columns.qty'"),
    ("[inventory]\nfiles = 'x.md'\n[inventory.columns]\nname = 'ID'\n", "columns id and name have the same name"),
    ("[inventory\n", "edakit.local.toml:"),
])
def test_settings_keys(project, monkeypatch, capsys, text, message):
    local(project, text)
    assert run(project, monkeypatch, "order") == 1
    assert message in capsys.readouterr().err


def test_an_id_mapped_to_two_numbers(project, monkeypatch, capsys):
    md_inventory(project, [("JST", "", "", 1)])
    (project.root / "map.md").write_text("| ID | LCSC |\n| --- | --- |\n| JST | C1 |\n| jst | C2 |\n", encoding="utf-8")
    local(project, '[inventory]\nfiles = "inventory.md"\nlcsc_map = "map.md"\n')
    assert run(project, monkeypatch, "order") == 1
    assert "jst is mapped to C1 (table at line 1, row 3) and to C2" in capsys.readouterr().err


def test_settings_without_files_change_nothing(project, monkeypatch):
    local(project, "[inventory]\n[inventory.columns]\nid = 'Teil'\n")
    assert run(project, monkeypatch, "order") == 0
    assert cart(project)[0][:2] == ["C131337", "5"]


# --- edakit inventory -------------------------------------------------------------------------------------------------

def test_the_report_and_a_query(project, monkeypatch, capsys):
    md_inventory(project, [("JST-PH2", "JST PH 2-pin", "C131337", 3), ("NE555N", "timer DIP-8", "", 4)])
    local(project, '[inventory]\nfiles = "inventory.md"\n')
    assert run(project, monkeypatch, "inventory") == 0
    out = capsys.readouterr().out
    assert out.startswith("Inventory: inventory.md (") and "2 rows" in out
    line = next(ln for ln in out.splitlines() if ln.startswith("B2B-PH-K-S(LF)(SN)"))
    assert line.split()[:7] == ["B2B-PH-K-S(LF)(SN)", "C131337", "J1", "5", "+", "0", "3"]
    assert "JST-PH2 (JST PH 2-pin) × 3" in line and "0 of 1 lines on hand in full, 1 to order" in out
    assert run(project, monkeypatch, "inventory", "dip", "TIMER") == 0
    out = capsys.readouterr().out
    assert "NE555N" in out and "JST-PH2" not in out
    assert run(project, monkeypatch, "inventory", "nothing-like-it") == 1


def test_the_report_without_an_inventory(project, monkeypatch, capsys):
    assert run(project, monkeypatch, "inventory") == 1
    assert "names no inventory – edakit inventory template FILE" in capsys.readouterr().err


@pytest.mark.parametrize("ext", [".md", ".xlsx", ".ods"])
def test_a_template_is_read_back_and_named(project, monkeypatch, capsys, ext):
    target = project.root / "private" / f"inventory{ext}"
    assert run(project, monkeypatch, "inventory", "template", f"private/inventory{ext}") == 0
    s = inventory.settings(project.config())
    assert s.files == [target] and s.raw_files == [f"private/inventory{ext}"]
    assert inventory.read(s) == []                    # a table with its header and no rows is an inventory
    tables = inventory.read_tables(target)
    assert [inventory._cell(c) for c in inventory.header(tables[0][1])[2]] == [
        "ID", "Name", "LCSC", "Quantity", "Description", "Link"]
    ignored = (project.root / ".gitignore").read_text().splitlines()
    assert "/edakit.local.toml" in ignored and f"/private/inventory{ext}" in ignored
    assert run(project, monkeypatch, "inventory", "template", f"private/inventory{ext}") == 1
    assert "edakit never overwrites an inventory" in capsys.readouterr().err


def test_a_template_with_the_maker_s_names_beside_files_named_already(project, monkeypatch, capsys):
    local(project, "# mine\n[inventory]\nfiles = 'a.md'\n[inventory.columns]\nquantity = 'Anzahl'\n")
    (project.root / "a.md").write_text("| ID | Anzahl |\n| --- | --- |\n", encoding="utf-8")
    assert run(project, monkeypatch, "inventory", "template", "b.md") == 0
    assert "names other files already – add b.md" in capsys.readouterr().out
    assert "| ID | Name | LCSC | Anzahl | Description | Link |" in (project.root / "b.md").read_text()


def test_a_template_into_settings_without_files(project, monkeypatch):
    local(project, "[inventory]\nlcsc_map = 'map.csv'\n")
    assert run(project, monkeypatch, "inventory", "template", "inv.md") == 0
    assert "files = [\"inv.md\"]" in (project.root / "edakit.local.toml").read_text()
    assert "lcsc_map" in (project.root / "edakit.local.toml").read_text()


def test_git_tracking_the_local_file_is_said(project, monkeypatch, capsys):
    md_inventory(project, [("JST", "", "C131337", 1)])
    local(project, '[inventory]\nfiles = "inventory.md"\n')
    root = project.root
    for cmd in (["init", "-q"], ["add", "edakit.local.toml"]):
        subprocess.run(["git", *cmd], cwd=root, check=True, capture_output=True)
    assert run(project, monkeypatch, "order") == 0
    assert "note: git tracks edakit.local.toml" in capsys.readouterr().err


def test_ods_template_is_a_valid_package(tmp_path):
    p = tmp_path / "t.ods"
    inventory.write_template(p, inventory.DEFAULT_NAMES)
    with zipfile.ZipFile(p) as z:
        first = z.infolist()[0]
        assert first.filename == "mimetype" and first.compress_type == zipfile.ZIP_STORED
        assert z.read("mimetype") == b"application/vnd.oasis.opendocument.spreadsheet"
