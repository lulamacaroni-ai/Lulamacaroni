from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from lulamacaroni.approval.gate import NotApproved, decide
from lulamacaroni.approval.store import JsonStore
from lulamacaroni.localbook import LocalWorkbook
from lulamacaroni.sitio_mx import construir as c
from lulamacaroni.sitio_mx import demo, paginas
from lulamacaroni.sitio_mx.__main__ import main
from lulamacaroni.sitio_mx.datos import Ajustes, seleccionar

AHORA = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
AJ = Ajustes(responsable="Responsable de prueba", domicilio="Calle 1, CDMX",
             whatsapp="5215500000000")


@pytest.fixture
def fotos(tmp_path):
    return demo.fotos(tmp_path / "fotos")


def _build(tmp_path, fotos, obras=None, variantes=None, ajustes=AJ):
    o, v = demo.filas()
    return c.construir(obras if obras is not None else o, variantes if variantes is not None else v,
                       fotos, tmp_path / "sitio", ajustes, AHORA)


def test_only_active_originals_with_photo(fotos):
    obras, variantes = demo.filas()
    variantes.append({"sku": "EJ-08-ORIG", "obra_id": "EJ-08", "linea": "MX-original",
                      "tipo": "original", "estado": "activa"})
    obras.append({"obra_id": "EJ-08", "titulo_es": "Sin foto", "estado": "activa"})
    obras[0]["estado"] = "reservada"
    sel = seleccionar(obras, variantes, fotos)
    ids = {p.obra_id for p in sel.piezas}
    assert ids == {"EJ-02", "EJ-03", "EJ-04", "EJ-05", "EJ-06"}
    texto = " ".join(sel.excluidas)
    assert "EJ-07" in texto and "EJ-08" in texto and "reservada" in texto


def test_photos_copied_byte_for_byte_and_never_cropped(tmp_path, fotos):
    r = _build(tmp_path, fotos)
    for p in r.seleccion.piezas:
        copia = r.carpeta / "img" / f"{p.slug}{p.foto.extension}"
        assert copia.read_bytes() == p.foto.ruta.read_bytes()
    assert "object-fit:contain" in paginas.CSS and "cover" not in paginas.CSS


def test_photo_proportion_mismatch_is_reported(tmp_path, fotos):
    Image.new("RGB", (800, 800), "white").save(fotos / "EJ-01.jpg")   # piece is 60x80
    sel = seleccionar(*demo.filas(), fotos)
    assert any("EJ-01" in a and "proporción" in a for a in sel.avisos)
    assert "EJ-01" in {p.obra_id for p in sel.piezas}


def test_missing_price_is_never_zero(tmp_path, fotos):
    r = _build(tmp_path, fotos)
    html = (r.carpeta / "obra" / "ej-05.html").read_text("utf-8")
    assert "Precio a consultar" in html and "$0" not in html
    assert "$14,500 MXN" in (r.carpeta / "index.html").read_text("utf-8")
    assert "IVA incluido" in (r.carpeta / "index.html").read_text("utf-8")


def test_pages_are_spanish_static_and_private(tmp_path, fotos):
    r = _build(tmp_path, fotos)
    for rel in r.archivos:
        if rel.endswith(".html"):
            html = (r.carpeta / rel).read_text("utf-8")
            assert 'lang="es-MX"' in html
            assert "<script" not in html and "<form" not in html
            assert "googleapis" not in html
    obra = (r.carpeta / "obra" / "ej-01.html").read_text("utf-8")
    assert "wa.me/5215500000000" in obra and "EJ-01" in obra
    assert "coleccion/jardines.html" in (r.carpeta / "index.html").read_text("utf-8")


def test_aviso_covers_required_elements(tmp_path, fotos):
    r = _build(tmp_path, fotos)
    av = (r.carpeta / "aviso-de-privacidad.html").read_text("utf-8")
    for txt in ("Responsable de prueba", "Calle 1, CDMX", "ARCO", "20 días hábiles",
                "Finalidad adicional", "retirar tu consentimiento", "Cambios a este aviso"):
        assert txt in av


def test_empty_catalog_says_soon(tmp_path, fotos):
    r = _build(tmp_path, fotos, obras=[], variantes=[])
    assert "Muy pronto" in (r.carpeta / "index.html").read_text("utf-8")
    assert "No hay ninguna obra" in " ".join(r.problemas())


def test_build_refuses_to_empty_a_foreign_folder(tmp_path, fotos):
    ajena = tmp_path / "sitio"
    ajena.mkdir()
    (ajena / "importante.txt").write_text("x")
    with pytest.raises(SystemExit):
        _build(tmp_path, fotos)
    assert (ajena / "importante.txt").exists()


def test_cannot_request_approval_without_aviso_details(tmp_path, fotos):
    r = _build(tmp_path, fotos, ajustes=Ajustes())
    with pytest.raises(SystemExit, match="LULA_MX_RESPONSABLE"):
        c.solicitar(JsonStore(tmp_path / "apr.json"), r)


def test_publish_needs_the_exact_approved_content(tmp_path, fotos):
    store = JsonStore(tmp_path / "apr.json")
    book = LocalWorkbook(tmp_path / "libro")
    book.upsert("Listados", [{"listado_ref": "sitio-mx-VIEJA", "sku": "VIEJA",
                              "linea": "MX-original", "canal": "sitio-mx",
                              "estado": "publicado"}])
    r = _build(tmp_path, fotos)
    rec = c.solicitar(store, r)
    with pytest.raises(NotApproved):                       # still pending
        c.publicar(store, book, r, rec.aprobacion_id, tmp_path / "pub")
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena", now=AHORA)

    obras, variantes = demo.filas()
    variantes[0]["precio_mxn_con_iva"] = 1                 # price changed after approval
    cambiado = _build(tmp_path, fotos, obras, variantes)
    with pytest.raises(NotApproved, match="cambió"):
        c.publicar(store, book, cambiado, rec.aprobacion_id, tmp_path / "pub")

    r = _build(tmp_path, fotos)
    zip_path = c.publicar(store, book, r, rec.aprobacion_id, tmp_path / "pub")
    assert zip_path.exists()
    filas = {f["listado_ref"]: f for f in book.read("Listados")}
    assert filas["sitio-mx-EJ-01-ORIG"]["estado"] == "publicado"
    assert filas["sitio-mx-EJ-01-ORIG"]["url"].endswith("/obra/ej-01.html")
    assert filas["sitio-mx-VIEJA"]["estado"] == "retirado"
    assert store.get(rec.aprobacion_id).ejecutado_en
    with pytest.raises(NotApproved, match="ya se usó"):
        c.publicar(store, book, r, rec.aprobacion_id, tmp_path / "pub")


def test_cli_demo_build(tmp_path, capsys):
    assert main(["construir", "--demo", "--salida", str(tmp_path / "s")]) == 0
    out = capsys.readouterr().out
    assert "6 obra(s)" in out and "vendida" in out
    assert Path(tmp_path / "s" / "sitemap.xml").exists()
