"""Oído: Whisper corriendo 100% local con faster-whisper (sin internet)."""
import numpy as np

import config

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"⏳ Cargando Whisper '{config.WHISPER_MODEL}' (la primera vez descarga el modelo)...")
        _model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type="int8",
        )
    return _model


def transcribe(audio_int16):
    """audio_int16: numpy 1-D. Devuelve el texto en español.

    beam_size=1 y sin condicionar al texto previo: en CPU es ~3 veces
    más rápido y para órdenes cortas el español sale igual de bueno."""
    model = _get_model()
    audio_f32 = audio_int16.astype(np.float32) / 32768.0
    segments, _info = model.transcribe(
        audio_f32, language=config.LANGUAGE, vad_filter=True,
        beam_size=1, condition_on_previous_text=False,
    )
    return " ".join(s.text.strip() for s in segments).strip()
