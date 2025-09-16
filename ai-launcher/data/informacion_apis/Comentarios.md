# API Guide — n8n & Cloud Run (AI Launcher)

Este README explica cómo funcionan y cómo consumir las **APIs** que usa tu solución:

- **n8n Webhook API** (módulo **A – Banners**)
- **Cloud Run – LLM Copy API** (módulo **B – Copys**)

> Nota: **Supabase** solo se usa para el **módulo C (Feedback)** como base de datos y storage; no expone API propia en esta guía.

---

## 🧭 Visión general de los flujos

```
[ Usuario ]
   │
   ▼
[ Streamlit UI (A/B/C) ]
   A: Banners   B: Copys   C: Feedback
   │            │
   │            ├─► (POST) Cloud Run – Copy API ─► Gemini ─► Copy JSON
   │            │
   └─► (POST) n8n Webhook API ─► (Capturar → Validar → NanoBanana → Convert to File → GCS) ─► URL imagen
```

---

## 🔑 Autenticación (recomendado)

- **n8n Webhook API**: usar **token** por cabecera (`X-API-KEY: <token>`) o por query string (`?token=<token>`).
- **Cloud Run – Copy API**: usar **Bearer token** en cabecera (`Authorization: Bearer <token>`). Puedes configurar un token simple o emplear IAP/ID tokens si está detrás de autenticación de Google.

> Evita exponer tokens en el front. Cárgalos por variables de entorno del backend o mediante un proxy.

---

## A) n8n Webhook API — Banners

Módulo **A** invoca un **webhook** de n8n que ejecuta tu flujo:

**Flujo (resumen)**

1. **Capturar** (recepción del request)
2. **Validar** (archivos y parámetros)
3. **NanoBanana** (motor/servicio de imagen, según tu setup)
4. **Convert to File** (estandariza formato)
5. **Guardar en GCS** (o el storage que uses)
6. **Devolver URL** del banner generado

### Endpoint

```
POST https://<tu-n8n>/webhook/banner/generate
```

### Request (multipart/form-data)

- `base_image` (file, **requerido**): imagen plantilla
- `product_image` (file, **requerido**): imagen del producto
- `prompt` (string, opcional): instrucciones de texto (slogan, estilo, colores)
- `brand` (string, opcional)
- `X-API-KEY` (header, recomendado)

**Ejemplo cURL**

```bash
curl -X POST "https://n8n.tu-dominio.com/webhook/banner/generate" \
  -H "X-API-KEY: $N8N_TOKEN" \
  -F "base_image=@data/base_images/Base1-banner.jpg" \
  -F "product_image=@data/product_images/Alacena.jpg" \
  -F "prompt=Banner para ecommerce, tono fresco, resalta limón"
```

### Response (200)

```json
{
  "status": "ok",
  "banner_url": "https://storage.googleapis.com/tu-bucket/banners/2025/09/banner_123.png",
  "meta": {
    "workflow_id": "wf_abc123",
    "elapsed_ms": 4230
  }
}
```


## B) Cloud Run – LLM Copy API — Copys

Módulo **B** invoca un **API en Cloud Run** que consume **Gemini** para generar copys.

### Endpoint

```
POST https://<cloud-run-domain>/v1/generate-copy
```

### Request

Se recomienda **multipart/form-data** si envías imagen; alternativamente JSON con URL de imagen.

**multipart/form-data**

- `image` (file, **requerido**): imagen del producto
- `prompt` (string, **requerido**): instrucciones de texto (tono, claims permitidos, etc.)

**JSON (si usas URL en lugar de archivo)**

```json
{
  "image_url": "https://.../producto.jpg",
  "prompt": "Descripción ecommerce, evitar claims médicos, resalta sabor a limón",
  "tone": "informativo",
  "model": "gemini-2.5-pro"
}
```

**Cabeceras**

- `Authorization: Bearer <token>`

**Ejemplo cURL (multipart)**

```bash
curl -X POST "$COPY_API_URL/v1/generate-copy" \
  -H "Authorization: Bearer $COPY_API_TOKEN" \
  -F "image=@data/product_images/Alacena.jpg" \
  -F "prompt=Descripción orientada a ecommerce, evita claims médicos y precios" \
  -F "tone=informativo"
```

### Response (200)

```json
{
  "title": "Mayonesa AlaCena con Toque de Limón",
  "bullets": [
    "Sabor auténtico y cremosidad",
    "Hecha en Perú, ideal para el día a día",
    "Versátil para sándwiches, ensaladas y más"
  ],
  "long_description": "Disfruta de la cremosidad...",
  "short_copy": "El sabor peruano que va con todo.",
  "safety_notes": ["Sin claims sensibles."]
}
```
