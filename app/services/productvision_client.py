import os, base64, json, requests
from typing import Optional

CF_DESCRIBE_URL = os.getenv("CF_DESCRIBE_URL", "")

class ProductVisionError(Exception):
    pass

def _to_data_url(image_bytes: bytes, mime: Optional[str]) -> str:
    """Convierte bytes -> dataURL como hace tu HTML (incluye prefijo)."""
    mime = (mime or "image/jpeg").strip() or "image/jpeg"
    b64 = base64.b64encode(image_bytes or b"").decode("utf-8")
    return f"data:{mime};base64,{b64}"

def describe_product_base64(
    image_bytes: bytes,
    prompt_extra: str = "",
    *,
    mime: Optional[str] = None,
    endpoint: Optional[str] = None,
    timeout: int = 60,
) -> dict:
    """POST { image_base64, prompt_extra } -> dict."""
    url = (endpoint or CF_DESCRIBE_URL).strip()
    if not url:
        raise ProductVisionError("Falta CF_DESCRIBE_URL o endpoint override.")
    payload = {
        "image_base64": _to_data_url(image_bytes, mime),
        "prompt_extra": prompt_extra or "",
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        text = r.text
        r.raise_for_status()
    except requests.RequestException as e:
        raise ProductVisionError(f"Error invocando ProductVision: {e}") from e

    try:
        return r.json()
    except Exception:
        try:
            return json.loads(text)
        except Exception:
            return {"raw": text}  # fallback


def describe_product(image_url: str, desc_basica: str | None = None) -> dict:
    url = (CF_DESCRIBE_URL or "").strip()
    if not url:
        raise ProductVisionError("Falta CF_DESCRIBE_URL.")
    payload = {"image_url": image_url, "desc_basica": desc_basica}
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()
