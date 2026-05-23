# --- Gemini API Handler con google-genai SDK ---
import json
import time
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_DISPONIBLE = True
except ImportError:
    genai = None
    genai_types = None
    GENAI_DISPONIBLE = False


class GeminiHandler:
    """Maneja solicitudes a Gemini con google-genai SDK, caché y rate limiting."""

    def __init__(self, api_key: Optional[str] = None, cache_ttl_seconds: int = 7200):
        if not GENAI_DISPONIBLE:
            raise ImportError(
                "google-genai no está instalado. Ejecuta: pip install google-genai"
            )

        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError(
                "No se encontró GEMINI_API_KEY. Agrega la variable en cafeAPI/.env "
                "y reinicia el servidor. Obtén tu clave gratis en https://aistudio.google.com/apikey"
            )

        # Configurar cliente usando el mismo patrón de tu notebook
        self.client = genai.Client(api_key=self.api_key)
        # Alinear el modelo con el que validaste en tu notebook
        self.model = "gemini-2.5-flash"

        # Caché en memoria
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl_seconds

        # Rate limiting
        self.request_times = []
        self.max_requests_per_minute = 20        # Reducido para respetar límites de Gemini gratuito
        self.total_requests_today = 0
        self.daily_limit = 300                   # Reducido para mantener dentro de cuota gratuita
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
                detail=f"Cuota diaria de Gemini agotada ({self.total_requests_today}/{self.daily_limit}). "
                       "Espera hasta mañana. Para más solicitudes, obtén una API key con plan pagado en https://aistudio.google.com/pricing",
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

    def llamar_gemini(
        self,
        prompt: str,
        json_mode: bool = False,
        reintentos: int = 5,
        usar_cache: bool = True,
    ) -> str:
        """Llama a Gemini usando google-genai SDK con caché y reintentos."""

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
                config_kwargs = {}
                if json_mode:
                    config_kwargs["response_mime_type"] = "application/json"

                # Llamada con google-genai SDK (igual que tu notebook)
                respuesta_obj = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(**config_kwargs)
                    if config_kwargs else None,
                )

                respuesta = respuesta_obj.text.strip()

                # Guardar en caché
                self.cache[cache_key] = {
                    "respuesta": respuesta,
                    "timestamp": datetime.now(),
                }
                self.request_times.append(datetime.now())
                self.total_requests_today += 1

                print(f"[✓] Gemini OK (intento {intento + 1}/{reintentos})")
                return respuesta

            except Exception as e:
                ultimo_error = e
                error_str = str(e).lower()

                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    if intento < reintentos - 1:
                        espera = (2 ** intento) * 5
                        print(f"[429] Intento {intento + 1}/{reintentos}. Esperando {espera}s...")
                        time.sleep(espera)
                        continue
                    raise HTTPException(
                        status_code=429,
                        detail="Límite de Gemini alcanzado tras varios reintentos. Espera unos minutos.",
                    )

                elif "401" in error_str or "unauthorized" in error_str or "api_key" in error_str or "api key" in error_str:
                    raise HTTPException(
                        status_code=401,
                        detail="API Key de Gemini inválida. Verifica GEMINI_API_KEY en .env",
                    )

                elif intento < reintentos - 1:
                    espera = min(10, (2 ** intento) * 2)
                    print(f"[ERROR] Intento {intento + 1}/{reintentos}. Esperando {espera}s... ({error_str[:80]})")
                    time.sleep(espera)
                    continue

                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error al contactar Gemini [{type(ultimo_error).__name__}]: {str(ultimo_error)[:400]}",
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
_gemini_handler: Optional[GeminiHandler] = None


def get_gemini_handler() -> GeminiHandler:
    """Obtiene la instancia única del handler (se crea al primer uso)."""
    global _gemini_handler
    if _gemini_handler is None:
        _gemini_handler = GeminiHandler()
    return _gemini_handler
