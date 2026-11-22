"""NEXUS — pipeline completo en tu Windows 10.

    "oye Nexus" (o hotkey Ctrl+Alt+Espacio)  →  Whisper te entiende  →
    LLM piensa  →  tools actúan  →  voz responde

Arranque:            py -3.12 main.py            (interfaz notch + orbe)
Modo consola:        py -3.12 main.py --cli
Cerebro local:       py -3.12 main.py --ollama   (instala qwen en tu Ryzen)
Parte del mañana:    py -3.12 main.py --briefing
Probar el oído:      py -3.12 main.py --diagnostico
Menú de voces:       py -3.12 main.py --voces
"""
import queue
import sys
import threading
import time


def _pub(novedades, linea):
    """Manda una línea al registro de la interfaz (si está en modo GUI)."""
    if novedades is not None:
        novedades.put(linea)


def _registrar_hotkey():
    """Ctrl+Alt+Espacio despierta a NEXUS desde cualquier app (global)."""
    try:
        import config
        import keyboard
        import audio
        tecla = getattr(config, "HOTKEY", "ctrl+alt+space")
        keyboard.add_hotkey(tecla, audio.forzar, suppress=False)
        print(f"⌨️  Hotkey global listo: {tecla} me despierta.")
    except Exception as exc:
        print(f"[hotkey no disponible: {type(exc).__name__}: {exc}] "
              "(instala con:  py -3.12 -m pip install keyboard)")


def pipeline(novedades=None):
    """El bucle del mayordomo. Corre en su propio hilo cuando hay interfaz."""
    import audio
    import estado
    import llm
    import stt
    import tts

    import config
    mostrar_transcripcion = getattr(config, "SHOW_TRANSCRIPT", False)

    history = []
    try:
        llm._client()      # valida proveedor y API key temprano (mensaje claro si falta)
        stt._get_model()   # precarga Whisper para que la primera orden no tarde
        llm.precargar()    # modelo LOCAL caliente: la 1ª orden no espera la carga
        cerebro = llm._proveedor_activo()
        print(f"🧠  Cerebro: {cerebro} · modelo {llm.model_name()}"
              + ("  (auto: nube si hay internet, local si no)" if
                 getattr(config, 'PROVIDER', '') == 'auto' else ""))
    except SystemExit as exc:
        print(exc)
        _pub(novedades, str(exc).strip())
        estado.set_texto("jarvis", "Revisa la consola: falta la API key.")
        return

    _registrar_hotkey()
    estado.set_modo("esperando")
    estado.set_texto("jarvis", "Todos los sistemas en línea, señor.")
    _pub(novedades, "✦ Nexus: Todos los sistemas en línea. Di «oye Nexus» o Ctrl+Alt+Espacio.")
    tts.speak("Todos los sistemas en línea. Di oye Nexus cuando me necesites.")

    while True:
        # el oído es a prueba de balas, pero si AUN ASÍ se cae,
        # el hilo no muere: reporta, espera y vuelve a intentarlo
        try:
            audio.wait_for_wake()
        except Exception as exc:
            print(f"❌  El oído se cayó ({type(exc).__name__}: {exc}); lo levanto en 2 s.")
            time.sleep(2)
            continue
        try:
            tts.chime()
            time.sleep(0.18)  # para no grabar la cola del wake word

            estado.set_modo("escuchando")
            grabado = audio.record_command()
        except Exception as exc:
            print(f"❌  Grabando la orden falló ({type(exc).__name__}: {exc}); sigo vivo.")
            estado.set_modo("esperando")
            continue
        if grabado is None:
            tts.speak("No oí nada, señor.")
            continue

        try:
            # Whisper ya transcribió MIENTRAS grababas: si cubre todo,
            # el texto está listo al instante (cero espera extra)
            texto = audio.texto_vivo(grabado)
            if texto is None:
                texto = stt.transcribe(grabado)
        except Exception as exc:
            print(f"❌  Error en Whisper: {exc}")
            tts.speak("Tuve un problema con el oído, señor. Revisa la consola.")
            continue

        print(f"🗣  Tú: {texto}")
        try:
            import panel          # la orden queda en el chat del panel
            panel.chat("tu", texto)
        except Exception:
            pass
        if mostrar_transcripcion:
            estado.set_texto("tu", texto or "…")
            _pub(novedades, f"🗣 Tú: {texto or '(silencio)'}")
        else:
            # sin transcripción en pantalla: solo un pulso de "te oí"
            estado.set_texto("tu", "")
        if not texto:
            tts.speak("No te entendí, señor. ¿Me lo repites?")
            continue

        estado.set_modo("pensando")
        try:
            respuesta, history = llm.respond(texto, history)
        except Exception as exc:
            print(f"❌  Error del cerebro: {exc}")
            tts.speak("Tuve un problema con mi cerebro, señor. Revisa la consola.")
            continue

        print(f"✦  Nexus: {respuesta}")
        limpio = tts.plano(respuesta)          # sin marcas <en> en la pantalla
        estado.set_texto("jarvis", limpio)
        _pub(novedades, f"✦ Nexus: {limpio}")
        try:
            import panel          # la respuesta también vive en el chat
            panel.chat("nexus", limpio)
        except Exception:
            pass
        tts.speak(respuesta)                  # la voz sí usa las marcas
        estado.set_modo("esperando")


def main():
    if "--ollama" in sys.argv:
        import llm
        llm.ollama_asistente()  # revisa/instala el cerebro local
        return
    if "--briefing" in sys.argv:
        import briefing
        briefing.briefing()  # resume el día y sale
        return
    if "--diagnostico" in sys.argv or "--test-mic" in sys.argv:
        import diagnostico
        diagnostico.main()  # prueba de micrófono: ¿me oyes?, ¿qué score logro?
        return
    if "--voces" in sys.argv:
        import tts
        tts.demo_voces()    # menú de voces: escucha y elige la tuya
        return
    if "--cli" in sys.argv:
        pipeline()  # modo consola clásico, sin interfaz
        return

    # Modo estrella: interfaz web (HTML/SVG, nitidez de verdad) con
    # el pipeline en su propio hilo; si pywebview falla → tkinter
    import estado

    novedades = queue.Queue()
    hilo = threading.Thread(target=pipeline, args=(novedades,), daemon=True)
    hilo.start()
    estado.set_modo("arrancando")
    try:
        import webui
        webui.arrancar(novedades)
    except Exception as exc:
        print(f"[interfaz web no disponible: {type(exc).__name__}: {exc}] "
              "→ uso la interfaz tkinter")
        import gui
        gui.arrancar(novedades)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Apagando sistemas. Hasta luego, señor.")
