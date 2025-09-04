import io
import pandas as pd
import streamlit as st
from datetime import datetime  
st.set_page_config(page_title="Generador QA", layout="wide", initial_sidebar_state="collapsed")

from auth_ui import SecureShell
from utils_ui import titulo_seccion, spinner_accion
from utils_csv import (
    limpiar_markdown_csv, limpiar_csv_sugerencias, corregir_csv_con_comas,
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


with tab1:
    from datetime import datetime
    from utils_csv import (
        limpiar_markdown_csv, limpiar_csv_con_formato,
        corregir_csv_con_comas, normalizar_steps,
        validar_csv_qa
    )

    st.subheader("📌 Generar escenarios de prueba automáticamente")

    texto_funcional = st.text_area(
        "Texto funcional original",
        value=st.session_state.get("texto_funcional", ""),
        height=250,
        key="texto_funcional"
    )

    if st.button("Generar escenarios de prueba", key="btn_generar_tab1"):
        if not st.session_state["texto_funcional"].strip():
            st.warning("⚠️ Ingresa el texto funcional primero.")
        else:
            try:
                with st.spinner("🧠 Reestructurando texto..."):
                    descripcion_refinada = obtener_descripcion_refinada(st.session_state["texto_funcional"])
                st.session_state["descripcion_refinada"] = descripcion_refinada

                with st.spinner("📄 Generando escenarios CSV profesionales..."):
                    respuesta_csv = enviar_a_gemini(
                        prompt_generar_escenarios_profesionales(descripcion_refinada)
                    )
                    texto_csv_raw = extraer_texto_de_respuesta_gemini(respuesta_csv).strip()

                csv_limpio = limpiar_markdown_csv(texto_csv_raw)
                csv_valido = limpiar_csv_con_formato(csv_limpio, columnas_esperadas=6)
                csv_corregido = corregir_csv_con_comas(csv_valido, columnas_objetivo=6)

                expected_cols = ["Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"]

                def _igual_a_encabezado(row_vals):
                    a = [str(x).strip().strip('"').strip("'") for x in row_vals]
                    b = [c.strip() for c in expected_cols]
                    return a == b

                df = None
                try:
                    validar_csv_qa(csv_corregido)
                    df = pd.read_csv(io.StringIO(csv_corregido))
                except Exception:
                    df = pd.read_csv(io.StringIO(csv_corregido), header=None, names=expected_cols)

                if not df.empty and _igual_a_encabezado(df.iloc[0].tolist()):
                    df = df.iloc[1:].reset_index(drop=True)

                df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
                if "Steps" in df.columns:
                    df["Steps"] = df["Steps"].apply(normalizar_steps).str.replace(r'\\n', '\n', regex=True)
                else:
                    df["Steps"] = ""

                if "Estado" not in df.columns:
                    df["Estado"] = "Pendiente"

                st.session_state.df_editable = df
                st.session_state.generado = True

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
                st.text_area("⚠️ CSV que causó error", texto_csv_raw, height=250)
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



with tab3:

    st.subheader("💡 Sugerencias de nuevos escenarios a partir del análisis actual")

    df_actual = st.session_state.get("df_editable")
    if df_actual is None or df_actual.empty:
        st.info("ℹ️ No hay escenarios generados aún.")
    else:
        columnas_base = ["Title", "Preconditions", "Steps", "Expected Result"]
        cols_presentes = [c for c in columnas_base if c in df_actual.columns]
        df_revisar = (
            df_actual.loc[df_actual["Estado"].isin(["Pendiente", "Listo"]), cols_presentes]
            .copy()
        )

        if df_revisar.empty:
            st.info("ℹ️ No hay datos para evaluar.")
        else:
            st.dataframe(df_revisar, use_container_width=True)

            # CSV de contexto para el LLM
            texto_contexto = df_revisar.to_csv(index=False)

            if st.button("🔍 Evaluar sugerencias", key="btn_eval_sug"):
                try:
                    prompt = {
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": (
                                            "Eres un Analista QA Senior especializado en diseño de pruebas funcionales.\n\n"
                                            "Evalúa los siguientes escenarios de prueba ya existentes (en formato CSV) y sugiere nuevos escenarios complementarios que amplíen la cobertura.\n\n"
                                            "Los nuevos escenarios deben centrarse en:\n"
                                            "- Validaciones que no estén cubiertas\n"
                                            "- Casos negativos, edge cases o de seguridad\n"
                                            "- Usabilidad, persistencia de datos y experiencia del usuario\n\n"
                                            "📄 Formato requerido del CSV (sin encabezados ni explicaciones):\n"
                                            "Title,Preconditions,Steps,Expected Result\n\n"
                                            "🎯 Instrucciones clave:\n"
                                            "- NO repitas escenarios ya presentes\n"
                                            "- Genera entre 4 y 8 escenarios distintos\n"
                                            "- Usa lenguaje profesional y técnico\n"
                                            "- No incluyas texto fuera del CSV\n\n"
                                            f"CSV:\n{texto_contexto}"
                                        )
                                    }
                                ]
                            }
                        ]
                    }

                    with spinner_accion("💡 Evaluando sugerencias..."):
                        respuesta = enviar_a_gemini(prompt)
                        texto_raw = extraer_texto_de_respuesta_gemini(respuesta)

                    texto_csv = limpiar_markdown_csv(texto_raw)
                    texto_csv = limpiar_csv_sugerencias(texto_csv, columnas_esperadas=4)

                    df_sugerencias = leer_csv_seguro(texto_csv, columnas_esperadas=4)

                    if "Steps" in df_sugerencias.columns:
                        df_sugerencias["Steps"] = df_sugerencias["Steps"].apply(normalizar_steps)

                    for c, dflt in [("Type", "Funcional"), ("Priority", "Media"), ("Estado", "Pendiente")]:
                        if c not in df_sugerencias.columns:
                            df_sugerencias[c] = dflt

                    st.session_state["sugerencias_df"] = df_sugerencias
                    st.success("✅ Sugerencias generadas.")
                except Exception as e:
                    st.error(f"❌ Error al generar sugerencias: {e}")

    df_sugerencias = st.session_state.get("sugerencias_df")
    if isinstance(df_sugerencias, pd.DataFrame) and not df_sugerencias.empty:
        st.markdown("### 💡 Sugerencias de nuevos escenarios")
        st.dataframe(df_sugerencias, use_container_width=True)

        st.markdown("### ✅ Selecciona los escenarios que deseas aplicar:")
        seleccion_indices = []
        for i, row in df_sugerencias.iterrows():
            titulo = str(row.get("Title", f"Escenario {i}")).strip()
            if st.checkbox(titulo, key=f"t3_sug_{i}"):
                seleccion_indices.append(i)

        hay_seleccion = len(seleccion_indices) > 0

        if st.button("➕ Aplicar escenarios seleccionados", key="btn_aplicar_sug", disabled=not hay_seleccion):
            try:
                df_aplicar = df_sugerencias.loc[seleccion_indices].copy()

                titulos_existentes = set(st.session_state["df_editable"]["Title"].astype(str))
                df_aplicar = df_aplicar[~df_aplicar["Title"].astype(str).isin(titulos_existentes)]

                if df_aplicar.empty:
                    st.info("ℹ️ Todos los seleccionados ya estaban aplicados o no hay nuevos.")
                else:
                    cols_destino = list(st.session_state["df_editable"].columns)
                    for c in cols_destino:
                        if c not in df_aplicar.columns:
                            df_aplicar[c] = ""  
                    df_aplicar = df_aplicar[cols_destino]

                    st.session_state["df_editable"] = pd.concat(
                        [st.session_state["df_editable"], df_aplicar], ignore_index=True
                    )
                    st.session_state["generado"] = True

                    st.session_state.setdefault("historial_generaciones", [])
                    st.session_state["historial_generaciones"].append({
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "origen": "Sugerencias",
                        "escenarios": df_aplicar.copy()
                    })

                    st.success(f"✅ {len(df_aplicar)} escenario(s) aplicados. Revisa 'Historial' y 'Subir a TestRail'.")
            except Exception as e:
                st.error(f"❌ Error al aplicar sugerencias: {e}")







import pandas as pd
from datetime import datetime

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





with tab5:
    st.subheader("🚀 Subir casos a TestRail")

    proyectos_raw = obtener_proyectos()

    if isinstance(proyectos_raw, dict) and "projects" in proyectos_raw:
        proyectos = proyectos_raw["projects"]
    else:
        st.error("❌ Formato inesperado al recibir proyectos.")
        st.stop()

    sel_proy = st.selectbox("Proyecto", [p["name"] for p in proyectos], key="select_proy")
    id_proy = next((p["id"] for p in proyectos if p["name"] == sel_proy), None)

    anuncio = next((p.get("announcement") for p in proyectos if p["id"] == id_proy), None)
    if anuncio:
        st.info(f"📢 {anuncio}")

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

    df = st.session_state.get("df_editable")

    if df is not None and section_id:
        st.markdown("### 🧪 Vista previa de los casos a subir")
        st.dataframe(df, use_container_width=True)

        if st.button("📤 Subir casos a TestRail"):
            with st.spinner("📡 Subiendo casos..."):
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


