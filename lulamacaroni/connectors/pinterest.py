"""Pinterest API v5, read-only: the account's boards, pins and analytics, plus ad spend.

Docs: https://developers.pinterest.com/docs/api/v5/

Nothing here creates, edits or deletes anything on Pinterest. Publishing a pin goes through
Lorena's approval (tipo ``contenido``) and is not built yet.

Settings (cloud environment "LulaMacaroni", or ``.env`` for ``sync.bat``; never in the repo):

* ``PINTEREST_ACCESS_TOKEN``  the OAuth token for the business account, scopes
  ``user_accounts:read,boards:read,pins:read,ads:read``. Made with the steps in
  ``docs/setup/pinterest.md``.
* ``PINTEREST_TOKEN_VENCE``   the token's expiry date (``YYYY-MM-DD``), copied with it, so the
  app warns a week before the sync stops working. Optional.

Pinterest rotates refresh tokens on every use and the sync cannot write a new secret back
into the environment, so it never refreshes. A new token is made by hand about once a month.

    python -m lulamacaroni.connectors.pinterest --check     # who the token belongs to, counts
    python -m lulamacaroni.connectors.pinterest --dry-run   # what it would write, writes nothing
    python -m lulamacaroni.connectors.pinterest             # sync into the workbook

What it writes:

* ``Tableros``         one row per board (name, privacy, pin and follower counts)
* ``Pines``            one row per pin (newest ``--max-pines``) with its last-30-day numbers
* ``PinterestDiario``  account totals per day (impressions, saves, clicks)
* ``Campanas``         daily spend per ad campaign, only if the account has an ad account
* ``Fuentes``          ``pinterest`` and ``pinterest-ads``

No other person's data is read: no comments, followers or audience lists.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator
from urllib.parse import urlparse

import requests

from .. import config

BASE_URL = "https://api.pinterest.com/v5"
SCOPES = "user_accounts:read,boards:read,pins:read,ads:read"
PAGE_SIZE = 100
MAX_PAGES = 50                 # 5,000 boards or pins at most; far beyond the account
MAX_PINES = 100                # pins that get their own analytics call (trial: ~1,000 calls/day)
DIAS = 30
LINEA = "US-POD"               # Pinterest sells the US prints (English pins to Shopify)

# Pinterest's metric names -> our columns
METRICAS = {"IMPRESSION": "impresiones", "SAVE": "guardados", "PIN_CLICK": "clics_pin",
            "OUTBOUND_CLICK": "clics_enlace", "ENGAGEMENT": "interacciones"}
METRICAS_PIN = ("IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK")
PRIVACIDAD = {"PUBLIC": "publico", "PROTECTED": "protegido", "SECRET": "secreto"}

# Ads: account-currency spend per campaign per day. Read-only.
COLUMNAS_ADS = ("SPEND_IN_DOLLAR", "TOTAL_IMPRESSION", "TOTAL_CLICKTHROUGH",
                "TOTAL_CHECKOUT", "TOTAL_CHECKOUT_VALUE_IN_MICRO_DOLLAR")


class PinterestError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"Pinterest {status}: {message}")
        self.status = status


@dataclass
class PinterestClient:
    access_token: str
    timeout: float = 30.0
    session: requests.Session | None = None
    calls: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "PinterestClient":
        return cls(access_token=config.require("PINTEREST_ACCESS_TOKEN").strip())

    def get(self, path: str, params: dict | None = None) -> Any:
        self.calls += 1
        resp = self.session.request(
            "GET", f"{BASE_URL}{path}", params=params, timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.access_token}",
                     "Accept": "application/json"})
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400:
            # Pinterest's own message only; never the request (it carries the token)
            msg = body.get("message") if isinstance(body, dict) else ""
            if resp.status_code == 401:
                msg = "el permiso venció o no es válido; haz uno nuevo (docs/setup/pinterest.md)"
            raise PinterestError(resp.status_code, str(msg or resp.reason or "error"))
        return body

    def paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        params = {**(params or {}), "page_size": PAGE_SIZE}
        for _ in range(MAX_PAGES):
            body = self.get(path, params)
            yield from body.get("items") or []
            bookmark = body.get("bookmark")
            if not bookmark:
                return
            params = {**params, "bookmark": bookmark}

    # -- reads ---------------------------------------------------------------------------
    def user_account(self) -> dict:
        return self.get("/user_account")

    def iter_boards(self) -> Iterator[dict]:
        return self.paginate("/boards")

    def iter_pins(self) -> Iterator[dict]:
        return self.paginate("/pins")

    def account_analytics(self, start: date, end: date) -> dict:
        return self.get("/user_account/analytics", {
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "metric_types": ",".join(METRICAS)})

    def pin_analytics(self, pin_id: str, start: date, end: date) -> dict:
        return self.get(f"/pins/{pin_id}/analytics", {
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "metric_types": ",".join(METRICAS_PIN)})

    def iter_ad_accounts(self) -> Iterator[dict]:
        return self.paginate("/ad_accounts")

    def iter_campaigns(self, ad_account_id: str) -> Iterator[dict]:
        return self.paginate(f"/ad_accounts/{ad_account_id}/campaigns")

    def campaign_analytics(self, ad_account_id: str, campaign_ids: list[str], start: date,
                           end: date) -> list[dict]:
        body = self.get(f"/ad_accounts/{ad_account_id}/campaigns/analytics", {
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "campaign_ids": ",".join(campaign_ids), "columns": ",".join(COLUMNAS_ADS),
            "granularity": "DAY"})
        return body if isinstance(body, list) else []


# --- pure transforms (tested offline) -----------------------------------------------------

def _num(v) -> int | float | str:
    if v in (None, ""):
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return int(f) if f.is_integer() else round(f, 2)


def _imagen(pin: dict) -> str:
    """The pin's own image on Pinterest's CDN (a link, never a copy), biggest listed."""
    media = pin.get("media") or {}
    imgs = media.get("images") or {}
    for k in ("600x", "1200x", "originals", "400x300", "150x150"):
        if (imgs.get(k) or {}).get("url"):
            return imgs[k]["url"]
    return media.get("cover_image_url") or ""


def board_to_row(b: dict, now: str) -> dict:
    return {
        "tablero_id": str(b["id"]),
        "nombre": b.get("name") or "",
        "descripcion": (b.get("description") or "")[:500],
        "privacidad": PRIVACIDAD.get(b.get("privacy") or "", ""),
        "pines": _num(b.get("pin_count")),
        "seguidores": _num(b.get("follower_count")),
        "creado": b.get("created_at") or "",
        "ultima_sync": now,
    }


def handle_producto(url: str) -> str:
    """``/products/<handle>`` from a store link, '' for anything else."""
    partes = [p for p in urlparse(url or "").path.split("/") if p]
    return partes[partes.index("products") + 1].lower() if "products" in partes[:-1] else ""


def productos_por_handle(listados: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in listados:
        h = handle_producto(r.get("url") or "")
        if h and h not in out:
            out[h] = r
    return out


def resumen_metricas(analytics: dict | None, metricas=METRICAS_PIN) -> tuple[dict, str]:
    """Totals for the period and their ``calidad_dato``.

    ``real`` when every day is final (READY), ``estimado`` while Pinterest is still
    processing some day, ``faltante`` when there is no answer at all. Missing is never 0.
    """
    todo = (analytics or {}).get("all") or {}
    dias = todo.get("daily_metrics") or []
    if not todo:
        return {METRICAS[k]: "" for k in metricas}, "faltante"
    listos = [d for d in dias if (d.get("data_status") or "READY") == "READY"]
    suma = todo.get("summary_metrics") or {}
    vals = {}
    for k in metricas:
        if k in suma:
            vals[METRICAS[k]] = _num(suma[k])
        elif listos:
            vals[METRICAS[k]] = _num(sum(float((d.get("metrics") or {}).get(k) or 0)
                                         for d in listos))
        else:
            vals[METRICAS[k]] = ""
    if any(v == "" for v in vals.values()):
        return vals, "faltante"
    calidad = "real" if len(listos) == len(dias) else "estimado"
    return vals, calidad


def pin_to_row(pin: dict, tableros: dict[str, str], productos: dict[str, dict],
               analytics: dict | None, periodo: str, now: str) -> dict:
    enlace = pin.get("link") or ""
    prod = productos.get(handle_producto(enlace), {})
    vals, calidad = resumen_metricas(analytics)
    media = pin.get("media") or {}
    return {
        "pin_id": str(pin["id"]),
        "linea": LINEA,
        "tablero_id": str(pin.get("board_id") or ""),
        "tablero": tableros.get(str(pin.get("board_id") or ""), ""),
        "titulo": pin.get("title") or "",
        "descripcion": (pin.get("description") or "")[:500],
        "enlace": enlace,
        "id_producto_canal": str(prod.get("id_producto_canal") or ""),
        "producto": (prod.get("titulo_en_canal") or "").split(" / ")[0],
        "imagen_url": _imagen(pin),
        "tipo_medio": media.get("media_type") or "",
        "creado": pin.get("created_at") or "",
        "periodo": periodo,
        **vals,
        "calidad_dato": calidad,
        "ultima_sync": now,
    }


def daily_rows(analytics: dict, now: str) -> list[dict]:
    rows = []
    for d in ((analytics or {}).get("all") or {}).get("daily_metrics") or []:
        estado = d.get("data_status") or ""
        met = d.get("metrics") or {}
        listo = estado == "READY"
        rows.append({
            "fecha": d.get("date") or "",
            "linea": LINEA,
            **{col: (_num(met.get(k)) if listo or estado == "PROCESSING" else "")
               for k, col in METRICAS.items()},
            "estado_pinterest": estado,
            "calidad_dato": ("real" if listo else "estimado" if estado == "PROCESSING"
                             else "faltante"),
            "ultima_sync": now,
        })
    return [r for r in rows if r["fecha"]]


def campaign_rows(filas: list[dict]) -> list[dict]:
    out = []
    for f in filas:
        cid = str(f.get("CAMPAIGN_ID") or "")
        dia = str(f.get("DATE") or "")[:10]
        if not cid or not dia:
            continue
        gasto = _num(f.get("SPEND_IN_DOLLAR"))
        valor = _num(f.get("TOTAL_CHECKOUT_VALUE_IN_MICRO_DOLLAR"))
        out.append({
            "campana_dia_id": f"pinterest-{cid}-{dia}",
            "linea": LINEA,
            "plataforma": "pinterest",
            "campana_id": f"pinterest-{cid}",
            "anuncio_id": "",
            "obra_id": "",
            "destino": "",
            "fecha": dia,
            "gasto": gasto,
            "impresiones": _num(f.get("TOTAL_IMPRESSION")),
            "clics": _num(f.get("TOTAL_CLICKTHROUGH")),
            "compras_atribuidas": _num(f.get("TOTAL_CHECKOUT")),
            "valor_atribuido": round(valor / 1_000_000, 2) if valor != "" else "",
            "calidad_dato": "real" if gasto != "" else "faltante",
        })
    return out


def nota_vence(hoy: date | None = None) -> str:
    """'el permiso vence el …' from PINTEREST_TOKEN_VENCE, or ''."""
    vence = config.get("PINTEREST_TOKEN_VENCE")
    if not vence:
        return "fecha de vencimiento del permiso desconocida (falta PINTEREST_TOKEN_VENCE)"
    try:
        d = date.fromisoformat(vence.strip()[:10])
    except ValueError:
        return f"PINTEREST_TOKEN_VENCE no es una fecha ({vence[:10]!r})"
    faltan = (d - (hoy or date.today())).days
    if faltan < 0:
        return f"el permiso venció el {d.isoformat()}: haz uno nuevo"
    aviso = ": haz uno nuevo esta semana" if faltan <= 7 else ""
    return f"el permiso vence el {d.isoformat()} (en {faltan} días){aviso}"


# --- sync ----------------------------------------------------------------------------------

@dataclass
class Resultado:
    cuenta: dict
    tableros: list[dict]
    pines: list[dict]
    diario: list[dict]
    campanas: list[dict] | None      # None: no ad account (or no ads permission)
    nota_ads: str
    avisos: list[str]


def leer(client: PinterestClient, listados: list[dict], hoy: date | None = None,
         dias: int = DIAS, max_pines: int = MAX_PINES) -> Resultado:
    hoy = hoy or datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    start, end = hoy - timedelta(days=dias), hoy - timedelta(days=1)
    periodo = f"{start.isoformat()} a {end.isoformat()}"
    avisos: list[str] = []

    cuenta = client.user_account()
    tableros = [board_to_row(b, now) for b in client.iter_boards()]
    nombres = {t["tablero_id"]: t["nombre"] for t in tableros}
    productos = productos_por_handle(listados)

    pins = sorted(client.iter_pins(), key=lambda p: p.get("created_at") or "", reverse=True)
    pines = []
    for i, p in enumerate(pins):
        analytics = None
        if i < max_pines:
            try:
                analytics = client.pin_analytics(str(p["id"]), start, end)
            except PinterestError as e:
                if e.status in (401, 429):
                    raise
                avisos.append(f"pin {p['id']}: sin números ({e.status})")
        pines.append(pin_to_row(p, nombres, productos, analytics, periodo, now))
    if len(pins) > max_pines:
        avisos.append(f"{len(pins) - max_pines} pines más viejos sin números (límite "
                      f"{max_pines} por sync)")

    diario = daily_rows(client.account_analytics(start, end), now)

    campanas, nota_ads = None, ""
    try:
        cuentas_ads = list(client.iter_ad_accounts())
    except PinterestError as e:
        if e.status not in (403, 404):
            raise
        cuentas_ads, nota_ads = [], f"sin permiso para leer anuncios (ads:read, {e.status})"
    if cuentas_ads:
        campanas = []
        for ad in cuentas_ads:
            camp = list(client.iter_campaigns(str(ad["id"])))
            ids = [str(c["id"]) for c in camp]
            for j in range(0, len(ids), 250):
                campanas += campaign_rows(client.campaign_analytics(
                    str(ad["id"]), ids[j:j + 250], start, end))
        nota_ads = f"{len(cuentas_ads)} cuenta(s) de anuncios"
    elif not nota_ads:
        nota_ads = "la cuenta de Pinterest no tiene cuenta de anuncios"
    return Resultado(cuenta, tableros, pines, diario, campanas, nota_ads, avisos)


def escribir(wb, r: Resultado) -> None:
    wb.upsert("Tableros", r.tableros)
    if r.pines:
        wb.upsert("Pines", r.pines)
    if r.diario:
        wb.upsert("PinterestDiario", r.diario)
    usuario = r.cuenta.get("username") or ""
    partes = [f"@{usuario}" if usuario else "",
              f"{r.cuenta.get('follower_count')} seguidores"
              if r.cuenta.get("follower_count") is not None else "",
              nota_vence()] + r.avisos[:3]
    wb.stamp_source("pinterest", rows=len(r.tableros) + len(r.pines) + len(r.diario),
                    note="; ".join(p for p in partes if p))
    if r.campanas is None:
        wb.stamp_source("pinterest-ads", rows=0, estado="sin-conectar", note=r.nota_ads)
    else:
        if r.campanas:
            wb.upsert("Campanas", r.campanas)
        wb.stamp_source("pinterest-ads", rows=len(r.campanas), note=r.nota_ads)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Pinterest (read-only) into the workbook")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="whose token it is and how many boards; writes nothing")
    group.add_argument("--dry-run", action="store_true", help="counts and samples; writes nothing")
    parser.add_argument("--max-pines", type=int, default=MAX_PINES)
    args = parser.parse_args(argv)

    client = PinterestClient.from_env()
    if args.check:
        c = client.user_account()
        print(f"Cuenta: @{c.get('username')} ({c.get('account_type')}); "
              f"tableros: {c.get('board_count', '—')}; pines: {c.get('pin_count', '—')}")
        print(nota_vence())
        return 0

    from ..localbook import open_workbook

    wb = open_workbook()
    r = leer(client, wb.read("Listados"), max_pines=args.max_pines)
    print(f"Tableros: {len(r.tableros)}  Pines: {len(r.pines)}  Días: {len(r.diario)}  "
          f"Anuncios: {'—' if r.campanas is None else len(r.campanas)} ({r.nota_ads})  "
          f"llamadas: {client.calls}")
    for a in r.avisos:
        print("aviso:", a)
    if args.dry_run:
        for row in r.tableros[:2] + r.pines[:2] + r.diario[-2:]:
            print(json.dumps(row, ensure_ascii=False))
        return 0
    escribir(wb, r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
