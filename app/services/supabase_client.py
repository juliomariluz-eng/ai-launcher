# services/supabase_client.py
import os
import streamlit as st # Necesario si quieres usar st.secrets para despliegue
from supabase import create_client, Client

def supabase() -> Client:
    """Initializes and returns a Supabase client instance."""
    url = os.getenv("SUPABASE_URL")
    # Usar SUPABASE_SERVICE_KEY como has indicado en tu .env
    key = os.getenv("SUPABASE_SERVICE_KEY") 
    
    if not url or not key:
        st.error(
            "Error de configuración: Las variables de entorno 'SUPABASE_URL' y 'SUPABASE_SERVICE_KEY' "
            "deben estar definidas. Verifica tu archivo .env o Streamlit secrets."
        )
        st.stop()
       
    return create_client(url, key)