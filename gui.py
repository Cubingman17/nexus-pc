"""La ISLA de NEXUS v35 — la copia fiel del notch del TROKO DESK.

· Isla NEGRA plana arriba y redondeada abajo (22 px), con los
  ANCHOS exactos de la web por estado (idle 236, listen/speak 320,
  think 268, focus 300, success 292, remind 380, sleep 256) y el
  ancho animado con la MISMA curva de la web —
  cubic-bezier(.22,.9,.3,1) en .5 s: sale rápido, frena suave.
· La cabeza es la de Troko: cuerpo trapezoidal con degradado
  (#F8F4E8→#E1D8C1) que ROTA con la mirada, ojos que siguen el
  cursor, moods (^^ feliz + rubor, líneas al dormir, entrecerrado
  en foco, pulso al hablar), parpadeo cada 2,8–6 s (110 ms) y
  mirada vagabunda cuando nadie mueve el mouse.
· Slots como la web: waves lima al escuchar, waves moradas al
  hablar, 3 puntitos al pensar, crosshair + cuenta en foco, check
  lima + palabra al cumplir, gota azul + texto al avisar, «z z»
  al dormir. Hover: abre a los 260 ms, se pliega a los 420.
· Duerme sola tras 35 s sin mover el mouse (como Troko) y despierta
  con el primer movimiento.
· Render HQ 3× + LANCZOS con CACHÉ por firma: solo se re-dibuja
  cuando algo cambia de verdad → fluida sin fundir la CPU.
"""
import math
import queue
import random
import re
import time
import tkinter as tk

import estado

# ── NITIDEZ DPI: sin esto Windows estira la ventana como bitmap ────
# (era la causa del notch «pixelado»: la pantalla escala al 125-150%)
try:
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))          # PerMonitorV2
    except Exception:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

# ── paleta: mascota Troko + acentos NASA (#0B3D91 #FC3D21 #38bdf8) ─
BG = "#05070d"               # el notch: negro azulado (body NASA)
CREMA = "#F2EBD9"          # --cream (texto)
GRIS = "#8E8E93"           # --gray
LIME = "#B6F23A"           # --lime (se usa en el panel)
SKY = "#38bdf8"            # acento cielo (el .ai-avatar-ring NASA)
AZUL = "#58B2FF"           # azul suave (waves al hablar)
VERDE = "#059669"          # éxito (state-green de la NASA)
ROJO = "#FC3D21"           # alerta (NASA red)
MORADO = "#8B5CF6"         # --purple
CARA = "#141414"           # los ojos (oscuros sobre crema)
BLUSH = "#F29DB0"          # rubor
CUERPO1 = "#F8F4E8"        # degradado del cuerpo (arriba)
CUERPO2 = "#E1D8C1"        # degradado del cuerpo (abajo)
CUERPO_FB = "#F4EFE2"      # cuerpo sin Pillow (plano)

# ── dimensiones ─────────────────────────────────────────────────────
ANCHO_V = 800              # ancho FIJO de la ventana = ancho del panel
ALTO = 30                  # la banda del notch, pegada arriba (más chiquita)
SOMBRA_H = 0               # sin sombra: notch negro limpio (adiós raya)
CANVAS_ALTO = ALTO
MAX_W = ANCHO_V            # panel.py lo usa para centrarse
TRANS = "#01100a"
S = 4                      # supersampling: 4× + LANCZOS = nitidez de verdad
R_ISLA = 14                # radio de abajo (≈ alto/2, como la web)

# anchos por estado: los de la web, a la escala del notch chiquito
ANCHOS = {"idle": 198, "listen": 268, "speak": 268, "think": 226,
          "focus": 252, "success": 246, "remind": 320, "sleep": 214}

A_ESTADO = {
    "arrancando": "sleep",
    "esperando": "idle",
    "escuchando": "listen",
    "pensando": "think",
    "hablando": "speak",
}

# el mood de la cabeza por estado (MOOD de la web)
MOODS = {"idle": "neutral", "listen": "listen", "think": "think",
         "speak": "speak", "focus": "focus", "success": "happy",
         "remind": "neutral", "sleep": "sleep"}

# Pillow disponible → render HQ; si no, dibujo vectorial de siempre
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    _HQ = True
except Exception:
    _HQ = False

_FUENTES = {}               # caché: leer el .ttl cada frame era lento
_PALABRA = re.compile(r"^[^\w¡¿]+")


def _fuente(tipo, tam):
    """Fuente para el render HQ (Segoe UI / Consolas de Windows)."""
    clave = (tipo, tam)
    if clave not in _FUENTES:
        ruta = "segoeui.ttf" if tipo == "ui" else "consola.ttf"
        try:
            _FUENTES[clave] = ImageFont.truetype(ruta, int(tam * S))
        except Exception:
            _FUENTES[clave] = ImageFont.load_default()
    return _FUENTES[clave]


def _rgb(hexcolor):
    return tuple(int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))


_COL = {}


def _col(c):
    """'#B6F23A' → (182, 242, 58, 255); ('#fff', 90) → con alpha."""
    v = _COL.get(c)
    if v is None:
        if isinstance(c, tuple):
            r, g, b = _rgb(c[0])
            v = (r, g, b, c[1])
        else:
            v = _rgb(c) + (255,)
        _COL[c] = v
    return v


# ── la curva de la web: cubic-bezier(.22,.9,.3,1) ───────────────────
def _bez(t, x1, y1, x2, y2):
    u = 1 - t
    return (3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t,
            3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t)


_EASE = [_bez(i / 128.0, .22, .9, .3, 1) for i in range(129)]


def _ease(p):
    """Progreso (0..1) → valor de la curva: rápida al salir, freno suave."""
    lo, hi = 0, len(_EASE) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if _EASE[m][0] < p:
            lo = m
        else:
            hi = m
    x0, y0 = _EASE[lo]
    x1, y1 = _EASE[hi]
    f = 0.0 if x1 == x0 else (p - x0) / (x1 - x0)
    return y0 + (y1 - y0) * f


class _Tween:
    """Anima un valor con la curva de la web (cubic-bezier .22,.9,.3,1)."""
    __slots__ = ("v", "de", "obj", "t0", "dur")

    def __init__(self, v):
        self.v = self.de = self.obj = float(v)
        self.t0 = 0.0
        self.dur = 0.0

    def ir(self, destino, dur, ahora):
        if abs(destino - self.obj) < 0.5:      # mismo objetivo: sigue
            return
        self.de = self.v                      # arranca desde donde está
        self.obj = float(destino)
        self.t0 = ahora
        self.dur = dur

    def paso(self, ahora):
        if self.dur <= 0:
            return self.v
        t = (ahora - self.t0) / self.dur
        if t >= 1:
            self.v = self.obj
            self.dur = 0
            return self.v
        self.v = self.de + (self.obj - self.de) * _ease(max(0.0, t))
        return self.v


# ── la cabeza de TROKO: la geometría del SVG de la web ───────────────
def _quad(p0, c, p1, n=6):
    """Muestrea una curva cuadrática del path (Q) en n puntos."""
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        pts.append((u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0],
                    u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]))
    return pts


def _path_cuerpo():
    """El cuerpo: M29 2H71Q80 2 84 11L97 46Q102 62 85 62H15
    Q-2 62 3 46L16 11Q20 2 29 2Z (trapecio redondeado)."""
    pts = [(29, 2), (71, 2)]
    pts += _quad((71, 2), (80, 2), (84, 11))
    pts += [(97, 46)]
    pts += _quad((97, 46), (102, 62), (85, 62))
    pts += [(15, 62)]
    pts += _quad((15, 62), (-2, 62), (3, 46))
    pts += [(16, 11)]
    pts += _quad((16, 11), (20, 2), (29, 2))
    return pts


_CUERPO = _path_cuerpo()
_ARCO_IZQ = [(29, 38)] + _quad((29, 38), (37, 25), (45, 38), 8)
_ARCO_DER = [(55, 38)] + _quad((55, 38), (63, 25), (71, 38), 8)
_SONRISA = [(43, 46)] + _quad((43, 46), (50, 52), (57, 46), 8)
_GOTA = ([(10, 1)] + _quad((10, 1), (1, 12), (1, 17.5), 6)
         + [(10 + 9 * math.cos(a), 17.5 + 9 * math.sin(a)) for a in
            [i * math.pi / 8 for i in range(8, -1, -1)]]
         + _quad((19, 17.5), (19, 12), (10, 1), 6))


def cabeza_items(its, cx, cy, alto, mood, gx, gy, blink, fase):
    """La cabeza de Troko en primitivas 1×: cuerpo con degradado que
    rota con la mirada, ojos que siguen el cursor y los moods de la
    web (^^ feliz + rubor, líneas al dormir, entrecerrado en foco,
    pulso al hablar). gx/gy ∈ [-1, 1]; fase en segundos."""
    k = alto / 82.0
    x0 = cx - 50 * k
    y0 = cy - 33 * k

    def X(px):
        return x0 + (px + 6) * k

    def Y(py):
        return y0 + (py + 8) * k

    rot = math.radians(gx * 3.0 + (-4.0 if mood == "sleep" else 0.0))
    crx, cry = X(50), Y(65.8)              # origin 50% 90% del SVG
    ca, sa = math.cos(rot), math.sin(rot)
    boost = 1.3 if alto < 40 else 1.0      # isla: carita legible a 26 px

    def R(px, py):
        x, y = X(px) - crx, Y(py) - cry
        return (crx + x * ca - y * sa, cry + x * sa + y * ca)

    # el cuerpo: degradado + translate con la mirada (--gx*1.6px)
    tbx, tby = gx * 1.6, gy * 1.0
    pts = [(x + tbx, y + tby) for x, y in (R(px, py) for px, py in _CUERPO)]
    its.append(("body", pts))

    if mood == "happy":                    # ^^ + sonrisa + rubor
        for arco in (_ARCO_IZQ, _ARCO_DER):
            its.append(("pline", [R(px, py) for px, py in arco],
                        max(1.3, 3.4 * k * boost), CARA))
        its.append(("pline", [R(px, py) for px, py in _SONRISA],
                    max(1.1, 2.6 * k * boost), CARA))
        for px in (25, 75):
            ex, ey = R(px, 44)
            its.append(("oval", ex - 6 * k, ey - 3.4 * k,
                        ex + 6 * k, ey + 3.4 * k, (BLUSH, 204)))
    elif mood == "sleep":                  # ojos cerrados: dos rayas
        for px0, px1 in ((30, 46), (54, 70)):
            a, b = R(px0, 35), R(px1, 35)
            its.append(("line", a[0], a[1], b[0], b[1], CARA,
                        max(1.3, 3.4 * k * boost)))
    elif mood == "focus":                  # entrecerrado (squint)
        for px in (38, 62):
            ex, ey = R(px, 35)
            its.append(("oval", ex - 7.6 * k, ey - 3 * k * boost,
                        ex + 7.6 * k, ey + 3 * k * boost, CARA))
    else:
        # ojos: siguen el cursor (--gx*5px, --gy*3.4px) y escalan.
        # En la isla la cabeza es chiquita: los ojos se BOOSTEAN ×1.3
        # y llevan CHISPA para que la cara se lea bien a 26 px.
        es = {"listen": 1.16, "think": 0.84}.get(mood, 1.0)
        if mood == "speak":                # talk: pulso .5 s ida y vuelta
            es = 1.05 + 0.05 * math.sin(2 * math.pi * fase)
        if mood == "think":                # a pensar mira pa' arriba
            exo, eyo = 0.0, -4.0
        else:
            exo, eyo = gx * 5.0, gy * 3.4
        by = 0.08 if blink else 1.0        # blink: --by:.08
        for px, py in ((38, 33), (62, 33)):
            ex, ey = R(px, py)
            ex, ey = ex + exo, ey + eyo
            r = 7.4 * es * k * boost
            its.append(("oval", ex - r, ey - r * by, ex + r, ey + r * by,
                        CARA))
            if r >= 2.2 and by > 0.5:      # chispa de luz en el ojo
                sr = r * 0.34
                its.append(("oval", ex - r * 0.32 - sr, ey - r * 0.36 - sr,
                            ex - r * 0.32 + sr, ey - r * 0.36 + sr,
                            CUERPO1))


def pts_pill(x0, y0, x1, y1, r):
    """Plano arriba + redondeado abajo (para el fallback vectorial)."""
    pts = [x0, y0, x1, y0]
    cyy = y1 - r
    cxr = x1 - r
    for i in range(9):
        a = (math.pi / 2) * (i / 8)
        pts += [cxr + r * math.cos(a), cyy + r * math.sin(a)]
    cxl = x0 + r
    for i in range(9):
        a = (math.pi / 2) * (i / 8)
        pts += [cxl - r * math.sin(a), cyy + r * math.cos(a)]
    return pts


def _fb_col(c):
    """Color sólido para el fallback (alpha sobre negro = multiplicar)."""
    if isinstance(c, tuple):
        r, g, b, a = _col(c)
        return "#%02x%02x%02x" % (r * a // 255, g * a // 255, b * a // 255)
    return c


def pintar_canvas(c, its, tag="isla"):
    """Pinta primitivas 1× en un canvas Tk (fallback sin Pillow y
    cabeza grande del sidebar)."""
    c.delete(tag)
    for it in its:
        t = it[0]
        if t == "rect":
            c.create_rectangle(it[1], it[2], it[3], it[4],
                               fill=_fb_col(it[5]), outline="", tags=tag)
        elif t == "pill":
            c.create_polygon(pts_pill(it[1], it[2], it[3], it[4], it[5]),
                             smooth=True, fill=_fb_col(it[6]), outline="",
                             tags=tag)
        elif t == "pillline":
            pass                      # hairline: imposible sin alpha
        elif t == "body":
            c.create_polygon([v for px, py in it[1] for v in (px, py)],
                             smooth=True,
                             fill=_fb_col(it[2]) if len(it) > 2
                             else CUERPO_FB, outline="", tags=tag)
        elif t == "oval":
            c.create_oval(it[1], it[2], it[3], it[4], fill=_fb_col(it[5]),
                          outline="", tags=tag)
        elif t == "circle":
            c.create_oval(it[1], it[2], it[3], it[4], fill="",
                          outline=_fb_col(it[5]), width=max(1, it[6]),
                          tags=tag)
        elif t == "line":
            c.create_line(it[1], it[2], it[3], it[4], fill=_fb_col(it[5]),
                          width=max(1, it[6]), capstyle="round", tags=tag)
        elif t == "pline":
            pts = [v for px, py in it[1] for v in (px, py)]
            c.create_line(pts, smooth=True, fill=_fb_col(it[3]),
                          width=max(1, it[2]), capstyle="round", tags=tag)
        elif t == "text":
            x, y, anchor, txt, tipo, tam = it[1:7]
            c.create_text(x, y, anchor=anchor, text=txt, fill=_fb_col(it[7]),
                          font=((("Consolas" if tipo == "mono"
                                  else "Segoe UI"), int(tam), "bold")),
                          tags=tag)


class Interfaz:
    def __init__(self, novedades):
        self.novedades = novedades
        self.fase = 0.0                 # segundos: reloj de la animación
        self._t_prev = time.monotonic()

        # carita
        self._gaze = (0.0, 0.0)
        self._gaze_tgt = (0.0, 0.0)
        self._prox_glance = 0.0
        self._blink = False
        self._blink_fin = 0.0
        self._prox_blink = time.monotonic() + 2.0
        self._raton_ultimo = None
        self._ult_mov = time.monotonic()
        self._aviso_desde = None

        # render con CACHÉ: solo se re-dibuja si la firma cambia
        self._ult_firma = None
        self._renders = 0

        # tweens de la web: ancho .5 s, panel .55 s
        self._tw_ancho = _Tween(40.0)   # arranca plegadita y crece
        self._tw_alto = _Tween(0.0)

        # hover (como la web: abre 260 ms, pliega 420 ms)
        self._sobre_desde = None
        self._fuera_desde = None
        self._cooldown = 0.0

        # arrastre
        self._inicio = None
        self._prev = (0, 0)
        self._movio = False

        # isla y despliegue del panel
        self.pw = 40.0
        self.abierto = False
        self.wh = float(ALTO)
        self._alto_marco = 0.0
        try:
            import panel as _panel_mod
            self.alto_panel = int(getattr(_panel_mod, "ALTO_P", 460))
        except Exception:
            self.alto_panel = 460

        self.raiz = tk.Tk()
        # fuentes con las métricas del diseño (96/72): la NITIDEZ la
        # da el DPI-awareness de arriba, no inflar los puntos
        try:
            self.raiz.call("tk", "scaling", 96.0 / 72.0)
        except Exception:
            pass
        self.raiz.title("NEXUS")
        self.raiz.configure(bg=TRANS)
        self.ancho, self.alto = MAX_W, ALTO
        self.raiz.attributes("-topmost", True)
        self.raiz.overrideredirect(True)
        try:
            self.raiz.attributes("-transparentcolor", TRANS)
        except tk.TclError:
            pass
        self.raiz.pack_propagate(False)
        self.raiz.bind("<Escape>", lambda e: self.cerrar_panel())

        # arriba: el lienzo de la isla (con aire para la sombra);
        # debajo (oculto hasta desplegar): el marco del panel
        self.canvas = tk.Canvas(self.raiz, width=ANCHO_V,
                                height=CANVAS_ALTO,
                                bg=TRANS, highlightthickness=0)
        self.canvas.pack(side="top")
        self.marco_panel = tk.Frame(self.raiz, bg=TRANS, height=1)
        self.marco_panel.pack(side="top", fill="x")
        self.marco_panel.pack_propagate(False)
        self._img = None                   # PhotoImage viva del frame HQ
        self._buf = None                   # buffer completo (composición)
        self._item = None                  # ítem del canvas (se crea 1 vez)

        self.canvas.bind("<Button-1>", self._presionar)
        self.canvas.bind("<B1-Motion>", self._arrastrar)
        self.canvas.bind("<ButtonRelease-1>", self._soltar)

        try:
            cx = (self.raiz.winfo_screenwidth() - ANCHO_V) // 2
        except Exception:
            cx = 100
        # VENTANA DE TAMAÑO FIJO: ya nace con el alto completo (isla +
        # panel). Lo que no se ve es transparente y no estorba los
        # clics. Así la ventana JAMÁS se redimensiona (el fantasma
        # transparente de v24 no vuelve).
        self.raiz.geometry(
            f"{ANCHO_V}x{CANVAS_ALTO + self.alto_panel}+{cx}+0")
        self._animar()

    # ── abrir/cerrar el panel DESDE la isla ─────────────────────────
    def abrir_panel(self):
        self.abierto = True

    def cerrar_panel(self):
        self.abierto = False
        try:
            import panel
            if panel._PANEL is not None:
                panel._PANEL.visible = False
        except Exception:
            pass

    # ── rectángulos en pantalla (para el hover) ──────────────────────
    def _rect_pill(self):
        try:
            wx, wy = self.raiz.winfo_x(), self.raiz.winfo_y()
        except Exception:
            wx, wy = 0, 0
        x0 = (ANCHO_V - self.pw) / 2
        return (wx + x0, wy, wx + x0 + self.pw, wy + ALTO)

    def _rect_ventana(self):
        try:
            wx, wy = self.raiz.winfo_x(), self.raiz.winfo_y()
        except Exception:
            wx, wy = 0, 0
        return (wx, wy, wx + ANCHO_V, wy + self.wh)

    # ── clic y arrastre ─────────────────────────────────────────────
    def _presionar(self, evento):
        self._inicio = (evento.x_root, evento.y_root)
        self._prev = (0, 0)
        self._movio = False

    def _arrastrar(self, evento):
        if self._inicio is None:
            return
        dx = evento.x_root - self._inicio[0]
        dy = evento.y_root - self._inicio[1]
        if abs(dx) + abs(dy) < 5:
            return
        self._movio = True
        paso_x, paso_y = dx - self._prev[0], dy - self._prev[1]
        self._prev = (dx, dy)
        try:
            x0, y0 = self.raiz.winfo_x(), self.raiz.winfo_y()
            self.raiz.geometry(f"+{x0 + paso_x}+{y0 + paso_y}")
        except Exception:
            pass

    def _soltar(self, evento):
        if not self._movio:
            try:
                import panel
                if panel.esta_visible():
                    panel.cerrar()
                    self._cooldown = time.monotonic() + 0.6
                else:
                    panel.abrir(self)
            except Exception:
                pass
        self._inicio = None
        self._movio = False

    # ── estado de la isla ───────────────────────────────────────────
    def _estado_actual(self, ahora):
        if self.abierto:
            return "abierto", None       # los slots se desvanecen (web)
        e = estado.get()
        aviso = e.get("aviso") or ""
        if aviso:
            palabra = _PALABRA.sub("", aviso)
            palabra = palabra if len(palabra) <= 26 else palabra[:25] + "…"
            return ("success" if "🎉" in aviso else "remind"), palabra
        if e.get("crono"):
            return "focus", None
        modo = e.get("modo", "esperando")
        if modo == "esperando" and ahora - self._ult_mov > 35:
            return "sleep", None         # Troko duerme tras 35 s quietos
        return A_ESTADO.get(modo, "idle"), None

    # ── mirada y parpadeo ────────────────────────────────────────────
    def _puntero(self, ahora):
        try:
            px, py = self.raiz.winfo_pointerx(), self.raiz.winfo_pointery()
        except Exception:
            return None, None
        if (px, py) != self._raton_ultimo:
            self._raton_ultimo = (px, py)
            self._ult_mov = ahora        # movió el mouse: despierta
        return px, py

    def _mirada(self, ahora, dt, px, py):
        if px is not None:
            try:
                wx = self.raiz.winfo_x() + ANCHO_V / 2
                wy = self.raiz.winfo_y() + ALTO / 2
            except Exception:
                wx, wy = ANCHO_V / 2, ALTO / 2
            self._gaze_tgt = (max(-1.0, min(1.0, (px - wx) / 260.0)),
                              max(-1.0, min(1.0, (py - wy) / 200.0)))
        elif (ahora - self._ult_mov > 5
              and ahora >= self._prox_glance):
            # nadie mueve el mouse: mira pa' los lados (life() de la web)
            self._gaze_tgt = (random.uniform(-0.8, 0.8),
                              random.uniform(-0.5, 0.5))
            self._prox_glance = ahora + random.uniform(2.0, 5.0)
        k = 1 - 0.84 ** (dt * 60)         # lerp .16/frame a 60 fps
        gx, gy = self._gaze
        tx, ty = self._gaze_tgt
        self._gaze = (gx + (tx - gx) * k, gy + (ty - gy) * k)

    def _tick_blink(self, ahora):
        if self._blink and ahora >= self._blink_fin:
            self._blink = False
            self._prox_blink = ahora + random.uniform(2.8, 6.0)
        elif not self._blink and ahora >= self._prox_blink:
            self._blink = True           # 110 ms, como la web
            self._blink_fin = ahora + 0.11

    # ── los slots de la isla (SLOTS de la web, a escala chiquita) ────
    def _waves(self, its, x, cy, color, izquierda):
        """▁▃▅▃▁: 5 barras de 3 px, ciclo de 1 s, retardo .12 s."""
        for i in range(5):
            h = 4 + 10 * (0.5 + 0.5 * math.sin(
                2 * math.pi * (self.fase - i * 0.12)))
            bx = x - 25 + i * 5.5 if izquierda else x + i * 5.5
            its.append(("rect", bx, cy - h / 2, bx + 3, cy + h / 2, color))

    def _dot(self, its, x, cy):
        """El punto cielo con glow de 3 pasos (suave, sin bloques)."""
        its.append(("oval", x - 6, cy - 6, x + 6, cy + 6, (SKY, 36)))
        its.append(("oval", x - 4.5, cy - 4.5, x + 4.5, cy + 4.5,
                    (SKY, 72)))
        its.append(("oval", x - 3, cy - 3, x + 3, cy + 3, SKY))

    def _dots(self, its, x, cy):
        """Pensando: 3 puntitos que respiran (blink 1 s, retardo .2 s)."""
        for i in range(3):
            a = 0.25 + 0.75 * (0.5 + 0.5 * math.sin(
                2 * math.pi * (self.fase - i * 0.2)))
            bx = x + i * 9
            its.append(("oval", bx, cy - 2.5, bx + 5, cy + 2.5, (SKY,
                        int(a * 255))))

    def _crosshair(self, its, x, cy):
        """El crosshair del foco (14 px, cielo)."""
        mx, my = x + 7, cy
        its.append(("circle", mx - 3.9, my - 3.9, mx + 3.9, my + 3.9,
                    SKY, 1.3))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            its.append(("line", mx + dx * 3.2, my + dy * 3.2,
                        mx + dx * 6.1, my + dy * 6.1, SKY, 1.3))

    def _check(self, its, x, cy):
        """El check VERDE con la palomita negra (state-green NASA)."""
        mx, my = x + 8, cy
        its.append(("oval", mx - 8, my - 8, mx + 8, my + 8, VERDE))
        its.append(("pline", [(mx - 4, my + 1.5), (mx - 1, my + 4.5),
                              (mx + 4, my - 3)], 2, "#000000"))

    def _gota(self, its, x, cy):
        """La gota ROJA del aviso (NASA red, como state-red)."""
        kx, ky = 12 / 20, 16 / 26
        pts = [(x - 12 + px * kx, cy - 8 + py * ky) for px, py in _GOTA]
        its.append(("body", pts, ROJO))

    def _isla_items(self, est, extra):
        """Devuelve [(tipo, ...)] con todo lo que hay que dibujar."""
        its = []
        w = self.pw
        if est == "abierto":
            # ABIERTO: la isla se ensancha hasta el panel y los slots
            # se desvanecen (opacity 0 en la web) — queda la banda negra
            if w >= ANCHO_V - 0.5:
                its.append(("rect", 0, 0, ANCHO_V, CANVAS_ALTO, BG))
            else:
                x0 = (ANCHO_V - w) / 2
                its.append(("pill", x0, 0, x0 + w, ALTO, R_ISLA, BG))
            return its
        x0 = (ANCHO_V - w) / 2
        x1 = x0 + w
        # la isla: NEGRA, plana arriba, redondeada abajo — LIMPIA:
        # ni hairline ni sombra (la sombra era la «raya bugueada»)
        its.append(("pill", x0, 0, x1, ALTO, R_ISLA, BG))

        cy = ALTO / 2
        hx = (x0 + x1) / 2
        izq = hx - 26.0            # borde del slot izq (media cabeza + gap)
        der = hx + 26.0            # borde del slot derecho

        # la cabeza al CENTRO de la barra (chiquita, como el notch)
        cabeza_items(its, hx, cy, 26, MOODS.get(est, "neutral"),
                     *self._gaze, self._blink, self.fase)

        # los slots según el estado (SLOTS de la web)
        if est == "idle":
            self._dot(its, der, cy)
        elif est in ("listen", "speak"):
            color = SKY if est == "listen" else AZUL
            self._waves(its, izq, cy, color, True)
            self._waves(its, der, cy, color, False)
        elif est == "think":
            self._dots(its, der, cy)
        elif est == "focus":
            self._crosshair(its, der, cy)
            its.append(("text", der + 19, cy, "w",
                        estado.get()["crono"], "mono", 11.5, CREMA))
        elif est == "success":
            self._check(its, der, cy)
            if extra:
                its.append(("text", der + 21, cy, "w", extra, "ui", 11,
                            CREMA))
        elif est == "remind":
            self._gota(its, izq, cy)
            if extra:
                its.append(("text", der, cy, "w", extra, "ui", 11, CREMA))
        elif est == "sleep":
            its.append(("text", der, cy, "w", "z z", "ui", 10.5, GRIS))
        return its

    def _ancho_estado(self, est, extra):
        """Ancho de la isla por estado — y si trae palabra (check o
        aviso), CRECE para que el texto quepa dentro, sin desbordarse."""
        if est == "abierto":
            return float(ANCHO_V)
        base = float(ANCHOS.get(est, 198))
        if not extra:
            return base
        wtxt = 5.9 * len(extra)
        if est == "success":       # check 16 + gap 5 + palabra
            return min(430.0, max(base, 2 * (60 + wtxt)))
        return min(430.0, max(base, 2 * (38 + max(wtxt, 20))))

    # ── el CACHÉ del render: firma = lo que de verdad cambia ────────
    def _firma(self, est, extra):
        anima = est in ("listen", "speak", "think")
        fase = int(self.fase * 30) if anima else 0
        gx, gy = self._gaze
        mirada = 0 if est == "abierto" else (round(gx * 40), round(gy * 40))
        return (est, extra, int(self.pw), fase, self._blink, mirada)

    # ── renderer HQ: 3× con Pillow + LANCZOS, SOLO la franja de la
    #    isla (el LANCZOS a ancho completo era el 60% del coste) ────
    def _dibujar_hq(self, its, x0r, x1r):
        W = max(2, x1r - x0r)
        img = Image.new("RGBA", (W * S, CANVAS_ALTO * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        def SX(x):
            return (x - x0r) * S

        def SY(y):
            return y * S

        for it in its:
            t = it[0]
            if t == "rect":
                d.rectangle([SX(it[1]), SY(it[2]), SX(it[3]), SY(it[4])],
                            fill=_col(it[5]))
            elif t == "pill":
                d.rounded_rectangle(
                    [SX(it[1]), SY(it[2]), SX(it[3]), SY(it[4])],
                    radius=it[5] * S, fill=_col(it[6]),
                    corners=(False, False, True, True))
            elif t == "pillline":
                d.rounded_rectangle(
                    [SX(it[1]), SY(it[2]), SX(it[3]), SY(it[4])],
                    radius=it[5] * S, fill=None,
                    outline=_col(it[6]), width=S)
            elif t == "body":
                pts = [((px - x0r) * S, py * S) for px, py in it[1]]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                bx0, by0 = int(min(xs)), int(min(ys))
                bx1, by1 = int(max(xs)) + 1, int(max(ys)) + 1
                if len(it) > 2:            # gota azul: color plano
                    d.polygon(pts, fill=_col(it[2]))
                elif by1 - by0 < 2:
                    d.polygon(pts, fill=_col(CUERPO1))
                else:
                    # degradado vertical #F8F4E8 → #E1D8C1 (tk-grad)
                    mask = Image.new("L", (bx1 - bx0, by1 - by0), 0)
                    ImageDraw.Draw(mask).polygon(
                        [(x - bx0, y - by0) for x, y in pts], fill=255)
                    grad = Image.new("RGBA", mask.size, (0, 0, 0, 0))
                    gd = ImageDraw.Draw(grad)
                    c1, c2 = _col(CUERPO1), _col(CUERPO2)
                    for yy in range(mask.size[1]):
                        f = yy / max(1, mask.size[1] - 1)
                        gd.line([(0, yy), (mask.size[0], yy)],
                                fill=tuple(int(a + (b - a) * f)
                                           for a, b in zip(c1[:3],
                                                           c2[:3])) + (255,))
                    img.paste(grad, (bx0, by0), mask)
            elif t == "oval":
                d.ellipse([SX(it[1]), SY(it[2]), SX(it[3]), SY(it[4])],
                          fill=_col(it[5]))
            elif t == "circle":
                d.ellipse([SX(it[1]), SY(it[2]), SX(it[3]), SY(it[4])],
                          fill=None, outline=_col(it[5]),
                          width=max(1, int(it[6] * S)))
            elif t == "line":
                d.line([SX(it[1]), SY(it[2]), SX(it[3]), SY(it[4])],
                       fill=_col(it[5]), width=max(1, int(it[6] * S)))
            elif t == "pline":
                d.line([((px - x0r) * S, py * S) for px, py in it[1]],
                       fill=_col(it[3]), width=max(1, int(it[2] * S)),
                       joint="curve")
            elif t == "text":
                x, y, anchor, txt, tipo, tam = it[1:7]
                f = _fuente(tipo, tam)
                bb = d.textbbox((0, 0), txt, font=f)
                if anchor == "c":
                    px = SX(x) - (bb[2] - bb[0]) / 2
                elif anchor == "e":
                    px = SX(x) - (bb[2] - bb[0])
                else:
                    px = SX(x)
                d.multiline_text((px, SY(y) - (bb[1] + bb[3]) / 2),
                                 txt, font=f, fill=_col(it[7]))
        chico = img.resize((W, CANVAS_ALTO), Image.LANCZOS)
        # componer la franja sobre base OPACA del color mágico: así
        # Tk nunca mezcla alphas parciales (los bordes anti-alias
        # se funden en Pillow, no contra el fondo de la ventana) y
        # -transparentcolor recorta LIMPIO lo que es exactamente TRANS
        buf = self._buf
        if buf is None:
            buf = self._buf = Image.new("RGBA", (ANCHO_V, CANVAS_ALTO),
                                        _col(TRANS))
        buf.paste(_col(TRANS), (0, 0, ANCHO_V, CANVAS_ALTO))
        buf.alpha_composite(chico, (x0r, 0))
        if self._img is None:
            self._img = ImageTk.PhotoImage(buf)
        else:
            try:
                self._img.paste(buf)
            except Exception:
                self._img = ImageTk.PhotoImage(buf)
        if self._item is None:
            self._item = self.canvas.create_image(0, 0, anchor="nw",
                                                  image=self._img)

    def _dibujar(self, est, extra):
        """Con CACHÉ: si la firma no cambió, la imagen pegada ya es
        la correcta → NO se re-renderiza."""
        firma = self._firma(est, extra)
        if firma == self._ult_firma and self._img is not None:
            return
        its = self._isla_items(est, extra)
        x0r = max(0, int((ANCHO_V - self.pw) / 2) - 3)
        x1r = min(ANCHO_V, int((ANCHO_V + self.pw) / 2) + 3)
        if _HQ:
            try:
                self._renders += 1
                self._dibujar_hq(its, x0r, x1r)
                self._ult_firma = firma
                return
            except Exception:
                pass        # Pillow falló (¿sin .ttf?): vectorial y listo
        pintar_canvas(self.canvas, its)
        self._ult_firma = firma

    # ── HOVER: abrir/cerrar sin clic (260/420 ms como la web) ───────
    def _hover(self, px, py, ahora):
        if self._inicio is not None:      # arrastrando: nada
            return
        try:
            import panel
        except Exception:
            return
        if self.abierto:
            sobre = self._en_rect(px, py, self._rect_ventana())
        else:
            sobre = self._en_rect(px, py, self._rect_pill())
        if ahora < self._cooldown:
            return
        if not panel.esta_visible():
            if sobre:
                if self._sobre_desde is None:
                    self._sobre_desde = ahora
                elif ahora - self._sobre_desde >= 0.12:   # abre al instante
                    panel.abrir(self)
                    self._sobre_desde = None
            else:
                self._sobre_desde = None
        else:
            if sobre or panel.dentro(px, py):
                self._fuera_desde = None
            elif self._fuera_desde is None:
                self._fuera_desde = ahora
            elif ahora - self._fuera_desde >= 0.24:       # pliega pronto
                panel.cerrar()
                self._fuera_desde = None

    def _en_rect(self, px, py, rect):
        return (px is not None and rect[0] - 2 <= px <= rect[2] + 2
                and rect[1] <= py <= rect[3] + 4)

    # ── el loop ─────────────────────────────────────────────────────
    def _animar(self):
        ahora = time.monotonic()
        dt = max(0.001, min(0.1, ahora - self._t_prev))
        self._t_prev = ahora
        self.fase += dt                   # el reloj de la animación (s)

        est, extra = self._estado_actual(ahora)

        # ancho de la isla → el del estado (curva de la web, .3 s)
        self._tw_ancho.ir(self._ancho_estado(est, extra), 0.3, ahora)
        self.pw = self._tw_ancho.paso(ahora)

        # despliegue del panel: .38 s con la misma curva (grid-rows web)
        objetivo = float(self.alto_panel) if self.abierto else 0.0
        self._tw_alto.ir(objetivo, 0.38, ahora)
        self._alto_marco = self._tw_alto.paso(ahora)
        try:
            self.marco_panel.configure(
                height=max(1, int(self._alto_marco)))
        except Exception:
            pass
        self.wh = CANVAS_ALTO + self._alto_marco

        # la losa del panel SOLO existe cuando se ve: plegada dejaba
        # una rayita negra de 1 px bajo el notch (el bug de la raya)
        try:
            import panel as _p
            if _p._PANEL is not None and _p._PANEL.vivo:
                _p._PANEL.losa_visible(self.abierto
                                       or self._alto_marco > 1.5)
        except Exception:
            pass

        # la carita VIVE aunque el render esté cacheado
        px, py = self._puntero(ahora)
        self._mirada(ahora, dt, px, py)
        self._tick_blink(ahora)
        self._dibujar(est, extra)

        # hover: el panel se abre y se pliega solito
        try:
            self._hover(px, py, ahora)
        except Exception:
            pass

        # el aviso dura como en la web: 1,7 s el check, 4,2 s el aviso
        e = estado.get()
        aviso = e.get("aviso") or ""
        if aviso:
            if self._aviso_desde is None:
                self._aviso_desde = ahora
            elif ahora - self._aviso_desde > (1.7 if "🎉" in aviso
                                              else 4.2):
                estado.set_aviso("")
                self._aviso_desde = None
        else:
            self._aviso_desde = None

        # la cola del pipeline no crece
        try:
            while True:
                self.novedades.get_nowait()
        except queue.Empty:
            pass
        self.raiz.after(16, self._animar)   # 60 fps: sedoso de verdad

    def arrancar(self):
        self.raiz.protocol("WM_DELETE_WINDOW", self.raiz.destroy)
        self.raiz.mainloop()


def arrancar(novedades):
    Interfaz(novedades).arrancar()
