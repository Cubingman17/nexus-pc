"""Las manos de NEXUS: herramientas reales sobre tu PC con Windows 10."""
import datetime
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import psutil

import estado

try:
    import winsound  # solo existe en Windows

    _WINDOWS = True
except ImportError:
    _WINDOWS = False

try:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    _PYCAW = True
except Exception:
    _PYCAW = False


NOTES_FILE = Path.home() / "jarvis_notas.txt"

APP_ALIASES = {
    "chrome": "chrome", "navegador": "chrome",
    "edge": "msedge",
    "vscode": "code", "vs code": "code", "editor": "code", "visual studio code": "code",
    "spotify": "spotify", "discord": "discord", "whatsapp": "whatsapp",
    "calculadora": "calc", "bloc de notas": "notepad", "notas": "notepad",
    "explorador": "explorer", "explorador de archivos": "explorer",
    "paint": "mspaint",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "configuracion": "ms-settings:",
    "minecraft": "minecraft:",   # Minecraft Bedrock (tienda de Microsoft)
    "arduino": "arduino ide", "arduino ide": "arduino ide",
    "dopamine": "dopamine",
}

# Rutas de instalación típicas para apps que no están ni en PATH ni App Paths
APP_PATHS = {
    "arduino ide": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arduino IDE\Arduino IDE.exe"),
        r"C:\Program Files\Arduino IDE\Arduino IDE.exe",
    ],
    "dopamine": [
        r"C:\Program Files\Dopamine\Dopamine.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Dopamine\Dopamine.exe"),
    ],
}


def _find_app(exe):
    """¿La app existe de verdad? PATH → registro App Paths → rutas conocidas.

    Devuelve lo que hay que pasarle a `start`, o None si no está instalada.
    """
    if exe.endswith(":"):  # URIs de shell: ms-settings:, minecraft:
        return exe
    if shutil.which(exe):  # chrome, notepad, mspaint... están en PATH
        return exe
    try:  # App Paths del registro: así 'start' resuelve code, spotify, winword...
        import winreg
        for raiz in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    raiz, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
                ) as clave:
                    ruta, _ = winreg.QueryValueEx(
                        clave, exe if exe.endswith(".exe") else exe + ".exe"
                    )
                    if ruta:
                        return ruta
            except OSError:
                continue
    except Exception:
        pass
    for ruta in APP_PATHS.get(exe, []):
        if os.path.isfile(ruta):
            return ruta
    return None

FOLDER_ALIASES = {
    "escritorio": Path.home() / "Desktop",
    "descargas": Path.home() / "Downloads",
    "documentos": Path.home() / "Documents",
    "imagenes": Path.home() / "Pictures", "imágenes": Path.home() / "Pictures",
    "videos": Path.home() / "Videos", "vídeos": Path.home() / "Videos",
    "musica": Path.home() / "Music", "música": Path.home() / "Music",
    "canciones": Path.home() / "Music" / "canciones",
}

# Extensiones que Jarvis considera canciones
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac")


def _desktop_path():
    """Soporta escritorio normal y de OneDrive."""
    for candidate in (Path.home() / "Desktop", Path.home() / "OneDrive" / "Desktop"):
        if candidate.exists():
            return candidate
    return Path.home() / "Desktop"


# ═══════════════════════ Implementaciones ═══════════════════════


def get_time():
    return datetime.datetime.now().strftime("Son las %I:%M %p.").lstrip("0")


def get_date():
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    hoy = datetime.date.today()
    return f"Hoy es {dias[hoy.weekday()]} {hoy.day} de {meses[hoy.month - 1]} de {hoy.year}."


def open_app(name):
    original = name.strip().lower()
    exe = APP_ALIASES.get(original, original)
    exe = APP_ALIASES.get(exe, exe)  # por si un alias apunta a otro alias
    ruta = _find_app(exe)
    if ruta is None:
        # antes decía "Abriendo..." aunque `start` fallara en silencio
        return (f"No encontré '{name}' instalada en el PC. "
                f"Si sí está, agrega su ruta exacta en APP_PATHS de tools.py.")
    subprocess.Popen(["cmd", "/c", "start", "", ruta])
    return f"Abriendo {name}."


def open_website(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Abriendo {url}."


def search_web(query):
    webbrowser.open("https://www.google.com/search?q=" + query.replace(" ", "+"))
    return f"Buscando '{query}' en Google."


def play_youtube(query):
    webbrowser.open("https://www.youtube.com/results?search_query=" + query.replace(" ", "+"))
    return f"Buscando '{query}' en YouTube."


def system_status():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    root = "C:\\" if os.name == "nt" else "/"
    disk = psutil.disk_usage(root)
    battery = psutil.sensors_battery()
    partes = [
        f"CPU al {cpu:.0f}%.",
        f"RAM: {ram.used / 1e9:.1f} de {ram.total / 1e9:.1f} GB en uso ({ram.percent:.0f}%).",
        f"Disco principal al {disk.percent:.0f}% de capacidad.",
    ]
    if battery is not None:
        estado = "enchufado" if battery.power_plugged else "con batería"
        partes.append(f"Batería al {battery.percent}%, {estado}.")
    return " ".join(partes)


def organize_desktop():
    escritorio = _desktop_path()
    categorias = {
        "Imágenes": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
        "Documentos": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"},
        "Videos": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
        "Otros": set(),
    }
    movidos = 0
    rutas = []   # (destino, origen) para poder deshacer
    for archivo in escritorio.iterdir():
        if not archivo.is_file() or archivo.suffix.lower() == ".lnk":
            continue  # los accesos directos NO se tocan
        carpeta = next(
            (cat for cat, exts in categorias.items() if archivo.suffix.lower() in exts),
            "Otros",
        )
        destino_dir = escritorio / "Organizado" / carpeta
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / archivo.name
        i = 1
        while destino.exists():
            destino = destino_dir / f"{archivo.stem} ({i}){archivo.suffix}"
            i += 1
        archivo.replace(destino)
        rutas.append((destino, archivo))
        movidos += 1

    if movidos:
        def _devolver():
            for destino, origen in reversed(rutas):
                if destino.exists():
                    destino.replace(origen)
        _registrar_undo(f"organizar el escritorio ({movidos} archivos)", _devolver)
    return (f"Escritorio organizado: {movidos} archivos movidos a la carpeta 'Organizado'. "
            f"Los accesos directos no los toqué. Di «deshaz eso» si te arrepientes.")


def set_reminder(message, when):
    """`when` en formato 'YYYY-MM-DD HH:MM' (24 horas)."""
    objetivo = datetime.datetime.strptime(when, "%Y-%m-%d %H:%M")
    delay = (objetivo - datetime.datetime.now()).total_seconds()
    if delay <= 0:
        return "Esa hora ya pasó, señor. Aún no domino los recordatorios del pasado."
    cancelar = threading.Event()
    threading.Thread(target=_disparar_recordatorio,
                     args=(delay, message, cancelar), daemon=True).start()
    _registrar_undo(f"recordatorio «{message}» del {when}",
                    lambda: cancelar.set())
    return f"Recordatorio listo para el {when}: «{message}». Di «deshaz eso» para cancelarlo."


def _disparar_recordatorio(delay, message, cancelar=None):
    if cancelar is not None:
        if cancelar.wait(max(0, delay)):   # True = lo deshicieron
            return
    else:
        time.sleep(max(0, delay))
    import tts
    if _WINDOWS:
        for _ in range(2):
            winsound.Beep(880, 300)
            time.sleep(0.1)
    estado.set_aviso(f"⏰ {message}")
    tts.speak(f"Recordatorio: {message}")


def set_volume(percent):
    percent = max(0, min(100, int(percent)))
    # camino A: control fino por COM (si está pycaw instalado)
    if _PYCAW:
        try:
            import comtypes
            comtypes.CoInitialize()  # el pipeline corre en un hilo: COM se arma AHÍ
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            anterior = round(volume.GetMasterVolumeLevelScalar() * 100)
            volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
            _registrar_undo(f"volumen al {percent}% (antes {anterior}%)",
                            lambda: volume.SetMasterVolumeLevelScalar(anterior / 100.0, None))
            return f"Volumen al {percent}%."
        except Exception as exc:
            print(f"[volumen COM falló: {type(exc).__name__}: {exc}] → teclas multimedia")
    # camino B: teclas de volumen del teclado — cero dependencias
    try:
        return _volumen_por_teclas(percent)
    except Exception:
        return ("No pude ajustar el volumen. Para control exacto instala: "
                "py -3.12 -m pip install pycaw comtypes")


def _volumen_por_teclas(percent):
    """Presiona las teclas multimedia: baja al mínimo y sube al objetivo.

    Windows mueve el volumen 2% por pulsación → 50 bajadas = 0%,
    luego percent//2 subidas = el nivel pedido. No necesita nada instalado.
    """
    import ctypes
    user32 = ctypes.windll.user32
    VK_UP, VK_DOWN, KEYUP = 0xAF, 0xAE, 0x0002

    def press(vk, n):
        for _ in range(n):
            user32.keybd_event(vk, 0, 0, 0)
            user32.keybd_event(vk, 0, KEYUP, 0)
            time.sleep(0.012)

    press(VK_DOWN, 50)                  # al 0%
    press(VK_UP, max(0, percent) // 2)  # 2% por pulsación → objetivo
    return f"Volumen al {percent}%."


def create_note(text):
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    linea = f"[{fecha}] {text}"
    with open(NOTES_FILE, "a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")
    _registrar_undo(f"nota «{text}»",
                    lambda: _quitar_ultima_linea(NOTES_FILE, linea))
    return f"Nota guardada en {NOTES_FILE}."


def open_folder(name):
    clave = name.strip().lower()
    ruta = FOLDER_ALIASES.get(clave)
    if ruta is None:
        # también acepta rutas completas: "C:\Users\Dante\Music\canciones"
        candidato = Path(name.strip().strip('"'))
        if candidato.exists():
            os.startfile(candidato)
            return f"Abriendo {candidato}."
        return ("No conozco esa carpeta. Manejo: escritorio, descargas, "
                "documentos, imagenes, videos, musica, canciones — "
                "o pásame la ruta completa.")
    if not ruta.exists():
        return "Esa carpeta no existe en este equipo."
    os.startfile(ruta)
    return f"Abriendo {name}."


def play_local_music(folder="canciones"):
    """Pone una canción AL AZAR de una carpeta de música del PC."""
    clave = folder.strip().lower().strip('"')
    base = FOLDER_ALIASES.get(clave)
    if base is None:
        candidato = Path(folder.strip().strip('"'))
        base = candidato if candidato.exists() else (Path.home() / "Music" / clave)
    if base is None or not base.exists():
        return (f"No encontré la carpeta '{folder}'. Prueba con: canciones, "
                "musica, o una ruta completa.")
    canciones = [f for f in base.iterdir() if f.is_file()
                 and f.suffix.lower() in AUDIO_EXTS]
    if not canciones:
        return f"No encontré archivos de audio en {base}."
    elegida = random.choice(canciones)
    os.startfile(elegida)  # la abre con tu reproductor predeterminado
    return f"Reproduciendo {elegida.stem}, de la carpeta {base.name}."


def show_desktop():
    """Minimiza todo y muestra el escritorio (como Win+D)."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(New-Object -ComObject Shell.Application).ToggleDesktop()"],
        capture_output=True, timeout=15,
    )
    return "Mostrando el escritorio."


# ═══════════════════════ Búsqueda silenciosa + documentos ═══════════════════════

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _limpiar_html(s):
    """Quita etiquetas y entidades para dejar texto legible."""
    s = re.sub(r"<[^>]+>", " ", s)
    for viejo, nuevo in (("&amp;", "&"), ("&quot;", '"'), ("&#x27;", "'"),
                        ("&#39;", "'"), ("&nbsp;", " "), ("&lt;", "<"),
                        ("&gt;", ">")):
        s = s.replace(viejo, nuevo)
    return re.sub(r"\s+", " ", s).strip()


def search_online(query):
    """Busca en internet SIN abrir el navegador y devuelve los hallazgos.

    El mayordomo lee el resumen en voz alta mientras el usuario sigue
    haciendo lo suyo: nada de ventanas que roben el foco.
    """
    import requests
    q = (query or "").strip()
    if not q:
        return "No me dijiste qué buscar."

    # camino A: DuckDuckGo en HTML (sin key, sin abrir nada)
    try:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": q},
                          headers=_UA, timeout=12)
        r.raise_for_status()
        titulos = re.findall(r'class="result__a"[^>]*>(.*?)</a>', r.text, re.S)
        frag = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.S)
        hallazgos = [f"{_limpiar_html(t)} — {_limpiar_html(f)}"
                     for t, f in zip(titulos, frag) if _limpiar_html(f)]
        if hallazgos:
            return ("HALLAZGOS para '" + q + "':\n- " + "\n- ".join(hallazgos[:4]) +
                    "\nResúmelos en 2-3 frases habladas y diceselo al usuario.")
    except Exception as exc:
        print(f"[búsqueda DDG falló: {type(exc).__name__}] → probando Wikipedia")

    # camino B: Wikipedia en español (API pública, sin key)
    try:
        r = requests.get("https://es.wikipedia.org/w/api.php", headers=_UA,
                         params={"action": "query", "list": "search",
                                 "srsearch": q, "srlimit": "3", "format": "json"},
                         timeout=12)
        datos = r.json().get("query", {}).get("search", [])
        hallazgos = [f"{d.get('title')} — {_limpiar_html(d.get('snippet', ''))}"
                     for d in datos]
        if hallazgos:
            return ("HALLAZGOS (Wikipedia) para '" + q + "':\n- " +
                    "\n- ".join(hallazgos) +
                    "\nResúmelos en 2-3 frases habladas y diceselo al usuario.")
    except Exception as exc:
        print(f"[búsqueda Wikipedia falló: {type(exc).__name__}]")

    return ("No pude completar la búsqueda (revisa el internet). "
            "Responde de tu propio conocimiento y avísale al usuario.")


_FUENTES = {"comic sans": "Comic Sans MS", "comic": "Comic Sans MS",
            "arial": "Arial", "calibri": "Calibri", "times": "Times New Roman",
            "courier": "Courier New", "consolas": "Consolas", "verdana": "Verdana"}


def create_document(content, font="Calibri", size=11, filename=None):
    """Crea un documento Word con el texto, la fuente y el tamaño pedidos.

    filename puede ser un nombre ('hola.docx') o una ruta completa del PC.
    Si python-docx no está instalado, genera un .rtf que Word abre igual
    respetando fuente y tamaño.
    """
    contenido = content or ""
    fuente = _FUENTES.get((font or "Calibri").strip().lower(), font or "Calibri")
    try:
        tam = max(6, min(400, int(size or 11)))
    except (TypeError, ValueError):
        tam = 11

    # ¿dónde se guarda? sin nombre → Escritorio con sello de hora;
    # carpeta existente → adentro; nombre o ruta completa → tal cual
    destino = None
    if filename and str(filename).strip():
        cand = Path(str(filename).strip().strip('"'))
        if cand.exists() and cand.is_dir():
            destino = cand / "documento_JARVIS.docx"
        else:
            destino = cand
    if destino is None:
        sello = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        destino = Path(_desktop_path()) / f"documento_JARVIS_{sello}"
    if not destino.suffix:
        destino = destino.with_suffix(".docx")

    try:
        from docx import Document
        from docx.shared import Pt
        doc = Document()
        p = doc.add_paragraph()
        run = p.add_run(contenido)
        run.font.name = fuente
        run.font.size = Pt(tam)
        destino.parent.mkdir(parents=True, exist_ok=True)  # ubicación nueva
        doc.save(str(destino))
        os.startfile(str(destino))          # lo abre para que lo vea
        _registrar_undo(f"documento {destino.name}",
                        lambda: os.remove(str(destino)))
        return (f"Documento creado en {destino} (fuente {fuente}, {tam} pt) "
                "y abierto. Di «deshaz eso» para borrarlo.")
    except ImportError:
        pass                                  # sin python-docx → RTF
    except Exception as exc:
        return f"No pude crear el documento: {type(exc).__name__}: {exc}"

    # plan B: RTF (cero dependencias, Word lo abre con la fuente puesta)
    destino = destino.with_suffix(".rtf")
    esc = contenido.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    rtf = ("{\\rtf1\\ansi{\\fonttbl{\\f0 " + fuente + ";}}\n"
           f"\\fs{tam * 2} {esc}\\par\n}}")
    destino.parent.mkdir(parents=True, exist_ok=True)  # ubicación nueva
    with open(destino, "w", encoding="utf-8") as f:
        f.write(rtf)
    os.startfile(str(destino))
    _registrar_undo(f"documento {destino.name}",
                    lambda: os.remove(str(destino)))
    return (f"Documento creado en {destino} (fuente {fuente}, {tam} pt, "
            "formato RTF) y abierto. Di «deshaz eso» para borrarlo.")


# ═══════════════════════ Memoria duradera de Jarvis ═══════════════════════

MEMORY_FILE = Path.home() / "jarvis_memoria.txt"


def remember(text):
    """Guarda un recuerdo duradero: Dante lo manda y Jarvis no lo olvida."""
    dato = (text or "").strip()
    if not dato:
        return "No me dijiste qué recordar."
    fecha = datetime.datetime.now().strftime("%Y-%m-%d")
    linea = f"[{fecha}] {dato}"
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(linea + "\n")
    _registrar_undo(f"recuerdo «{dato}»",
                    lambda: _quitar_ultima_linea(MEMORY_FILE, linea))
    return f"Guardado en mi memoria para siempre: '{dato}'. Di «deshaz eso» si fue un error."


def leer_memoria(n=30):
    """Las últimas n líneas de memoria (las inyecta el prompt de cada sesión)."""
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE, encoding="utf-8") as f:
        lineas = [l.rstrip() for l in f if l.strip()]
    return lineas[-n:]


# ═══════════════════════ Deshacer: la herramienta undo ═══════════════════════

_UNDO = []   # pila de (descripción, callable que revierte)


def _registrar_undo(desc, accion):
    """Apila la reversión de lo último hecho (máx 20 pasos)."""
    _UNDO.append((desc, accion))
    if len(_UNDO) > 20:
        _UNDO.pop(0)


def _quitar_ultima_linea(ruta, linea):
    """Borra la última línea que coincida con `linea` en un archivo de texto."""
    with open(ruta, encoding="utf-8") as f:
        lineas = f.readlines()
    for i in range(len(lineas) - 1, -1, -1):
        if lineas[i].rstrip("\n") == linea.rstrip("\n"):
            del lineas[i]
            break
    with open(ruta, "w", encoding="utf-8") as f:
        f.writelines(lineas)


def undo():
    """Deshace la última acción reversible (una a la vez, la más reciente)."""
    if not _UNDO:
        return "No tengo nada que deshacer, señor."
    desc, accion = _UNDO.pop()
    try:
        accion()
        return f"Deshecho: {desc}."
    except Exception as exc:
        return (f"Intenté deshacer '{desc}' pero falló: {type(exc).__name__}: "
                f"{exc}. Quizá lo tienes abierto — ciérralo y reintenta.")


# ═══════════════════ Modo CLI: código, archivos y cálculos ═══════════════════

_EXT_POR_LENGUAJE = {
    "python": ".py", "py": ".py", "javascript": ".js", "js": ".js",
    "html": ".html", "css": ".css", "batch": ".bat", "bat": ".bat",
    "java": ".java", "c": ".c", "cpp": ".cpp", "c++": ".cpp",
    "json": ".json", "texto": ".txt", "txt": ".txt", "markdown": ".md",
}

SCRIPTS_DIR = Path.home() / "nexus_scripts"


def create_code(filename, content, language="python"):
    """Escribe un archivo de código en el Escritorio (o ruta pedida)."""
    nombre = (filename or "").strip().strip('"')
    if not nombre:
        sello = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        nombre = f"script_nexus_{sello}"
    destino = Path(nombre)
    if not destino.is_absolute():
        destino = Path(_desktop_path()) / destino
    ext = _EXT_POR_LENGUAJE.get((language or "python").strip().lower(), "")
    if not destino.suffix:                      # sin extensión → la del lenguaje
        destino = destino.with_suffix(ext or ".py")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(content or "", encoding="utf-8")
    _registrar_undo(f"código {destino.name}", lambda: os.remove(str(destino)))
    try:
        os.startfile(str(destino))              # lo abre con tu editor
    except Exception:
        pass
    return (f"Código {language} escrito en {destino} y abierto. "
            f"Di «deshaz eso» para borrarlo.")


def read_file(path):
    """Lee un archivo de texto y devuelve su contenido para analizarlo."""
    candidato = Path((path or "").strip().strip('"').replace("~", str(Path.home())))
    if not candidato.is_absolute():
        candidato = Path(_desktop_path()) / candidato
    if not candidato.exists():
        return f"No existe: {candidato}. Pásame la ruta completa."
    try:
        contenido = candidato.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"No pude leer {candidato}: {type(exc).__name__}: {exc}"
    if len(contenido) > 8000:
        return (f"{candidato} ({len(contenido)} caracteres) — primeros 8000:\n"
                + contenido[:8000])
    return f"{candidato}:\n{contenido}"


def run_python(code, filename=None):
    """Escribe y EJECUTA un script de Python; devuelve su salida."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    sello = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = SCRIPTS_DIR / (filename or f"run_{sello}").strip().strip('"')
    if not destino.suffix:
        destino = destino.with_suffix(".py")
    destino.write_text(code or "", encoding="utf-8")
    import subprocess
    import sys
    try:
        r = subprocess.run(
            [sys.executable, str(destino)],
            capture_output=True, text=True, timeout=25,
            encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return f"El script {destino.name} no terminó en 25 s — lo detuve."
    salida = (r.stdout or "").strip()
    error = (r.stderr or "").strip()
    resumen = []
    if salida:
        resumen.append(salida[:1500])
    if error:
        resumen.append("ERRORES:\n" + error[:800])
    _registrar_undo(f"script {destino.name}", lambda: os.remove(str(destino)))
    if not resumen:
        return f"Script {destino.name} ejecutado: corrió limpio (sin salida)."
    return f"Script {destino.name} ejecutado:\n" + "\n".join(resumen)


def calculate(expression):
    """Calcula una expresión matemática de forma EXACTA (no a ojo).

    Acepta números, + - * / // % **, paréntesis y funciones:
    sqrt, sin, cos, tan, log, log10, exp, abs, round, pi, e.
    """
    import ast
    import math
    expr = (expression or "").strip()
    if not expr:
        return "No me diste nada que calcular."
    funciones = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                 "tan": math.tan, "log": math.log, "log10": math.log10,
                 "exp": math.exp, "abs": abs, "round": round}
    constantes = {"pi": math.pi, "e": math.e}

    def _eval(nodo):
        if isinstance(nodo, ast.Expression):
            return _eval(nodo.body)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
            return nodo.value
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) \
                and nodo.func.id in funciones:
            return funciones[nodo.func.id](*[_eval(a) for a in nodo.args])
        if isinstance(nodo, ast.BinOp):
            izq, der = _eval(nodo.left), _eval(nodo.right)
            if isinstance(nodo.op, ast.Add):
                return izq + der
            if isinstance(nodo.op, ast.Sub):
                return izq - der
            if isinstance(nodo.op, ast.Mult):
                return izq * der
            if isinstance(nodo.op, ast.Div):
                return izq / der
            if isinstance(nodo.op, ast.FloorDiv):
                return izq // der
            if isinstance(nodo.op, ast.Mod):
                return izq % der
            if isinstance(nodo.op, ast.Pow):
                return izq ** der
        if isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, (ast.USub, ast.UAdd)):
            v = _eval(nodo.operand)
            return -v if isinstance(nodo.op, ast.USub) else v
        raise ValueError(f"no entiendo esa parte: {ast.dump(nodo)[:60]}")

    try:
        for nombre, valor in constantes.items():
            expr = re.sub(rf"\b{nombre}\b", f"({valor!r})", expr)
        arbol = ast.parse(expr.replace("^", "**"), mode="eval")
        resultado = _eval(arbol)
        bonito = f"{resultado:.10f}".rstrip("0").rstrip(".") \
            if isinstance(resultado, float) else str(resultado)
        return f"{expression} = {bonito}"
    except Exception as exc:
        return (f"No pude calcular '{expression}': {exc}. "
                "Usa números, + - * / paréntesis, sqrt, pi...")


def list_files(folder="escritorio"):
    """Lista lo que hay en una carpeta (escritorio, descargas, música...)."""
    clave = (folder or "escritorio").strip().lower().strip('"')
    alias = FOLDER_ALIASES.get(clave)
    if alias is not None:
        base = Path(alias)
    else:
        candidato = Path((folder or "").strip().strip('"').replace("~", str(Path.home())))
        base = candidato if candidato.exists() else None
    if base is None or not base.exists():
        return (f"No conozco esa carpeta. Manejo: {', '.join(FOLDER_ALIASES)} "
                "— o pásame la ruta completa.")
    entradas = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entradas:
        return f"{base} está vacía."
    lineas = []
    for e in entradas[:50]:
        lineas.append(("📁 " if e.is_dir() else "📄 ") + e.name)
    if len(entradas) > 50:
        lineas.append(f"… y {len(entradas) - 50} más")
    return f"En {base} hay {len(entradas)} elementos:\n" + "\n".join(lineas)


def look_screen():
    """LOS OJOS DE NEXUS: captura la pantalla y la deja lista para que el
    cerebro la VEA como imagen (la ruta va con prefijo CAPTURA: y llm.py
    la convierte en imagen para el modelo con visión)."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return ("No tengo ojos todavía: falta Pillow. Instálalo con "
                "`py -3.12 -m pip install Pillow` y reiníciame.")
    try:
        try:
            img = ImageGrab.grab(all_screens=True)   # todos los monitores
        except TypeError:
            img = ImageGrab.grab()                   # PIL viejo: monitor 1
    except Exception as exc:
        return f"No pude capturar la pantalla: {exc}"

    # achicar para que la imagen no pese una tonelada en el contexto
    if img.width > 1280:
        escala = 1280 / img.width
        img = img.resize((1280, max(1, int(img.height * escala))))
    temp = Path(os.environ.get("TEMP", tempfile.gettempdir()))
    # limpiar capturas viejas de NEXUS para no llenar el disco
    for vieja in temp.glob("nexus_vista_*.jpg"):
        try:
            vieja.unlink()
        except OSError:
            pass
    ruta = temp / f"nexus_vista_{int(time.time() * 1000)}.jpg"
    try:
        img.convert("RGB").save(str(ruta), "JPEG", quality=72)
    except Exception as exc:
        return f"Capturé la pantalla pero no pude guardarla: {exc}"
    return f"CAPTURA:{ruta}"


# ═══════════════════ MODO TROKO: tareas, hábitos y enfoque ═══════════════════

TAREAS_PATH = Path.home() / "nexus_tareas.json"
HABITOS_PATH = Path.home() / "nexus_habitos.json"
_FOCO = {"cancelar": None, "total": 0}   # Event y duración del foco activo


def _leer_json(ruta, defecto):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def _guardar_json(ruta, datos):
    Path(ruta).write_text(
        json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _aviso(texto):
    """Notificación que aparece en la isla de la GUI."""
    try:
        estado.set_aviso(texto)
    except Exception:
        pass


# ── Tareas ──────────────────────────────────────────────────────────
def add_task(text):
    texto = (text or "").strip().strip('"')
    if not texto:
        return "¿Qué tarea quiero anotar?"
    datos = _leer_json(TAREAS_PATH, {"pendientes": [], "hechas": []})
    datos["pendientes"].append(texto)
    _guardar_json(TAREAS_PATH, datos)
    _aviso("✓ Anotado")
    _registrar_undo(f"tarea «{texto}»",
                    lambda: (_guardar_json(TAREAS_PATH, _sacar_ultima(
                        TAREAS_PATH, "pendientes")), _aviso("Deshago ✓")))
    return (f"Anotado: «{texto}». Tienes {len(datos['pendientes'])} "
            "tareas pendientes.")


def _sacar_ultima(ruta, campo):
    """Quita el último elemento de `campo` (para deshacer tareas)."""
    datos = _leer_json(ruta, {"pendientes": [], "hechas": []})
    if datos[campo]:
        datos[campo].pop()
    return datos


def complete_task(match):
    datos = _leer_json(TAREAS_PATH, {"pendientes": [], "hechas": []})
    pend = datos["pendientes"]
    if not pend:
        return "No tienes tareas pendientes. Día limpio, señor."
    clave = (match or "").strip().lower()
    idx = None
    if clave.isdigit():
        n = int(clave)
        if 1 <= n <= len(pend):
            idx = n - 1
    if idx is None:
        for i, t in enumerate(pend):
            if clave and (clave in t.lower() or t.lower() in clave):
                idx = i
                break
    if idx is None:
        return f"No encontré «{match}». Pendientes: {', '.join(pend)}"
    hecha = pend.pop(idx)
    datos.setdefault("hechas", []).append(
        {"texto": hecha, "fecha": datetime.date.today().isoformat()})
    _guardar_json(TAREAS_PATH, datos)
    _aviso("✓ Hecho")
    _registrar_undo(f"completar «{hecha}»",
                    lambda: (_guardar_json(TAREAS_PATH, _recuperar_tarea(hecha)),
                             _aviso("Deshago ✓")))
    return (f"Hecho: «{hecha}». Te quedan {len(pend)} pendientes."
            if pend else f"Hecho: «{hecha}». ¡Todo limpio, señor!")


def _recuperar_tarea(texto):
    """Devolver una tarea completada a pendientes (para deshacer)."""
    datos = _leer_json(TAREAS_PATH, {"pendientes": [], "hechas": []})
    if texto in datos["pendientes"]:
        return datos
    datos["pendientes"].append(texto)
    return datos


def list_tasks():
    datos = _leer_json(TAREAS_PATH, {"pendientes": [], "hechas": []})
    pend = datos["pendientes"]
    if not pend:
        return "No tienes tareas pendientes."
    hoy = datetime.date.today().isoformat()
    hechas_hoy = sum(1 for h in datos.get("hechas", []) if h.get("fecha") == hoy)
    lineas = [f"  {i + 1}. {t}" for i, t in enumerate(pend)]
    return (f"Tienes {len(pend)} pendientes (y {hechas_hoy} hechas hoy):\n"
            + "\n".join(lineas))


def uncomplete_task(match):
    """Devuelve una tarea HECHA a pendientes (missclick / error)."""
    datos = _leer_json(TAREAS_PATH, {"pendientes": [], "hechas": []})
    hechas = datos.get("hechas", [])
    if not hechas:
        return "No tienes tareas hechas que descompletar."
    clave = (match or "").strip().lower()
    idx = None
    if clave.isdigit():
        n = int(clave)
        if 1 <= n <= len(hechas):
            idx = n - 1
    if idx is None:
        for i, h in enumerate(hechas):
            texto = h.get("texto", "") if isinstance(h, dict) else str(h)
            if clave and (clave in texto.lower() or texto.lower() in clave):
                idx = i
                break
    if idx is None:
        return ("No encontré esa tarea hecha. Últimas hechas: "
                + ", ".join((h.get("texto", "") if isinstance(h, dict)
                             else str(h)) for h in hechas[-5:]))
    h = hechas.pop(idx)
    texto = h.get("texto", "") if isinstance(h, dict) else str(h)
    datos["pendientes"].append(texto)
    _guardar_json(TAREAS_PATH, datos)
    _aviso("↩ Pendiente otra vez")
    _registrar_undo(f"descompletar «{texto}»",
                    lambda: (_guardar_json(TAREAS_PATH, _sacar_ultima(
                        TAREAS_PATH, "pendientes")), _aviso("Deshago ✓")))
    return f"De vuelta a pendientes: «{texto}»."


def delete_task(match):
    """BORRA una tarea (pendiente o hecha) de la lista (undo la revive)."""
    datos = _leer_json(TAREAS_PATH, {"pendientes": [], "hechas": []})
    clave = (match or "").strip().lower()
    # primero entre las pendientes
    for i, t in enumerate(datos["pendientes"]):
        if clave and (clave in t.lower() or t.lower() in clave):
            borrada = datos["pendientes"].pop(i)
            _guardar_json(TAREAS_PATH, datos)
            _aviso("✕ Tarea borrada")
            _registrar_undo(f"borrado de «{borrada}»",
                            lambda b=borrada: (_guardar_json(
                                TAREAS_PATH, _recuperar_tarea(b)),
                                _aviso("Deshago ✓")))
            return f"Borré la tarea «{borrada}»."
    # si no, entre las hechas
    for i, h in enumerate(datos.get("hechas", [])):
        texto = h.get("texto", "") if isinstance(h, dict) else str(h)
        if clave and (clave in texto.lower() or texto.lower() in clave):
            datos["hechas"].pop(i)
            _guardar_json(TAREAS_PATH, datos)
            _aviso("✕ Tarea borrada")
            _registrar_undo(f"borrado de «{texto}»",
                            lambda: (_aviso("Deshago ✓"),))
            return f"Borré la tarea hecha «{texto}»."
    if datos["pendientes"]:
        return ("No la encontré. Pendientes: "
                + ", ".join(datos["pendientes"]))
    return "No tengo tareas que borrar."


# ── Hábitos con rachas ──────────────────────────────────────────────
def _racha_habito(habito):
    """Días consecutivos cumplidos. Si hoy aún no cumple, cuenta desde ayer."""
    dias = habito.get("dias", {})
    meta = habito.get("meta", 1)
    hoy = datetime.date.today()
    if dias.get(str(hoy), 0) < meta:
        hoy -= datetime.timedelta(days=1)
    racha = 0
    while dias.get(str(hoy), 0) >= meta:
        racha += 1
        hoy -= datetime.timedelta(days=1)
    return racha


def _habitologia():
    return _leer_json(HABITOS_PATH, {})


def add_habit(name, goal=1):
    nombre = (name or "").strip().strip('"')
    if not nombre:
        return "¿Cómo se llama el hábito?"
    meta = max(1, min(50, int(float(goal or 1))))
    datos = _habitologia()
    clave = nombre.lower()
    if clave in datos:
        return f"«{nombre}» ya existe: {datos[clave]['dias'].get(str(datetime.date.today()), 0)} de {datos[clave]['meta']} hoy."
    datos[clave] = {"nombre": nombre, "meta": meta, "dias": {}}
    _guardar_json(HABITOS_PATH, datos)
    _aviso("✓ Hábito nuevo")
    return f"Hábito «{nombre}» creado: meta de {meta} por día. Di «registrar {nombre}» cada vez que lo cumplas."


def _habito_por_nombre(name):
    datos = _habitologia()
    clave = (name or "").strip().lower()
    if clave in datos:
        return datos, clave
    for k, h in datos.items():
        if clave and (clave in k or clave in h.get("nombre", "").lower()):
            return datos, k
    return datos, None


def check_habit(name, count=1):
    datos, clave = _habito_por_nombre(name)
    if clave is None:
        habitos = ", ".join(h["nombre"] for h in datos.values()) or "ninguno aún"
        return f"No conozco ese hábito. Tienes: {habitos}."
    h = datos[clave]
    hoy = str(datetime.date.today())
    antes = h.get("dias", {}).get(hoy, 0)
    cuantos = max(1, min(20, int(float(count or 1))))
    nuevo = antes + cuantos
    h.setdefault("dias", {})[hoy] = nuevo
    _guardar_json(HABITOS_PATH, datos)
    _aviso("✓ Registrado")
    _registrar_undo(f"registro de «{h['nombre']}»", lambda: _retroceder_habito(clave))
    meta = h["meta"]
    racha = _racha_habito(h)
    if antes < meta <= nuevo:
        _aviso(f"🎉 ¡Meta cumplida!")
        return (f"¡Meta cumplida para «{h['nombre']}»: {nuevo} de {meta}! "
                f"Racha de {racha} día" + ("s." if racha != 1 else "."))
    return f"«{h['nombre']}»: {nuevo} de {meta} hoy. Racha de {racha} día" + ("s." if racha != 1 else ".")


def _retroceder_habito(clave):
    datos = _habitologia()
    h = datos.get(clave)
    if h:
        hoy = str(datetime.date.today())
        nuevo = max(0, h.get("dias", {}).get(hoy, 0) - 1)
        if nuevo:
            h["dias"][hoy] = nuevo
        else:
            h["dias"].pop(hoy, None)
        _guardar_json(HABITOS_PATH, datos)
    _aviso("Deshago ✓")


def uncheck_habit(name):
    """Quita UN registro del hábito de hoy (missclick / error)."""
    datos, clave = _habito_por_nombre(name)
    if clave is None:
        return "No conozco ese hábito."
    h = datos[clave]
    hoy = str(datetime.date.today())
    antes = h.get("dias", {}).get(hoy, 0)
    if antes <= 0:
        return f"«{h['nombre']}» hoy no tiene registros que quitar."
    _retroceder_habito(clave)
    return (f"Quité un registro de «{h['nombre']}»: "
            f"{max(0, antes - 1)} de {h['meta']} hoy.")


def delete_habit(name):
    """BORRA un hábito de la lista (undo lo revive con racha y todo)."""
    datos, clave = _habito_por_nombre(name)
    if clave is None:
        habitos = ", ".join(h["nombre"] for h in datos.values()) or "ninguno aún"
        return f"No tengo ese hábito. Tienes: {habitos}."
    borrado = datos.pop(clave)
    _guardar_json(HABITOS_PATH, datos)
    _registrar_undo(f"borrado de «{borrado['nombre']}»",
                    lambda: _revivir_habito(clave, borrado))
    _aviso("🗑 Hábito borrado")
    return (f"Hábito «{borrado['nombre']}» borrado. "
            f"Di «deshaz eso» si te arrepientes.")


def _revivir_habito(clave, h):
    datos = _habitologia()
    datos[clave] = h
    _guardar_json(HABITOS_PATH, datos)
    _aviso("Deshago ✓")


def habit_status():
    datos = _habitologia()
    if not datos:
        return "Todavía no tienes hábitos. Di «crea el hábito agua con meta 8»."
    hoy = str(datetime.date.today())
    lineas = []
    cumplidos = 0
    for h in datos.values():
        hecho = h.get("dias", {}).get(hoy, 0)
        if hecho >= h["meta"]:
            cumplidos += 1
        racha = _racha_habito(h)
        emoji = "✅" if hecho >= h["meta"] else "⏳"
        lineas.append(f"  {emoji} {h['nombre']}: {hecho} de {h['meta']} "
                      f"(racha de {racha})")
    return (f"Hoy: {cumplidos} de {len(datos)} hábitos cumplidos.\n"
            + "\n".join(lineas))


def resumen_dia():
    """Frase corta para el parte del mañana y para la GUI."""
    try:
        datos = _leer_json(TAREAS_PATH, {"pendientes": []})
        n_pend = len(datos.get("pendientes", []))
    except Exception:
        n_pend = 0
    try:
        habitos = _habitologia()
        hoy = str(datetime.date.today())
        cumplidos = sum(1 for h in habitos.values()
                        if h.get("dias", {}).get(hoy, 0) >= h.get("meta", 1))
        n_hab = len(habitos)
    except Exception:
        cumplidos, n_hab = 0, 0
    partes = []
    if n_pend:
        partes.append(f"{n_pend} tarea" + ("s" if n_pend != 1 else "") + " pendiente" + ("s" if n_pend != 1 else ""))
    if n_hab:
        partes.append(f"{cumplidos} de {n_hab} hábitos cumplidos hoy")
    return ". ".join(partes) + "." if partes else "Día limpio: sin tareas ni hábitos pendientes."


# ── Enfoque / temporizador ──────────────────────────────────────────
def focus(minutes):
    """Bloque de enfoque (o temporizador): cuenta atrás visible en la isla."""
    try:
        minutos = max(1, min(180, int(float(minutes))))
    except (TypeError, ValueError):
        minutos = 25
    cancelar = threading.Event()
    if _FOCO["cancelar"] is not None:
        _FOCO["cancelar"].set()       # reemplaza el temporizador anterior
    _FOCO["cancelar"] = cancelar
    _FOCO["total"] = minutos * 60          # el anillo del panel lo usa
    threading.Thread(target=_correr_foco, args=(minutos, cancelar),
                     daemon=True).start()
    _registrar_undo(f"enfoque de {minutos} min",
                    lambda: stop_timer() if _FOCO["cancelar"] is cancelar else None)
    return (f"Bloque de enfoque de {minutos} minutos iniciado. La cuenta "
            "va en la isla. ¡A darle, señor!")


def _correr_foco(minutos, cancelar, tick=1.0):
    """Cuenta atrás; `tick` es el paso real en segundos (1.0 en producción;
    más corto solo para pruebas)."""
    restante = int(round(minutos * 60 / tick))
    while restante > 0:
        if cancelar.wait(tick):
            return
        restante -= 1
        total = int(round(restante * tick))
        mm, ss = divmod(total, 60)
        estado.set_crono(f"{mm:02d}:{ss:02d}")
    estado.set_crono("")
    estado.set_aviso("🎉 ¡Enfoque completado!")
    try:
        import tts
        if _WINDOWS:
            for _ in range(3):
                winsound.Beep(880, 250)
                time.sleep(0.12)
        tts.speak(f"Bloque de enfoque de {minutos} minutos terminado. "
                  "¡Buen trabajo, Dante!")
    except Exception:
        pass


def stop_timer():
    """Cancela el temporizador de enfoque activo."""
    cancelar = _FOCO["cancelar"]
    if cancelar is None or cancelar.is_set():
        return "No hay ningún temporizador activo, señor."
    cancelar.set()
    estado.set_crono("")
    return "Temporizador cancelado."


# ═══════════════════════ Correo: GMail con contraseña de aplicación ═══════════════════════

BORRADOR_CORREO = None   # el panel lo mira: dict(body=..., subject=..., to=...)


def _email_cfg():
    """(usuario, contraseña de aplicación) desde config; vacío si no hay."""
    import config
    return ((getattr(config, "EMAIL_USER", "") or "").strip(),
            (getattr(config, "EMAIL_APP_PASS", "") or "").strip())


def draft_email(body, subject="", to=""):
    """Prepara el correo DICTADO y pide al panel abrir el diálogo.

    La dirección NO se dicta (whisper la escucha mal): se escribe en el
    diálogo, donde además se puede editar todo antes de enviar.
    """
    global BORRADOR_CORREO
    dato = (body or "").strip()
    if not dato:
        return "¿Qué quieres que diga el correo?"
    BORRADOR_CORREO = {"body": dato,
                       "subject": (subject or "").strip(),
                       "to": (to or "").strip()}
    _aviso("📧 Borrador listo")
    return ("BORRADOR listo: se abrió un diálogo para que pongas la "
            "dirección, edites el mensaje y lo envíes.")


def send_email(to, subject, body):
    """Envía el correo con el GMail de Dante (SMTP + contraseña de app)."""
    usuario, clave = _email_cfg()
    if not usuario or not clave:
        return ("Falta configurar el correo: en config.py pon EMAIL_USER "
                "y EMAIL_APP_PASS (la contraseña de aplicación de Google; "
                "activa la verificación en 2 pasos primero). Mira el README.")
    destino = (to or "").strip()
    if "@" not in destino:
        return f"«{destino}» no parece una dirección de correo válida."
    import smtplib
    from email.header import Header
    from email.mime.text import MIMEText
    msg = MIMEText(body or "", "plain", "utf-8")
    msg["Subject"] = Header(subject or "(sin asunto)", "utf-8")
    msg["From"] = usuario
    msg["To"] = destino
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(usuario, clave)
            srv.sendmail(usuario, [destino], msg.as_string())
    except Exception as exc:
        return (f"No pude enviar el correo: {type(exc).__name__}: {exc}. "
                "Revisa EMAIL_USER y EMAIL_APP_PASS en config.py.")
    _aviso("📧 Enviado")
    return f"Correo enviado a {destino}."


# ═══════════════════════ GitHub: commit + push (estilo GitHub Desktop) ═══════════════════════

_NO_VENTANA = 0x08000000 if os.name == "nt" else 0   # no abrir consolas negras


def _git_exe():
    """git del PATH o el que trae GitHub Desktop adentro."""
    cual = shutil.which("git")
    if cual:
        return cual
    patron = os.path.expandvars(
        r"%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe")
    hallados = sorted(__import__("glob").glob(patron))
    return hallados[-1] if hallados else None


def _git(carpeta, *args):
    """Corre un git -C carpeta <args>; devuelve stdout o lanza error claro."""
    exe = _git_exe()
    if exe is None:
        raise FileNotFoundError(
            "no encontré git (ni el que viene con GitHub Desktop)")
    kwargs = {"capture_output": True, "text": True, "encoding": "utf-8",
              "errors": "replace", "timeout": 90}
    if os.name == "nt":
        kwargs["creationflags"] = _NO_VENTANA
    r = subprocess.run([exe, "-C", str(carpeta), *args], **kwargs)
    if r.returncode != 0:
        lineas = (r.stderr or r.stdout or "").strip().splitlines()
        raise RuntimeError(lineas[-1] if lineas else f"git {args[0]} falló")
    return (r.stdout or "").strip()


def github_push(folder, repo="", message=""):
    """Commit de TODOS los cambios de una carpeta + push al repo.

    GitHub Desktop deja las credenciales guardadas en Windows: el push
    sale solo, sin pedir claves.
    """
    bruto = (folder or "").strip().strip('"')
    carpeta = Path(FOLDER_ALIASES.get(bruto.lower(), bruto))
    if not carpeta.exists():
        return (f"No encontré la carpeta «{folder}». Pásame la ruta "
                "completa del proyecto.")
    try:
        _git(carpeta, "rev-parse", "--is-inside-work-tree")
    except (FileNotFoundError, RuntimeError) as exc:
        return (f"«{folder}» no es un repo de git (o {exc}). Ábrela una "
                "vez en GitHub Desktop y vuelve a intentarlo.")
    cambios = _git(carpeta, "status", "--porcelain")
    if not cambios:
        return f"En «{carpeta.name}» no hay cambios que subir, señor."
    n = len([l for l in cambios.splitlines() if l.strip()])
    _git(carpeta, "add", "-A")
    commit = (message or "").strip() or ("cambios del "
                                        + datetime.date.today().isoformat())
    _git(carpeta, "commit", "-m", commit)
    remotos = _git(carpeta, "remote").split()
    destino = ""
    if remotos:
        if repo:
            clave = repo.strip().lower().strip("/")
            for r in remotos:
                if clave in _git(carpeta, "remote", "get-url", r).lower():
                    destino = r
                    break
        if not destino:
            destino = ("origin" if "origin" in remotos else remotos[0])
    if not destino:
        return (f"Hice el commit en «{carpeta.name}», pero la carpeta no "
                "tiene remotos: ábrela en GitHub Desktop, publícala y "
                "pídeme el push otra vez.")
    rama = _git(carpeta, "rev-parse", "--abbrev-ref", "HEAD") or "main"
    _git(carpeta, "push", destino, "HEAD")
    _aviso("🚀 Push listo")
    return (f"Commit «{commit}» con {n} archivos y push de la rama "
            f"«{rama}» a {destino}. Enhorabuena, señor.")


# ═══════════════════════ Esquemas para el LLM ═══════════════════════

TOOLS_JSON = [
    {"type": "function", "function": {
        "name": "get_time", "description": "Hora actual.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_date", "description": "Fecha de hoy: día de la semana, día, mes y año.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "open_app",
        "description": "Abre una aplicación: chrome, vscode, spotify, discord, whatsapp, calculadora, notepad, paint, word, excel, minecraft, configuración...",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string", "description": "Nombre común de la app"}},
                       "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "open_website",
        "description": "Abre una página web por URL (ej: youtube.com).",
        "parameters": {"type": "object",
                       "properties": {"url": {"type": "string"}},
                       "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Busca algo en Google y abre los resultados.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "play_youtube",
        "description": "Busca algo en YouTube y abre los resultados (para música o videos).",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "system_status",
        "description": "Reporta CPU, RAM, disco y batería del equipo.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "organize_desktop",
        "description": "Organiza los archivos del escritorio en carpetas por tipo (imágenes, documentos, videos, otros).",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "set_reminder",
        "description": "Programa un recordatorio hablado a una hora exacta.",
        "parameters": {"type": "object",
                       "properties": {
                           "message": {"type": "string", "description": "Qué recordar"},
                           "when": {"type": "string", "description": "Fecha y hora: YYYY-MM-DD HH:MM"}},
                       "required": ["message", "when"]}}},
    {"type": "function", "function": {
        "name": "set_volume",
        "description": "Sube o baja el volumen del sistema a un porcentaje (0-100).",
        "parameters": {"type": "object",
                       "properties": {"percent": {"type": "integer"}},
                       "required": ["percent"]}}},
    {"type": "function", "function": {
        "name": "create_note",
        "description": "Guarda una nota de texto con fecha en el archivo de notas de Jarvis.",
        "parameters": {"type": "object",
                       "properties": {"text": {"type": "string"}},
                       "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "open_folder",
        "description": "Abre una carpeta del sistema: escritorio, descargas, documentos, imagenes, videos, musica, canciones — o una ruta completa (ej: C:\\Users\\Dante\\Music\\canciones).",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string"}},
                       "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "play_local_music",
        "description": "Reproduce una canción AL AZAR de una carpeta de música local (por defecto la carpeta 'canciones' dentro de Música).",
        "parameters": {"type": "object",
                       "properties": {"folder": {"type": "string",
                                                 "description": "canciones | musica | o una ruta completa"}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "show_desktop",
        "description": "Minimiza todas las ventanas y muestra el escritorio (como Win+D).",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "search_online",
        "description": "Busca en internet SIN abrir el navegador y devuelve los hallazgos para responder en voz alta. Úsala para datos específicos: specs técnicas, consumo, precios, personas, fechas, actualidad. El usuario sigue usando el PC mientras.",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "create_document",
        "description": "Crea un documento Word con un texto, fuente y tamaño de letra, y lo abre. Ej: 'hola muchachos' en Comic Sans tamaño 72.",
        "parameters": {"type": "object",
                       "properties": {"content": {"type": "string", "description": "El texto del documento"},
                                      "font": {"type": "string", "description": "Fuente: Comic Sans, Arial, Calibri..."},
                                      "size": {"type": "integer", "description": "Tamaño de letra en puntos (pt)"},
                                      "filename": {"type": "string", "description": "Nombre o ruta completa, ej: C:\\\\Users\\\\Dante\\\\Desktop\\\\saludo.docx"}},
                       "required": ["content"]}}},
    {"type": "function", "function": {
        "name": "remember",
        "description": "Guarda en la memoria duradera de Jarvis un dato para todas las sesiones futuras. Úsala cuando Dante diga 'recuerda que...', 'aprende...', 'no olvides...' o comparta gustos, datos de sus proyectos o preferencias.",
        "parameters": {"type": "object",
                       "properties": {"text": {"type": "string", "description": "El dato a recordar, en una frase"}},
                       "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "undo",
        "description": "Deshace la última acción reversible (documentos, notas, recuerdos, organización del escritorio, volumen, recordatorios). Úsala cuando Dante diga 'deshaz eso', 'deshazlo', 'cancela lo último' o se arrepienta de algo. Cada llamada deshace UNA acción, la más reciente.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "create_code",
        "description": "Escribe un archivo de código en el Escritorio y lo abre. Úsala cuando Dante pida 'créame/hazme un script/programa/archivo de código' de cualquier lenguaje (python, javascript, html, batch, c...). El contenido va COMPLETO en 'content'.",
        "parameters": {"type": "object",
                       "properties": {"filename": {"type": "string", "description": "Nombre del archivo, ej: 'juego.py'. Sin extensión se añade la del lenguaje"},
                                      "content": {"type": "string", "description": "El código COMPLETO a guardar"},
                                      "language": {"type": "string", "description": "Lenguaje: python, javascript, html, css, batch, java, c, cpp, json, texto"}},
                       "required": ["filename", "content"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Lee un archivo de texto de su PC y devuelve su contenido para resumirlo, explicarlo o modificarlo. Úsala cuando Dante diga 'lee X', 'qué hay en X', 'muéstrame X', 'analiza X'. Rutas relativas se buscan en el Escritorio.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "Nombre o ruta del archivo"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_python",
        "description": "Escribe y EJECUTA un script de Python real en su PC y devuelve la salida. Úsala cuando Dante pida 'ejecuta este código', 'prueba esto', 'corre este script' o quiera ver el resultado de un programa.",
        "parameters": {"type": "object",
                       "properties": {"code": {"type": "string", "description": "El código Python COMPLETO a ejecutar"},
                                      "filename": {"type": "string", "description": "Nombre opcional para el script"}},
                       "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Calcula una expresión matemática de forma EXACTA (multiplicaciones, potencias, porcentajes, raíces, trigonometría). Úsala SIEMPRE que haya un cálculo concreto, no lo hagas de cabeza.",
        "parameters": {"type": "object",
                       "properties": {"expression": {"type": "string", "description": "La expresión, ej: '17*43', 'sqrt(144)', '(1250-320)*0.19'"}},
                       "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "list_files",
        "description": "Lista lo que hay en una carpeta de su PC (escritorio, descargas, documentos, música, imágenes, videos, o una ruta completa). Úsala cuando Dante pregunte 'qué hay en X' o quiera explorar carpetas.",
        "parameters": {"type": "object",
                       "properties": {"folder": {"type": "string", "description": "Carpeta: escritorio, descargas, documentos, música, imágenes, videos o ruta completa"}},
                       "required": ["folder"]}}},
    {"type": "function", "function": {
        "name": "look_screen",
        "description": "TUS OJOS: captura la pantalla de Dante ahora mismo y te la manda como imagen para que la veas. Úsala cuando diga «mira», «mira mi pantalla», «mira lo que estoy haciendo», «qué error ves», «qué hay abierto» o quieras ACTUAR según lo que pasa en pantalla. Después de verla, describe lo relevante y ejecuta las herramientas que toquen.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "add_task",
        "description": "Anota una tarea en la lista de pendientes de Dante. Úsala cuando diga «anota una tarea X», «agrégame a la lista X», «tengo que hacer X».",
        "parameters": {"type": "object",
                       "properties": {"text": {"type": "string", "description": "La tarea en pocas palabras"}},
                       "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "complete_task",
        "description": "Marca una tarea como hecha (por número o por nombre aproximado). Úsala cuando diga «ya hice X», «completé X», «tacha X», «terminé X».",
        "parameters": {"type": "object",
                       "properties": {"match": {"type": "string", "description": "Nombre o número de la tarea"}},
                       "required": ["match"]}}},
    {"type": "function", "function": {
        "name": "uncomplete_task",
        "description": "Devuelve una tarea HECHA a pendientes (por si la marcó por error). Úsala cuando diga «la marqué sin querer», «descompleta X», «esa aún no está hecha».",
        "parameters": {"type": "object",
                       "properties": {"match": {"type": "string", "description": "Nombre o número de la tarea hecha"}},
                       "required": ["match"]}}},
    {"type": "function", "function": {
        "name": "delete_task",
        "description": "BORRA una tarea de la lista (pendiente o hecha; se puede deshacer). Úsala cuando diga «borra la tarea X», «elimina X de la lista», «quita X».",
        "parameters": {"type": "object",
                       "properties": {"match": {"type": "string", "description": "Nombre o número de la tarea a borrar"}},
                       "required": ["match"]}}},
    {"type": "function", "function": {
        "name": "list_tasks",
        "description": "Lista las tareas pendientes de Dante. Úsala cuando diga «qué tengo pendiente», «mis tareas», «qué me toca hacer».",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "add_habit",
        "description": "Crea un hábito nuevo con una meta diaria (ej: agua, 8 vasos). Úsala cuando diga «créa el hábito X con meta N».",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string", "description": "Nombre del hábito"},
                                      "goal": {"type": "number", "description": "Meta diaria (default 1)"}},
                       "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "check_habit",
        "description": "Registra que Dante cumplió su hábito ahora (cuenta racha y celebra al llegar a la meta). Úsala cuando diga «registrar hábito X», «tomé agua», «ya leí», «hice X» siendo X un hábito.",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string", "description": "Nombre del hábito"},
                                      "count": {"type": "number", "description": "Cuántas veces lo cumplió ahora (default 1)"}},
                       "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "uncheck_habit",
        "description": "Quita UN registro del hábito de hoy (por si se registró por error). Úsala cuando diga «me equivoqué», «quita el registro de X», «sin querer registré X».",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string", "description": "Nombre del hábito"}},
                       "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "delete_habit",
        "description": "BORRA un hábito de la lista (se puede deshacer). Úsala cuando diga «borra el hábito X», «elimina el hábito X», «ya no quiero el hábito X».",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string", "description": "Nombre del hábito a borrar"}},
                       "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "habit_status",
        "description": "Resumen de los hábitos de hoy: progreso y rachas. Úsala cuando diga «cómo van mis hábitos», «mi progreso de hoy».",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "focus",
        "description": "Inicia un bloque de enfoque o temporizador con cuenta atrás visible en la isla; al terminar NEXUS lo anuncia en voz alta. Úsala cuando diga «enfoque 25 minutos», «concéntreme 25 minutos», «temporizador de 5 minutos», «cuenta 10 minutos».",
        "parameters": {"type": "object",
                       "properties": {"minutes": {"type": "number", "description": "Duración en minutos (default 25)"}},
                       "required": ["minutes"]}}},
    {"type": "function", "function": {
        "name": "stop_timer",
        "description": "Cancela el temporizador de enfoque activo. Úsala cuando diga «cancela el temporizador», «ya no necesito el enfoque».",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "draft_email",
        "description": "Prepara un correo GMail dictado por Dante y abre un diálogo en pantalla para que ponga la dirección, edite el texto y envíe. Úsala cuando diga «envía un correo», «mándale un correo», «envía este correo» y te diga el contenido. El mensaje dictado va COMPLETO en body; la dirección NO se dicta (se escribe en el diálogo; solo ponla en to si Dante la dijo claramente).",
        "parameters": {"type": "object",
                       "properties": {
                           "body": {"type": "string", "description": "El mensaje del correo, completo"},
                           "subject": {"type": "string", "description": "Asunto corto (opcional)"},
                           "to": {"type": "string", "description": "Dirección del destinatario SOLO si la dijo claramente (opcional)"}},
                       "required": ["body"]}}},
    {"type": "function", "function": {
        "name": "send_email",
        "description": "Envía YA un correo GMail con la cuenta configurada de Dante (smtp.gmail.com). Úsala SOLO cuando el destinatario ya está confirmado; para correos dictados por voz usa draft_email.",
        "parameters": {"type": "object",
                       "properties": {
                           "to": {"type": "string", "description": "Dirección del destinatario"},
                           "subject": {"type": "string", "description": "Asunto"},
                           "body": {"type": "string", "description": "El mensaje"}},
                       "required": ["to", "body"]}}},
    {"type": "function", "function": {
        "name": "github_push",
        "description": "Hace commit de TODOS los cambios de una carpeta y push al repo de GitHub (las credenciales de GitHub Desktop ya están guardadas). Úsala cuando diga «en esta carpeta hice cambios, haz commit y push», «sube los cambios de X», «commit y push al repo Y».",
        "parameters": {"type": "object",
                       "properties": {
                           "folder": {"type": "string", "description": "Carpeta del proyecto (ruta completa, ej: C:\\\\Users\\\\Dante\\\\proyectos\\\\web)"},
                           "repo": {"type": "string", "description": "Nombre del repo de GitHub (opcional)"},
                           "message": {"type": "string", "description": "Mensaje del commit (opcional)"}},
                       "required": ["folder"]}}},
]

_IMPLEMENTATIONS = {
    "get_time": lambda a: get_time(),
    "get_date": lambda a: get_date(),
    "open_app": lambda a: open_app(a["name"]),
    "open_website": lambda a: open_website(a.get("url", "")),
    "search_web": lambda a: search_web(a.get("query", "")),
    "play_youtube": lambda a: play_youtube(a.get("query", "")),
    "system_status": lambda a: system_status(),
    "organize_desktop": lambda a: organize_desktop(),
    "set_reminder": lambda a: set_reminder(a.get("message", ""), a.get("when", "")),
    "set_volume": lambda a: set_volume(a.get("percent", 50)),
    "create_note": lambda a: create_note(a.get("text", "")),
    "open_folder": lambda a: open_folder(a.get("name", "")),
    "play_local_music": lambda a: play_local_music(a.get("folder", "canciones")),
    "show_desktop": lambda a: show_desktop(),
    "search_online": lambda a: search_online(a.get("query", "")),
    "create_document": lambda a: create_document(a.get("content", ""),
                                                a.get("font", "Calibri"),
                                                a.get("size", 11),
                                                a.get("filename")),
    "remember": lambda a: remember(a.get("text", "")),
    "undo": lambda a: undo(),
    "create_code": lambda a: create_code(a.get("filename", ""), a.get("content", ""),
                                         a.get("language", "python")),
    "read_file": lambda a: read_file(a.get("path", "")),
    "run_python": lambda a: run_python(a.get("code", ""), a.get("filename")),
    "calculate": lambda a: calculate(a.get("expression", "")),
    "list_files": lambda a: list_files(a.get("folder", "escritorio")),
    "look_screen": lambda a: look_screen(),
    "add_task": lambda a: add_task(a.get("text", "")),
    "complete_task": lambda a: complete_task(a.get("match", "")),
    "uncomplete_task": lambda a: uncomplete_task(a.get("match", "")),
    "delete_task": lambda a: delete_task(a.get("match", "")),
    "list_tasks": lambda a: list_tasks(),
    "add_habit": lambda a: add_habit(a.get("name", ""), a.get("goal", 1)),
    "check_habit": lambda a: check_habit(a.get("name", ""), a.get("count", 1)),
    "uncheck_habit": lambda a: uncheck_habit(a.get("name", "")),
    "delete_habit": lambda a: delete_habit(a.get("name", "")),
    "habit_status": lambda a: habit_status(),
    "focus": lambda a: focus(a.get("minutes", 25)),
    "stop_timer": lambda a: stop_timer(),
    "draft_email": lambda a: draft_email(a.get("body", ""),
                                         a.get("subject", ""),
                                         a.get("to", "")),
    "send_email": lambda a: send_email(a.get("to", ""),
                                        a.get("subject", ""),
                                        a.get("body", "")),
    "github_push": lambda a: github_push(a.get("folder", ""),
                                         a.get("repo", ""),
                                         a.get("message", "")),
}


def execute(name, args):
    """Punto único de ejecución de herramientas; siempre devuelve texto."""
    funcion = _IMPLEMENTATIONS.get(name)
    if funcion is None:
        return f"Herramienta desconocida: {name}"
    try:
        return str(funcion(args or {}))
    except Exception as exc:
        return f"Error ejecutando {name}: {exc}"
