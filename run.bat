@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem NEXUS necesita Python 3.12 o 3.13 (el 3.14 todavia no tiene binarios de pygame/onnxruntime).
rem Si tienes ambos instalados, "py -3.12" usa el correcto.
py -3.12 main.py
if errorlevel 1 python main.py
pause
