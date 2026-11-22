"""NEXUS — interfaz WEB (pywebview + Edge WebView2).

HTML/CSS/SVG de verdad: anti-aliasing perfecto (adiós dientes de
sierra), animaciones a 60 fps del navegador y libertad gráfica
total. El notch y el panel viven en web/nexus.html; este módulo es
el puente: expone las herramientas a JavaScript y ajusta la
ventana (el notch pegado al borde superior o a la barra de tareas,
según la pestaña Ajustes; el panel se despliega del lado contrario).
"""
import copy
import ctypes
import json
import os
import re
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import estado

# ── nitidez DPI: sin esto Windows estira la ventana como bitmap ────
try:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4))          # PerMonitorV2
    except Exception:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

ANCHO = 800                     # tamaño base (referencia; el real sale de _tam_panel())
ALTO_NOTCH = 88                 # ventana del notch: FIJA y holgada para que la
                                # pastilla escalada (hasta 220%) no se corte
ALTO_PANEL = 500                # alto base del panel (el real sale de _tam_panel())
ANCHO_NOTCH = 720               # idem en ancho (la isla escala con notch_s)

CHAT = []                       # la conversación, para el panel web
_ventana = None                 # la ventana del notch
_ventana_panel = None           # la ventana del panel (oculta/mostrar)
_panel_on = {"valor": False}    # ¿el panel se ve?
_latido = [time.monotonic()]    # «siguen con el mouse encima»: vivo
_IR_A = {"sec": "", "t": 0.0}   # el engranaje manda: abrir en Ajustes
_PID = os.getpid()              # mis ventanas, no las de otra copia
_AJUSTES_PATH = Path.home() / "nexus_ajustes.json"

import version                  # APP_VERSION: la versión del .exe
_UPDATE = {"hay": False, "actual": version.APP_VERSION}   # último chequeo
_NOVEDADES = None               # cola del pipeline (para avisar updates)


def _ruta_base():
    """Carpeta raíz de recursos: en el .exe onefile los datos viven en
    el directorio temporal de desempaquetado (sys._MEIPASS)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

# ── look de la interfaz (pestaña Ajustes → «Mascota y apariencia») ──
# Colores de la mascota (degradado del cuerpo), de los ojos, del notch y
# el acento (brillos/bordes). Los cosméticos van por slot con valores de
# lista blanca para que un JSON raro nunca rompa el SVG.
_COSM_OPTS = {"sombrero": ("ninguno", "gorra", "corona", "copa", "orejas"),
              "gafas": ("ninguno", "sol", "redondas", "monoculo"),
              "extra": ("ninguno", "mono", "bigotes", "corbata"),
              "mano": ("ninguno",)}
_PNG_MAX = 220_000          # dataURL tope por PNG subido (se reescala a 128 px)
_ANIM_OPTS = ("clasico", "rebote", "flotar", "pulso", "turbo", "lento")
_FORMAS = ("original", "redonda", "pildora", "cuadrada", "diamante")


def _clamp_num(n, lo, hi, base):
    try:
        return round(max(lo, min(hi, float(n))), 1)
    except Exception:
        return base


def _norm_xy_s(v, s_lo, s_hi, lim=400):
    """{x, y, s} saneado: x/y en ±lim (sin límites prácticos), s en
    [s_lo, s_hi], default centrado."""
    v = v if isinstance(v, dict) else {}
    return {"x": _clamp_num(v.get("x"), -lim, lim, 0.0),
            "y": _clamp_num(v.get("y"), -lim, lim, 0.0),
            "s": _clamp_num(v.get("s"), s_lo, s_hi, 1.0)}


def _norm_ajuste(v):
    """Ajuste fino de cada cosmético (unidades del viewBox 100×66):
    {slot: {"x", "y", "s", "r"}} — lo que se arrastra en la vista previa.
    Sin límites: x/y ±400, s 0.05..10. Basura → default (centrado, 1×)."""
    v = v if isinstance(v, dict) else {}
    out = {}
    for k in _COSM_OPTS:
        a = _norm_xy_s(v.get(k), 0.05, 10.0)
        a["r"] = _clamp_num((v.get(k) or {}).get("r"), -180, 180, 0.0)
        out[k] = a
    return out


_TEMA_DEF = {"cuerpo": "#F8F4E8", "cuerpo2": "#E1D8C1", "ojos": "#141414",
             "notch": "#05070d", "acento": "#38bdf8",
             "cosm_color": {"sombrero": "", "gafas": "", "extra": "",
                            "mano": ""},
             "png": {"sombrero": "", "gafas": "", "extra": "", "mano": ""},
             "ajuste": _norm_ajuste(None),
             # OJO: la posición/tamaño de NEXUS es "cuerpo_t" — «cuerpo» ya
             # es el COLOR del cuerpo (una clave duplicada hacía que el dict
             # pisara el color y el degradado quedara negro arriba)
             "cuerpo_t": {"x": 0.0, "y": 0.0, "s": 1.0},
             "notch_s": 1.0,                          # escala de la pastilla
             "anim": "clasico",                       # set de animaciones
             "forma": "original",                     # forma de la mascota
             "panel": "#0a1120", "card": "#101a2e",   # más colores custom
             "borde": "#1e3a5f", "texto": "#f8fafc",
             "cosmeticos": {"sombrero": "ninguno", "gafas": "ninguno",
                            "extra": "ninguno", "mano": "ninguno"}}


def _norm_hex_opt(v):
    """#RRGGBB o vacío («» = seguir al acento). Cualquier otra cosa → «»."""
    if isinstance(v, str) and (v == "" or re.fullmatch(r"#[0-9a-fA-F]{6}", v)):
        return v.lower() if v else ""
    return ""


def _norm_png(v):
    """Solo dataURL de imagen pequeña (el JS la reescala a 128 px antes
    de guardar); cualquier otra cosa → «»."""
    if (isinstance(v, str) and len(v) <= _PNG_MAX
            and re.match(r"data:image/(png|webp);base64,[A-Za-z0-9+/=]+$", v)):
        return v
    return ""


def _norm_presets(p):
    """[{nombre, tema}] saneado: máx. 24, nombre ≤ 30, sin duplicados."""
    if not isinstance(p, list):
        return []
    vistos, out = set(), []
    for x in p[:24]:
        if isinstance(x, dict) and isinstance(x.get("nombre"), str):
            nom = x["nombre"].strip()[:30]
            if nom and nom not in vistos:
                vistos.add(nom)
                out.append({"nombre": nom, "tema": _norm_tema(x.get("tema"))})
    return out


def _norm_color(v, base):
    """Solo se aceptan #RRGGBB; cualquier otra cosa cae al default."""
    return v if (isinstance(v, str)
                 and re.fullmatch(r"#[0-9a-fA-F]{6}", v)) else base


def _norm_tema(t):
    """Tema válido y completo: mezcla lo recibido con los defaults.
    cosm_color: color independiente por slot («» = seguir al acento).
    png: dataURL del cosmético subido por slot («» = usar el dibujado)."""
    t = t if isinstance(t, dict) else {}
    cosm = t.get("cosmeticos")
    cosm = cosm if isinstance(cosm, dict) else {}
    cc = t.get("cosm_color")
    cc = cc if isinstance(cc, dict) else {}
    png = t.get("png")
    png = png if isinstance(png, dict) else {}
    return {"cuerpo": _norm_color(t.get("cuerpo"), _TEMA_DEF["cuerpo"]),
            "cuerpo2": _norm_color(t.get("cuerpo2"), _TEMA_DEF["cuerpo2"]),
            "ojos": _norm_color(t.get("ojos"), _TEMA_DEF["ojos"]),
            "notch": _norm_color(t.get("notch"), _TEMA_DEF["notch"]),
            "acento": _norm_color(t.get("acento"), _TEMA_DEF["acento"]),
            "panel": _norm_color(t.get("panel"), _TEMA_DEF["panel"]),
            "card": _norm_color(t.get("card"), _TEMA_DEF["card"]),
            "borde": _norm_color(t.get("borde"), _TEMA_DEF["borde"]),
            "texto": _norm_color(t.get("texto"), _TEMA_DEF["texto"]),
            "anim": t.get("anim") if t.get("anim") in _ANIM_OPTS else "clasico",
            "forma": t.get("forma") if t.get("forma") in _FORMAS else "original",
            "cosm_color": {k: _norm_hex_opt(cc.get(k)) for k in _COSM_OPTS},
            "png": {k: _norm_png(png.get(k)) for k in _COSM_OPTS},
            "ajuste": _norm_ajuste(t.get("ajuste")),
            # migración: en temas viejos la posición vivía en "cuerpo" (dict)
            "cuerpo_t": _norm_xy_s(
                t.get("cuerpo_t") if t.get("cuerpo_t") is not None
                else (t.get("cuerpo") if isinstance(t.get("cuerpo"), dict) else None),
                0.1, 10.0),
            "notch_s": _clamp_num(t.get("notch_s"), 0.3, 2.2, 1.0),
            "cosmeticos": {k: (cosm.get(k) if cosm.get(k) in opts
                               else "ninguno")
                           for k, opts in _COSM_OPTS.items()}}


# Tamaños del panel («espacio de trabajo»): (ancho, alto) de la ventana.
# OJO: el tamaño solo se fija AL CREAR la ventana — un resize en caliente
# rompe la transparencia de WebView2 (por eso las ventanas son fijas).
_TAM_PANEL = {"compacto": (800, 500), "grande": (1080, 600),
              "ancho": (1320, 640)}

_AJ = {"pos": "arriba", "monitor": 0,   # lo que salva la pestaña Ajustes
       "tema": _norm_tema(None), "presets": [], "tam": "grande",
       "hpos": "centro"}                # centro | izquierda | derecha
_HPOS_OK = ("centro", "izquierda", "derecha")


def _tam_panel():
    return _TAM_PANEL.get(_AJ.get("tam"), _TAM_PANEL["grande"])


def _patch_chat():
    """La voz y la UI mandan a panel.chat; aquí también queda una copia
    para que la interfaz web la pinte."""
    import panel
    original = panel.chat

    def chat(quien, texto):
        CHAT.append({"quien": quien, "texto": str(texto or "")})
        del CHAT[:-200]
        try:
            original(quien, texto)
        except Exception:
            pass
    panel.chat = chat


def _escala():
    """DPI/96 REAL: pywebview escala la ventana por el DPI de SU
    monitor; GetDpiForSystem puede dar otro valor (aquí 96 vs 120) y
    con él la ventana quedaba mal apoyada (p.ej. 11 px cortados bajo
    la pantalla en modo barra)."""
    try:
        hwnd = _hwnd("NEXUS")
        if hwnd:
            dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
            if dpi:
                return dpi / 96.0
    except Exception:
        pass
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0


def _leer_ajustes():
    """Lo guardado en ~/nexus_ajustes.json (posiciones, menú de voces
    y overrides de config). 'abajo' (el nombre antiguo) hoy es 'barra'."""
    datos = {}
    try:
        with open(_AJUSTES_PATH, encoding="utf-8") as f:
            leido = json.load(f)
        if isinstance(leido, dict):
            datos = leido
    except Exception:
        pass
    datos["pos"] = ("barra" if datos.get("pos") == "abajo"
                   else datos.get("pos", "arriba"))
    if not isinstance(datos.get("monitor"), int) or datos.get("monitor", 0) < 0:
        datos["monitor"] = 0
    if "voces" in datos:
        datos["voces"] = [v for v in (_norm_voz(x) for x in datos["voces"])
                          if v]
    else:
        datos["voces"] = _voces_base()
    datos["tema"] = _norm_tema(datos.get("tema"))
    datos["presets"] = _norm_presets(datos.get("presets"))
    if datos.get("tam") not in _TAM_PANEL:
        datos["tam"] = "grande"
    if datos.get("hpos") not in _HPOS_OK:
        datos["hpos"] = "centro"
    return datos


def _escribir_ajustes(datos):
    try:
        with open(_AJUSTES_PATH, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _norm_voz(v):
    """{'nombre','id'} válido (id obligatorio) o None."""
    if isinstance(v, dict) and isinstance(v.get("id"), str):
        vid = v["id"].strip()
        if vid:
            nombre = str(v.get("nombre") or "").strip() or vid[:8]
            return {"nombre": nombre, "id": vid}
    return None


def _voces_base():
    """Las voces de arranque (config.VOCES_FISH): el menú inicial,
    hasta que guardes tus propios cambios en la pestaña Ajustes."""
    try:
        import config
        base = []
        for nombre, vid in getattr(config, "VOCES_FISH", {}).items():
            v = _norm_voz({"nombre": nombre, "id": vid})
            if v:
                base.append(v)
        return base
    except Exception:
        return []


_AJ.update(_leer_ajustes())


class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                ("r", ctypes.c_long), ("b", ctypes.c_long)]


def _monitores():
    """[{i, nombre, pantalla(l,t,r,b), trabajo(l,t,r,b), principal}] —
    en el orden que da Windows (físico, puro user32)."""
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("rcMonitor", _RECT), ("rcWork", _RECT),
                    ("dwFlags", wintypes.DWORD)]
    lista = []

    def cb(hmon, hdc, lprect, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            pantalla = (mi.rcMonitor.l, mi.rcMonitor.t,
                        mi.rcMonitor.r, mi.rcMonitor.b)
            trabajo = (mi.rcWork.l, mi.rcWork.t,
                       mi.rcWork.r, mi.rcWork.b)
            lista.append({
                "i": len(lista),
                "nombre": "Monitor " + str(len(lista) + 1),
                "res": (f"{pantalla[2] - pantalla[0]}"
                        f"×{pantalla[3] - pantalla[1]}"),
                "pantalla": pantalla, "trabajo": trabajo,
                "principal": bool(mi.dwFlags & 1)})
        return True

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE,
                                   wintypes.HDC, wintypes.LPRECT,
                                   wintypes.LPARAM)
    if not lista:
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, enum_proc(cb), 0)
    if not lista:                      # sin EnumDisplayMonitores:
        w = ctypes.windll.user32.GetSystemMetrics(0)   # pantalla única
        h = ctypes.windll.user32.GetSystemMetrics(1)
        lista.append({"i": 0, "nombre": "Monitor 1", "res": f"{w}×{h}",
                      "pantalla": (0, 0, w, h), "trabajo": (0, 0, w, h),
                      "principal": True})
    return lista


def _monitor_elegido():
    """El monitor que pidió la pestaña Ajustes (el principal si no)."""
    mons = _monitores()
    for m in mons:
        if m["i"] == _AJ["monitor"]:
            return m
    for m in mons:
        if m["principal"]:
            return m
    return mons[0]


_HWND_CACHE = {}   # título → hwnd (las ventanas viven todo el proceso;
                   # sin caché el vigía corría EnumWindows sobre TODAS las
                   # ventanas del sistema 2 veces cada 120 ms = CPU fija)


def _hwnd(titulo):
    """HWND de MI ventana 'titulo' (busca primero entre las de ESTE
    proceso; si otra copia de NEXUS corre, no me roba sus ventanas).
    Cacheado: se verifica con IsWindow + GetWindowTextW (barato) en vez
    de re-enumerar todas las ventanas en cada llamada."""
    h = _HWND_CACHE.get(titulo)
    if h and ctypes.windll.user32.IsWindow(h):
        buf = ctypes.create_unicode_buffer(64)
        if (ctypes.windll.user32.GetWindowTextW(h, buf, 64)
                and buf.value == titulo):
            return h
        _HWND_CACHE.pop(titulo, None)   # ya no es mi ventana: re-buscar
    hallados = []

    def cb(h, lparam):
        buf = ctypes.create_unicode_buffer(64)
        if ctypes.windll.user32.GetWindowTextW(h, buf, 64):
            if buf.value == titulo:
                pid = wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(
                    h, ctypes.byref(pid))
                if pid.value == _PID:
                    hallados.append(h)
        return True

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                   wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(enum_proc(cb), 0)
    if hallados:
        _HWND_CACHE[titulo] = hallados[0]
        return hallados[0]
    h = ctypes.windll.user32.FindWindowW(None, titulo)
    # el fallback puede ser de OTRA copia de NEXUS: solo lo cacheo si
    # el PID es el mío (si no, cada llamada re-verifica y no estorba)
    if h:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == _PID:
            _HWND_CACHE[titulo] = h
    return h


class Api:
    """Todo lo que JavaScript puede pedirle a Python."""

    # ── estado del notch ───────────────────────────────────────────
    def estado(self):
        try:                          # la cola del pipeline no crece
            import queue
            while True:
                self._novedades.get_nowait()
        except Exception:
            pass
        e = estado.get()
        # el engranaje manda «ve a Ajustes»: válido 2 s (un par de
        # sondeos del panel) para que el salto se dispare una vez
        ira = _IR_A["sec"] if time.monotonic() - _IR_A["t"] < 2.0 else ""
        return {"modo": e["modo"], "aviso": e["aviso"],
                "crono": e["crono"], "tu": e["tu"], "jarvis": e["jarvis"],
                "pos": _AJ["pos"], "ir_a": ira,
                "tam": _AJ.get("tam", "grande"),
                "hpos": _AJ.get("hpos", "centro"),
                "version": version.APP_VERSION,
                "update": _UPDATE if _UPDATE.get("hay") else None,
                "tema": _AJ.get("tema") or _TEMA_DEF}

    def limpiar_aviso(self):
        estado.set_aviso("")
        return "ok"

    # ── datos del panel ────────────────────────────────────────────
    def datos(self, completo=True):
        import datetime
        import tools
        datos = tools._leer_json(
            tools.TAREAS_PATH, {"pendientes": [], "hechas": []})
        hoy = datetime.date.today().isoformat()
        hechas = [h.get("texto", "") if isinstance(h, dict) else str(h)
                  for h in datos.get("hechas", [])
                  if (h.get("fecha") if isinstance(h, dict) else hoy) == hoy]
        habitos = []
        for clave, h in tools._habitologia().items():
            habitos.append({
                "clave": clave,
                "nombre": h.get("nombre", clave),
                "meta": int(h.get("meta", 1)),
                "hoy": int(h.get("dias", {}).get(hoy, 0)),
                "racha": tools._racha_habito(h),
            })
        return {"tareas": {"pendientes": datos.get("pendientes", []),
                           "hechas": hechas},
                "habitos": habitos,
                "chat": CHAT}

    # ── tareas ─────────────────────────────────────────────────────
    def anadir_tarea(self, texto):
        import tools
        return tools.add_task(str(texto or ""))

    def completar_tarea(self, indice):
        import tools
        return tools.complete_task(str(int(indice) + 1))

    def descompletar_tarea(self, indice):
        import tools
        hechas = self._hechas_hoy()
        i = int(indice)
        if 0 <= i < len(hechas):
            return tools.uncomplete_task(hechas[i])
        return "No encontré esa tarea hecha."

    def _hechas_hoy(self):
        """Las hechas de HOY (las mismas que ve la UI: mismos índices)."""
        import datetime
        import tools
        datos = tools._leer_json(
            tools.TAREAS_PATH, {"pendientes": [], "hechas": []})
        hoy = datetime.date.today().isoformat()
        return [h.get("texto", "") if isinstance(h, dict) else str(h)
                for h in datos.get("hechas", [])
                if (h.get("fecha") if isinstance(h, dict) else hoy) == hoy]

    def borrar_tarea(self, indice, hecha=False):
        import tools
        if hecha:
            hechas = self._hechas_hoy()
            i = int(indice)
            if 0 <= i < len(hechas):
                return tools.delete_task(hechas[i])
            return "No encontré esa tarea hecha."
        datos = tools._leer_json(
            tools.TAREAS_PATH, {"pendientes": [], "hechas": []})
        pend = datos.get("pendientes", [])
        i = int(indice)
        if 0 <= i < len(pend):
            return tools.delete_task(pend[i])
        return "No encontré esa tarea."

    # ── hábitos ────────────────────────────────────────────────────
    def anadir_habito(self, texto):
        """«agua 8» → hábito agua con meta 8; «leer» → meta 1."""
        import tools
        partes = str(texto or "").strip().split()
        meta = 1
        if len(partes) > 1:
            try:
                meta = int(float(partes[-1]))
                partes = partes[:-1]
            except ValueError:
                pass
        return tools.add_habit(" ".join(partes), meta)

    def registrar_habito(self, clave):
        import tools
        return tools.check_habit(str(clave))

    def quitar_habito(self, clave):
        import tools
        return tools.uncheck_habit(str(clave))

    def borrar_habito(self, clave):
        import tools
        return tools.delete_habit(str(clave))

    # ── conversación y voz ──────────────────────────────────────────
    def preguntar(self, texto):
        texto = str(texto or "").strip()
        if not texto:
            return "ok"
        import panel
        panel.chat("tu", texto)

        def hilo():
            try:
                import llm
                import tts
                estado.set_modo("pensando")
                respuesta, _ = llm.respond(texto, [])
                limpio = tts.plano(respuesta)
                estado.set_texto("jarvis", limpio)
                panel.chat("nexus", limpio)
                tts.speak(respuesta)
            except Exception as exc:
                panel.chat("nexus", f"Tuve un problema: {exc}")
            finally:
                estado.set_modo("esperando")
        threading.Thread(target=hilo, daemon=True).start()
        return "ok"

    def mic(self):
        """El botón 🎙: despierta el oído como el hotkey."""
        try:
            import audio
            audio.forzar()
        except Exception:
            pass
        return "ok"

    # ── enfoque ─────────────────────────────────────────────────────
    def enfocar(self, minutos):
        import tools
        return tools.focus(float(minutos))

    def parar_timer(self):
        import tools
        return tools.stop_timer()

    # ── ventana ─────────────────────────────────────────────────────
    def abrir_panel(self):
        """Muestra el panel SIN robar el foco de la app activa
        (SW_SHOWNOACTIVATE=4); el clic en el input le da el foco."""
        _mostrar_panel()
        return "ok"

    def cerrar_panel(self):
        _ocultar_panel()
        return "ok"

    def panel_latido(self):
        """«Sigue habiendo actividad»: no cerrar el panel."""
        _latido[0] = time.monotonic()
        return "ok"

    # ── ajustes ────────────────────────────────────────────────────
    def ajustes(self):
        """Todo lo que alimenta la pestaña Ajustes: ubicación,
        monitores y los valores actuales del cerebro y la voz."""
        import config
        mons = _monitores()
        return {"pos": _AJ["pos"], "monitor": _AJ["monitor"],
                "monitores": [{"i": m["i"], "nombre": m["nombre"],
                               "res": m["res"], "principal": m["principal"],
                               "activo": m["i"] == _AJ["monitor"]}
                              for m in mons],
                "llm_api_key": getattr(config, "LLM_API_KEY", ""),
                "llm_model": getattr(config, "LLM_MODEL", ""),
                "fish_api_key": getattr(config, "FISH_API_KEY", ""),
                "voces": self._voces_ui(),
                "tam": _AJ.get("tam", "grande"),
                "hpos": _AJ.get("hpos", "centro"),
                "version": version.APP_VERSION,
                "update": _UPDATE if _UPDATE.get("hay") else None,
                "presets": copy.deepcopy(_AJ.get("presets", []))}

    def tema(self):
        """El look actual (mascota, notch, acento, cosméticos) para que
        las dos ventanas (notch y panel) lo pinten al arrancar."""
        import copy
        return copy.deepcopy(_AJ.get("tema") or _TEMA_DEF)

    def guardar_tema(self, tema):
        """Pestaña Ajustes → «Mascota y apariencia»: guarda el look en
        ~/nexus_ajustes.json y queda activo YA en las dos ventanas (el
        notch lo recoge en su sondeo de estado). Se sanea todo: colores
        #RRGGBB y cosméticos de la lista blanca."""
        t = _norm_tema(tema)
        datos = _leer_ajustes()
        datos["tema"] = t
        _escribir_ajustes(datos)
        _AJ["tema"] = t
        estado.set_aviso("🎉 Look actualizado")
        return "ok"

    def guardar_preset(self, nombre):
        """Pestaña Ajustes → «＋ Guardar actual»: el look VIGENTE queda
        como preset con nombre (si el nombre ya existía, se reemplaza).
        Devuelve la lista actualizada de presets del usuario."""
        nom = str(nombre or "").strip()[:30]
        if not nom:
            return _AJ.get("presets", [])
        presets = [p for p in _AJ.get("presets", []) if p["nombre"] != nom]
        presets.append({"nombre": nom,
                        "tema": copy.deepcopy(_AJ.get("tema") or _TEMA_DEF)})
        presets = _norm_presets(presets)
        datos = _leer_ajustes()
        datos["presets"] = presets
        _escribir_ajustes(datos)
        _AJ["presets"] = presets
        estado.set_aviso(f"🎉 Preset «{nom}» guardado")
        return copy.deepcopy(presets)

    def borrar_preset(self, nombre):
        """Quita un preset del usuario. Devuelve la lista actualizada."""
        nom = str(nombre or "").strip()
        antes = _AJ.get("presets", [])
        presets = [p for p in antes if p["nombre"] != nom]
        if len(presets) != len(antes):
            datos = _leer_ajustes()
            datos["presets"] = presets
            _escribir_ajustes(datos)
            _AJ["presets"] = presets
            estado.set_aviso("🎉 Preset eliminado")
        return copy.deepcopy(presets)

    def fijar_posicion(self, pos):
        """'arriba': notch pegado al borde superior, menú hacia abajo.
        'barra': integrado en la barra de tareas (solo ojos y estado),
        menú hacia arriba. Se aplica YA y queda en el JSON."""
        _AJ["pos"] = "barra" if str(pos) in ("barra", "abajo") else "arriba"
        datos = _leer_ajustes()
        datos["pos"] = _AJ["pos"]
        _escribir_ajustes(datos)
        _reposicionar()
        return "ok"

    # ── actualizaciones (solo con sentido corriendo como .exe) ─────
    def estado_update(self):
        return dict(_UPDATE)

    def buscar_update(self):
        """Busca un nexus.exe más nuevo (carpeta del exe, Descargas,
        manifiesto remoto) y devuelve el resultado."""
        try:
            import updater
            r = updater.buscar_update()
            if r.get("hay"):
                _UPDATE.update(r)
            else:
                _UPDATE["hay"] = False
                _UPDATE["actual"] = version.APP_VERSION
            return dict(_UPDATE)
        except Exception as exc:
            return {"hay": False, "actual": version.APP_VERSION,
                    "error": f"{type(exc).__name__}: {exc}"}

    def instalar_update(self):
        """Reemplaza el .exe por el update encontrado y reinicia NEXUS."""
        try:
            import updater
            r = updater.instalar_update(_UPDATE.get("ruta", ""))
            if r.get("ok"):
                def _morir():          # deja ver el aviso un segundo
                    time.sleep(1.2)
                    try:
                        import webview
                        webview.destroy_all_windows()
                    except Exception:
                        pass
                    os._exit(0)
                threading.Timer(0.1, _morir).start()
            return r
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def fijar_monitor(self, indice):
        """¿En cuál pantalla vive NEXUS? 0, 1, 2…"""
        try:
            i = int(indice)
        except Exception:
            i = 0
        if 0 <= i < len(_monitores()):
            _AJ["monitor"] = i
            datos = _leer_ajustes()
            datos["monitor"] = i
            _escribir_ajustes(datos)
            _reposicionar()
        return "ok"

    def fijar_hpos(self, hpos):
        """Posición horizontal de las ventanas (arriba o abajo da igual):
        'centro', 'izquierda' o 'derecha'. Se aplica YA y queda guardado."""
        hpos = str(hpos or "")
        if hpos not in _HPOS_OK:
            return "ok"
        _AJ["hpos"] = hpos
        datos = _leer_ajustes()
        datos["hpos"] = hpos
        _escribir_ajustes(datos)
        _reposicionar()
        estado.set_aviso(f"🎉 NEXUS a la {hpos}")
        return "ok"

    def fijar_tam(self, tam):
        """Tamaño del panel («compacto» 800×500, «grande» 1080×600,
        «ancho» 1320×640). Se aplica AL REINICIAR: cambiar el tamaño en
        caliente rompería la transparencia de WebView2."""
        tam = str(tam or "")
        if tam not in _TAM_PANEL:
            return "ok"
        _AJ["tam"] = tam
        datos = _leer_ajustes()
        datos["tam"] = tam
        _escribir_ajustes(datos)
        estado.set_aviso(f"🎉 Panel {tam}: se aplica al reiniciar")
        return "ok"

    def _aplicar_config(self, clave, valor):
        """Override de config en vivo: valor no vacío manda (se lee
        en cada pedido de llm/tts, así que pesca al instante);
        vacío = volver al valor de config.py (el que guarda _BASE)."""
        import config
        datos = _leer_ajustes()
        v = str(valor or "").strip()
        if v:
            datos[clave] = v
            setattr(config, clave, v)
        else:
            datos.pop(clave, None)
            base = getattr(config, "_BASE", {})
            if clave in base:
                setattr(config, clave, base[clave])
        _escribir_ajustes(datos)

    def guardar_cerebro(self, llave, modelo):
        """Pestaña Ajustes → cerebro: llave de la nube y modelo.
        Vacío = usar el de config.py."""
        self._aplicar_config("LLM_API_KEY", llave)
        self._aplicar_config("LLM_MODEL", modelo)
        estado.set_aviso("🎉 Cerebro actualizado")
        return "ok"

    def guardar_llave_fish(self, llave):
        """Pestaña Ajustes → voz: la llave de fish.audio del menú.
        Vacía = la de config.py."""
        self._aplicar_config("FISH_API_KEY", llave)
        estado.set_aviso("🎉 Llave de voz actualizada")
        return "ok"

    def _voces_ui(self):
        """Las voces del MENÚ: [{nombre, id, activa}]. 'activa' es la
        que en este momento vive en config.FISH_VOICE_ID."""
        import config
        activa = (getattr(config, "FISH_VOICE_ID", "") or "").strip()
        return [{"nombre": v["nombre"], "id": v["id"],
                 "activa": v["id"] == activa}
                for v in _AJ.get("voces", [])]

    def elegir_voz(self, id_voz):
        """Click en una voz del menú: pasa a ser LA voz YA (tts la lee
        en cada respuesta, no hace falta reiniciar)."""
        vid = str(id_voz or "").strip()
        if not vid:
            return "ok"
        nom = vid[:8]
        for v in _AJ.get("voces", []):
            if v["id"] == vid:
                nom = v["nombre"]
                break
        self._aplicar_config("FISH_VOICE_ID", vid)
        estado.set_aviso(f"🎉 Voz {nom}")
        return "ok"

    def anadir_voz(self, nombre, id_voz):
        """Añade (o renombra, si el ID ya existía) una voz del menú.
        Si es la primera, queda ACTIVA de una vez."""
        vid = str(id_voz or "").strip()
        if not vid:
            return "ok"
        nom = str(nombre or "").strip() or vid[:8]
        voces = [dict(v) for v in _AJ.get("voces", [])]
        habia = bool(voces)
        for v in voces:
            if v["id"] == vid:
                v["nombre"] = nom
                break
        else:
            voces.append({"nombre": nom, "id": vid})
        datos = _leer_ajustes()
        datos["voces"] = voces
        _escribir_ajustes(datos)
        _AJ["voces"] = voces
        if not habia:
            self._aplicar_config("FISH_VOICE_ID", vid)
            estado.set_aviso(f"🎉 Voz {nom} añadida y activada")
        else:
            estado.set_aviso(f"🎉 Voz {nom} añadida")
        return "ok"

    def quitar_voz(self, id_voz):
        """Quita una voz del menú. Si era la activa, pasa a quedar
        activa la primera que reste."""
        vid = str(id_voz or "").strip()
        antes = [dict(v) for v in _AJ.get("voces", [])]
        voces = [v for v in antes if v["id"] != vid]
        if len(voces) == len(antes):
            return "ok"
        datos = _leer_ajustes()
        datos["voces"] = voces
        _escribir_ajustes(datos)
        _AJ["voces"] = voces
        import config
        if (getattr(config, "FISH_VOICE_ID", "") or "").strip() == vid:
            if voces:
                self._aplicar_config("FISH_VOICE_ID", voces[0]["id"])
                estado.set_aviso(f"🎉 Vale: voz {voces[0]['nombre']}")
            else:
                estado.set_aviso("🎉 Voz eliminada")
        else:
            estado.set_aviso("🎉 Voz eliminada")
        return "ok"

    def probar_voz(self):
        """Suena una frase con la voz configurada (la nueva si acabas
        de guardarla). Corre en su hilo: no congela el panel."""
        def hilo():
            try:
                import tts
                estado.set_modo("hablando")
                tts.speak("Hola Dante. Así queda mi nueva voz, señor.")
            except Exception:
                pass
            finally:
                estado.set_modo("esperando")
        threading.Thread(target=hilo, daemon=True).start()
        return "ok"

    def abrir_ajustes(self):
        """El engranaje del notch: abre el panel DIRECTO en Ajustes."""
        _IR_A["sec"] = "ajustes"
        _IR_A["t"] = time.monotonic()
        _mostrar_panel()
        return "ok"


def _mostrar_panel():
    _panel_on["valor"] = True
    _latido[0] = time.monotonic()
    hwnd = _hwnd("NEXUS panel")
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 4)   # sin activar
    else:
        try:
            _ventana_panel.show()
        except Exception:
            pass
    # la página del panel quita el freno de sondeo/animaciones
    try:
        _ventana_panel.evaluate_js(
            "document.body.classList.remove('pausado')")
    except Exception:
        pass


def _ocultar_panel():
    _panel_on["valor"] = False
    try:
        _ventana_panel.hide()
    except Exception:
        pass
    # ventana oculta: la página pausa sondeos y animaciones (menos CPU)
    try:
        _ventana_panel.evaluate_js(
            "document.body.classList.add('pausado')")
    except Exception:
        pass


def _rect(titulo):
    """(l, t, r, b) físico de una ventana, o None."""
    hwnd = _hwnd(titulo)
    if not hwnd:
        return None
    r = _RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.l, r.t, r.r, r.b)


# ancho de la barra del notch según la clase CSS (px LÓGICOS)
_ANCHO_BARRA = {"arrancando": 214, "esperando": 198, "escuchando": 268,
                "pensando": 226, "hablando": 268}


def _sobre_notch(x, y):
    """¿El cursor está sobre la BARRA VISIBLE del notch?
    (la ventana es más ancha, pero el resto es transparente)"""
    rn = _rect("NEXUS")
    if not rn:
        return False
    l, t, r, b = rn
    if not (l <= x <= r and t <= y <= b):
        return False
    e = estado.get()
    if e.get("aviso"):
        ancho = 320 if "🎉" not in e["aviso"] else 246   # remind/success
    elif e.get("crono"):
        ancho = 252                                     # focus
    else:
        ancho = _ANCHO_BARRA.get(e.get("modo"), 214)
    ancho = ancho * _escala()                            # → físico
    cx = (l + r) / 2
    return abs(x - cx) <= ancho / 2 + 10                # 10 px de perdón


def _sobre_panel(x, y):
    rp = _rect("NEXUS panel")
    if not rp:
        return False
    l, t, r, b = rp
    return l <= x <= r and t <= y <= b


def _vigia():
    """Hover y autocierre del panel, TODO nativo (GetCursorPos):
    los eventos mouseenter/mouseleave de WebView2 a veces disparan
    un «mouseleave fantasma» con el cursor quieto y mataban el panel.
    - cursor sobre la barra del notch ≥0.25 s → abre el panel
    - cursor sobre el notch o el panel → latido (se mantiene abierto)
    - 0.9 s sin cursor encima ni actividad (teclado) → se cierra
    """
    dentro_desde = None
    while True:
        time.sleep(0.12)
        try:
            pt = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            x, y = pt.x, pt.y
        except Exception:
            continue
        ahora = time.monotonic()
        en_notch = _sobre_notch(x, y)
        en_panel = _panel_on["valor"] and _sobre_panel(x, y)
        if en_notch or en_panel:
            _latido[0] = ahora
        if en_notch and not _panel_on["valor"]:
            if dentro_desde is None:
                dentro_desde = ahora
            elif ahora - dentro_desde >= 0.25:
                _mostrar_panel()
                dentro_desde = None
        else:
            dentro_desde = None
        if _panel_on["valor"] and ahora - _latido[0] > 0.9:
            _ocultar_panel()


def _x_window(ancho, area, hpos):
    """X de una ventana según la posición horizontal pedida:
    izquierda → pegada a la izquierda, derecha → pegada a la derecha,
    centro → centrada (default)."""
    if area:
        if hpos == "izquierda":
            return area[0] + 8
        if hpos == "derecha":
            return max(area[0], area[2] - 8 - ancho)
        return area[0] + max(0, ((area[2] - area[0]) - ancho) // 2)
    sw = ctypes.windll.user32.GetSystemMetrics(0)
    if hpos == "izquierda":
        return 8
    if hpos == "derecha":
        return max(0, sw - 8 - ancho)
    return max(0, (sw - ancho) // 2)


def _mover(titulo, y_fisico, area=None, hpos="centro"):
    """Coloca la ventana EXACTAMENTE (solo MUEVE: el resize rompe la
    transparencia de WebView2). Usa el ancho REAL de la ventana;
    'area' = (l, t, r, b) del monitor donde colocarse."""
    hwnd = _hwnd(titulo)
    if not hwnd:
        return
    r = _RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    ancho = r.r - r.l
    x = _x_window(ancho, area, hpos)
    ctypes.windll.user32.SetWindowPos(
        hwnd, None, x, y_fisico, 0, 0, 0x0001)   # SWP_NOSIZE


def _reposicionar():
    """Coloca notch y panel según la pestaña Ajustes, en el monitor
    elegido y centrados en SU ancho:
    arriba → notch pegado al borde superior, menú hacia ABAJO;
    barra  → el widget SOBRE la barra de tareas (solo ojos y estado,
             integrado en la franja de la barra) y el menú crece
             hacia ARRIBA, muriendo justo donde empieza la barra."""
    esc = _escala()
    m = _monitor_elegido()
    scr, wrk = m["pantalla"], m["trabajo"]
    alto_n = int(ALTO_NOTCH * esc)
    if _AJ["pos"] == "barra":
        y_notch = scr[3] - alto_n                    # franja de la barra
        y_panel = wrk[3] - int(_tam_panel()[1] * esc)   # menú hacia arriba
    else:
        y_notch = scr[1]                             # borde superior
        y_panel = scr[1] + alto_n                    # menú hacia abajo
    _mover("NEXUS", y_notch, scr, _AJ.get("hpos", "centro"))
    _mover("NEXUS panel", y_panel, scr, _AJ.get("hpos", "centro"))


def _pintar_fondo_oscuro():
    """«La barra blanca de fondo»: mientras WebView2 todavía no compone
    el primer frame (y cuando Windows revive del sleep), lo que se ve
    de la ventana es el FONDO del formulario WinForms — #F0F0F0 por
    defecto, un blanco que canta. Se pinta del azul-noche NEXUS
    (#05070d): si algo asoma, asoma oscuro, nunca blanco.
    OJO: solo con la ventana TODAVÍA OCULTA; sobre una ventana ya
    visible el repaint del color TAPA la transparencia píxel a píxel."""
    try:
        import clr
        clr.AddReference('System.Windows.Forms')
        clr.AddReference('System.Drawing')
        from System import Func, Object
        from System.Drawing import Color

        for v in (_ventana, _ventana_panel):
            form = getattr(v, "native", None)
            if not form:
                continue
            try:
                def _pintar(f=form):
                    f.BackColor = Color.FromArgb(5, 7, 13)
                if form.InvokeRequired:
                    form.Invoke(Func[Object](_pintar))
                else:
                    _pintar()
            except Exception:
                pass
    except Exception:
        pass


def _ajustes():
    """Corre cuando el loop de pywebview YA vive: las ventanas ya
    tienen su tamaño final → centrar de verdad."""
    _pintar_fondo_oscuro()          # ANTES de que nada asome en blanco
    # pywebview MUESTRA toda ventana transparente al navegar (el hack
    # de on_navigation_start) → el panel nace VISIBLE: esconderlo
    # todo el arranque hasta que la UI asiente.
    fin = time.monotonic() + 3.0
    while time.monotonic() < fin:
        try:
            _ventana_panel.hide()
        except Exception:
            pass
        time.sleep(0.15)
    _reposicionar()
    try:
        _ventana_panel.hide()
    except Exception:
        pass


def _chequeo_update():
    """Al arrancar como .exe: tras unos segundos busca un nexus.exe más
    nuevo y, si hay, avisa en el notch y en la pestaña Ajustes."""
    if not getattr(sys, "frozen", False):
        return
    import updater

    def _callback(r):
        _UPDATE.update(r)
        estado.set_aviso(f"🎉 Update v{r['version']} disponible — pestaña Ajustes")
        if _NOVEDADES is not None:
            try:
                _NOVEDADES.put(f"🎉 Update disponible: v{r['version']} (Ajustes)")
            except Exception:
                pass

    updater.comprobar_en_segundo_plano(_callback, espera=12)


def arrancar(novedades):
    """Dos ventanas: el notch (siempre visible) y el panel (oculto
    hasta que se pide). Sin resizes: la transparencia no se rompe."""
    global _ventana, _ventana_panel, _NOVEDADES
    _patch_chat()
    import webview

    class _Api(Api):
        _novedades = novedades

    api = _Api()
    _NOVEDADES = novedades
    ruta = _ruta_base() / "web" / "nexus.html"
    uri = ruta.as_uri()

    # ubicación inicial (píxel LÓGICO, aprox.): el monitor elegido y
    # la posición de la pestaña Ajustes; a los 2,5 s _ajustes() fija
    # las coordenadas físicas exactas
    _AJ.update(_leer_ajustes())
    ancho_p, alto_p = _tam_panel()          # tamaño pedido en Ajustes
    m = _monitor_elegido()
    scr, wrk = m["pantalla"], m["trabajo"]
    esc = _escala()
    hpos = _AJ.get("hpos", "centro")
    # create_window recibe píxeles LÓGICOS: _x_window da físicos → ÷ esc
    x_notch = int(round(_x_window(int(ANCHO_NOTCH * esc), scr, hpos) / esc))
    x_panel = int(round(_x_window(int(ancho_p * esc), scr, hpos) / esc))
    if _AJ["pos"] == "barra":
        y_notch = max(0, int(round(scr[3] / esc)) - ALTO_NOTCH)
        y_panel = max(0, int(round(wrk[3] / esc)) - alto_p)
    else:
        y_notch = int(round(scr[1] / esc))
        y_panel = y_notch + ALTO_NOTCH

    # el notch: chiquito, centrado, SIEMPRE encima
    _ventana = webview.create_window(
        "NEXUS", url=uri + "#notch", js_api=api,
        width=ANCHO_NOTCH, height=ALTO_NOTCH,
        x=x_notch, y=y_notch,
        min_size=(ANCHO_NOTCH, ALTO_NOTCH),
        frameless=True, transparent=True, resizable=False,
        on_top=True, background_color="#000000")

    # el panel: nace OCULTO del lado contrario del notch; mostrar/ocultar
    _ventana_panel = webview.create_window(
        "NEXUS panel", url=uri + "#panel", js_api=api,
        width=ancho_p, height=alto_p,
        x=x_panel, y=y_panel,
        min_size=(ancho_p, alto_p),
        frameless=True, transparent=True, resizable=False,
        on_top=True, hidden=True, background_color="#000000")

    threading.Thread(target=_vigia, daemon=True).start()
    _chequeo_update()
    webview.start(gui="edgechromium", func=_ajustes, debug=False)
