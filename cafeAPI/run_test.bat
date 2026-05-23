@echo off
cd /d "%~dp0"
echo Ejecutando test de Gemini Handler...
echo.
.\cafefastapi-env\Scripts\python.exe test_gemini_handler.py
pause
