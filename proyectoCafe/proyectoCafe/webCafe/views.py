import requests, json, os
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from functools import wraps

# URL base de la FastAPI — se lee en cada petición para respetar el settings cargado
def _api_base():
    return getattr(settings, 'FASTAPI_URL', 'http://127.0.0.1:8001')

# ──────────────────────────────────────────────
# CARGA DE VARIABLES DE ENTORNO (.env)
# ──────────────────────────────────────────────

def _load_env():
    """Carga variables del .env ubicado en cafeAPI/ (un nivel arriba del proyecto Django)."""
    env_paths = [
        Path(__file__).resolve().parent.parent.parent.parent.parent / "cafeAPI" / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        os.environ.setdefault(key.strip(), val.strip())
            break

_load_env()

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _volver_url(request):
    rol = (request.session.get("rol") or "").strip().lower()
    if rol == "admin":
        return "/vista_admin/"
    if rol == "recolector":
        return "/vista_recolector/"
    return "/vista_propietario/"


def _session_rol(request):
    return (request.session.get("rol") or "").strip().lower()


def _require_authenticated(request):
    if not request.session.get("usuario"):
        return JsonResponse({"error": "No autenticado", "message": "Inicie sesión."}, status=401)
    return None


def _crud_propietario_entidad_solo_admin(request, nombre_tabla):
    if (nombre_tabla or "").strip().lower() == "propietario" and _session_rol(request) != "admin":
        return JsonResponse({"error": "Acceso denegado"}, status=403)
    return None


def _propietario_posee_recolector(request, id_recolector):
    fk = (request.session.get("fk_persona") or "").strip()
    try:
        r = requests.get(f"{_api_base()}/consultarRegistro/recolector/{id_recolector}", timeout=5)
        if r.status_code != 200:
            return False
        row = r.json()
        return str(row.get("fk_id_propietario") or "") == fk
    except Exception:
        return False


def _puede_corregir_recolector(request, id_recolector):
    rol = _session_rol(request)
    if rol == "admin":
        return True
    if rol == "propietario":
        return _propietario_posee_recolector(request, id_recolector)
    if rol == "recolector":
        return str(id_recolector).strip() == str(request.session.get("fk_persona") or "").strip()
    return False


def _puede_eliminar_recolector(request, id_recolector):
    rol = _session_rol(request)
    if rol == "admin":
        return True
    if rol == "propietario":
        return _propietario_posee_recolector(request, id_recolector)
    return False


# ──────────────────────────────────────────────
# DECORADORES
# ──────────────────────────────────────────────

def reporte_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = (request.session.get("rol") or "").strip().lower()
        if rol not in ["admin", "propietario", "recolector"]:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.session.get('rol') != 'admin':
            messages.error(request, "Acceso denegado. Se requieren permisos de administrador.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def propietario_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = request.session.get('rol')
        if rol not in ['admin', 'propietario']:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_or_propietario_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = request.session.get('rol')
        if rol not in ['admin', 'propietario']:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def recolector_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        rol = request.session.get('rol')
        if rol not in ['admin', 'recolector']:
            messages.error(request, "Acceso denegado.")
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


_TABLA_REDIRECT = {
    "propietario": "/propietario/",
    "persona": "/persona/",
    "finca": "/finca/",
    "recolector": "/recolector/",
    "lote": "/lote/",
    "insumo": "/insumo/",
    "recoleccion": "/recoleccion/",
}


def _redirect_por_tabla(nombre_tabla: str):
    return redirect(_TABLA_REDIRECT.get((nombre_tabla or "").lower(), "/"))


# ──────────────────────────────────────────────
# AUTENTICACIÓN
# ──────────────────────────────────────────────

def inicio(request):
    if request.method == "POST":
        user = (request.POST.get("username") or "").strip()
        pasw = (request.POST.get("password") or "").strip()
        try:
            response = requests.post(
                f"{_api_base()}/login",
                json={"username": user, "password": pasw},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                request.session['usuario'] = data['username']
                rol = (data.get('rol') or '').strip().lower()
                request.session['fk_persona'] = data.get('fk_persona')
                request.session['rol'] = rol
                if rol == 'admin':
                    return redirect("/vista_admin/")
                elif rol == 'propietario':
                    return redirect("/vista_propietario/")
                elif rol == 'recolector':
                    return redirect("/vista_recolector/")
            else:
                messages.error(request, "Usuario o contraseña incorrectos")
        except Exception:
            messages.error(request, "Error de conexión con el servidor de autenticación")
    return render(request, "inicio.html")


def logout_view(request):
    """Cierra la sesión y redirige al login."""
    request.session.flush()
    return redirect("/")


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

def dashboard(request):
    if not request.session.get("usuario"):
        return redirect("/")
    return render(request, "dashboard.html")


# ──────────────────────────────────────────────
# GET
# ──────────────────────────────────────────────

def consultar_registro(request, nombre_tabla, id_registro):
    deny = _require_authenticated(request)
    if deny:
        return deny
    deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
    if deny:
        return deny
    url_api = f"{_api_base()}/consultarRegistro/{nombre_tabla}/{id_registro}"
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if nombre_tabla.lower() == "persona" and _session_rol(request) == "recolector":
                if str(id_registro).strip() != str(request.session.get("fk_persona") or "").strip():
                    return JsonResponse({"error": "Acceso denegado"}, status=403)
            if nombre_tabla.lower() == "persona":
                roles = []
                if requests.get(f"{_api_base()}/consultarRegistro/propietario/{id_registro}", timeout=5).status_code == 200:
                    roles.append("Propietario")
                if requests.get(f"{_api_base()}/consultarRegistro/recolector/{id_registro}", timeout=5).status_code == 200:
                    roles.append("Recolector")
                if isinstance(data, dict):
                    data['rol'] = ", ".join(roles) if roles else "Sin Rol"
            if nombre_tabla.lower() == "recolector" and _session_rol(request) == "propietario":
                fk_sess = (request.session.get("fk_persona") or "").strip()
                fk_row = data.get("fk_id_propietario") if isinstance(data, dict) else None
                if str(fk_row or "") != fk_sess:
                    return JsonResponse({'error': 'Acceso denegado'}, status=403)
            if nombre_tabla.lower() == "recolector" and _session_rol(request) == "recolector":
                if str(id_registro).strip() != str(request.session.get("fk_persona") or "").strip():
                    return JsonResponse({'error': 'Acceso denegado'}, status=403)
            return JsonResponse(data)
        else:
            return JsonResponse({'error': 'Registro no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': 'La API no responde'}, status=500)


def get_todos(request, nombre_tabla):
    deny = _require_authenticated(request)
    if deny:
        return deny
    deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
    if deny:
        return deny
    t = (nombre_tabla or "").strip().lower()
    if t == "persona" and _session_rol(request) == "recolector":
        return JsonResponse({"error": "Acceso denegado"}, status=403)
    url_api = f"{_api_base()}/detallesT/{nombre_tabla}"
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            rows = response.json()
            rol = _session_rol(request)
            if t == "recolector" and rol == "propietario":
                fk_sess = (request.session.get("fk_persona") or "").strip()
                if isinstance(rows, list):
                    rows = [r for r in rows if str(r.get("fk_id_propietario") or "") == fk_sess]
            if t == "recolector" and rol == "recolector":
                fk_sess = str(request.session.get("fk_persona") or "").strip()
                if isinstance(rows, list):
                    rows = [r for r in rows if str(r.get("id_recolector") or "") == fk_sess]
            return JsonResponse(rows, safe=False)
        return JsonResponse({"error": response.text or "Error API"}, status=response.status_code)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def obtener_persona_temporal(request):
    datos = request.session.get('datos_persona_temp')
    if datos:
        return JsonResponse({"success": True, "data": datos})
    return JsonResponse({"success": False, "message": "No hay datos temporales"})


def consulta_rdf(request, tipo_consulta, nombre_tabla, id):
    template = f"{nombre_tabla.lower()}.html"
    if tipo_consulta == 'detalle':
        url_api = f"{_api_base()}/detalle/{id}"
    else:
        url_api = f"{_api_base()}/detallesClase/{id}"
    try:
        response = requests.get(url_api, timeout=10)
        if response.status_code == 200:
            datos = response.json()
            return render(request, template, {
                'resultado': datos, 'tipo': tipo_consulta,
                'nombre': id, 'nombre_tabla': nombre_tabla
            })
        else:
            messages.error(request, "El recurso no existe")
    except Exception:
        messages.error(request, "Error de conexión")
    return render(request, template)


# ──────────────────────────────────────────────
# EDITAR
# ──────────────────────────────────────────────

def corregir_registro(request, nombre_tabla, id_registro):
    if request.method == 'POST':
        try:
            deny = _require_authenticated(request)
            if deny:
                return deny
            deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
            if deny:
                return deny
            tabla = (nombre_tabla or "").strip().lower()
            if tabla == "recolector" and not _puede_corregir_recolector(request, id_registro):
                return JsonResponse({"status": "error", "message": "Acceso denegado"}, status=403)
            if tabla == "persona" and _session_rol(request) == "recolector":
                if str(id_registro).strip() != str(request.session.get("fk_persona") or "").strip():
                    return JsonResponse({"status": "error", "message": "Acceso denegado"}, status=403)
            actualiza = json.loads(request.body)
            url_api = f"{_api_base()}/corregirRegistro/{nombre_tabla}/{id_registro}"
            response = requests.patch(url_api, json=actualiza, timeout=10)
            if response.status_code == 200:
                return JsonResponse({"status": "success", "message": "Registro actualizado correctamente"})
            else:
                try:
                    msg = response.json().get("detail", "Error en la API")
                except Exception:
                    msg = response.text or "Error en la API"
                return JsonResponse({"status": "error", "message": msg}, status=response.status_code or 400)
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    return JsonResponse({"status": "error", "message": "Método no permitido"})


def editar_individuo(request, id_recurso, nombre_tabla):
    if request.method == 'POST':
        nuevos_datos = {k: v for k, v in request.POST.items() if k != 'csrfmiddlewaretoken'}
        url_api = f"{_api_base()}/corregirIndividuo/{id_recurso}"
        try:
            response = requests.put(url_api, json=nuevos_datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Información actualizada")
                return _redirect_por_tabla(nombre_tabla)
            else:
                messages.error(request, "Error al actualizar")
        except Exception:
            messages.error(request, "Error de conexión")
    return _redirect_por_tabla(nombre_tabla)


# ──────────────────────────────────────────────
# ELIMINAR
# ──────────────────────────────────────────────

def eliminar_registro(request, nombre_tabla, id_registro):
    try:
        deny = _require_authenticated(request)
        if deny:
            return deny
        deny = _crud_propietario_entidad_solo_admin(request, nombre_tabla)
        if deny:
            return deny
        tabla = (nombre_tabla or "").lower()
        doc = str(id_registro)
        if tabla == "recolector":
            if not _puede_eliminar_recolector(request, doc):
                return JsonResponse({"status": "error", "message": "Acceso denegado."}, status=403)
        if tabla == "persona" and _session_rol(request) == "recolector":
            return JsonResponse({"status": "error", "message": "Acceso denegado."}, status=403)
        if tabla in ["propietario", "recolector"]:
            if tabla == "propietario":
                try:
                    from .node_compat import _rdf_list
                    fincas = _rdf_list("finca")
                    for fid, props in fincas.items():
                        if str(props.get("fk_idPropietario")) == str(id_registro):
                            requests.delete(f"{_api_base()}/individuos/{fid}", timeout=10)
                except Exception as e_finca:
                    pass
            url_rol = f"{_api_base()}/registros/{nombre_tabla}/{id_registro}"
            r_rol = requests.delete(url_rol, timeout=10)
            if r_rol.status_code != 200:
                try:
                    msg = r_rol.json().get("detail", r_rol.text)
                except Exception:
                    msg = r_rol.text or "Error al eliminar el rol"
                return JsonResponse({"status": "error", "message": str(msg)}, status=400)
            url_persona = f"{_api_base()}/registros/Persona/{id_registro}"
            response = requests.delete(url_persona, timeout=10)
        else:
            url_api = f"{_api_base()}/registros/{nombre_tabla}/{id_registro}"
            response = requests.delete(url_api, timeout=10)
        if response.status_code == 200:
            return JsonResponse({"status": "success", "message": f"Registro {id_registro} eliminado correctamente."})
        else:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text or "Error al eliminar."
            return JsonResponse({"status": "error", "message": str(detail)}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Error de conexión: {str(e)}"}, status=500)


def eliminar_individuo(request, id_recurso, nombre_tabla):
    url_api = f"{_api_base()}/individuos/{id_recurso}"
    try:
        response = requests.delete(url_api, timeout=10)
        if response.status_code == 200:
            messages.success(request, "El recurso se ha eliminado")
        else:
            messages.error(request, "No es posible eliminarlo.")
    except Exception:
        messages.error(request, "Error de conexión")
    return _redirect_por_tabla(nombre_tabla)


# ──────────────────────────────────────────────
# PÁGINAS / FORMULARIOS
# ──────────────────────────────────────────────

@admin_or_propietario_required
@ensure_csrf_cookie
def persona_page(request):
    return render(request, 'persona.html', {
        "volver_url": _volver_url(request),
        "is_admin": request.session.get("rol") == "admin"
    })


@admin_or_propietario_required
def insert_persona(request):
    if request.method == 'POST':
        try:
            if 'datos_persona_temp' not in request.session:
                return JsonResponse({"success": False, "message": "Primero registra la persona como temporal."}, status=400)
            datos = {
                "documento_persona": request.POST.get('documento_persona'),
                "nombre_persona": request.POST.get('nombre_persona'),
                "edad_persona": int(request.POST.get('edad_persona')),
                "telefono_persona": request.POST.get('telefono_persona'),
                "fk_tipo_documento": int(request.POST.get('id_tipodoc'))
            }
            response = requests.post(f"{_api_base()}/personas", json=datos, timeout=10)
            if response.status_code == 200:
                return JsonResponse({"success": True, "data": datos})
            return JsonResponse({"success": False, "message": "Error en la API"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})


@admin_or_propietario_required
def insert_persona_temporal(request):
    if request.method == 'POST':
        datos = {
            "documento_persona": request.POST.get('documento_persona'),
            "fk_tipo_documento": int(request.POST.get('id_tipodoc')),
            "nombre_persona": request.POST.get('nombre_persona'),
            "edad_persona": int(request.POST.get('edad_persona')),
            "telefono_persona": request.POST.get('telefono_persona')
        }
        request.session['datos_persona_temp'] = datos
        return JsonResponse({"success": True, "data": datos})
    return JsonResponse({"success": False})


@admin_required
def propietario_page(request):
    return render(request, 'propietario.html', {"volver_url": _volver_url(request)})


@admin_required
def insert_propietario(request):
    if request.method == 'POST':
        try:
            id_propietario = request.POST.get('id_propietario')
            email = request.POST.get('email_propietario')
            estado = request.POST.get('estado_propietario')
            username = (request.POST.get("username_propietario") or "").strip()
            password = (request.POST.get("password_propietario") or "").strip()
            estado_bool = estado != "0"
            if not id_propietario or not email or not username or not password:
                return JsonResponse({"success": False, "message": "Campos incompletos"}, status=400)
            datos = {"id_propietario": id_propietario, "email_propietario": email, "estado_propietario": estado_bool}
            response = requests.post(f"{_api_base()}/propietarios", json=datos, timeout=10)
            if response.status_code == 200:
                r_user = requests.post(f"{_api_base()}/usuarios", json={
                    "username": username, "password": password,
                    "rol": "propietario", "fk_persona": str(id_propietario),
                }, timeout=10)
                if r_user.status_code != 200:
                    try:
                        requests.delete(f"{_api_base()}/registros/propietario/{id_propietario}", timeout=5)
                        requests.delete(f"{_api_base()}/registros/persona/{id_propietario}", timeout=5)
                    except Exception:
                        pass
                    try:
                        detail = r_user.json().get("detail")
                    except Exception:
                        detail = None
                    return JsonResponse({"success": False, "message": detail or "No se pudo crear el usuario"}, status=400)
                request.session.pop('datos_persona_temp', None)
                return JsonResponse({"success": True, "data": {**datos, "username": username}})
            return JsonResponse({"success": False, "message": "Error en API Propietarios"})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False})


@admin_or_propietario_required
def recoleccion_page(request):
    return render(request, 'recoleccion.html', {"volver_url": _volver_url(request)})


@admin_or_propietario_required
def insert_recoleccion(request):
    if request.method == 'POST':
        datos = {
            "id_recoleccion": request.POST.get('id_recoleccion'),
            "id_numeric": int(request.POST.get('id_numeric') or 0),
            "fecha": request.POST.get('fecha'),
            "FK_idRecolector": str(request.POST.get('fk_idRecolector') or ''),
        }
        try:
            response = requests.post(f"{_api_base()}/recolecciones", json=datos, timeout=10)
            if response.status_code == 200:
                return render(request, 'recoleccion.html', {'recoleccion': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "Error de conexión")
    return render(request, 'recoleccion.html')


@admin_or_propietario_required
@ensure_csrf_cookie
def recolector_page(request):
    rol = (request.session.get("rol") or "").strip().lower()
    return render(request, 'recolector.html', {
        "volver_url": _volver_url(request),
        "is_propietario": rol == "propietario",
        "is_admin": rol == "admin",
        "propietario_doc": (request.session.get("fk_persona") or ""),
    })


@admin_or_propietario_required
def insert_recolector(request):
    if request.method == 'POST':
        try:
            datos = {
                "id_recolector": request.POST.get('id_recolector'),
                "fechainicio_recolector": request.POST.get('fechainicio_recolector'),
                "fechafin_recolector": request.POST.get('fechafin_recolector') or None,
                "estado_recolector": request.POST.get('estado_recolector') == "1",
                "diastrabajados_recolector": int(request.POST.get('diastrabajados_recolector') or 0)
            }
            rol = (request.session.get("rol") or "").strip().lower()
            fk_fin = (request.POST.get("fk_id_finca") or "").strip()
            if rol == "propietario":
                datos["fk_id_propietario"] = request.session.get("fk_persona")
                if not fk_fin:
                    return JsonResponse({"success": False, "message": "Debe seleccionar una finca"}, status=400)
                datos["fk_id_finca"] = fk_fin
            elif rol == "admin":
                fp = (request.POST.get("fk_id_propietario") or "").strip()
                if fp:
                    datos["fk_id_propietario"] = fp
                if fk_fin:
                    datos["fk_id_finca"] = fk_fin
            response = requests.post(f"{_api_base()}/recolectores", json=datos, timeout=10)
            if response.status_code == 200:
                request.session.pop('datos_persona_temp', None)
                out = {"success": True, "data": datos}
                try:
                    av = response.json().get("aviso")
                    if av:
                        out["aviso"] = av
                except Exception:
                    pass
                return JsonResponse(out)
            else:
                try:
                    msg = response.json().get("detail", response.text)
                except Exception:
                    msg = response.text or "Error en la API de Recolectores"
                return JsonResponse({"success": False, "message": str(msg)}, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return render(request, 'recolector.html')


@reporte_access_required
def reporte_page(request):
    rol = (request.session.get("rol") or "").strip().lower()
    return render(request, 'reporte.html', {
        "volver_url": _volver_url(request),
        "is_recolector": rol == "recolector",
    })


@reporte_access_required
def insert_reporte(request):
    if request.method == 'POST':
        est = request.POST.get('estado_reporte')
        datos = {
            "id_reporte": str(request.POST.get('id_reporte') or ''),
            "fecha_reporte": request.POST.get('fecha_reporte'),
            "totaltecoleccion_reporte": float(request.POST.get('totalrecoleccion_reporte') or 0),
            "estado_reporte": est in ('1', 'true', 'True', 'on', 'si'),
            "fk_id_recolector": str(request.POST.get('fk_id_recolector') or ''),
        }
        if _session_rol(request) == "recolector":
            doc = str(request.session.get("fk_persona") or "").strip()
            if str(datos["fk_id_recolector"]).strip() != doc:
                messages.error(request, "Solo puede registrar reportes de su propio documento.")
                return render(request, 'reporte.html')
        try:
            response = requests.post(f"{_api_base()}/reportes", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Reporte registrado")
                return render(request, 'reporte.html', {'reporte': datos, 'respuesta_api': response.json()})
            else:
                messages.error(request, "Error en la API")
        except Exception:
            messages.error(request, "La API no está encendida")
    return render(request, 'reporte.html')


@admin_or_propietario_required
def finca_page(request):
    return render(request, 'finca.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_finca(request):
    if request.method == 'POST':
        datos = {
            "id_finca": request.POST.get('id_finca'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "nombre": request.POST.get('nombre'),
            "direccion": request.POST.get('direccion'),
            "area": float(request.POST.get('area')),
            "altitud": float(request.POST.get('altitud')),
            "FK_idPropietario": str(request.POST.get('FK_idpropietario') or ''),
            "lotes": request.POST.getlist('lotes'),
            "compras": request.POST.getlist('compras')
        }
        if _session_rol(request) == "propietario":
            datos["FK_idPropietario"] = str(request.session.get("fk_persona") or "")
        try:
            response = requests.post(f"{_api_base()}/fincas", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Finca registrada")
                return render(request, 'finca.html', {'finca': datos, 'respuesta_api': response.json()})
            messages.error(request, "Error en la API")
        except Exception:
            messages.error(request, "La API no está encendida")
    return render(request, 'finca.html')


@admin_or_propietario_required
def insumo_page(request):
    return render(request, 'insumo.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_insumo(request):
    if request.method == 'POST':
        datos = {
            "id_insumo": request.POST.get('id_insumo'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "nombre": request.POST.get('nombre'),
            "precio": float(request.POST.get('precio')),
            "tipo": request.POST.get('tipo'),
            "estado": request.POST.get('estado'),
            "compras": request.POST.getlist('compras'),
            "suministrosVinculados": request.POST.getlist('suministrosVinculados')
        }
        try:
            response = requests.post(f"{_api_base()}/insumos", json=datos, timeout=10)
            if response.status_code == 200:
                return render(request, 'insumo.html', {'insumo': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "Error de conexión")
    return render(request, 'insumo.html')


@admin_or_propietario_required
def pago_page(request):
    return render(request, 'pago.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_pago(request):
    if request.method == 'POST':
        est = request.POST.get('estado_pago')
        datos = {
            "id_pago": str(request.POST.get('id_pago') or ''),
            "fecha_pago": request.POST.get('fecha_pago'),
            "preciokilo_pago": float(request.POST.get('preciokilo_pago') or 0),
            "estado_pago": est in ('1', 'true', 'True', 'on', 'si'),
            "monto_pago": float(request.POST.get('monto_pago') or 0),
            "metodo_pago": str(request.POST.get('metodo_pago') or 'Efectivo'),
            "fk_id_reporte": str(request.POST.get('fk_id_reporte') or ''),
        }
        try:
            response = requests.post(f"{_api_base()}/pagos", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Pago registrado")
                return render(request, 'pago.html', {'pago': datos, 'respuesta_api': response.json()})
            messages.error(request, "Error en la API")
        except Exception:
            messages.error(request, "La API no está encendida")
    return render(request, 'pago.html')


@admin_or_propietario_required
def mantenimiento_page(request):
    return render(request, 'mantenimiento.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_mantenimiento(request):
    if request.method == 'POST':
        datos = {
            "id_mantenimiento": request.POST.get('id_mantenimiento'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "fecha": request.POST.get('fecha'),
            "tipo": request.POST.get('tipo')
        }
        try:
            response = requests.post(f"{_api_base()}/mantenimientos", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Mantenimiento registrado")
                return render(request, 'mantenimiento.html', {'mantenimiento': datos, 'respuesta_api': response.json()})
            messages.error(request, "Error en la API")
        except Exception:
            messages.error(request, "La API no está encendida")
    return render(request, 'mantenimiento.html')


@propietario_required
def insert_evento_recoleccion(request):
    if request.method == 'POST':
        datos = {
            "id_evento": request.POST.get('id_evento'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "cantidad": int(request.POST.get('cantidad')),
            "id_lote": request.POST.get('id_lote'),
            "id_recoleccion": request.POST.get('id_recoleccion')
        }
        try:
            response = requests.post(f"{_api_base()}/eventosRecoleccion", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Evento registrado")
                return render(request, 'recoleccion.html', {'evento': datos, 'respuesta_api': response.json()})
            messages.error(request, "Error en la API")
        except Exception:
            messages.error(request, "La API no está encendida")
    return render(request, 'recoleccion.html')


@propietario_required
def insert_inventario(request):
    if request.method == 'POST':
        datos = {
            "id_inventario": request.POST.get('id_inventario'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "cantidad": int(request.POST.get('cantidad')),
            "fecha": request.POST.get('fecha'),
            "unidadMedida": request.POST.get('unidadMedida'),
            "id_insumo": request.POST.get('id_insumo')
        }
        try:
            response = requests.post(f"{_api_base()}/inventarios", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Inventario registrado")
                return render(request, 'inventario.html', {'inventario': datos, 'respuesta_api': response.json()})
            messages.error(request, response.text or "Error en la API")
        except Exception as ex:
            messages.error(request, str(ex))
    return render(request, 'inventario.html')


@propietario_required
def insert_suministro(request):
    if request.method == 'POST':
        datos = {
            "id_suministro": request.POST.get('id_suministro'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "fecha": request.POST.get('fecha'),
            "cantidad": int(request.POST.get('cantidad')),
            "estado": request.POST.get('estado') == 'true',
            "id_insumo": request.POST.get('id_insumo'),
            "id_lote": request.POST.get('id_lote')
        }
        try:
            response = requests.post(f"{_api_base()}/suministros", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Suministro registrado")
                return render(request, 'suministros.html', {'suministro': datos, 'respuesta_api': response.json()})
            messages.error(request, response.text or "Error en la API")
        except Exception as ex:
            messages.error(request, str(ex))
    return render(request, 'suministros.html')


@admin_or_propietario_required
def tipo_doc_page(request):
    return render(request, 'tipo_doc.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_tipodocumento(request):
    if request.method == 'POST':
        datos = {"id_doc": int(request.POST.get('id_doc')), "tipo": request.POST.get('tipo')}
        try:
            response = requests.post(f"{_api_base()}/tipoDocumento", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Tipo de documento registrado")
                return render(request, 'tipo_doc.html', {'tipo_doc': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "Error de conexión")
    return render(request, 'tipo_doc.html')


@admin_or_propietario_required
def compra_page(request):
    return render(request, 'compra.html', {"volver_url": _volver_url(request)})


@propietario_required
def inventario_page(request):
    return render(request, 'inventario.html', {"volver_url": _volver_url(request)})


@propietario_required
def suministro_page(request):
    return render(request, 'suministros.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_compra(request):
    if request.method == 'POST':
        est = request.POST.get('estado')
        datos = {
            "id_compra": request.POST.get('id_compra'),
            "id_numeric": int(request.POST.get('id_numeric') or 0),
            "fecha": request.POST.get('fecha'),
            "cantidad": int(float(request.POST.get('cantidad') or 0)),
            "precio": float(request.POST.get('precio') or 0),
            "estado": est in ('1', 'true', 'True', 'on', 'si'),
            "id_insumo": request.POST.get('id_insumo'),
            "id_finca": request.POST.get('id_finca')
        }
        try:
            response = requests.post(f"{_api_base()}/compras", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Compra registrada")
                return render(request, 'compra.html', {'compra': datos, 'respuesta_api': response.json()})
            messages.error(request, response.text or "Error al registrar compra")
        except Exception as ex:
            messages.error(request, f"Error de conexión: {ex}")
    return render(request, 'compra.html')


@admin_or_propietario_required
def lote_page(request):
    return render(request, 'lote.html', {"volver_url": _volver_url(request)})


@propietario_required
def insert_lote(request):
    if request.method == 'POST':
        datos = {
            "id_lote": request.POST.get('id_lote'),
            "id_numeric": int(request.POST.get('id_numeric')),
            "nombre": request.POST.get('nombre'),
            "area": float(request.POST.get('area')),
            "cantidad": int(request.POST.get('cantidad')),
            "estado": request.POST.get('estado'),
            "eventosRecoleccion": request.POST.getlist('eventosRecoleccion'),
            "suministros": request.POST.getlist('suministros'),
            "mantenimientos": request.POST.getlist('mantenimientos')
        }
        try:
            response = requests.post(f"{_api_base()}/lotes", json=datos, timeout=10)
            if response.status_code == 200:
                messages.success(request, "Lote registrado")
                return render(request, 'lote.html', {'lote': datos, 'respuesta_api': response.json()})
        except Exception:
            messages.error(request, "La API no está encendida")
    return render(request, 'lote.html')


# ──────────────────────────────────────────────
# VISTAS DE ROL
# ──────────────────────────────────────────────

@admin_required
def audi_recolector(request):
    return render(request, 'audi_recolector.html', {"volver_url": "/vista_admin/"})


@admin_required
def audi_reporte(request):
    return render(request, 'audi_reporte.html', {"volver_url": "/vista_admin/"})


@admin_required
def vista_admin(request):
    return render(request, 'vista_admin.html')


@propietario_required
def vista_propietario(request):
    return render(request, 'vista_propietario.html')


@recolector_required
def vista_recolector(request):
    return render(request, 'vista_recolector.html', {
        "fk_persona": request.session.get("fk_persona") or "",
    })


@recolector_required
def perfil_recolector(request):
    doc = (request.session.get("fk_persona") or "").strip()
    if not doc:
        messages.error(request, "No hay persona asociada a este usuario.")
        return redirect("/")
    if request.method == "POST":
        try:
            actualiza = json.loads(request.body or "{}")
        except Exception:
            actualiza = {}
        actualiza.pop("documento_persona", None)
        actualiza.pop("documento", None)
        try:
            r = requests.patch(f"{_api_base()}/corregirRegistro/persona/{doc}", json=actualiza, timeout=10)
            if r.status_code == 200:
                return JsonResponse({"status": "success"})
            return JsonResponse({"status": "error", "message": r.text or "Error API"}, status=400)
        except Exception:
            return JsonResponse({"status": "error", "message": "Error de conexión"}, status=500)
    try:
        r = requests.get(f"{_api_base()}/consultarRegistro/persona/{doc}", timeout=10)
        persona_data = r.json() if r.status_code == 200 else {}
    except Exception:
        persona_data = {}
    return render(request, "perfil_recolector.html", {
        "volver_url": "/vista_recolector/",
        "persona": persona_data
    })


@admin_or_propietario_required
def tipo_insumo_page(request):
    return render(request, 'tipo_insumo.html', {"volver_url": _volver_url(request)})


@admin_or_propietario_required
def unidad_medida_page(request):
    return render(request, 'unidad_medida.html', {"volver_url": _volver_url(request)})


@admin_or_propietario_required
def metodo_aplicacion_page(request):
    return render(request, 'metodo_aplicacion.html', {"volver_url": _volver_url(request)})


# ══════════════════════════════════════════════
# ASISTENTE IA — CHATBOT con Groq (LLaMA 3)
# La API key se lee desde cafeAPI/.env (variable GROQ_API_KEY).
# Nunca escribas claves directamente en este archivo.
# ══════════════════════════════════════════════

GROQ_MODEL = "llama-3.1-8b-instant"
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"


def _get_groq_key() -> str:
    """Devuelve la GROQ_API_KEY desde el entorno (cargado del .env)."""
    return os.environ.get("GROQ_API_KEY", "").strip()


def _chatbot_contexto():
    """Recopila TODOS los datos reales del sistema para que la IA tenga contexto completo."""

    def fetch(tabla):
        try:
            r = requests.get(f"{_api_base()}/detallesT/{tabla}", timeout=6)
            return r.json() if r.status_code == 200 else []
        except Exception:
            return []

    # ── Obtener todos los datos ────────────────────────────────────────────────
    personas      = fetch("persona")
    propietarios  = fetch("propietario")
    recolectores  = fetch("recolector")
    fincas        = fetch("finca")
    lotes         = fetch("lote")
    insumos       = fetch("insumo")
    recolecciones = fetch("recoleccion")
    reportes      = fetch("reporte")
    pagos         = fetch("pago")
    compras       = fetch("compra")
    inventarios   = fetch("inventario")
    suministros   = fetch("suministro")
    mantenimientos= fetch("mantenimiento")

    datos_tecnicos = {
        "persona": personas, "propietario": propietarios, "recolector": recolectores,
        "finca": fincas, "lote": lotes, "insumo": insumos,
        "recoleccion": recolecciones, "reporte": reportes, "pago": pagos,
        "compra": compras, "inventario": inventarios, "suministro": suministros,
        "mantenimiento": mantenimientos,
    }

    # ── Construir texto de contexto legible para la IA ─────────────────────────────
    lines = []

    # Personas
    lines.append(f"\n--- PERSONAS REGISTRADAS ({len(personas)}) ---")
    for p in personas:
        lines.append(f"  Doc: {p.get('documento_persona')} | Nombre: {p.get('nombre_persona')} | "
                     f"Edad: {p.get('edad_persona')} | Tel: {p.get('telefono_persona')}")

    # Propietarios
    lines.append(f"\n--- PROPIETARIOS ({len(propietarios)}) ---")
    for p in propietarios:
        lines.append(f"  ID: {p.get('id_propietario')} | Email: {p.get('email_propietario')} | "
                     f"Estado: {'Activo' if p.get('estado_propietario') else 'Inactivo'}")

    # Recolectores
    lines.append(f"\n--- RECOLECTORES ({len(recolectores)}) ---")
    for r in recolectores:
        lines.append(f"  ID: {r.get('id_recolector')} | Propietario: {r.get('fk_id_propietario')} | "
                     f"Finca: {r.get('fk_id_finca')} | "
                     f"Inicio: {r.get('fechainicio_recolector')} | Fin: {r.get('fechafin_recolector')} | "
                     f"Días trabajados: {r.get('diastrabajados_recolector')} | "
                     f"Estado: {'Activo' if r.get('estado_recolector') else 'Inactivo'}")

    # Fincas
    lines.append(f"\n--- FINCAS ({len(fincas)}) ---")
    for f in fincas:
        lines.append(f"  ID: {f.get('id_finca')} | Nombre: {f.get('nombre')} | "
                     f"Área: {f.get('area')} ha | Altitud: {f.get('altitud')} msnm | "
                     f"Propietario: {f.get('FK_idPropietario') or f.get('fk_idPropietario')}")

    # Lotes
    lines.append(f"\n--- LOTES ({len(lotes)}) ---")
    for l in lotes:
        lines.append(f"  ID: {l.get('id_lote')} | Nombre: {l.get('nombre')} | "
                     f"Área: {l.get('area')} ha | Cantidad plantas: {l.get('cantidad')} | "
                     f"Estado: {l.get('estado')}")

    # Insumos
    lines.append(f"\n--- INSUMOS ({len(insumos)}) ---")
    for i in insumos:
        lines.append(f"  ID: {i.get('id_insumo')} | Nombre: {i.get('nombre')} | "
                     f"Precio: ${i.get('precio')} | Tipo: {i.get('tipo')} | "
                     f"Estado: {i.get('estado')}")

    # Recolecciones
    lines.append(f"\n--- RECOLECCIONES ({len(recolecciones)}) ---")
    for r in recolecciones:
        lines.append(f"  ID: {r.get('id_recoleccion')} | Fecha: {r.get('fecha')} | "
                     f"Recolector: {r.get('FK_idRecolector') or r.get('fk_idRecolector')}")

    # Reportes
    lines.append(f"\n--- REPORTES DE RECOLECCIÓN ({len(reportes)}) ---")
    total_kg = 0
    for r in reportes:
        kg = float(r.get('totaltecoleccion_reporte') or 0)
        total_kg += kg
        lines.append(f"  ID: {r.get('id_reporte')} | Fecha: {r.get('fecha_reporte')} | "
                     f"Total kg: {kg} | Recolector: {r.get('fk_id_recolector')} | "
                     f"Estado: {'Pagado' if r.get('estado_reporte') else 'Pendiente'}")
    lines.append(f"  >>> TOTAL KG RECOLECTADOS EN TODOS LOS REPORTES: {total_kg:.1f} kg")

    # Resumen kg por recolector
    kg_por_recolector = {}
    for r in reportes:
        rec_id = str(r.get('fk_id_recolector') or '')
        kg = float(r.get('totaltecoleccion_reporte') or 0)
        kg_por_recolector[rec_id] = kg_por_recolector.get(rec_id, 0) + kg
    if kg_por_recolector:
        lines.append(f"\n--- KG RECOLECTADOS POR RECOLECTOR ---")
        for rec_id, kg in kg_por_recolector.items():
            lines.append(f"  Recolector {rec_id}: {kg:.1f} kg")

    # Pagos
    lines.append(f"\n--- PAGOS ({len(pagos)}) ---")
    total_pagos = 0
    for p in pagos:
        monto = float(p.get('monto_pago') or 0)
        total_pagos += monto
        lines.append(f"  ID: {p.get('id_pago')} | Fecha: {p.get('fecha_pago')} | "
                     f"Monto: ${monto:,.0f} | Método: {p.get('metodo_pago')} | "
                     f"Precio/kg: ${p.get('preciokilo_pago')} | Reporte: {p.get('fk_id_reporte')} | "
                     f"Estado: {'Pagado' if p.get('estado_pago') else 'Pendiente'}")
    lines.append(f"  >>> TOTAL PAGADO: ${total_pagos:,.0f}")

    # Compras
    lines.append(f"\n--- COMPRAS DE INSUMOS ({len(compras)}) ---")
    total_compras = 0
    for c in compras:
        precio = float(c.get('precio') or 0)
        total_compras += precio
        lines.append(f"  ID: {c.get('id_compra')} | Fecha: {c.get('fecha')} | "
                     f"Insumo: {c.get('id_insumo')} | Finca: {c.get('id_finca')} | "
                     f"Cantidad: {c.get('cantidad')} | Precio: ${precio:,.0f}")
    if compras:
        lines.append(f"  >>> TOTAL INVERTIDO EN COMPRAS: ${total_compras:,.0f}")

    # Inventarios
    lines.append(f"\n--- INVENTARIOS ({len(inventarios)}) ---")
    for i in inventarios:
        lines.append(f"  ID: {i.get('id_inventario')} | Insumo: {i.get('id_insumo')} | "
                     f"Cantidad: {i.get('cantidad')} {i.get('unidadMedida')} | Fecha: {i.get('fecha')}")

    # Suministros
    lines.append(f"\n--- SUMINISTROS APLICADOS ({len(suministros)}) ---")
    for s in suministros:
        lines.append(f"  ID: {s.get('id_suministro')} | Insumo: {s.get('id_insumo')} | "
                     f"Lote: {s.get('id_lote')} | Cantidad: {s.get('cantidad')} | "
                     f"Fecha: {s.get('fecha')} | Estado: {'Aplicado' if s.get('estado') else 'Pendiente'}")

    # Mantenimientos
    lines.append(f"\n--- MANTENIMIENTOS ({len(mantenimientos)}) ---")
    for m in mantenimientos:
        lines.append(f"  ID: {m.get('id_mantenimiento')} | Tipo: {m.get('tipo')} | Fecha: {m.get('fecha')}")

    context_str = "\n".join(lines) if lines else "Sin datos disponibles."
    return context_str, datos_tecnicos


def _chatbot_system_prompt(usuario: str, rol: str, context_str: str) -> str:
    conocimiento_fitosanitario = """
=== BASE DE CONOCIMIENTO: PLAGAS Y ENFERMEDADES DEL CAFÉ ===

ENFERMEDADES FUNGOSAS:
1. ROYA (Hemileia vastatrix): Manchas amarillas en el haz de la hoja, polvo anaranjado en el envés. Favorecida por temperaturas 18-28°C y alta humedad. Puede reducir la cosecha hasta un 50%. Control preventivo: fungicidas cúpricos (oxicloruro de cobre, hidróxido de cobre) cada 45-60 días en épocas lluviosas. Control curativo: triazoles (cyproconazole, tebuconazole). Control biológico: Beauveria bassiana, Trichoderma spp. Variedades resistentes: Colombia, Castillo, Cenicafé 1. Aplicar cuando el 5% de hojas presenten síntomas.
2. ANTRACNOSIS (Colletotrichum gloeosporioides): Lesiones oscuras en frutos y ramas, frutos negros momificados. Control: carbendazim o tiofanato metílico, mejorar drenaje, retirar material enfermo.
3. OJO DE GALLO / MANCHA DE HIERRO (Cercospora coffeicola): Manchas circulares con centro gris y halo amarillo. Favorecida por deficiencias de N y K. Control: fertilización adecuada, fungicidas cúpricos, regular sombra.
4. LLAGA MACANA (Ceratocystis fimbriata): Oscurecimiento vascular, muerte descendente de ramas, olor a alcohol. Control: evitar heridas, proteger cortes con pasta bordelesa, erradicar plantas enfermas, desinfectar herramientas.
5. PUDRICIN DE RAÍZ (Rosellinia / Phytophthora): Raíces negras, amarillamiento generalizado. Control: mejorar drenaje, cal agrícola, Trichoderma en suelo.

PLAGAS INSECTILES:
6. BROCA (Hypothenemus hampei) - LA MAS IMPORTANTE: Orificio en la corona del fruto, granos barrenados y fermentados. Pérdidas de hasta 35%. Control cultural: RE-RE (Recolección, Repase, Requinta), trampas con alcohol etílico+metanol (3:1). Control biológico: Beauveria bassiana. Control químico: Spinosad (solo cuando >2% frutos brocados). Monitoreo: muestrear 100 frutos por lote.
7. ACARO ROJO (Oligonychus yothersi): Hojas con brillo bronceado, defoliación. Favorecido por sequía. Control: riego, acaricidas (abamectina, bifenazate).
8. MINADOR DE LA HOJA (Leucoptera coffeella): Galerías sinuosas dentro de la hoja, manchas blancas traslúcidas. Control: clorpirifos, imidacloprid, parasitoides (Mirax insularis).
9. TRIPS (Frankliniella spp.): Deformación de flores y frutos, cicatrices corchosas. Control: Spinosad, Beauveria bassiana.
10. COCHINILLAS / ESCAMAS: Masas algodonosas blancas en ramas, fumagina negra. Control: aceite agrícola, imidacloprid.

DEFICIENCIAS NUTRICIONALES:
11. NITROGENO (N): Amarillamiento de hojas viejas, crecimiento lento. Corrección: urea, sulfato de amonio, compost.
12. POTASIO (K): Bordes quemados en hojas, frutos de menor peso. Corrección: KCl, sulfato de potasio.
13. HIERRO (Fe) - CLOROSIS FERRICA: Nervaduras verdes pero tejido entre nervaduras amarillo en hojas jóvenes. Corrección: quelato de hierro foliar.

BUENAS PRACTICAS GENERALES: Monitoreo semanal, rotación de fungicidas/insecticidas para evitar resistencia, priorizar control biológico y cultural antes del químico, nutrición balanceada como base de la sanidad, registrar todas las aplicaciones con fecha y dosis.
=== FIN BASE DE CONOCIMIENTO ===
"""
    return (
        "Eres SIGIC-IA, el asistente inteligente del Sistema de Información "
        "para la Gestión Integral del Café (SIGIC), desarrollado para fincas "
        "cafeteras colombianas.\n\n"
        f"Usuario activo: {usuario} (rol: {rol})\n\n"
        f"{conocimiento_fitosanitario}\n"
        "=== DATOS EN TIEMPO REAL DEL SISTEMA ===\n"
        f"{context_str}\n"
        "=========================================\n\n"
        "Puedes responder sobre:\n"
        "• Datos del sistema: recolectores, fincas, lotes, pagos, insumos, reportes\n"
        "• Plagas y enfermedades: síntomas, causas y cómo tratarlas con productos específicos\n"
        "• Deficiencias nutricionales y buenas prácticas agronómicas cafeteras\n\n"
        "Reglas:\n"
        "• Responde SIEMPRE en español\n"
        "• Usa los datos reales del sistema cuando la pregunta sea sobre el sistema\n"
        "• Usa la base de conocimiento fitosanitario para preguntas sobre plagas, enfermedades o nutrición\n"
        "• Da respuestas detalladas y prácticas en temas fitosanitarios (síntomas, causa, tratamiento)\n"
        "• Sé conciso en preguntas de datos del sistema (máximo 4 párrafos)\n"
        "• Nunca inventes datos del sistema que no estén en el contexto\n"
        "• Tono profesional pero amigable"
    )


@csrf_exempt
@admin_or_propietario_required
def api_chatbot_consultar(request):
    """
    Endpoint principal del chatbot.
    Usa Google Gemini leyendo la GEMINI_API_KEY desde cafeAPI/.env
    """
    try:
        return _api_chatbot_consultar_inner(request)
    except Exception as e:
        import traceback
        return JsonResponse({"error": f"Error interno: {str(e)}", "traceback": traceback.format_exc()}, status=500)


def _api_chatbot_consultar_inner(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    try:
        body = json.loads(request.body or "{}")
        pregunta = body.get("pregunta", "").strip()
    except Exception:
        return JsonResponse({"error": "Payload JSON inválido"}, status=400)

    if not pregunta:
        return JsonResponse({"error": "La pregunta no puede estar vacía"}, status=400)

    groq_key = _get_groq_key()
    if not groq_key or groq_key == "PEGA_TU_KEY_AQUI":
        return JsonResponse({
            "error": (
                "No se encontró GROQ_API_KEY. "
                "Obtén tu clave gratis en https://console.groq.com "
                "y agrégala en cafeAPI/.env como GROQ_API_KEY=gsk_..."
            )
        }, status=500)

    context_str, datos_tecnicos = _chatbot_contexto()
    usuario = request.session.get("usuario", "desconocido")
    rol     = _session_rol(request)
    system  = _chatbot_system_prompt(usuario, rol, context_str)

    import time
    resp = None
    for intento in range(3):
        try:
            resp = requests.post(
                GROQ_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {groq_key}",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": pregunta},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.4,
                },
                timeout=30,
            )
        except requests.exceptions.Timeout:
            return JsonResponse({"error": "La solicitud a Groq tardó demasiado. Intenta de nuevo."}, status=504)
        except requests.exceptions.ConnectionError:
            return JsonResponse({"error": "No se pudo conectar con Groq. Verifica tu conexión."}, status=503)

        if resp.status_code != 429:
            break
        time.sleep(3)

    if resp.status_code == 200:
        try:
            data  = resp.json()
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            return JsonResponse({"error": f"Respuesta inesperada de Groq: {str(e)}"}, status=500)

        return JsonResponse({
            "respuesta": reply,
            "detalles_tecnicos": {
                "database": f"PostgreSQL + Groq AI ({GROQ_MODEL})",
                "explanation": (
                    f"Contexto construido con {len(context_str.splitlines())} métricas "
                    f"del sistema en tiempo real."
                ),
                "sql": context_str,
                "resultados_sql": datos_tecnicos,
                "sparql": None,
                "resultados_rdf": None,
            }
        })

    status = resp.status_code
    try:
        err_body = resp.json()
        err_msg  = err_body.get("error", {}).get("message", resp.text)
    except Exception:
        err_msg = resp.text or f"HTTP {status}"

    if status == 401:
        return JsonResponse({
            "error": f"API key de Groq inválida. Verifica GROQ_API_KEY en cafeAPI/.env. Detalle: {err_msg}"
        }, status=403)
    if status == 429:
        return JsonResponse({
            "error": "Límite de Groq alcanzado. Espera un momento e intenta de nuevo."
        }, status=429)

    return JsonResponse({"error": f"Error de Groq (HTTP {status}): {err_msg}"}, status=500)


@admin_or_propietario_required
@ensure_csrf_cookie
def chatbot_page(request):
    return render(request, 'chatbot.html', {"volver_url": _volver_url(request)})


@require_POST
def chatbot_view(request):
    """Endpoint alternativo (mantiene compatibilidad con otros templates)."""
    return api_chatbot_consultar(request)
