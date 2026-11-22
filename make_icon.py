"""Genera assets/nexus.ico y assets/nexus.png: la mascota clásica de NEXUS
(cuerpo trapecio crema con degradado, gafas redondas negras, moño rojo),
dibujada con PIL a 4x supersampling. El path del cuerpo es el mismo SVG
de web/nexus.html (viewBox 0 0 100 66)."""
import math
from pathlib import Path

from PIL import Image, ImageDraw

SS = 4                      # supersampling
W, H = 100 * SS, 66 * SS    # lienzo viewBox 100x66


def _q(p0, c, p1, n=24):
    """muestrea una curva cuadrática Q"""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p1[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p1[1]
        pts.append((x * SS, y * SS))
    return pts


def _cuerpo_path():
    """mismo path que FORMAS.original del SVG"""
    pts = [(29 * SS, 2 * SS)]
    pts += [(x * SS, 2 * SS) for x in range(30, 72)]                 # H71
    pts += _q((71, 2), (80, 2), (84, 11))                              # Q
    pts += [(x * SS, y * SS) for x, y in
            [(84 + (97 - 84) * i / 20, 11 + (46 - 11) * i / 20)
             for i in range(1, 21)]]                                   # L97,46
    pts += _q((97, 46), (102, 62), (85, 62))                           # Q
    pts += [(x * SS, 62 * SS) for x in range(84, 14, -1)]              # H15
    pts += _q((15, 62), (-2, 62), (3, 46))                             # Q
    pts += [(x * SS, y * SS) for x, y in
            [(3 + (16 - 3) * i / 20, 46 + (11 - 46) * i / 20)
             for i in range(1, 21)]]                                   # L16,11
    pts += _q((16, 11), (20, 2), (29, 2))                              # Q
    return pts


def _degradado(w, h, c0, c1):
    img = Image.new("RGB", (w, h))
    px = img.load()
    r0, g0, b0 = c0
    r1, g1, b1 = c1
    for y in range(h):
        t = y / max(1, h - 1)
        px_col = (round(r0 + (r1 - r0) * t), round(g0 + (g1 - g0) * t),
                  round(b0 + (b1 - b0) * t))
        for x in range(w):
            px[x, y] = px_col
    return img


def pintar(size=512):
    S = size // 100                      # escala respecto al viewBox
    w, h = 100 * S, 66 * S
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # cuerpo con degradado crema
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon([(x * S / SS, y * S / SS) for x, y in
                                  _cuerpo_path()], fill=255)
    grad = _degradado(w, h, (0xF8, 0xF4, 0xE8), (0xE1, 0xD8, 0xC1)).convert("RGBA")
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)

    def esc(x, y):
        return x * S, y * S

    negro = (20, 20, 20, 255)
    # gafas redondas (aros gruesos) + lentes oscuros
    for cx in (37.9, 62.1):
        x, y = esc(cx, 33)
        r = 9 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=(15, 15, 15, 235),
                  outline=negro, width=max(2, round(2.4 * S)))
        # brillo del lente
        d.line([esc(cx - 3.5, 29.5)[0], esc(cx - 3.5, 29.5)[1],
                esc(cx - 0.5, 32.5)[0], esc(cx - 0.5, 32.5)[1]],
               fill=(255, 255, 255, 110), width=max(1, round(1.4 * S)))
    # puente
    x0, y0 = esc(46.9, 32)
    x1, y1 = esc(53.1, 32)
    d.arc([min(x0, x1) - 3 * S, y0 - 4 * S, max(x0, x1) + 3 * S, y0 + 2 * S],
          start=200, end=340, fill=negro, width=max(2, round(2.4 * S)))
    # patillas
    for (a, b) in [((28.9, 31.5), (20, 28.5)), ((71.1, 31.5), (80, 28.5))]:
        d.line([esc(*a), esc(*b)], fill=negro, width=max(2, round(2.2 * S)))
    # moño rojo
    rojo = (226, 45, 40, 255)
    d.polygon([esc(50, 54), esc(37, 47), esc(37, 61), esc(44, 60.5)], fill=rojo)
    d.polygon([esc(50, 54), esc(63, 47), esc(63, 61), esc(56, 60.5)], fill=rojo)
    x, y = esc(50, 54)
    r = 3.8 * S
    d.ellipse([x - r, y - r, x + r, y + r], fill=(160, 20, 18, 255))
    return img


def main():
    out = Path(__file__).parent / "assets"
    out.mkdir(exist_ok=True)
    base = pintar(100 * SS * 4)          # 1600x1056, supersampleado
    png = base.resize((512, 512 * 66 // 100), Image.LANCZOS)
    png.save(out / "nexus.png")
    ico = base.resize((256, 256 * 66 // 100), Image.LANCZOS)
    ico.save(out / "nexus.ico", sizes=[(256, 256), (128, 128), (64, 64),
                                       (48, 48), (32, 32), (16, 16)])
    print("icono OK:", out / "nexus.ico", "y", out / "nexus.png")


if __name__ == "__main__":
    main()
