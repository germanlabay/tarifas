@echo off
chcp 65001 >nul
cd /d "%~dp0docs"
title Probar la app de tarifas
echo.
echo  Servidor de prueba en http://localhost:8080
echo  Deje esta ventana abierta mientras usa la app.
echo  Para cortarlo: cierre la ventana o presione Ctrl+C.
echo.
start "" http://localhost:8080
..\venv\Scripts\python.exe -m http.server 8080
