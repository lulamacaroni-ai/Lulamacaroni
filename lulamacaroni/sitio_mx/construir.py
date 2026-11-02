"""Build, approve and publish the Mexico catalog site.

Publishing goes through the approval gate like any listing change: ``solicitar`` asks
Lorena to approve a manifest of exactly what will be public (each piece, its price and
the fingerprint of its photo, the aviso de privacidad and the contact details);
``publicar`` rebuilds from the Sheet, refuses unless the rebuilt manifest is the one she
approved, then packs the site as a zip for the host and records the pages in
``Listados`` (canal ``sitio-mx``) so the sold-original guard can watch them.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..approval.gate import assert_approved, mark_executed, request_approval
from . import aviso, paginas
from .datos import Ajustes, Pieza, Seleccion, seleccionar

MARCA = ".sitio-mx"   # only a folder carrying this file is ever emptied by a build


@dataclass
class Resultado:
    carpeta: Path
    seleccion: Seleccion
    ajustes: Ajustes
    ahora: datetime
    archivos: list[str]

    def problemas(self) -> list[str]:
        """What blocks asking for approval or publishing."""
        out = [f"Falta configurar {f}." for f in self.ajustes.faltantes()]
        if not self.seleccion.piezas:
            out.append("No hay ninguna obra lista para publicar.")
        return out


def carpeta_por_defecto() -> Path:
    return config.REPO_ROOT / "data" / "sitio-mx"


def _preparar(carpeta: Path) -> None:
    if carpeta.exists() and any(carpeta.iterdir()):
        if not (carpeta / MARCA).exists():
            raise SystemExit(f"{carpeta} no está vacía y no es un sitio construido antes; "
                             "elige otra carpeta con --salida.")
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / MARCA).write_text("carpeta generada por lulamacaroni.sitio_mx\n", "utf-8")


def construir(obras: list[dict], variantes: list[dict], fotos: Path | None,
              carpeta: Path, ajustes: Ajustes, ahora: datetime | None = None) -> Resultado:
    ahora = ahora or datetime.now(timezone.utc)
    sel = seleccionar(obras, variantes, fotos)
    _preparar(carpeta)
    archivos: list[str] = []

    def escribe(rel: str, texto: str) -> None:
        p = carpeta / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, "utf-8")
        archivos.append(rel)

    escribe("estilos.css", paginas.CSS.strip() + "\n")
    escribe("index.html", paginas.inicio(sel.piezas, ajustes, ahora))
    escribe("como-comprar.html", paginas.como_comprar(ajustes, ahora))
    escribe("aviso-de-privacidad.html", paginas.aviso_privacidad(ajustes, ahora))
    escribe("404.html", paginas.no_encontrada(ajustes, ahora))
    for p in sel.piezas:
        escribe(f"obra/{p.slug}.html", paginas.obra(p, ajustes, ahora))
        destino = carpeta / "img" / f"{p.slug}{p.foto.extension}"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p.foto.ruta, destino)          # byte for byte, never edited
        archivos.append(f"img/{destino.name}")
    for slug, _, _ in paginas.colecciones(sel.piezas):
        escribe(f"coleccion/{slug}.html", paginas.coleccion(slug, sel.piezas, ajustes, ahora))
    escribe("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {ajustes.url}/sitemap.xml\n")
    escribe("sitemap.xml", _sitemap(ajustes, archivos))
    return Resultado(carpeta, sel, ajustes, ahora, archivos)


def _sitemap(a: Ajustes, archivos: list[str]) -> str:
    urls = [f for f in archivos if f.endswith(".html") and f != "404.html"]
    filas = "".join(f"<url><loc>{a.url}/{'' if f == 'index.html' else f}</loc></url>"
                    for f in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{filas}</urlset>\n')


# --- what Lorena approves -------------------------------------------------------

def _pieza_manifiesto(p: Pieza) -> dict:
    return {"obra_id": p.obra_id, "sku": p.sku, "titulo": p.titulo, "tecnica": p.tecnica,
            "medidas": p.medidas, "anio": p.anio, "coleccion": p.coleccion,
            "precio_mxn_con_iva": p.precio_mxn, "foto": f"{p.foto.ancho_px}x{p.foto.alto_px}",
            "foto_sha256": p.foto.huella}


def manifiesto(r: Resultado) -> dict:
    a = r.ajustes
    return {
        "sitio": a.url,
        "obras": [_pieza_manifiesto(p) for p in r.seleccion.piezas],
        "contacto": {"correo": a.correo, "whatsapp": a.whatsapp, "ciudad": a.ciudad,
                     "instagram": a.instagram},
        "aviso_de_privacidad": {
            "fecha": aviso.FECHA_AVISO,
            "sha256": hashlib.sha256(aviso.html(a).encode("utf-8")).hexdigest(),
            "responsable": a.responsable, "domicilio": a.domicilio,
        },
    }


def reporte(r: Resultado) -> str:
    s = r.seleccion
    lineas = [f"Sitio de catálogo México: {len(s.piezas)} obra(s) publicables, "
              f"{len(r.archivos)} archivos en {r.carpeta}"]
    for p in s.piezas:
        precio = paginas.pesos(p.precio_mxn) if p.precio_mxn is not None else "a consultar"
        lineas.append(f"  · {p.titulo} ({p.obra_id}) — {precio}")
    if s.excluidas:
        lineas.append("No se publican:")
        lineas += [f"  · {x}" for x in s.excluidas]
    if s.avisos:
        lineas.append("Revisar (sí se publican):")
        lineas += [f"  · {x}" for x in s.avisos]
    probs = r.problemas()
    if probs:
        lineas.append("Antes de publicar:")
        lineas += [f"  · {x}" for x in probs]
    return "\n".join(lineas)


def solicitar(store, r: Resultado, creado_por: str = "sitio-mx"):
    probs = r.problemas()
    if probs:
        raise SystemExit("No se puede pedir aprobación todavía:\n" + "\n".join(probs))
    n = len(r.seleccion.piezas)
    return request_approval(
        store, tipo="listado", linea="MX-original",
        resumen=f"Publicar el catálogo México ({n} obra{'s' if n != 1 else ''}) en {r.ajustes.url}",
        contenido=manifiesto(r), creado_por=creado_por)


def publicar(store, book, r: Resultado, aprobacion_id: str, destino: Path) -> Path:
    """Pack the approved build and record it in Listados. Raises NotApproved otherwise."""
    probs = r.problemas()
    if probs:
        raise SystemExit("No se puede publicar:\n" + "\n".join(probs))
    registro = store.get(aprobacion_id)
    contenido = manifiesto(r)
    assert_approved(registro, tipo="listado", contenido=contenido, now=r.ahora)
    destino.mkdir(parents=True, exist_ok=True)
    zip_path = destino / f"sitio-mx-{r.ahora:%Y%m%d-%H%M}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in r.archivos:
            z.write(r.carpeta / rel, rel)
    book.upsert("Listados", filas_listados(r, book.read("Listados"), aprobacion_id))
    mark_executed(store, registro)
    return zip_path


def filas_listados(r: Resultado, actuales: list[dict], aprobacion_id: str) -> list[dict]:
    hoy = r.ahora.replace(microsecond=0).isoformat()
    filas, publicados = [], set()
    for p in r.seleccion.piezas:
        ref = f"sitio-mx-{p.sku or p.obra_id}"
        publicados.add(ref)
        filas.append({
            "listado_ref": ref, "sku": p.sku, "linea": "MX-original", "canal": "sitio-mx",
            "id_en_canal": p.slug, "titulo_en_canal": p.titulo,
            "url": f"{r.ajustes.url}/obra/{p.slug}.html",
            "precio": "" if p.precio_mxn is None else p.precio_mxn, "inventario": 1,
            "estado": "publicado", "aprobacion_id": aprobacion_id, "ultima_sync": hoy,
        })
    for l in actuales:   # pages that dropped out of this build come down with it
        if (l.get("canal") == "sitio-mx" and l.get("estado") == "publicado"
                and l.get("listado_ref") not in publicados):
            filas.append({**l, "estado": "retirado", "aprobacion_id": aprobacion_id,
                          "ultima_sync": hoy})
    return filas


def manifiesto_json(r: Resultado) -> str:
    return json.dumps(manifiesto(r), ensure_ascii=False, indent=2)
