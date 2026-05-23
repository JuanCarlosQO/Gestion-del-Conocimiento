"""
Compatibilidad con las rutas que antes apuntaban a Node (puerto 3000).
Traduce peticiones al FastAPI local (8001) y al esquema Postgres/RDF.
"""
import json
import time
import uuid

import requests
from django.http import JsonResponse
from pydantic import ValidationError

from .schemas.finanzas import (
    FinanzasGenerarPagoBody,
    FinanzasKgSugeridoQuery,
    LiquidacionRecolectorBody,
    ReporteDiarioBody,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

API = "http://127.0.0.1:8001"


def _req(method, path, **kwargs):
    url = f"{API}{path}" if path.startswith("/") else f"{API}/{path}"
    return requests.request(method, url, timeout=60, **kwargs)


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _pydantic_400(exc: ValidationError) -> JsonResponse:
    errs = exc.errors()
    first = errs[0] if errs else {}
    loc = ".".join(str(x) for x in first.get("loc", ()))
    msg = first.get("msg", "Datos inválidos")
    detail = f"{loc}: {msg}" if loc else str(msg)
    return JsonResponse({"message": detail, "errors": errs}, status=400)


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "activo", "si", "sí")


def _rdf_list(clase: str):
    r = _req("GET", f"/detallesClase/{clase}")
    if r.status_code != 200:
        return {}
    data = r.json()
    ind = data.get("Individuos") or {}
    return ind


def _rdf_row_finca(ind_id, props):
    return {
        "id_finca": ind_id,
        "nombre_finca": props.get("nombre"),
        "direccion_finca": props.get("direccion"),
        "area_finca": props.get("area"),
        "altitud_finca": props.get("altitud"),
        "id_propietario": props.get("fk_idPropietario"),
    }


def _rdf_row_lote(ind_id, props):
    return {
        "id_finca": ind_id,
        "nombre_lote_finca": props.get("nombre"),
        "cantidadCafe_finca": props.get("cantidad"),
        "tamanio_finca": props.get("area"),
        "altitud_finca": props.get("estado"),
        "id_mantenimiento": "—",
    }


def _rdf_row_recoleccion(ind_id, props):
    fecha = props.get("fecha")
    if hasattr(fecha, "isoformat"):
        fecha = fecha.isoformat()
    return {
        "id_recoleccion": ind_id,
        "fecha_recoleccion": fecha,
        "id_recolector": props.get("fk_idRecolector"),
    }


def _rdf_row_mantenimiento(ind_id, props):
    fecha = props.get("fecha")
    if hasattr(fecha, "isoformat"):
        fecha = str(fecha)[:10]
    return {
        "id_tipocafe": ind_id,
        "tipo_mantenimiento_tipocafe": props.get("tipo"),
        "fecha_mantenimiento_tipocafe": fecha,
    }


def _rdf_row_insumo(ind_id, props):
    est = props.get("estado")
    return {
        "id_insumo": ind_id,
        "nombre_insumo": props.get("nombre"),
        "preciounidad_insumo": props.get("precio"),
        "estado_insumo": "Activo" if est is True else ("Inactivo" if est is False else est),
        "id_tipoinsumo": props.get("tipo"),
        "unidad_medida": props.get("unidadMedida") or "",
        "metodo_aplicacion": props.get("metodoAplicacion") or "",
    }


def _detalle_payload_finca(ind_id, datos, rels):
    return {"data": {"id_finca": ind_id, "nombre_finca": datos.get("nombre"), "direccion_finca": datos.get("direccion"), "area_finca": datos.get("area"), "altitud_finca": datos.get("altitud"), "id_propietario": datos.get("fk_idPropietario")}}


def _detalle_payload_lote(ind_id, datos, rels):
    return {"data": {"id_finca": ind_id, "nombre_lote_finca": datos.get("nombre"), "cantidadCafe_finca": datos.get("cantidad"), "tamanio_finca": datos.get("area"), "altitud_finca": datos.get("estado"), "id_mantenimiento": rels.get("tieneMantenimiento", "—")}}


def _detalle_payload_recoleccion(ind_id, datos, rels):
    fecha = datos.get("fecha")
    if hasattr(fecha, "isoformat"):
        fecha = fecha.isoformat()
    return {"data": {"id_recoleccion": ind_id, "fecha_recoleccion": fecha, "id_recolector": datos.get("fk_idRecolector")}}


def _detalle_payload_mantenimiento(ind_id, datos, rels):
    fecha = datos.get("fecha")
    if hasattr(fecha, "isoformat"):
        fecha = str(fecha)[:10]
    return {"data": {"id_tipocafe": ind_id, "tipo_mantenimiento_tipocafe": datos.get("tipo"), "fecha_mantenimiento_tipocafe": fecha}}


def _detalle_payload_insumo(ind_id, datos, rels):
    est = datos.get("estado")
    return {"id_insumo": ind_id, "nombre_insumo": datos.get("nombre"), "preciounidad_insumo": datos.get("precio"), "estado_insumo": "1" if est is True else "0", "id_tipoinsumo": datos.get("tipo"), "unidad_medida": datos.get("unidadMedida") or "", "metodo_aplicacion": datos.get("metodoAplicacion") or ""}


def _get_detalle(ind_id):
    r = _req("GET", f"/detalle/{ind_id}")
    if r.status_code != 200:
        return None
    j = r.json()
    return j.get("Id"), j.get("Datos") or {}, j.get("Relaciones") or {}


def _pg_rows(tabla):
    r = _req("GET", f"/detallesT/{tabla}")
    if r.status_code != 200:
        return []
    data = r.json()
    return data if isinstance(data, list) else []


def _metodo_pago_label(value):
    metodo = str(value or "").strip()
    lower = metodo.lower()
    if metodo == "1" or "efect" in lower:
        return "Efectivo", 1
    if metodo == "2" or "trans" in lower:
        return "Transferencia", 2
    if metodo == "3" or "tarj" in lower:
        return "Tarjeta", 3
    return metodo or "Efectivo", 1


def _row_pago_front(row):
    if not row:
        return {}
    metodo, metodo_codigo = _metodo_pago_label(row.get("metodo_pago"))
    return {"id_pago": row.get("id_pago"), "fecha_pago": row.get("fecha_pago"), "preciokilo_pago": row.get("preciokilo_pago"), "estado_pago": row.get("estado_pago"), "monto_pago": row.get("monto_pago"), "fk_idreport": row.get("fk_id_reporte"), "metodo_pago": metodo, "metodo_pago_codigo": metodo_codigo}


def _row_reporte_api(row):
    if not row:
        return {}
    est = row.get("estado_reporte")
    return {"id_reporte": row.get("id_reporte"), "estado_reporte": bool(est) if est is not None else False, "totalrecoleccion_reporte": row.get("totaltecoleccion_reporte"), "fk_idrecolector": row.get("fk_id_recolector"), "fecha_reporte": row.get("fecha_reporte")}


def _row_tipodoc(row):
    return {"id_tipodoc": row.get("id_doc"), "nombre_tipodoc": row.get("tipo"), "tipo_tipodoc": row.get("tipo")}


def _row_metodo_list(row):
    if not row:
        return {}
    nm = row.get("nombre_metodoaplicacion")
    return {"id_metodoaplicacion": row.get("id_metodoaplicacion"), "nombre_metodoaplicacion": nm, "nombre_aplicacion": nm}


# =====================================================================
# FINCA
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_productosfinca(request):
    if request.method == "GET":
        return JsonResponse([_rdf_row_finca(k, v) for k, v in _rdf_list("finca").items()], safe=False)
    body = _json_body(request)
    id_finca = body.get("id_finca") or f"finca_{uuid.uuid4().hex[:10]}"
    payload = {"id_finca": id_finca, "id_numeric": _int(body.get("id_numeric"), int(time.time()) % 1_000_000_000), "nombre": body.get("nombre_finca"), "direccion": body.get("direccion_finca"), "area": _int(body.get("area_finca"), 0), "altitud": _int(body.get("altitud_finca"), 0), "FK_idPropietario": str(body.get("id_propietario") or ""), "lotes": [], "compras": []}
    r = _req("POST", "/fincas", json=payload)
    if r.status_code != 200:
        return JsonResponse({"message": r.text or "Error API"}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": _rdf_row_finca(id_finca, {"nombre": payload["nombre"], "direccion": payload["direccion"], "area": payload["area"], "altitud": payload["altitud"], "fk_idPropietario": payload["FK_idPropietario"]})})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_productosfinca_id(request, id_finca):
    if request.method == "GET":
        d = _get_detalle(id_finca)
        if not d:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse(_detalle_payload_finca(*d))
    if request.method == "DELETE":
        r = _req("DELETE", f"/individuos/{id_finca}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": r.json().get("mensaje", "Eliminado")})
    body = _json_body(request)
    patch = {k: v for k, v in {"nombre": body.get("nombre_finca"), "direccion": body.get("direccion_finca"), "area": _int(body.get("area_finca"), None), "altitud": _int(body.get("altitud_finca"), None), "fk_idPropietario": str(body.get("id_propietario") or "")}.items() if v is not None and v != ""}
    r = _req("PUT", f"/corregirIndividuo/{id_finca}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# LOTE
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_productoslote(request):
    if request.method == "GET":
        return JsonResponse([_rdf_row_lote(k, v) for k, v in _rdf_list("lote").items()], safe=False)
    body = _json_body(request)
    id_lote = body.get("id_lote") or body.get("id_finca") or f"lote_{uuid.uuid4().hex[:10]}"
    payload = {"id_lote": str(id_lote), "id_numeric": _int(body.get("id_numeric"), int(time.time()) % 1_000_000_000), "nombre": body.get("nombre_lote") or body.get("nombre_lote_finca"), "area": _int(body.get("tamanio_finca") or body.get("area"), 0), "cantidad": _int(body.get("cantidadCafe") or body.get("cantidadCafe_finca"), 0), "estado": _bool(body.get("estado_insumo") or body.get("estado") or True), "eventosRecoleccion": [], "suministros": [], "mantenimientos": [body.get("id_mantenimiento")] if body.get("id_mantenimiento") else []}
    r = _req("POST", "/lotes", json=payload)
    if r.status_code != 200:
        return JsonResponse({"message": r.text or "Error API"}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": _rdf_row_lote(id_lote, {"nombre": payload["nombre"], "area": payload["area"], "cantidad": payload["cantidad"], "estado": payload["estado"]})})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_productoslote_id(request, id_lote):
    if request.method == "GET":
        d = _get_detalle(id_lote)
        if not d:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse(_detalle_payload_lote(*d))
    if request.method == "DELETE":
        r = _req("DELETE", f"/individuos/{id_lote}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": r.json().get("mensaje", "Eliminado")})
    body = _json_body(request)
    patch = {k: v for k, v in {"nombre": body.get("nombre_lote_finca"), "area": _int(body.get("tamanio_finca"), None), "cantidad": _int(body.get("cantidadCafe_finca"), None), "estado": body.get("altitud_finca")}.items() if v is not None and v != ""}
    if "estado" in patch:
        patch["estado"] = _bool(patch["estado"])
    r = _req("PUT", f"/corregirIndividuo/{id_lote}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# RECOLECCIÓN
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_recoleccion(request):
    if request.method == "GET":
        return JsonResponse([_rdf_row_recoleccion(k, v) for k, v in _rdf_list("recoleccion").items()], safe=False)
    body = _json_body(request)
    id_rec = body.get("id_recoleccion") or f"rec_{uuid.uuid4().hex[:10]}"
    payload = {"id_recoleccion": str(id_rec), "id_numeric": _int(body.get("id_numeric"), int(time.time()) % 1_000_000_000), "fecha": body.get("fecha_recoleccion") or body.get("fecha"), "FK_idRecolector": str(body.get("id_recolector") or "")}
    r = _req("POST", "/recolecciones", json=payload)
    if r.status_code != 200:
        try:
            msg = r.json().get("detail", r.text)
        except Exception:
            msg = r.text
        return JsonResponse({"message": str(msg)}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": _rdf_row_recoleccion(id_rec, {"fecha": payload["fecha"], "fk_idRecolector": payload["FK_idRecolector"]})})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_recoleccion_id(request, id_recoleccion):
    if request.method == "GET":
        d = _get_detalle(id_recoleccion)
        if not d:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse(_detalle_payload_recoleccion(*d))
    if request.method == "DELETE":
        r = _req("DELETE", f"/individuos/{id_recoleccion}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": r.json().get("mensaje", "Eliminado")})
    body = _json_body(request)
    patch = {k: v for k, v in {"fecha": body.get("fecha_recoleccion"), "fk_idRecolector": str(body.get("id_recolector") or "")}.items() if v}
    r = _req("PUT", f"/corregirIndividuo/{id_recoleccion}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# REPORTE
# =====================================================================
@csrf_exempt
@require_http_methods(["GET"])
def api_productosreporte(request):
    rol = (request.session.get("rol") or "").strip().lower()
    fk_persona = (request.session.get("fk_persona") or "").strip()
    rows = _pg_rows("reporte")
    if rol == "recolector" and fk_persona:
        rows = [r for r in rows if str(r.get("fk_id_recolector") or "") == fk_persona]
    return JsonResponse([_row_reporte_api(x) for x in rows], safe=False)


@csrf_exempt
@require_http_methods(["DELETE"])
def api_productosreporte_id(request, id_reporte):
    if (request.session.get("rol") or "").strip().lower() not in ("admin", "propietario"):
        return JsonResponse({"message": "Acceso denegado"}, status=403)
    r = _req("DELETE", f"/registros/reporte/{id_reporte}")
    if r.status_code != 200:
        return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
    return JsonResponse({"message": "Reporte eliminado con éxito"})


# =====================================================================
# PAGO
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_pago(request):
    if request.method == "GET":
        return JsonResponse([_row_pago_front(x) for x in _pg_rows("pago")], safe=False)
    body = _json_body(request)
    id_pago = body.get("id_pago") or f"P{uuid.uuid4().hex[:10]}"
    metodo_str, _ = _metodo_pago_label(body.get("metodo_pago"))
    payload = {"id_pago": str(id_pago), "fecha_pago": body.get("fecha_pago"), "preciokilo_pago": float(body.get("preciokilo_pago") or 0), "estado_pago": True, "monto_pago": float(body.get("monto_pago") or 0), "metodo_pago": metodo_str, "fk_id_reporte": str(body.get("fk_idreport") or body.get("fk_id_reporte") or "")}
    r = _req("POST", "/pagos", json=payload)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": {"id_pago": id_pago}})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_pago_id(request, id_pago):
    if request.method == "GET":
        r = _req("GET", f"/consultarRegistro/pago/{id_pago}")
        if r.status_code != 200:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse(_row_pago_front(r.json()))
    if request.method == "DELETE":
        r = _req("DELETE", f"/registros/pago/{id_pago}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": "Eliminado"})
    body = _json_body(request)
    patch = {}
    for k in ("fecha_pago", "preciokilo_pago", "monto_pago", "estado_pago", "fk_id_reporte", "metodo_pago"):
        if k in body:
            if k == "preciokilo_pago" or k == "monto_pago":
                patch[k] = float(body[k])
            elif k == "estado_pago":
                patch[k] = _bool(body[k])
            elif k == "metodo_pago":
                patch[k], _ = _metodo_pago_label(body[k])
            else:
                patch[k] = body[k]
    if "fk_idreport" in body:
        patch["fk_id_reporte"] = str(body["fk_idreport"])
    r = _req("PATCH", f"/corregirRegistro/pago/{id_pago}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# INSUMO
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_insumos(request):
    if request.method == "GET":
        return JsonResponse([_rdf_row_insumo(k, v) for k, v in _rdf_list("insumo").items()], safe=False)
    body = _json_body(request)
    id_insumo = body.get("id_insumo") or f"ins_{uuid.uuid4().hex[:8]}"
    payload = {"id_insumo": str(id_insumo), "id_numeric": _int(body.get("id_numeric"), int(time.time()) % 1_000_000_000), "nombre": body.get("nombre_insumo"), "precio": float(body.get("preciounidad_insumo") or 0), "tipo": str(body.get("id_tipoinsumo") or "general"), "estado": _bool(body.get("estado_insumo") if body.get("estado_insumo") not in (None, "") else True), "unidadMedida": str(body.get("unidad_medida") or ""), "metodoAplicacion": str(body.get("metodo_aplicacion") or ""), "compras": [], "suministrosVinculados": []}
    r = _req("POST", "/insumos", json=payload)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": {"id_insumo": id_insumo, "nombre_insumo": payload["nombre"], "preciounidad_insumo": payload["precio"], "estado_insumo": payload["estado"], "id_tipoinsumo": payload["tipo"], "unidad_medida": payload["unidadMedida"], "metodo_aplicacion": payload["metodoAplicacion"]}})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_insumos_id(request, id_insumo):
    if request.method == "GET":
        d = _get_detalle(id_insumo)
        if not d:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse(_detalle_payload_insumo(*d))
    if request.method == "DELETE":
        r = _req("DELETE", f"/individuos/{id_insumo}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": r.json().get("mensaje", "Eliminado")})
    body = _json_body(request)
    patch = {k: v for k, v in {"nombre": body.get("nombre_insumo"), "precio": float(body["preciounidad_insumo"]) if body.get("preciounidad_insumo") is not None else None, "tipo": body.get("id_tipoinsumo"), "estado": _bool(body["estado_insumo"]) if body.get("estado_insumo") is not None else None, "unidadMedida": body.get("unidad_medida"), "metodoAplicacion": body.get("metodo_aplicacion")}.items() if v is not None and v != ""}
    r = _req("PUT", f"/corregirIndividuo/{id_insumo}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# MANTENIMIENTO (usa alias productostipocafe)
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_productostipocafe(request):
    if request.method == "GET":
        return JsonResponse([_rdf_row_mantenimiento(k, v) for k, v in _rdf_list("mantenimiento").items()], safe=False)
    body = _json_body(request)
    mid = body.get("id_tipocafe") or body.get("id_mantenimiento") or f"mant_{uuid.uuid4().hex[:8]}"
    fecha = body.get("fecha_mantenimiento_tipocafe")
    if fecha is not None and not isinstance(fecha, str):
        fecha = str(fecha)
    payload = {"id_mantenimiento": str(mid), "id_numeric": _int(body.get("id_numeric"), int(time.time()) % 1_000_000_000), "fecha": fecha or "", "tipo": str(body.get("tipo_mantenimiento_tipocafe") or "")}
    r = _req("POST", "/mantenimientos", json=payload)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": _rdf_row_mantenimiento(mid, {"fecha": payload["fecha"], "tipo": payload["tipo"]})})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_productostipocafe_id(request, id_tipocafe):
    if request.method == "GET":
        d = _get_detalle(id_tipocafe)
        if not d:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse(_detalle_payload_mantenimiento(*d))
    if request.method == "DELETE":
        r = _req("DELETE", f"/individuos/{id_tipocafe}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": r.json().get("mensaje", "Eliminado")})
    body = _json_body(request)
    patch = {}
    if body.get("tipo_mantenimiento_tipocafe"):
        patch["tipo"] = body["tipo_mantenimiento_tipocafe"]
    if body.get("fecha_mantenimiento_tipocafe") is not None:
        patch["fecha"] = str(body["fecha_mantenimiento_tipocafe"])
    r = _req("PUT", f"/corregirIndividuo/{id_tipocafe}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# TIPO DOCUMENTO
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_productos_tipodoc(request):
    if request.method == "GET":
        return JsonResponse([_row_tipodoc(x) for x in _pg_rows("tipo_doc")], safe=False)
    body = _json_body(request)
    id_doc = _int(body.get("id_tipodoc") or body.get("id_doc"))
    payload = {"tipo": body.get("nombre_tipodoc") or body.get("tipo")}
    if id_doc > 0:
        payload["id_doc"] = id_doc
    r = _req("POST", "/tipoDocumento", json=payload)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": {"id_tipodoc": payload.get("id_doc"), "nombre_tipodoc": payload.get("tipo"), "tipo_tipodoc": payload.get("tipo")}})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_productos_tipodoc_id(request, id_tipodoc):
    if request.method == "GET":
        r = _req("GET", f"/consultarRegistro/tipo_doc/{id_tipodoc}")
        if r.status_code != 200:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse({"data": _row_tipodoc(r.json())})
    if request.method == "DELETE":
        r = _req("DELETE", f"/registros/tipo_doc/{id_tipodoc}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": "Eliminado"})
    body = _json_body(request)
    patch = {}
    if body.get("nombre_tipodoc") or body.get("tipo"):
        patch["tipo"] = body.get("nombre_tipodoc") or body.get("tipo")
    r = _req("PATCH", f"/corregirRegistro/tipo_doc/{id_tipodoc}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


# =====================================================================
# STUBS (MongoDB stub / recolecciones vista)
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_connect_mongo(request):
    return JsonResponse({"connected": True, "success": True, "message": "Modo local (sin MongoDB)"})


@csrf_exempt
@require_http_methods(["GET", "POST", "OPTIONS"])
def api_recolecciones_vista(request, documento_persona):
    rol = (request.session.get("rol") or "").strip().lower()
    fk_persona = (request.session.get("fk_persona") or "").strip()
    doc = (documento_persona or "").strip()
    if not doc:
        return JsonResponse({"recolecciones": []})
    if rol == "recolector" and fk_persona and doc != fk_persona:
        return JsonResponse({"message": "Acceso denegado"}, status=403)
    try:
        rp = _req("GET", f"/consultarRegistro/persona/{doc}")
        rr = _req("GET", f"/consultarRegistro/recolector/{doc}")
        if rp.status_code != 200 or rr.status_code != 200:
            return JsonResponse({"recolecciones": []})
        pers = rp.json()
        reco = rr.json()
        total = 0.0
        rrep = _req("GET", "/detallesT/reporte")
        if rrep.status_code == 200:
            for rep in rrep.json():
                if str(rep.get("fk_id_recolector") or "") == doc:
                    total += float(rep.get("totaltecoleccion_reporte") or 0)
        fi = reco.get("fechainicio_recolector")
        if fi is not None and hasattr(fi, "isoformat"):
            fi = fi.isoformat()
        return JsonResponse({"recolecciones": [{"documento_persona": doc, "nombre_persona": pers.get("nombre_persona"), "cantidadtotal": total, "fechainicio_recolector": str(fi) if fi is not None else ""}]})
    except Exception:
        return JsonResponse({"recolecciones": []})


# =====================================================================
# FINANZAS
# =====================================================================
@csrf_exempt
@require_http_methods(["POST"])
def api_reporte_diario(request):
    if (request.session.get("rol") or "").strip().lower() not in ("admin", "propietario"):
        return JsonResponse({"message": "Acceso denegado"}, status=403)
    try:
        body = ReporteDiarioBody.model_validate(_json_body(request))
    except ValidationError as e:
        return _pydantic_400(e)
    r = _req("POST", "/reportes/diario", json={"id_recolector": body.id_recolector, "fecha": body.fecha})
    if r.status_code != 200:
        try:
            msg = r.json().get("detail", r.text)
        except Exception:
            msg = r.text
        return JsonResponse({"message": str(msg)}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": r.json()})


@csrf_exempt
@require_http_methods(["POST"])
def api_liquidacion_recolector(request):
    if (request.session.get("rol") or "").strip().lower() not in ("admin", "propietario"):
        return JsonResponse({"message": "Acceso denegado"}, status=403)
    try:
        body = LiquidacionRecolectorBody.model_validate(_json_body(request))
    except ValidationError as e:
        return _pydantic_400(e)
    payload = {"id_recolector": body.id_recolector, "precio_kilo": body.precio_kilo}
    r = _req("POST", "/liquidacion/recolector", json=payload)
    if r.status_code != 200:
        try:
            msg = r.json().get("detail", r.text)
        except Exception:
            msg = r.text
        return JsonResponse({"message": str(msg)}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": r.json()})


@csrf_exempt
@require_http_methods(["GET"])
def api_finanzas_kg_sugerido(request):
    if (request.session.get("rol") or "").strip().lower() not in ("admin", "propietario"):
        return JsonResponse({"message": "Acceso denegado"}, status=403)
    try:
        q = FinanzasKgSugeridoQuery.model_validate(dict(request.GET))
    except ValidationError as e:
        return _pydantic_400(e)
    r = _req("GET", "/finanzas/kg_sugerido", params={"id_recolector": q.id_recolector, "fecha": q.fecha})
    if r.status_code != 200:
        try:
            msg = r.json().get("detail", r.text)
        except Exception:
            msg = r.text
        return JsonResponse({"message": str(msg)}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": r.json()})


@csrf_exempt
@require_http_methods(["POST"])
def api_finanzas_generar_pago(request):
    if (request.session.get("rol") or "").strip().lower() not in ("admin", "propietario"):
        return JsonResponse({"message": "Acceso denegado"}, status=403)
    try:
        body = FinanzasGenerarPagoBody.model_validate(_json_body(request))
    except ValidationError as e:
        return _pydantic_400(e)
    r = _req("POST", "/finanzas/generar_pago", json={"id_recolector": body.id_recolector, "dias": [d.model_dump() for d in body.dias]})
    if r.status_code != 200:
        try:
            msg = r.json().get("detail", r.text)
        except Exception:
            msg = r.text
        return JsonResponse({"message": str(msg)}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": r.json()})


# =====================================================================
# CATÁLOGOS
# =====================================================================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_tiposinsumo(request):
    if request.method == "GET":
        return JsonResponse(_pg_rows("cat_tipo_insumo"), safe=False)
    body = _json_body(request)
    r = _req("POST", "/catalogo/tipoInsumo", json={"id_tipoinsumo": str(body.get("id_tipoinsumo") or ""), "nombre_tipo": body.get("nombre_tipo") or ""})
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": r.json().get("data", {})})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_tiposinsumo_id(request, id_tipoinsumo):
    if request.method == "GET":
        r = _req("GET", f"/consultarRegistro/cat_tipo_insumo/{id_tipoinsumo}")
        if r.status_code != 200:
            return JsonResponse({"message": "No encontrado"}, status=404)
        row = r.json()
        return JsonResponse({"id_tipoinsumo": row.get("id_tipoinsumo"), "nombre_tipo": row.get("nombre_tipo")})
    if request.method == "DELETE":
        r = _req("DELETE", f"/registros/cat_tipo_insumo/{id_tipoinsumo}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": "Eliminado"})
    body = _json_body(request)
    patch = {}
    if body.get("nombre_tipo"):
        patch["nombre_tipo"] = body["nombre_tipo"]
    r = _req("PATCH", f"/corregirRegistro/cat_tipo_insumo/{id_tipoinsumo}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "Actualizado"})


@csrf_exempt
@require_http_methods(["DELETE"])
def api_productostiposinsumo_id(request, id_tipoinsumo):
    r = _req("DELETE", f"/registros/cat_tipo_insumo/{id_tipoinsumo}")
    if r.status_code != 200:
        return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
    return JsonResponse({"message": "Tipo de insumo eliminado correctamente."})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_productosmedida(request):
    if request.method == "GET":
        return JsonResponse(_pg_rows("cat_unidad_medida"), safe=False)
    body = _json_body(request)
    r = _req("POST", "/catalogo/unidadMedida", json={"nombre_unidadmedida": body.get("nombre_unidadmedida") or ""})
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    return JsonResponse({"message": "OK", "data": r.json().get("data", {})})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_productosmedida_id(request, id_unidadmedida):
    if request.method == "GET":
        r = _req("GET", f"/consultarRegistro/cat_unidad_medida/{id_unidadmedida}")
        if r.status_code != 200:
            return JsonResponse({"message": "No encontrado"}, status=404)
        row = r.json()
        return JsonResponse({"data": {"id_unidadmedida": row.get("id_unidadmedida"), "nombre_unidadmedida": row.get("nombre_unidadmedida")}})
    if request.method == "DELETE":
        r = _req("DELETE", f"/registros/cat_unidad_medida/{id_unidadmedida}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": "Eliminado"})
    body = _json_body(request)
    patch = {}
    if body.get("nombre_unidadmedida"):
        patch["nombre_unidadmedida"] = body["nombre_unidadmedida"]
    r = _req("PATCH", f"/corregirRegistro/cat_unidad_medida/{id_unidadmedida}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "OK"})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_productosmetodoaplica(request):
    if request.method == "GET":
        return JsonResponse([_row_metodo_list(x) for x in _pg_rows("cat_metodo_aplicacion")], safe=False)
    body = _json_body(request)
    nombre = body.get("nombre_metodoaplicacion") or body.get("nombre_aplicacion") or ""
    r = _req("POST", "/catalogo/metodoAplicacion", json={"nombre_metodoaplicacion": nombre})
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code or 400)
    d = r.json().get("data") or {}
    d["nombre_aplicacion"] = d.get("nombre_metodoaplicacion")
    return JsonResponse({"message": "OK", "data": d})


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_productosmetodoaplica_id(request, id_metodoaplicacion):
    if request.method == "GET":
        r = _req("GET", f"/consultarRegistro/cat_metodo_aplicacion/{id_metodoaplicacion}")
        if r.status_code != 200:
            return JsonResponse({"message": "No encontrado"}, status=404)
        return JsonResponse({"data": _row_metodo_list(r.json())})
    if request.method == "DELETE":
        r = _req("DELETE", f"/registros/cat_metodo_aplicacion/{id_metodoaplicacion}")
        if r.status_code != 200:
            return JsonResponse({"message": r.json().get("detail", "Error")}, status=r.status_code)
        return JsonResponse({"message": "Eliminado"})
    body = _json_body(request)
    patch = {}
    if body.get("nombre_metodoaplicacion"):
        patch["nombre_metodoaplicacion"] = body["nombre_metodoaplicacion"]
    r = _req("PATCH", f"/corregirRegistro/cat_metodo_aplicacion/{id_metodoaplicacion}", json=patch)
    if r.status_code != 200:
        return JsonResponse({"message": r.text}, status=r.status_code)
    return JsonResponse({"message": "OK"})


# =====================================================================
# NUEVAS RUTAS — KPIs Dashboard
# =====================================================================
@csrf_exempt
@require_http_methods(["GET"])
def api_personas(request):
    """GET /api/personas → lista de personas (Postgres)."""
    return JsonResponse(_pg_rows("persona"), safe=False)


@csrf_exempt
@require_http_methods(["GET"])
def api_fincas(request):
    """GET /api/fincas → lista de fincas (RDF)."""
    return JsonResponse([_rdf_row_finca(k, v) for k, v in _rdf_list("finca").items()], safe=False)


@csrf_exempt
@require_http_methods(["GET"])
def api_pagos_list(request):
    """GET /api/pagos → lista de pagos (Postgres)."""
    return JsonResponse([_row_pago_front(x) for x in _pg_rows("pago")], safe=False)
