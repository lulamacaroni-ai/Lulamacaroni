"""Which originals go on the Mexico site, and what the build has to warn about.

A piece is published when all of this holds:

* it has a variant with ``linea`` MX-original and ``tipo`` original, ``estado`` activa;
* its ``Obras`` row is ``activa`` (``reservada`` and ``vendida`` never show: that is the
  same rule the sold-original guard in ``checks/guards.py`` enforces);
* there is a web photo for it in the photos folder, named after ``obra_id``.

Photos are copied byte for byte. Nothing here crops, resizes, stretches or regenerates
artwork; a photo whose proportions don't match the piece's measurements is reported so a
person can check it.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .. import config

EXTENSIONES = (".jpg", ".jpeg", ".png", ".webp")
TOLERANCIA_PROPORCION = 0.03     # 3 %: more than this and the photo may be cropped
FOTO_PESADA = 4 * 1024 * 1024    # bytes; heavier photos load slowly on a phone


@dataclass(frozen=True)
class Ajustes:
    """Public details the site prints. Set them in .env / the cloud environment."""

    responsable: str = ""      # who is responsible for personal data (aviso de privacidad)
    domicilio: str = ""        # address for the aviso (required by law)
    correo: str = "info@lulamacaroni.com"
    whatsapp: str = ""         # digits with country code, e.g. 52155...
    url: str = "https://mx.lulamacaroni.com"
    ciudad: str = ""           # where pieces can be picked up or delivered, free text
    instagram: str = "lulamacaroni"

    @classmethod
    def desde_entorno(cls) -> "Ajustes":
        d = cls()
        return cls(
            responsable=config.get("LULA_MX_RESPONSABLE", ""),
            domicilio=config.get("LULA_MX_DOMICILIO", ""),
            correo=config.get("LULA_MX_CORREO", d.correo),
            whatsapp=re.sub(r"\D", "", config.get("LULA_MX_WHATSAPP", "")),
            url=config.get("LULA_MX_URL", d.url).rstrip("/"),
            ciudad=config.get("LULA_MX_CIUDAD", ""),
            instagram=config.get("LULA_MX_INSTAGRAM", d.instagram).lstrip("@"),
        )

    def faltantes(self) -> list[str]:
        """Settings without which the site must not be published."""
        out = []
        if not self.responsable:
            out.append("LULA_MX_RESPONSABLE (nombre del responsable para el aviso de privacidad)")
        if not self.domicilio:
            out.append("LULA_MX_DOMICILIO (domicilio para el aviso de privacidad)")
        if not (self.correo or self.whatsapp):
            out.append("LULA_MX_CORREO o LULA_MX_WHATSAPP (cómo escribir para comprar)")
        return out


@dataclass
class Foto:
    ruta: Path
    ancho_px: int
    alto_px: int
    bytes: int
    huella: str           # SHA-256 of the file, so an approval covers this exact photo

    @property
    def extension(self) -> str:
        ext = self.ruta.suffix.lower()
        return ".jpg" if ext == ".jpeg" else ext


@dataclass
class Pieza:
    obra_id: str
    sku: str
    titulo: str
    tecnica: str
    anio: str
    coleccion: str
    ancho_cm: float | None
    alto_cm: float | None
    precio_mxn: float | None        # IVA included; None = "precio a consultar", never 0
    precio_actualizado: str          # Variantes.actualizado, as typed in the sheet
    foto: Foto
    descripcion: str = ""

    @property
    def slug(self) -> str:
        return slug(self.obra_id)

    @property
    def coleccion_slug(self) -> str:
        return slug(self.coleccion) if self.coleccion else ""

    @property
    def medidas(self) -> str:
        if self.ancho_cm and self.alto_cm:
            return f"{_cm(self.ancho_cm)} × {_cm(self.alto_cm)} cm"
        return ""


@dataclass
class Seleccion:
    piezas: list[Pieza] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)       # published, but someone should look
    excluidas: list[str] = field(default_factory=list)    # not published, and why


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "obra"


def _cm(v: float) -> str:
    return f"{v:g}"


def _num(v) -> float | None:
    if v in (None, ""):
        return None
    try:
        n = float(str(v).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None
    return n


def buscar_foto(carpeta: Path | None, obra_id: str) -> Path | None:
    if carpeta is None or not carpeta.is_dir():
        return None
    for ext in EXTENSIONES:
        for nombre in (obra_id + ext, obra_id + ext.upper()):
            p = carpeta / nombre
            if p.is_file():
                return p
    return None


def leer_foto(ruta: Path) -> Foto:
    data = ruta.read_bytes()
    with Image.open(ruta) as im:
        ancho, alto = im.size
    return Foto(ruta, ancho, alto, len(data), hashlib.sha256(data).hexdigest())


def seleccionar(obras: list[dict], variantes: list[dict], fotos: Path | None) -> Seleccion:
    sel = Seleccion()
    obra_by_id = {str(o.get("obra_id")): o for o in obras if o.get("obra_id")}
    vistos: set[str] = set()
    for v in variantes:
        if v.get("linea") != "MX-original" or v.get("tipo") != "original":
            continue
        oid = str(v.get("obra_id") or "")
        if not oid or oid in vistos:
            continue
        vistos.add(oid)
        o = obra_by_id.get(oid)
        nombre = (o or {}).get("titulo_es") or (o or {}).get("titulo") or oid
        if o is None:
            sel.excluidas.append(f"{oid}: la variante {v.get('sku')} no tiene fila en Obras.")
            continue
        if o.get("estado") != "activa":
            sel.excluidas.append(f"{nombre} ({oid}): la obra está «{o.get('estado') or 'sin estado'}».")
            continue
        if v.get("estado") != "activa":
            sel.excluidas.append(f"{nombre} ({oid}): la variante {v.get('sku')} está "
                                 f"«{v.get('estado') or 'sin estado'}».")
            continue
        ruta = buscar_foto(fotos, oid)
        if ruta is None:
            sel.excluidas.append(f"{nombre} ({oid}): falta la foto {oid}.jpg (o .png/.webp) "
                                 "en la carpeta de fotos.")
            continue
        try:
            foto = leer_foto(ruta)
        except OSError:
            sel.excluidas.append(f"{nombre} ({oid}): la foto {ruta.name} no se puede abrir.")
            continue
        pieza = Pieza(
            obra_id=oid, sku=str(v.get("sku") or ""), titulo=str(nombre),
            tecnica=str(o.get("tecnica") or ""), anio=_anio(o.get("anio")),
            coleccion=str(o.get("coleccion") or ""),
            ancho_cm=_num(o.get("ancho_cm")), alto_cm=_num(o.get("alto_cm")),
            precio_mxn=_precio(v.get("precio_mxn_con_iva")),
            precio_actualizado=str(v.get("actualizado") or ""),
            foto=foto,
        )
        sel.avisos.extend(_avisos(pieza))
        sel.piezas.append(pieza)
    sel.piezas.sort(key=lambda p: (p.coleccion.lower(), p.titulo.lower()))
    return sel


def _anio(v) -> str:
    n = _num(v)
    return str(int(n)) if n else ""


def _precio(v) -> float | None:
    n = _num(v)
    return n if n and n > 0 else None


def _avisos(p: Pieza) -> list[str]:
    out = []
    nombre = f"{p.titulo} ({p.obra_id})"
    if p.precio_mxn is None:
        out.append(f"{nombre}: sin precio en Variantes.precio_mxn_con_iva; se muestra "
                   "«Precio a consultar».")
    if not p.medidas:
        out.append(f"{nombre}: faltan ancho_cm/alto_cm en Obras; la ficha no muestra medidas.")
    else:
        obra = p.ancho_cm / p.alto_cm
        foto = p.foto.ancho_px / p.foto.alto_px
        if abs(foto - obra) / obra > TOLERANCIA_PROPORCION:
            out.append(f"{nombre}: la foto mide {p.foto.ancho_px}×{p.foto.alto_px} px y no tiene "
                       f"la proporción de la obra ({p.medidas}). Revisa que no esté recortada "
                       "(una foto con fondo o marco también puede causarlo). No se modifica.")
    if p.foto.bytes > FOTO_PESADA:
        out.append(f"{nombre}: la foto pesa {p.foto.bytes / 1048576:.1f} MB; tardará en cargar "
                   "en el celular. Conviene exportar una versión web completa (sin recortar).")
    return out

