"""Micrófono: detección del wake word + grabación de la orden.

v14 NEXUS: DOS formas de despertarlo —
  · onnx    → 'hey Jarvis' con acento gringo (rápido, el de siempre)
  · whisper → Whisper 'tiny' escucha frases en ESPAÑOL natural:
              di «oye Nexus» o «hey Nexus» como lo dirías siempre.
  · ambos (por defecto) → cualquiera de los dos dispara.
Y audio.forzar() despierta el asistente al instante (hotkey o clic).
"""
import difflib
import queue
import threading
import time
import unicodedata

import numpy as np
import sounddevice as sd

import config

# Modelo precompilado de openWakeWord (descarga onnx + tflite juntos)
WAKE_MODEL = "hey_jarvis_v0.1"

_oww_model = None
_tiny = None

# despertar manual: hotkey global (Ctrl+Alt+Espacio) o clic en el orbe
_FORCE = threading.Event()

# ── transcripción EN VIVO ───────────────────────────────────────────
# Mientras grabas tu orden, un hilo va transcribiendo el audio acumulado
# con Whisper: al cortar por silencio el texto ya está (casi) listo y
# NEXUS no espera a transcribir DESPUÉS de que callaste.
#   cubierto = muestras que cubre el último texto en vivo
#   voz_fin  = muestras acumuladas al oír la ÚLTIMA palabra (la cola de
#              silencio no cuenta: no aporta texto)
_VIVO = {"texto": None, "cubierto": 0, "voz_fin": 0}


def texto_vivo(audio_int16):
    """El texto que Whisper fue sacando MIENTRAS grababas.

    Devuelve None si la transcripción en vivo no cubre hasta la última
    palabra (habrá que transcribir completo, como siempre)."""
    if _VIVO["texto"] is None:
        return None
    if _VIVO["voz_fin"] <= _VIVO["cubierto"]:
        return _VIVO["texto"]
    return None

# ── sensibilidad del micrófono (v23: NEXUS oye más fácil) ────────────
# MIC_SENSIBILIDAD multiplica lo que diga config.py: 1 = como antes,
# 1.7 = sensible (por defecto), 2.5 = oye hasta un susurro.
def _sens():
    try:
        return max(1.0, float(getattr(config, "MIC_SENSIBILIDAD", 1.7)))
    except Exception:
        return 1.7


def gate_voz():
    """Umbral de «hay voz»: el de config dividido por la sensibilidad."""
    base = float(getattr(config, "VOICE_ACTIVITY_RMS", 150))
    return base / _sens()


def umbral_wake():
    """Umbral del wake word onnx. La sensibilidad ya no lo hunde tanto
    (antes 0.55/1.7 = 0.32 y CUALQUIER ruido lo disparaba solo):
    raíz cuadrada de la sensibilidad y piso de 0.40."""
    base = float(getattr(config, "WAKE_THRESHOLD", 0.55))
    return max(0.40, base / (_sens() ** 0.5))


def forzar():
    """Despierta al asistente YA, sin wake word (hotkey o clic en el orbe)."""
    _FORCE.set()


def _get_model():
    """Carga openWakeWord con el modelo 'hey_jarvis' en formato ONNX.

    ⚠️ En Windows hay que forzar ONNX: el formato por defecto (tflite) no
    tiene runtime para Windows. `download_models` baja onnx + tflite una
    sola vez y luego los encuentra ya en disco.
    """
    global _oww_model
    if _oww_model is None:
        from openwakeword.model import Model
        from openwakeword.utils import download_models

        download_models(model_names=[WAKE_MODEL])  # la primera vez descarga (~30 MB)
        _oww_model = Model(
            wakeword_models=[WAKE_MODEL],
            inference_framework="onnx",  # clave en Windows: tflite no existe aquí
        )
        print(f"✅ Wake word '{WAKE_MODEL}' listo (ONNX)")
    return _oww_model


def _get_tiny():
    """Whisper 'tiny' SOLO para el wake: pesa poco y vuela en CPU.
    Es un modelo aparte del que transcribe órdenes (ese es 'small')."""
    global _tiny
    if _tiny is None:
        from faster_whisper import WhisperModel
        _tiny = WhisperModel(
            getattr(config, "WAKE_WHISPER_MODEL", "tiny"),
            device=config.WHISPER_DEVICE,
            compute_type="int8",
        )
        print("✅ Wake por Whisper listo (entiende español natural)")
    return _tiny


def _normalizar(texto):
    """minúsculas y sin tildes: 'NéXus' → 'nexus'."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _frases_wake():
    """Las frases de config + «yarvis» SIEMPRE: jarvis en español,
    sin acento gringo (v28 — Dante lo dice a su manera)."""
    frases = list(getattr(config, "WAKE_FRASES", ["nexus", "jarvis"]))
    for extra in ("yarvis",):
        if extra not in frases:
            frases.append(extra)
    return [_normalizar(f) for f in frases]


def _match_wake(dicho, objetivo):
    """¿El texto contiene un wake? ENDURECIDO (v30): antes era tan
    difuso que «next» en una canción o «jardín» despertaban a NEXUS
    solos. Ahora solo pasa si:
    - el wake aparece EXACTO como palabra completa («conexo» ya no
      cuenta: exige límites de palabra), o
    - un token empieza por casi TODO el wake («nexu…», «jarv…»), o
    - un token es casi idéntico (≥0.85: «javis»≈«jarvis» sí,
      «marvis» no)."""
    import re
    for f in objetivo:
        if len(f) >= 4 and re.search(rf"\b{re.escape(f)}\b", dicho):
            return f
    toks = dicho.split()
    for tok in toks:
        for f in objetivo:
            if (len(f) >= 4 and tok.startswith(f[:4])
                    and len(tok) <= len(f) + 3):
                return f
    for tok in toks:
        for f in objetivo:
            # similitud solo para wakes de 5+ letras: con 4 («nexo»)
            # hasta «anexo» parecía suficiente y despertaba solo
            if (len(f) >= 5 and len(tok) >= 4
                    and difflib.SequenceMatcher(None, tok, f).ratio()
                    >= 0.85):
                return f
    return None


def _tiny_texto(buffer):
    """Transcribe la ventana de audio (whisper tiny) y normaliza.
    Con language fija y VAD: no gasta CPU en detección de idioma ni en
    tramos de puro ruido."""
    audio_f32 = buffer.astype(np.float32) / 32768.0
    segments, _ = _get_tiny().transcribe(
        audio_f32, language=config.LANGUAGE, vad_filter=True, beam_size=1)
    return _normalizar(" ".join(s.text.strip() for s in segments))


def _tiny_oye(buffer):
    """¿El buffer contiene alguna frase wake? (whisper modo)"""
    return _match_wake(_tiny_texto(buffer), _frases_wake())


def _apagar(stream):
    """Cierra el stream sin quejarse (puede ya estar muerto)."""
    try:
        stream.close()
    except Exception:
        pass


def _next_audio(audio_queue, timeout=0.25):
    """Saca un chunk 1D con TIMEOUT: si el micro se queda callado,
    no bloqueamos para siempre (el hotkey manual tiene que poder
    respondes aunque no llegue audio). Si hay rezago, lo une sin perder."""
    chunk = np.asarray(audio_queue.get(timeout=timeout)).reshape(-1)
    while True:
        try:
            extra = audio_queue.get_nowait()
        except queue.Empty:
            return chunk
        chunk = np.concatenate([chunk, np.asarray(extra).reshape(-1)])


def _jarvis_score(model, chunk):
    """Score del wake word, compatible con openwakeword 0.6+.

    En 0.6+ predict() DEVUELVE el dict de scores (el atributo
    prediction_dict de versiones viejas ya no existe).
    """
    scores = model.predict(chunk) or {}
    return max(
        (float(v) for k, v in scores.items() if "jarvis" in str(k).lower()),
        default=0.0,
    )


def _print_active_mic():
    """Muestra qué micro está usando Windows (para descartar el sordo)."""
    try:
        dev = sd.query_devices(kind="input")
        print(f"🎤 Micrófono activo: {dev['name']}")
    except Exception:
        print("⚠️ No pude consultar el micrófono predeterminado de Windows.")


def _make_stream():
    """Stream de micrófono que alimenta una cola de chunks de 80 ms."""
    audio_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        # sounddevice entrega audio 2D (muestras, canales); openwakeword
        # necesita audio PLANO 1D — si no, su buffer interno se corrompe
        # y el modelo ONNX revienta con "Invalid input shape".
        audio_queue.put(indata[:, 0].copy())

    stream = sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=int(config.SAMPLE_RATE * config.CHUNK_MS / 1000),
        device=getattr(config, "MIC_DEVICE_INDEX", None),  # None = predeterminado
        callback=callback,
    )
    stream.start()   # ⚠️ SIN ESTO no llega audio NUNCA (v24 lo perdió al
                     # quitar el «with stream:», que arrancaba solo)
    return stream, audio_queue


def wait_for_wake():
    """Bloquea hasta oír el wake — A PRUEBA DE BALAS.

    v24: el hilo del oído ya NO puede morirse en silencio (ese era el
    bug de «funciona solo una vez»): el hotkey manual se revisa aunque
    no llegue audio, y si el micro se queda callado o algo revienta,
    el stream se REINICIA y se sigue escuchando.
    """
    modo = getattr(config, "WAKE_MODE", "ambos")     # onnx | whisper | ambos
    usar_onnx = modo in ("onnx", "ambos")
    usar_whisper = modo in ("whisper", "ambos")
    model = _get_model() if usar_onnx else None
    threshold = umbral_wake()
    gate = gate_voz()
    stream, audio_queue = _make_stream()
    _print_active_mic()
    pistas = []
    if usar_onnx:
        pistas.append('"hey Jarvis" (a lo gringo: YÁRvis)')
    if usar_whisper:
        pistas.append('"nexus" / "hey nexus" / "oe nexus" (como hablas siempre)')
    print(f"🟡 En espera... di {' o '.join(pistas)} (umbral {threshold:.2f})")

    best = 0.0                 # mejor score onnx de toda la sesión
    prev = 0.0                 # score del chunk ANTERIOR: un pico solo
                               # (1 chunk de 80 ms) ya NO despierta solo
    sec_rms, sec_t = 0.0, 0.0   # nivel de voz y tiempo acumulado del segundo actual
    avisos = {"micro", "cercano"}  # pistas que se imprimen solo una vez
    buffer = np.zeros(0, dtype=np.int16)     # ventana rolling para whisper
    ultimo_whisper = 0.0
    pico = 0.0                 # pico de voz reciente (decae suave): el
                               # wake por whisper se dispara por él
    amb = 0.0                  # nivel AMBIENTE del cuarto (media móvil muy
                               # lenta, ~80 s): la voz se detecta como un
                               # SUBIDÓN sobre él, no con un número fijo
    ultimo_casi = 0.0          # última vez que avisé «casi te oí»
    vacios = 0                 # chunks de timeout seguidos = micro callado
    while True:
        # 1) EL MANUAL MANDA: se revisa aunque no llegue audio NUNCA
        if _FORCE.is_set():
            _FORCE.clear()
            _apagar(stream)
            print("\n⚡ Despertado por control manual.")
            return

        # 2) chunk con timeout: micro muerto ≠ hilo muerto
        try:
            chunk = _next_audio(audio_queue)
            vacios = 0
        except queue.Empty:
            vacios += 1
            if vacios >= 12:            # ~3 s sin audio: lo levantamos
                _apagar(stream)
                try:
                    stream, audio_queue = _make_stream()
                    vacios = 0
                    print("\n⚠️ Reinicié el micrófono (se había quedado callado).")
                except Exception as exc:
                    print(f"\n[micro no quiso volver: {type(exc).__name__}] "
                          f"reintento en 2 s]")
                    time.sleep(2)
            continue

        # 3) TODO el procesamiento blindado: una excepción aquí YA NO
        #    puede matar el hilo (mataba a NEXUS después de la 1ª orden)
        try:
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            amb = amb * 0.999 + rms * 0.001     # fondo del cuarto, muy lento
            # el modelo onnx SOLO merece CPU cuando hay algo claramente
            # más fuerte que el ambiente (antes corría en cada chunk de
            # 80 ms aunque no hubiera nadie hablando)
            if usar_onnx and rms >= max(30.0, amb * 1.5):
                score = _jarvis_score(model, chunk)
            else:
                score = 0.0
            best = max(best, score)
            sec_rms = max(sec_rms, rms)
            sec_t += len(chunk) / config.SAMPLE_RATE

            # dispara solo si el score se SOSTIENE (2 chunks seguidos):
            # un «hey jarvis» real dura varios frames, un ruido con
            # pico aislado no — antes eso lo despertaba solo
            if score >= threshold and prev >= threshold * 0.8:
                if hasattr(model, "reset"):
                    model.reset()
                _apagar(stream)
                print()  # deja limpia la línea del medidor
                return
            prev = score

            # modo whisper: se transcribe SOLO cuando la voz sube
            # claramente sobre el ambiente del cuarto (pico ≥ 3× amb y
            # ≥ gate). Antes el umbral era gate*0.25 ≈ 22 RMS: cualquier
            # ventilador lo cumplía y whisper tiny corría cada 0.5 s EN
            # BUCLE gastando núcleos enteros sin que nadie hablara.
            if usar_whisper:
                buffer = np.concatenate([buffer, chunk])
                buffer = buffer[-int(config.SAMPLE_RATE * 2.5):]
                pico = max(pico * 0.92, rms)
                ahora = time.time()
                if (pico >= max(gate, amb * 3.0)
                        and ahora - ultimo_whisper >= 1.0
                        and len(buffer) >= config.SAMPLE_RATE):
                    ultimo_whisper = ahora
                    try:
                        dicho = _tiny_texto(buffer)
                        if dicho:
                            oido = _match_wake(dicho, _frases_wake())
                            if oido:
                                _apagar(stream)
                                print(f"\n⚡ Wake por Whisper: «{oido}» "
                                      "— te oí natural, señor.")
                                return
                            if (pico >= gate * 0.5
                                    and ahora - ultimo_casi >= 4.0):
                                ultimo_casi = ahora
                                print(f"\n🤏 Casi: te oí «{dicho[:40]}». "
                                      "Habla cerca y claro, o baja "
                                      "VOICE_ACTIVITY_RMS.")
                    except Exception as exc:   # si tiny falla, el onnx sigue
                        print(f"\n[whisper wake falló: {type(exc).__name__}: {exc}]")

            # Medidor en vivo: 1 línea que se actualiza cada segundo
            if sec_t >= 1.0:
                print(
                    f"\r🔊 voz={sec_rms:5.0f}  score máx={best:.2f}  "
                    f"(dispara en {threshold:.2f})   ",
                    end="", flush=True,
                )
                if "micro" in avisos and sec_rms < 60:
                    avisos.discard("micro")
                    print("\n⚠️ El micro casi no capta nada. Corre:  py -3.12 diagnostico.py")
                if ("cercano" in avisos and usar_onnx
                        and 0.25 <= best < threshold):
                    avisos.discard("cercano")
                    print(
                        f"\n👀 Te oí cerca (score {best:.2f}). Di 'oye Nexus' en español "
                        f"natural (whisper) o baja WAKE_THRESHOLD a {max(0.3, best - 0.05):.2f} en config.py"
                    )
                sec_rms, sec_t = 0.0, 0.0
        except Exception as exc:      # ¿score/onnx/lo que sea reventó?
            print(f"\n[oído falló: {type(exc).__name__}: {exc}] → reinicio y sigo]")
            _apagar(stream)
            try:
                if model is not None and hasattr(model, "reset"):
                    model.reset()
            except Exception:
                pass
            try:
                stream, audio_queue = _make_stream()
            except Exception:
                time.sleep(1)
            continue
def record_command():
    """Graba tu orden: arranca al oír voz y corta tras un silencio.

    MIENTRAS graba, un hilo transcribe en vivo lo acumulado (Whisper):
    al cortar, el texto suele estar listo y NEXUS responde antes.
    Devuelve numpy int16 con el audio, o None si no se oyó nada.
    """
    stream, audio_queue = _make_stream()
    gate = gate_voz()
    chunk_s = config.CHUNK_MS / 1000
    frames, heard_voice, silence_s, sin_audio = [], False, 0.0, 0.0
    _VIVO["texto"] = None
    _VIVO["cubierto"] = 0
    _VIVO["voz_fin"] = 0
    vivo = {"on": False}
    hilo = [None]

    def _transcribir_vivo():
        """Whisper en paralelo: transcribe el audio acumulado cada vez
        que crece; guarda el último texto que CUBRE lo dicho."""
        import numpy as _np
        import stt
        while vivo["on"]:
            copia = list(frames)          # copia estable del acumulado
            if not copia or len(copia) * chunk_s < 1.0:
                time.sleep(0.1)
                continue
            audio = _np.concatenate(copia).reshape(-1)
            if len(audio) <= _VIVO["cubierto"]:
                time.sleep(0.15)          # aún no crece: no repetir
                continue
            try:
                texto = stt.transcribe(audio)
            except Exception:
                return
            _VIVO["texto"] = texto
            _VIVO["cubierto"] = len(audio)

    print("🎤 Te escucho...")
    try:
        while len(frames) * chunk_s < config.MAX_COMMAND_S:
            try:
                chunk = audio_queue.get(timeout=0.5)
            except queue.Empty:
                sin_audio += 0.5
                if not heard_voice and sin_audio >= 3.0:
                    break   # micro mudo: soltar antes de colgar el pipeline
                continue          # micro lento ≠ orden perdida
            sin_audio = 0.0
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            if rms >= gate:
                heard_voice = True
                silence_s = 0.0
                frames.append(chunk)
                _VIVO["voz_fin"] = int(len(frames) * chunk_s
                                       * config.SAMPLE_RATE)
                if not vivo["on"]:      # primera palabra: Whisper arranca
                    vivo["on"] = True
                    hilo[0] = threading.Thread(
                        target=_transcribir_vivo, daemon=True)
                    hilo[0].start()
            elif heard_voice:
                frames.append(chunk)
                silence_s += chunk_s
                if silence_s >= config.SILENCE_LIMIT_S:
                    break
    finally:
        vivo["on"] = False               # el hilo para tras su pasada actual
        if hilo[0] is not None:
            hilo[0].join(timeout=8)
        _apagar(stream)          # SIEMPRE cerrar: si no, el micro queda tomado
    if not heard_voice:
        return None
    return np.concatenate(frames).reshape(-1)
