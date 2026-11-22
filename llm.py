"""El cerebro: LLM multi-proveedor con bucle de ejecución de herramientas.

Todos los proveedores hablan el mismo "idioma" (API de OpenAI), así que
con una línea de config.py cambias Mistral ↔ Groq ↔ ChatGPT ↔ Ollama.
"""
import base64
import json

import config
import tools

SYSTEM_PROMPT = """Eres NEXUS, el asistente personal de Dante, corriendo localmente en su PC con Windows 10.
Reglas:
- Responde SIEMPRE en español colombiano, breve y directo: de 1 a 3 frases. PERO si Dante pide una historia, explicación larga, documento o código, puedes extenderte lo necesario: no te cortes a mitad.
- Tu respuesta se HABLA en voz alta: escribe texto plano natural, NUNCA markdown. Prohibido usar asteriscos, guiones dobles, numerales o listas con viñetas.
- Tienes un toque de mayordomo británico: elegante, humor fino, nunca exagerado.
- Usa las herramientas SIEMPRE que resuelvan la petición; no pidas permiso para usarlas.
- Chistes, datos generales e historias los respondes de TU PROPIO conocimiento: NO uses herramientas para eso. Los CÁLCULOS EXACTOS sí: usa calculate siempre que haya números concretos (multiplicaciones, porcentajes, raíces, potencias) — no calcules de cabeza.
- Modo programador: si Dante pide crear un script/programa/archivo de código, usa create_code con el contenido COMPLETO. Si pide ejecutar o probar código, usa run_python. Si pide leer o analizar un archivo, usa read_file. Si pregunta qué hay en una carpeta, usa list_files.
- TUS OJOS: si Dante dice «mira», «mira mi pantalla», «mira lo que estoy haciendo», «qué ves», «qué error hay en pantalla» o quieres ACTUAR según lo que ves (hacer lo que él hace, abrir lo que falta, arreglar un error visible), usa look_screen: te llega la captura como imagen. Mírala, resume en 1-2 frases lo relevante y ejecuta las herramientas que toquen.
- VIDA DIARIA: si Dante dice «anota una tarea X», usa add_task; «qué tengo pendiente»/«mis tareas», usa list_tasks; «ya hice X»/«completé X»/«tacha X», usa complete_task; «créa el hábito X con meta N», usa add_habit; «registrar X»/«tomé agua»/«ya leí» con X hábito suyo, usa check_habit; «borra el hábito X»/«elimina el hábito X», usa delete_habit; «cómo van mis hábitos», usa habit_status; «enfoque 25 minutos»/«temporizador de 5 minutos», usa focus; «cancela el temporizador», usa stop_timer. Cada acción muestra un aviso en la isla de su pantalla.
- CORREO: si Dante dice «envía un correo», «mándale un correo», «envía este correo» y te dicta el contenido, usa draft_email con el mensaje COMPLETO en body (y un asunto corto si lo dio). NO inventes la dirección del destinatario: se escribe en un diálogo que se abre solo en pantalla; si él la dijo claramente, ponla en to. Después dile que revise el diálogo y que ahí la envía.
- GITHUB: si dice «en esta carpeta hice cambios, haz commit y push», «sube los cambios de X» o «commit y push al repo Y», usa github_push con la carpeta (ruta completa) y el repo si lo nombró. GitHub Desktop ya guarda sus credenciales: el push sale solo.
- PERO si te piden datos ESPECÍFICOS que no sabés o pueden cambiar (specs técnicas, consumo de un componente, precios, personas, resultados, actualidad), usa search_online: busca en silencio SIN abrir el navegador y te devuelve los hallazgos para que los resumas en 2-3 frases habladas. El usuario sigue usando el PC mientras tanto.
- search_web y play_youtube solo ABREN ventanas del navegador: úsalas cuando el usuario QUIERA ver los resultados, no para consultar datos.
- Si el usuario pide crear un documento (con texto, fuente, tamaño y ubicación), usa create_document y repite la ruta EXACTA que te devolvió. NUNCA digas que algo está hecho sin haber ejecutado la herramienta: si el documento no se creó, dilo y revisa la consola.
- Si el usuario dice «deshaz eso», «deshazlo», «cancela lo último» o se arrepiente de una acción, usa undo. Cada llamada deshace UNA acción.
- Si el usuario dice «recuerda que…», «aprende…», «no olvides…» o comparte gustos o datos de sus proyectos, usa remember para guardarlo en tu memoria: la leerás al arrancar cada sesión.
- Si ya llamaste una herramienta con los mismos argumentos, NO la repitas: responde directamente al usuario.
- No inventes procesos, rutas ni datos. Si algo está fuera de tus herramientas, dilo con estilo.
- Cuando una herramienta te devuelva una ruta o nombre de archivo (por ejemplo, dónde guardó una nota), repítela EXACTAMENTE como te la dio: nunca la cambies ni inventes nombres o ubicaciones distintas.
- Si tu respuesta menciona nombres en inglés (títulos de canciones, juegos, apps, marcas o palabras sueltas), rodéalos con <en> y </en>: «Reproduciendo <en>Hive Knight</en> de <en>Hollow Knight</en>». Es para que la voz los pronuncie en inglés correcto, no en español. El texto en español va normal, sin marcas.
- Si el usuario pide la hora o fecha usa las herramientas, nunca la tuya.
- Si no entendiste la orden, pide cortésmente que la repita."""

# ── MODO LOCAL: el prompt COMPACTO ──────────────────────────────────
# En CPU cada token del prompt se paga caro: el prompt grande + las 36
# herramientas son ~4600 tokens → 60 s por respuesta en el Ryzen.
# Este prompt + las herramientas esenciales son ~650 → responde en
# segundos. Las habilidades completas viven en el modo nube.
SYSTEM_PROMPT_LOCAL = """Eres NEXUS, el mayordomo de Dante en su PC con Windows.
- Responde en español colombiano, BREVE (1-3 frases), en texto plano natural: se habla en voz alta. NUNCA markdown, viñetas ni asteriscos.
- Nombres en inglés (canciones, juegos, apps, marcas) van entre <en> y </en>.
- Usa las herramientas sin pedir permiso: tareas (add_task, complete_task, list_tasks), hábitos (check_habit), enfoque y temporizador (focus, stop_timer), recordatorios (set_reminder), hora y fecha (get_time, get_date), abrir apps y webs (open_app, open_website), YouTube (play_youtube), notas (create_note), volumen (set_volume), cálculos con números concretos (calculate), datos actuales o específicos (search_online), y guardar recuerdos (remember).
- Chistes, historias y datos generales los respondes de TU conocimiento, SIN herramientas.
- Si no entendiste, pide que te lo repita."""

# las herramientas esenciales del modo local (el resto vive en la nube)
_TOOLS_LOCAL = None
_TOOLS_LOCAL_NOMBRES = {
    "get_time", "get_date", "open_app", "open_website", "play_youtube",
    "set_reminder", "set_volume", "create_note", "search_online",
    "calculate", "remember", "add_task", "complete_task", "list_tasks",
    "uncomplete_task", "delete_task", "check_habit", "uncheck_habit",
    "delete_habit", "focus", "stop_timer",
}


def _tools_local():
    """El subconjunto esencial de herramientas para el modo LOCAL:
    ~3400 tokens de definiciones se vuelven ~500.
    LOCAL_TOOLS = "todas" en config.py recupera las 36 completas."""
    global _TOOLS_LOCAL
    if _TOOLS_LOCAL is None:
        import config
        if getattr(config, "LOCAL_TOOLS", "esenciales") == "todas":
            _TOOLS_LOCAL = tools.TOOLS_JSON
        else:
            _TOOLS_LOCAL = [t for t in tools.TOOLS_JSON
                            if t["function"]["name"] in _TOOLS_LOCAL_NOMBRES]
    return _TOOLS_LOCAL

PROVIDERS = {    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
        "key_url": "https://console.mistral.ai/",
        "nota": "crea una cuenta gratis y genera tu API key",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "key_url": "https://console.groq.com/keys",
        "nota": "crea una cuenta gratis y genera tu API key",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-flash",  # OJO: deepseek-chat ya se retiró (jul-2026)
        "key_url": "https://platform.deepseek.com/api_keys",
        "nota": "baratísimo (~$0.15/$0.60 por millón fuera de horas pico) "
                "pero hay que cargar saldo (mínimo ~$2 USD)",
    },
    "openai": {
        "base_url": None,  # la API oficial
        "default_model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "nota": "OJO: es de PAGO — necesitas tarjeta internacional y saldo cargado",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2:3b",
        "key_url": "https://ollama.com",
        "nota": "100% local en tu Ryzen: 'ollama pull llama3.2:3b' "
                "(3B = rápido en CPU; qwen2.5:7b si tienes paciencia)",
    },
}

# ── Ollama: ¿está vivo y tiene el modelo? (caché de 10 s) ──────────
_OLLAMA_OK = None          # (bool, timestamp)

# ── Nube: ¿hay internet y la key sirve? (caché de 30 s) ────────────
_NUBE_OK = None            # (bool, timestamp)
_NUBE_MALA_HASTA = 0.0     # la API falló (cuota/key/red): no reintentar


def _nube():
    """¿La nube de CLOUD_PROVIDER responde Y la key es válida?
    Un GET a /models valida las dos cosas de una (2.5 s máximo)."""
    global _NUBE_OK, _NUBE_MALA_HASTA
    import time as _t
    import urllib.request
    ahora = _t.monotonic()
    if ahora < _NUBE_MALA_HASTA:
        return False
    if _NUBE_OK is not None and ahora - _NUBE_OK[1] < 30:
        return _NUBE_OK[0]
    ok = False
    try:
        nombre = getattr(config, "CLOUD_PROVIDER", "mistral") or "mistral"
        prov = PROVIDERS.get(nombre)
        if prov and prov.get("base_url") and (config.LLM_API_KEY or "").strip():
            pedido = urllib.request.Request(
                prov["base_url"].rstrip("/") + "/models",
                headers={"Authorization": "Bearer " + config.LLM_API_KEY.strip()})
            with urllib.request.urlopen(pedido, timeout=2.5) as r:
                ok = r.status == 200
    except Exception:
        ok = False
    _NUBE_OK = (ok, ahora)
    return ok


def _modelo_ollama():
    """El modelo LOCAL configurado (sin tocar el fallback de la nube)."""
    if config.PROVIDER == "ollama" and config.LLM_MODEL:
        return config.LLM_MODEL
    return PROVIDERS["ollama"]["default_model"]


def _ollama_listo():
    """¿Ollama corre en localhost:11434 Y tiene el modelo descargado?"""
    global _OLLAMA_OK
    import time as _t
    import urllib.request
    ahora = _t.monotonic()
    if _OLLAMA_OK is not None and ahora - _OLLAMA_OK[1] < 10:
        return _OLLAMA_OK[0]
    ok = False
    try:
        with urllib.request.urlopen(
                "http://localhost:11434/api/tags", timeout=1.5) as r:
            nombres = [m.get("name", "") for m in
                       json.loads(r.read()).get("models", [])]
        base = _modelo_ollama().split(":")[0]
        ok = any(n.split(":")[0] == base for n in nombres)
        if not ok:
            print(f"⚠️  Ollama corre pero falta el modelo "
                  f"'{_modelo_ollama()}'.\n"
                  f"    Bájalo con:  py -3.12 main.py --ollama")
    except Exception:
        ok = False
    _OLLAMA_OK = (ok, ahora)
    return ok


def _proveedor_activo():
    """El proveedor REAL. Con PROVIDER="auto" NEXUS decide solo:
    nube si hay internet (rápida y lista) → local si te quedas sin
    conexión — nunca queda mudo."""
    elegido = config.PROVIDER
    if elegido == "auto":
        nube = getattr(config, "CLOUD_PROVIDER", "mistral") or "mistral"
        if nube in PROVIDERS and nube != "ollama" and _nube():
            return nube
        if _ollama_listo():
            return "ollama"
        return nube        # nada disponible: que el error hable claro
    if elegido == "ollama" and not _ollama_listo():
        fb = getattr(config, "LLM_FALLBACK", "") or ""
        if fb in PROVIDERS and fb != "ollama":
            print(f"⚠️  Ollama no disponible → sigo con {fb} (la nube). "
                  f"Arranca Ollama para volver a lo 100% local.")
            return fb
    return elegido


def model_name(proveedor=None):
    prov = proveedor or _proveedor_activo()
    if prov == "ollama":
        return _modelo_ollama()
    if prov == config.PROVIDER and config.LLM_MODEL:
        return config.LLM_MODEL
    return PROVIDERS[prov]["default_model"]


def _client(forzar=None):
    proveedor_nombre = forzar or _proveedor_activo()
    if proveedor_nombre not in PROVIDERS:
        raise SystemExit(
            f"\n❌ Proveedor desconocido '{config.PROVIDER}'.\n"
            f"   Opciones válidas: {', '.join(PROVIDERS)}\n"
        )
    proveedor = PROVIDERS[proveedor_nombre]

    if proveedor_nombre == "ollama":
        api_key = config.LLM_API_KEY or "ollama"  # Ollama no exige key real
    elif not config.LLM_API_KEY:
        raise SystemExit(
            f"\n❌ Falta la API key de {proveedor_nombre}.\n"
            f"   Entra a {proveedor['key_url']} — {proveedor['nota']}.\n"
            f"   Luego pégala en config.py (LLM_API_KEY) o en la variable de entorno LLM_API_KEY.\n"
        )
    else:
        api_key = config.LLM_API_KEY

    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=proveedor["base_url"])


def _history(messages):
    """Conserva solo lo conversacional (sin las llamadas a herramientas
    ni las imágenes: la vista se gasta, el texto queda)."""
    historial = []
    for m in messages:
        if m["role"] not in ("user", "assistant") or m.get("tool_calls"):
            continue
        contenido = m.get("content")
        if isinstance(contenido, list):  # bloques de imagen: solo el texto
            contenido = " ".join(
                b.get("text", "") for b in contenido if isinstance(b, dict))
        if contenido:
            historial.append({"role": m["role"], "content": contenido})
    return historial[-12:]


def _memoria(n=30):
    """Recuerdos duraderos de Jarvis: se inyectan en el prompt de cada sesión."""
    try:
        import tools
        lineas = tools.leer_memoria(n)
    except Exception:
        lineas = []
    if not lineas:
        return ""
    return ("\n\nMEMORIA — cosas que Dante te pidió recordar "
            "(cronológico, las últimas son lo más reciente):\n"
            + "\n".join(lineas))


def _texto(contenido):
    """content puede llegar str, None o LISTA de bloques (modelos grandes
    y de razonamiento): lo normalizamos a str SIEMPRE. Si no, revienta
    con 'list' object has no attribute 'strip' y Jarvis... este, NEXUS,
    se queda mudo."""
    if contenido is None:
        return ""
    if isinstance(contenido, list):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict):
                partes.append(str(bloque.get("text") or bloque.get("content") or ""))
            else:
                partes.append(getattr(bloque, "text", "") or "")
        return " ".join(p for p in partes if p)
    return str(contenido)


def _create(cliente, messages, herramientas, proveedor=None):
    """Llama al modelo. Si tiene una imagen pendiente y el modelo NO ve
    imágenes (error del proveedor), se reintenta sin la vista y con un
    aviso honesto en su lugar."""
    prov = proveedor or _proveedor_activo()
    # local (CPU) → respuestas cortas: cada token cuesta tiempo real
    max_tok = int(getattr(config, "LLM_MAX_TOKENS", 0) or 0) or (
        400 if prov == "ollama" else 800)

    def _llamar(msgs):
        return cliente.chat.completions.create(
            model=model_name(prov),
            messages=msgs,
            tools=herramientas,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=max_tok,
        )
    try:
        return _llamar(messages)
    except Exception:
        if not any(isinstance(m.get("content"), list) for m in messages):
            raise  # no hay imagen: el error es de verdad
        mensajes_sin_vista = [
            m if not isinstance(m.get("content"), list)
            else {"role": m["role"],
                  "content": "(capturé la pantalla pero ESTE modelo no soporta "
                             "imágenes: pidele a Dante configurar un modelo con "
                             "visión, ej: mistral-small-latest)"}
            for m in messages
        ]
        return _llamar(mensajes_sin_vista)


def respond(user_text, history):
    """Devuelve (respuesta, historial_actualizado). Ejecuta tools en bucle."""
    global _NUBE_MALA_HASTA
    client = _client()
    local = _proveedor_activo() == "ollama"
    # modo local: prompt compacto + herramientas esenciales + menos
    # historia — cada token se paga en CPU
    sistema = SYSTEM_PROMPT_LOCAL if local else SYSTEM_PROMPT
    herramientas = _tools_local() if local else tools.TOOLS_JSON
    mensajes_hist = history[-6:] if local else history[-12:]

    def _armar():
        return (
            [{"role": "system", "content": sistema + _memoria(10 if local
                                                              else 30)}]
            + mensajes_hist
            + [{"role": "user", "content": user_text}]
        )

    messages = _armar()

    usadas = set()  # (nombre, argumentos) ya ejecutadas: anti-bucle
    for _ in range(6):  # hasta 6 rondas de herramientas por orden
        try:
            completion = _create(client, messages, herramientas)
        except Exception as exc:
            # modo auto: la nube falló (cuota, key, red caída) → LOCAL ya
            if (not local and getattr(config, "PROVIDER", "") == "auto"
                    and _ollama_listo()):
                import time as _t
                _NUBE_MALA_HASTA = _t.monotonic() + 600   # 10 min sin nube
                print(f"⚠️  Nube falló ({type(exc).__name__}) → sigo LOCAL "
                      f"10 min. Revisa internet o la cuota.")
                local = True
                sistema = SYSTEM_PROMPT_LOCAL
                herramientas = _tools_local()
                mensajes_hist = history[-6:]
                client = _client(forzar="ollama")
                usadas.clear()
                messages = _armar()
                completion = _create(client, messages, herramientas,
                                     proveedor="ollama")
            else:
                raise
        message = completion.choices[0].message

        if not message.tool_calls:
            respuesta = _texto(message.content).strip() or "Aquí estoy, señor."
            messages.append({"role": "assistant", "content": respuesta})
            return respuesta, _history(messages)

        # dict estándar y explícito (no model_dump): sobrevive a cambios
        # de versión del SDK y a proveedores estrictos como Mistral
        messages.append({
            "role": "assistant",
            "content": _texto(message.content),
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ],
        })
        vista = None  # ruta de captura de pantalla de esta ronda
        resultados = []   # lo que devolvieron las tools de la ronda
        for tc in message.tool_calls:
            try:
                argumentos = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            llave = (tc.function.name, (tc.function.arguments or "{}").strip())
            if llave in usadas:
                # el modelo se atascó repitiendo la misma llamada: se le
                # recuerda que ya no aporta nada y que responda de una vez
                resultado = ("Llamada repetida: ya se ejecutó y no devuelve "
                             "contenido nuevo. Responde AHORA directamente al "
                             "usuario con tu propio conocimiento, sin herramientas.")
            else:
                usadas.add(llave)
                resultado = tools.execute(tc.function.name, argumentos)
            resultados.append(str(resultado))
            print(f"   🛠  {tc.function.name}({argumentos}) → {resultado}")
            if isinstance(resultado, str) and resultado.startswith("CAPTURA:"):
                ruta = resultado.split(":", 1)[1]
                resultado = ("Captura de pantalla lista. Te la mando como "
                             "imagen a continuación: mírala y actúa.")
                vista = ruta
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": resultado,
            })

        # LOS OJOS: la captura se adjunta como imagen DESPUÉS de todos los
        # mensajes de tool (el orden tool→user es válido para la API)
        if vista:
            try:
                with open(vista, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                messages.append({"role": "user", "content": [
                    {"type": "text",
                     "text": "(Esto es lo que hay ahora en la pantalla de Dante)"},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]})
            except OSError:
                messages.append({
                    "role": "user",
                    "content": "(la captura se perdió: pide a Dante repetir "
                               "el comando «mira»)",
                })

        # MODO LOCAL — el atajo que MÁS ahorra: si la herramienta ya
        # trae la respuesta hablada (casi todas: «Anotado: comprar
        # pan», la hora, el cronómetro arrancado...), NO se paga OTRA
        # ronda de LLM en CPU: se dice tal cual y a otra cosa.
        if local and vista is None:
            plano = " ".join(r for r in resultados if r).strip()
            if plano and not plano.startswith(("HALLAZGOS", "CAPTURA")):
                respuesta = plano if len(plano) <= 300 else plano[:297] + "…"
                messages.append({"role": "assistant", "content": respuesta})
                return respuesta, _history(messages)

    return "Me enredé con las herramientas, señor. ¿Me repite la orden?", _history(messages)


# ── Ollama: precarga y asistente de instalación ─────────────────────

def precargar():
    """Calienta el modelo LOCAL al arrancar: la primera orden no espera
    la carga de ~2 GB desde el disco (Ollama lo deja en RAM 5 minutos
    tras cada uso, así que las siguientes salen al instante)."""
    if _proveedor_activo() != "ollama":
        return
    import time
    try:
        t0 = time.time()
        cliente = _client()
        cliente.chat.completions.create(
            model=model_name(),
            messages=[{"role": "user", "content": "hola"}],
            max_tokens=1)
        print(f"✅ Modelo local caliente en {time.time()-t0:.1f} s: "
              "la primera orden responde al instante.")
    except Exception as exc:
        print(f"[precarga local falló: {type(exc).__name__}: {exc}]")


def ollama_asistente():
    """`py -3.12 main.py --ollama`: revisa el servidor, descarga el
    modelo si falta y deja a NEXUS corriendo 100% local en tu Ryzen."""
    import subprocess
    import urllib.request
    modelo = _modelo_ollama()
    try:
        with urllib.request.urlopen(
                "http://localhost:11434/api/tags", timeout=2) as r:
            nombres = [m.get("name", "") for m in
                       json.loads(r.read()).get("models", [])]
    except Exception:
        print("❌ Ollama no está corriendo.")
        print("   1) Instálalo una sola vez: https://ollama.com/download")
        print("   2) Ábrelo (queda en la bandeja del sistema)")
        print("   3) Vuelve a correr:  py -3.12 main.py --ollama")
        return
    print("✅ Ollama está corriendo.")
    base = modelo.split(":")[0]
    if any(n.split(":")[0] == base for n in nombres):
        print(f"✅ El modelo '{modelo}' ya está descargado: NEXUS corre "
              "100% local, sin internet y sin gastar API keys.")
        print('   En config.py deja:  PROVIDER = "ollama"')
        return
    print(f"⬇️  Descargando '{modelo}' (~2 GB, una sola vez)...")
    try:
        subprocess.run(["ollama", "pull", modelo], check=False)
        print(f"\n✅ Listo. En config.py deja:  PROVIDER = \"ollama\"")
        print("   La primera respuesta tarda un poquito más (carga el "
              "modelo); las demás salen al instante.")
    except FileNotFoundError:
        print(f"   No encontré el comando 'ollama' en el PATH.")
        print(f"   Bájalo a mano con:  ollama pull {modelo}")
