# --- Chatbot Inteligente Semántico ---
import json
from openai_handler import get_openai_handler

class ChatbotConsultaReq(BaseModel):
    pregunta: str

@app.post("/chatbot/consultar", tags=["Chatbot"])
def chatbot_consultar(data: ChatbotConsultaReq, db: Session = Depends(get_db)):
    pregunta = data.pregunta.strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")

    # Obtener handler de OpenAI (singleton con caché y rate limiting)
    openai = get_openai_handler()

    # ── PROMPT ÚNICO: traducción + consultas + respuesta en una sola llamada ──
    prompt_unico = f"""
Eres el asistente inteligente del sistema SIGIC (Gestión de Información Cafetera).
Responde la pregunta del usuario usando los esquemas de datos disponibles.

=== BASE DE DATOS POSTGRESQL ===
- persona(documento_persona PK, nombre_persona, edad_persona, telefono_persona, fk_tipo_documento)
- propietario(id_propietario PK→persona, email_propietario, estado_propietario bool)
- recolector(id_recolector PK→persona, fechainicio_recolector date, fechafin_recolector date, estado_recolector bool, diastrabajados_recolector int, fk_id_propietario, fk_id_finca)
- reporte(id_reporte PK, fecha_reporte date, totaltecoleccion_reporte numeric, estado_reporte bool, fk_id_recolector)
- pago(id_pago PK, fecha_pago date, preciokilo_pago numeric, estado_pago bool, monto_pago numeric, metodo_pago, fk_id_reporte)

=== ONTOLOGÍA RDF (SPARQL) ===
PREFIX cafe: <http://www.semanticweb.org/cafe/>
Clases: cafe:finca (nombre,direccion,area,altitud,fk_idPropietario),
        cafe:lote (nombre,area,cantidad,estado),
        cafe:insumo (nombre,precio,tipo,estado,unidadMedida,metodoAplicacion),
        cafe:recoleccion (fecha,fk_idRecolector),
        cafe:eventoRecoleccion (cantidad) → relaciones: ocurreEn→lote, generaRecoleccion→recoleccion
        cafe:mantenimiento (fecha,tipo), cafe:compra (fecha,cantidad,precio,estado)

=== PREGUNTA ===
"{pregunta}"

=== TAREA ===
1. Decide si necesitas SQL (personas/pagos/reportes), SPARQL (fincas/lotes/insumos) o ambos.
2. Si puedes responder sin consultas (pregunta general, saludo, etc.), pon sql:null y sparql:null.
3. Devuelve SOLO JSON puro sin markdown con esta estructura exacta:
{{
  "database": "postgres" | "rdf" | "both" | "none",
  "sql": "<consulta SQL válida o null>",
  "sparql": "<consulta SPARQL completa con prefijos o null>",
  "respuesta_directa": "<respuesta amigable en español si no necesitas datos, si no: null>"
}}
"""

    # Primera llamada — obtener plan
    try:
        json_str = openai.llamar_openai(prompt_unico, json_mode=True, reintentos=5)
        plan = json.loads(json_str)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando plan de OpenAI: {str(e)}")

    db_choice        = plan.get("database", "none")
    sql_query        = plan.get("sql")
    sparql_query     = plan.get("sparql")
    respuesta_directa = plan.get("respuesta_directa")

    # Si Gemini respondió sin necesitar datos
    if respuesta_directa and not sql_query and not sparql_query:
        return {
            "pregunta": pregunta,
            "respuesta": respuesta_directa,
            "detalles_tecnicos": {
                "database": db_choice, "sql": None, "resultados_sql": None,
                "sparql": None, "resultados_rdf": None, "errores": None
            }
        }

    # Ejecutar consultas
    resultados_sql    = None
    resultados_sparql = None
    errores           = []

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
                        row_dict[var] = (vs.split("/")[-1] if "semanticweb.org/cafe/" in vs
                                         else (val.toPython() if hasattr(val, "toPython") else vs))
                    else:
                        row_dict[var] = None
                records.append(row_dict)
            resultados_sparql = records
        except Exception as e:
            errores.append(f"Error SPARQL: {str(e)}")

    # Segunda llamada — generar respuesta amigable con los datos
    ctx = {
        "resultados_postgres": resultados_sql,
        "resultados_rdf":      resultados_sparql,
        "errores":             errores
    }
    prompt_resumen = f"""
Eres el asistente del sistema SIGIC de gestión de fincas cafeteras.
El usuario preguntó: "{pregunta}"

Datos obtenidos de la base de datos:
{json.dumps(ctx, ensure_ascii=False, indent=2, default=str)}

Redacta una respuesta clara, amigable y profesional en español para el usuario.
- Usa los datos concretos (nombres, fechas, montos, cantidades).
- Si no hay datos o hay errores, dilo con cortesía y sugiere qué verificar.
- No muestres SQL ni SPARQL.
- Sé conciso. Usa viñetas si hay varios elementos.
"""
    try:
        respuesta_final = gemini.llamar_gemini(prompt_resumen, json_mode=False, reintentos=5)
    except HTTPException as e:
        # Si falla la 2da llamada y ya tenemos datos, dar respuesta básica
        if resultados_sql or resultados_sparql:
            respuesta_final = (
                "Se encontraron datos pero no pude generar el resumen. "
                f"Resultados: {json.dumps(ctx, ensure_ascii=False, default=str)[:400]}"
            )
        else:
            raise

    return {
        "pregunta": pregunta,
        "respuesta": respuesta_final,
        "detalles_tecnicos": {
            "database":       db_choice,
            "sql":            sql_query,
            "resultados_sql": resultados_sql,
            "sparql":         sparql_query,
            "resultados_rdf": resultados_sparql,
            "errores":        errores if errores else None
        }
    }
