"""Estado compartido entre el oído, el cerebro, la voz y la interfaz.

Los hilos escriben aquí y la interfaz (gui.py) lee cada 100 ms para
mover la esfera y actualizar los subtítulos.
"""
import threading

_lock = threading.Lock()
_estado = {
    "modo": "arrancando",  # arrancando | esperando | escuchando | pensando | hablando
    "tu": "",              # última frase reconocida
    "jarvis": "",          # última respuesta
    "aviso": "",           # burbuja de notificación: la GUI la muestra ~3 s
    "crono": "",           # cuenta atrás visible en la pastilla ("24:59" o "")
}


def set_modo(modo):
    with _lock:
        _estado["modo"] = modo


def set_texto(quien, texto):  # quien: "tu" | "jarvis"
    with _lock:
        _estado[quien] = texto


def set_aviso(texto):
    """Notificación para la isla: «✓ Anotado», «⏰ Recordatorio»…"""
    with _lock:
        _estado["aviso"] = texto


def set_crono(texto):
    """Cuenta atrás del enfoque: 'MM:SS' o '' para apagarla."""
    with _lock:
        _estado["crono"] = texto


def get():
    with _lock:
        return dict(_estado)
