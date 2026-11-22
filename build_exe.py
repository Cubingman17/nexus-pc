"""Compila NEXUS como dist/nexus.exe (PyInstaller, onefile, windowed).

IMPORTANTE: el build NO usa config.py del repo (tiene tus claves API).
Copia el árbol a build/src, pone ahí config.example.py como config.py
(sin claves) y compila desde ahí. Tus ajustes reales viven en
~/nexus_ajustes.json (fuera del repo) y sobreviven al update.

Uso:  py -3.12 build_exe.py
Sale: dist/nexus.exe  (con icono, metadatos de versión v1.0.0 y nombre
      «nexus»; probá con:  dist\\nexus.exe --version)
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BUILD = ROOT / "build"
SRC = BUILD / "src"
DIST = ROOT / "dist"

MODULOS = ["main.py", "webui.py", "audio.py", "llm.py", "stt.py", "tts.py",
           "tools.py", "estado.py", "briefing.py", "diagnostico.py",
           "gui.py", "panel.py", "updater.py", "version.py"]

HIDDEN = [
    "webview", "sounddevice", "faster_whisper", "ctranslate2",
    "onnxruntime", "openwakeword", "edge_tts", "pygame", "keyboard",
    "comtypes", "pycaw", "docx", "psutil", "requests", "numpy", "PIL",
    "config", "updater", "version",
]


def version_file(v: str) -> Path:
    nums = v.split(".")
    while len(nums) < 4:
        nums.append("0")
    fv = tuple(int(x) for x in nums[:4])
    p = BUILD / "version.txt"
    p.write_text(f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={fv}, prodvers={fv},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904b0', [
        StringStruct('FileDescription', 'NEXUS - asistente de voz local'),
        StringStruct('FileVersion', '{v}'),
        StringStruct('ProductName', 'nexus'),
        StringStruct('ProductVersion', '{v}'),
        StringStruct('OriginalFilename', 'nexus.exe'),
        StringStruct('InternalName', 'nexus'),
        StringStruct('CompanyName', 'NEXUS'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x409, 1200])])
  ]
)
""", encoding="utf-8")
    return p


def main():
    import version
    v = version.APP_VERSION
    print(f"== build nexus v{v} ==")

    if SRC.exists():
        shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    for m in MODULOS:
        shutil.copy2(ROOT / m, SRC / m)
    shutil.copy2(ROOT / "config.example.py", SRC / "config.py")  # SIN claves
    shutil.copytree(ROOT / "web", SRC / "web")
    shutil.copytree(ROOT / "assets", SRC / "assets")
    # el icono vive dentro del build dir
    assert (SRC / "assets" / "nexus.ico").exists(), "falta assets/nexus.ico (py -3.12 make_icon.py)"

    vf = version_file(v)
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
           "--onefile", "--windowed", "--name", "nexus",
           "--icon", str(SRC / "assets" / "nexus.ico"),
           "--version-file", str(vf),
           "--distpath", str(DIST), "--workpath", str(BUILD / "pyinst"),
           "--specpath", str(BUILD),
           "--add-data", f"{SRC / 'web'};web",
           "--log-level", "WARN"]
    for h in HIDDEN:
        cmd += ["--hidden-import", h]
    cmd.append(str(SRC / "main.py"))

    print(" ".join(cmd[:12]), "…")
    r = subprocess.run(cmd, cwd=SRC)
    if r.returncode != 0:
        print("BUILD FALLÓ")
        sys.exit(r.returncode)
    exe = DIST / "nexus.exe"
    print(f"OK → {exe}  ({exe.stat().st_size / 1e6:.0f} MB)")
    print(f"probalo:  {exe} --version")


if __name__ == "__main__":
    main()
