
# ─── NUEVAS RUTAS para el dashboard (KPIs) ───────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
def api_personas(request):
    """Alias para el dashboard: GET /api/personas → lista de personas."""
    return JsonResponse(_pg_rows("persona"), safe=False)


@csrf_exempt
@require_http_methods(["GET"])
def api_fincas(request):
    """Alias para el dashboard: GET /api/fincas → lista de fincas (RDF)."""
    rows = []
    for ind_id, props in _rdf_list("finca").items():
        rows.append(_rdf_row_finca(ind_id, props))
    return JsonResponse(rows, safe=False)


@csrf_exempt
@require_http_methods(["GET"])
def api_pagos_list(request):
    """Alias para el dashboard: GET /api/pagos → lista de pagos (Postgres)."""
    return JsonResponse([_row_pago_front(x) for x in _pg_rows("pago")], safe=False)
