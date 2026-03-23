# app/tabs/tab_product.py
import io, json, time, requests, streamlit as st
from services.productvision_client import describe_product_base64, ProductVisionError

def _strip_status_layer(data):
    """Quita 'status' de la respuesta y devuelve el contenido útil.
       Preferimos claves conocidas; si no, devolvemos el dict sin 'status'."""
    if isinstance(data, dict) and "status" in data:
        for k in ("data", "result", "product", "payload", "output", "response"):
            if k in data and isinstance(data[k], (dict, list, str, int, float, bool, type(None))):
                return data[k]
        # si no hay claves conocidas, quitamos 'status'
        rest = {k: v for k, v in data.items() if k != "status"}
        if len(rest) == 1:
            return next(iter(rest.values()))
        return rest
    return data

def _file_card(title: str, b: bytes, key_prefix: str):
    """Mini-card con preview + 'Cambiar' para reemplazar la imagen."""
    c1, c2 = st.columns([1, 2])
    with c1:
        st.image(io.BytesIO(b), use_container_width=True)
    with c2:
        kb = len(b) / 1024
        st.caption(title)
        st.caption(f"{kb:,.1f} KB")
        if st.button("Cambiar", key=f"{key_prefix}_change"):
            st.session_state.pop(f"{key_prefix}_bytes", None)
            st.rerun()

def render():
    # ===== estilos =====
    st.markdown("""
    <style>
      :root{ --pri:#0A84FF; --bg:#F7F9FC; --card:#FFFFFF; --border:#E6E9F2; --text:#101828; }
      [data-testid="stAppViewContainer"]{ background: linear-gradient(180deg,var(--bg) 0%, #FFFFFF 100%); }
      .card{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 10px 30px rgba(16,24,40,.06); }
      .card h3{ margin:0 0 12px 0; color:var(--text) }
      #drop-scope [data-testid="stFileUploadDropzone"]{
        border:2px dashed #d7ddea !important; border-radius:14px; min-height:240px;
        background:repeating-linear-gradient(45deg,#fafcff,#fafcff 12px,#f3f6fb 12px,#f3f6fb 24px);
        display:flex;align-items:center;justify-content:center;
      }
      #drop-scope [data-testid="stFileUploadDropzone"] > div{ text-align:center;color:#8A94A6;font-weight:500; }
      .json-card{ border:1px solid var(--border); border-radius:14px; padding:8px 8px 4px; background:#fff; }
      .stButton > button[kind="primary"]{
        width:100%; border:0; border-radius:12px; padding:.8rem 1rem; background:var(--pri); color:#fff; font-weight:700;
        box-shadow:0 8px 18px rgba(10,132,255,.25);
      }
    </style>
    """, unsafe_allow_html=True)

    # ===== estado =====
    st.session_state.setdefault("pv_img_bytes", None)
    st.session_state.setdefault("pv_img_mime", None)
    st.session_state.setdefault("pv_json", None)

    left, right = st.columns([1,1], vertical_alignment="top")

    # ===== izquierda: entrada =====
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>B) Product Vision</h3>", unsafe_allow_html=True)
        st.caption("Sube una imagen de producto y añade un prompt (obligatorio). El servicio devuelve JSON.")

        # Dropzone -> desaparece al tener imagen
        if st.session_state.get("pv_img_bytes"):
            _file_card("Imagen de producto", st.session_state["pv_img_bytes"], "pv_img")
        else:
            st.markdown('<div id="drop-scope">', unsafe_allow_html=True)
            up = st.file_uploader(" ", type=["png","jpg","jpeg"], label_visibility="collapsed",
                                  help="Haz clic o suelta el archivo aquí (hasta ~200MB).")
            st.markdown('</div>', unsafe_allow_html=True)
            if up is not None:
                st.session_state["pv_img_bytes"] = up.getvalue()
                st.session_state["pv_img_mime"]  = getattr(up, "type", "image/jpeg")
                st.rerun()

        # Prompt obligatorio
        prompt = st.text_area(
            "Prompt (obligatorio — estilo, beneficios, tono, etc.)",
            value="Empaque, beneficios, ingredientes clave, tono amigable.",
            height=110,
            placeholder="Describe atributos y contexto que quieras resaltar…",
        )

        cA, cB = st.columns([1,1])
        gen = cA.button("Analizar", type="primary", use_container_width=True,
                        disabled=not (bool(st.session_state.get("pv_img_bytes")) and bool(prompt.strip())))
        clr = cB.button("Limpiar", use_container_width=True)

        if clr:
            for k in ("pv_img_bytes","pv_img_mime","pv_json"):
                st.session_state.pop(k, None)
            st.rerun()

        if gen:
            try:
                with st.spinner("Analizando…"):
                    raw = describe_product_base64(
                        st.session_state["pv_img_bytes"],
                        prompt_extra=prompt.strip(),
                        mime=st.session_state.get("pv_img_mime"),
                    )
                st.session_state["pv_json"] = _strip_status_layer(raw)
                st.success("¡Listo! JSON recibido.")
            except ProductVisionError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Error inesperado: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

    # ===== derecha: resultado =====
    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h3>Resultado</h3>", unsafe_allow_html=True)

        # Preview arriba (opcional, queda lindo)
        if st.session_state.get("pv_img_bytes"):
            st.image(io.BytesIO(st.session_state["pv_img_bytes"]), use_container_width=True)
            st.markdown("---")

        data = st.session_state.get("pv_json")
        if data is not None:
            st.markdown('<div class="json-card">', unsafe_allow_html=True)
            st.json(data, expanded=2, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)

            # Copiar JSON
            from streamlit.components.v1 import html
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            html(f"""
            <script>
              async function copyJson(){{
                await navigator.clipboard.writeText({json.dumps(pretty)});
                const btn = document.getElementById("copyjson");
                btn.innerText = "Copiado ✔";
                setTimeout(()=>btn.innerText="Copiar JSON", 1200);
              }}
            </script>
            <button id="copyjson" onclick="copyJson()" style="
              margin-top:8px;border:1px solid #E6E9F2;border-radius:10px;padding:.5rem .75rem;
              background:#fff;cursor:pointer;font-weight:600;">Copiar JSON</button>
            """, height=60)
        else:
            st.info("Sube una imagen, escribe el prompt y pulsa **Analizar**.")

        st.markdown('</div>', unsafe_allow_html=True)
