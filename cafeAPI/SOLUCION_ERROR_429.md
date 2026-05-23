# 🆘 Solución: Error 429 - Too Many Requests

## ¿Por Qué Ocurre?

El error **429** ocurre cuando se alcanza el **límite de solicitudes** de la API de Gemini. Hay 3 niveles:

1. **API de Gemini** (Google): Límite muy bajo en plan gratuito (~30 req/min)
2. **Rate Limiting Local** (Tu servidor): Protege de sobrecarga
3. **Caché**: Si funciona bien, evita llamadas repetidas

---

## 🔍 Diagnóstico

### Ver estado actual:
```bash
# Terminal 1: Verificar diagnostico
curl http://localhost:8000/diagnostico/gemini

# Terminal 2: Ver estado del rate limiting
curl http://localhost:8000/chatbot/estado
```

**Salida esperada de `/chatbot/estado`:**
```json
{
  "status": "ok",
  "modelo": "gemini-2.5-flash",
  "solicitudes_hoy": 45,
  "limite_diario": 300,
  "porcentaje_usado": "15.0%",
  "solicitudes_ultimo_minuto": 2,
  "cache_items": 12,
  "cache_ttl_segundos": 7200,
  "recomendacion": "Si el porcentaje es >80%, espera hasta mañana..."
}
```

---

## ✅ Soluciones (En Orden de Prioridad)

### **1. Esperar 1-2 minutos** ⏳
- El caché durará 2 horas (7200 segundos)
- Las preguntas idénticas NO consumirán cuota

### **2. Verificar Limits Actuales** 📊
Cambios realizados:
- ✅ Caché: **1 hora → 2 horas** (evita llamadas repetidas)
- ✅ Límite por minuto: **60 → 20 req/min**
- ✅ Límite diario: **1500 → 300 req/día**

Estos límites son **conservadores** para respetar el plan gratuito.

### **3. Estrategia de Preguntas** 💡
Para ahorrar cuota:
- ❌ **Evita**: Hacer preguntas ligeramente diferentes (cada una = nueva llamada)
- ✅ **Usa**: Las mismas preguntas (el caché las sirve gratis)
- ✅ **Ejemplos**: 
  - Q1: "¿Cuántas fincas hay?" → **CACHEADA**
  - Q1 de nuevo: "¿Cuántas fincas hay?" → **SIN COSTO (de caché)**
  - Q2: "¿Cuántas fincas tengo?" → **NUEVA LLAMADA** (pregunta diferente)

### **4. Plan Pagado (Recomendado)** 💳
Si necesitas más cuota, obtén un plan pagado:
1. Ve a: https://aistudio.google.com/pricing
2. Activa billing
3. Usa la misma API key (los límites suben automáticamente a ~1000 req/min)

---

## 🔧 Configuración Personalizada

Si quieres cambiar los límites manualmente:

**Archivo**: `cafeAPI/gemini_handler.py` (líneas 47-50)

```python
# Cambiar estos valores:
self.max_requests_per_minute = 20        # Solicitudes por minuto
self.daily_limit = 300                   # Solicitudes por día
```

**Ejemplos de límites según plan:**

| Plan | Límite/Min | Límite/Día | TTL Caché |
|------|-----------|-----------|----------|
| **Gratuito** | 20 | 300 | 2h |
| **Pagado** | 500 | 10,000+ | 2h |

---

## 📋 Checklist de Debugging

- [ ] Ejecutar: `curl http://localhost:8000/chatbot/estado`
- [ ] Ver porcentaje de uso de cuota diaria
- [ ] Si >80%: Esperar hasta mañana
- [ ] Si <80%: Revisar logs del servidor (`[429]` en stderr)
- [ ] Verificar API key correcta en `.env`
- [ ] Reiniciar servidor: `Ctrl+C` en terminal uvicorn

---

## 📝 Logs Útiles

Cuando hagas una llamada, verás en servidor:

**Caso 1: Cache hit** (pregunta repetida, SIN costo)
```
[CACHE HIT] ¿Cuántas fincas hay?...
```

**Caso 2: Primera llamada** (nueva pregunta, CON costo)
```
[✓] Gemini OK (intento 1/5)
```

**Caso 3: Rate limit por minuto**
```
[429] Intento 1/5. Esperando 5s...
Límite por minuto alcanzado (20/min). Espera 15 segundos.
```

**Caso 4: Cuota diaria agotada**
```
Cuota diaria de Gemini agotada (300/300). Espera hasta mañana...
```

---

## 🆘 Si el error persiste

1. **Reinicia el servidor:**
   ```bash
   cd cafeAPI
   # Presiona Ctrl+C en la terminal uvicorn
   # Espera 2 segundos
   # Ejecuta:
   uvicorn main:app --reload --port 8001
   ```

2. **Limpia el caché manualmente:**
   - El servidor gestiona el caché automáticamente
   - No requiere acción manual

3. **Contacta a Google:**
   - Si el error viene de Gemini API (no del rate limiting local):
   - Visita: https://support.google.com/docs/answer/12674393

---

**Última actualización**: 22 de mayo de 2026
**Servidor**: FastAPI + google-genai
**Modelo**: gemini-2.5-flash
