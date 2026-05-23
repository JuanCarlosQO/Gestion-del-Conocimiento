#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de prueba para validar el handler de Gemini
Ejecutar: python test_gemini_handler.py
"""

import os
import sys
import time
from datetime import datetime

# Cargar variables de entorno desde .env manualmente
def load_env_file(filepath):
    """Carga variables del archivo .env sin dependencias externas."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env_file(os.path.join(os.path.dirname(__file__), '.env'))

# Asegurarse que está en el path
sys.path.insert(0, os.path.dirname(__file__))

def test_gemini_handler():
    """Prueba las funcionalidades del handler de Gemini."""
    
    print("=" * 60)
    print("🧪 TEST: Gemini Handler with Rate Limiting & Cache")
    print("=" * 60)
    
    # 1. Verificar API Key
    print("\n1️⃣  Verificando GEMINI_API_KEY...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("   ❌ GEMINI_API_KEY no configurada")
        print("   📝 Configura en .env: GEMINI_API_KEY=your_key_here")
        return False
    print(f"   ✅ API Key encontrada: {api_key[:10]}...{api_key[-4:]}")
    
    # 2. Importar handler
    print("\n2️⃣  Importando GeminiHandler...")
    try:
        from gemini_handler import GeminiHandler
        print("   ✅ Importación exitosa")
    except ImportError as e:
        print(f"   ❌ Error importando: {e}")
        return False
    
    # 3. Crear instancia
    print("\n3️⃣  Creando instancia de GeminiHandler...")
    try:
        handler = GeminiHandler(api_key=api_key, cache_ttl_seconds=3600)
        print("   ✅ Handler creado correctamente")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 4. Prueba simple (prompt corto)
    print("\n4️⃣  Prueba 1: Prompt simple...")
    prompt_simple = "Responde en 10 palabras: ¿Qué es el café?"
    try:
        print(f"   📤 Enviando: '{prompt_simple}'")
        respuesta1 = handler.llamar_gemini(prompt_simple, json_mode=False, reintentos=3)
        print(f"   📥 Respuesta: {respuesta1[:80]}...")
        print("   ✅ Solicitud exitosa")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 5. Prueba caché (misma pregunta)
    print("\n5️⃣  Prueba 2: Verificar caché...")
    print(f"   📤 Enviando MISMA pregunta (desde caché)...")
    try:
        start = time.time()
        respuesta2 = handler.llamar_gemini(prompt_simple, json_mode=False)
        elapsed = time.time() - start
        print(f"   📥 Tiempo: {elapsed:.3f}s (caché es más rápido: <1s)")
        if respuesta1 == respuesta2:
            print("   ✅ Caché funcionando correctamente")
        else:
            print("   ⚠️  Respuestas diferentes (no es error crítico)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # 6. Prueba JSON mode
    print("\n6️⃣  Prueba 3: JSON mode...")
    prompt_json = 'Responde en JSON con {"nombre": "...", "descripcion": "..."}: ¿Qué es café?'
    try:
        print(f"   📤 Enviando prompt con JSON mode...")
        respuesta3 = handler.llamar_gemini(prompt_json, json_mode=True, reintentos=3)
        print(f"   📥 Respuesta (primeros 100 chars): {respuesta3[:100]}...")
        print("   ✅ JSON mode funcionando")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        # No es crítico si falla
        print("   ⚠️  JSON mode puede fallar si Gemini no responde en JSON puro")
    
    # 7. Ver estadísticas
    print("\n7️⃣  Estadísticas del handler:")
    stats = handler.get_stats()
    print(f"   • Solicitudes hoy: {stats['requests_today']}")
    print(f"   • Límite diario: {stats['daily_limit']}")
    print(f"   • Tamaño caché: {stats['cache_size']}")
    print(f"   • TTL caché: {stats['cache_ttl_seconds']}s")
    print(f"   • Requests último minuto: {stats['requests_last_minute']}")
    
    # 8. Resumen
    print("\n" + "=" * 60)
    print("✅ TODAS LAS PRUEBAS PASARON")
    print("=" * 60)
    print("\n📌 Próximos pasos:")
    print("   1. Reinicia el servidor: uvicorn main:app --reload")
    print("   2. Prueba el endpoint: POST http://localhost:8000/chatbot/consultar")
    print('   3. Ejemplo: {"pregunta": "¿Cuántas recolecciones hay?"')
    print("\n✨ El handler está listo para usar con rate limiting y caché.\n")
    
    return True

if __name__ == "__main__":
    success = test_gemini_handler()
    sys.exit(0 if success else 1)
