
import os
from pathlib import Path

# Cargar .env antes de cualquier otra cosa
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Body
from rdflib import Graph, RDF, OWL, Namespace, URIRef, Literal, XSD
from rdflib.plugins.sparql import prepareQuery
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from database import get_db, Base, ensure_recolector_propietario_finca_columns
from models import (
    persona,
    propietario,
    recolector,
    tipoDoc,
    reporte,
    pago,
    usuario,
    cat_tipo_insumo,
    cat_unidad_medida,
    cat_metodo_aplicacion,
)
from schemas import fincaModel, loteModel, insumoModel, compraModel, recoleccionModel, suministraInsumoModel, eventoRecoleccionModel, inventarioModel
from schemas import personaModel, propietarioModel, recolectorModel, tipoDocModel, reporteModel, pagoModel, loginModel, usuarioModel
from schemas import catTipoInsumoModel, catUnidadMedidaCreateModel, catMetodoAplicacionCreateModel
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="API Ontología RDF", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción pon la URL de tu Django
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
CAFE = Namespace("http://www.semanticweb.org/cafe/")

g = Graph()
g.parse("CafeV9_Final.rdf", format="xml")

print(f"Ontología cargada: {len(g)} triples")

ensure_recolector_propietario_finca_columns()

class reporteDiarioReq(BaseModel):
    id_recolector: str
    fecha: str  # YYYY-MM-DD


class liquidacionRecolectorReq(BaseModel):
    id_recolector: str
    precio_kilo: float
    propietario_doc: Optional[str] = None  # si viene, debe coincidir con fk_id_propietario del recolector


class DiaFinanzaManual(BaseModel):
    fecha: str  # YYYY-MM-DD
    kg_dia: float = 0
    precio_kilo: float = 0
    ausente: bool = False
    metodo_pago: Optional[str] = "Efectivo"


class GenerarPagoDiasReq(BaseModel):
    id_recolector: str
    dias: List[DiaFinanzaManual]
    propietario_doc: Optional[str] = None


def _rdf_propietario_de_finca(finca_id: str) -> Optional[str]:
    fid = (finca_id or "").strip()
    if not fid:
        return None
    uri = URIRef(f"http://www.semanticweb.org/cafe/{fid}")
    if (uri, None, None) not in g:
        return None
    for _, _, o in g.triples((uri, CAFE.fk_idPropietario, None)):
        return str(o).split("/")[-1]
    return None


def _kg_recolector_en_fecha(recolector_id: str, fecha_str: str) -> float:
    rid = (recolector_id or "").strip()
    fs = (fecha_str or "").strip()[:10]
    total = 0.0
    rec_uris = []
    for rec_uri, _, r_obj in g.triples((None, CAFE.fk_idRecolector, None)):
        if str(r_obj).strip() != rid:
            continue
        for _, __, f in g.triples((rec_uri, CAFE.fecha, None)):
            if str(f).strip()[:10] == fs:
                rec_uris.append(rec_uri)
                break
    for rec_uri in rec_uris:
        for ev_uri, _, _ in g.triples((None, CAFE.generaRecoleccion, rec_uri)):
            for _, __, q in g.triples((ev_uri, CAFE.cantidad, None)):
                try:
                    total += float(str(q))
                except Exception:
                    pass
    return total


# Listar todas las clases ----------------------
@app.get("/clases")
def get_clases():
    query = """
        SELECT DISTINCT ?clase WHERE {
            ?clase a owl:Class .
            FILTER(!isBlank(?clase))
        }
    """
    resultados = g.query(query, initNs={"owl": OWL})
    clases = [str(row.clase) for row in resultados]
    return {"total": len(clases), "clases": clases}


# Listar todas las propiedades ------------------
@app.get("/propiedades")
def get_propiedades():
    query = """
        SELECT DISTINCT ?prop WHERE {
            { ?prop a owl:ObjectProperty }
            UNION
            { ?prop a owl:DatatypeProperty }
        }
    """
    resultados = g.query(query, initNs={"owl": OWL})
    props = [str(row.prop) for row in resultados]
    return {"total": len(props), "propiedades": props}


# Listar todos los individuos ----------------------
@app.get("/individuos")
def get_individuos():
    query = """
        SELECT DISTINCT ?ind ?tipo WHERE {
            ?ind a ?tipo .
            ?tipo a owl:Class .
            FILTER(!isBlank(?ind))
        }
    """
    resultados = g.query(query, initNs={"owl": OWL})
    individuos = [{"individuo": str(row.ind), "tipo": str(row.tipo)} for row in resultados]
    return {"total": len(individuos), "individuos": individuos}




### Apache JENA -----------------------Ontologia

# --- Si existe el individuo
def existe_recurso(id_recurso: str) -> bool:
    uri = URIRef(f"http://www.semanticweb.org/cafe/{id_recurso}")
    return (uri, None, None) in g

# ---Get individuo ----------
@app.get("/detalle/{id_recurso}", tags=["consultas"])
def get_detalle_individual(id_recurso: str):
    
    uri_individuo = URIRef(f"http://www.semanticweb.org/cafe/{id_recurso}")
    

    if (uri_individuo, None, None) not in g:
        raise HTTPException(
            status_code=404, 
            detail=f"El individuo '{id_recurso}' no existe en la base de datos."
        )

    detalles = {}
    relaciones = {}
    
    for p, o in g.predicate_objects(uri_individuo):
        nombre_prop = str(p).split('/')[-1]
        if nombre_prop == "type": continue
        
        if isinstance(o, Literal):
            detalles[nombre_prop] = o.toPython()
        else:
            id_relacionado = str(o).split('/')[-1]
            relaciones[nombre_prop] = id_relacionado

    return {
        "Id": id_recurso,
        "Datos": detalles,
        "Relaciones": relaciones
    }

# --- Get por clase ----------

@app.get("/detallesClase/{nombre_clase}", tags=["consultasClase"])
def get_individuosClase(nombre_clase: str):
  
    uri_clase = URIRef(f"http://www.semanticweb.org/cafe/{nombre_clase}")
    
    query = """
        SELECT ?ind ?p ?o WHERE {
            ?ind rdf:type ?clase .
            ?ind ?p ?o .
            FILTER(?clase = %s)
            FILTER(isLiteral(?o))
        }
    """ % uri_clase.n3() # n3formatea la URI 

    try:
        resultados = g.query(query)
        respuesta = {}
        for row in resultados:
            ind_id = str(row.ind).split('/')[-1]
            propiedad = str(row.p).split('/')[-1]
            valor = row.o.toPython()
            if ind_id not in respuesta:
                respuesta[ind_id] = {} 
            respuesta[ind_id][propiedad] = valor
        if not respuesta:
            return {"mensaje": f"No se encontraron individuos para  '{nombre_clase}'"}
        return {
            "Clase": nombre_clase,
            "Total de registros": len(respuesta),
            "Individuos": respuesta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar")

# --Eliminar por id individuo

@app.delete("/individuos/{id_recurso}", tags=["Eliminar"])
def eliminar_individuo(id_recurso: str):
    uri_encontrar = URIRef(f"http://www.semanticweb.org/cafe/{id_recurso}")
    
    if (uri_encontrar, None, None) not in g and (None, None, uri_encontrar) not in g:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró el individuo"
        )
    try:
        g.remove((uri_encontrar, None, None))
        g.remove((None, None, uri_encontrar))
        
        g.serialize(destination="CafeV9_Final.rdf", format="xml")
        return {
            "mensaje": f"El individuo ha sido eliminado.",
            "id_eliminado": id_recurso
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al intentar eliminar"
        )

# --Editar un individuo
@app.put("/corregirIndividuo/{id_recurso}", tags=["Editar"])
def editar_individuo(id_recurso: str, nuevos_datos: dict):
    uri_editar = URIRef(f"http://www.semanticweb.org/cafe/{id_recurso}")
    
    if (uri_editar, None, None) not in g:
        raise HTTPException(
            status_code=404, 
            detail=f"No se puede editar"
        )
    
    try:
        tipo_original = g.value(uri_editar, RDF.type)
        for p, o in g.predicate_objects(uri_editar):
            if isinstance(o, Literal):
                g.remove((uri_editar, p, o))

        for propiedad, valor in nuevos_datos.items():
            prop_uri = CAFE[propiedad] 
            
            if isinstance(valor, bool):
                nuevo_valor = Literal(valor, datatype=XSD.boolean)
            elif isinstance(valor, int):
                nuevo_valor = Literal(valor, datatype=XSD.int)
            elif isinstance(valor, float):
                nuevo_valor = Literal(valor, datatype=XSD.double)
            else:
                nuevo_valor = Literal(str(valor), datatype=XSD.string)
            
            g.add((uri_editar, prop_uri, nuevo_valor))
        if tipo_original:
            g.add((uri_editar, RDF.type, tipo_original))

        g.serialize(destination="CafeV9_Final.rdf", format="xml")
        return {
            "mensaje": f"Individuo '{id_recurso}' actualizado correctamente.",
            "datos_actualizados": nuevos_datos
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error durante la edición"
        )

# -- Guardar -----------------

def guardar_rdf(id_uri, tipo_clase, id_numero, datos_restantes, relaciones_dict=None):
    uri_recurso = URIRef(f"http://www.semanticweb.org/cafe/{id_uri}")
    if (uri_recurso, None, None) in g:
        raise HTTPException(status_code=400, detail=f"El individuo ya existe.")

    g.add((uri_recurso, RDF.type, CAFE[tipo_clase]))
    g.add((uri_recurso, CAFE.id, Literal(id_numero, datatype=XSD.int)))
    
    for prop, valor in datos_restantes.items():
        if valor is not None:
            if isinstance(valor, bool): dtype = XSD.boolean
            elif isinstance(valor, int): dtype = XSD.int
            elif isinstance(valor, float): dtype = XSD.double
            else: dtype = XSD.string
            g.add((uri_recurso, CAFE[prop], Literal(valor, datatype=dtype)))

    if relaciones_dict:
        for prop, id_destino in relaciones_dict.items():
            if id_destino:
                uri_destino = URIRef(f"http://www.semanticweb.org/cafe/{id_destino}")
                g.add((uri_recurso, CAFE[prop], uri_destino))
    
    g.serialize(destination="CafeV9_Final.rdf", format="xml")


# Crear un individuo RDF genérico por clase
@app.post("/individuos/{tipo_clase}", tags=["Estructura"])
def crear_individuo_generico(tipo_clase: str, body: dict = Body(...)):
    """
    body esperado:
      - id_uri: str (obligatorio)
      - id_numeric: int (obligatorio)
      - datos: dict (propiedades literales)
      - relaciones: dict (propiedades -> id_destino)
    """
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body inválido")
    id_uri = body.get("id_uri") or body.get("id") or body.get("id_recurso")
    id_numeric = body.get("id_numeric")
    datos = body.get("datos") or {}
    relaciones = body.get("relaciones") or {}
    if not id_uri or id_numeric is None:
        raise HTTPException(status_code=400, detail="id_uri e id_numeric son obligatorios")
    if not isinstance(datos, dict) or not isinstance(relaciones, dict):
        raise HTTPException(status_code=400, detail="datos/relaciones deben ser dict")
    guardar_rdf(str(id_uri), str(tipo_clase), int(id_numeric), datos, relaciones)
    return {"status": "creado", "id": str(id_uri), "clase": str(tipo_clase)}

# -- Post por clase------------------

# Finca
@app.post("/fincas", tags=["Estructura"])
def insert_finca(data: fincaModel, db: Session = Depends(get_db)):

    propietario_sql = db.query(propietario).filter(
        propietario.id_propietario == data.FK_idPropietario
    ).first()
    if not propietario_sql:
        raise HTTPException(
            status_code=404, 
            detail="Propietario no existe"
        )

    datos = {
        "nombre": data.nombre, 
        "direccion": data.direccion, 
        "area": data.area, 
        "altitud": data.altitud,
        "fk_idPropietario": propietario_sql.id_propietario  
    }
    guardar_rdf(data.id_finca, "finca", data.id_numeric, datos)
    uri_finca = URIRef(f"http://www.semanticweb.org/cafe/{data.id_finca}")
    for l_id in data.lotes:
        g.add((uri_finca, CAFE.contieneLote, URIRef(f"http://www.semanticweb.org/cafe/{l_id}")))
    for c_id in data.compras:
        g.add((uri_finca, CAFE.realizaCompra, URIRef(f"http://www.semanticweb.org/cafe/{c_id}")))
    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Finca registrada"}

#Lote
@app.post("/lotes", tags=["Estructura"])
def insert_lote(data: loteModel):
    datos= {
        "nombre": data.nombre, 
        "area": data.area, 
        "cantidad": data.cantidad, 
        "estado": data.estado
    } 
    guardar_rdf(data.id_lote, "lote", data.id_numeric, datos)
    uri_lote = URIRef(f"http://www.semanticweb.org/cafe/{data.id_lote}")
    for e_id in data.eventosRecoleccion:
        g.add((uri_lote, CAFE.estableceRecoleccion, URIRef(f"http://www.semanticweb.org/cafe/{e_id}")))
    for s_id in data.suministros:
        g.add((uri_lote, CAFE.seAbastecePor, URIRef(f"http://www.semanticweb.org/cafe/{s_id}")))
    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Lote registrado"}

@app.post("/compras", tags=["Estructura"])
def insert_compra(data: compraModel):
    datos = {"fecha": data.fecha, "cantidad": data.cantidad, "precio": data.precio, "estado": data.estado}
    relaciones = {"incluyeInsumo": data.id_insumo, "esCompraDe": data.id_finca}
    guardar_rdf(data.id_compra, "compra", data.id_numeric, datos, relaciones)
    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Compra registrada"}

#Insumos
@app.post("/insumos", tags=["Estructura"])
def insert_insumo(data: insumoModel):
    datos = {
        "nombre": data.nombre, 
        "precio": data.precio, 
        "tipo": data.tipo, 
        "estado": data.estado,
        "unidadMedida": data.unidadMedida,
        "metodoAplicacion": data.metodoAplicacion,
    }
    datos = {k: v for k, v in datos.items() if v not in (None, "")}
    guardar_rdf(data.id_insumo, "insumo", data.id_numeric, datos)
    uri_insumo = URIRef(f"http://www.semanticweb.org/cafe/{data.id_insumo}")
    for c_id in getattr(data, 'compras', []):
        uri_compra = URIRef(f"http://www.semanticweb.org/cafe/{c_id}")
        g.add((uri_insumo, CAFE.esAdquiridoPor, uri_compra))
        
    for s_id in getattr(data, 'suministrosVinculados', []):
        uri_sum = URIRef(f"http://www.semanticweb.org/cafe/{s_id}")
        g.add((uri_insumo, CAFE.permiteLa, uri_sum))

    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Insumo registrado"}

#Inventario
@app.post("/inventarios", tags=["Estructura"])
def insert_inventario(data: inventarioModel):
    datos = {
        "cantidad": data.cantidad,
        "fecha": data.fecha,
        "unidadMedida": data.unidadMedida
    }
    relaciones = {"contieneInsumo": data.id_insumo}
    guardar_rdf(data.id_inventario, "inventario", data.id_numeric, datos, relaciones)
    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Inventario registrado"}

#Suministros
@app.post("/suministros", tags=["Estructura"])
def insert_suministro(data: suministraInsumoModel):
    datos = {"fecha": data.fecha, "cantidad": data.cantidad, "estado": data.estado}
    relaciones = {
        "requiereA": data.id_insumo, 
        "seaplicaEn": data.id_lote  
    }
    guardar_rdf(data.id_suministro, "suministroInsumo", data.id_numeric, datos, relaciones)
    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Suministro registrado"}


#Recoleccion
@app.post("/recolecciones", tags=["Estructura"])
def insert_recoleccion(data: recoleccionModel, db: Session = Depends(get_db)):
    recolector_sql = db.query(recolector).filter(
        recolector.id_recolector == data.FK_idRecolector
    ).first()

    if not recolector_sql:
        raise HTTPException(
            status_code=404, 
            detail="El recolector no existe"
        )
    # Validar rango de contrato del recolector
    try:
        fecha_rec = datetime.fromisoformat(str(data.fecha)[:10]).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha de recolección inválida (use YYYY-MM-DD)")
    inicio = recolector_sql.fechainicio_recolector
    fin = recolector_sql.fechafin_recolector or date.today()
    if fecha_rec < inicio or fecha_rec > fin:
        raise HTTPException(
            status_code=400,
            detail=f"Fecha fuera de rango. Debe estar entre {inicio.isoformat()} y {fin.isoformat()}",
        )
    datos = {
        "fecha": data.fecha,
        "fk_idRecolector": recolector_sql.id_recolector  
    }
    guardar_rdf(data.id_recoleccion, "recoleccion", data.id_numeric, datos)
    return {"status": "Recoleccion registrada"}

#Evento Recoleccion
@app.post("/eventosRecoleccion", tags=["Estructura"])
def insert_evento_recoleccion(data: eventoRecoleccionModel):
    datos = {
        "cantidad": data.cantidad
    }
    relaciones = {
        "ocurreEn": data.id_lote,
        "generaRecoleccion": data.id_recoleccion
    }
    guardar_rdf(data.id_evento, "eventoRecoleccion", data.id_numeric, datos, relaciones)
    return {"status": "Evento de recoleccion registrado"}

### Postgres -----------------------Bd

# Get un registro
@app.get("/consultarRegistro/{nombre_tabla}/{id_registro}", tags=["consultas"])
def get_registro(nombre_tabla: str, id_registro: str, db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get(nombre_tabla.lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="La tabla no existe")
    pk_name = tabla.primary_key.columns.values()[0].name
    query = text(f"SELECT * FROM {tabla.name} WHERE {pk_name} = :id")
    resultado = db.execute(query, {"id": id_registro}).mappings().first()

    if not resultado:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró registro con ID {id_registro} en la tabla {nombre_tabla}"
        )

    return resultado

# Get todos los registros de una tabla

@app.get("/detallesT/{nombre_tabla}", tags=["consultasClase"])
def get_todos(nombre_tabla: str, db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get(nombre_tabla.lower())

    if tabla is None:
        raise HTTPException(
            status_code=404, 
            detail="La tabla no existe"
        )
    query = text(f"SELECT * FROM {tabla.name}")
    resultados = db.execute(query).mappings().all()
    return resultados


# Crear un registro en cualquier tabla Postgres registrada en SQLAlchemy
@app.post("/registros/{nombre_tabla}", tags=["Estructura"])
def crear_registro(nombre_tabla: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get((nombre_tabla or "").lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="Payload inválido")

    cols = {c.name for c in tabla.columns}
    data = {k: v for k, v in payload.items() if k in cols}
    if not data:
        raise HTTPException(status_code=400, detail="No hay campos válidos para insertar")

    pk_col = list(tabla.primary_key.columns)[0]
    keys = ", ".join(data.keys())
    vals = ", ".join([f":{k}" for k in data.keys()])
    q = text(f"INSERT INTO {tabla.name} ({keys}) VALUES ({vals}) RETURNING {pk_col.name}")
    def _reset_serial_sequence_if_any():
        # Corrige secuencia (caso típico: SERIAL desincronizado → duplicate key en PK)
        try:
            db.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence(:tname, :pk),
                        COALESCE((SELECT MAX({pk_col.name}) FROM {tabla.name}), 0) + 1,
                        false
                    )
                    """
                ),
                {"tname": tabla.name, "pk": pk_col.name},
            )
            db.commit()
        except Exception:
            db.rollback()

    try:
        new_id = db.execute(q, data).scalar()
        db.commit()
    except Exception as e:
        # Retry 1 vez si parece PK duplicada por secuencia desincronizada
        msg = str(e)
        db.rollback()
        if (f"{tabla.name}_pkey" in msg) and ("UniqueViolation" in msg or "llave duplicada" in msg or "duplicate key" in msg):
            _reset_serial_sequence_if_any()
            try:
                new_id = db.execute(q, data).scalar()
                db.commit()
            except Exception as e2:
                db.rollback()
                raise HTTPException(status_code=400, detail=f"Error al insertar: {str(e2)}")
        else:
            raise HTTPException(status_code=400, detail=f"Error al insertar: {msg}")
    return {"status": "creado", "id": new_id}


def _cascade_delete_recolector_db(db: Session, rid: str) -> None:
    """Quita pagos y reportes ligados al recolector y luego la fila recolector."""
    db.execute(
        text(
            "DELETE FROM pago WHERE fk_id_reporte IN "
            "(SELECT id_reporte FROM reporte WHERE fk_id_recolector = :rid)"
        ),
        {"rid": rid},
    )
    db.execute(text("DELETE FROM reporte WHERE fk_id_recolector = :rid"), {"rid": rid})
    db.execute(text("DELETE FROM recolector WHERE id_recolector = :rid"), {"rid": rid})


def _recolector_tabla_tiene_columnas_propietario_finca(db: Session) -> bool:
    """True si existe migrate_recolector_fk.sql aplicado (columnas en Postgres)."""
    try:
        n = db.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'recolector'
                  AND column_name IN ('fk_id_propietario', 'fk_id_finca')
                """
            )
        ).scalar()
        return int(n or 0) >= 2
    except Exception:
        return False


def _liberar_recolectores_de_propietario(db: Session, doc_propietario: str) -> None:
    if not _recolector_tabla_tiene_columnas_propietario_finca(db):
        return
    db.execute(
        text(
            "UPDATE recolector SET fk_id_propietario = NULL, fk_id_finca = NULL "
            "WHERE fk_id_propietario = :doc"
        ),
        {"doc": doc_propietario},
    )


# Eliminar un registro en cascada
@app.delete("/registros/{nombre_tabla}/{id_registro}", tags=["Eliminar"])
def eliminar_registro(nombre_tabla: str, id_registro: str, db: Session = Depends(get_db)):
    tabla = Base.metadata.tables.get((nombre_tabla or "").lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    pk_column = list(tabla.primary_key.columns)[0].name

    if tabla.name == "persona":
        db.execute(text("DELETE FROM usuario WHERE fk_persona = :doc"), {"doc": id_registro})
        _liberar_recolectores_de_propietario(db, id_registro)
        db.execute(text("DELETE FROM propietario WHERE id_propietario = :doc"), {"doc": id_registro})
        _cascade_delete_recolector_db(db, id_registro)
    elif tabla.name == "propietario":
        _liberar_recolectores_de_propietario(db, id_registro)
    elif tabla.name == "recolector":
        _cascade_delete_recolector_db(db, id_registro)
        db.commit()
        uri_recurso = URIRef(f"http://www.semanticweb.org/cafe/{id_registro}")
        g.remove((uri_recurso, None, None))
        g.remove((None, None, uri_recurso))
        g.serialize(destination="CafeV9_Final.rdf", format="xml")
        return {"status": "Eliminacion realizada"}

    query = text(f"DELETE FROM {tabla.name} WHERE {pk_column} = :id")
    result = db.execute(query, {"id": id_registro})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="El registro no existe en Postgres")

    uri_recurso = URIRef(f"http://www.semanticweb.org/cafe/{id_registro}")
    g.remove((uri_recurso, None, None))
    g.remove((None, None, uri_recurso))
    g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {"status": "Eliminacion realizada"}

# Editar un registro
@app.patch("/corregirRegistro/{nombre_tabla}/{id_registro}", tags=["Editar"])
def editar_registro(
    nombre_tabla: str, 
    id_registro: str, 
    actualizaciones: dict = Body(...), 
    db: Session = Depends(get_db)
):
    tabla = Base.metadata.tables.get(nombre_tabla.lower())
    if tabla is None:
        raise HTTPException(status_code=404, detail="Tabla no encontrada")
    pk_column = tabla.primary_key.columns.values()[0].name

    # Recolector: recalcular días trabajados cuando cambian fechas (campo no editable)
    if tabla.name.lower() == "recolector" and isinstance(actualizaciones, dict):
        if "diastrabajados_recolector" in actualizaciones:
            actualizaciones.pop("diastrabajados_recolector", None)
        if "fechainicio_recolector" in actualizaciones or "fechafin_recolector" in actualizaciones:
            def _to_date(value):
                if value in (None, ""):
                    return None
                if isinstance(value, date):
                    return value
                return datetime.fromisoformat(str(value).strip()[:10]).date()

            row = db.execute(
                text(f"SELECT fechainicio_recolector, fechafin_recolector FROM {tabla.name} WHERE {pk_column} = :id"),
                {"id": id_registro},
            ).mappings().first()
            if not row:
                raise HTTPException(status_code=404, detail="No existe el registro")
            try:
                fi = _to_date(actualizaciones.get("fechainicio_recolector")) or _to_date(row.get("fechainicio_recolector"))
                ff = _to_date(actualizaciones.get("fechafin_recolector")) or _to_date(row.get("fechafin_recolector")) or date.today()
                dias = (ff - fi).days
            except Exception:
                raise HTTPException(status_code=400, detail="Fechas inválidas")
            if dias < 0:
                raise HTTPException(status_code=400, detail="fechafin_recolector no puede ser menor a fechainicio_recolector")
            actualizaciones["diastrabajados_recolector"] = dias

    campos_set = ", ".join([f"{campo} = :{campo}" for campo in actualizaciones.keys()])
    
    if not campos_set:
        raise HTTPException(status_code=400, detail="No hay campos")

    query = text(f"UPDATE {tabla.name} SET {campos_set} WHERE {pk_column} = :id_pk")
    parametros = {**actualizaciones, "id_pk": id_registro}

    result = db.execute(query, parametros)
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="No existe el registro")
    
    #Apache jena
    uri_recurso = URIRef(f"http://www.semanticweb.org/cafe/{id_registro}")
    
    for campo, nuevo_valor in actualizaciones.items():
        predicado = CAFE[campo] 
        g.remove((uri_recurso, predicado, None))
        g.add((uri_recurso, predicado, Literal(nuevo_valor)))
        g.serialize(destination="CafeV9_Final.rdf", format="xml")
    return {
        "status": "Actualización realizada",
        "campos_modificados": list(actualizaciones.keys())
    }

# --- Auth ---
@app.post("/login", tags=["Auth"])
def login(data: loginModel, db: Session = Depends(get_db)):
    user = db.query(usuario).filter(usuario.username == data.username).first()
    if not user or user.password != data.password:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {
        "status": "success",
        "username": user.username,
        "rol": user.rol,
        "fk_persona": user.fk_persona
    }

@app.post("/usuarios", tags=["Auth"])
def register_user(data: usuarioModel, db: Session = Depends(get_db)):
    if db.query(usuario).filter(usuario.username == data.username).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")

    rol = (data.rol or "").strip().lower()
    if rol not in ("admin", "propietario", "recolector"):
        raise HTTPException(status_code=400, detail="Rol inválido. Use: admin, propietario, recolector")
    
    nuevo_usuario = usuario(
        username=data.username,
        password=data.password,
        rol=rol,
        fk_persona=data.fk_persona
    )
    db.add(nuevo_usuario)
    db.commit()
    return {"mensaje": "Usuario registrado"}

# ---- Post-----------

#Persona
@app.post("/personas", tags=["Estructura"])
def insert_persona(data: personaModel, db: Session = Depends(get_db)):
    nueva_persona = persona(
        documento_persona=data.documento_persona,
        nombre_persona=data.nombre_persona,
        edad_persona=data.edad_persona,
        telefono_persona=data.telefono_persona,
        fk_tipo_documento=data.fk_tipo_documento
    )
    db.add(nueva_persona)
    db.commit()
    db.refresh(nueva_persona)
    return {"mensaje": "Persona registrada"}

#Tipo doc
@app.post("/tipoDocumento", tags=["Estructura"])
def insert_tipo_documento(data: tipoDocModel, db: Session = Depends(get_db)):
        nuevo_tipo = tipoDoc(
            id_doc=data.id_doc,
           tipo=data.tipo,
        )
        db.add(nuevo_tipo)
        db.commit()
        db.refresh(nuevo_tipo)
        return {
            "mensaje": "Tipo de documento registrado"
        }

#Propietario
@app.post("/propietarios", tags=["Estructura"])
def insert_propietario(data: propietarioModel, db: Session = Depends(get_db)):
    nuevo_propietario = propietario(
        id_propietario=data.id_propietario,
        email_propietario=data.email_propietario,
        estado_propietario=data.estado_propietario
    )
    db.add(nuevo_propietario)
    db.commit()
    return {"mensaje": "Propietario registrado"}

#Recolector
@app.post("/recolectores", tags=["Estructura"])
def insert_recolector(data: recolectorModel, db: Session = Depends(get_db)):
    # Los días trabajados se calculan a partir de las fechas (no editable por UI)
    fin = data.fechafin_recolector or date.today()
    dias = (fin - data.fechainicio_recolector).days
    if dias < 0:
        raise HTTPException(status_code=400, detail="fechafin_recolector no puede ser menor a fechainicio_recolector")

    fk_prop = (data.fk_id_propietario or "").strip() or None
    fk_fin = (data.fk_id_finca or "").strip() or None

    if fk_fin:
        prop_de_finca = _rdf_propietario_de_finca(fk_fin)
        if prop_de_finca is None:
            raise HTTPException(status_code=404, detail="La finca no existe en RDF")
        if fk_prop and prop_de_finca != fk_prop:
            raise HTTPException(status_code=400, detail="La finca no pertenece al propietario indicado")
        if not fk_prop:
            fk_prop = prop_de_finca

    tiene_columnas_fk = _recolector_tabla_tiene_columnas_propietario_finca(db)
    aviso = None
    if not tiene_columnas_fk and (fk_fin or fk_prop):
        aviso = (
            "La tabla recolector en Postgres no tiene aún las columnas fk_id_propietario/fk_id_finca. "
            "Ejecute cafeAPI/migrate_recolector_fk.sql en bdcafe. El recolector se guardó sin esos vínculos."
        )
        fk_prop = None
        fk_fin = None

    if tiene_columnas_fk:
        nuevo_recolector = recolector(
            id_recolector=data.id_recolector,
            fechainicio_recolector=data.fechainicio_recolector,
            fechafin_recolector=data.fechafin_recolector,
            estado_recolector=data.estado_recolector,
            diastrabajados_recolector=dias,
            fk_id_propietario=fk_prop,
            fk_id_finca=fk_fin,
        )
        db.add(nuevo_recolector)
    else:
        db.execute(
            text(
                """
                INSERT INTO recolector (
                    id_recolector, fechainicio_recolector, fechafin_recolector,
                    estado_recolector, diastrabajados_recolector
                ) VALUES (
                    :id, :fi, :ff, :est, :dias
                )
                """
            ),
            {
                "id": data.id_recolector,
                "fi": data.fechainicio_recolector,
                "ff": data.fechafin_recolector,
                "est": data.estado_recolector,
                "dias": dias,
            },
        )
    db.commit()
    out: dict = {"mensaje": "Recolector registrado"}
    if aviso:
        out["aviso"] = aviso
    return out

#Reporte
@app.post("/reportes", tags=["Estructura"])
def insert_reporte(data: reporteModel, db: Session = Depends(get_db)):
        nuevo_reporte = reporte(
            id_reporte=data.id_reporte,
            fecha_reporte=data.fecha_reporte,
            totaltecoleccion_reporte=data.totaltecoleccion_reporte,
            estado_reporte=data.estado_reporte,
            fk_id_recolector=data.fk_id_recolector
        )
        db.add(nuevo_reporte)
        db.commit()
        db.refresh(nuevo_reporte)
        return {
            "mensaje": "Reporte registrado"
        }

#Pago
@app.post("/pagos", tags=["Estructura"])
def insert_pago(data: pagoModel, db: Session = Depends(get_db)):
        nuevo_pago = pago(
            id_pago=data.id_pago,
            fecha_pago=data.fecha_pago,
            preciokilo_pago=data.preciokilo_pago,
            estado_pago=data.estado_pago,
            monto_pago=data.monto_pago,
            metodo_pago=data.metodo_pago,
            fk_id_reporte=data.fk_id_reporte
        )
        db.add(nuevo_pago)
        db.commit()
        db.refresh(nuevo_pago)
        return {
            "mensaje": "Pago registrado"
        }


@app.get("/finanzas/kg_sugerido", tags=["Finanzas"])
def finanzas_kg_sugerido(
    id_recolector: str,
    fecha: str,
    propietario_doc: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Kg del día según RDF (solo lectura), sin crear reporte."""
    rid = (id_recolector or "").strip()
    fs = (fecha or "").strip()[:10]
    if not rid or not fs:
        raise HTTPException(status_code=400, detail="id_recolector y fecha son obligatorios")
    rec_sql = db.query(recolector).filter(recolector.id_recolector == rid).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    if propietario_doc:
        pd = str(propietario_doc).strip()
        if (rec_sql.fk_id_propietario or "") != pd:
            raise HTTPException(status_code=403, detail="El recolector no pertenece a este propietario")
    try:
        fd = datetime.fromisoformat(fs).date()
    except Exception:
        raise HTTPException(status_code=400, detail="fecha inválida (YYYY-MM-DD)")
    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fd < inicio or fd > fin:
        raise HTTPException(
            status_code=400,
            detail=f"Fecha fuera del contrato ({inicio.isoformat()} — {fin.isoformat()})",
        )
    kg = float(_kg_recolector_en_fecha(rid, fs))
    return {"id_recolector": rid, "fecha": fs, "kg_sugerido": kg}


@app.post("/finanzas/generar_pago", tags=["Finanzas"])
def finanzas_generar_pago(data: GenerarPagoDiasReq, db: Session = Depends(get_db)):
    """
    Registra reporte + pago por cada día trabajado (kg × precio/kg).
    Días marcados ausente eliminan reporte/pago de ese día si existían.
    """
    rid = (data.id_recolector or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="id_recolector es obligatorio")
    rec_sql = db.query(recolector).filter(recolector.id_recolector == rid).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    if data.propietario_doc:
        pd = str(data.propietario_doc).strip()
        if (rec_sql.fk_id_propietario or "") != pd:
            raise HTTPException(status_code=403, detail="El recolector no pertenece a este propietario")

    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fin < inicio:
        raise HTTPException(status_code=400, detail="Rango de contrato inválido")

    if not data.dias:
        raise HTTPException(status_code=400, detail="Debe enviar al menos un día para liquidar")

    fechas_vistas = set()
    dias_normalizados = []
    dias_omitidos = []
    detalle = []
    total_kg = 0.0
    total_monto = 0.0
    pagos_n = 0

    for d in data.dias:
        fs = (d.fecha or "").strip()[:10]
        if fs in fechas_vistas:
            raise HTTPException(status_code=400, detail=f"Fecha duplicada: {fs}")
        fechas_vistas.add(fs)
        try:
            fd = datetime.fromisoformat(fs).date()
        except Exception:
            raise HTTPException(status_code=400, detail=f"fecha inválida: {d.fecha}")
        if fd < inicio or fd > fin:
            raise HTTPException(status_code=400, detail=f"La fecha {fs} está fuera del contrato")

        reporte_id = f"RD_{rid}_{fs}"
        id_pago = f"PAGO_MAN_{rid}_{fs}"
        pago_existente = db.query(pago).filter(pago.fk_id_reporte == reporte_id).first()
        if not pago_existente:
            pago_existente = db.query(pago).filter(pago.id_pago == id_pago).first()
        if pago_existente:
            dias_omitidos.append({"fecha": fs, "motivo": "Ya se reportó pago para este día"})
            continue

        if d.ausente:
            dias_normalizados.append(
                {
                    "fecha": fs,
                    "fecha_date": fd,
                    "reporte_id": reporte_id,
                    "id_pago": id_pago,
                    "ausente": True,
                    "kg": 0.0,
                    "precio_kilo": 0.0,
                }
            )
            continue

        metodo_pago = (d.metodo_pago or "Efectivo").strip()
        if metodo_pago not in ("Efectivo", "Transferencia", "Tarjeta"):
            raise HTTPException(status_code=400, detail=f"Método de pago inválido para el día {fs}")
        kg = float(d.kg_dia or 0)
        pk = float(d.precio_kilo or 0)
        if pk < 0:
            raise HTTPException(status_code=400, detail=f"precio_kilo no puede ser negativo ({fs})")
        if kg < 0:
            raise HTTPException(status_code=400, detail=f"kg_dia no puede ser negativo ({fs})")
        dias_normalizados.append(
            {
                "fecha": fs,
                "fecha_date": fd,
                "reporte_id": reporte_id,
                "id_pago": id_pago,
                "ausente": False,
                "kg": kg,
                "precio_kilo": pk,
                "metodo_pago": metodo_pago,
            }
        )

    if not dias_normalizados:
        raise HTTPException(status_code=400, detail="Todos los días enviados ya fueron reportados")

    for d in dias_normalizados:
        fs = d["fecha"]
        fd = d["fecha_date"]
        reporte_id = d["reporte_id"]

        if d["ausente"]:
            db.query(pago).filter(pago.fk_id_reporte == reporte_id).delete(synchronize_session=False)
            db.query(reporte).filter(reporte.id_reporte == reporte_id).delete(synchronize_session=False)
            detalle.append({"fecha": fs, "ausente": True, "kg_dia": 0.0, "precio_kilo": 0.0, "monto_dia": 0.0})
            continue

        kg = d["kg"]
        pk = d["precio_kilo"]
        monto = kg * pk
        total_kg += kg
        total_monto += monto

        rep = db.query(reporte).filter(reporte.id_reporte == reporte_id).first()
        if rep:
            rep.fecha_reporte = fd
            rep.totaltecoleccion_reporte = float(kg)
            rep.estado_reporte = True
            rep.fk_id_recolector = rid
        else:
            db.add(
                reporte(
                    id_reporte=reporte_id,
                    fecha_reporte=fd,
                    totaltecoleccion_reporte=float(kg),
                    estado_reporte=True,
                    fk_id_recolector=rid,
                )
            )

        db.flush()
        db.add(
            pago(
                id_pago=d["id_pago"],
                fecha_pago=fd,
                preciokilo_pago=float(pk),
                estado_pago=True,
                monto_pago=float(monto),
                metodo_pago=d["metodo_pago"],
                fk_id_reporte=reporte_id,
            )
        )
        pagos_n += 1
        detalle.append({"fecha": fs, "ausente": False, "kg_dia": kg, "precio_kilo": pk, "monto_dia": monto, "metodo_pago": d["metodo_pago"]})

    db.commit()
    mensaje = "Liquidación registrada"
    if dias_omitidos:
        mensaje = f"Liquidación registrada. Se omitieron {len(dias_omitidos)} día(s) ya reportado(s)."
    return {
        "mensaje": mensaje,
        "id_recolector": rid,
        "total_kg": total_kg,
        "total_monto": total_monto,
        "pagos_registrados": pagos_n,
        "dias_omitidos": dias_omitidos,
        "detalle": detalle,
    }


@app.post("/reportes/diario", tags=["Reporte"])
def generar_reporte_diario(data: reporteDiarioReq, db: Session = Depends(get_db)):
    recolector_id = (data.id_recolector or "").strip()
    fecha_str = (data.fecha or "").strip()[:10]
    if not recolector_id or not fecha_str:
        raise HTTPException(status_code=400, detail="id_recolector y fecha son obligatorios")
    try:
        fecha = datetime.fromisoformat(fecha_str).date()
    except Exception:
        raise HTTPException(status_code=400, detail="fecha inválida (use YYYY-MM-DD)")

    rec_sql = db.query(recolector).filter(recolector.id_recolector == recolector_id).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fecha < inicio or fecha > fin:
        raise HTTPException(status_code=400, detail=f"Fecha fuera de rango ({inicio.isoformat()} - {fin.isoformat()})")

    # Calcular total recolectado desde RDF
    total_cantidad = 0
    rec_uris = []
    for rec_uri, _, rid in g.triples((None, CAFE.fk_idRecolector, None)):
        if str(rid).strip() != recolector_id:
            continue
        for _, __, f in g.triples((rec_uri, CAFE.fecha, None)):
            if str(f).strip()[:10] == fecha_str:
                rec_uris.append(rec_uri)
                break

    for rec_uri in rec_uris:
        for ev_uri, _, _ in g.triples((None, CAFE.generaRecoleccion, rec_uri)):
            for _, __, q in g.triples((ev_uri, CAFE.cantidad, None)):
                try:
                    total_cantidad += int(float(str(q)))
                except Exception:
                    pass

    reporte_id = f"RD_{recolector_id}_{fecha_str}"
    rep = db.query(reporte).filter(reporte.id_reporte == reporte_id).first()
    if not rep:
        rep = reporte(
            id_reporte=reporte_id,
            fecha_reporte=fecha,
            totaltecoleccion_reporte=float(total_cantidad),
            estado_reporte=True,
            fk_id_recolector=recolector_id,
        )
        db.add(rep)
    else:
        rep.fecha_reporte = fecha
        rep.totaltecoleccion_reporte = float(total_cantidad)
        rep.estado_reporte = True
        rep.fk_id_recolector = recolector_id
    db.commit()

    pagado = 0.0
    try:
        pagos = db.query(pago).filter(pago.fk_id_reporte == reporte_id).all()
        for p in pagos:
            pagado += float(p.monto_pago or 0)
    except Exception:
        pagado = 0.0

    return {
        "id_reporte": reporte_id,
        "fecha_reporte": fecha_str,
        "fk_id_recolector": recolector_id,
        "total_recolectado": total_cantidad,
        "total_pagado": pagado,
    }


@app.post("/liquidacion/recolector", tags=["Reporte"])
def liquidacion_recolector(data: liquidacionRecolectorReq, db: Session = Depends(get_db)):
    rid = (data.id_recolector or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="id_recolector es obligatorio")
    rec_sql = db.query(recolector).filter(recolector.id_recolector == rid).first()
    if not rec_sql:
        raise HTTPException(status_code=404, detail="El recolector no existe")
    if data.propietario_doc:
        pd = str(data.propietario_doc).strip()
        if (rec_sql.fk_id_propietario or "") != pd:
            raise HTTPException(status_code=403, detail="El recolector no pertenece a este propietario")

    inicio = rec_sql.fechainicio_recolector
    fin = rec_sql.fechafin_recolector or date.today()
    if fin < inicio:
        raise HTTPException(status_code=400, detail="Rango de contrato inválido")

    pk = float(data.precio_kilo or 0)
    dias_out = []
    total_kg = 0.0
    total_monto = 0.0
    d = inicio
    while d <= fin:
        fs = d.isoformat()
        kg = _kg_recolector_en_fecha(rid, fs)
        monto = kg * pk
        dias_out.append({"fecha": fs, "kg_dia": kg, "monto_dia": monto})
        total_kg += kg
        total_monto += monto
        d += timedelta(days=1)

    return {
        "id_recolector": rid,
        "precio_kilo": pk,
        "dias": dias_out,
        "total_kg": total_kg,
        "total_monto": total_monto,
    }


# --- Catálogos Postgres (tipo insumo, unidad medida, método aplicación) ---
@app.post("/catalogo/tipoInsumo", tags=["Catalogo"])
def catalogo_tipo_insumo_post(data: catTipoInsumoModel, db: Session = Depends(get_db)):
    if not (data.id_tipoinsumo or "").strip() or not (data.nombre_tipo or "").strip():
        raise HTTPException(status_code=400, detail="id_tipoinsumo y nombre_tipo son obligatorios")
    if db.query(cat_tipo_insumo).filter(cat_tipo_insumo.id_tipoinsumo == data.id_tipoinsumo).first():
        raise HTTPException(status_code=400, detail="Ya existe un tipo de insumo con ese id")
    row = cat_tipo_insumo(id_tipoinsumo=data.id_tipoinsumo, nombre_tipo=data.nombre_tipo)
    db.add(row)
    db.commit()
    return {
        "mensaje": "Tipo de insumo registrado",
        "data": {"id_tipoinsumo": data.id_tipoinsumo, "nombre_tipo": data.nombre_tipo},
    }


@app.post("/catalogo/unidadMedida", tags=["Catalogo"])
def catalogo_unidad_medida_post(data: catUnidadMedidaCreateModel, db: Session = Depends(get_db)):
    nombre = (data.nombre_unidadmedida or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="nombre_unidadmedida es obligatorio")
    row = cat_unidad_medida(nombre_unidadmedida=nombre)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "mensaje": "Unidad registrada",
        "data": {
            "id_unidadmedida": row.id_unidadmedida,
            "nombre_unidadmedida": row.nombre_unidadmedida,
        },
    }


@app.post("/catalogo/metodoAplicacion", tags=["Catalogo"])
def catalogo_metodo_aplicacion_post(data: catMetodoAplicacionCreateModel, db: Session = Depends(get_db)):
    nombre = (data.nombre_metodoaplicacion or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="nombre_metodoaplicacion es obligatorio")
    usados = {
        row[0]
        for row in db.query(cat_metodo_aplicacion.id_metodoaplicacion)
        .order_by(cat_metodo_aplicacion.id_metodoaplicacion)
        .all()
    }
    siguiente_id = 1
    while siguiente_id in usados:
        siguiente_id += 1
    row = cat_metodo_aplicacion(
        id_metodoaplicacion=siguiente_id,
        nombre_metodoaplicacion=nombre,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "mensaje": "Método registrado",
        "data": {
            "id_metodoaplicacion": row.id_metodoaplicacion,
            "nombre_metodoaplicacion": row.nombre_metodoaplicacion,
        },
    }


# --- Chatbot Inteligente Semántico con Gemini ---
try:
    from gemini_handler import get_gemini_handler
except ImportError:
    get_gemini_handler = None

class ChatbotConsultaReq(BaseModel):
    pregunta: str

@app.get("/diagnostico/gemini", tags=["Diagnostico"])
def diagnostico_gemini():
    """Verifica la configuración y estado de Gemini API."""
    diagnostico = {
        "estado": "✅ OK",
        "checks": []
    }
    
    # 1. Verificar API Key
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        diagnostico["estado"] = "❌ ERROR"
        diagnostico["checks"].append({
            "check": "GEMINI_API_KEY",
            "estado": "❌ No configurada",
            "detalles": "Agrega GEMINI_API_KEY=tu_clave en .env"
        })
    else:
        diagnostico["checks"].append({
            "check": "GEMINI_API_KEY",
            "estado": "✅ Configurada",
            "detalles": f"Clave: {api_key[:10]}...{api_key[-4:]}"
        })
    
    # 2. Verificar handler
    if get_gemini_handler:
        try:
            gemini = get_gemini_handler()
            stats = gemini.get_stats()
            diagnostico["checks"].append({
                "check": "GeminiHandler",
                "estado": "✅ Inicializado",
                "detalles": f"Requests hoy: {stats['requests_today']}/{stats['daily_limit']}"
            })
        except Exception as e:
            diagnostico["estado"] = "⚠️ WARNING"
            diagnostico["checks"].append({
                "check": "GeminiHandler",
                "estado": "⚠️ Error al inicializar",
                "detalles": str(e)
            })
    else:
        diagnostico["checks"].append({
            "check": "gemini_handler.py",
            "estado": "❌ No importado",
            "detalles": "El archivo gemini_handler.py no se encontró"
        })
    
    # 3. Recomendaciones
    diagnostico["recomendaciones"] = []
    if diagnostico["estado"] == "❌ ERROR":
        diagnostico["recomendaciones"].append(
            "1. Verifica que cafeAPI/.env existe y tiene GEMINI_API_KEY"
        )
        diagnostico["recomendaciones"].append(
            "2. Obtén tu clave en: https://aistudio.google.com/apikey"
        )
        diagnostico["recomendaciones"].append(
            "3. Reinicia el servidor después de actualizar .env"
        )
    
    return diagnostico

@app.get("/chatbot/estado", tags=["Chatbot"])
def estado_chatbot():
    """Retorna el estado actual del rate limiting y caché de Gemini."""
    try:
        gemini = get_gemini_handler()
        stats = gemini.get_stats()
        return {
            "status": "ok",
            "modelo": stats.get("model", "gemini-2.5-flash"),
            "solicitudes_hoy": stats.get("requests_today", 0),
            "limite_diario": stats.get("daily_limit", 300),
            "porcentaje_usado": f"{(stats.get('requests_today', 0) / stats.get('daily_limit', 1) * 100):.1f}%",
            "solicitudes_ultimo_minuto": stats.get("requests_last_minute", 0),
            "cache_items": stats.get("cache_size", 0),
            "cache_ttl_segundos": stats.get("cache_ttl_seconds", 7200),
            "recomendacion": "Si el porcentaje es >80%, espera hasta mañana o obtén un API key con cuota mayor"
        }
    except Exception as e:
        return {
            "status": "error",
            "detalle": str(e)
        }

@app.post("/chatbot/consultar", tags=["Chatbot"])
def chatbot_consultar(data: ChatbotConsultaReq, db: Session = Depends(get_db)):
    """Chatbot inteligente con caché y rate limiting."""
    pregunta = data.pregunta.strip()
    if not pregunta:
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")

    if not get_gemini_handler:
        raise HTTPException(
            status_code=500,
            detail="gemini_handler.py no disponible. Verifica la instalación."
        )

    # Obtener handler (singleton con caché y rate limiting)
    try:
        gemini = get_gemini_handler()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    # ── Prompt 1: Plan de consulta ──
    prompt_plan = f"""Eres el asistente del sistema SIGIC (Gestión de Información Cafetera).
Responde la pregunta usando los esquemas disponibles.

POSTGRES: persona(documento_persona,nombre_persona,edad_persona,telefono_persona,fk_tipo_documento), propietario(id_propietario,email_propietario,estado_propietario), recolector(id_recolector,fechainicio_recolector,fechafin_recolector,estado_recolector,diastrabajados_recolector,fk_id_propietario,fk_id_finca), reporte(id_reporte,fecha_reporte,totaltecoleccion_reporte,estado_reporte,fk_id_recolector), pago(id_pago,fecha_pago,preciokilo_pago,estado_pago,monto_pago,metodo_pago,fk_id_reporte)

RDF PREFIX cafe: <http://www.semanticweb.org/cafe/> — Clases: cafe:finca(nombre,direccion,area,altitud,fk_idPropietario), cafe:lote(nombre,area,cantidad,estado), cafe:insumo(nombre,precio,tipo,estado,unidadMedida,metodoAplicacion), cafe:recoleccion(fecha,fk_idRecolector), cafe:eventoRecoleccion(cantidad)

PREGUNTA: "{pregunta}"

Devuelve SOLO JSON puro sin markdown:
{{"database":"postgres"|"rdf"|"both"|"none","sql":"<SQL o null>","sparql":"<SPARQL con prefijos o null>","respuesta_directa":"<respuesta si no necesitas datos, sino null>"}}"""

    try:
        plan_str = gemini.llamar_gemini(prompt_plan, json_mode=True, reintentos=5)
        plan = json.loads(plan_str)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando plan: {str(e)}")

    db_choice = plan.get("database", "none")
    sql_query = plan.get("sql")
    sparql_query = plan.get("sparql")
    respuesta_directa = plan.get("respuesta_directa")

    # Si puede responder sin datos
    if respuesta_directa and not sql_query and not sparql_query:
        return {
            "pregunta": pregunta,
            "respuesta": respuesta_directa,
            "detalles_tecnicos": {
                "database": db_choice,
                "sql": None,
                "resultados_sql": None,
                "sparql": None,
                "resultados_rdf": None,
                "errores": None
            }
        }

    # ── Ejecutar consultas ──
    resultados_sql = None
    resultados_sparql = None
    errores = []

    if db_choice in ("postgres", "both") and sql_query:
        try:
            res = db.execute(text(sql_query))
            resultados_sql = [dict(row) for row in res.mappings()]
        except Exception as e:
            errores.append(f"Error SQL: {str(e)}")

    if db_choice in ("rdf", "both") and sparql_query:
        try:
            res_sparql = g.query(sparql_query)
            vars_list = [str(v) for v in res_sparql.vars]
            records = []
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

    # ── Prompt 2: Respuesta final ──
    ctx = {"resultados_postgres": resultados_sql, "resultados_rdf": resultados_sparql, "errores": errores}
    prompt_respuesta = f"""Eres el asistente del sistema SIGIC de gestión de fincas cafeteras.
El usuario preguntó: "{pregunta}"
Datos obtenidos: {json.dumps(ctx, ensure_ascii=False, default=str)}
Redacta una respuesta clara y amigable en español. Usa datos concretos. No muestres SQL ni SPARQL."""

    try:
        respuesta_final = gemini.llamar_gemini(prompt_respuesta, json_mode=False, reintentos=5)
    except HTTPException:
        # Si falla, dar respuesta con datos crudos
        if resultados_sql or resultados_sparql:
            respuesta_final = f"Datos encontrados: {json.dumps(ctx, ensure_ascii=False, default=str)[:400]}"
        else:
            raise

    return {
        "pregunta": pregunta,
        "respuesta": respuesta_final,
        "detalles_tecnicos": {
            "database": db_choice,
            "sql": sql_query,
            "resultados_sql": resultados_sql,
            "sparql": sparql_query,
            "resultados_rdf": resultados_sparql,
            "errores": errores if errores else None
        }
    }
