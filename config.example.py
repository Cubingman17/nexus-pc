"""PLANTILLA de configuración de NEXUS — SIN claves reales.
Copia este archivo a config.py y pega ahí tus llaves (o usa las
variables de entorno LLM_API_KEY / FISH_API_KEY / EMAIL_APP_PASS).
config.py está en .gitignore: nunca se sube al repositorio.
"""
"""Configuración central de NEXUS — edita SOLO este archivo."""
import os

# ══ Cerebro (elige tu proveedor) ══════════════════════════════════
#   "mistral"   → ★ SOLO NUBE (lo que se usa ahora): rápido y listo.
#                 El local (Ollama) quedó fuera: en tu CPU era lento
#                 (~15-25 s) y respondía bobo.
#   "groq"      → GRATIS (console.groq.com/keys, rapidísimo, modelos Llama)
#   "deepseek"  → baratísimo por uso (~$0.15/$0.60 por millón off-peak; carga saldo en platform.deepseek.com)
#   "openai"    → ChatGPT real, pero DE PAGO (tarjeta + saldo en platform.openai.com)
#   "auto"      → nube si hay internet, local si te quedas sin conexión
#   "ollama"    → 100% local (solo si algún día lo quieres de vuelta)
PROVIDER = "mistral"
CLOUD_PROVIDER = "mistral"   # a qué nube ir en modo "auto" (mistral/groq/deepseek/openai)
# 🧠 CEREBRO — ¿qué modelo? (vacío = el recomendado de cada proveedor)
# Sube de modelo pegando acá el nombre, ej:
#   LLM_MODEL = "mistral-large-latest"     # mucho más listo
#   LLM_MODEL = "mistral-medium-latest"     # todoterreno
LLM_MODEL = "mistral-small-latest"
# Si Ollama NO está corriendo, NEXUS cae aquí solo (nunca queda mudo):
LLM_FALLBACK = "mistral"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")   # pégala aquí abajo si prefieres:
# LLM_API_KEY = ""
# 🧠 CEREBRO — ¿qué modelo? (vacío = el recomendado de cada proveedor)
# Si usas la nube (mistral), sube de modelo pegando acá el nombre, ej:
#   LLM_MODEL = "mistral-large-latest"     # mucho más listo
#   LLM_MODEL = "mistral-medium-latest"     # todoterreno
# OJO: con PROVIDER="ollama" este LLM_MODEL es el modelo LOCAL; el
# fallback de la nube usa su modelo por defecto (mistral-small-latest).
LLM_MAX_TOKENS = 0    # 0 = automático: 400 local (cada token cuesta CPU) / 800 nube
# Herramientas en modo LOCAL: "esenciales" = 17 rápidas (por defecto);
# "todas" = las 36 completas (más lento: más tokens que leer por turno)
LOCAL_TOOLS = "esenciales"

# ══ Oído (Whisper local, no gasta internet) ═══════════════════════
WHISPER_MODEL = "small"     # tiny (rapidísimo) / base / small (mejor español)
WHISPER_DEVICE = "cpu"       # el Ryzen 5 5500U lo maneja sobrado
LANGUAGE = "es"

# ══ Voz (edge-tts: voces neuronales de Microsoft, gratis, sin key) ══
TTS_VOICE = "en-GB-RyanMultilingualNeural"  # ★ voz JARVIS: británico elegante, español E inglés
# Menú de voces — córrelo con:  py -3.12 main.py --voces   (escucha y elige)
#   en-GB-RyanMultilingualNeural    ★ JARVIS británico elegante (multilingüe)
#   en-GB-NoahMultilingualNeural    británico joven, cálido (multilingüe)
#   en-GB-OliverMultilingualNeural  británico serio (multilingüe)
#   en-GB-ThomasMultilingualNeural  británico energético (multilingüe)
#   en-US-AndrewMultilingualNeural  mayordomo HD premium (multilingüe)
#   en-US-BrianMultilingualNeural   joven, natural (multilingüe)
#   en-US-AvaMultilingualNeural     femenina HD (multilingüe)
#   es-CO-GonzaloNeural             Colombia (la clásica de siempre)
#   es-CO-SalomeNeural              Colombia femenina
# Si la voz suena robótica o cae a la colombiana sola, actualiza edge-tts:
#   py -3.12 -m pip install -U edge-tts
# Las "Multilingual" pronuncian bien español e inglés con el mismo timbre.
EN_VOICE = "en-US-GuyNeural"  # inglés — solo se usa si TTS_VOICE NO es multilingüe
TTS_RATE = "+3%"   # ritmo: "-10%" más pausado / "+10%" más rápido
TTS_GAIN = 2.2     # volumen de la voz: 1.0 = como viene (quedaba pasito);
                   # 2.2 = bien fuerte sin distorsionar. 3.0 = a todo dar

# ══ Wake word — ya NO tienes que hablar en gringo ══════════════════
WAKE_WORD = "hey_jarvis"    # openWakeWord trae este modelo precompilado y gratis
WAKE_THRESHOLD = 0.60       # 0.60: si se activaba SOLO sube a 0.7 / si no te oye baja a 0.5
WAKE_MODE = "ambos"         # "onnx" (hey Jarvis gringo) | "whisper" (nexus natural) | "ambos"
WAKE_FRASES = ["nexus", "nexo", "jarvis"]
# ↑ con que el audio CONTENGA una de estas palabras dispara (sin tildes,
#   mayúsculas o acento importan): vale «nexus», «hey nexus», «oye nexus»,
#   «oe nexus», «ey nexus», «nexo», «hey jarvis»... di la que sea natural.
WAKE_WHISPER_MODEL = "tiny" # el whisper del wake: pesa poco y vuela

# ══ Voz FISH AUDIO (la voz española que elegiste) ═════════════════
# 1) Crea tu cuenta en fish.audio → copia tu API key aquí abajo
# 2) Al pegarla, NEXO habla con ESA voz (si falla, cae a edge-tts solo)
FISH_API_KEY = os.environ.get("FISH_API_KEY", "")   # ← pega tu API key de fish.audio entre las comillas
FISH_VOICE_ID = "cceb4a19d86448d6afd30833c88f5236"  # la voz que te gustó
FISH_MODEL = "s2.1-pro-free"  # tier gratis; sube a "s2.1-pro" si tienes créditos
# El MENÚ de voces de la pestaña Ajustes arranca con estas dos
# (nombre → ID de fish.audio); allá añades o quitas las que quieras.
# La voz ACTIVA sigue siendo FISH_VOICE_ID: un clic en el menú la cambia.
VOCES_FISH = {
    "Mickey Mouse": "cceb4a19d86448d6afd30833c88f5236",
    "JARVIS": "21adf3cda02a4aa88dc593353cc9d715",
}

# Correo (Gmail)
EMAIL_USER = "tucorreo@gmail.com"
EMAIL_APP_PASS = os.environ.get("EMAIL_APP_PASS", "")   # la contraseña de aplicación, NO tu clave normal

# ══ Interfaz NEXUS ═════════════════════════════════════════════════
NOTCH = True                # True = pastilla arriba (clic para abrir) | False = ventana normal
HOTKEY = "ctrl+alt+space"   # despierta a NEXUS desde CUALQUIER app (requiere: pip install keyboard)
SHOW_TRANSCRIPT = False     # True = mostrar en pantalla lo que dices | False = solo la consola

# ══ Parte del mañana (briefing) ═══════════════════════════════════
BRIEFING_CITY = "Medellín"   # clima local, gratis vía wttr.in

# ══ Micrófono ═════════════════════════════════════════════════════
MIC_DEVICE_INDEX = None   # None = predeterminado de Windows. ¿Otro micro?
                           # corre "py -3.12 diagnostico.py", mira su número [n] y ponlo aquí
SAMPLE_RATE = 16000
CHUNK_MS = 80             # openWakeWord trabaja con frames de 80 ms
SILENCE_LIMIT_S = 0.7     # segundos de silencio que cortan tu orden
                           # (0.7 = te responde más rápido; 1.2 si hablas pausado)
MAX_COMMAND_S = 12        # duración máxima de una orden
VOICE_ACTIVITY_RMS = 150  # umbral de "hay voz" (ya viene más sensible)
MIC_SENSIBILIDAD = 1.7     # 1 = normal · 1.7 = sensible · 2.5 = susurros
                           # (multiplica TODO: wake word, detección de voz y orden)

# ══ Ajustes desde la interfaz (pestaña «Ajustes» del panel) ═══════
# Lo que guardas en la pestaña Ajustes vive en ~/nexus_ajustes.json y
# MANDA sobre lo escrito aquí arriba (llave de la nube, modelo y voz
# de fish.audio). Si dejas el campo VACÍO en la pestaña, vuelve el
# valor de este archivo. _BASE guarda los originales para revertir.
_BASE = {"LLM_API_KEY": LLM_API_KEY, "LLM_MODEL": LLM_MODEL,
         "FISH_API_KEY": FISH_API_KEY, "FISH_VOICE_ID": FISH_VOICE_ID}
try:
    import json as _json
    from pathlib import Path as _Path
    with open(_Path.home() / "nexus_ajustes.json", encoding="utf-8") as _f:
        _sobre = _json.load(_f) or {}
    for _k in _BASE:
        _v = _sobre.get(_k)
        if isinstance(_v, str):
            globals()[_k] = _v
except Exception:
    pass
