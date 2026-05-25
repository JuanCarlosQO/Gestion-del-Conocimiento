"""
fuseki_client.py
Reemplaza rdflib con llamadas HTTP a Apache Jena Fuseki.
Endpoints:
  QUERY:  GET/POST http://fuseki:3030/cafe/query   (SPARQL SELECT/ASK/CONSTRUCT)
  UPDATE: POST      http://fuseki:3030/cafe/update  (SPARQL INSERT/DELETE)
  DATA:   POST/PUT  http://fuseki:3030/cafe/data    (carga directa de triples)
"""

import os
import requests
from typing import Optional, Any

FUSEKI_URL     = os.environ.get("FUSEKI_URL", "http://fuseki:3030")
FUSEKI_DATASET = os.environ.get("FUSEKI_DATASET", "cafe")
FUSEKI_USER    = os.environ.get("FUSEKI_USER", "admin")
FUSEKI_PASS    = os.environ.get("FUSEKI_PASS", "admin123")

QUERY_URL  = f"{FUSEKI_URL}/{FUSEKI_DATASET}/query"
UPDATE_URL = f"{FUSEKI_URL}/{FUSEKI_DATASET}/update"
DATA_URL   = f"{FUSEKI_URL}/{FUSEKI_DATASET}/data"

CAFE_NS = "http://www.semanticweb.org/cafe/"

_AUTH = (FUSEKI_USER, FUSEKI_PASS)


# ── Utilidades ────────────────────────────────────────────────────────────────

def _uri(local: str) -> str:
    return f"<{CAFE_NS}{local}>"


def _literal(value: Any) -> str:
    """Convierte un valor Python a literal SPARQL con tipo XSD."""
    if isinstance(value, bool):
        return f'"{str(value).lower()}"^^<http://www.w3.org/2001/XMLSchema#boolean>'
    if isinstance(value, int):
        return f'"{value}"^^<http://www.w3.org/2001/XMLSchema#int>'
    if isinstance(value, float):
        return f'"{value}"^^<http://www.w3.org/2001/XMLSchema#double>'
    return f'"{str(value)}"^^<http://www.w3.org/2001/XMLSchema#string>'


# ── Operaciones base ──────────────────────────────────────────────────────────

def sparql_query(query: str) -> dict:
    """Ejecuta un SPARQL SELECT y devuelve el JSON completo de Fuseki."""
    r = requests.post(
        QUERY_URL,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        auth=_AUTH,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sparql_update(update: str) -> None:
    """Ejecuta un SPARQL INSERT/DELETE sobre Fuseki."""
    r = requests.post(
        UPDATE_URL,
        data={"update": update},
        auth=_AUTH,
        timeout=30,
    )
    r.raise_for_status()


def sparql_ask(query: str) -> bool:
    """Ejecuta un SPARQL ASK y devuelve True/False."""
    r = requests.post(
        QUERY_URL,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        auth=_AUTH,
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("boolean", False)


# ── Equivalentes de rdflib ────────────────────────────────────────────────────

def existe_recurso(id_recurso: str) -> bool:
    """Equivalente a: (uri, None, None) in g"""
    q = f"""
    ASK {{
        {_uri(id_recurso)} ?p ?o .
    }}
    """
    return sparql_ask(q)


def get_triples_sujeto(id_recurso: str) -> list[dict]:
    """
    Equivalente a: g.predicate_objects(uri)
    Devuelve lista de {predicate, object, is_literal}
    """
    q = f"""
    SELECT ?p ?o WHERE {{
        {_uri(id_recurso)} ?p ?o .
    }}
    """
    results = sparql_query(q)
    out = []
    for row in results.get("results", {}).get("bindings", []):
        out.append({
            "predicate": row["p"]["value"],
            "object":    row["o"]["value"],
            "is_literal": row["o"]["type"] == "literal",
        })
    return out


def get_triples_objeto(id_recurso: str) -> list[dict]:
    """
    Equivalente a: g.triples((None, None, uri))
    Devuelve lista de {subject, predicate}
    """
    q = f"""
    SELECT ?s ?p WHERE {{
        ?s ?p {_uri(id_recurso)} .
    }}
    """
    results = sparql_query(q)
    out = []
    for row in results.get("results", {}).get("bindings", []):
        out.append({
            "subject":   row["s"]["value"],
            "predicate": row["p"]["value"],
        })
    return out


def insertar_individuo(
    id_uri: str,
    tipo_clase: str,
    id_numero: int,
    datos: dict,
    relaciones: Optional[dict] = None,
) -> None:
    """
    Equivalente a guardar_rdf() en main.py original.
    Inserta un individuo con sus propiedades literales y relaciones.
    """
    if existe_recurso(id_uri):
        raise ValueError(f"El individuo '{id_uri}' ya existe en Fuseki.")

    triples = []
    triples.append(f"{_uri(id_uri)} a {_uri(tipo_clase)} .")
    triples.append(f"{_uri(id_uri)} <{CAFE_NS}id> {_literal(id_numero)} .")

    for prop, valor in datos.items():
        if valor is not None:
            triples.append(f"{_uri(id_uri)} <{CAFE_NS}{prop}> {_literal(valor)} .")

    if relaciones:
        for prop, id_destino in relaciones.items():
            if id_destino:
                triples.append(f"{_uri(id_uri)} <{CAFE_NS}{prop}> {_uri(id_destino)} .")

    update = f"""
    INSERT DATA {{
        {chr(10).join(triples)}
    }}
    """
    sparql_update(update)


def eliminar_individuo(id_recurso: str) -> None:
    """
    Equivalente a: g.remove((uri, None, None)) + g.remove((None, None, uri))
    Elimina el individuo y todas sus referencias.
    """
    update = f"""
    DELETE WHERE {{
        {_uri(id_recurso)} ?p ?o .
    }};
    DELETE WHERE {{
        ?s ?p {_uri(id_recurso)} .
    }}
    """
    sparql_update(update)


def editar_literal(id_recurso: str, propiedad: str, nuevo_valor: Any) -> None:
    """
    Equivalente a: g.remove((uri, pred, None)) + g.add((uri, pred, Literal(val)))
    """
    update = f"""
    DELETE WHERE {{
        {_uri(id_recurso)} <{CAFE_NS}{propiedad}> ?o .
    }};
    INSERT DATA {{
        {_uri(id_recurso)} <{CAFE_NS}{propiedad}> {_literal(nuevo_valor)} .
    }}
    """
    sparql_update(update)


def editar_individuo_completo(id_recurso: str, nuevos_datos: dict) -> None:
    """
    Equivalente a editar_individuo() en main.py original.
    Reemplaza todas las propiedades literales del individuo.
    """
    # Eliminar todos los literales actuales
    delete_q = f"""
    DELETE WHERE {{
        {_uri(id_recurso)} ?p ?o .
        FILTER(isLiteral(?o))
    }}
    """
    sparql_update(delete_q)

    # Preservar el tipo (rdf:type)
    tipo = get_tipo_individuo(id_recurso)

    # Reinsertar con nuevos valores
    triples = []
    if tipo:
        triples.append(f"{_uri(id_recurso)} a <{tipo}> .")
    for prop, valor in nuevos_datos.items():
        triples.append(f"{_uri(id_recurso)} <{CAFE_NS}{prop}> {_literal(valor)} .")

    if triples:
        insert_q = f"""
        INSERT DATA {{
            {chr(10).join(triples)}
        }}
        """
        sparql_update(insert_q)


def get_tipo_individuo(id_recurso: str) -> Optional[str]:
    """Devuelve la URI del tipo (rdf:type) del individuo."""
    q = f"""
    SELECT ?tipo WHERE {{
        {_uri(id_recurso)} a ?tipo .
    }} LIMIT 1
    """
    results = sparql_query(q)
    bindings = results.get("results", {}).get("bindings", [])
    if bindings:
        return bindings[0]["tipo"]["value"]
    return None


def agregar_relacion(id_sujeto: str, propiedad: str, id_objeto: str) -> None:
    """Agrega una relación entre dos individuos."""
    update = f"""
    INSERT DATA {{
        {_uri(id_sujeto)} <{CAFE_NS}{propiedad}> {_uri(id_objeto)} .
    }}
    """
    sparql_update(update)


def kg_recolector_en_fecha(recolector_id: str, fecha_str: str) -> float:
    """
    Equivalente a _kg_recolector_en_fecha() en main.py original.
    Consulta los kg recolectados por un recolector en una fecha.
    """
    fs = fecha_str.strip()[:10]
    q = f"""
    PREFIX cafe: <{CAFE_NS}>
    SELECT (SUM(?cantidad) AS ?total) WHERE {{
        ?recoleccion cafe:fk_idRecolector "{recolector_id}"^^<http://www.w3.org/2001/XMLSchema#string> .
        ?recoleccion cafe:fecha ?fecha .
        ?evento cafe:generaRecoleccion ?recoleccion .
        ?evento cafe:cantidad ?cantidad .
        FILTER(STRSTARTS(STR(?fecha), "{fs}"))
    }}
    """
    results = sparql_query(q)
    bindings = results.get("results", {}).get("bindings", [])
    if bindings and bindings[0].get("total"):
        val = bindings[0]["total"]["value"]
        try:
            return float(val)
        except Exception:
            return 0.0
    return 0.0


def propietario_de_finca(finca_id: str) -> Optional[str]:
    """
    Equivalente a _rdf_propietario_de_finca() en main.py original.
    """
    q = f"""
    PREFIX cafe: <{CAFE_NS}>
    SELECT ?propietario WHERE {{
        {_uri(finca_id)} cafe:fk_idPropietario ?propietario .
    }} LIMIT 1
    """
    results = sparql_query(q)
    bindings = results.get("results", {}).get("bindings", [])
    if bindings:
        val = bindings[0]["propietario"]["value"]
        return val.split("/")[-1]
    return None


def get_detalle_individuo(id_recurso: str) -> Optional[dict]:
    """
    Equivalente a get_detalle_individual() en main.py original.
    Devuelve {Id, Datos, Relaciones}
    """
    if not existe_recurso(id_recurso):
        return None

    triples = get_triples_sujeto(id_recurso)
    datos = {}
    relaciones = {}

    for t in triples:
        nombre_prop = t["predicate"].split("/")[-1].split("#")[-1]
        if nombre_prop == "type":
            continue
        if t["is_literal"]:
            datos[nombre_prop] = t["object"]
        else:
            relaciones[nombre_prop] = t["object"].split("/")[-1]

    return {"Id": id_recurso, "Datos": datos, "Relaciones": relaciones}


def get_individuos_clase(nombre_clase: str) -> dict:
    """
    Equivalente a get_individuosClase() en main.py original.
    """
    q = f"""
    PREFIX cafe: <{CAFE_NS}>
    SELECT ?ind ?p ?o WHERE {{
        ?ind a {_uri(nombre_clase)} .
        ?ind ?p ?o .
        FILTER(isLiteral(?o))
    }}
    """
    results = sparql_query(q)
    respuesta = {}
    for row in results.get("results", {}).get("bindings", []):
        ind_id = row["ind"]["value"].split("/")[-1]
        prop   = row["p"]["value"].split("/")[-1].split("#")[-1]
        valor  = row["o"]["value"]
        if ind_id not in respuesta:
            respuesta[ind_id] = {}
        respuesta[ind_id][prop] = valor
    return respuesta


def init_fuseki() -> None:
    """
    Inicializa Fuseki:
    1. Espera a que esté listo (ping).
    2. Crea el dataset si no existe.
    3. Si está vacío, importa CafeV9_Final.rdf.
    """
    import time
    from pathlib import Path

    print("=== Inicializando Fuseki ===")
    
    # 1. Esperar a que Fuseki esté listo (ping)
    ping_url = f"{FUSEKI_URL}/$/ping"
    ready = False
    for i in range(30):
        try:
            r = requests.get(ping_url, auth=_AUTH, timeout=2)
            if r.status_code == 200:
                print("Fuseki está listo.")
                ready = True
                break
        except Exception:
            pass
        print(f"Esperando a Fuseki... ({i+1}/30)")
        time.sleep(2)
        
    if not ready:
        print("ADVERTENCIA: Fuseki no respondió a tiempo. Continuando de todos modos...")
        return

    # 2. Crear dataset 'cafe' si no existe
    dataset_url = f"{FUSEKI_URL}/$/datasets/{FUSEKI_DATASET}"
    try:
        r = requests.get(dataset_url, auth=_AUTH, timeout=10)
        if r.status_code == 404:
            print(f"Dataset '{FUSEKI_DATASET}' no existe. Creándolo...")
            create_url = f"{FUSEKI_URL}/$/datasets"
            r_create = requests.post(
                create_url,
                data={"dbName": FUSEKI_DATASET, "dbType": "tdb2"},
                auth=_AUTH,
                timeout=15,
            )
            r_create.raise_for_status()
            print(f"Dataset '{FUSEKI_DATASET}' creado exitosamente.")
        else:
            print(f"Dataset '{FUSEKI_DATASET}' ya existe (HTTP {r.status_code}).")
    except Exception as e:
        print(f"Error al verificar/crear el dataset: {e}")

    # 3. Verificar si el dataset está vacío
    try:
        count_q = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
        res = sparql_query(count_q)
        bindings = res.get("results", {}).get("bindings", [])
        count = 0
        if bindings:
            count = int(bindings[0]["n"]["value"])
        print(f"Triples actuales en '{FUSEKI_DATASET}': {count}")
        
        if count == 0:
            # Buscar el archivo rdf. Probaremos rutas típicas
            paths_to_try = [
                Path(__file__).parent / "CafeV9_Final.rdf",
                Path("CafeV9_Final.rdf"),
                Path("/app/CafeV9_Final.rdf"),
            ]
            rdf_file = None
            for p in paths_to_try:
                if p.exists():
                    rdf_file = p
                    break
            
            if rdf_file:
                print(f"Importando RDF desde {rdf_file}...")
                with open(rdf_file, "rb") as f:
                    rdf_data = f.read()
                
                r_import = requests.post(
                    DATA_URL,
                    data=rdf_data,
                    headers={"Content-Type": "application/rdf+xml"},
                    auth=_AUTH,
                    timeout=60,
                )
                r_import.raise_for_status()
                print("RDF importado correctamente en Fuseki.")
            else:
                print("ERROR: No se encontró CafeV9_Final.rdf en ninguna ruta conocida.")
        else:
            print("El dataset ya contiene datos. No se realiza importación.")
            
    except Exception as e:
        print(f"Error al verificar/importar datos en Fuseki: {e}")
        
    print("=== Inicialización de Fuseki completa ===")
