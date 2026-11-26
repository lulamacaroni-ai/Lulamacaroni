"""Store settings, all from the environment (.env locally, Render's dashboard when hosted).

Nothing here has a default secret. The public texts (legal name, address) are settings too,
so the repo never carries them and the policies show "[pending]" until they are set.
"""

from __future__ import annotations

from dataclasses import dataclass

from .. import config

PENDIENTE = "[pending]"


@dataclass(frozen=True)
class Ajustes:
    url: str = "http://127.0.0.1:8780"     # public address, no trailing slash
    marca: str = "Lula Macaroni"
    soporte: str = "info@lulamacaroni.com"  # the business inbox (Google Workspace)
    remitente: str = "Lula Macaroni <orders@lulamacaroni.com>"
    razon_social: str = ""                  # the US LLC's legal name
    domicilio: str = ""                     # its business address
    estado_constitucion: str = ""           # state where the LLC was formed
    envio_usd: float = 0.0                  # flat US shipping per order; 0 = free shipping
    impuestos: bool = True                  # Stripe Tax at checkout
    secreto: str = ""                       # signs the cart cookie

    @classmethod
    def desde_entorno(cls) -> Ajustes:
        def num(nombre: str, defecto: float) -> float:
            try:
                return float(config.get(nombre, str(defecto)))
            except ValueError:
                return defecto

        return cls(
            url=(config.get("LULA_TIENDA_URL") or cls.url).rstrip("/"),
            marca=config.get("LULA_TIENDA_MARCA", cls.marca),
            soporte=config.get("LULA_TIENDA_SOPORTE", cls.soporte),
            remitente=config.get("LULA_TIENDA_REMITENTE", cls.remitente),
            razon_social=config.get("LULA_US_RAZON_SOCIAL", ""),
            domicilio=config.get("LULA_US_DOMICILIO", ""),
            estado_constitucion=config.get("LULA_US_ESTADO", ""),
            envio_usd=num("LULA_TIENDA_ENVIO_USD", 0.0),
            impuestos=(config.get("LULA_TIENDA_IMPUESTOS", "si").lower() not in ("no", "0", "off")),
            secreto=config.get("LULA_TIENDA_SECRET", ""),
        )

    def faltantes(self) -> list[str]:
        """Settings the store needs before it opens to buyers."""
        out = []
        for nombre, valor in (("LULA_US_RAZON_SOCIAL", self.razon_social),
                              ("LULA_US_DOMICILIO", self.domicilio),
                              ("LULA_US_ESTADO", self.estado_constitucion),
                              ("LULA_TIENDA_SECRET", self.secreto)):
            if not valor:
                out.append(nombre)
        return out

    def texto(self, valor: str) -> str:
        return valor or PENDIENTE
