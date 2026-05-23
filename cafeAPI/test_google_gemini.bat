@echo off
REM Script de validacion rapida para Gemini 2.5 Flash
REM Uso: test_google_gemini.bat

setlocal enabledelayedexpansion
cls

echo.
echo =========================================================
echo  TEST: Google Gemini 2.5 Flash Integration
echo =========================================================
echo.

REM Cargar API key del .env
for /f "usebackq delims==" %%i in (.env) do (
    if "%%i"=="GEMINI_API_KEY" (
        set "API_KEY=%%j"
    )
)

if not defined API_KEY (
    echo ❌ GEMINI_API_KEY no encontrada en .env
    echo Asegúrate de tener: GEMINI_API_KEY=AIzaSyDOTGEaOK_8h_99axjw-kupLMj5G5z1YCE
    pause
    exit /b 1
)

echo API KEY: %API_KEY:~0,10%...%API_KEY:~-4%
echo.

REM Crear script Python temporal
set "TEST_SCRIPT=_test_gemini_temp.py"
(
    echo import os
    echo os.environ["GEMINI_API_KEY"] = "%API_KEY%"
    echo.
    echo try:
    echo     from google import genai
    echo     print("^[OK^] google-genai importado")
    echo except ImportError as e:
    echo     print("^[ERROR^] google-genai no instalado:", e)
    echo     exit(1)
    echo.
    echo try:
    echo     client = genai.Client(api_key="%API_KEY%")
    echo     print("^[OK^] Cliente Gemini configurado")
    echo except Exception as e:
    echo     print("^[ERROR^] Error configurando cliente:", e)
    echo     exit(1)
    echo.
    echo try:
    echo     print("^[...^] Llamando a gemini-2.5-flash...")
    echo     response = client.models.generate_content(
    echo         model="gemini-2.5-flash",
    echo         contents="Responde en una sola palabra: ¿funcionas?"
    echo     )
    echo     print("^[OK^] Respuesta:", response.text[:50])
    echo except Exception as e:
    echo     print("^[ERROR^] Error llamando a Gemini:", str(e)[:100])
    echo     exit(1)
    echo.
    echo print("^[SUCCESS^] ✅ Gemini 2.5 Flash funcionando correctamente")
) > %TEST_SCRIPT%

echo Ejecutando validacion...
echo.

.\cafefastapi-env\Scripts\python.exe %TEST_SCRIPT%
set "TEST_RESULT=%errorlevel%"

REM Limpiar
del /f /q %TEST_SCRIPT% 2>nul

echo.
if %TEST_RESULT% equ 0 (
    echo =========================================================
    echo  ✅ TEST EXITOSO - Sistema listo para usar
    echo =========================================================
    echo.
    echo Ahora:
    echo   1. Reinicia el servidor: uvicorn main:app --reload --port 8001
    echo   2. Prueba en navegador: http://localhost:8001/diagnostico/gemini
    echo.
) else (
    echo =========================================================
    echo  ❌ TEST FALLIDO - Revisa los errores arriba
    echo =========================================================
)

pause
