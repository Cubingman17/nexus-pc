"""El panel de NEXUS v32 — LA COPIA EXACTA del TROKO (verde claro):

· Mismo look Troko Desk: sidebar con ICONOS de verdad (HQ), tarjetas
  #1E1E1E, fondo NEGRO PURO fundido con el notch → cero costura.
· ARREGLADA LA DEMORA (el bug de v29): las secciones se construyen
  LAZY — solo la que estás viendo — y a los 900 ms se precalienta
  el resto EN PARALELO, invisible. Cuando hagas hover ya está todo
  listo: el panel sale instantáneo.
· La LOSA se renderiza con Pillow (2× + LANCZOS): bordes suaves de
  verdad, no dentados. Burbujas del CHAT redondeadas de verdad.
· Chat con burbujas, diálogo del correo, tareas/hábitos/enfoque:
  toda la lógica de siempre intacta.
"""
import datetime
import math
import random
import threading
import time
import tkinter as tk

import estado
import tools

# ── paleta NASA SPACE APPS (global.css del reto) ───────────────────
# azul #0B3D91 · rojo #FC3D21 · cielo #38bdf8 · tarjetas #101a2e
TRANS = "#01100a"          # color mágico: transparente en Windows
FONDO = "#05070d"          # body NASA: negro azulado (funde con notch)
BORDE = "#1e3a5f"          # borde ui-card
ACTIVO_NAV = "#0d1f3c"     # pestaña activa (azul NASA profundo)
ITEM_TX = "#64748b"        # texto de items inactivos (slate)
TARJETA = "#101a2e"        # ui-card
RAISE = "#16233f"          # hover de botones (tablet-frame border)
CHIP = "#0d1526"           # .chip
ACTIVO = "#12275c"         # burbuja tuya: azul NASA oscuro
LINEA = "#1e293b"          # hairlines
PISTAS = "#1e3a5f"         # tracks / drops off
ACENTO = "#38bdf8"         # cielo: el acento de la interfaz NASA
ACENTO_TX = "#062033"      # texto azul-oscuro sobre el cielo
AZUL = "#60a5fa"           # azul claro (focus ring)
MORADO = "#8B5CF6"         # --purple: hechas
AMBAR = "#F5A623"          # --amber: rachas 🔥
ROJO = "#FC3D21"           # NASA red: Parar / alertas
TEXTO = "#f8fafc"          # texto principal
SUBTEXTO = "#94a3b8"       # --gray
MUTED = "#cbd5e1"          # --muted
GLOW = "#0f2a52"           # azul NASA MUY oscuro (tracks del ring)
# los estados en palabras, como la isla de la web (STATUS)
STATUS = {"arrancando": "arrancando", "esperando": "listo",
          "escuchando": "escuchando", "pensando": "pensando",
          "hablando": "hablando"}

ANCHO_P, ALTO_P = 800, 480      # v33: más ancho (sidebar con texto)
LATERAL = 150                   # sidebar con TEXTO (image-32)
SOMBRA1 = "#03040a"
SOMBRA2 = "#070b16"
BRILLO = "#223a5e"
GLOW = "#0f2a52"
DIAS = ["lunes", "martes", "miércoles", "jueves",
        "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]
PUNTO_MODO = {"arrancando": SUBTEXTO, "esperando": "#059669",
              "escuchando": ACENTO, "pensando": AMBAR,
              "hablando": TEXTO}
# (icono HQ, emoji de respaldo, sección)
NAVEGACION = [("inicio", "🏠", "Inicio"), ("chat", "💬", "Chat"),
              ("tareas", "📋", "Tareas"), ("habitos", "💧", "Hábitos"),
              ("enfoque", "⏳", "Enfoque")]
SUBTITULOS = {"Inicio": "Tu resumen de hoy",
              "Chat": "Habla o escribe con NEXUS",
              "Tareas": "Tus pendientes de hoy",
              "Hábitos": "Tu progreso de hoy",
              "Enfoque": "Bloques de concentración"}
FUENTE = "Segoe UI"

# Pillow disponible → ICONOS de verdad (imágenes HQ); si no, emoji
try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL = True
except Exception:
    _PIL = False

_ICONOS = {}               # caché de PhotoImages (vivas, no basura)
_LOSA_IMG = None           # la losa HQ (una sola vez)


def _rgb(hexcolor):
    """'#4dff96' → (77, 255, 150)."""
    return tuple(int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))


def _icono_img(nombre, color, tam=22):
    """ICONO HQ con Pillow: se dibuja a 3× y se reduce con LANCZOS
    (imágenes bonitas de verdad, no puntos). None si no hay Pillow."""
    if not _PIL:
        return None
    clave = (nombre, color, tam)
    if clave in _ICONOS:
        return _ICONOS[clave]
    SS = 3
    N = tam * SS
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = _rgb(color)
    if nombre == "inicio":            # 🏠 casa
        d.polygon([(6, 36), (33, 8), (60, 36)], fill=c)
        d.rounded_rectangle((12, 32, 54, 60), radius=5, fill=c)
        d.rounded_rectangle((27, 42, 39, 60), radius=3,
                            fill=(0, 0, 0, 255))
    elif nombre == "chat":           # 💬 burbuja
        d.rounded_rectangle((6, 8, 60, 46), radius=13, fill=c)
        d.polygon([(16, 42), (16, 58), (32, 46)], fill=c)
        for i in range(3):
            x = 15 + i * 12
            d.ellipse((x, 22, x + 8, 30), fill=(0, 0, 0, 255))
    elif nombre == "tareas":         # 📋 lista con líneas
        for i, y in enumerate((14, 32, 50)):
            d.rounded_rectangle((6, y - 6, 16, y + 4), radius=5,
                                fill=c)
            d.line((24, y, 58, y), fill=c, width=6)
    elif nombre == "habitos":        # 💧 gota
        d.polygon([(33, 4), (52, 32), (56, 44), (33, 60),
                   (10, 44), (14, 32)], fill=c)
        d.ellipse((22, 30, 34, 42), fill=(0, 0, 0, 255))
    elif nombre == "enfoque":        # ⏳ reloj de arena
        d.rounded_rectangle((14, 4, 52, 12), radius=4, fill=c)
        d.polygon([(16, 14), (50, 14), (33, 33)], fill=c)
        d.polygon([(16, 52), (50, 52), (33, 33)], fill=c)
        d.rounded_rectangle((14, 54, 52, 62), radius=4, fill=c)
    elif nombre == "pc":            # 🖥 monitor
        d.rounded_rectangle((8, 8, 58, 42), radius=6, fill=c)
        d.rectangle((30, 42, 36, 50), fill=c)
        d.rounded_rectangle((20, 50, 46, 56), radius=3, fill=c)
    elif nombre == "check":         # ✓ círculo con palomita
        d.ellipse((4, 4, 60, 60), outline=c, width=6)
        d.line([(18, 31), (28, 41), (47, 20)], fill=c, width=6)
    else:                            # fallback: un punto con halo
        d.ellipse((8, 8, 58, 58), fill=c)
    chico = img.resize((tam, tam), Image.LANCZOS)
    photo = ImageTk.PhotoImage(chico)
    _ICONOS[clave] = photo       # referencia viva (tk la necesita)
    return photo


def seg_de_crono(crono):
    """'24:59' → 1499 segundos (o None si no es un crono válido)."""
    try:
        mm, ss = crono.split(":")
        s = int(mm) * 60 + int(ss)
        return s if s >= 0 else None
    except Exception:
        return None


def _losa_hq():
    """Render de la losa con Pillow (2× + LANCZOS): plana ARRIBA
    (fundida con la banda del notch: cero costura) y redondeada
    abajo con radio 30. Fondo NASA: degradado #05070d→#0a1120,
    CAMPO DE ESTRELLAS y dos glows radiales (azul arriba-der,
    rojo abajo-izq) como el body::before del reto. UNA vez → cero."""
    if not _PIL:
        return None
    try:
        SS = 2
        W, H = ANCHO_P * SS, ALTO_P * SS
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, W - 1, (ALTO_P - 2) * SS - 1),
            radius=30 * SS, fill=255,
            corners=(False, False, True, True))
        grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        c1, c2 = (5, 7, 13), (10, 17, 32)
        for yy in range(H):
            f = yy / max(1, H - 1)
            gd.line([(0, yy), (W, yy)],
                    fill=tuple(int(a + (b - a) * f)
                               for a, b in zip(c1, c2)) + (255,))
        # glows y estrellas van en una CAPA aparte: ImageDraw con
        # alpha REEMPLAZA píxeles (no mezcla), así que se dibujan
        # sobre transparente y luego se funden con alpha_composite
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gdd = ImageDraw.Draw(glow)
        for gx, gy, rad, col, top in (
                (int(W * .88), int(H * .08), int(560 * SS),
                 (11, 61, 145), 60),
                (int(W * .06), int(H * .92), int(440 * SS),
                 (252, 61, 33), 22)):
            pasos = 26
            for i in range(pasos):        # grande+tenue → chico+intenso
                f = i / pasos
                r = rad * (1 - f)
                a = int(top * f * f)
                if a <= 0:
                    continue
                gdd.ellipse([gx - r, gy - r, gx + r, gy + r],
                            fill=col + (a,))
        # campo de estrellas (semilla fija: mismas siempre)
        rng = random.Random(7)
        for _ in range(90):
            sx, sy = rng.uniform(0, W), rng.uniform(0, H)
            br = rng.choice((1, 1, 1, 1.5, 2)) * SS
            a = rng.randint(38, 190)
            col = (248, 250, 252) if rng.random() < .7 else (148, 163, 184)
            gdd.ellipse([sx - br, sy - br, sx + br, sy + br],
                        fill=col + (a,))
        grad.alpha_composite(glow)
        # borde de cristal sutil (rgba(255,255,255,.07)) — en capa
        # nueva, para que se FUNDA y no reemplace el alpha
        borde = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(borde).rounded_rectangle(
            (0, 0, W - 1, (ALTO_P - 2) * SS - 1), radius=30 * SS,
            fill=None, outline=(255, 255, 255, 18), width=SS,
            corners=(False, False, True, True))
        grad.alpha_composite(borde)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.paste(grad, (0, 0), mask)
        chico = img.resize((ANCHO_P, ALTO_P), Image.LANCZOS)
        return ImageTk.PhotoImage(chico)
    except Exception:
        return None


def pts_rrect(x0, y0, x1, y1, r):
    return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]


def pts_pill(x0, y0, x1, y1, r):
    """Plano arriba + redondeado abajo: la isla desplegada de la web."""
    pts = [x0, y0, x1, y0]
    cyy = y1 - r
    cxr = x1 - r
    import math
    for i in range(9):
        a = (math.pi / 2) * (i / 8)
        pts += [cxr + r * math.cos(a), cyy + r * math.sin(a)]
    cxl = x0 + r
    for i in range(9):
        a = (math.pi / 2) * (i / 8)
        pts += [cxl - r * math.sin(a), cyy + r * math.cos(a)]
    return pts


class Boton:
    """Botón redondeado en canvas con hover de verdad."""

    def __init__(self, padre, texto, command, fondo=FONDO,
                 fill=TARJETA, fg=TEXTO, hover=None, hover_fg=None,
                 ancho=None, alto=32, r=9, font=None,
                 padx=14, side="top",
                 activo_fill=None, activo_fg=None,
                 inactivo_fill=None, inactivo_fg=None):
        self.texto = texto
        self.command = command
        self._fill, self._fg = fill, fg
        self._hover = hover if hover is not None else fill
        self._hover_fg = hover_fg if hover_fg is not None else fg
        self._activo_fill = activo_fill or ACTIVO
        self._activo_fg = activo_fg or ACENTO
        self._inactivo_fill = inactivo_fill or FONDO
        self._inactivo_fg = inactivo_fg or SUBTEXTO
        self.alto = alto
        self.rr = min(r, max(1, alto // 2))
        self.w = ancho or max(44, len(texto) * 7 + padx * 2)
        self.canvas = tk.Canvas(padre, width=self.w, height=alto,
                                bg=fondo, highlightthickness=0)
        self.canvas.pack(side=side)
        self.font = font or (FUENTE, 10)
        self._pintar(fill, fg)
        self.canvas.bind("<Button-1>", lambda e: self.invocar())
        self.canvas.bind("<Enter>",
                         lambda e: self._pintar(self._hover, self._hover_fg))
        self.canvas.bind("<Leave>",
                         lambda e: self._pintar(self._fill, self._fg))

    def _pintar(self, fill, fg):
        self._ult_fill, self._ult_fg = fill, fg
        c = self.canvas
        c.delete("all")
        r = min(self.rr, self.alto // 2)
        c.create_polygon(pts_rrect(1, 1, self.w - 1, self.alto - 1, r),
                         smooth=True, fill=fill, outline="")
        c.create_text(self.w // 2, self.alto // 2, text=self.texto,
                      fill=fg, font=self.font)

    def marcar(self, activo):
        if activo:
            self._pintar(self._activo_fill, self._activo_fg)
        else:
            self._pintar(self._inactivo_fill, self._inactivo_fg)

    def invocar(self):
        if self.command:
            self.command()


class Icono:
    """v33: fila de navegación del SIDEBAR estilo TROKO (image-32):
    ICONO + TEXTO al lado ("Inicio", "Chat"...). Activo = fondo
    #2D2D2D con texto BLANCO; inactivo = texto #A0A0A0. Sin Pillow
    cae a emoji y sigue vivo."""

    def __init__(self, padre, nombre, emoji, command, tam=44,
                 icon_tam=22, fondo=None, texto=None, ancho=134,
                 alto=38):
        self.nombre = nombre
        self.emoji = emoji
        self.command = command
        self.texto = texto
        self.icon_tam = icon_tam if texto else 22
        self.fondo = fondo if fondo is not None else FONDO
        self.modo = "off"          # off | hover | on
        if texto is not None:
            self.tam, self.alto_f = ancho, alto
            self.canvas = tk.Canvas(padre, width=ancho, height=alto,
                                    bg=self.fondo, highlightthickness=0)
        else:
            self.tam, self.alto_f = tam, tam
            self.icon_tam = icon_tam
            self.canvas = tk.Canvas(padre, width=tam, height=tam,
                                    bg=self.fondo, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.invocar())
        self.canvas.bind("<Enter>", lambda e: self._pintar("hover"))
        self.canvas.bind("<Leave>", lambda e: self._pintar(self.modo))
        self._pintar("off")

    def _pintar(self, modo):
        self._ult_modo = modo
        c = self.canvas
        c.delete("all")
        if self.texto is not None:
            # fila Troko: icono + texto, activo #2D2D2D (image-32)
            if modo == "on":
                c.create_polygon(pts_rrect(1, 1, self.tam - 1,
                                          self.alto_f - 1, 10),
                                 smooth=True, fill=ACTIVO_NAV, outline="")
            elif modo == "hover":
                c.create_polygon(pts_rrect(1, 1, self.tam - 1,
                                          self.alto_f - 1, 10),
                                 smooth=True, fill=TARJETA, outline="")
            color = ACENTO if modo == "on" else (
                "#F2F2F2" if modo == "hover" else ITEM_TX)
            img = _icono_img(self.nombre, color, self.icon_tam)
            if img is not None:
                c.create_image(19, self.alto_f // 2, image=img)
            else:
                c.create_text(19, self.alto_f // 2, text=self.emoji,
                              fill=color, font=(FUENTE, 12))
            c.create_text(41, self.alto_f // 2, text=self.texto,
                          anchor="w", fill=color,
                          font=(FUENTE, 10, "bold"))
            return
        if modo == "on":
            c.create_polygon(pts_rrect(1, 1, self.tam - 1,
                                      self.tam - 1, 12),
                             smooth=True, fill=ACTIVO_NAV, outline="")
            color = ACENTO
        else:
            if modo == "hover":
                c.create_polygon(pts_rrect(1, 1, self.tam - 1,
                                          self.tam - 1, 12),
                                 smooth=True, fill=TARJETA, outline="")
            color = "#F2F2F2" if modo == "hover" else ITEM_TX
        img = _icono_img(self.nombre, color, self.icon_tam)
        if img is not None:
            c.create_image(self.tam // 2, self.tam // 2, image=img)
        else:
            c.create_text(self.tam // 2, self.tam // 2, text=self.emoji,
                          fill=color, font=(FUENTE, 15))

    def marcar(self, activo):
        self.modo = "on" if activo else "off"
        self._pintar(self.modo)

    def invocar(self):
        if self.command:
            self.command()


class Panel:
    """El TROKO DESK de NEXUS: sidebar + tarjetas, negro puro."""

    def __init__(self, ui):
        self.ui = ui
        self.visible = False
        self.vivo = True
        self.sucio = True
        self.seccion = "Inicio"
        self._frames = {}
        self._nav = {}
        self._nav_lbl = {}
        self._todos = []          # todos los Boton, para tests y orden
        self._bt = []             # Boton efímeros de tareas
        self._bh = []             # Boton efímeros de hábitos
        self.chat_msj = []
        self._ultima_foco = None
        self._mini_fase = 0.0      # la cabeza del sidebar (v35)
        self._mini_blink = 0
        self._mini_prox = 0.0
        self._correo_win = None
        self._correo_cerrar = False
        self._losa_on = True       # la losa vive mientras el panel se ve

        # vive DENTRO de la ventana de la isla, justo bajo el lienzo
        self.marco = tk.Frame(ui.marco_panel, bg=TRANS)
        self.marco.pack(fill="both", expand=True)

        # la losa: NEGRA PURA (el color del notch), plano arriba
        # (fundida con la banda del notch: CERO costura) y abajo
        # redondeada, como .island[data-open] de la web
        lienzo = tk.Canvas(self.marco, width=ANCHO_P, height=ALTO_P,
                           bg=TRANS, highlightthickness=0)
        lienzo.pack()
        self._losa(lienzo)

        base = tk.Frame(self.marco, bg=FONDO)
        base.place(x=14, y=8, width=ANCHO_P - 28, height=ALTO_P - 16)
        self._cuerpo(base)

        # LAZY: solo se construye lo que se está VIENDO. Las demás
        # secciones se precalientan a los 900 ms (invisible) → el
        # primer hover es INSTANTÁNEO (v29 construía TODO ahí y
        # congelaba la ventana 1-2 segundos: ese era "se demora").
        self._construir_inicio()
        self.mostrar_seccion("Inicio")
        try:
            self.marco.after(250, self._precalentar)
        except Exception:
            pass
        self._refrescar()
        self._pintar_mini()

    def _losa(self, lienzo):
        """La losa negra: HQ con Pillow (plana arriba, radio 30 abajo,
        una sola vez y en caché) o polygon vectorial de respaldo."""
        global _LOSA_IMG
        if _PIL:
            try:
                if _LOSA_IMG is None:
                    _LOSA_IMG = _losa_hq()
                if _LOSA_IMG is not None:
                    lienzo.create_image(0, 0, anchor="nw",
                                        image=_LOSA_IMG)
                    return
            except Exception:
                pass
        lienzo.create_polygon(
            pts_pill(0, 0, ANCHO_P, ALTO_P - 2, 30),
            smooth=True, fill=FONDO, outline="")

    def losa_visible(self, visible):
        """La losa SOLO existe cuando el panel se ve: plegada dejaba
        una rayita negra de 1 px bajo el notch (el bug de la raya)."""
        if visible == self._losa_on:
            return
        self._losa_on = visible
        if visible:
            self.marco.pack(fill="both", expand=True)
        else:
            self.marco.pack_forget()

    # ── construcción LAZY de secciones ──────────────────────────────
    _CONSTRUIR = {"Inicio": "_construir_inicio",
                  "Chat": "_construir_chat",
                  "Tareas": "_construir_tareas",
                  "Hábitos": "_construir_habitos",
                  "Enfoque": "_construir_enfoque"}

    def _asegurar_seccion(self, sec):
        """Construye la sección la PRIMERA vez que se pide."""
        if sec in self._frames:
            return
        getattr(self, self._CONSTRUIR[sec])()

    def _precalentar(self):
        """A los 900 ms del arranque construye el resto, invisible.
        Así el primer hover no construye nada → abre al instante."""
        if not self.vivo:
            return
        for sec in ("Chat", "Tareas", "Hábitos", "Enfoque"):
            try:
                self._asegurar_seccion(sec)
            except Exception:
                pass
        try:
            if self.sucio:
                self._refrescar()
        except Exception:
            pass

    # ── helpers ─────────────────────────────────────────────────────
    def _boton(self, padre, texto, command, **kw):
        b = Boton(padre, texto, command, **kw)
        self._todos.append(b)
        return b

    def _tarjeta(self, c, x0, y0, x1, y1, r=14, fill=TARJETA):
        """Tarjeta #1E1E1E: sombra 2 capas + borde + brillo arriba."""
        c.create_polygon(pts_rrect(x0 + 2, y0 + 3, x1 + 2, y1 + 3, r),
                         smooth=True, fill=SOMBRA1, outline="")
        c.create_polygon(pts_rrect(x0 + 1, y0 + 2, x1 + 1, y1 + 2, r),
                         smooth=True, fill=SOMBRA2, outline="")
        c.create_polygon(pts_rrect(x0, y0, x1, y1, r), smooth=True,
                         fill=fill, outline=BORDE)
        c.create_line(x0 + r, y0 + 1, x1 - r, y0 + 1, fill=BRILLO)

    def _texto_widget(self, padre, t="", tamanio=10, color=TEXTO,
                      bold=False, anclar="w", pad=(0, 0), fuente=None,
                      side="top"):
        lbl = tk.Label(padre, text=t, bg=padre["bg"], fg=color,
                       anchor=anclar, font=(fuente or FUENTE, tamanio,
                                            "bold" if bold else "normal"))
        lbl.pack(side=side, anchor=anclar, padx=pad[0], pady=pad[1])
        return lbl

    def _badge(self, padre, texto):
        chip = tk.Frame(padre, bg=CHIP)
        chip.pack(side="left", padx=(8, 0))
        lbl = tk.Label(chip, text=texto, bg=CHIP, fg=MUTED, padx=8,
                       font=("Consolas", 9, "bold"))
        lbl.pack()
        return lbl

    def _field(self, padre, alto=44):
        """Field pill con sombrita (#1E1E1E + hairline + sombra)."""
        marco = tk.Frame(padre, bg=SOMBRA2)
        marco.pack(fill="x", pady=(2, 8))
        borde = tk.Frame(marco, bg=BORDE)
        borde.pack(fill="x", padx=2, pady=(0, 2))
        fila = tk.Frame(borde, bg=TARJETA)
        fila.pack(fill="x", padx=1, pady=1)
        fila.configure(height=alto)
        fila.pack_propagate(False)
        return fila

    def _entrada(self, padre, fila=None):
        dest = fila if fila is not None else padre
        ent = tk.Entry(dest, bg=TARJETA, fg=TEXTO,
                       insertbackground=ACENTO, bd=0, relief="flat",
                       font=(FUENTE, 10))
        ent.pack(side="left", fill="x", expand=True, padx=12, pady=7)
        return ent

    # ── la cabeza del sidebar: Troko en grande ────────────────────
    def _pintar_mini(self):
        """v35: la CABEZA de Troko en el sidebar (74×54, como el
        .who de la web): mira el cursor, parpadea cada 2,8–6 s y
        cambia de mood con el estado de la isla."""
        if not self.vivo:
            return
        import gui
        c = self.canvas_mini
        c.delete("all")
        e = estado.get()
        aviso = e.get("aviso") or ""
        if aviso:
            est = "success" if "🎉" in aviso else "remind"
        elif e.get("crono"):
            est = "focus"
        else:
            est = {"arrancando": "sleep", "esperando": "idle",
                   "escuchando": "listen", "pensando": "think",
                   "hablando": "speak"}.get(e.get("modo", "esperando"),
                                            "idle")
        # la mirada sigue al cursor (aim() de la web)
        gx = gy = 0.0
        try:
            px = self.ui.raiz.winfo_pointerx()
            py = self.ui.raiz.winfo_pointery()
            cx = c.winfo_rootx() + 37
            cy = c.winfo_rooty() + 27
            gx = max(-1.0, min(1.0, (px - cx) / 260.0))
            gy = max(-1.0, min(1.0, (py - cy) / 200.0))
        except Exception:
            pass
        # parpadeo: 110 ms cada 2,8–6 s, como la web
        ahora = time.monotonic()
        if self._mini_blink > 0:
            self._mini_blink -= 1
        elif (est in ("idle", "listen", "think", "speak")
              and ahora >= self._mini_prox):
            self._mini_blink = 2          # 2 ticks de 50 ms ≈ 110 ms
            self._mini_prox = ahora + random.uniform(2.8, 6.0)
        self._mini_fase += 0.05
        its = []
        gui.cabeza_items(its, 37, 27, 54, gui.MOODS.get(est, "neutral"),
                         gx, gy, self._mini_blink > 0, self._mini_fase)
        gui.pintar_canvas(c, its, "mini")
        try:
            self.lbl_mini_status.config(
                text={"idle": "listo", "listen": "escuchando",
                      "think": "pensando", "speak": "hablando",
                      "focus": "enfoque", "success": "listo",
                      "remind": "aviso", "sleep": "dormido"}.get(
                          est, "listo"))
        except Exception:
            pass
        try:
            self.marco.after(50, self._pintar_mini)
        except Exception:
            pass

    # ── estructura: sidebar + main ──────────────────────────────────
    def _cuerpo(self, base):
        cuerpo = tk.Frame(base, bg=FONDO)
        cuerpo.pack(fill="both", expand=True)

        # el SIDEBAR del Troko: el CUBITO de la isla vive justo
        # encima (en la banda del notch) → avatar del panel
        lateral = tk.Frame(cuerpo, bg=FONDO)
        lateral.pack(side="left", fill="y")
        lateral.configure(width=LATERAL)
        # logo arriba (como el .who de la web): la CABEZA grande
        # (74×54) + nombre + estado «● listo»
        tk.Frame(lateral, bg=FONDO, height=10).pack()
        self.canvas_mini = tk.Canvas(lateral, width=74, height=54,
                                     bg=FONDO, highlightthickness=0)
        self.canvas_mini.pack()
        tk.Label(lateral, text="NEXUS", bg=FONDO, fg=TEXTO,
                 font=(FUENTE, 13, "bold")).pack()
        fila_st = tk.Frame(lateral, bg=FONDO)
        fila_st.pack()
        tk.Label(fila_st, text="●", bg=FONDO, fg=ACENTO,
                 font=(FUENTE, 8)).pack(side="left")
        self.lbl_mini_status = tk.Label(fila_st, text="listo", bg=FONDO,
                                        fg=MUTED, font=("Consolas", 8))
        self.lbl_mini_status.pack(side="left")
        tk.Frame(lateral, bg=FONDO, height=12).pack()
        for icono, emoji, nombre in NAVEGACION:
            b = Icono(lateral, icono, emoji,
                      lambda n=nombre: self.mostrar_seccion(n),
                      texto=nombre)
            self._nav[nombre] = b
            tk.Frame(lateral, bg=FONDO, height=4).pack()

        tk.Frame(cuerpo, bg=LINEA, width=1).pack(side="left", fill="y")

        main = tk.Frame(cuerpo, bg=FONDO)
        main.pack(side="left", fill="both", expand=True)
        self._cabecera(main)
        self.zona = tk.Frame(main, bg=FONDO)
        self.zona.pack(fill="both", expand=True, padx=18, pady=(4, 10))

    def _cabecera(self, main):
        cab = tk.Frame(main, bg=FONDO)
        cab.pack(fill="x", padx=(18, 12), pady=(10, 2))
        izq = tk.Frame(cab, bg=FONDO)
        izq.pack(side="left")
        self.lbl_titulo = self._texto_widget(izq, "Inicio", 19, TEXTO,
                                             True, pad=(2, 0))
        self.lbl_subtitulo = self._texto_widget(izq, "", 9, SUBTEXTO,
                                                pad=(2, 0))
        der = tk.Frame(cab, bg=FONDO)
        der.pack(side="right")
        self.lbl_punto = self._texto_widget(der, "●", 10, ACENTO, True,
                                            side="left")
        self.lbl_modo = self._texto_widget(der, "listo", 8, MUTED,
                                           side="left",
                                           fuente="Consolas")
        tk.Label(der, text="100% LOCAL", bg=CHIP, fg=MUTED, padx=7,
                 pady=1, font=("Consolas", 7, "bold")).pack(
                     side="left", padx=(8, 0))
        tk.Label(der, text="⌃⌥ Espacio", bg=CHIP, fg=MUTED, padx=7,
                 pady=1, font=("Consolas", 8)).pack(side="left",
                                                    padx=(8, 0))
        self._boton(der, "✕", self._cerrar, ancho=28, alto=28, r=8,
                    fill=TARJETA, hover=RAISE, hover_fg=ROJO,
                    side="left")
        sep = tk.Frame(main, bg=LINEA, height=1)
        sep.pack(fill="x", padx=(18, 12))

    # ── secciones ───────────────────────────────────────────────────
    def _construir_inicio(self):
        f = tk.Frame(self.zona, bg=FONDO)
        self._frames["Inicio"] = f

        fila = tk.Frame(f, bg=FONDO)
        fila.pack(fill="x", pady=(0, 8))
        izq = tk.Frame(fila, bg=FONDO)
        izq.pack(side="left")
        hora = datetime.datetime.now().hour
        if 5 <= hora < 12:
            saludo, emo = "Buenos días", "☀️"
        elif 12 <= hora < 19:
            saludo, emo = "Buenas tardes", "🌤️"
        else:
            saludo, emo = "Buenas noches", "🌙"
        self._texto_widget(izq, f"{saludo}, Dante {emo}", 16, TEXTO,
                           True, pad=(2, 0))
        hoy = datetime.date.today()
        self.lbl_fecha = self._texto_widget(
            izq, f"{DIAS[hoy.weekday()].capitalize()}, {hoy.day} de "
                 f"{MESES[hoy.month - 1]} {hoy.year}", 9, SUBTEXTO,
            pad=(2, 0))

        der = tk.Frame(fila, bg=FONDO)
        der.pack(side="right", fill="x", expand=True, padx=(12, 0))
        camp = self._field(der, alto=44)
        self.entrada_pregunta = self._entrada(camp)
        self._ph_pregunta = True
        self.entrada_pregunta.insert(0, "Escribe o habla con NEXUS…")
        self.entrada_pregunta.configure(fg=MUTED)
        self.entrada_pregunta.bind("<FocusIn>", self._foco_pregunta)
        self.entrada_pregunta.bind("<Return>", self._preguntar)
        self._boton(camp, "🎙", self._escuchar, ancho=34, alto=34, r=17,
                    fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc",
                    font=(FUENTE, 12), side="right")

        # stats: 3 tarjetas con ICONITOS HQ de verdad
        self.lbl_stats = {}
        stats = tk.Frame(f, bg=FONDO)
        stats.pack(fill="x", pady=(0, 8))
        for clave, (icono, color, titulo) in {
            "pend": ("tareas", AZUL, "Pendientes"),
            "hoy": ("check", MORADO, "Hechas hoy"),
            "hab": ("habitos", ACENTO, "Hábitos ✓"),
        }.items():
            card = tk.Canvas(stats, width=194, height=96, bg=FONDO,
                             highlightthickness=0)
            card.pack(side="left", padx=3)
            self._tarjeta(card, 1, 1, 192, 94, 12)
            img = _icono_img(icono, color, 16)
            if img is not None:
                card.create_image(28, 28, image=img)
            else:
                card.create_oval(18, 16, 38, 36, fill="", outline=color,
                                 width=1)
            num = card.create_text(18, 52, anchor="w", text="--",
                                   fill=TEXTO,
                                   font=("Consolas", 18, "bold"))
            card.create_text(18, 80, anchor="w", text=titulo.upper(),
                             fill=MUTED, font=("Consolas", 7, "bold"))
            self.lbl_stats[clave] = (card, num)

        # el GRÁFICO de barras: bonito y con datos de verdad
        self.grafico = tk.Canvas(f, width=607, height=148, bg=FONDO,
                                highlightthickness=0)
        self.grafico.pack(pady=(0, 6))
        self._valores_grafico = (0, 0, 0)

        self._texto_widget(
            f, "Di «oe nexus» o Ctrl+Alt+Espacio — todo corre "
               "100% local en tu PC", 9, SUBTEXTO, pad=(2, (4, 0)))

    def _construir_chat(self):
        """La vista de CHAT como el Troko: burbujas y campo abajo."""
        f = tk.Frame(self.zona, bg=FONDO)
        self._frames["Chat"] = f
        self.zona_chat = tk.Frame(f, bg=FONDO)
        self.zona_chat.pack(fill="both", expand=True, pady=(0, 4))
        fila = self._field(f, alto=44)
        self.entrada_chat = self._entrada(fila)
        self._ph_chat = True
        self.entrada_chat.insert(0, "Escribe con NEXUS…")
        self.entrada_chat.configure(fg=MUTED)
        self.entrada_chat.bind("<FocusIn>", self._foco_pregunta)
        self.entrada_chat.bind("<Return>", self._preguntar)
        self._boton(fila, "🎙", self._escuchar, ancho=34, alto=34, r=17,
                    fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc",
                    font=(FUENTE, 12), side="right")

    def _construir_tareas(self):
        f = tk.Frame(self.zona, bg=FONDO)
        self._frames["Tareas"] = f
        cab = tk.Frame(f, bg=FONDO)
        cab.pack(fill="x", pady=(0, 4))
        self.lbl_chip_tareas = self._badge(cab, "0 pendientes")
        # la BARRA DE PROGRESO de las tareas (gráfico bonito)
        self.prog = tk.Canvas(f, width=607, height=64, bg=FONDO,
                              highlightthickness=0)
        self.prog.pack(fill="x", pady=(0, 6))
        cols = tk.Frame(f, bg=FONDO)
        cols.pack(fill="both", expand=True)
        self.col_tareas = [tk.Frame(cols, bg=FONDO),
                           tk.Frame(cols, bg=FONDO)]
        for col in self.col_tareas:
            col.pack(side="left", fill="both", expand=True, padx=3)
        fila = self._field(f, alto=44)
        self.entrada_tarea = self._entrada(fila, f)
        self._boton(fila, "＋", self._añadir_tarea, ancho=34, alto=34,
                    r=17, fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc",
                    font=(FUENTE, 12, "bold"), side="right")
        self.lbl_hechas = self._texto_widget(f, "", 9, SUBTEXTO,
                                             pad=(2, (4, 0)))

    def _construir_habitos(self):
        f = tk.Frame(self.zona, bg=FONDO)
        self._frames["Hábitos"] = f
        cab = tk.Frame(f, bg=FONDO)
        cab.pack(fill="x", pady=(0, 4))
        self.lbl_chip_habitos = self._badge(cab, "0/0")
        self.zona_habitos = tk.Frame(f, bg=FONDO)
        self.zona_habitos.pack(fill="both", expand=True)
        fila = self._field(f, alto=44)
        self.entrada_habito = self._entrada(fila, f)
        self._boton(fila, "＋", self._nuevo_habito, ancho=34, alto=34,
                    r=17, fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc",
                    font=(FUENTE, 12, "bold"), side="right")
        self._texto_widget(f, "Formato: nombre : meta  (ej. «agua : 8»)",
                           9, SUBTEXTO, pad=(2, (4, 0)))

    def _construir_enfoque(self):
        f = tk.Frame(self.zona, bg=FONDO)
        self._frames["Enfoque"] = f
        fila = tk.Frame(f, bg=FONDO)
        fila.pack(fill="both", expand=True)
        lado = tk.Frame(fila, bg=FONDO)
        lado.pack(side="left", padx=(0, 16))
        self.ring = tk.Canvas(lado, width=200, height=200, bg=FONDO,
                             highlightthickness=0)
        self.ring.pack()
        self.lbl_crono = None
        der = tk.Frame(fila, bg=FONDO)
        der.pack(side="left", fill="both", expand=True)
        self._texto_widget(der, "Elige tu bloque", 12, TEXTO, True,
                           pad=(2, (6, 8)))
        malla = tk.Frame(der, bg=FONDO)
        malla.pack(fill="x", pady=(0, 8))
        for mins in (5, 15, 25, 50):
            self._boton(malla, f"  {mins} min  ",
                        lambda m=mins: self._iniciar_foco(m),
                        alto=30, side="left", fill=TARJETA,
                        hover=RAISE, fg=TEXTO,
                        font=(FUENTE, 9, "bold"))
        self._boton(der, "■  Parar", self._parar_foco, ancho=100,
                    alto=30, fill=TARJETA, hover=RAISE, fg=ROJO)
        self._texto_widget(der, "La cuenta vive aquí y en la isla.\n"
                              "Al terminar suena y te lo digo 🎉",
                           9, SUBTEXTO, pad=(2, (10, 0)))

    # ── acciones (mismas tools de voz) ──────────────────────────────
    def _cerrar(self):
        self.ocultar()
        try:
            self.ui.cerrar_panel()
        except Exception:
            pass

    def _escuchar(self):
        try:
            import audio
            audio.forzar()
        except Exception:
            pass

    # ── preguntas por TEXTO: escribe y Enter → cerebro + voz ───────
    def _foco_pregunta(self, evento=None):
        w = getattr(evento, "widget", None) or self.entrada_pregunta
        self._ultima_foco = w
        if w is self.entrada_chat:
            if self._ph_chat:
                self._ph_chat = False
                try:
                    w.delete(0, "end")
                    w.configure(fg=TEXTO)
                except Exception:
                    pass
        elif self._ph_pregunta:
            self._ph_pregunta = False
            try:
                w.delete(0, "end")
                w.configure(fg=TEXTO)
            except Exception:
                pass

    def _preguntar(self, evento=None):
        w = (getattr(evento, "widget", None) or self._ultima_foco
             or self.entrada_pregunta)
        try:
            texto = w.get().strip()
        except Exception:
            texto = ""
        ph = self._ph_chat if w is self.entrada_chat else self._ph_pregunta
        if not texto or ph:
            return
        try:
            w.delete(0, "end")
        except Exception:
            pass
        estado.set_texto("tu", texto)
        estado.set_aviso("💬 Ya voy…")
        chat("tu", texto)
        threading.Thread(target=self._procesar_pregunta, args=(texto,),
                         daemon=True).start()

    def _procesar_pregunta(self, texto):
        try:
            import llm
            import tts
            estado.set_modo("pensando")
            respuesta, _ = llm.respond(texto, [])
            plano = tts.plano(respuesta)
            estado.set_texto("jarvis", plano[:120])
            chat("nexus", plano[:200])
            estado.set_modo("hablando")
            tts.speak(respuesta)
            estado.set_aviso("💬 Respondido")
            estado.set_modo("esperando")
        except Exception as exc:
            try:
                estado.set_aviso(f"⚠️ {type(exc).__name__}")
                estado.set_modo("esperando")
            except Exception:
                pass

    def _pintar_chat(self):
        """Burbujas REDONDEADAS de verdad (canvas): tú en verde oscuro
        a la derecha, NEXUS en tarjeta a la izquierda."""
        for h in self.zona_chat.winfo_children():
            h.destroy()
        if not self.chat_msj:
            self._texto_widget(self.zona_chat,
                               "Habla o escribe con NEXUS ✨", 10,
                               SUBTEXTO, pad=(8, 10))
            return
        for quien, texto in self.chat_msj[-6:]:
            es_tu = quien == "tu"
            color = ACTIVO if es_tu else TARJETA
            fg = ACENTO if es_tu else TEXTO
            wtxt = max(120, min(540, 24 + int(len(texto) * 5.8)))
            lineas = max(1, math.ceil(len(texto) * 5.8
                                     / max(40.0, wtxt - 24)))
            alto = lineas * 17 + 12
            c = tk.Canvas(self.zona_chat, width=607, height=alto,
                          bg=FONDO, highlightthickness=0)
            c.pack(fill="x", pady=(3, 0))
            if es_tu:
                x0, x1 = 599 - wtxt, 599
            else:
                x0, x1 = 8, 8 + wtxt
            c.create_polygon(pts_rrect(x0, 1, x1, alto - 1, 12),
                             smooth=True, fill=color, outline="")
            c.create_text((x0 + x1) / 2, alto / 2, text=texto, fill=fg,
                          width=wtxt - 20, font=(FUENTE, 10),
                          justify="left")

    def _añadir_tarea(self):
        try:
            texto = self.entrada_tarea.get().strip()
        except Exception:
            texto = ""
        if texto:
            tools.add_task(texto)
            try:
                self.entrada_tarea.delete(0, "end")
            except Exception:
                pass
            self.sucio = True

    def _completar(self, texto):
        tools.complete_task(texto)
        self.sucio = True

    def _nuevo_habito(self):
        try:
            bruto = self.entrada_habito.get().strip()
        except Exception:
            bruto = ""
        if bruto:
            if ":" in bruto:
                nombre, meta = bruto.split(":", 1)
            else:
                nombre, meta = bruto, "1"
            tools.add_habit(nombre.strip(), meta.strip() or "1")
            try:
                self.entrada_habito.delete(0, "end")
            except Exception:
                pass
            self.sucio = True

    def _sumar_habito(self, nombre):
        tools.check_habit(nombre, 1)
        self.sucio = True

    def _borrar_habito(self, nombre):
        tools.delete_habit(nombre)
        self.sucio = True

    def _iniciar_foco(self, mins):
        tools.focus(mins)
        self.sucio = True

    def _parar_foco(self):
        tools.stop_timer()
        self.sucio = True

    # ── pintado de listas y contadores ─────────────────────────────
    def _limpiar(self, marco, efimeros):
        for h in marco.winfo_children():
            h.destroy()
        for b in efimeros:
            b.canvas._muerto = True
            if b in self._todos:
                self._todos.remove(b)
        efimeros.clear()

    def _fila_tarea(self, marco, texto):
        """Fila de tarea: tarjeta #1E1E1E + check redondito."""
        c = tk.Canvas(marco, width=296, height=40, bg=FONDO,
                      highlightthickness=0)
        c.pack(fill="x", pady=1)
        self._tarjeta(c, 1, 1, 295, 39, 10)
        b = self._boton(c, "✓", lambda t=texto: self._completar(t),
                        fondo=TARJETA, ancho=22, alto=22, r=11,
                        fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc")
        b.canvas.place(x=10, y=9)
        c.create_text(42, 20, anchor="w", text=texto, fill=TEXTO,
                      font=(FUENTE, 10), width=240)
        self._bt.append(b)

    def _pintar_tareas(self):
        datos = tools._leer_json(tools.TAREAS_PATH,
                                 {"pendientes": [], "hechas": []})
        pend = datos.get("pendientes", [])
        self.lbl_chip_tareas.config(text=f"{len(pend)} pendientes")
        for b in self._bt:
            b.canvas._muerto = True
            if b in self._todos:
                self._todos.remove(b)
        self._bt.clear()
        for col in self.col_tareas:
            for h in col.winfo_children():
                h.destroy()
        for i, t in enumerate(pend[:8]):
            self._fila_tarea(self.col_tareas[i % 2], t)
        if len(pend) > 8:
            self._texto_widget(self.col_tareas[0],
                               f"… y {len(pend) - 8} más",
                               9, SUBTEXTO, pad=(8, 0))
        if not pend:
            self._texto_widget(self.col_tareas[0],
                               "Todo limpio, señor ✨", 10, SUBTEXTO,
                               pad=(8, 6))
        hoy = datetime.date.today().isoformat()
        hechas = sum(1 for h in datos.get("hechas", [])
                     if h.get("fecha") == hoy)
        self.lbl_hechas.config(text=f"✓  {hechas} hechas hoy")
        # ── la BARRA DE PROGRESO (el gráfico de tus tareas) ──
        total = len(pend) + hechas
        c = self.prog
        c.delete("all")
        self._tarjeta(c, 1, 1, 606, 62, 12)
        c.create_text(18, 16, anchor="w", text="PROGRESO DE HOY",
                      fill=MUTED, font=("Consolas", 7, "bold"))
        frac = (hechas / total) if total else 0.0
        pct = int(round(frac * 100))
        c.create_text(18, 40, anchor="w",
                      text=f"{hechas} de {total} listas" if total
                      else "Sin tareas aún",
                      fill=TEXTO, font=(FUENTE, 10, "bold"))
        c.create_polygon(pts_rrect(150, 30, 540, 42, 6), smooth=True,
                         fill=PISTAS, outline="")
        if frac > 0:
            c.create_polygon(pts_rrect(150, 30, 150 + max(8, 390 * frac),
                                      42, 6), smooth=True,
                             fill=ACENTO, outline="")
        c.create_text(588, 36, anchor="e", text=f"{pct}%",
                      fill=ACENTO, font=("Consolas", 24, "bold"))

    def _fila_habito(self, marco, h):
        """Tarjeta ANCHA: nombre, racha 🔥, drops/barra, +1 y 🗑."""
        hecho = h.get("dias", {}).get(str(datetime.date.today()), 0)
        meta = h.get("meta", 1)
        racha = tools._racha_habito(h)
        c = tk.Canvas(marco, width=607, height=62, bg=FONDO,
                      highlightthickness=0)
        c.pack(fill="x", pady=3)
        self._tarjeta(c, 1, 1, 605, 60, 12)
        c.create_text(18, 20, anchor="w",
                      text=f"{'✅' if hecho >= meta else '⏳'} "
                           f"{h['nombre']}",
                      fill=TEXTO, font=(FUENTE, 10, "bold"))
        c.create_text(500, 20, anchor="w", text=f"🔥 {racha}",
                      fill=AMBAR, font=(FUENTE, 9, "bold"))
        if meta <= 12:
            for i in range(meta):
                x = 18 + i * 16
                c.create_oval(x, 34, x + 11, 47,
                             fill=AZUL if i < hecho else PISTAS,
                             outline="")
            c.create_text(18 + meta * 16 + 10, 41, anchor="w",
                          text=f"{hecho}/{meta}", fill=SUBTEXTO,
                          font=("Consolas", 9, "bold"))
        else:
            c.create_text(18, 41, anchor="w", text=f"{hecho} de {meta}",
                          fill=SUBTEXTO, font=(FUENTE, 9))
            frac = max(0.0, min(1.0, hecho / max(1, meta)))
            c.create_polygon(pts_rrect(100, 36, 430, 44, 4), smooth=True,
                             fill=PISTAS, outline="")
            if frac > 0:
                c.create_polygon(pts_rrect(100, 36, 100 + max(6, 330 * frac),
                                           44, 4), smooth=True,
                                 fill=ACENTO, outline="")
        b = self._boton(c, "+1", lambda n=h["nombre"]: self._sumar_habito(n),
                        fondo=TARJETA, ancho=28, alto=24, r=12,
                        fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc")
        b.canvas.place(x=571, y=18)
        t = self._boton(c, "🗑", lambda n=h["nombre"]: self._borrar_habito(n),
                        fondo=TARJETA, ancho=24, alto=24, r=12,
                        fill=TARJETA, hover=RAISE, hover_fg=ROJO)
        t.canvas.place(x=539, y=18)
        self._bh.append(t)
        self._bh.append(b)

    def _pintar_habitos(self):
        datos = tools._habitologia()
        self._limpiar(self.zona_habitos, self._bh)
        hoy = datetime.date.today()
        cumplidos = 0
        lista = list(datos.values())
        for h in lista:
            if h.get("dias", {}).get(str(hoy), 0) >= h.get("meta", 1):
                cumplidos += 1
        for h in lista[:4]:
            self._fila_habito(self.zona_habitos, h)
        if len(lista) > 4:
            self._texto_widget(self.zona_habitos,
                               f"… y {len(lista) - 4} más",
                               9, SUBTEXTO, pad=(8, 0))
        if not datos:
            self._texto_widget(self.zona_habitos,
                              "Sin hábitos aún.\nPrueba: «agua : 8»",
                              10, SUBTEXTO, pad=(8, 6))
        self.lbl_chip_habitos.config(text=f"{cumplidos}/{len(datos)}")

    def _pintar_grafico(self, valores):
        """El GRÁFICO DE BARRAS de Inicio (bonito y de verdad)."""
        self._valores_grafico = valores
        c = self.grafico
        c.delete("all")
        self._tarjeta(c, 1, 1, 606, 146, 14)
        c.create_text(20, 18, anchor="w", text="TU DÍA EN BARRAS",
                      fill=MUTED, font=("Consolas", 7, "bold"))
        datos = [("Pendientes", valores[0], AZUL),
                ("Hechas hoy", valores[1], MORADO),
                ("Hábitos ✓", valores[2], ACENTO)]
        maxv = max(1, max(v for _, v, _ in datos))
        base_y = 118
        for i, (titulo, val, color) in enumerate(datos):
            x = 60 + i * 180
            h = 12 + int(66 * val / maxv)
            c.create_polygon(pts_rrect(x, base_y - 78, x + 56, base_y, 8),
                             smooth=True, fill=PISTAS, outline="")
            if val > 0:
                c.create_polygon(pts_rrect(x, base_y - h, x + 56,
                                           base_y, 8), smooth=True,
                                 fill=color, outline="")
            c.create_text(x + 28, base_y - h - 10, text=str(val),
                          fill=TEXTO, font=("Consolas", 12, "bold"))
            c.create_text(x + 28, 134, text=titulo.upper(),
                          fill=MUTED, font=("Consolas", 7, "bold"))

    def _pintar_inicio(self):
        try:
            datos = tools._leer_json(tools.TAREAS_PATH,
                                     {"pendientes": [], "hechas": []})
            pend = len(datos.get("pendientes", []))
            hoy = datetime.date.today().isoformat()
            hechas = sum(1 for h in datos.get("hechas", [])
                         if h.get("fecha") == hoy)
            habitos = tools._habitologia()
            cumplidos = sum(
                1 for h in habitos.values()
                if h.get("dias", {}).get(str(datetime.date.today()), 0)
                >= h.get("meta", 1))
            for clave, n in (("pend", pend), ("hoy", hechas),
                             ("hab", cumplidos)):
                card, num = self.lbl_stats[clave]
                card.itemconfig(num, text=str(n))
            self._pintar_grafico((pend, hechas, cumplidos))
        except Exception:
            pass

    def _pintar_ring(self, crono):
        """Anillo GRANDE con tarjeta, GLOW verde y progreso lima."""
        seg = seg_de_crono(crono) if crono else None
        c = self.ring
        c.delete("all")
        self._tarjeta(c, 2, 2, 198, 198, 14)
        c.create_oval(40, 40, 160, 160, outline=PISTAS, width=10)
        if seg is not None:
            total = tools._FOCO.get("total") or seg
            frac = max(0.0, min(1.0, seg / total))
            c.create_arc(35, 35, 165, 165, start=90,
                         extent=-int(360 * frac), style="arc",
                         outline=GLOW, width=16)
            c.create_arc(40, 40, 160, 160, start=90,
                         extent=-int(360 * frac), style="arc",
                         outline=ACENTO, width=10)
        else:
            c.create_arc(40, 40, 160, 160, start=90, extent=359,
                         style="arc", outline=LINEA, width=10)
        self.lbl_crono = c.create_text(100, 100, text=crono or "—",
                                       fill=TEXTO,
                                       font=("Consolas", 16, "bold"))

    # ── refresco periódico ──────────────────────────────────────────
    def _refrescar(self):
        if not self.vivo:
            return
        try:
            e = estado.get()
            modo = e.get("modo", "esperando")
            self.lbl_punto.config(fg=PUNTO_MODO.get(modo, SUBTEXTO))
            self.lbl_modo.config(text=STATUS.get(modo, modo))
            crono = e.get("crono") or ""
            if "Enfoque" in self._frames:
                self._pintar_ring(crono)
            if self.sucio:
                if "Tareas" in self._frames:
                    self._pintar_tareas()
                if "Hábitos" in self._frames:
                    self._pintar_habitos()
                if "Inicio" in self._frames:
                    self._pintar_inicio()
                self.sucio = False
            with _CHAT_LOCK:
                nuevos = list(_CHAT_PENDIENTE)
                _CHAT_PENDIENTE.clear()
            if nuevos:
                self.chat_msj.extend(nuevos)
                self._pintar_chat()
            borrador = getattr(tools, "BORRADOR_CORREO", None)
            if borrador:
                tools.BORRADOR_CORREO = None
                try:
                    self._abrir_correo(borrador)
                except Exception:
                    pass
            if self._correo_cerrar:
                self._correo_cerrar = False
                self._cerrar_correo()
        except Exception:
            pass
        try:
            self.marco.after(500, self._refrescar)
        except Exception:
            self.vivo = False

    # ── navegación y vida del panel ─────────────────────────────────
    def mostrar_seccion(self, sec):
        self._asegurar_seccion(sec)
        self.seccion = sec
        for clave, fr in self._frames.items():
            fr.pack_forget()
        self._frames[sec].pack(fill="both", expand=True)
        for clave, b in self._nav.items():
            b.marcar(clave == sec)
        try:
            self.lbl_titulo.config(text=sec)
            self.lbl_subtitulo.config(
                text=SUBTITULOS.get(sec, ""))
        except Exception:
            pass
        self.sucio = True

    # ── CORREO: el diálogo para poner la dirección, editar y enviar ─
    def _abrir_correo(self, borrador):
        """Ventanita del correo: la dirección se ESCRIBE (dictarla falla)."""
        self._cerrar_correo()
        win = tk.Toplevel(self.ui.raiz)
        self._correo_win = win
        win.title("NEXUS — correo nuevo")
        win.configure(bg=FONDO)
        try:
            win.geometry("440x340+420+180")
            win.attributes("-topmost", True)
        except Exception:
            pass
        marco = tk.Frame(win, bg=FONDO)
        marco.pack(fill="both", expand=True, padx=14, pady=10)
        self._texto_widget(marco, "📧 Correo nuevo", 12, TEXTO, True,
                           pad=(0, 2))
        self._texto_widget(marco, "Para (escribe la dirección)", 8,
                           SUBTEXTO, pad=(0, (6, 0)))
        self.ent_correo_para = tk.Entry(marco, bg=TARJETA, fg=TEXTO,
                                        insertbackground=ACENTO, bd=0,
                                        relief="flat", font=(FUENTE, 10))
        self.ent_correo_para.pack(fill="x", ipady=6)
        if borrador.get("to"):
            self.ent_correo_para.insert(0, borrador["to"])
        self._texto_widget(marco, "Asunto", 8, SUBTEXTO, pad=(0, (6, 0)))
        self.ent_correo_asunto = tk.Entry(marco, bg=TARJETA, fg=TEXTO,
                                         insertbackground=ACENTO, bd=0,
                                         relief="flat", font=(FUENTE, 10))
        self.ent_correo_asunto.pack(fill="x", ipady=6)
        self.ent_correo_asunto.insert(0, borrador.get("subject", ""))
        self._texto_widget(marco, "Mensaje (edítalo si quieres)", 8,
                           SUBTEXTO, pad=(0, (6, 0)))
        self.txt_correo = tk.Text(marco, bg=TARJETA, fg=TEXTO, bd=0,
                                  relief="flat", font=(FUENTE, 10),
                                  padx=10, pady=8, height=6)
        self.txt_correo.pack(fill="both", expand=True)
        self.txt_correo.insert("1.0", borrador.get("body", ""))
        botones = tk.Frame(marco, bg=FONDO)
        botones.pack(fill="x", pady=(8, 0))
        self._boton(botones, "Enviar 📧", self._enviar_correo, ancho=110,
                    alto=30, fill=ACENTO, fg=ACENTO_TX, hover="#7dd3fc",
                    font=(FUENTE, 9, "bold"), side="left")
        self._boton(botones, "Cancelar", self._cerrar_correo, ancho=90,
                    alto=30, fill=TARJETA, hover=RAISE, side="left")
        estado.set_aviso("📧 Revisa el correo…")

    def _cerrar_correo(self):
        try:
            if self._correo_win is not None:
                self._correo_win.destroy()
        except Exception:
            pass
        self._correo_win = None

    def _enviar_correo(self):
        try:
            para = self.ent_correo_para.get().strip()
        except Exception:
            para = ""
        if "@" not in para:
            estado.set_aviso("📧 Falta el destinatario")
            return
        try:
            asunto = self.ent_correo_asunto.get().strip()
            cuerpo = self.txt_correo.get("1.0", "end-1c")
        except Exception:
            asunto, cuerpo = "", ""
        estado.set_aviso("📧 Enviando…")  # antes del hilo: no se pisa el final
        threading.Thread(target=self._mandar_correo,
                         args=(para, asunto, cuerpo), daemon=True).start()

    def _mandar_correo(self, para, asunto, cuerpo):
        """Hilo: SMTP puede tardar; el aviso cuenta cómo fue."""
        resultado = tools.send_email(para, asunto, cuerpo)
        if resultado.startswith("Correo enviado"):
            estado.set_aviso("📧 Enviado")
            chat("nexus", f"📧 Correo enviado a {para}")
            self._correo_cerrar = True
        else:
            estado.set_aviso("⚠️ " + resultado[:40])

    def mostrar(self):
        self.sucio = True
        self.visible = True

    def ocultar(self):
        self.visible = False

    def dentro(self, px, py):
        """¿El puntero está sobre la ventana desplegada? (hover)."""
        if px is None or py is None:
            return False
        try:
            return self.ui._en_rect(px, py, self.ui._rect_ventana())
        except Exception:
            return False


# ── chat: el hilo de la VOZ deja aquí sus líneas (thread-safe) ──────
_CHAT_LOCK = threading.Lock()
_CHAT_PENDIENTE = []


def chat(quien, texto):
    """La voz y la UI mandan aquí la conversación; el panel la pinta."""
    with _CHAT_LOCK:
        _CHAT_PENDIENTE.append((quien, str(texto or "")))


# ── la puerta del panel: la isla manda (hover y clic) ────────────────
_PANEL = None


def _asegurar(ui):
    global _PANEL
    if _PANEL is None or not _PANEL.vivo:
        _PANEL = Panel(ui)
    return _PANEL


def abrir(ui):
    """HOVER/clic → el panel se despliega desde la isla."""
    _asegurar(ui).mostrar()
    ui.abrir_panel()


def cerrar():
    """El cursor salió (o clic/Esc) → se pliega solito."""
    if _PANEL is not None and _PANEL.visible:
        _PANEL.ocultar()
        try:
            _PANEL.ui.cerrar_panel()
        except Exception:
            pass


def dentro(px, py):
    if _PANEL is None or not _PANEL.vivo:
        return False
    return _PANEL.dentro(px, py)


def esta_visible():
    return _PANEL is not None and _PANEL.vivo and _PANEL.visible


def alternar(ui):
    """Clic en la isla → abre/cierra."""
    if esta_visible():
        cerrar()
    else:
        abrir(ui)
