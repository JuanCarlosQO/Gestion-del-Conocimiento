#!/bin/bash
# fuseki_init.sh — Crea el dataset 'cafe' e importa el RDF si está vacío

DATASET="cafe"
RDF_FILE="/staging/CafeV9_Final.rdf"
FUSEKI_URL="http://localhost:3030"
ADMIN_PASS="${ADMIN_PASSWORD:-admin}"

echo "=== Fuseki Init Script ==="

# Esperar a que Fuseki esté listo (máx 60s)
echo "Esperando a que Fuseki arranque..."
for i in $(seq 1 30); do
    if curl -sf "${FUSEKI_URL}/\$/ping" > /dev/null 2>&1; then
        echo "Fuseki listo."
        break
    fi
    sleep 2
done

# Crear dataset 'cafe' si no existe
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -u "admin:${ADMIN_PASS}" \
    "${FUSEKI_URL}/\$/datasets/${DATASET}")

if [ "$STATUS" = "404" ]; then
    echo "Creando dataset '${DATASET}'..."
    curl -sf -X POST \
        -u "admin:${ADMIN_PASS}" \
        -d "dbName=${DATASET}&dbType=tdb2" \
        "${FUSEKI_URL}/\$/datasets"
    echo "Dataset '${DATASET}' creado."
else
    echo "Dataset '${DATASET}' ya existe (HTTP ${STATUS})."
fi

# Verificar si el dataset está vacío
COUNT=$(curl -sf \
    -u "admin:${ADMIN_PASS}" \
    --data-urlencode "query=SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }" \
    -H "Accept: application/sparql-results+json" \
    "${FUSEKI_URL}/${DATASET}/query" \
    | grep -o '"value":"[0-9]*"' | grep -o '[0-9]*' | head -1)

echo "Triples actuales: ${COUNT:-0}"

if [ "${COUNT:-0}" = "0" ] && [ -f "$RDF_FILE" ]; then
    echo "Importando ${RDF_FILE} en Fuseki..."
    curl -sf -X POST \
        -u "admin:${ADMIN_PASS}" \
        -H "Content-Type: application/rdf+xml" \
        --data-binary "@${RDF_FILE}" \
        "${FUSEKI_URL}/${DATASET}/data"
    echo "RDF importado correctamente."
else
    echo "Dataset ya tiene datos o RDF no encontrado. No se reimporta."
fi

echo "=== Fuseki Init Completo ==="
