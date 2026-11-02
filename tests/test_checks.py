import pytest
from PIL import Image

from lulamacaroni.checks.guards import discontinued_pod, sold_original
from lulamacaroni.checks.resolution import check, check_file, parse_size


def test_ideal_and_orientation_independent():
    assert check(3600, 4800, 12, 16).estado == "ideal"
    assert check(4800, 3600, 12, 16).estado == "ideal"  # landscape file, size given portrait


def test_acceptable_and_low():
    assert check(2400, 3200, 12, 16).estado == "aceptable"      # 200 dpi
    assert check(1200, 1600, 12, 16).estado == "baja-resolucion"  # 100 dpi


def test_never_crops_mismatched_proportion():
    r = check(3600, 4800, 8, 10)
    assert r.estado == "no-apto" and not r.ok
    assert "no se recorta" in r.motivo


def test_parse_size():
    assert parse_size("12x16") == (12, 16)
    assert parse_size("8×10in") == (8, 10)
    with pytest.raises(ValueError):
        parse_size("A4")


def test_check_file(tmp_path):
    p = tmp_path / "obra.png"
    Image.new("RGB", (900, 1200)).save(p)
    results = check_file(str(p), ["3x4", "6x8"])
    assert [r.estado for r in results] == ["ideal", "aceptable"]


def test_discontinued_pod_guard():
    variantes = [
        {"sku": "A-12x16", "linea": "US-POD", "estado": "activa", "pod_sku": "GLOBAL-FAP-12X16"},
        {"sku": "B-12x16", "linea": "US-POD", "estado": "descontinuada", "pod_sku": "X"},
        {"sku": "C-12x16", "linea": "US-POD", "estado": "activa", "pod_sku": "GONE"},
    ]
    listados = [
        {"listado_ref": "L1", "sku": "A-12x16", "linea": "US-POD", "canal": "etsy", "estado": "publicado"},
        {"listado_ref": "L2", "sku": "B-12x16", "linea": "US-POD", "canal": "shopify", "estado": "publicado"},
        {"listado_ref": "L3", "sku": "C-12x16", "linea": "US-POD", "canal": "etsy", "estado": "publicado"},
        {"listado_ref": "L4", "sku": "Z", "linea": "US-POD", "canal": "etsy", "estado": "publicado"},
        {"listado_ref": "L5", "sku": "B-12x16", "linea": "US-POD", "canal": "etsy", "estado": "pausado"},
    ]
    found = discontinued_pod(variantes, listados, pod_available=lambda s: s != "GONE")
    assert sorted(f.referencia for f in found) == ["L2", "L3", "L4"]


def test_sold_original_guard():
    obras = [{"obra_id": "O1", "estado": "vendida"}, {"obra_id": "O2", "estado": "activa"}]
    variantes = [{"sku": "O1-ORIG", "obra_id": "O1", "tipo": "original"},
                 {"sku": "O2-ORIG", "obra_id": "O2", "tipo": "original"}]
    listados = [
        {"listado_ref": "M1", "sku": "O1-ORIG", "linea": "MX-original", "canal": "sitio-mx", "estado": "publicado"},
        {"listado_ref": "M2", "sku": "O2-ORIG", "linea": "MX-original", "canal": "sitio-mx", "estado": "publicado"},
    ]
    assert [f.referencia for f in sold_original(obras, variantes, listados)] == ["M1"]
