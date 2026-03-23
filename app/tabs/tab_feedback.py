# tabs/tab_feedback.py
import secrets, time
from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from services.supabase_client import supabase
from services.gemini_classifier import classify_text # Esto importará la versión correcta del servicio

TABLE_NAME = "reclamos"  # nombre real de tu tabla en Supabase

# ---------- Estilos ----------
def _style():
    """Injects custom CSS for a more branded look and feel."""
    # Se eliminan los estilos específicos para .fab y .chat-panel
    st.markdown("""
    <style>
      :root{ --pri:#0A84FF; --bg:#F7F9FC; --card:#FFFFFF; --border:#E6E9F2; --text:#101828 }
      [data-testid="stAppViewContainer"]{ background:linear-gradient(180deg,var(--bg) 0%, #FFFFFF 100%) }
      .card{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:16px;
             box-shadow:0 10px 30px rgba(16,24,40,.06) }
      .card h3{ margin:0 0 12px 0; color:var(--text) }
      .stButton > button[kind="primary"]{
        width:100%; border:0; border-radius:12px; padding:.8rem 1rem; background:var(--pri); color:#fff; font-weight:700;
        box-shadow:0 8px 18px rgba(10,132,255,.25)
      }
      .chip{ display:inline-block; padding:.2rem .5rem; border-radius:999px; border:1px solid #e5e7ef; background:#f7f9ff; font-size:.75rem; color:#334; }
      textarea[aria-label="Det_reclamo*"] {
          min-height: 100px;
      }
    </style>
    """, unsafe_allow_html=True)

# ---------- IDs/fechas y normalizaciones ----------
def ksid(prefix: str) -> str:
    """Generates a K-Sortable Unique ID (KSUID-like) with a given prefix."""
    epoch_ms = int(time.time() * 1000)
    rand8 = secrets.token_hex(4)
    return f"{prefix}-{epoch_ms:013d}-{rand8}"

def now_utc_iso(x=None) -> str:
    """Returns the current UTC time as an ISO 8601 string, or converts a given timestamp."""
    ts = pd.Timestamp.utcnow() if x is None else pd.to_datetime(x, errors="coerce")
    if ts is pd.NaT: ts = pd.Timestamp.utcnow()
    if ts.tzinfo is None: ts = ts.tz_localize("UTC")
    else: ts = ts.tz_convert("UTC")
    return ts.isoformat()

def format_datetime_for_id(dt_obj: datetime) -> str:
    """Formats a datetime object to 'YYYY-MM-DD_HH:MM:SS' string for Id_reclamo."""
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    else:
        dt_obj = dt_obj.astimezone(timezone.utc)
    return dt_obj.strftime("%Y-%m-%d_%H:%M:%S")

def generate_reclamo_id(dni_val: int | None, fecha_dt: datetime) -> str:
    """
    Generates Id_reclamo using DNI and formatted date (DNI_YYYY-MM-DD_HH:MM:SS).
    Falls back to ksid if DNI is missing or invalid.
    """
    if dni_val is not None and pd.notna(dni_val):
        formatted_fecha = format_datetime_for_id(fecha_dt)
        return f"{dni_val}_{formatted_fecha}"
    else:
        return ksid("R")

def normalize_sent(value: str) -> str:
    """Normalizes sentiment strings to 'positivo', 'neutral', or 'negativo'.
       Also handles "FALLO_GEMINI" to keep it for internal error checking."""
    s = (value or "").strip().lower()
    if s == "fallo_gemini": # Keep "FALLO_GEMINI" as is for error checking
        return "FALLO_GEMINI"
    mapping = {
        "malo": "negativo", "mala": "negativo", "negativo": "negativo",
        "bueno": "positivo", "buena": "positivo", "positivo": "positivo",
        "neutral": "neutral", "neutro": "neutral",
    }
    return mapping.get(s, "neutral")

def ensure_min_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures required columns exist, renames common variations, and auto-generates
    Id_reclamo, Fecha (local only), Id_chat if they are missing or empty.
    The 'Fecha' column will be used for Id_reclamo generation but NOT sent to Supabase.
    This function ensures internal DF columns are 'DNI' and 'Det_reclamo' (capitalized).
    """
    colmap = {
        "id_reclamo":"Id_reclamo", "id":"Id_reclamo", "reclamo_id":"Id_reclamo",
        "id_chat":"Id_chat", "chat_id":"Id_chat",
        "dni":"DNI", "id_cliente":"DNI", "customer_id":"DNI", "documento":"DNI", # Map to 'DNI' (capital)
        "det_reclamo":"Det_reclamo", "descripcion":"Det_reclamo", "comment":"Det_reclamo", "feedback":"Det_reclamo", "mensaje":"Det_reclamo" # Map to 'Det_reclamo' (capital D)
    }
    
    df_columns_lower = {col.lower(): col for col in df.columns}
    rename_dict = {}
    for lower_k, mapped_v in colmap.items():
        if lower_k in df_columns_lower and df_columns_lower[lower_k] != mapped_v:
            rename_dict[df_columns_lower[lower_k]] = mapped_v
    df = df.rename(columns=rename_dict).copy()

    # Ensure all critical columns are present, add with NA if not
    for c in ["Id_reclamo","Id_chat","DNI","Det_reclamo"]:
        if c not in df.columns:
            df[c] = pd.NA

    # Handle 'Fecha_local' for internal Id_reclamo generation
    # If a 'Fecha' or 'fecha' column existed in the CSV, use it to populate 'Fecha_local'.
    # Otherwise, initialize 'Fecha_local' with NA.
    if "Fecha" not in df.columns and "fecha" not in df_columns_lower:
        df["Fecha_local"] = pd.NA
    else:
        if "Fecha" not in df.columns:
            if "fecha" in df_columns_lower:
                df['Fecha_local'] = pd.to_datetime(df[df_columns_lower['fecha']], errors="coerce", utc=True)
            else:
                df["Fecha_local"] = pd.NA
        else:
            df['Fecha_local'] = pd.to_datetime(df["Fecha"], errors="coerce", utc=True)
        # Drop the original 'Fecha' or 'fecha' column(s) if they were loaded from CSV
        if "Fecha" in df.columns:
            df.drop(columns=["Fecha"], inplace=True)
        if "fecha" in df_columns_lower:
            df.drop(columns=[df_columns_lower['fecha']], inplace=True)

    df["DNI"] = pd.to_numeric(df["DNI"], errors="coerce").astype("Int64")
    df["Det_reclamo"] = df["Det_reclamo"].astype(str).fillna("").str.strip()

    miss_chat = df["Id_chat"].isna() | (df["Id_chat"].astype(str).str.strip() == "")
    df.loc[miss_chat, "Id_chat"] = [ksid("CHAT") for _ in range(miss_chat.sum())]

    miss_fecha_local = df["Fecha_local"].isna()
    df.loc[miss_fecha_local, "Fecha_local"] = [pd.Timestamp.utcnow().to_pydatetime() for _ in range(miss_fecha_local.sum())]

    miss_rec = df["Id_reclamo"].isna() | (df["Id_reclamo"].astype(str).str.strip() == "")
    
    df.loc[miss_rec, "Id_reclamo"] = [
        generate_reclamo_id(
            int(dni_val) if pd.notna(dni_val) else None,
            fecha_dt
        )
        for dni_val, fecha_dt in zip(df.loc[miss_rec, "DNI"], df.loc[miss_rec, "Fecha_local"])
    ]

    return df

# ---------- Supabase query ----------
def _fetch_rows(sentiments: list, d_from: datetime.date = None, d_to: datetime.date = None) -> list:
    """Fetches reclamo data from Supabase based on sentiment and date filters."""
    sb = supabase()
    q = sb.table(TABLE_NAME).select("*")
    if sentiments:
        q = q.in_("Sentimiento", sentiments)
    if d_from:
        q = q.gte("Fecha", now_utc_iso(d_from))
    if d_to:
        d_to_inc = (pd.to_datetime(d_to) + pd.Timedelta(days=1)).isoformat()
        q = q.lt("Fecha", d_to_inc)
    return q.order("Fecha", desc=True).execute().data

# ---------- UI ----------
def render():
    """Renders the feedback insights dashboard and CSV upload/classification interface."""
    _style()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>C) Feedback Insights</h3>", unsafe_allow_html=True)
    st.caption("CSV → clasificar con Gemini → **autogenerar** Id_reclamo/Fecha_local/Id_chat → guardar en Supabase (Fecha autogenerada por Supabase) → dashboard en vivo.")

    # Filtros + autorefresco
    c1, c2, c3, c4 = st.columns([1,1,1,1]) 
    with c1:
        senti_filter = st.multiselect("Filtrar Sentimiento", ["positivo","neutral","negativo"],
                                      default=["positivo","negativo","neutral"])
    with c2:
        default_from = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        d_from = st.date_input("Desde", value=default_from)
    with c3:
        d_to = st.date_input("Hasta", value=datetime.now(timezone.utc).date())
    with c4:
        auto = st.toggle("🔄 Auto-actualizar", value=False, help="Refresca cada 5 s el dashboard.")
    if auto:
        st_autorefresh(interval=5000, key="feedback_autorefresh")

    # Carga CSV + clasificación
    st.markdown("### Cargar CSV y clasificar")
    st.caption("Mínimo requerido: **DNI**, **Det_reclamo**")
    
    if 'csv_uploader_key' not in st.session_state:
        st.session_state['csv_uploader_key'] = 0
    
    csv_file = st.file_uploader(
        "CSV de comentarios", 
        type=["csv"], 
        label_visibility="collapsed", 
        key=f"csv_uploader_{st.session_state['csv_uploader_key']}"
    )
    
    b1, b2 = st.columns(2) 
    subir  = b1.button("Cargar y clasificar en Supabase", type="primary", use_container_width=True, disabled=csv_file is None)
    limpiar = b2.button("Limpiar selección", use_container_width=True)
    
    if limpiar:
        st.session_state['csv_uploader_key'] += 1
        st.rerun()

    if csv_file is not None and subir:
        with st.spinner("Cargando y clasificando datos con Gemini... Esto puede tardar unos minutos para archivos grandes."):
            try:
                df = pd.read_csv(csv_file)
                df = ensure_min_columns(df) 

                if "Det_reclamo" not in df.columns or df["Det_reclamo"].isnull().all():
                    st.error("La columna 'Det_reclamo' es requerida y no se encontró o está completamente vacía en tu CSV. "
                             "Asegúrate de que tu CSV contenga una columna con el detalle de los reclamos.")
                    st.stop()

                bar = st.progress(0, text="Clasificando reclamos...")
                preds = []
                failed_classifications_details = [] 
                total_reclamos = len(df)
                for i, txt in enumerate(df["Det_reclamo"].tolist()):
                    pred_result, error_detail = classify_text(txt) 
                    preds.append(pred_result)
                    if pred_result.get("Sentimiento") == "FALLO_GEMINI":
                        failed_classifications_details.append(f"Reclamo '{txt[:70]}...' falló: {error_detail}")
                    bar.progress(int((i + 1) * 100 / total_reclamos), text=f"Clasificando reclamo {i+1} de {total_reclamos}...")
                bar.empty()

                pred_df = pd.DataFrame(preds)
                df["Sentimiento"]  = pred_df["Sentimiento"].map(normalize_sent) 
                df["Clasificacion"] = pred_df["Clasificacion"].fillna("otros")
                
                df_successful = df[df["Sentimiento"] != "FALLO_GEMINI"].copy()

                if df_successful.empty:
                    st.warning("No se pudieron clasificar ni guardar reclamos exitosamente. Revisa los detalles de los errores a continuación.")
                    if failed_classifications_details:
                        st.subheader("Detalles de las clasificaciones fallidas:")
                        for detail in failed_classifications_details:
                            st.error(detail) 
                else:
                    df_to_supabase = df_successful.copy()
                    
                    if 'Fecha_local' in df_to_supabase.columns:
                        df_to_supabase.drop(columns=['Fecha_local'], inplace=True)
                    
                    supabase().table(TABLE_NAME).upsert(
                        df_to_supabase.to_dict(orient="records"),
                        on_conflict="Id_reclamo"
                    ).execute()
                    st.toast(f"✅ ¡Éxito! Insertados/actualizados {len(df_to_supabase)} reclamos.")
                    
                    failed_count = len(df) - len(df_successful)
                    if failed_count > 0:
                        st.error(f"❌ Fallaron {failed_count} clasificaciones de Gemini y no fueron guardadas.")
                        if failed_classifications_details:
                            st.subheader("Detalles de las clasificaciones fallidas:")
                            with st.expander(f"Mostrar detalles de {failed_count} reclamos fallidos"):
                                for detail in failed_classifications_details:
                                    st.error(detail) 
                    
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error procesando/guardando CSV: {e}")
                st.exception(e)

    st.markdown("</div>", unsafe_allow_html=True)

    # --- Sección de Formulario de "Nuevo Reclamo" integrada aquí ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>Nuevo Reclamo</h3>", unsafe_allow_html=True)
    st.caption("Ingresa un reclamo manualmente. Id_reclamo / Id_chat se generan automáticamente. Fecha por Supabase.")

    with st.form("new_claim_form", clear_on_submit=True): # Cambié el nombre del form para evitar conflictos si se reutiliza "chat_form"
        c1, c2 = st.columns(2)
        with c1:
            dni = st.text_input("DNI", placeholder="12345678", key="new_claim_dni_input")
        with c2:
            st.empty() # Placeholder para mantener el layout si no hay nada más en esta columna

        det = st.text_area("Det_reclamo*", placeholder="Describe el reclamo del cliente...", height=100, key="new_claim_det_reclamo_input")
        
        send_manual = st.form_submit_button("Clasificar y guardar", use_container_width=True, type="primary")

    if send_manual:
        if not det.strip():
            st.warning("Completa **Det_reclamo** para clasificar el reclamo.")
        else:
            with st.spinner("Clasificando y guardando reclamo..."):
                try:
                    dni_val = None
                    if dni and dni.strip():
                        if dni.strip().isdigit():
                            dni_val = int(dni.strip())
                        else:
                            st.warning("El DNI debe ser un número entero válido.")
                            st.stop()
                    
                    current_datetime_utc = pd.Timestamp.utcnow().to_pydatetime()

                    pred, error_detail = classify_text(det.strip()) 
                    
                    if pred.get("Sentimiento") == "FALLO_GEMINI" or pred.get("Clasificacion") == "FALLO_GEMINI":
                        st.error(f"❌ Falló la clasificación del texto con Gemini. El reclamo no se guardó. Detalle: {error_detail}") 
                        st.stop() 

                    row = {
                        "Id_reclamo": generate_reclamo_id(dni_val, current_datetime_utc),
                        "Id_chat": ksid("CHAT"), # Aquí podrías cambiar a un ID más específico si el formulario manual no es "chat"
                        "DNI": dni_val, 
                        "Det_reclamo": det.strip(), 
                        "Sentimiento": normalize_sent(pred.get("Sentimiento")),
                        "Clasificacion": pred.get("Clasificacion", "otros"),
                    }
                    supabase().table(TABLE_NAME).upsert(row, on_conflict="Id_reclamo").execute()
                    st.toast("✅ ¡Reclamo guardado correctamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error guardando reclamo: {e}")
                    st.exception(e)
    st.markdown("</div>", unsafe_allow_html=True) # Cierra la card del nuevo reclamo

    # Dashboard
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>Dashboard</h3>", unsafe_allow_html=True)
    try:
        rows = _fetch_rows(senti_filter, d_from, d_to)
        if rows:
            dv = pd.DataFrame(rows)
            
            if 'Fecha' in dv.columns:
                dv["Fecha"] = pd.to_datetime(dv["Fecha"], utc=True)
                dv["dia"] = dv["Fecha"].dt.date
            else:
                dv["Fecha"] = pd.Timestamp.utcnow() 
                dv["dia"] = dv["Fecha"].dt.date
                st.warning("La columna 'Fecha' no se encontró en los datos de Supabase. Mostrando fecha actual.")

            # Métricas
            m1, m2, m3 = st.columns(3)
            m1.metric("Total comentarios", len(dv))
            m2.metric("Positivos", int((dv["Sentimiento"] == "positivo").sum()))
            m3.metric("Negativos", int((dv["Sentimiento"] == "negativo").sum()))

            st.markdown("---")
            st.subheader("Distribución de Sentimientos")
            sent_counts = dv["Sentimiento"].value_counts().reset_index()
            sent_counts.columns = ["Sentimiento", "count"]
            pie = alt.Chart(sent_counts).mark_arc(innerRadius=40).encode(
                theta=alt.Theta("count", stack=True),
                color=alt.Color("Sentimiento", legend=alt.Legend(title="Sentimiento")),
                order=alt.Order("count", sort="descending"),
                tooltip=["Sentimiento","count"]
            ).properties(title="Comentarios por Sentimiento")
            st.altair_chart(pie, use_container_width=True)

            st.subheader("Tendencia Diaria de Reclamos")
            daily = dv.groupby("dia", as_index=False)["Id_reclamo"].count()
            area = alt.Chart(daily).mark_area(opacity=0.6, line=True).encode(
                x=alt.X("dia:T", title="Fecha"), 
                y=alt.Y("Id_reclamo:Q", title="Cantidad de Reclamos"), 
                tooltip=[alt.Tooltip("dia:T", title="Fecha"), alt.Tooltip("Id_reclamo:Q", title="Cantidad")]
            ).properties(title="Tendencia Diaria de Reclamos")
            st.altair_chart(area, use_container_width=True)

            st.subheader("Clasificación por Sentimiento")
            cls_sent = dv.groupby(["Clasificacion","Sentimiento"], as_index=False).size().rename(columns={'size': 'Count'})
            stacked = alt.Chart(cls_sent).mark_bar().encode(
                x=alt.X("Clasificacion:N", sort="-y", title="Clasificación"),
                y=alt.Y("Count:Q", title="Cantidad"),
                color=alt.Color("Sentimiento:N", legend=alt.Legend(title="Sentimiento")),
                tooltip=["Clasificacion","Sentimiento","Count"]
            ).properties(title="Distribución de Clasificaciones por Sentimiento").interactive()
            st.altair_chart(stacked, use_container_width=True)

            st.subheader("Mapa de Calor: Reclamos por Día y Clasificación")
            heat_data = dv.groupby(["dia","Clasificacion"], as_index=False).size().rename(columns={'size': 'Count'})
            heat = alt.Chart(heat_data).mark_rect().encode(
                x=alt.X("dia:T", title="Fecha"), 
                y=alt.Y("Clasificacion:N", title="Clasificación"),
                color=alt.Color("Count:Q", title="Cantidad", scale=alt.Scale(range="heatmap")),
                tooltip=[alt.Tooltip("dia:T", title="Fecha"), "Clasificacion:N", alt.Tooltip("Count:Q", title="Cantidad")]
            ).properties(title="Cantidad de Reclamos por Día y Clasificación").interactive()
            st.altair_chart(heat, use_container_width=True)

            st.markdown("### Tabla de Reclamos")
            st.dataframe(
                dv[["Fecha","Det_reclamo","Sentimiento","Clasificacion","DNI","Id_chat","Id_reclamo"]]
                  .sort_values("Fecha", ascending=False),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Sin datos para los filtros actuales. Prueba a cargar un CSV o ajusta los filtros de fecha/sentimiento.")
    except Exception as e:
        st.error(f"❌ Error consultando Supabase o generando gráficos: {e}")
        st.exception(e)
    st.markdown("</div>", unsafe_allow_html=True)