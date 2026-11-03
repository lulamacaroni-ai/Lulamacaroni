"""Import monthly eRank and EverBee CSV exports into the workbook (Investigacion tab).

Neither tool is connected by API: eRank has no public API and EverBee's needs a plan we
have not confirmed (Lorena's requirements, section 7: "si la conexión automática no está
disponible, ofrecer un flujo de importación de reportes fácil de mantener"). So Lorena
exports a CSV once a month and drops it in a Google Drive folder; this reads it.

    python -m lulamacaroni.connectors.investigacion                  # new files in the Drive folder
    python -m lulamacaroni.connectors.investigacion --archivo x.csv  # one file on this machine
    python -m lulamacaroni.connectors.investigacion --dry-run        # read and count, write nothing

Drive folder: ``LULA_INVESTIGACION_CARPETA_ID`` if set, else the folder named
"LulaMacaroni Investigación" shared with the service account. CSV files and Google
Sheets in it are read (a Sheet: its first tab). Excel files are refused with a note.

Rules:

* Column names are matched loosely (case, accents and punctuation ignored, English or
  Spanish). Unknown columns are listed as ignored, never guessed. Without a keyword or a
  product title/price column the file is refused.
* Every figure is the tool's own estimate on the export date. Competitor prices are what
  the tool saw published; their sales and revenue are estimates.
* The same file imported twice changes nothing (its id is a hash of the content).
* Every file, imported or refused, gets a row in Importaciones saying why.
* Nothing here publishes, spends or contacts anyone: it only writes research rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .. import config

CARPETA_NOMBRE = "LulaMacaroni Investigación"
DRIVE = "https://www.googleapis.com/drive/v3/files"
MAX_BYTES = 5_000_000
MAX_FILAS = 20_000
CSV_MIMES = ("text/csv", "text/plain", "application/csv", "text/comma-separated-values",
             "application/vnd.ms-excel")
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIMES = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


# Column -> header spellings we accept (compared after _norm). Best guesses from the
# tools' screens; the first real export confirms them, and docs/setup/investigacion-es.md
# tells Lorena how to rename a column if one is not recognized.
ALIAS: dict[str, tuple[str, ...]] = {
    "keyword": ("keyword", "keywords", "searchterm", "term", "tag", "palabraclave",
                "palabrasclave", "busqueda"),
    "busquedas": ("searches", "avgsearches", "averagesearches", "etsysearches",
                  "avgmonthlysearches", "monthlysearches", "searchvolume", "volume",
                  "estsearches", "estimatedsearches", "busquedas", "volumen"),
    "clics": ("clicks", "avgclicks", "averageclicks", "etsyclicks", "clics"),
    "ctr": ("ctr", "avgctr", "clickrate", "clickthroughrate", "averagectr"),
    "competencia": ("competition", "etsycompetition", "competinglistings", "competencia",
                    "listings", "keywordcompetition"),
    "tendencia": ("trend", "trends", "trending", "tendencia", "searchtrend"),
    "mercado": ("country", "market", "mercado", "pais"),
    "titulo": ("title", "listingtitle", "producttitle", "productname", "product", "listing",
               "titulo", "producto"),
    "tienda": ("shop", "shopname", "store", "storename", "seller", "tienda"),
    "precio": ("price", "listingprice", "avgprice", "precio"),
    "moneda": ("currency", "moneda"),
    "ventas_mes": ("mosales", "monthlysales", "estmonthlysales", "estimatedmonthlysales",
                   "salesmonth", "ventasmes", "ventasmensuales"),
    "ingresos_mes": ("morevenue", "monthlyrevenue", "estmonthlyrevenue",
                     "estimatedmonthlyrevenue", "revenuemonth", "ingresosmes",
                     "ingresosmensuales"),
    "resenas": ("reviews", "totalreviews", "numberofreviews", "resenas"),
    "favoritos": ("favorites", "favourites", "totalfavorites", "hearts", "favoritos"),
    "etiquetas": ("tags", "listingtags", "etiquetas"),
}
_ALIAS_INV = {a: col for col, alias in ALIAS.items() for a in alias}
NUMERICAS = ("busquedas", "clics", "ctr", "competencia", "precio", "ventas_mes",
             "ingresos_mes", "resenas", "favoritos")

# Product type from the words of a keyword or a title. Order matters: "printable" is a
# download, "framed print" is framed.
CATEGORIA_REGLAS = (
    ("descargable", ("digital", "printable", "download", "instant", "descargable", "svg",
                     "png", "pdf")),
    ("enmarcado", ("framed", "frame", "enmarcado", "marco")),
    ("cojin", ("pillow", "cushion", "cojin", "throwpillow")),
    ("wallpaper", ("wallpaper", "mural", "peelandstick", "papeltapiz")),
    ("print", ("print", "poster", "wallart", "artprint", "canvas", "lamina", "giclee",
               "painting", "artwork", "cuadro")),
)
FUENTE_NOMBRE = {"erank": "eRank", "everbee": "EverBee"}


def categoria(texto: str) -> str:
    t = _norm(texto)
    for cat, palabras in CATEGORIA_REGLAS:
        if any(p in t for p in palabras):
            return cat
    return "otro"


def numero(value) -> float | None:
    """'1,234' -> 1234, '$12.50' -> 12.5, '3.4%' -> 3.4, '1.2k' -> 1200; '< 20', 'N/A' -> None."""
    s = str(value or "").strip().lower()
    if not s or s in ("-", "—", "n/a", "na", "none", "null") or s[0] in "<>~":
        return None
    s = re.sub(r"^(us|mx|ca|au)?\$|[€£%\s]|usd|mxn", "", s)
    mult = 1
    if s.endswith("k"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("m"):
        mult, s = 1_000_000, s[:-1]
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    elif re.fullmatch(r"-?\d+,\d+", s):     # decimal comma (Spanish Excel)
        s = s.replace(",", ".")
    try:
        v = float(s) * mult
    except ValueError:
        return None
    return int(v) if v == int(v) and abs(v) < 1e15 else round(v, 4)


def moneda_de(value) -> str:
    s = str(value or "").strip().upper()
    if s.startswith("MX$") or "MXN" in s:
        return "MXN"
    if "€" in s or "EUR" in s:
        return "EUR"
    if "£" in s or "GBP" in s:
        return "GBP"
    if s.startswith(("CA$", "CAD")):
        return "CAD"
    if "$" in s or "USD" in s:
        return "USD"
    return ""


_FECHA = (
    (re.compile(r"(20\d\d)[-_.](\d\d)[-_.](\d\d)"), "ymd"),
    (re.compile(r"(?<!\d)(20\d\d)(\d\d)(\d\d)(?!\d)"), "ymd"),
    (re.compile(r"(\d\d)[-_.](\d\d)[-_.](20\d\d)"), "mdy"),
    (re.compile(r"(20\d\d)[-_.](\d\d)(?![-_.]?\d)"), "ym"),
)


def fecha_en_nombre(nombre: str) -> date | None:
    for rx, orden in _FECHA:
        mt = rx.search(nombre)
        if not mt:
            continue
        g = [int(x) for x in mt.groups()]
        try:
            if orden == "ymd":
                return date(g[0], g[1], g[2])
            if orden == "mdy":
                return date(g[2], g[0], g[1])
            return date(g[0], g[1], 1)
        except ValueError:
            continue
    return None


def texto_csv(contenido: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(enc)
        except UnicodeDecodeError:
            continue
    return contenido.decode("latin-1")


@dataclass
class Lectura:
    nombre: str
    fuente: str = ""
    tipo: str = ""
    filas: list[dict] = field(default_factory=list)
    usadas: dict[str, str] = field(default_factory=dict)      # column -> header in the file
    ignoradas: list[str] = field(default_factory=list)
    omitidas: int = 0
    error: str = ""
    notas: list[str] = field(default_factory=list)


def detectar_fuente(nombre: str, headers: list[str]) -> str:
    n = _norm(nombre)
    if "erank" in n and "everbee" not in n:
        return "erank"
    if "everbee" in n and "erank" not in n:
        return "everbee"
    hs = {_norm(h) for h in headers}
    if hs & {"mosales", "morevenue", "estmonthlyrevenue", "monthlyrevenue"}:
        return "everbee"
    if hs & {"etsycompetition", "avgsearches", "etsysearches", "googlesearches"}:
        return "erank"
    return ""


def leer(nombre: str, contenido: bytes, moneda_defecto: str = "USD") -> Lectura:
    """Parse one export. Pure: no workbook, no network."""
    out = Lectura(nombre)
    if len(contenido) > MAX_BYTES:
        out.error = f"El archivo pesa más de {MAX_BYTES // 1_000_000} MB; exporta menos filas."
        return out
    text = texto_csv(contenido)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        out.error = "El archivo está vacío."
        return out
    header = [h.strip() for h in rows[0]]
    out.fuente = detectar_fuente(nombre, header)
    if not out.fuente:
        out.error = ("No sé si es de eRank o de EverBee: pon “erank” o “everbee” en el "
                     "nombre del archivo.")
        return out
    idx: dict[str, int] = {}
    for i, h in enumerate(header):
        col = _ALIAS_INV.get(_norm(h))
        if col and col not in idx:
            idx[col] = i
            out.usadas[col] = h
        elif h:
            out.ignoradas.append(h)
    if "titulo" in idx or ("precio" in idx and "keyword" not in idx):
        out.tipo = "producto"
    elif "keyword" in idx:
        out.tipo = "keyword"
    else:
        out.error = ("No encontré una columna de keyword ni de producto (título o precio). "
                     f"Columnas del archivo: {', '.join(header[:12])}.")
        return out

    supuesta = False
    for r in rows[1:MAX_FILAS + 1]:
        r = r + [""] * (len(header) - len(r))
        raw = {col: r[i].strip() for col, i in idx.items()}
        principal = raw.get("keyword") if out.tipo == "keyword" else (
            raw.get("titulo") or raw.get("keyword"))
        if not principal:
            out.omitidas += 1
            continue
        fila = {"tipo": out.tipo, "mercado": raw.get("mercado", "")}
        for col in ("keyword", "tendencia", "titulo", "tienda", "etiquetas"):
            if col in raw:
                fila[col] = raw[col][:500]
        for col in NUMERICAS:
            if col in raw:
                v = numero(raw[col])
                # a competition level like "Low" / "Alta" stays as text
                fila[col] = raw[col][:40] if v is None and col == "competencia" else (
                    "" if v is None else v)
        if out.tipo == "producto":
            mon = moneda_de(raw.get("moneda")) or moneda_de(raw.get("precio"))
            if not mon and fila.get("precio") not in (None, ""):
                mon, supuesta = moneda_defecto, True
            fila["moneda"] = mon
        fila["categoria"] = categoria(" ".join(
            str(fila.get(c, "")) for c in ("keyword", "titulo", "etiquetas")))
        out.filas.append(fila)
    if len(rows) - 1 > MAX_FILAS:
        out.notas.append(f"Solo se leyeron las primeras {MAX_FILAS} filas.")
    if supuesta:
        out.notas.append(f"El archivo no dice la moneda; se supuso {moneda_defecto}.")
    if not out.filas:
        out.error = "Ninguna fila trae keyword o título."
    return out


def _hash(*parts) -> str:
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:12]


def importacion_id(fuente: str, contenido: bytes) -> str:
    return f"{fuente or 'desconocida'}-{hashlib.sha256(contenido).hexdigest()[:12]}"


def filas_investigacion(lec: Lectura, imp_id: str, fecha_export: str,
                        linea: str = "US-POD") -> list[dict]:
    out = []
    for f in lec.filas:
        clave = (f.get("keyword") if lec.tipo == "keyword"
                 else f"{f.get('titulo')}|{f.get('tienda', '')}")
        out.append({"investigacion_id": f"{imp_id}-{_hash(_norm(clave or ''), f.get('mercado'))}",
                    "importacion_id": imp_id, "linea": linea, "fuente": lec.fuente,
                    "fecha_export": fecha_export, **f})
    return out


def importar(book, nombre: str, contenido: bytes, archivo_id: str = "",
             fecha_archivo: datetime | None = None, now: datetime | None = None,
             moneda_defecto: str = "USD", escribir: bool = True) -> dict:
    """Read one export and write it (Investigacion + Importaciones + Fuentes).

    Returns the Importaciones row plus ``repetido`` (already imported, nothing written).
    """
    now = now or datetime.now(timezone.utc)
    lec = leer(nombre, contenido, moneda_defecto)
    imp_id = importacion_id(lec.fuente, contenido)
    previas = {r.get("importacion_id"): r for r in _leer(book, "Importaciones", escribir)}
    if imp_id in previas and previas[imp_id].get("estado") != "error":
        return {**previas[imp_id], "repetido": True}

    d = fecha_en_nombre(nombre)
    if d:
        fecha, origen = d.isoformat(), "nombre-archivo"
    elif fecha_archivo:
        fecha, origen = fecha_archivo.astimezone(timezone.utc).date().isoformat(), "archivo"
    else:
        fecha, origen = now.date().isoformat(), "dia-importacion"
    imp = {
        "importacion_id": imp_id, "fuente": lec.fuente, "tipo": lec.tipo,
        "archivo": nombre[:200], "archivo_id": archivo_id, "fecha_export": fecha,
        "fecha_export_origen": origen,
        "importado_en": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "filas": len(lec.filas), "filas_omitidas": lec.omitidas,
        "columnas_usadas": ", ".join(f"{h}→{c}" for c, h in lec.usadas.items()),
        "columnas_ignoradas": ", ".join(lec.ignoradas)[:1000],
        "estado": "error" if lec.error else ("parcial" if lec.omitidas else "ok"),
        "nota": lec.error or " ".join(lec.notas),
    }
    filas = [] if lec.error else filas_investigacion(lec, imp_id, fecha)
    if escribir:
        if filas:
            book.upsert("Investigacion", filas)
        book.upsert("Importaciones", [imp])
        if not lec.error:
            total = sum(1 for r in _leer(book, "Investigacion")
                        if r.get("fuente") == lec.fuente)
            book.stamp_source(lec.fuente, total, "ok", f"último archivo: {nombre[:120]}")
    return {**imp, "repetido": False}


def _leer(book, nombre: str, obligatoria: bool = True) -> list[dict]:
    from ..workbook import GoogleSetupError

    try:
        return book.read(nombre)
    except GoogleSetupError:
        if not obligatoria:   # a dry run on a sheet that still lacks the tab
            return []
        raise GoogleSetupError(
            f"La hoja aún no tiene la pestaña {nombre}. Corre primero: "
            "python -m lulamacaroni.setup_workbook") from None


# --- Google Drive -----------------------------------------------------------------------------

def _q(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'")


def carpeta_id(http, nombre: str = CARPETA_NOMBRE) -> str:
    """The research folder's id: ``LULA_INVESTIGACION_CARPETA_ID`` or found by name."""
    from ..workbook import GoogleSetupError

    fijo = config.get("LULA_INVESTIGACION_CARPETA_ID")
    if fijo:
        return fijo
    resp = http.request("get", DRIVE, params={
        "q": f"mimeType='application/vnd.google-apps.folder' and name='{_q(nombre)}' "
             "and trashed=false",
        "fields": "files(id,name)", "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true"}).json()
    found = resp.get("files", [])
    if not found:
        raise GoogleSetupError(
            f'No hay una carpeta llamada "{nombre}" compartida con la cuenta de servicio. '
            "En Google Drive crea la carpeta, Compartir, agrega el correo de la cuenta de "
            "servicio como Lector.")
    if len(found) > 1:
        raise GoogleSetupError(
            f'Hay {len(found)} carpetas llamadas "{nombre}". Pon LULA_INVESTIGACION_CARPETA_ID '
            "con la correcta.")
    return found[0]["id"]


def archivos(http, folder: str) -> list[dict]:
    out, token = [], None
    while True:
        params = {"q": f"'{_q(folder)}' in parents and trashed=false",
                  "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,size)",
                  "pageSize": "100", "orderBy": "modifiedTime",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if token:
            params["pageToken"] = token
        resp = http.request("get", DRIVE, params=params).json()
        out += resp.get("files", [])
        token = resp.get("nextPageToken")
        if not token:
            return out


def descargar(http, archivo: dict) -> bytes | None:
    """The file's CSV bytes, or None if it is not a CSV or a Google Sheet."""
    mime, name = archivo.get("mimeType", ""), archivo.get("name", "")
    if mime == SHEET_MIME:
        return http.request("get", f"{DRIVE}/{archivo['id']}/export",
                            params={"mimeType": "text/csv"}).content
    if mime == "text/csv" or (mime in CSV_MIMES and name.lower().endswith((".csv", ".tsv", ".txt"))):
        if int(archivo.get("size") or 0) > MAX_BYTES:
            return b"x" * (MAX_BYTES + 1)   # refused by leer() with a clear note
        return http.request("get", f"{DRIVE}/{archivo['id']}", params={"alt": "media"}).content
    return None


def importar_drive(book, http, now: datetime | None = None, escribir: bool = True) -> list[dict]:
    folder = carpeta_id(http)
    out = []
    for a in archivos(http, folder):
        if a.get("mimeType") == "application/vnd.google-apps.folder":
            continue
        contenido = descargar(http, a)
        if contenido is None:
            nota = ("Es un Excel: ábrelo y guárdalo como CSV." if a.get("mimeType") in XLSX_MIMES
                    or a.get("name", "").lower().endswith(".xlsx")
                    else "No es un CSV ni una hoja de Google.")
            out.append({"archivo": a.get("name", ""), "estado": "error", "nota": nota,
                        "repetido": False, "filas": 0})
            continue
        modificado = None
        if a.get("modifiedTime"):
            from ..app.metrics import parse_dt
            modificado = parse_dt(a["modifiedTime"])
        out.append(importar(book, a.get("name", ""), contenido, a.get("id", ""), modificado,
                            now, escribir=escribir))
    return out


def drive_http(book):
    """The authorized HTTP client of the opened sheet (gspread), reused for Drive."""
    inner = getattr(book, "book", book)
    client = getattr(inner, "client", None)
    if client is None or not hasattr(client, "request"):
        from ..workbook import GoogleSetupError
        raise GoogleSetupError("La carpeta de Drive solo se lee con la llave de Google "
                               "configurada (GOOGLE_SERVICE_ACCOUNT_JSON_B64).")
    return client


def _linea(r: dict) -> str:
    estado = "ya estaba importado" if r.get("repetido") else r.get("estado", "")
    fuente = FUENTE_NOMBRE.get(r.get("fuente", ""), r.get("fuente") or "?")
    extra = f" · {r['nota']}" if r.get("nota") else ""
    return f"{r.get('archivo')}: {fuente} {r.get('tipo', '')}, {r.get('filas', 0)} filas, {estado}{extra}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Importa exports CSV de eRank y EverBee")
    parser.add_argument("--archivo", help="un CSV en esta máquina (si no, la carpeta de Drive)")
    parser.add_argument("--dry-run", action="store_true", help="lee y cuenta; no escribe nada")
    parser.add_argument("--moneda", default="USD", help="moneda si el archivo no la trae")
    args = parser.parse_args(argv)

    from ..localbook import open_workbook

    book = open_workbook()
    if args.archivo:
        p = Path(args.archivo)
        mtime = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
        res = [importar(book, p.name, p.read_bytes(), "", mtime, moneda_defecto=args.moneda,
                        escribir=not args.dry_run)]
    else:
        res = importar_drive(book, drive_http(book), escribir=not args.dry_run)
    for r in res:
        print(_linea(r))
    if not res:
        print("La carpeta no tiene archivos.")
    if args.dry_run:
        print("(prueba: no se escribió nada)")
    return 1 if any(r.get("estado") == "error" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
