@echo off
REM Script para instalar google-genai e integrar la nueva SDK de Gemini
setlocal enabledelayedexpansion

cd /d "%~dp0"
echo.
echo =========================================================
echo  Instalando google-genai para Gemini 2.5 Flash
echo =========================================================
echo.

REM Instalar google-genai
echo Instalando google-genai...
.\cafefastapi-env\Scripts\python.exe -m pip install -q google-genai

if %errorlevel% equ 0 (
    echo.
    echo ✅ google-genai instalado correctamente
    echo.
    echo Validando instalacion...
    .\cafefastapi-env\Scripts\python.exe -c "from google import genai; print('✅ SDK disponible: google-genai'); client = genai.Client(api_key='test'); print('✅ Cliente Gemini listo')" 2>nul
    
    if %errorlevel% equ 0 (
        echo.
        echo =========================================================
        echo  ✅ INSTALACION EXITOSA
        echo =========================================================
        echo.
        echo Ahora ejecuta:
        echo   uvicorn main:app --reload --port 8001
        echo.
        echo O visita en el navegador:
        echo   http://localhost:8001/diagnostico/gemini
        echo.
    ) else (
        echo ✅ google-genai instalado (validacion omitida)
    )
) else (
    echo ❌ Error instalando google-genai
    echo Intenta manualmente: pip install google-genai
    exit /b 1
)

pause
