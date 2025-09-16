import os
import base64
import json
import re
from typing import Optional, Tuple
import requests

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")          # Webhook principal (POST)
N8N_STATUS_URL  = os.getenv("N8N_STATUS_URL", "").strip()  # Endpoint GET/POST status?job_id=... (opcional)

class N8NClientError(Exception):
    pass

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", re.I)

def _b64(b: bytes) -> str:
    return base64.b64encode(b or b"").decode("utf-8")

def _looks_like_json(text: str) -> bool:
    t = (text or "").strip()
    return (t.startswith("{") and t.endswith("}")) or (t.startswith("[") and t.endswith("]"))

def _extract_url_from_json(obj) -> Optional[str]:
    if obj is None: return None
    if isinstance(obj, str):
        m = _URL_RE.search(obj);  return m.group(0) if m else None
    if isinstance(obj, dict):
        for k in ["banner_url","url_final","final_url","url","image_url","result_url"]:
            if k in obj:
                u = _extract_url_from_json(obj[k])
                if u: return u
        for v in obj.values():
            u = _extract_url_from_json(v)
            if u: return u
    if isinstance(obj, list):
        for it in obj:
            u = _extract_url_from_json(it)
            if u: return u
    return None

def _extract_url_from_text(text: str) -> Optional[str]:
    m = _URL_RE.search(text or "")
    return m.group(0) if m else None

def _extract_job_id(obj_or_text) -> Optional[str]:
    """Busca job_id en JSON ('job_id','executionId','execution_id','id') o UUID en texto."""
    if isinstance(obj_or_text, (dict, list, str)) and not isinstance(obj_or_text, bytes):
        try:
            obj = obj_or_text if not isinstance(obj_or_text, str) else json.loads(obj_or_text)
        except Exception:
            obj = obj_or_text
    else:
        obj = obj_or_text

    # JSON
    if isinstance(obj, dict):
        for k in ["job_id","executionId","execution_id","id"]:
            v = obj.get(k)
            if isinstance(v, str) and _UUID_RE.search(v):
                return _UUID_RE.search(v).group(0)
    # Texto
    if isinstance(obj_or_text, str):
        m = _UUID_RE.search(obj_or_text)
        if m: return m.group(0)
    return None

# ---------- 1) Modo síncrono: espera banner_url (requiere que el flujo termine <~100s) ----------
def create_banner_with_two_images(*, image1_bytes: bytes, image2_bytes: bytes, prompt: str, timeout: int = 220) -> str:
    if not N8N_WEBHOOK_URL:
        raise N8NClientError("Falta N8N_WEBHOOK_URL en entorno.")
    if not image1_bytes or not image2_bytes:
        raise N8NClientError("Ambas imágenes son obligatorias.")

    files = {
        "image1_base64": (None, _b64(image1_bytes)),
        "image2_base64": (None, _b64(image2_bytes)),
        "prompt":        (None, (prompt or "").strip()),
    }
    try:
        resp = requests.post(N8N_WEBHOOK_URL, files=files, timeout=timeout)
        ct = (resp.headers.get("content-type") or "").lower()
        text = resp.text
        resp.raise_for_status()
    except requests.HTTPError:
        raise N8NClientError(f"HTTP {resp.status_code} desde n8n. Cuerpo: {text[:400]}")
    except requests.RequestException as e:
        raise N8NClientError(f"Error de red llamando a n8n: {e}") from e

    if "application/json" in ct:
        try:
            payload = resp.json()
            url = _extract_url_from_json(payload)
            if url: return url
        except Exception:
            pass
    if _looks_like_json(text):
        try:
            url = _extract_url_from_json(json.loads(text))
            if url: return url
        except Exception:
            pass
    url = _extract_url_from_text(text)
    if not url:
        raise N8NClientError("No se encontró URL en la respuesta del Webhook.")
    return url

# ---------- 2) Modo asíncrono: devuelve job_id rápidamente ----------
def start_banner_job(*, image1_bytes: bytes, image2_bytes: bytes, prompt: str, timeout: int = 120) -> str:
    """
    Usa el mismo Webhook pero asumiendo que tu flujo responde de inmediato con {job_id: "..."}.
    """
    if not N8N_WEBHOOK_URL:
        raise N8NClientError("Falta N8N_WEBHOOK_URL en entorno.")
    files = {
        "image1_base64": (None, _b64(image1_bytes)),
        "image2_base64": (None, _b64(image2_bytes)),
        "prompt":        (None, (prompt or "").strip()),
        # si tu flujo distingue 'inmediato', puedes agregar banderas aquí
        # "respond_immediately": (None, "1"),
    }
    try:
        resp = requests.post(N8N_WEBHOOK_URL, files=files, timeout=timeout)
        text = resp.text
        ct = (resp.headers.get("content-type") or "").lower()
        resp.raise_for_status()
    except requests.RequestException as e:
        raise N8NClientError(f"Error iniciando job en n8n: {e}") from e

    job_id = None
    if "application/json" in ct:
        try:
            payload = resp.json()
            job_id = _extract_job_id(payload)
        except Exception:
            pass
    if not job_id:
        # quizá devolvió texto/HTML con el id
        job_id = _extract_job_id(text)
    if not job_id:
        raise N8NClientError(f"No se pudo extraer job_id. Respuesta: {text[:200]}")
    return job_id

# ---------- 3) Consultar estado (endpoint en n8n o lo que configures) ----------
def fetch_status(job_id: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str]]:
    """
    Devuelve (status, banner_url) si N8N_STATUS_URL está configurado y responde.
    Espera un JSON tipo: {"status":"queued|processing|done|error", "banner_url":"https://..."}.
    """
    if not N8N_STATUS_URL:
        return None, None
    try:
        # GET ?job_id=... (o POST, cambia si tu endpoint lo requiere)
        r = requests.get(N8N_STATUS_URL, params={"job_id": job_id}, timeout=timeout)
        r.raise_for_status()
        data = r.json() if "json" in (r.headers.get("content-type") or "") else {}
        status = (data or {}).get("status")
        url = (data or {}).get("banner_url")
        return status, url
    except Exception:
        return None, None
