@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Publicar tarifas
echo.
echo  Leyendo la planilla de tarifas ...
echo.
venv\Scripts\python.exe scripts\publicar.py --git
echo.
echo  ----------------------------------------------------------------
echo  Cierre esta ventana. Si hubo ERRORES, corrija el Excel y repita.
echo  ----------------------------------------------------------------
echo.
pause
