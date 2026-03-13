@echo off
title SERVIDOR MESA DE AYUDA LOCAL
color 0A

cd /d %~dp0

echo ===============================
echo INICIANDO SERVIDOR LOCAL
echo ===============================
echo.

:loop

echo Iniciando Flask...
python app.py

echo.
echo ===============================
echo El servidor se detuvo
echo Reiniciando en 5 segundos...
echo ===============================
timeout /t 5 >nul

goto loop