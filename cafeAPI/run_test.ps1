# Script para ejecutar el test de Gemini Handler
Set-Location $PSScriptRoot
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Ejecutando Test de Gemini Handler" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Usar Python del entorno virtual
$pythonPath = ".\cafefastapi-env\Scripts\python.exe"

if (Test-Path $pythonPath) {
    & $pythonPath test_gemini_handler.py
} else {
    Write-Host "❌ Python no encontrado en: $pythonPath" -ForegroundColor Red
    Write-Host "Intenta crear el entorno virtual con: python -m venv cafefastapi-env" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Presiona Enter para cerrar..." -ForegroundColor Gray
Read-Host
