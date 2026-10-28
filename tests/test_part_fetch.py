"""edakit part fetch (#34): a part's datasheet fetched once, kept beside the project, checked to be of that part.

No test goes to the network: `part._download` answers from the recordings below, `part.catalogue_search` from a
recorded catalogue hit. fixtures/datasheets/ holds LCSC's product data of C2297 (wmsc.lcsc.com, 2026-10-27, trimmed
to the fields edakit reads) and the datasheet page of item.szlcsc.com trimmed to its PDF viewer; the PDFs are made
here, a few hundred bytes each."""

import hashlib
import json
import shutil
import urllib.error
from pathlib import Path

import pytest

from edakit import cli, part

ANSWERS = Path(__file__).resolve().parent / "fixtures" / "datasheets"
ENTRY_URL = "https://item.szlcsc.com/datasheet/KT-0805G/2670.html"          # the example's datasheet.url of C2297
LCSC_URL = "https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=C2297"
LCSC_PDF = "https://datasheet.lcsc.com/datasheet/pdf/de342fde3322df0797012cd7a04e2194.pdf?productCode=C2297"
VIEWER_PDF = "https://atta.szlcsc.com/upload/public/pdf/source/20250710/3FC4C280BF1950D44A000B3513D3602B.pdf"
TODAY = "2026-10-27"
needs_pdftotext = pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext (poppler-utils) not installed")


def pdf(*pages, scan=False):
    """A small, valid PDF: one page per text (Helvetica); scan=True draws a line instead – no text layer."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        content = "0 0 m 300 200 l S" if scan else f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
        objs.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


SHEET = pdf("0805 Package Chip LED, green", "Green 525 nm, 20 mA forward current")       # the KT-0805G sheet never prints KT-0805G


def http(code):
    def fail(url):
        raise urllib.error.HTTPError(url, code, "Not Allowed", {}, None)
    return fail


@pytest.fixture
def web(monkeypatch):
    """The network as a dict url -> bytes or a function raising; the URLs asked for, in order. The catalogue answers
    from `web.catalogue` (keyword -> hits)."""
    class Web(dict):
        pass
    w = Web()
    w.asked, w.catalogue = [], {}

    def download(url):
        w.asked.append(url)
        a = w.get(url, http(404))
        return a(url) if callable(a) else a

    def search(keyword, page_size=25):
        w.asked.append(f"catalogue:{keyword}")
        return w.catalogue.get(keyword, [])
    monkeypatch.setattr(part, "_download", download)
    monkeypatch.setattr(part, "catalogue_search", search)
    return w


def run(project, *args):
    return cli.main(["part", "fetch", *args, "--config", str(project.root / "edakit.toml")])


def kept(project, key, ext):
    return project.root / "build" / "edakit" / "datasheets" / f"{key}.{ext}"


def record(project, key):
    return json.loads(kept(project, key, "json").read_text())


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(part, "today", lambda: TODAY)


@needs_pdftotext
def test_falls_back_to_lcsc_product_data(project, web, capsys):
    """The example's datasheet.url answers 405 (2026-10-26, curl); LCSC's product data gives the PDF."""
    before = (project.root / "hardware" / "parts" / "C2297.json").read_bytes()
    web[ENTRY_URL] = http(405)
    web[LCSC_URL] = (ANSWERS / "lcsc-C2297.json").read_bytes()
    web[LCSC_PDF] = SHEET
    assert run(project, "C2297") == 0
    assert kept(project, "C2297", "pdf").read_bytes() == SHEET
    r = record(project, "C2297")
    assert r == {"key": "C2297", "mpn": "KT-0805G", "url": LCSC_PDF, "source": "LCSC product data",
                 "sha256": hashlib.sha256(SHEET).hexdigest(), "fetched": TODAY, "bytes": len(SHEET), "pages": 2,
                 "text": True, "names_mpn": "no"}
    out = capsys.readouterr().out
    assert f"datasheet.url {ENTRY_URL}: HTTP 405" in out
    assert "NOTE    the text does not name KT-0805G" in out
    assert (project.root / "hardware" / "parts" / "C2297.json").read_bytes() == before   # the entry stays as it is
    assert web.asked == [ENTRY_URL, LCSC_URL, LCSC_PDF]


def test_an_html_wrapper_is_followed_once(project, web):
    web[ENTRY_URL] = (ANSWERS / "szlcsc-C2297.html").read_bytes()
    web[VIEWER_PDF] = SHEET
    assert run(project, "C2297") == 0
    r = record(project, "C2297")
    assert (r["url"], r["pdf_url"]) == (ENTRY_URL, VIEWER_PDF)              # the viewer's link, without #page=1
    assert kept(project, "C2297", "pdf").read_bytes() == SHEET


def test_a_wrapper_of_a_wrapper_is_not_followed(project, web, capsys):
    page = b'<!DOCTYPE html><html><body><a href="/sheet.pdf">datasheet</a></body></html>'
    web["https://example.com/part"] = page
    web["https://example.com/sheet.pdf"] = page                            # a link to a page that is HTML again
    assert run(project, "C2297", "--url", "https://example.com/part") == 1  # nothing else answers, nothing kept
    err = capsys.readouterr()
    assert "an HTML page whose PDF link https://example.com/sheet.pdf gave an HTML page" in err.out + err.err
    assert web.asked.count("https://example.com/sheet.pdf") == 1
    assert not kept(project, "C2297", "pdf").exists()


def test_a_failed_retry_keeps_the_copy(project, web, capsys):
    """JLCPCB's signed URLs expire: the second fetch gets an HTML page, the first file stays."""
    web["https://jlcpcb.com/signed/C2297.pdf?Expires=1"] = SHEET
    assert run(project, "C2297", "--url", "https://jlcpcb.com/signed/C2297.pdf?Expires=1") == 0
    first = record(project, "C2297")
    web["https://jlcpcb.com/signed/C2297.pdf?Expires=1"] = b"<html><body>AccessDenied: Request has expired</body></html>"
    web[LCSC_URL] = (ANSWERS / "lcsc-C2297.json").read_bytes()
    web[LCSC_PDF] = SHEET[:200]                                            # a download that broke off
    capsys.readouterr()
    assert run(project, "C2297", "--url", "https://jlcpcb.com/signed/C2297.pdf?Expires=1") == 2
    out = capsys.readouterr().out
    assert f"kept the copy of {TODAY}" in out
    assert "an incomplete PDF" in out and "an HTML page (" in out
    assert kept(project, "C2297", "pdf").read_bytes() == SHEET and record(project, "C2297") == first


@needs_pdftotext
@pytest.mark.parametrize("text, names, code", [("MT3608L High Efficiency 1.2MHz 2A Step Up Converter", "MT3608L", 2),
                                               ("MT3608 High Efficiency 1.2MHz 2A Step Up Converter", "yes", 0)])
def test_a_sheet_of_a_longer_variant_is_a_warning(project, web, capsys, text, names, code):
    """pytree's MT3608: the sheet linked from EasyEDA describes the MT3608L, whose pin 6 is OC instead of NC."""
    e = project.part("C17414")
    project.save_part("C17414", {**e, "mpn": "MT3608", "datasheet": {"url": "https://example.com/mt3608.pdf"}})
    web["https://example.com/mt3608.pdf"] = pdf(text)
    assert run(project, "C17414") == code
    assert record(project, "C17414")["names_mpn"] == names
    out = capsys.readouterr().out
    assert ("WARNING the text names MT3608L, not MT3608" in out) == (code == 2)


@needs_pdftotext
def test_a_scan_has_no_text_layer(project, web, capsys):
    web["https://example.com/scan.pdf"] = pdf("", "", scan=True)
    assert run(project, "C2297", "--url", "https://example.com/scan.pdf") == 0
    r = record(project, "C2297")
    assert (r["text"], r["names_mpn"], r["pages"]) == (False, None, 2)
    assert "NOTE    no text layer: scanned, read the drawings as images" in capsys.readouterr().out


def test_without_pdftotext_the_text_is_not_checked(project, web, monkeypatch, capsys):
    monkeypatch.setattr(part.shutil, "which", lambda name: None)
    web["https://example.com/sheet.pdf"] = SHEET
    assert run(project, "C2297", "--url", "https://example.com/sheet.pdf") == 0
    r = record(project, "C2297")
    assert (r["text"], r["names_mpn"], r["pages"]) == (None, None, 2)       # pages counted in the file itself
    assert "NOTE    pdftotext not on PATH: the text is not checked" in capsys.readouterr().out


def test_jlcpcb_catalogue_is_the_last_source(project, web):
    """No datasheet.url, no pdfUrl at LCSC: the catalogue's dataManualUrl of exactly that number."""
    e = project.part("C2297")
    project.save_part("C2297", {k: v for k, v in e.items() if k != "datasheet"})
    web[LCSC_URL] = json.dumps({"code": 200, "ok": True, "result": {"productCode": "C2297", "pdfUrl": None}}).encode()
    web.catalogue["C2297"] = [{"componentCode": "C3187252", "dataManualUrl": "https://wmsc.lcsc.com/mic2297.pdf"},
                              {"componentCode": "C2297", "dataManualUrl": "https://wmsc.lcsc.com/kt-0805g.pdf"}]
    web["https://wmsc.lcsc.com/kt-0805g.pdf"] = SHEET
    assert run(project, "C2297") == 0
    assert record(project, "C2297")["source"] == "JLCPCB catalogue"
    assert record(project, "C2297")["url"] == "https://wmsc.lcsc.com/kt-0805g.pdf"


def test_a_new_file_against_the_sign_off(project, web, capsys):
    """verified.datasheet_sha256 tells the reader whether they hold the signed file."""
    other = pdf("0805 Package Chip LED, revision B")
    e = project.part("C2297")
    project.save_part("C2297", {**e, "verified": {**e["verified"], "datasheet_sha256": hashlib.sha256(SHEET).hexdigest()}})
    web["https://example.com/sheet.pdf"] = SHEET
    assert run(project, "C2297", "--url", "https://example.com/sheet.pdf") == 0
    assert "the signed file (verified.datasheet_sha256)" in capsys.readouterr().out
    web["https://example.com/sheet.pdf"] = other
    assert run(project, "C2297", "--url", "https://example.com/sheet.pdf") == 2
    out = capsys.readouterr().out
    assert "WARNING changed since the sign-off" in out and f"the copy of {TODAY}" in out
    assert kept(project, "C2297", "pdf").read_bytes() == other


def test_all_fetches_what_is_missing(project, web, capsys):
    """--all: every entry without a kept copy; a kept one is not asked for again."""
    keys = sorted(p.stem for p in (project.root / "hardware" / "parts").glob("*.json"))
    for key in keys:
        project.save_part(key, {**project.part(key), "datasheet": {"url": f"https://example.com/{key}.pdf"}})
        web[f"https://example.com/{key}.pdf"] = pdf(f"{key} datasheet, electrical characteristics")
    assert run(project, "--all") == 0
    assert all(kept(project, k, "pdf").exists() for k in keys)
    web.asked.clear()
    assert run(project, "--all") == 0
    assert web.asked == []
    assert f"C2297: kept, fetched {TODAY}" in capsys.readouterr().out


def test_datasheets_key_keeps_them_in_the_repository(project, web):
    toml = project.root / "edakit.toml"
    toml.write_text(toml.read_text().replace('reports = "build/release"',
                                             'reports = "build/release"\ndatasheets = "docs/datasheets"'))
    assert project.config().datasheets == project.root / "docs" / "datasheets"
    web["https://example.com/sheet.pdf"] = SHEET
    assert run(project, "C2297", "--url", "https://example.com/sheet.pdf") == 0
    assert (project.root / "docs" / "datasheets" / "C2297.pdf").read_bytes() == SHEET


def test_no_entry_no_source(project, web, capsys):
    assert run(project, "C999") == 1
    assert "no parts entry C999" in capsys.readouterr().err
    assert run(project) == 1                                               # neither a key nor --all


@pytest.mark.parametrize("text, mpn, names", [
    ("Part No. KT-0805G, 0805 green", "KT-0805G", "yes"),
    ("0805 翠绿 525nm", "KT-0805G", "no"),
    ("MT3608L: pin 6 OC. Order MT3608L-AB", "MT3608", "MT3608L"),
    ("the mt3608 boost converter", "MT3608", "yes"),                       # case does not matter
    ("TLC5916 and TLC5916IDR", "TLC5916", "yes"),                          # the whole word once is enough
    ("SS32 thru SS36", "SS34", "no"),
])
def test_names_mpn(text, mpn, names):
    assert part.names_mpn(text, mpn) == names
