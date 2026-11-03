"""Write docs/data-layer.md from schema.py so the doc never drifts.

    python -m lulamacaroni.schema_doc
"""

from __future__ import annotations

from .config import REPO_ROOT
from .schema import LINEAS, LINEAS_GASTOS, TABS

DOC_PATH = REPO_ROOT / "docs" / "data-layer.md"


def render() -> str:
    out = [
        "# Data layer: LulaMacaroni Operaciones workbook",
        "",
        "_Generated from `lulamacaroni/schema.py` by `python -m lulamacaroni.schema_doc`. "
        "Edit the schema, not this file._",
        "",
        "The Google Sheets workbook is the system of record. Lorena owns it in the business "
        "Google account, and the repo's service account reads and writes it. Tab and column "
        "names are in Spanish because she reads them.",
        "",
        "## Two lines, one back office",
        "",
        f"Every record that carries money, a customer or a listing has a `linea` column: "
        f"{', '.join(f'`{l}`' for l in LINEAS)}. `Gastos` also allows "
        f"`{LINEAS_GASTOS[-1]}` for costs that serve both lines; the contador decides the split. "
        "The dashboard reports each line separately and together, and the US LLC's numbers "
        "never mix with the Mexico originals.",
        "",
        "Metric tabs carry `calidad_dato` (`real`, `estimado`, `faltante`) so a missing number "
        "is never shown as zero. `Pedidos` (gross sale) and `Pagos` (deposit received) are "
        "separate tabs so a sale is never counted twice as income.",
        "",
        "## Tabs",
        "",
    ]
    for t in TABS:
        out.append(f"### {t.nombre}")
        out.append("")
        out.append(f"One row per: {t.fila}. Key: `{t.clave}`.")
        out.append("")
        out.append("| Column | Allowed values |")
        out.append("|---|---|")
        for c in t.columnas:
            allowed = ", ".join(t.validaciones.get(c, ()))
            out.append(f"| `{c}` | {allowed} |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    DOC_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {DOC_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
