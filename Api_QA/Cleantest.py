import io
import pandas as pd
import streamlit as st
from datetime import datetime  
import hashlib
from datetime import datetime
import time
import math

st.set_page_config(page_title="Generador QA", layout="wide", initial_sidebar_state="collapsed")

from auth_ui import SecureShell
from utils_ui import titulo_seccion, spinner_accion
from utils_csv import (
    limpiar_markdown_csv, validar_csv_qa, corregir_csv_con_comas,
    normalizar_steps, limpiar_csv_con_formato, leer_csv_seguro,limpiar_markdown_csv
)
from utils_testrail import (
    obtener_proyectos, obtener_suites, obtener_secciones, enviar_a_testrail
)
from utils_gemini import (
    enviar_a_gemini, extraer_texto_de_respuesta_gemini,
    prompt_generar_escenarios_profesionales, obtener_descripcion_refinada
)

   


shell = SecureShell(
    auth_yaml=".streamlit/auth.yaml",
    login_page_width=560,   
    app_page_width=1600,    
    logout_top=12,
    logout_right=96,
)
if not shell.login():
    st.stop()

st.title("🧪 Generador de Escenarios QA para TestRail")

st.session_state.setdefault("historial_generaciones", [])
st.session_state.setdefault("historial", [])
st.session_state.setdefault("df_editable", None)
st.session_state.setdefault("generado", False)
st.session_state.setdefault("texto_funcional", "")
st.session_state.setdefault("descripcion_refinada", "")

# Tabs principales
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "✏️ Generar", "🛠️ Editar", "🧪 Revisar", "📚 Historial", "🚀 Subir a TestRail"
])

def limpiar_pestanas():
    """Limpia variables de estado menos el historial."""
    keys_keep = {"historial_generaciones"}  
    for key in list(st.session_state.keys()):
        if key not in keys_keep:
            pass

st.markdown("""
<style>
.divider { border-top: 1px solid #CCC; margin: 20px 0 10px; }
</style>
<div class="divider"></div>
""", unsafe_allow_html=True)

if st.button("🧹 Limpiar todo", key="btn_limpiar_global"):
    limpiar_pestanas()
    st.rerun()


# --------------------------- TAB 1: GENERAR ---------------------------
with tab1:
    st.subheader("📌 Generar escenarios de prueba automáticamente")

    # 📝 Entrada: texto funcional
    texto_funcional = st.text_area(
        "Texto funcional original",
        value=st.session_state.get("texto_funcional", ""),
        height=260,
        key="texto_funcional",
        help="Pega aquí la descripción funcional que quieres convertir a escenarios."
    )

    # 🎛️ Acciones visibles y a lo ancho
    c1, c2 = st.columns([1, 1])
    generar_click = c1.button("⚙️ Generar escenarios de prueba", key="btn_generar_tab1", use_container_width=True)
    limpiar_click  = c2.button("🧹 Limpiar todo", key="btn_limpiar_tab1", use_container_width=True)

    if limpiar_click:
        # Resetea estado mínimo sin tocar el historial
        st.session_state["df_editable"] = None
        st.session_state["generado"] = False
        st.session_state["texto_funcional"] = ""
        st.session_state["descripcion_refinada"] = ""
        st.rerun()

    if generar_click:
        if not st.session_state["texto_funcional"].strip():
            st.warning("⚠️ Ingresa el texto funcional primero.")
        else:
            try:
                # 1) Refinar descripción para guiar al LLM
                with st.spinner("🧠 Reestructurando texto..."):
                    descripcion_refinada = obtener_descripcion_refinada(st.session_state["texto_funcional"])
                st.session_state["descripcion_refinada"] = descripcion_refinada

                # 2) Pedir a Gemini CSV profesional (6 columnas)
                with st.spinner("📄 Generando escenarios CSV profesionales..."):
                    respuesta_csv = enviar_a_gemini(
                        prompt_generar_escenarios_profesionales(descripcion_refinada)
                    )
                    texto_csv_raw = extraer_texto_de_respuesta_gemini(respuesta_csv).strip()

                # 3) Limpiezas para CSV robusto
                csv_limpio    = limpiar_markdown_csv(texto_csv_raw)                                # quita ``` y basura
                csv_valido    = limpiar_csv_con_formato(csv_limpio, columnas_esperadas=6)          # filtra filas con 6 cols
                csv_corregido = corregir_csv_con_comas(csv_valido, columnas_objetivo=6)            # reescapa comas
                df = pd.read_csv(io.StringIO(csv_corregido))
                # Normalizaciones
                df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                if "Steps" in df.columns:
                    df["Steps"] = df["Steps"].apply(normalizar_steps).str.replace(r'\\n', '\n', regex=True)
                df["Estado"] = "Pendiente"

                # 4) Persistir en sesión
                st.session_state.df_editable = df
                st.session_state.generado = True

                from datetime import datetime
                st.session_state.setdefault("historial_generaciones", [])
                st.session_state["historial_generaciones"].append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fuente": "QA",
                    "origen": "Generación inicial",
                    "descripcion": descripcion_refinada,
                    "escenarios": df.copy()
                })

                st.success(f"✅ Se generaron {len(df)} escenarios.")
                st.dataframe(df, use_container_width=True)

            except Exception as e:
                st.error(f"❌ Error durante el proceso: {e}")
                # Mostrar lo que vino para depurar
                try:
                    st.text_area("⚠️ CSV recibido (crudo)", texto_csv_raw, height=220)
                except Exception:
                    pass
                st.session_state.df_editable = None
                st.session_state.generado = False





with tab2:
    titulo_seccion("Editar escenarios generados", "🛠️")

    if not st.session_state.get("generado") or st.session_state.get("df_editable") is None:
        st.info("ℹ️ No hay escenarios generados para editar.")
    else:
        df = st.session_state.df_editable.copy()

        if "Estado" not in df.columns:
            df["Estado"] = "Pendiente"

        df["Steps"] = df["Steps"].apply(normalizar_steps)
        df["Expected Result"] = df["Expected Result"].apply(normalizar_steps)
        df = st.session_state.df_editable.copy()
        df.reset_index(drop=True, inplace=True)
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Priority": st.column_config.SelectboxColumn("Priority", options=["Alta", "Media", "Baja"]),
                "Type": st.column_config.SelectboxColumn("Type", options=["Funcional", "Validación", "Usabilidad", "Integración", "Seguridad"]),
                "Estado": st.column_config.SelectboxColumn("Estado", options=["Pendiente", "Listo", "Descartado"])
            }
        )

        st.session_state.df_editable = edited_df

        if st.button("✅ Marcar todos como listos"):
            edited_df["Estado"] = "Listo"
            st.session_state.df_editable = edited_df
            st.success("Todos los escenarios han sido marcados como listos.")


# --------------------------- TAB 3: REVISAR (SOLO GEMINI) ---------------------------
# --------------------------- TAB 3: REVISAR (AUTOMÁTICO, SOLO GEMINI) ---------------------------
with tab3:

    st.subheader("💡 Sugerencias de nuevos escenarios a partir del análisis actual")

    df_actual = st.session_state.get("df_editable")
    if df_actual is None or df_actual.empty:
        st.info("ℹ️ No hay escenarios generados aún.")
    else:
        # Solo columnas relevantes (y Estados Pendiente/Lista)
        cols_base = ["Title", "Preconditions", "Steps", "Expected Result"]
        cols_presentes = [c for c in cols_base if c in df_actual.columns]
        df_revisar = df_actual.loc[df_actual["Estado"].isin(["Pendiente", "Listo"]), cols_presentes].copy()

        if df_revisar.empty:
            st.info("ℹ️ No hay datos para evaluar.")
        else:
            st.dataframe(df_revisar, use_container_width=True)

            # --- Disparador automático por hash del contexto ---
            texto_contexto = df_revisar.to_csv(index=False)
            context_hash = hashlib.sha256(texto_contexto.encode("utf-8")).hexdigest()[:12]

            ss = st.session_state
            ss.setdefault("sug_context_hash", None)
            ss.setdefault("sugerencias_df", None)
            ss.setdefault("sug_inflight", False)

            # Ejecutar solo si cambió el contexto y no hay ejecución en curso
            should_run = (context_hash != ss["sug_context_hash"]) and (not ss["sug_inflight"])

            if should_run:
                ss["sug_inflight"] = True
                try:
                    prompt = {
                        "generationConfig": {"temperature": 0.15, "topK": 40, "topP": 0.9, "maxOutputTokens": 2048},
                        "contents": [{
                            "parts": [{
                                "text": (
                                    "Eres un Analista QA Senior especializado en diseño de pruebas funcionales.\n\n"
                                    "Evalúa los siguientes escenarios existentes (CSV) y sugiere NUEVOS escenarios complementarios que amplíen cobertura.\n"
                                    "Prioriza validaciones faltantes, negativos/edge/seguridad y usabilidad/persistencia.\n\n"
                                    "⚠️ Reglas:\n"
                                    "- NO repitas escenarios ya presentes.\n"
                                    "- Devuelve de 4 a 8 filas.\n"
                                    "- Formato CSV puro, SIN encabezados ni texto adicional:\n"
                                    "Title,Preconditions,Steps,Expected Result\n\n"
                                    f"CSV:\n{texto_contexto}"
                                )
                            }]}
                        ]
                    }

                    with spinner_accion("🧠 Generando sugerencias con Gemini..."):    # spinner claro y visible :contentReference[oaicite:3]{index=3}
                        resp = enviar_a_gemini(prompt)                                # llamada a la API :contentReference[oaicite:4]{index=4}
                        texto_raw = extraer_texto_de_respuesta_gemini(resp)           # extrae texto plano    :contentReference[oaicite:5]{index=5}

                    # Limpieza y parseo robusto
                    texto_csv = limpiar_markdown_csv(texto_raw)                       # quita ```csv ...```    :contentReference[oaicite:6]{index=6}
                    df_sug = leer_csv_seguro(texto_csv, columnas_esperadas=4)         # CSV -> DataFrame       :contentReference[oaicite:7]{index=7}

                    # Postproceso: normalizar, defaults y deduplicar contra los actuales
                    if "Steps" in df_sug.columns:
                        df_sug["Steps"] = df_sug["Steps"].apply(normalizar_steps)     # bullets/num.           :contentReference[oaicite:8]{index=8}

                    for c, dflt in [("Type", "Funcional"), ("Priority", "Media"), ("Estado", "Pendiente")]:
                        if c not in df_sug.columns:
                            df_sug[c] = dflt

                    tit_exist = set(df_actual["Title"].astype(str).str.strip().str.lower())
                    df_sug["__t"] = df_sug["Title"].astype(str).str.strip().str.lower()
                    df_sug = df_sug[~df_sug["__t"].isin(tit_exist)].drop(columns="__t", errors="ignore")
                    df_sug = df_sug.reset_index(drop=True)

                    ss["sugerencias_df"] = df_sug
                    ss["sug_context_hash"] = context_hash

                    if df_sug.empty:
                        st.warning("⚠️ Gemini no propuso escenarios nuevos para este análisis.")
                    else:
                        st.success(f"✅ Sugerencias generadas: {len(df_sug)}")
                except Exception as e:
                    ss["sugerencias_df"] = pd.DataFrame()
                    st.error(f"❌ Error al generar sugerencias: {e}")
                finally:
                    ss["sug_inflight"] = False

    # --- Render y aplicación ---
    df_sugerencias = st.session_state.get("sugerencias_df")
    if isinstance(df_sugerencias, pd.DataFrame) and not df_sugerencias.empty:
        st.markdown("### 💡 Sugerencias de nuevos escenarios")
        st.dataframe(df_sugerencias, use_container_width=True)

        st.markdown("### ✅ Selecciona los escenarios que deseas aplicar:")
        seleccion_indices = []
        for i, row in df_sugerencias.iterrows():
            titulo = str(row.get("Title", f"Escenario {i}")).strip()
            if st.checkbox(titulo, key=f"t3_sug_{i}_{st.session_state.get('sug_context_hash','')}"):
                seleccion_indices.append(i)

        if st.button("➕ Aplicar escenarios seleccionados", key="btn_aplicar_sug", disabled=(len(seleccion_indices) == 0)):
            try:
                df_aplicar = df_sugerencias.loc[seleccion_indices].copy()

                # Evitar duplicados por Title contra el DF actual
                titulos_existentes = set(st.session_state["df_editable"]["Title"].astype(str).str.strip().str.lower())
                df_aplicar["__t"] = df_aplicar["Title"].astype(str).str.strip().str.lower()
                df_aplicar = df_aplicar[~df_aplicar["__t"].isin(titulos_existentes)].drop(columns="__t", errors="ignore")

                if df_aplicar.empty:
                    st.info("ℹ️ Todos los seleccionados ya estaban aplicados o no hay nuevos.")
                else:
                    # Alinear columnas con df_editable
                    cols_destino = list(st.session_state["df_editable"].columns)
                    for c in cols_destino:
                        if c not in df_aplicar.columns:
                            df_aplicar[c] = ""
                    df_aplicar = df_aplicar[cols_destino]

                    # Actualiza DF principal
                    st.session_state["df_editable"] = pd.concat(
                        [st.session_state["df_editable"], df_aplicar], ignore_index=True
                    )
                    st.session_state["generado"] = True

                    # Historial
                    st.session_state.setdefault("historial_generaciones", [])
                    st.session_state["historial_generaciones"].append({
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "origen": "Sugerencias",
                        "escenarios": df_aplicar.copy()
                    })

                    st.success(f"✅ {len(df_aplicar)} escenario(s) aplicados. Revisa 'Historial' y 'Subir a TestRail'.")
            except Exception as e:
                st.error(f"❌ Error al aplicar sugerencias: {e}")






with tab4:

    if "historial_generaciones" not in st.session_state:
        st.session_state["historial_generaciones"] = []

    historial = st.session_state["historial_generaciones"]

    if not historial:
        st.info("ℹ️ Aún no hay historial disponible. Genera escenarios para comenzar a registrar.")
    else:
        resumen = pd.DataFrame([
            {
                "Fecha": item["fecha"],
                "Fuente": f"{item.get('fuente', 'Desconocida')} ({item.get('origen', 'N/A')})",
                "Escenarios": len(item["escenarios"]),
                "Ver": f"📝 Ver #{i}"
            }
            for i, item in enumerate(historial)
        ])

        st.markdown("### 🧾 Generaciones previas")
        st.dataframe(resumen, use_container_width=True, hide_index=True)

        seleccion = st.selectbox("Selecciona una generación para revisar:",
                                 options=[f"#{i+1} | {item['fecha']} ({item.get('fuente', 'N/A')})"
                                          for i, item in enumerate(historial)],
                                 index=len(historial)-1)

        idx = int(seleccion.split("|")[0].replace("#", "")) - 1
        item = historial[idx]

        #st.markdown(f"### 🧪 Escenarios generados el {item['fecha']}")
        #st.code(item["descripcion"], language="markdown")
        #st.dataframe(item["escenarios"], use_container_width=True)

        if st.button("↩ Restaurar esta generación"):
            st.session_state.df_editable = item["escenarios"].copy()
            st.success("✅ Escenarios restaurados.")
            st.rerun()





# --------------------------- TAB 5: SUBIR A TESTRAIL ---------------------------
with tab5:
    st.subheader("🚀 Subir casos a TestRail")

    # 📡 Obtener proyectos
    proyectos_raw = obtener_proyectos()
    if isinstance(proyectos_raw, dict) and "projects" in proyectos_raw:
        proyectos = proyectos_raw["projects"]
    elif isinstance(proyectos_raw, list):
        proyectos = proyectos_raw
    else:
        st.error("❌ Formato inesperado al recibir proyectos.")
        st.stop()

    # 🎛️ Proyecto
    sel_proy = st.selectbox("Proyecto", [p["name"] for p in proyectos], key="select_proy")
    id_proy = next((p["id"] for p in proyectos if p["name"] == sel_proy), None)

    # 📢 Anuncio del proyecto (si existe)
    anuncio = next((p.get("announcement") for p in proyectos if p["id"] == id_proy), None)
    if anuncio:
        st.info(f"📢 {anuncio}")

    # 📁 Suites
    suites_raw = obtener_suites(id_proy)
    if isinstance(suites_raw, dict) and "suites" in suites_raw:
        suites = suites_raw["suites"]
    elif isinstance(suites_raw, list):
        suites = suites_raw
    else:
        st.error("❌ Error al recibir suites desde TestRail.")
        st.json(suites_raw)
        st.stop()

    sel_suite = st.selectbox("Suite", [s["name"] for s in suites], key="select_suite")
    suite_id = next((s["id"] for s in suites if s["name"] == sel_suite), None)

    # 📂 Secciones
    secciones_raw = obtener_secciones(id_proy, suite_id)
    if isinstance(secciones_raw, dict) and "sections" in secciones_raw:
        secciones = secciones_raw["sections"]
    elif isinstance(secciones_raw, list):
        secciones = secciones_raw
    else:
        st.error("❌ Error al recibir secciones desde TestRail.")
        st.json(secciones_raw)
        st.stop()

    sel_seccion = st.selectbox("Sección", [s["name"] for s in secciones], key="select_seccion")
    section_id = next((s["id"] for s in secciones if s["name"] == sel_seccion), None)

    # ✅ Vista previa + subida
    df = st.session_state.get("df_editable")

    if df is not None and section_id:
        import re
        from textwrap import shorten
        import pandas as pd

        def _orac_preview(row: pd.Series) -> str:
            """Genera un oráculo breve (custom_case_oracle) que NO duplique el Expected."""
            title = str(row.get("Title", "") or "").strip()
            steps = str(row.get("Steps", "") or "").strip()
            expected = str(row.get("Expected Result", "") or "").strip()

            if re.search(r"obligatori|requerid", expected.lower()) or "no se envía" in expected.lower():
                m = re.search(r"(campo|nombre)\s*['“\"]?([^'”\"]+)['”\"]?", title.lower()) or \
                    re.search(r"(campo|nombre)\s*['“\"]?([^'”\"]+)['”\"]?", steps.lower())
                campo = m.group(2) if m else "el campo requerido"
                oracle = f"Regla: si falta {campo}, el formulario debe bloquear el envío y mostrar validación."
            else:
                oracle = f"Regla: {title} cumple condición de aceptación sin persistir datos inválidos."

            if oracle.strip().lower() == expected.strip().lower():
                oracle = "Regla: validar mensaje y bloqueo en ausencia de dato requerido."
            return oracle

        # Construir DF de previsualización (incluye el oráculo que se enviará)
        df_prev = df.copy()
        df_prev["custom_case_oracle (preview)"] = df_prev.apply(_orac_preview, axis=1)

        # Señalar posibles duplicados con Expected
        iguales = (df_prev["custom_case_oracle (preview)"].astype(str).str.strip().str.lower()
                   == df_prev["Expected Result"].astype(str).str.strip().str.lower())
        duplicados = int(iguales.sum())
        if duplicados > 0:
            st.warning(f"⚠️ {duplicados} oráculo(s) parecen iguales al 'Expected Result'. "
                       "Se ajustarán automáticamente al enviar.")

        # Mostrar tabla amigable (acortamos columnas largas)
        df_mostrar = df_prev.copy()
        df_mostrar["Expected Result"] = df_mostrar["Expected Result"].apply(lambda t: shorten(str(t), width=160, placeholder="…"))
        df_mostrar["custom_case_oracle (preview)"] = df_mostrar["custom_case_oracle (preview)"].apply(lambda t: shorten(str(t), width=160, placeholder="…"))

        st.markdown("### 🧪 Vista previa (incluye oráculo no duplicado)")
        st.dataframe(df_mostrar, use_container_width=True)

        # Deshabilitar envío si hay Expected vacío (tu instancia exige oráculo ≠ vacío)
        faltantes_expected = df["Expected Result"].apply(lambda x: not bool(str(x).strip())).sum()
        disabled_upload = faltantes_expected > 0
        if disabled_upload:
            st.error(f"❌ Hay {faltantes_expected} caso(s) con 'Expected Result' vacío. Complétalos antes de subir.")

        if st.button("📤 Subir casos a TestRail", disabled=disabled_upload):
            with st.spinner("📡 Subiendo casos..."):
                # Usa utils_testrail.enviar_a_testrail (versión que envía custom_case_oracle)
                resultado = enviar_a_testrail(section_id, df)

            if resultado["exito"]:
                st.success(f"✅ {resultado['subidos']} casos subidos correctamente.")
                st.rerun()
            else:
                st.error(f"❌ Solo se subieron {resultado['subidos']} de {resultado['total']} casos.")
                if resultado["detalle"]:
                    with st.expander("🔍 Ver detalles del error"):
                        for err in resultado["detalle"]:
                            st.write(err)
    else:
        st.info("Genera los casos en el Tab '✏️ Generar' y selecciona Proyecto, Suite y Sección.")
