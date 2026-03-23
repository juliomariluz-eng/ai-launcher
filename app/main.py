# main.py
import os
from dotenv import load_dotenv

# Esta llamada debe ser la primera acción de tu script
load_dotenv()


import json, requests, pandas as pd
import streamlit as st
from datetime import date

# Importar tus pestañas
from tabs.tab_banner import render as render_banner_tab
from tabs.tab_product import render as render_product_tab
from tabs.tab_feedback import render as render_feedback_tab

# Importar tus servicios
from services.n8n_client import create_banner_with_two_images
from services.productvision_client import describe_product
from services.supabase_client import supabase
from services.gemini_classifier import classify_text

# app/main.py (al inicio del archivo)
from io import BytesIO
import requests
from PIL import Image
import streamlit as st

# Logo oficial que pasaste
LOGO_URL = "https://logolook.net/wp-content/uploads/2021/01/Alicorp-Emblem.png"

# Configuración inicial de la página
st.set_page_config(
    page_title="OptiCore",
    page_icon=LOGO_URL,  
    layout="wide",
)

# --- Alicorp Color Palette & Logo ---
ALICORP_RED = "#FF3233"    # Rojo: RGB 255 50 51
ALICORP_GREEN = "#78B928"  # Verde: RGB 120 185 40
ALICORP_GREY = "#E2E5E4"   # Gris: RGB 226 229 228
ALICORP_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Alicorp.svg/2560px-Alicorp.svg.png"
APP_TITLE_TEXT = " Optimiza el corazón de tus operaciones"

# Custom CSS para aplicar la paleta de colores y el estilo deseado
st.markdown(f"""
    <style>
        /* Define CSS Variables for Alicorp colors */
        :root {{
            --alicorp-red: {ALICORP_RED};
            --alicorp-green: {ALICORP_GREEN};
            --alicorp-grey: {ALICORP_GREY};
            --text-dark: #333333;
            --text-light: #ffffff;
            --background-light: #f0f2f6; /* Fondo Streamlit un poco más claro */
            --background-card: #ffffff; /* Fondo para elementos tipo "card" */
        }}

        /* Asegurar que el fondo de la aplicación sea el deseado */
        .stApp {{
            background-color: var(--background-light);
            color: var(--text-dark);
        }}

        /* Estilo para el contenedor de la cabecera (logo + título) */
        .custom-header-section {{
            display: flex;
            align-items: center;
            margin-bottom: 0.5rem; /* Espacio antes de la línea divisoria */
            padding-left: 0.5rem; /* Pequeño padding para el logo desde el borde */
        }}
        .custom-header-section img {{
            height: 50px; /* Ajusta la altura del logo */
            margin-right: 15px;
            object-fit: contain; /* Asegura que la imagen se ajuste sin distorsión */
        }}
        .custom-header-section h1 {{
            font-size: 2.2em; /* Tamaño del título */
            font-weight: bold;
            color: var(--text-dark); 
            margin: 0; /* Elimina márgenes por defecto del h1 */
            line-height: 1.2;
        }}

        /* Línea horizontal roja debajo de la cabecera */
        .alicorp-hr {{
            height: 2px;
            border: none;
            background-color: var(--alicorp-red);
            margin-top: 0; /* Para pegarla al título */
            margin-bottom: 1.5rem; /* Espacio antes de las pestañas */
        }}

        /* General Streamlit element styling */
        .stButton > button {{
            background-color: var(--alicorp-red);
            color: var(--text-light);
            border-radius: 8px;
            border: none;
            padding: 10px 20px;
            font-weight: bold;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); /* Sombra suave para los botones */
        }}
        .stButton > button:hover {{
            background-color: #e62e2e; /* Rojo ligeramente más oscuro al pasar el ratón */
        }}

        /* Multi-select borders */
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] {{
            border-color: var(--alicorp-grey) !important; /* Borde gris para los selects */
            border-radius: 8px;
        }}
        div[data-testid="stMultiSelect"] div[data-baseweb="select"]:hover {{
            border-color: var(--alicorp-red) !important; /* Resaltar en rojo al pasar el ratón */
        }}


        /* Tabs Styling */
        div[data-testid="stTabs"] div[data-testid="stTabList"] button {{
            background-color: var(--alicorp-grey);
            color: var(--text-dark);
            border-radius: 8px 8px 0 0;
            margin-right: 5px;
            padding: 10px 15px;
            border: 1px solid var(--alicorp-grey); 
            border-bottom: none; 
            font-weight: bold;
            transition: all 0.2s ease-in-out; /* Transición suave */
        }}
        div[data-testid="stTabs"] div[data-testid="stTabList"] button:hover {{
            background-color: #d1d4d2; /* Gris ligeramente más oscuro al pasar el ratón */
        }}
        div[data-testid="stTabs"] div[data-testid="stTabList"] button[aria-selected="true"] {{
            background-color: var(--alicorp-red);
            color: var(--text-light);
            border-color: var(--alicorp-red); /* El borde se mezcla con el fondo de la pestaña seleccionada */
            border-bottom-color: var(--alicorp-red); 
        }}
        div[data-testid="stTabs"] div[data-testid="stTabItem"] {{
            background-color: var(--background-card); /* Contenido de las pestañas en blanco */
            padding: 20px;
            border: 1px solid var(--alicorp-grey); /* Borde suave para el contenido */
            border-radius: 0 8px 8px 8px; 
            margin-top: -1px; /* Para que el borde de la pestaña seleccionada se vea continuo */
            box-shadow: 0 4px 12px rgba(0,0,0,0.08); /* Sombra para el contenido de la pestaña */
        }}
        
        /* Asegura que el contenedor principal del contenido no tenga un padding excesivo en la parte superior */
        .block-container {{
            padding-top: 1rem;
        }}

        /* --- CSS EXTREMADAMENTE AGRESIVO PARA OCULTAR EL TOOLBAR NATIVO DE STREAMLIT --- */
        /* Esto debería ocultar la cabecera nativa, incluyendo el botón de Deploy y el menú de 3 puntos. */
        header[data-testid="stToolbar"] {{
            display: none !important;
            height: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important; /* Desactiva interacción con el mouse */
        }}
        /* También intenta ocultar si usa otro data-testid para la app header */
        [data-testid="stAppHeader"] {{
            display: none !important;
            height: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}
        /* A veces hay un padding superior en el cuerpo de la app que también puede causar la franja */
        .stApp > header {{
            display: none !important;
            height: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}


    </style>
""", unsafe_allow_html=True)

# --- Cabecera personalizada con Logo y Título ---
st.markdown(f"""
    <div class="custom-header-section">
        <img src="{ALICORP_LOGO_URL}" alt="Alicorp Logo">
        <h1>{APP_TITLE_TEXT}</h1>
    </div>
""", unsafe_allow_html=True)

# --- Línea divisoria roja ---
st.markdown("<div class='alicorp-hr'></div>", unsafe_allow_html=True)


tabA, tabB, tabC = st.tabs(["A) Creación de imágenes promocionales", "B) Generación automática de descripciones", "C) Resumen de comentarios o feedback"])

# ---------- TAB A ----------
with tabA:
    render_banner_tab() 

# ---------- TAB B ----------
with tabB:
    render_product_tab()

# ---------- TAB C ----------
with tabC:
    render_feedback_tab()