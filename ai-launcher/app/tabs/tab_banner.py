import time, io, requests, streamlit as st
from services.n8n_client import (
    create_banner_with_two_images, start_banner_job, fetch_status, N8NClientError
)

def _file_card(title: str, b: bytes, key_prefix: str):
    """Mini-card: thumb + nombre + tamaño + botón Cambiar."""
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(io.BytesIO(b), use_container_width=True)
    with col2:
        kb = len(b)/1024
        st.caption(title)
        st.caption(f"{kb:,.1f} KB")
        if st.button("Cambiar", key=f"{key_prefix}_change"):
            # borramos del estado para que reaparezca el uploader
            st.session_state.pop(f"{key_prefix}_bytes", None)
            st.rerun()

def render():
    # ===== estilos suaves =====
    st.markdown("""
    <style>
      :root{ --pri:#0A84FF; --bg:#F7F9FC; --card:#FFFFFF; --border:#E6E9F2; --text:#101828; }
      [data-testid="stAppViewContainer"]{ background: linear-gradient(180deg,var(--bg) 0%, #FFFFFF 100%); }
      .card{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 10px 30px rgba(16,24,40,.06); }
      .card h3{ margin:0 0 12px 0; color:var(--text) }
      /* dropzone solo visible si no hay archivo */
      #upload-scope [data-testid="stFileUploadDropzone"]{
        border:2px dashed #d7ddea !important; border-radius:14px; min-height:220px;
        background:repeating-linear-gradient(45deg,#fafcff,#fafcff 12px,#f3f6fb 12px,#f3f6fb 24px);
        display:flex;align-items:center;justify-content:center;
      }
      #upload-scope [data-testid="stFileUploadDropzone"] > div{ text-align:center;color:#8A94A6;font-weight:500; }
      .result-ph{
        border:2px dashed #d7ddea; border-radius:14px; min-height:520px;
        background:repeating-linear-gradient(45deg,#fafcff,#fafcff 12px,#f3f6fb 12px,#f3f6fb 24px);
        display:flex;align-items:center;justify-content:center;color:#8A94A6;
      }
      .stButton > button[kind="primary"]{
        width:100%; border:0; border-radius:12px; padding:.8rem 1rem; background:var(--pri); color:#fff; font-weight:700;
        box-shadow:0 8px 18px rgba(10,132,255,.25);
      }
    </style>
    """, unsafe_allow_html=True)

    # ===== estado =====
    st.session_state.setdefault("banner_result_url", None)
    st.session_state.setdefault("last_job_id", None)

    left, right = st.columns([1,1], vertical_alignment="top")

    # ===== izquierda: entradas (oculta dropzone si ya hay imagen) =====
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>Entradas</h3>", unsafe_allow_html=True)

        st.markdown('<div id="upload-scope">', unsafe_allow_html=True)
        c1, c2 = st.columns(2, vertical_alignment="top")

        # -------- Imagen 1
        with c1:
            st.caption("Imagen 1 (Banner)")
            if "img1_bytes" in st.session_state and st.session_state["img1_bytes"]:
                _file_card("Imagen 1", st.session_state["img1_bytes"], "img1")
            else:
                up1 = st.file_uploader(" ", type=["png","jpg","jpeg"], label_visibility="collapsed", key="upl1",
                                       help="Haz clic o suelta el archivo aquí (hasta ~200MB).")
                if up1 is not None:
                    st.session_state["img1_bytes"] = up1.getvalue()
                    st.rerun()

        # -------- Imagen 2
        with c2:
            st.caption("Imagen 2 (Producto)")
            if "img2_bytes" in st.session_state and st.session_state["img2_bytes"]:
                _file_card("Imagen 2", st.session_state["img2_bytes"], "img2")
            else:
                up2 = st.file_uploader(" ", type=["png","jpg","jpeg"], label_visibility="collapsed", key="upl2")
                if up2 is not None:
                    st.session_state["img2_bytes"] = up2.getvalue()
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        adv = st.toggle("Personalizar descripción")
        prompt = st.text_area("Prompt Personalizado",
                              value="",
                              height=110, disabled=not adv) if adv else "default"

        with st.form("banner_form_upload", clear_on_submit=False):
            cA, cB = st.columns([1,1])
            gen = cA.form_submit_button("Generar", use_container_width=True)
            clr = cB.form_submit_button("Limpiar", use_container_width=True)

        if clr:
            for k in ("img1_bytes","img2_bytes","banner_result_url","last_job_id"):
                st.session_state.pop(k, None)
            st.rerun()

        if gen:
            img1 = st.session_state.get("img1_bytes")
            img2 = st.session_state.get("img2_bytes")
            if not img1 or not img2:
                st.warning("Sube **ambas** imágenes.")
            else:
                # 1) intento síncrono
                try:
                    with st.spinner("Generando banner…"):
                        url = create_banner_with_two_images(
                            image1_bytes=img1, image2_bytes=img2, prompt=prompt
                        )
                    st.session_state["banner_result_url"] = url
                    st.success("¡Listo! Banner generado.")
                except N8NClientError:
                    # 2) fallback asíncrono (si tu webhook devuelve job_id rápido)
                    st.info("El flujo parece demorar. Probando modo asíncrono…")
                    try:
                        job_id = start_banner_job(image1_bytes=img1, image2_bytes=img2, prompt=prompt)
                        st.session_state["last_job_id"] = job_id
                        with st.spinner(f"Procesando job {job_id}…"):
                            url = None; t0 = time.time()
                            while time.time() - t0 < 120:
                                status, got_url = fetch_status(job_id)
                                if got_url: url = got_url; break
                                time.sleep(3)
                        if url:
                            st.session_state["banner_result_url"] = url
                            st.success("¡Listo! Banner generado (async).")
                        else:
                            st.warning("No llegó la URL dentro del tiempo de espera. Revisa el estado más tarde.")
                    except Exception as ee:
                        st.error(f"Error en modo asíncrono: {ee}")

        st.markdown("</div>", unsafe_allow_html=True)

    # ===== derecha: resultado (y previews) =====
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>Resultado</h3>", unsafe_allow_html=True)

        p1, p2 = st.columns(2)
        with p1:
            st.caption("Preview · Imagen 1")
            if st.session_state.get("img1_bytes"):
                st.image(io.BytesIO(st.session_state["img1_bytes"]), use_container_width=True)
            else:
                st.markdown('<div class="result-ph">Selecciona la Imagen 1</div>', unsafe_allow_html=True)
        with p2:
            st.caption("Preview · Imagen 2")
            if st.session_state.get("img2_bytes"):
                st.image(io.BytesIO(st.session_state["img2_bytes"]), use_container_width=True)
            else:
                st.markdown('<div class="result-ph">Selecciona la Imagen 2</div>', unsafe_allow_html=True)

        st.markdown("---")
        url = st.session_state.get("banner_result_url")
        if url:
            st.image(url, use_container_width=True, caption="Banner generado")
            try:
                content = requests.get(url, timeout=30).content
                st.download_button("⬇️ Descargar banner", data=content,
                                   file_name="banner.jpg", mime="image/jpeg",
                                   use_container_width=True)
            except Exception:
                st.info("No se pudo preparar la descarga directa; abre la imagen desde la vista previa.")
        else:
            st.markdown('<div class="result-ph">La imagen generada aparecerá aquí</div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
