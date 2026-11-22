"""Diagnóstico del oído de J.A.R.V.I.S.

    py -3.12 diagnostico.py        (o:  py -3.12 main.py --diagnostico)

En 12 segundos te dice si el micro te capta y qué score logra tu
'hey Jarvis' — con veredicto y el umbral exacto que te conviene.
"""
import time

import numpy as np
import sounddevice as sd

import audio
import config

DURACION_S = 12  # tiempo de prueba


def _listar_dispositivos():
    print("\n📋 Micrófonos que ve Windows:")
    try:
        activo = sd.query_devices(kind="input")
    except Exception:
        activo = None
    for dev in sd.query_devices():
        if dev["max_input_channels"] > 0:
            marca = ""
            if activo is not None and dev["index"] == activo["index"]:
                marca = "   ← ACTIVO"
            print(f"   [{dev['index']}] {dev['name']}{marca}")
    if activo is None:
        print("❌ Windows no tiene ningún micrófono de entrada.")
        print("   Configuración → Sistema → Sonido → Entrada: elige tu micro.")
        return None
    return activo


def main():
    print("=" * 56)
    print("  DIAGNÓSTICO DEL OÍDO — NEXUS")
    print("=" * 56)

    activo = _listar_dispositivos()
    if activo is None:
        return
    print(f"\n🎤 Micro activo: {activo['name']}")

    print(f"\n🔴 Grabando {DURACION_S} s en dos rondas:")
    print("   0-6 s:  di 'hey Jarvis' NATURAL, como siempre hablas")
    print("   6-12 s: di 'hey Jarvis' bien a lo gringo ('éi yárvis')")
    print("   Así vemos cuál de tus acentos dispara mejor. (Ctrl+C corta)\n")

    model = audio._get_model()
    stream, audio_queue = audio._make_stream()

    mejor = {"natural": 0.0, "gringo": 0.0}
    rms_max, seg, chunks = 0.0, 0, 0
    with stream:
        t0 = time.time()
        while time.time() - t0 < DURACION_S:
            chunk = audio._next_audio(audio_queue)
            score = audio._jarvis_score(model, chunk)
            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            ronda = "natural" if time.time() - t0 < DURACION_S / 2 else "gringo"
            mejor[ronda] = max(mejor[ronda], score)
            rms_max = max(rms_max, rms)
            chunks += 1
            transcurrido = int(time.time() - t0)
            if transcurrido > seg:
                seg = transcurrido
                print(f"   {seg:2d} s   voz máx={rms_max:5.0f}   "
                      f"natural={mejor['natural']:.2f}   gringo={mejor['gringo']:.2f}")

    if chunks == 0:
        print("❌ No llegó ni un pedazo de audio al programa. Revisa los drivers de audio.")
        return

    thr = getattr(config, "WAKE_THRESHOLD", 0.55)
    print("\n" + "=" * 56)
    print("  VEREDICTO")
    print("=" * 56)
    if rms_max < 60:
        print(f"❌ El micro casi no capta tu voz (nivel {rms_max:.0f}, esperaba >100).")
        print("   → Permisos: Configuración → Privacidad → Micrófono → activa")
        print("     'Permitir que las aplicaciones accedan al micrófono' Y")
        print("     'Permitir que las aplicaciones de escritorio accedan'.")
        print("   → ¿Estás usando el micro correcto? Arriba está la lista;")
        print("     si tu micro real no es el ACTIVO, en Sonido → Entrada cámbialo,")
        print("     o pon su número en config.py:  MIC_DEVICE_INDEX = <número>.")
        return

    for ronda, score in mejor.items():
        if score >= thr:
            print(f"✅ Acento {ronda.upper()}: dispara ({score:.2f} ≥ umbral {thr}).")
        elif score >= 0.25:
            sugerido = max(0.25, round(score - 0.05, 2))
            print(f"🟡 Acento {ronda}: te oye ({score:.2f}) pero no llega al umbral {thr}.")
            print(f"   → Baja WAKE_THRESHOLD a {sugerido} en config.py y ese acento también dispara.")
        else:
            print(f"❌ Acento {ronda}: casi nada ({score:.2f}).")
    ganador = max(mejor, key=mejor.get)
    print(f"\n🏆 Te conviene el acento: {ganador.upper()}  (score {mejor[ganador]:.2f})")
    print("   Recuerda: 'Jarvis' en inglés suena 'YÁRvis' — la J es como Y.")
    print("   PERO v14: di 'oye Nexus' en tu acento natural — el modo whisper")
    print("   (WAKE_MODE en config.py) te entiende sin hablar gringo.")
    print("\n💡 Prueba de nuevo con:   py -3.12 diagnostico.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnóstico cancelado.")
