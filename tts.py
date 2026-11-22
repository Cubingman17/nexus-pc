"""Síntesis de voz: edge-tts bilingüe (es-CO + en-US) con fallback SAPI.

El LLM marca los nombres en inglés con <en>...</en>; `segmentar()` parte el
texto y cada segmento se sintetiza con la voz de su idioma.
"""
import os
import re
import tempfile

import config

# voces: español latino e inglés (respetamos si cambió TTS_VOICE en config)
_ES_VOICE = getattr(config, "TTS_VOICE", None) or getattr(
    config, "VOICE", "es-CO-GonzaloNeural")
_EN_VOICE = getattr(config, "EN_VOICE", "en-US-GuyNeural")
_RATE = getattr(config, "TTS_RATE", "+3%")
# GANANCIA de la voz: se oía muy pasito. tanh comprime suave, así que
# 2.2 suena MÁS FUERTE sin reventar (sube o baja en config.py)
_GAIN = float(getattr(config, "TTS_GAIN", 2.2))

try:
    import edge_tts  # noqa: F401
    import pygame
    import pygame.sndarray  # noqa: F401
    _EDGE = True
except Exception:
    _EDGE = False

# ── Fish Audio: la voz española que Dante eligió ────────────────────
_FISH_URL = "https://api.fish.audio/v1/tts"


def _fish_lista():
    """¿Fish Audio está configurado? (API key + voz puestas en config)"""
    return bool((getattr(config, "FISH_API_KEY", "") or "").strip()
                and (getattr(config, "FISH_VOICE_ID", "") or "").strip())


def _hablar_fish(texto):
    """Sintetiza con Fish Audio (reference_id = la voz elegida) y lo toca.

    La voz Fish habla español E inglés con el mismo timbre, así que NO
    se parte en segmentos: todo el texto de una. Si falla, speak() cae
    a edge-tts sin morir.
    """
    import json
    import urllib.request

    cuerpo = json.dumps({
        "text": texto,
        "reference_id": getattr(config, "FISH_VOICE_ID", "").strip(),
        "normalize": True,     # fechas y números dichos como gente
        "format": "mp3",
    }).encode("utf-8")
    pedido = urllib.request.Request(
        _FISH_URL, data=cuerpo,
        headers={
            "Authorization": "Bearer "
                             + getattr(config, "FISH_API_KEY", "").strip(),
            "Content-Type": "application/json",
            "model": getattr(config, "FISH_MODEL", "s2.1-pro-free"),
        })
    with urllib.request.urlopen(pedido, timeout=45) as r:
        audio = r.read()
    if not audio or len(audio) < 200:
        raise RuntimeError("Fish Audio devolvió audio vacío")

    import time
    import pygame
    fd, ruta = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    with open(ruta, "wb") as f:
        f.write(audio)
    try:
        _asegurar_mixer()
        _tocar(ruta)
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass

# limpiar mp3s viejos de sesiones pasadas (podrían quedar bloqueados)
try:
    for _viejo in os.listdir(tempfile.gettempdir()):
        if _viejo.startswith("jarvis_voice") or _viejo.startswith("tmp"):
            if _viejo.endswith(".mp3"):
                try:
                    os.remove(os.path.join(tempfile.gettempdir(), _viejo))
                except OSError:
                    pass
except Exception:
    pass


def _sub(texto):
    return re.sub(r"\s+", " ", (texto or "").strip())


def segmentar(texto):
    """Parte el texto en [(idioma, texto)] usando marcas <en>...</en>.

    Los segmentos vacíos se descartan; lo que no está marcado es español.
    """
    partes = []
    resto = _sub(texto)
    pos = 0
    for m in re.finditer(r"<en>(.*?)</en>", resto, flags=re.IGNORECASE | re.DOTALL):
        antes = resto[pos:m.start()]
        if antes.strip():
            partes.append(("es", _sub(antes)))
        if m.group(1).strip():
            partes.append(("en", _sub(m.group(1))))
        pos = m.end()
    cola = resto[pos:]
    if cola.strip():
        partes.append(("es", _sub(cola)))
    return partes


def _hablable(texto):
    """Quita el markdown que el LLM suelta a veces (*negrita*, viñetas…):
    la voz NO debe decir 'asterisco'."""
    t = texto or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)      # bloques de código
    t = re.sub(r"`([^`]*)`", r"\1", t)                # código inline
    t = t.replace("*", " ").replace("~~", " ").replace("__", " ")
    t = re.sub(r"(?m)^\s*[-•]\s+", "", t)              # viñetas
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)            # encabezados
    t = re.sub(r"(?m)^\s*\d+\.\s+", r"", t)            # "1. " al inicio de línea
    return re.sub(r"[ \t]+", " ", t).strip()


def plano(texto):
    """Texto limpio sin marcas <en> NI markdown (para subtítulos y consola)."""
    return _sub(_hablable(re.sub(r"</?en>", "", texto or "", flags=re.IGNORECASE)))


# --- API pública ----------------------------------------------------------

_EMERGENCIA = "es-CO-GonzaloNeural"  # si tu voz elegida no existe en edge-tts


def _voces_para(voz=None):
    """Qué voz usa cada idioma. Las 'Multilingual' (HD) sirven para las dos."""
    if voz and "Multilingual" in voz:
        return {"es": voz, "en": voz}
    return {"es": voz or _ES_VOICE, "en": voz or _EN_VOICE}


def speak(texto, voz=None):
    """Pronuncia el texto y marca el estado 'hablando' si hay GUI.

    Orden de voces: Fish Audio (si pusiste la API key) → edge-tts →
    voz de Windows. Nunca queda mudo por gustos.
    voz: opcional — prueba una voz edge-tts específica (menú --voces).
    """
    try:
        from estado import set_hablando, set_esperando
    except Exception:
        set_hablando = set_esperando = None
    try:
        set_hablando()
    except Exception:
        pass
    limpio = _hablable(texto)
    try:
        hecho = False
        if _fish_lista() and not voz:      # la voz Fish manda si está puesta
            try:
                _hablar_fish(plano(limpio))
                hecho = True
            except Exception as exc:
                print(f"[Fish Audio falló: {type(exc).__name__}: {exc}] "
                      f"→ sigo con edge-tts]")
        if not hecho:
            if _EDGE:
                _hablar_edge(limpio, voz)
            else:
                _fallback_windows(limpio)
    except Exception as exc:
        print(f"[voz caída: {type(exc).__name__}: {exc}] → usando voz de Windows")
        try:
            _fallback_windows(texto)
        except Exception as exc2:
            print(f"[voz de Windows también falló: {exc2}]")
            pass  # mudo pero vivo: el pipeline sigue
    finally:
        try:
            set_esperando()
        except Exception:
            pass


def chime():
    """Beep de confirmación al detectar la wake word (cosmético, blindado)."""
    try:
        import numpy as np
        import pygame
        _asegurar_mixer()
        sr = 16000
        t = np.linspace(0, 0.18, int(sr * 0.18), False)
        freqs = np.where(t < 0.09, 880.0, 1320.0)
        onda = (np.sin(2 * np.pi * freqs * t) * 26000).astype(np.int16)
        audio = np.column_stack((onda, onda))  # estéreo
        pygame.sndarray.make_sound(audio).play()
        import time as _time
        _deadline = _time.time() + 0.3
        while pygame.mixer.get_busy() and _time.time() < _deadline:
            _time.sleep(0.02)
    except Exception:
        pass


# --- internas -------------------------------------------------------------

def _hablar_edge(texto, voz=None):
    """Sintetiza cada segmento con su voz y los reproduce en orden.

    Si la voz elegida no existe en edge-tts, reintenta con Gonzalo antes
    de caer a la voz robótica de Windows: nunca mudo por gustos.
    """
    voces = _voces_para(voz)
    try:
        _sintetizar_y_reproducir(texto, voces)
    except Exception as exc:
        if voces["es"] != _EMERGENCIA:
            print(f"[voz '{voces['es']}' falló: {type(exc).__name__}: {exc}] "
                  f"→ reintentando con {_EMERGENCIA}")
            _sintetizar_y_reproducir(texto, _voces_para(_EMERGENCIA))
        else:
            raise


def _sintetizar_y_reproducir(texto, voces):
    import asyncio
    import time

    import edge_tts
    import pygame

    segmentos = segmentar(texto) or [("es", plano(texto))]
    rutas = []
    _asegurar_mixer()
    try:
        for i, (idioma, trozo) in enumerate(segmentos):
            fd, ruta = tempfile.mkstemp(suffix=f"_{i}.mp3")
            os.close(fd)
            rutas.append(ruta)

        async def _uno(i=i, idioma=idioma, trozo=trozo):
            com = edge_tts.Communicate(trozo, voces[idioma], rate=_RATE)
            await com.save(rutas[i])

        async def _todos():
            # TODOS los segmentos en PARALELO: el primero suena en ~1 segundo
            # aunque la respuesta tenga muchas frases (antes sumaba una por una)
            await asyncio.gather(*[
                _uno(i, idioma, trozo)
                for i, (idioma, trozo) in enumerate(segmentos)])

        asyncio.run(_todos())

        # reproducir SECUENCIAL para que no se enciman las voces
        for ruta in rutas:
            _tocar(ruta)
    finally:
        for ruta in rutas:
            try:
                os.remove(ruta)
            except OSError:
                pass


def _tocar(ruta):
    """Reproduce un mp3 con GANANCIA: tanh comprime suave, así que la
    voz suena más fuerte SIN distorsionar (el volumen 1.0 de pygame
    se quedaba corto: se oía muy pasito)."""
    import time

    import pygame
    _asegurar_mixer()
    sonido = pygame.mixer.Sound(ruta)
    if _GAIN > 1.0:
        try:
            import numpy as np
            import pygame.sndarray
            arr = pygame.sndarray.array(sonido).astype(np.float64)
            arr = np.tanh(arr / 32768.0 * _GAIN) * 32000.0
            sonido = pygame.sndarray.make_sound(arr.astype(np.int16))
        except Exception:
            pass          # sin numpy: se toca tal cual, nunca mudo
    sonido.play()
    while pygame.mixer.get_busy():
        time.sleep(0.03)
    sonido.stop()  # por si el mixer se queda colgado con "busy" falso


def _fallback_windows(texto):
    """Plan B: voz de Windows vía PowerShell (offline, cero dependencias).

    Elige una voz es-* si hay instalada y lee el texto plano (sin marcas).
    """
    import subprocess
    limpio = plano(texto).replace("'", "''")  # PowerShell escapa comillas así
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.Volume = 100;"
        "try { $v = $s.GetInstalledVoices()"
        " | Where-Object {$_.GetInstalledVoiceInfo().Culture.Name -like 'es-*'}"
        " | Select-Object -First 1; if ($v) { $s.SelectVoice($v.VoiceInfo.Name) } } catch {};"
        f"$s.Speak('{limpio}');"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   check=False, creationflags=flags)


# ── menú de voces: córrelo con  py -3.12 main.py --voces ──────────────

DEMO_VOCES = [
    "en-GB-RyanMultilingualNeural",    # ★ JARVIS: británico elegante, es+en
    "en-GB-NoahMultilingualNeural",    # británico joven, cálido, es+en
    "en-GB-OliverMultilingualNeural",  # británico serio, es+en
    "en-GB-ThomasMultilingualNeural",  # británico energético, es+en
    "en-US-AndrewMultilingualNeural",   # mayordomo HD premium: español e inglés
    "en-US-BrianMultilingualNeural",   # HD masculina joven
    "en-US-AvaMultilingualNeural",     # HD femenina
    "es-ES-AlvaroNeural",               # España, grave y dramática
    "es-MX-JorgeNeural",               # México, cálida
    "es-CO-GonzaloNeural",             # Colombia (la de siempre)
    "es-CO-SalomeNeural",              # Colombia femenina
    "es-ES-ElviraNeural",              # España femenina
]


def _voz_disponible(voz):
    """¿Existe esta voz en edge-tts? Sintetiza 3 palabras en silencio."""
    import asyncio

    import edge_tts
    fd, ruta = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        async def _run():
            com = edge_tts.Communicate("uno dos tres", voz, rate=_RATE)
            await com.save(ruta)
        asyncio.run(_run())
        return os.path.getsize(ruta) > 100
    except Exception:
        return False
    finally:
        try:
            os.remove(ruta)
        except OSError:
            pass


def demo_voces():
    """Escucha una frase con cada voz y elige tu favorita para el config."""
    print("\n🎧 DEMO DE VOCES — ponte los audífonos y anota la que te guste\n")
    buenas = []
    for voz in DEMO_VOCES:
        if not _voz_disponible(voz):
            print(f"❌ {voz} — no disponible en tu versión de edge-tts\n")
            continue
        buenas.append(voz)
        print(f"▶ {voz}")
        speak("Hola Dante. Así suena esta voz, señor. ¿Me la dejas puesta?", voz=voz)
        print()
    if not buenas:
        print("Ninguna voz funcionó: revisa el internet (edge-tts lo necesita).")
        return
    print("Para dejar una fija → abre config.py → pega tu favorita en TTS_VOICE.")
    print("Si es una 'Multilingual' habla español E inglés con la misma voz;\n"
          "si no, EN_VOICE se encarga del inglés.")


# compat con imports viejos
_Voz = speak


def _asegurar_mixer():
    """El mixer DEBE existir antes de reproducir; si ya está, no se toca."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=16000, size=-16, channels=2)
    except Exception:
        pass  # si no se puede, speak() caerá al plan B y lo reportará


# arranque: inicializar apenas importamos para que ni el chime falle
_asegurar_mixer()
