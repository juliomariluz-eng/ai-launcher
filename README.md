# AI Launcher (n8n + Cloud Functions + Supabase + Streamlit)

Un starter práctico para lanzar flujos de IA de punta a punta: interfaz en **Streamlit**, servicios conectores (Gemini, n8n y Supabase) y endpoints en **Cloud Functions**.

---

## 📦 Estructura del proyecto

```text
ai-launcher/
├─ app/
│  ├─ components/                # (opcional) componentes UI reutilizables
│  ├─ services/                  # wrappers/SDKs internos
│  │  ├─ gemini_classifier.py    # cliente para clasificación / LLM (Gemini)
│  │  ├─ n8n_client.py           # cliente para disparar workflows n8n
│  │  ├─ productvision_client.py # edición/síntesis de imágenes (p. ej. templates)
│  │  └─ supabase_client.py      # lectura/escritura en Supabase
│  ├─ tabs/                      # pantallas (tabs) de Streamlit
│  │  ├─ tab_banner.py           # A) Creación de imágenes promocionales
│  │  ├─ tab_product.py          # B) Generación automática de descripciones
│  │  └─ tab_feedback.py         # C) Resumen de comentarios/feedback
│  └─ main.py                    # entrypoint de Streamlit (router de tabs)
├─ data/
│  ├─ base_images/               # plantillas/base para banners
│  ├─ product_images/            # imágenes de producto
│  └─ sample_comments.csv        # ejemplo de comentarios para pruebas
├─ sql/
│  └─ setup.sql                  # script inicial para tablas en Supabase/PG
├─ .env.example                  # ejemplo de variables de entorno
├─ .env                          # (local) variables reales
├─ requirements.txt
└─ README.md
```

---

## 🚀 Quickstart

### 1) Requisitos

- Python 3.10+
- (Opcional) Cuenta en **Supabase** (Postgres + Storage)
- (Opcional) Instancia de **n8n** con endpoints/webhooks
- (Opcional) Proyecto en **Google Cloud** para Cloud Functions

### 2) Crear y activar entorno virtual

```bash
python -m venv .venv
# Activar:
#  Windows PowerShell
.\.venv\Scripts\Activate.ps1
#  macOS/Linux/Git Bash
source .venv/bin/activate
```

> **Tip (PowerShell):** si aparece error de ejecución de scripts, corre: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 3) Instalar dependencias

```bash
cd .\ai-launcher\
pip install -r requirements.txt
```

### 4) Variables de entorno

1. Copia `.env.example` a `.env` y completa los valores.
2. Variables típicas (ajusta a tu stack):

| Variable                | Descripción                                                  |
| ----------------------- | ------------------------------------------------------------ |
| `GEMINI_API_KEY`        | API key de Google AI (Gemini) para generación/clasificación. |
| `MODEL_ID`              | Modelo por defecto (ej. `gemini-2.5-pro`).                   |
| `SUPABASE_URL`          | URL del proyecto Supabase.                                   |
| `SUPABASE_ANON_KEY`     | Public Anon Key de Supabase.                                 |
| `SUPABASE_SERVICE_ROLE` | (opcional) Service Role para operaciones de backend.         |
| `N8N_WEBHOOK_URL`       | URL del webhook de n8n para flujos automáticos.              |
| `PRODUCTVISION_API_KEY` | (opcional) API key del servicio de imágenes/edición.         |
| `ENV`                   | `local`, `dev` o `prod` (para toggles en la app).            |

**Ejemplo .env**

```env
GEMINI_API_KEY=xxxxx
MODEL_ID=gemini-2.5-pro
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...
N8N_WEBHOOK_URL=https://n8n.tu-dominio.com/webhook/xyz
PRODUCTVISION_API_KEY=
ENV=local
```

### 5) Ejecutar la app

```bash
streamlit run app/main.py
```

---

## 🧭 Navegación general

`app/main.py` levanta una interfaz con **3 módulos** (tabs) principales. Abre el enlace local que te muestre Streamlit y selecciona el tab que necesites.

---

## A) Creación de imágenes promocionales (tab\_banner)

Genera **banners publicitarios** a partir de una **imagen de banner base** y una **imagen de producto**, opcionalmente puedes añadir un **prompt con instrucciones** adicionales.

### Flujo

1. Selecciona o sube una **imagen base** desde `data/base_images/`.
2. Sube una **imagen de producto** desde `data/product_images/`.
3. (Opcional) Añade un **prompt creativo** con instrucciones adicionales (texto deseado, colores, estilo, claims, etc.)
4. Haz clic en **Generar banner**.
5. Obtendrás una **imagen publicitaria lista para ese producto**.

---

## B) Generación automática de descripciones (tab\_product)

Genera **copys y descripciones de producto** optimizadas para ecommerce/marketplaces.

### Requisitos

- Debes subir una **imagen del producto**.
- Debes ingresar un **prompt o descripción con detalles** de lo que se desea generar.

### Flujo

1. Sube la imagen del producto.
2. Escribe un prompt detallando lo que quieres para el copy (tono, estilo, atributos clave).
3. Haz clic en **Generar** y el sistema devolverá:
   - Título
   - Bullets
   - Descripción larga
   - Short copy

---

## C) Resumen de comentarios o feedback (tab\_feedback)

Permite **ver, ingresar y analizar feedback de usuarios en tiempo real**.

### Características

- **Dashboard en tiempo real** con registros y gráficos de los comentarios ingresados.
- Puedes **ingresar comentarios individuales** desde un formulario.
- Puedes **cargar comentarios en lotes** desde un archivo CSV (`data/sample_comments.csv`).
- Hace un **análisis de sentimiento y clasificación temática** de cada comentario y lo almacena en la base de datos.
- Incluye un **Agente Bot de Telegram** donde puedes dejar comentarios directamente. El bot los clasificará y almacenará automáticamente.
  - 📲 URL del chatbot AI: [https://t.me/Reclamos\_insuma\_bot](https://t.me/Reclamos_insuma_bot)

---

## 🧪 Datos de ejemplo

- **Imágenes base:** `data/base_images/`
- **Imágenes de producto:** `data/product_images/`
- **Comentarios:** `data/sample_comments.csv`


---

## Funcionamiento de n8n y cloud run
En la carpeta **informacion_apis** encontrará el detalle de como funcionan y como se contruyeron.