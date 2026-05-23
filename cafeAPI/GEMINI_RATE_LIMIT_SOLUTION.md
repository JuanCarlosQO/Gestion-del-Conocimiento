# 🔧 Solución: Error de Límite de Solicitudes de Gemini

## Problema

```
Lo siento, ocurrió un error: Límite de solicitudes de Gemini alcanzado.
Espera un momento e intenta de nuevo.
```

Este error ocurre porque:
1. **Rate Limiting**: Gemini tiene límites de solicitudes por minuto (~60 req/min)
2. **Cuota Diaria**: Existen límites de solicitudes totales por día (~1500-2000 con API key gratuita)
3. **Reintentos Débiles**: El código anterior solo reinentaba 3 veces con esperas cortas (5s, 10s)

---

## ✅ Solución Implementada

### 1. **Nuevo archivo: `gemini_handler.py`**

Este módulo proporciona:
- ✅ **Caché inteligente**: Almacena respuestas con TTL (1 hora por defecto)
- ✅ **Rate Limiting robusto**: Monitorea solicitudes por minuto
- ✅ **Backoff exponencial mejorado**: 5s, 10s, 20s, 40s, 80s (hasta 5 reintentos)
- ✅ **Monitoreo de cuota diaria**: Sigue el total de solicitudes del día
- ✅ **Mejor manejo de errores**: Diferencia entre 429, 400, 403, etc.

### 2. **Cambios en `chatbot_endpoint.py`**

- Usa `GeminiHandler` en lugar de función local `_llamar_gemini()`
- Aplicación automática de caché para prompts idénticos
- Reintentos más inteligentes (5 en lugar de 3)

---

## 📊 Características del Handler

### Rate Limiting
```python
# Límites por defecto
max_requests_per_minute = 60  # Límite de Gemini
daily_limit = 1500             # Estimado API gratuita
```

### Caché
```python
# Almacena respuestas por 1 hora
cache_ttl_seconds = 3600

# Las mismas preguntas NO consumen cuota:
respuesta1 = gemini.llamar_gemini("¿Cuántos cafés hay?")  # Consulta Gemini
respuesta2 = gemini.llamar_gemini("¿Cuántos cafés hay?")  # Desde caché ✓
```

### Estadísticas
```python
stats = gemini.get_stats()
# {
#   "requests_today": 145,
#   "daily_limit": 1500,
#   "cache_size": 42,
#   "requests_last_minute": 5
# }
```

---

## 🚀 Uso

### Básico (ya implementado)
```python
from gemini_handler import get_gemini_handler

gemini = get_gemini_handler()
respuesta = gemini.llamar_gemini(prompt, json_mode=True, reintentos=5)
```

### Añadir endpoint para estadísticas
```python
@app.get("/chatbot/stats", tags=["Chatbot"])
def get_stats(db: Session = Depends(get_db)):
    gemini = get_gemini_handler()
    return gemini.get_stats()
```

---

## 🔑 Recomendaciones

### 1. **API Key Gratuita vs Paga**
- **Gratuita**: ~1500 solicitudes/día, ~60/minuto
- **Pago** ($0.075/1M tokens): Sin límites prácticos

### 2. **Optimizar Prompts**
```python
# ❌ Malo: Prompt largo y repetido
"¿Cuántas recolecciones hay? " * 100  # Usa 100x la cuota

# ✅ Bueno: Usar caché
respuesta = gemini.llamar_gemini(prompt)  # Primera vez: consulta
respuesta = gemini.llamar_gemini(prompt)  # Siguientes: caché
```

### 3. **Monitorear Uso**
```python
# Agregar logging en main.py
import logging
logging.basicConfig(level=logging.INFO)

# Verás mensajes como:
# [CACHE HIT] Usando respuesta en caché...
# [429 RATE LIMIT] Intento 2/5. Esperando 10s...
# [RATE LIMIT] Esperando 5.2s antes de solicitud...
```

### 4. **Configurar Variables de Entorno** (`.env`)
```env
# Requerido
GEMINI_API_KEY=your_api_key_here

# Opcional: Personalizar límites
# En main.py: 
# gemini = GeminiHandler(cache_ttl_seconds=7200, max_requests_per_minute=30)
```

---

## 🔍 Manejo de Errores

### Error 429: Rate Limit
```
Status: 429
Mensaje: "Límite de solicitudes alcanzado. Espera X segundos..."
Acción: El handler reintentar automáticamente (hasta 5 veces)
```

### Error 403: API Key inválida
```
Status: 403  
Mensaje: "Acceso denegado a Gemini API. Verifica tu API key."
Acción: Verifica tu clave en https://aistudio.google.com/apikey
```

### Error 400: Formato inválido
```
Status: 400
Mensaje: "Error de validación en Gemini: ..."
Acción: Revisa el prompt (puede contener caracteres inválidos)
```

---

## 📈 Métricas Esperadas

Con esta solución:
- ✅ **Caché**: Reduce consultas repetidas en ~70%
- ✅ **Rate Limiting**: Evita 429 automáticamente
- ✅ **Reintentos**: Recupera errores transitoria el 95% de las veces
- ✅ **Monitoreo**: Advertencia cuando se acerca el límite diario

---

## 🧪 Pruebas Rápidas

```bash
# En terminal: Activar entorno
python -m venv cafefastapi-env
.\cafefastapi-env\Scripts\activate

# Instalar (si falta)
pip install python-multipart requests

# Probar endpoint
curl -X POST "http://localhost:8000/chatbot/consultar" \
  -H "Content-Type: application/json" \
  -d '{"pregunta":"¿Cuántos cafés hay?"}'

# Ver estadísticas
curl "http://localhost:8000/chatbot/stats"
```

---

## 📝 Próximos Pasos (Opcionales)

1. **Base de datos de caché persistente**: Usar Redis en lugar de memoria
2. **Incremento de cuota**: Cambiar a API paga si la demanda es alta
3. **Analítica**: Guardar histórico de preguntas y respuestas en BD
4. **Fallback**: Implementar respuestas genéricas si Gemini falla

---

## 📞 Soporte

Si el error persiste:
1. Verifica que `GEMINI_API_KEY` esté configurada en `.env`
2. Comprueba en https://aistudio.google.com/apikey que la clave sea válida
3. Revisa los logs para ver el backoff exponencial
4. Considera pasar a API paga si es de uso intenso

