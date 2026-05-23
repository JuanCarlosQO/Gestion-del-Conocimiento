import json
import time
from fastapi import HTTPException
from sqlalchemy import text
import google.generativeai as genai

# ── CHATBOT: Usando google-genai con gemini-2.5-flash ──────────────────────────

def responder_pregunta(pregunta: str, key: str, db, g):
    """
    Procesa una pregunta usando Gemini (google-genai), genera consultas SQL/SPARQL y retorna respuesta.
    
    Args:
        pregunta: Pregunta del usuario
        key: API key de Google Gemini
        db: Conexión SQLAlchemy a la base de datos
        g: Grafo RDF cargado con rdflib
    """
    
    # Configurar google-genai con el API key
    genai.configure(api_key=key)
    
    # Usar modelo gemini-2.5-flash
    model = genai.GenerativeModel("gemini-2.5-flash")

    def _llamar_gemini(prompt_text: str, json_mode: bool = False, reintentos: int = 3) -> str:
        """Llama a Gemini usando google-genai con reintento exponencial en caso de rate-limit."""
        for intento in range(reintentos):
            try:
                # Configurar respuesta en JSON si es necesario
                generation_config = {}
                if json_mode:
                    generation_config = {
                        "temperature": 1,
                        "response_mime_type": "application/json",
                    }
                
                # Llamar a Gemini
                response = model.generate_content(
                    prompt_text,
                    generation_config=genai.types.GenerationConfig(**generation_config) if generation_config else None,
                    request_options={"timeout": 45}
                )
                
                return response.text.strip()
            
            except Exception as ex:
                # Verificar si es un error de rate limit
                error_str = str(ex).lower()
                is_rate_limit = "429" in error_str or "rate" in error_str or "quota" in error_str
                
                if is_rate_limit and intento < reintentos - 1:
                    espera = (2 ** intento) * 5  # 5s, 10s, 20s
                    time.sleep(espera)
                    continue
                
                if is_rate_limit:
                    raise HTTPException(
                        status_code=429,
                        detail="Límite de solicitudes de Gemini alcanzado. Espera unos segundos e intenta de nuevo."
                    )
                
                if intento < reintentos - 1:
                    time.sleep(3)
                    continue
                
                raise HTTPException(
                    status_code=500, 
                    detail=f"Error llamando a Gemini (gemini-2.5-flash): {str(ex)[:300]}"
                )

    # ── PROMPT ÚNICO: traducción + respuesta en una sola llamada ─────────────────
    prompt_unico = f"""
Eres un asistente inteligente del sistema SIGIC (Sistema de Gestión de Información Cafetera).
Tu trabajo es responder preguntas sobre la finca usando la base de datos Postgres y la ontología RDF.

=== ESQUEMA POSTGRES ===
- persona(documento_persona PK, nombre_persona, edad_persona, telefono_persona, fk_tipo_documento)
- propietario(id_propietario PK FK→persona, email_propietario, estado_propietario bool)
- recolector(id_recolector PK FK→persona, fechainicio_recolector date, fechafin_recolector date, estado_recolector bool, diastrabajados_recolector int, fk_id_propietario, fk_id_finca)
- reporte(id_reporte PK, fecha_reporte date, totaltecoleccion_reporte numeric, estado_reporte bool, fk_id_recolector)
- pago(id_pago PK, fecha_pago date, preciokilo_pago numeric, estado_pago bool, monto_pago numeric, metodo_pago, fk_id_reporte)

=== ESQUEMA RDF (SPARQL) ===
PREFIX cafe: <http://www.semanticweb.org/cafe/>
Clases: cafe:finca (nombre,direccion,area,altitud,fk_idPropietario), cafe:lote (nombre,area,cantidad,estado), cafe:insumo (nombre,precio,tipo,estado,unidadMedida,metodoAplicacion), cafe:recoleccion (fecha,fk_idRecolector), cafe:eventoRecoleccion (cantidad), cafe:compra (fecha,cantidad,precio,estado), cafe:mantenimiento (fecha,tipo)
Relaciones: finca→lote (contieneLote), lote→eventoRecoleccion (estableceRecoleccion), eventoRecoleccion→recoleccion (generaRecoleccion), lote→mantenimiento (tieneMantenimiento)

=== PREGUNTA DEL USUARIO ===
"{pregunta}"

=== INSTRUCCIONES ===
1. Decide si la respuesta requiere SQL (datos de personas/pagos/reportes), SPARQL (fincas/lotes/insumos/RDF) o ambos.
2. Genera las consultas necesarias.
3. Retorna ÚNICAMENTE un JSON puro (sin markdown) con esta estructura exacta:
{{
  "database": "postgres" | "rdf" | "both",
  "sql": "<consulta SQL o null>",
  "sparql": "<consulta SPARQL completa con prefijos, o null>",
  "respuesta_directa": "<respuesta amigable en español para el usuario SI la puedes dar sin ejecutar consultas, o null si necesitas los datos primero>"
}}
"""

    # Paso 1: Obtener plan de consulta
    try:
        json_str = _llamar_gemini(prompt_unico, json_mode=True)
        plan = json.loads(json_str)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando respuesta de Gemini: {str(e)}")

    db_choice  = plan.get("database", "both")
    sql_query  = plan.get("sql")
    sparql_query = plan.get("sparql")
    respuesta_directa = plan.get("respuesta_directa")

    # Si Gemini pudo responder sin consultas, devolver directo (sin segunda llamada)
    if respuesta_directa and not sql_query and not sparql_query:
        return {
            "pregunta": pregunta,
            "respuesta": respuesta_directa,
            "detalles_tecnicos": {
                "database": db_choice, "sql": None,
                "resultados_sql": None, "sparql": None,
                "resultados_rdf": None, "errores": None
            }
        }

    # Paso 2: Ejecutar consultas
    resultados_sql     = None
    resultados_sparql  = None
    errores            = []

    if db_choice in ("postgres", "both") and sql_query:
        try:
            res_sql = db.execute(text(sql_query))
            resultados_sql = [dict(row) for row in res_sql.mappings()]
        except Exception as e:
            errores.append(f"Error SQL: {str(e)}")

    if db_choice in ("rdf", "both") and sparql_query:
        try:
            res_sparql = g.query(sparql_query)
            vars_list  = [str(v) for v in res_sparql.vars]
            records    = []
            for row in res_sparql:
                row_dict = {}
                for var in vars_list:
                    try:
                        val = row[var]
                    except Exception:
                        val = getattr(row, var, None)
                    if val is not None:
                        vs = str(val)
                        row_dict[var] = vs.split("/")[-1] if "semanticweb.org/cafe/" in vs else (
                            val.toPython() if hasattr(val, "toPython") else vs)
                    else:
                        row_dict[var] = None
                records.append(row_dict)
            resultados_sparql = records
        except Exception as e:
            errores.append(f"Error SPARQL: {str(e)}")

    # Paso 3: Generar respuesta final (segunda llamada a Gemini)
    ctx = {
        "resultados_postgres": resultados_sql,
        "resultados_rdf":      resultados_sparql,
        "errores":             errores
    }
    prompt_resumen = f"""
Eres un asistente experto en gestión de fincas cafeteras del sistema SIGIC.
El usuario preguntó: "{pregunta}"

Aquí están los datos obtenidos de la base de datos:
{json.dumps(ctx, ensure_ascii=False, indent=2, default=str)}

Redacta una respuesta clara, amigable y profesional en español.
- Usa los datos concretos de los resultados (nombres, fechas, montos).
- Si hay errores o no hay datos, dilo amablemente y sugiere qué verificar.
- No muestres código SQL ni SPARQL al usuario.
- Sé conciso pero completo. Usa viñetas si hay varios datos.
"""
    try:
        respuesta_final = _llamar_gemini(prompt_resumen, json_mode=False)
    except HTTPException as e:
        # Si falla la segunda llamada, dar la respuesta con los datos crudos
        if resultados_sql or resultados_sparql:
            respuesta_final = f"Datos encontrados, pero no pude generar resumen. Resultados: {json.dumps(ctx, ensure_ascii=False, default=str)[:500]}"
        else:
            raise

    return {
        "pregunta": pregunta,
        "respuesta": respuesta_final,
        "detalles_tecnicos": {
            "database":        db_choice,
            "sql":             sql_query,
            "resultados_sql":  resultados_sql,
            "sparql":          sparql_query,
            "resultados_rdf":  resultados_sparql,
            "errores":         errores if errores else None
        }
    }
