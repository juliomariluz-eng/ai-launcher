# services/gemini_classifier.py
import os, json
import re
import google.generativeai as genai
# --- CAMBIO CRÍTICO AQUÍ: Cambiar la importación de types.GenerateContentConfig ---
# Ahora importamos GenerationConfig directamente de genai
from google.generativeai import GenerationConfig # <-- Forma correcta para la configuración de generación
from google.api_core.exceptions import GoogleAPIError

# Usar os.getenv para GEMINI_MODEL, que será cargado desde .env
MODEL = os.getenv("MODEL_ID", "gemini-1.5-flash") # Usar MODEL_ID como en Cloud Run, pero con fallback

api_key_value = os.getenv("GEMINI_API_KEY")

if not api_key_value:
    raise ValueError(
        "La variable de entorno 'GEMINI_API_KEY' no se encontró. "
        "Asegúrate de que esté definida en tu archivo .env o en el entorno del sistema."
    )

# --- INICIALIZACIÓN CORRECTA DEL CLIENTE Y MODELO ---
genai.configure(api_key=api_key_value) # Configura la clave API globalmente
model = genai.GenerativeModel(MODEL)   # Obtiene una instancia del modelo específico
# ----------------------------------------------------

SYSTEM = ("Eres un analista de reclamos. Devuelve SOLO JSON con campos: "
          "{'Sentimiento':'positivo|neutral|negativo','Clasificacion':'producto|entrega|servicio|otros'}.")

# Modificamos la firma para poder devolver un segundo valor para el error
def classify_text(texto: str) -> tuple[dict, str]: # Ahora devuelve (resultado_dict, mensaje_error_str)
    if not texto or not texto.strip():
        return {"Sentimiento":"neutral","Clasificacion":"otros"}, ""

    prompt = f"{SYSTEM}\n\nTexto:\n{texto}\n\nDevuelve solo JSON válido."
    
    res = None
    gemini_raw_response = "No se pudo obtener una respuesta raw de Gemini debido a un error previo o un error de la API." 
    error_message_detail = "" 
    
    try:
        # --- CAMBIO CRÍTICO AQUÍ: Usar genai.GenerationConfig ---
        cfg = GenerationConfig( 
            temperature=0, # para respuestas más deterministas
        )

        res = model.generate_content(
            contents=[{"role":"user","parts":[{"text": prompt}]}],
            generation_config=cfg # El parámetro correcto es 'generation_config'
        )
        
        if not res.candidates or not res.candidates[0].content.parts:
            error_message_detail = "Gemini API no devolvió candidatos o el contenido está vacío."
            return {"Sentimiento":"FALLO_GEMINI","Clasificacion":"FALLO_GEMINI"}, error_message_detail

        json_output_raw = res.candidates[0].content.parts[0].text
        
        gemini_raw_response = json_output_raw 

        match = re.search(r"```json\s*(.*?)\s*```", json_output_raw, re.DOTALL)
        if match:
            json_string = match.group(1)
        else:
            json_string = json_output_raw
            
        return json.loads(json_string), "" 
        
    except (GoogleAPIError, ValueError, json.JSONDecodeError) as e:
        error_message_detail = f"Error específico: {e}. Texto problemático: {texto[:100]}... Respuesta RAW: {gemini_raw_response}"
        return {"Sentimiento":"FALLO_GEMINI","Clasificacion":"FALLO_GEMINI"}, error_message_detail
    except Exception as e:
        error_message_detail = f"Error inesperado: {e}. Texto problemático: {texto[:100]}... Respuesta RAW: {gemini_raw_response}"
        return {"Sentimiento":"FALLO_GEMINI","Clasificacion":"FALLO_GEMINI"}, error_message_detail