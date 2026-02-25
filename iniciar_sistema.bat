@echo off
title SISTEMA TICKETS INPHONITY + NGROK
color 0A

echo ==============================
echo   INICIANDO SISTEMA TICKETS
echo ==============================

cd /d %~dp0

echo Iniciando servidor Flask...
start cmd /k "python app.py"

timeout /t 5 > nul

echo Iniciando tunel ngrok...
start cmd /k "ngrok http 8000"

echo.
echo ==============================
echo   SISTEMA Y NGROK ACTIVOS
echo ==============================
pause
