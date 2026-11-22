"""Auto-actualización de NEXUS (cuando corre como .exe congelado).

El .exe instalado vigila su propia carpeta y la de Descargas: si aparece
un «nexus*.exe» con FileVersion MAYOR (leída del PE, sin pywin32), se
ofrece como update. Al instalar, un .bat lanzado aparte espera a que
este proceso muera, copia el nuevo .exe sobre el viejo, relanza NEXUS
y se borra solo — así el .exe puede reemplazarse a sí mismo.

También soporta un manifiesto remoto (config.UPDATE_MANIFEST_URL, por
defecto vacío): un JSON {"version": "1.0.1", "url": "https://…/nexus.exe"}
que se descarga a temporal y se valida que sea PE (MZ).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import version as _ver

FIRMA_PE = b"\xbd\x04\xef\xfe"   # VS_FIXEDFILEINFO (0xFEEF04BD, little-endian)


def exe_actual():
    """Ruta del .exe corriendo (None si no estamos congelados)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return None


def _a_tupla(v):
    nums = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in nums[:4]) if nums else (0,)


def version_propia():
    return _ver.APP_VERSION


def version_de_exe(ruta):
    """FileVersion embebida en el PE (VS_FIXEDFILEINFO), leyendo por chunks."""
    try:
        with open(ruta, "rb") as f:
            prev = b""
            while True:
                chunk = f.read(8 * 1024 * 1024)
                if not chunk:
                    return None
                data = prev + chunk
                i = data.find(FIRMA_PE)
                if i >= 0 and i + 16 <= len(data):
                    ms = int.from_bytes(data[i + 8:i + 12], "little")
                    ls = int.from_bytes(data[i + 12:i + 16], "little")
                    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
                prev = chunk[-3:]
    except Exception:
        return None


def _carpetas_vigilar():
    cs = []
    exe = exe_actual()
    if exe is not None:
        cs.append(exe.parent)
    dl = Path.home() / "Downloads"
    if dl.is_dir():
        cs.append(dl)
    cs.append(Path(tempfile.gettempdir()))
    return cs


def _candidatos_locales():
    exe = exe_actual()
    if exe is None:
        return []
    out = []
    for carpeta in _carpetas_vigilar():
        try:
            for f in carpeta.glob("nexus*.exe"):
                try:
                    if f.resolve() == exe:
                        continue
                except Exception:
                    continue
                if f.stat().st_size < 1_000_000:   # un .exe de verdad pesa
                    continue
                out.append(f)
        except Exception:
            pass
    return out


def _candidato_manifest():
    try:
        import config
        url = getattr(config, "UPDATE_MANIFEST_URL", "")
    except Exception:
        url = ""
    if not url:
        return None
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=8) as r:
            man = json.loads(r.read().decode("utf-8"))
        v = str(man.get("version", ""))
        u = str(man.get("url", ""))
        if not v or not u or _a_tupla(v) <= _a_tupla(version_propia()):
            return None
        tmp = Path(tempfile.gettempdir()) / f"nexus_update_v{v}.exe"
        urllib.request.urlretrieve(u, tmp)
        with open(tmp, "rb") as f:
            if f.read(2) != b"MZ":
                return None
        return {"hay": True, "version": v, "ruta": str(tmp),
                "origen": "nube", "actual": version_propia()}
    except Exception:
        return None


def buscar_update():
    """{'hay': bool, 'version', 'ruta', 'origen', 'actual'} — el mejor candidato."""
    actual = _a_tupla(version_propia())
    mejor, mejor_v = None, None
    for f in _candidatos_locales():
        v = version_de_exe(f) or ""
        tv = _a_tupla(v)
        if tv > actual and (mejor_v is None or tv > mejor_v):
            mejor, mejor_v = f, tv
    if mejor is not None:
        return {"hay": True, "version": version_de_exe(mejor), "ruta": str(mejor),
                "origen": "local", "actual": version_propia()}
    man = _candidato_manifest()
    if man:
        return man
    return {"hay": False, "actual": version_propia()}


def instalar_update(ruta):
    """Copia el .exe nuevo sobre el viejo tras morir este proceso (vía .bat)."""
    exe = exe_actual()
    if exe is None:
        return {"ok": False, "error": "solo aplica corriendo como .exe"}
    nuevo = Path(ruta).resolve()
    if not nuevo.is_file():
        return {"ok": False, "error": "no existe el .exe nuevo"}
    v = version_de_exe(nuevo) or ""
    if _a_tupla(v) <= _a_tupla(version_propia()):
        return {"ok": False, "error": f"{v or '?'} no es más nuevo que {version_propia()}"}
    bat = Path(tempfile.gettempdir()) / "nexus_update.bat"
    bat.write_text(
        "@echo off\r\n"
        "set /a n=0\r\n"
        ":copiar\r\n"
        f'copy /y "{nuevo}" "{exe}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        "  set /a n+=1\r\n"
        "  if %n% gtr 90 exit /b 1\r\n"
        "  ping 127.0.0.1 -n 2 >nul\r\n"
        "  goto copiar\r\n"
        ")\r\n"
        f'start "" "{exe}"\r\n'
        'del "%~f0"\r\n',
        encoding="ascii", errors="ignore")
    DETACHED = 0x00000008
    NEW_GROUP = 0x00000200
    subprocess.Popen(["cmd", "/c", str(bat)],
                     creationflags=DETACHED | NEW_GROUP,
                     close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "version": v}


def comprobar_en_segundo_plano(callback, espera=12):
    """Al arrancar: espera unos segundos y busca update sin bloquear."""
    import threading

    def _hilo():
        time.sleep(espera)
        try:
            r = buscar_update()
            if r.get("hay"):
                callback(r)
        except Exception:
            pass

    threading.Thread(target=_hilo, daemon=True).start()
