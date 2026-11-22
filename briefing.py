"""🌅 El parte del mañana: resumen hablado de tu día y tu equipo."""
import datetime

import config
import tools
import tts


def _clima():
    """Clima actual vía wttr.in (gratis, sin API key). Si falla, se omite."""
    try:
        import requests

        respuesta = requests.get(
            f"https://wttr.in/{config.BRIEFING_CITY}?format=j1&lang=es",
            timeout=8,
        )
        datos = respuesta.json()
        actual = datos["current_condition"][0]
        temp = actual["temp_C"]
        desc = ""
        if actual.get("lang_es"):
            desc = actual["lang_es"][0].get("value", "")
        if not desc:
            desc = actual["weatherDesc"][0]["value"]
        maximas = [int(d["maxtempC"]) for d in datos["weather"]]
        minimas = [int(d["mintempC"]) for d in datos["weather"]]
        return (f"En {config.BRIEFING_CITY} hay {temp} grados, {desc.lower()}, "
                f"con máxima de {max(maximas)} y mínima de {min(minimas)}.")
    except Exception:
        return None  # sin internet o API caída: el parte sigue sin clima


def briefing():
    """Resume el día en una sola hablada. Úsalo manual o programado."""
    ahora = datetime.datetime.now()
    if ahora.hour < 12:
        saludo = "Buenos días, Dante."
    elif ahora.hour < 19:
        saludo = "Buenas tardes, Dante."
    else:
        saludo = "Buenas noches, Dante."

    partes = [saludo, tools.get_date(), tools.get_time()]

    clima = _clima()
    if clima:
        partes.append(clima)

    try:
        dia = tools.resumen_dia()
        if dia:
            partes.append(dia)
    except Exception:
        pass

    partes.append(tools.system_status())

    reporte = " ".join(partes)
    print(f"🌅  {reporte}")
    tts.speak(reporte)
    return reporte
