# -*- coding: utf-8 -*-
"""Genera los iconos PNG de la app en app/.

Se ejecuta una sola vez; los PNG quedan versionados junto a la app.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs"

FONDO = (20, 38, 61, 255)
ACENTO = (232, 163, 61, 255)

L = 1024  # se dibuja grande y se reduce, para bordes suaves


def dibujar(escala_glifo=1.0, fondo_completo=True):
    img = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if fondo_completo:
        d.rounded_rectangle([0, 0, L - 1, L - 1], radius=int(L * 0.22), fill=FONDO)
    else:
        d.rectangle([0, 0, L - 1, L - 1], fill=FONDO)

    # contenedor visto de costado, centrado
    ancho = L * 0.64 * escala_glifo
    alto = L * 0.30 * escala_glifo
    x0 = (L - ancho) / 2
    y0 = (L - alto) / 2
    x1, y1 = x0 + ancho, y0 + alto

    d.rounded_rectangle([x0, y0, x1, y1], radius=int(alto * 0.14), fill=ACENTO)

    # corrugado: ranuras verticales del color del fondo
    ranura = ancho * 0.028
    paso = ancho / 9
    for i in range(1, 9):
        cx = x0 + paso * i
        d.rectangle([cx - ranura / 2, y0 + alto * 0.14, cx + ranura / 2, y1 - alto * 0.14], fill=FONDO)

    # marco superior e inferior, para que lea como contenedor y no como codigo de barras
    grosor = alto * 0.10
    d.rectangle([x0, y0, x1, y0 + grosor], fill=ACENTO)
    d.rectangle([x0, y1 - grosor, x1, y1], fill=ACENTO)

    return img


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)

    base = dibujar()
    for tam in (192, 512):
        base.resize((tam, tam), Image.LANCZOS).save(DESTINO / f"icono-{tam}.png")
        print(f"icono-{tam}.png")

    # maskable: fondo a sangre y glifo dentro de la zona segura (80%)
    mask = dibujar(escala_glifo=0.74, fondo_completo=False)
    mask.resize((512, 512), Image.LANCZOS).save(DESTINO / "icono-maskable-512.png")
    print("icono-maskable-512.png")

    base.resize((32, 32), Image.LANCZOS).save(DESTINO / "favicon.png")
    print("favicon.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
