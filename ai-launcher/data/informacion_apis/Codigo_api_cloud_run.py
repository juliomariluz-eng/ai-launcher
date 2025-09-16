import functions_framework
import json, os, base64, logging, re
from typing import Optional
from google import genai
from google.genai import types  # <-- necesario para GenerateContentConfig

logging.basicConfig(level=logging.INFO)

# ===== Config =====
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']='AIzaSyDYtBwqjN_2gm_7UY2rg1gBS7RixhIiAxc'
MODEL_ID = os.getenv("MODEL_ID", "gemini-2.5-pro")
client = genai.Client(api_key=GEMINI_API_KEY)

# CORS: usa "*" o lista blanca (ej. "http://localhost:5173,https://mi-front.com")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
ALLOW_CREDENTIALS = os.getenv("ALLOW_CREDENTIALS", "false").lower() == "true"

# Prompt base fijo (instrucciones generales) + regla de salida estricta
PROMPT_BASE = (
    "Eres un redactor publicitario experto en ecommerce y marketplaces. "
    "Analiza la imagen del producto y redacta SOLO EL TEXTO del copy listo para publicar. "
    "No inventes especificaciones que no estén en la imagen o en el texto del usuario. "
    "Evita precios, links y claims sensibles. "
    "Devuelve ÚNICAMENTE un objeto JSON válido con esta forma EXACTA (sin texto adicional ni bloques de código):\n"
    "{\n"
    '  "title": "string",\n'
    '  "bullets": ["string","string","string","string","string"],\n'
    '  "description_short": "string",\n'
    '  "description_long": "string"\n'
    "}\n"
    "Bullets escaneables, beneficios claros, lenguaje natural. Idioma: español."
)

# ===== Utilidades =====
def _detect_mime(b64: str) -> str:
    if b64.startswith("data:"):
        return b64.split(";")[0].split(":")[1]
    return "image/png"

def _strip_data_url(b64: str) -> str:
    return b64.split(",")[1] if b64.startswith("data:") else b64

def _extract_json(text: str) -> dict:
    # Intenta JSON puro; si viene con ```json ... ```, extrae el primer {...}
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))

def _cors_headers(origin: str | None = None):
    allow_origin = "*"
    if ALLOWED_ORIGINS != "*":
        allowlist = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
        allow_origin = origin if origin in allowlist else "null"
    headers = {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "3600",
    }
    if ALLOW_CREDENTIALS:
        headers["Access-Control-Allow-Credentials"] = "true"
    return headers

# ===== Core =====
def generar_copy(image_b64: str, prompt_extra: Optional[str] = None) -> dict:
    try:
        if not GEMINI_API_KEY:
            return {"status": "failed", "error": "Falta GEMINI_API_KEY en variables de entorno."}

        # Imagen como inline_data base64 + mime_type
        mime = _detect_mime(image_b64)
        raw_bytes = base64.b64decode(_strip_data_url(image_b64))
        raw_b64_for_api = base64.b64encode(raw_bytes).decode("utf-8")
        image_part = {"inline_data": {"mime_type": mime, "data": raw_b64_for_api}}

        user_text = (prompt_extra or "").strip()
        full_prompt = f"{PROMPT_BASE}\n\nPrompt complementario del usuario:\n{user_text}"

        # <-- Cambio clave: usar 'config=types.GenerateContentConfig(...)'
        resp = client.models.generate_content(
            model=MODEL_ID,
            contents=[image_part, full_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        text = (resp.text or "").strip()
        if not text:
            return {"status": "failed", "error": "El modelo no devolvió texto."}

        as_json = _extract_json(text)
        return {"status": "ok", "copy": as_json}

    except Exception as e:
        logging.exception("Error generando copy")
        return {"status": "failed", "error": str(e)}

# ===== HTTP Entrypoint =====
@functions_framework.http
def hello_http(request):
    # 1) Preflight CORS
    if request.method == "OPTIONS":
        return ("", 204, _cors_headers(request.headers.get("Origin")))

    # 2) POST normal
    try:
        data = request.get_json(silent=True) or {}
        img = data.get("image_base64")
        prompt_extra = data.get("prompt_extra")

        if not img or not prompt_extra:
            return (
                json.dumps({"status":"failed","error":"Faltan 'image_base64' y/o 'prompt_extra'."}, ensure_ascii=False),
                400,
                {**_cors_headers(request.headers.get("Origin")), "Content-Type":"application/json"}
            )

        result = generar_copy(img, prompt_extra)
        code = 200 if result.get("status") == "ok" else 400
        return (
            json.dumps(result, ensure_ascii=False),
            code,
            {**_cors_headers(request.headers.get("Origin")), "Content-Type":"application/json"}
        )

    except Exception as e:
        logging.exception("Error en request")
        return (
            json.dumps({"status":"failed","error":str(e)}, ensure_ascii=False),
            500,
            {**_cors_headers(request.headers.get("Origin")), "Content-Type":"application/json"}
        )
