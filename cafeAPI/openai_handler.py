# --- OpenAI ChatGPT Handler con gpt-4o-mini SDK ---
import json
import time
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException

try:
    from openai import OpenAI, RateLimitError, APIError
    OPENAI_DISPONIBLE = True
except ImportError:
    OpenAI = None
    RateLimitError = None
    APIError = None
    OPENAI_DISPONIBLE = False


class OpenAIHandler:
    """Maneja solicitudes a OpenAI ChatGPT con caché y rate limiting."""

    def __init__(self, api_key: Optional[str] = None, cache_ttl_seconds: int = 7200):
        if not OPENAI_DISPONIBLE:
            raise ImportError(
                "openai no está instalado. Ejecuta: pip install openai"
            )

        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError(
                "No se encontró OPENAI_API_KEY. Agrega la variable en cafeAPI/.env "
                "y reinicia el servidor. Obtén tu clave en https://platform.openai.com/api-keys"
            )

        # Configurar cliente de OpenAI
        self.client = OpenAI(api_key=self.api_key)
        # Usar el modelo gpt-4o-mini (mejor precio/rendimiento)
        self.model = "gpt-4o-mini"

        # Caché en memoria
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl_seconds

        # Rate limiting (OpenAI plan free: 3 rpm, pagado: 90,000 TPM)
        self.request_times = []
        self.max_requests_per_minute = 3        # Conservative para plan free
        self.total_requests_today = 0
        self.daily_limit = 100                  # Conservative para plan free
        self.last_reset = datetime.now()

    def _get_cache_key(self, prompt: str, json_mode: bool) -> str:
        cache_str = f"{prompt}_{json_mode}"
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _check_rate_limit(self):
        now = datetime.now()

        # Reset diario
        if (now - self.last_reset).days >= 1:
            self.total_requests_today = 0
            self.last_reset = now

        if self.total_requests_today >= self.daily_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Cuota diaria de OpenAI agotada ({self.total_requests_today}/{self.daily_limit}). "
                       "Espera hasta mañana. Para más solicitudes, obtén un API key con plan pagado en https://platform.openai.com/billing",
            )

        # Limpiar requests viejas
        self.request_times = [
            t for t in self.request_times if (now - t).total_seconds() < 60
        ]

        if len(self.request_times) >= self.max_requests_per_minute:
            espera = 60 - (now - self.request_times[0]).total_seconds()
            raise HTTPException(
                status_code=429,
                detail=f"Límite por minuto alcanzado ({self.max_requests_per_minute}/min). Espera {int(espera) + 1} segundos.",
            )

    def _limpiar_cache(self):
        now = datetime.now()
        self.cache = {
            k: v for k, v in self.cache.items()
            if (now - v["timestamp"]).total_seconds() < self.cache_ttl
        }

    def llamar_openai(
        self,
        prompt: str,
        json_mode: bool = False,
        reintentos: int = 5,
        usar_cache: bool = True,
    ) -> str:
        """Llama a OpenAI ChatGPT con caché y reintentos."""

        # Caché
        self._limpiar_cache()
        cache_key = self._get_cache_key(prompt, json_mode)
        if usar_cache and cache_key in self.cache:
            print(f"[CACHE HIT] {prompt[:50]}...")
            return self.cache[cache_key]["respuesta"]

        self._check_rate_limit()

        ultimo_error = None

        for intento in range(reintentos):
            try:
                # Construir config
                response_format = None
                if json_mode:
                    response_format = {"type": "json_object"}

                # Llamada a OpenAI ChatGPT
                respuesta_obj = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    response_format=response_format,
                    timeout=45
                )

                respuesta = respuesta_obj.choices[0].message.content.strip()

                # Guardar en caché
                self.cache[cache_key] = {
                    "respuesta": respuesta,
                    "timestamp": datetime.now(),
                }
                self.request_times.append(datetime.now())
                self.total_requests_today += 1

                print(f"[✓] OpenAI OK (intento {intento + 1}/{reintentos})")
                return respuesta

            except RateLimitError as e:
                ultimo_error = e
                if intento < reintentos - 1:
                    espera = (2 ** intento) * 5
                    print(f"[429] Intento {intento + 1}/{reintentos}. Esperando {espera}s...")
                    time.sleep(espera)
                    continue
                raise HTTPException(
                    status_code=429,
                    detail="Límite de OpenAI alcanzado tras varios reintentos. Espera unos minutos.",
                )

            except APIError as e:
                ultimo_error = e
                error_str = str(e).lower()

                if "401" in error_str or "unauthorized" in error_str or "invalid" in error_str:
                    raise HTTPException(
                        status_code=401,
                        detail="API Key de OpenAI inválida. Verifica OPENAI_API_KEY en .env",
                    )

                if intento < reintentos - 1:
                    espera = min(10, (2 ** intento) * 2)
                    print(f"[ERROR] Intento {intento + 1}/{reintentos}. Esperando {espera}s... ({error_str[:80]})")
                    time.sleep(espera)
                    continue

                raise HTTPException(
                    status_code=500,
                    detail=f"Error al contactar OpenAI [{type(ultimo_error).__name__}]: {str(ultimo_error)[:400]}",
                )

            except Exception as e:
                ultimo_error = e
                if intento < reintentos - 1:
                    espera = min(10, (2 ** intento) * 2)
                    print(f"[ERROR] Intento {intento + 1}/{reintentos}. Esperando {espera}s...")
                    time.sleep(espera)
                    continue

                raise HTTPException(
                    status_code=500,
                    detail=f"Error inesperado [{type(ultimo_error).__name__}]: {str(ultimo_error)[:400]}",
                )

        raise HTTPException(
            status_code=500,
            detail=f"Falló tras {reintentos} intentos [{type(ultimo_error).__name__}]: {str(ultimo_error)[:400]}",
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "requests_today": self.total_requests_today,
            "daily_limit": self.daily_limit,
            "cache_size": len(self.cache),
            "cache_ttl_seconds": self.cache_ttl,
            "requests_last_minute": len(self.request_times),
        }


# ── Singleton global ──
_openai_handler: Optional[OpenAIHandler] = None


def get_openai_handler() -> OpenAIHandler:
    """Obtiene la instancia única del handler (se crea al primer uso)."""
    global _openai_handler
    if _openai_handler is None:
        _openai_handler = OpenAIHandler()
    return _openai_handler
