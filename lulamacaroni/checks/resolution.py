"""Resolution and proportion check for print files.

Rule from Lorena's list: never stretch or crop a work to fit a format. So this
check only *reports*: a size whose proportion doesn't match the file is
``no-apto`` and must get its own file from Lorena, never an automatic crop.

DPI thresholds are defaults to confirm against Prodigi's file guidelines for each
product during the sample-print step (M3).

    python -m lulamacaroni.checks.resolution archivo.jpg 8x10 12x16 18x24
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

MIN_DPI = 150          # below this: not printable
RECOMMENDED_DPI = 300  # at or above: ideal
ASPECT_TOLERANCE = 0.01  # 1 % difference in proportion is invisible after bleed


@dataclass(frozen=True)
class Result:
    tamano: str
    estado: str      # "ideal", "aceptable", "baja-resolucion", "no-apto"
    dpi: float
    motivo: str

    @property
    def ok(self) -> bool:
        return self.estado in ("ideal", "aceptable")


def parse_size(text: str) -> tuple[float, float]:
    """'12x16' -> (12.0, 16.0) inches."""
    try:
        a, b = text.lower().replace("in", "").replace("×", "x").split("x")
        return float(a), float(b)
    except ValueError:
        raise ValueError(f"size must look like 12x16 (inches), got {text!r}") from None


def check(width_px: int, height_px: int, print_w_in: float, print_h_in: float,
          min_dpi: float = MIN_DPI, recommended_dpi: float = RECOMMENDED_DPI,
          tolerance: float = ASPECT_TOLERANCE) -> Result:
    label = f"{print_w_in:g}x{print_h_in:g}"
    if min(width_px, height_px, print_w_in, print_h_in) <= 0:
        raise ValueError("dimensions must be positive")

    # Match orientation: a portrait file can print a portrait size given either way round.
    file_long, file_short = max(width_px, height_px), min(width_px, height_px)
    print_long, print_short = max(print_w_in, print_h_in), min(print_w_in, print_h_in)

    file_ratio = file_long / file_short
    print_ratio = print_long / print_short
    diff = abs(file_ratio - print_ratio) / print_ratio
    if diff > tolerance:
        return Result(label, "no-apto", 0.0,
                      f"proporción distinta ({file_ratio:.3f} vs {print_ratio:.3f}); "
                      "no se recorta ni se estira: hace falta un archivo para este tamaño")

    dpi = min(file_long / print_long, file_short / print_short)
    if dpi >= recommended_dpi:
        return Result(label, "ideal", dpi, f"{dpi:.0f} dpi")
    if dpi >= min_dpi:
        return Result(label, "aceptable", dpi, f"{dpi:.0f} dpi (menos de {recommended_dpi:g})")
    return Result(label, "baja-resolucion", dpi,
                  f"{dpi:.0f} dpi, mínimo {min_dpi:g}: no imprimir en este tamaño")


def check_file(path: str, sizes: list[str]) -> list[Result]:
    from PIL import Image

    with Image.open(path) as img:
        w, h = img.size
    return [check(w, h, *parse_size(s)) for s in sizes]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a print file against print sizes")
    parser.add_argument("archivo")
    parser.add_argument("tamanos", nargs="+", help="print sizes in inches, e.g. 12x16")
    args = parser.parse_args(argv)
    results = check_file(args.archivo, args.tamanos)
    for r in results:
        print(f"{r.tamano:>8}  {r.estado:16} {r.motivo}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
