# ============================ Cleantest.py (LIMPIO + PATCH + HEADER FIX) ============================
import io
import pandas as pd
import streamlit as st
from datetime import datetime

# 1) SIEMPRE la primera llamada Streamlit
st.set_page_config(page_title="Generador QA", layout="wide", initial_sidebar_state="collapsed")

# 2) Importar utilidades propias SOLO una vez
from auth_ui import SecureShell
from utils_ui import titulo_seccion, spinner_accion
from utils_csv import (
    limpiar_markdown_csv, normalizar_preconditions, corregir_csv_con_comas,
    normalizar_steps, limpiar_csv_con_formato, leer_csv_seguro
)
from utils_testrail import (
    obtener_proyectos, obtener_suites, obtener_secciones, enviar_a_testrail
)
from utils_gemini import (
    prompt_refinar_descripcion, enviar_a_gemini, extraer_texto_de_respuesta_gemini,
    prompt_generar_escenarios_profesionales, obtener_descripcion_refinada
)

# 3) Login + tamaños independientes
shell = SecureShell(
    auth_yaml=".streamlit/auth.yaml",
    login_page_width=560,   # <-- ancho SOLO del login
    app_page_width=1600,    # <-- ancho SOLO del contenido de la app
    logout_top=12,
    logout_right=96,
)
if not shell.login():
    st.stop()

# ============================ APP (UNA SOLA VEZ) ============================
st.title("🧪 Generador de Escenarios QA para TestRail")

# Estado global
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

st.markdown(
    """
<style>
.divider { border-top: 1px solid #CCC; margin: 20px 0 10px; }
</style>
<div class="divider"></div>
""",
    unsafe_allow_html=True,
)

# Botón global de limpieza con key única
if st.button("🧹 Limpiar todo", key="btn_limpiar_global"):
    limpiar_pestanas()
    st.rerun()

# --------------------------- TAB 1: GENERAR ---------------------------
with tab1:
    st.subheader("📌 Generar escenarios de prueba automáticamente")

    texto_funcional = st.text_area(
        "Texto funcional original",
        value=st.session_state.get("texto_funcional", ""),
        height=250,
        key="texto_funcional"  # la misma clave para que la conserve
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

                # Limpiar y corregir CSV
                csv_limpio = limpiar_markdown_csv(texto_csv_raw)
                csv_valido = limpiar_csv_con_formato(csv_limpio, columnas_esperadas=6)
                csv_corregido = corregir_csv_con_comas(csv_valido, columnas_objetivo=6)

                # Convertir en DataFrame
                df = pd.read_csv(io.StringIO(csv_corregido))
                df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

                # Normalización de Steps y Preconditions
                df["Steps"] = df["Steps"].apply(normalizar_steps).str.replace(r'\\n', '\n', regex=True)
                if "Preconditions" in df.columns:
                    df["Preconditions"] = df["Preconditions"].apply(normalizar_preconditions)

                df["Estado"] = "Pendiente"

                st.session_state.df_editable = df
                st.session_state.generado = True

                from datetime import datetime
                st.session_state["historial_generaciones"].append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "fuente": "QA",
                    "origen": "Generación inicial",
                    "descripcion": descripcion_refinada,
                    "escenarios": df.copy()
                })

            except Exception as e:
                st.error(f"❌ Error durante el proceso: {e}")
                st.text_area("⚠️ CSV que causó error", texto_csv_raw, height=250)
                st.session_state.df_editable = None
                st.session_state.generado = False

    # Mostrar DF si ya existía
    if st.session_state.get("df_editable") is not None:
        st.markdown("### ✅ Escenarios generados previamente:")
        st.dataframe(st.session_state.df_editable, use_container_width=True)


# --------------------------- TAB 2: EDITAR ---------------------------
with tab2:
    titulo_seccion("Editar escenarios generados", "🛠️")

    if not st.session_state.get("generado") or st.session_state.get("df_editable") is None:
        st.info("ℹ️ No hay escenarios generados para editar.")
    else:
        df = st.session_state.df_editable.copy()

        # Agregar columna de estado si no existe
        if "Estado" not in df.columns:
            df["Estado"] = "Pendiente"

        # Normalización de Steps, Expected y Preconditions
        if "Steps" in df.columns:
            df["Steps"] = df["Steps"].apply(normalizar_steps)
        if "Expected Result" in df.columns:
            df["Expected Result"] = df["Expected Result"].apply(normalizar_steps)
        if "Preconditions" in df.columns:
            df["Preconditions"] = df["Preconditions"].apply(normalizar_preconditions)

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

        # Botón para marcar todos como listos
        if st.button("✅ Marcar todos como listos"):
            edited_df["Estado"] = "Listo"
            st.session_state.df_editable = edited_df
            st.success("Todos los escenarios han sido marcados como listos.")


# --------------------------- TAB 3: REVISAR / SUGERENCIAS ---------------------------
# --------------------------- TAB 3: REVISAR / SUGERENCIAS ---------------------------
with tab3:
    st.subheader("💡 Sugerencias de nuevos escenarios a partir del análisis actual")

    df_actual = st.session_state.get("df_editable")
    if df_actual is None or df_actual.empty:
        st.info("ℹ️ No hay escenarios generados aún.")
    else:
        # Tomamos solo los estados de interés y las columnas necesarias
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
            contexto_csv = df_revisar.to_csv(index=False)

            if st.button("🔍 Evaluar sugerencias", key="btn_eval_sug"):
                try:
                    prompt = {
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": (
                                            "Eres un Analista QA Senior especializado en diseño de pruebas funcionales.\n\n"
                                            "A partir del CSV de escenarios existente, sugiere nuevos casos COMPLEMENTARIOS "
                                            "(sin repetir los actuales) y devuélvelos en **CSV puro** con columnas EXACTAS:\n"
                                            "Title,Preconditions,Steps,Expected Result\n\n"
                                            "REGLAS DE SALIDA (obligatorias):\n"
                                            "- SOLO imprime el CSV (sin explicaciones, sin markdown, sin texto adicional).\n"
                                            "- Usa comas como separador; si un campo contiene comas o saltos de línea, ENCERRAR en comillas dobles.\n"
                                            "- Steps numerados como '1. ', '2. ', '3. ', cada uno en su propia línea usando \\n dentro de la celda.\n"
                                            "- Genera 4–8 casos nuevos, profesionales y no redundantes con el contexto.\n\n"
                                            "PRECONDITIONS (formato y contenido OBLIGATORIOS):\n"
                                            "- Deben ir **enumeradas** y en **líneas separadas dentro de la misma celda** usando \\n.\n"
                                            "- Sigue SIEMPRE este patrón (según aplique por el escenario):\n"
                                            "  1. Aplicación disponible y sesión iniciada\n"
                                            "  2. Usuario con permisos para <ACCIÓN inferida de los Steps>\n"
                                            "  3. Existen <DATOS DE NEGOCIO requeridos> (p. ej., asiento contable X, movimientos en rango, cliente válido)\n"
                                            "  4. Servicios de <MÓDULO/SUBMÓDULO> <operativos | NO operativos (si el caso es negativo por indisponibilidad)>\n"
                                            "- Inferir **<ACCIÓN>** desde los Steps (mapa típico):\n"
                                            "    consultar/ver → 'consultar'; exportar/descargar → 'exportar';\n"
                                            "    generar reporte → 'consultar y generar reportes'; acceder → 'acceder al módulo';\n"
                                            "    crear/editar/eliminar → 'crear/editar/eliminar <objeto>' según corresponda.\n"
                                            "- Si los Steps implican error por caída/indisponibilidad → usa 'NO operativos'; de lo contrario 'operativos'.\n"
                                            "- Prohibido: 'Ninguna', 'N/A', o solo 'Usuario con sesión iniciada' sin permisos ni datos.\n\n"
                                            "CHECKLIST interno antes de responder (NO imprimir):\n"
                                            "- ¿Permisos alineados con la acción principal de los Steps? ✔\n"
                                            "- ¿Datos de negocio explícitos y realistas? ✔\n"
                                            "- ¿Servicios correctamente marcados operativos/NO operativos según el objetivo del caso? ✔\n"
                                            "- ¿Preconditions enumeradas con '\\n' dentro de la celda y sin duplicados? ✔\n\n"
                                            "Contexto (CSV existente):\n"
                                            f"{contexto_csv}"
                                        )
                                    }
                                ]
                            }
                        ]
                    }

                    # Llama a Gemini y limpia salida
                    respuesta = enviar_a_gemini(prompt)
                    texto_raw = extraer_texto_de_respuesta_gemini(respuesta)
                    texto_csv = limpiar_markdown_csv(texto_raw)

                    # Cargar sugerencias (4 columnas)
                    df_sugerencias = leer_csv_seguro(texto_csv, columnas_esperadas=4)

                    # No normalizamos Precondition localmente: dejamos el formato tal como viene de Gemini
                    # (sí limpiamos Steps para garantizar saltos de línea visibles)
                    if "Steps" in df_sugerencias.columns:
                        df_sugerencias["Steps"] = df_sugerencias["Steps"].apply(normalizar_steps)

                    # Completar metadatos faltantes para integrarse con el DF principal
                    for c, dflt in [("Type", "Funcional"), ("Priority", "Media"), ("Estado", "Pendiente")]:
                        if c not in df_sugerencias.columns:
                            df_sugerencias[c] = dflt

                    st.session_state["sugerencias_df"] = df_sugerencias
                    st.success("✅ Sugerencias generadas.")
                except Exception as e:
                    st.error(f"❌ Error al generar sugerencias: {e}")

    # Render de sugerencias si existen
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

                # Evitar duplicados por Title contra el DF actual
                titulos_existentes = set(st.session_state["df_editable"]["Title"].astype(str))
                df_aplicar = df_aplicar[~df_aplicar["Title"].astype(str).isin(titulos_existentes)]

                if df_aplicar.empty:
                    st.info("ℹ️ Todos los seleccionados ya estaban aplicados o no hay nuevos.")
                else:
                    # Alinear columnas con df_editable
                    cols_destino = list(st.session_state["df_editable"].columns)
                    for c in cols_destino:
                        if c not in df_aplicar.columns:
                            df_aplicar[c] = ""  # relleno vacío para columnas faltantes
                    df_aplicar = df_aplicar[cols_destino]

                    # Actualiza el DF principal
                    st.session_state["df_editable"] = pd.concat(
                        [st.session_state["df_editable"], df_aplicar], ignore_index=True
                    )
                    st.session_state["generado"] = True

                    # Guarda en historial
                    st.session_state.setdefault("historial_generaciones", [])
                    st.session_state["historial_generaciones"].append({
                        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "origen": "Sugerencias",
                        "escenarios": df_aplicar.copy()
                    })

                    st.success(f"✅ {len(df_aplicar)} escenario(s) aplicados. Revisa 'Historial' y 'Subir a TestRail'.")
            except Exception as e:
                st.error(f"❌ Error al aplicar sugerencias: {e}")


# --------------------------- TAB 4: HISTORIAL ---------------------------
with tab4:
    if "historial_generaciones" not in st.session_state:
        st.session_state["historial_generaciones"] = []

    historial = st.session_state["historial_generaciones"]

    if not historial:
        st.info(
            "ℹ️ Aún no hay historial disponible. Genera escenarios para comenzar a registrar."
        )
    else:
        resumen = pd.DataFrame(
            [
                {
                    "Fecha": item["fecha"],
                    "Fuente": f"{item.get('fuente', 'Desconocida')} ({item.get('origen', 'N/A')})",
                    "Escenarios": len(item["escenarios"]),
                    "Ver": f"📝 Ver #{i}",
                }
                for i, item in enumerate(historial)
            ]
        )

        st.markdown("### 🧾 Generaciones previas")
        st.dataframe(resumen, use_container_width=True, hide_index=True)

        seleccion = st.selectbox(
            "Selecciona una generación para revisar:",
            options=[
                f"#{i+1} | {item['fecha']} ({item.get('fuente', 'N/A')})"
                for i, item in enumerate(historial)
            ],
            index=len(historial) - 1,
        )

        idx = int(seleccion.split("|")[0].replace("#", "")) - 1
        item = historial[idx]

        if st.button("↩ Restaurar esta generación"):
            st.session_state.df_editable = item["escenarios"].copy()
            st.success("✅ Escenarios restaurados.")
            st.rerun()

# --------------------------- TAB 5: SUBIR A TESTRAIL ---------------------------
# --------------------------- TAB 5: SUBIR A TESTRAIL ---------------------------
with tab5:
    st.subheader("🚀 Subir casos a TestRail")

    # 📡 Obtener proyectos desde TestRail
    proyectos_raw = obtener_proyectos()

    # 🛡️ Validación segura del formato
    if isinstance(proyectos_raw, dict) and "projects" in proyectos_raw:
        proyectos = proyectos_raw["projects"]
    else:
        st.error("❌ Formato inesperado al recibir proyectos.")
        st.stop()

    # 🎛️ Selector de proyecto
    sel_proy = st.selectbox("Proyecto", [p["name"] for p in proyectos], key="select_proy")
    id_proy = next((p["id"] for p in proyectos if p["name"] == sel_proy), None)

    # 📢 Mostrar anuncio del proyecto (si existe)
    anuncio = next((p.get("announcement") for p in proyectos if p["id"] == id_proy), None)
    if anuncio:
        st.info(f"📢 {anuncio}")

    # 📁 Obtener suites del proyecto
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

    # 📂 Obtener secciones de la suite
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

    # ✅ Validar si hay escenarios generados para subir
    df = st.session_state.get("df_editable")

    if df is not None and section_id:
        st.markdown("### 🧪 Vista previa de los casos a subir")
        st.dataframe(df, use_container_width=True)

        # —————————————————— CONFIRMACIÓN EN DOS PASOS ——————————————————
        # 1) Primer click: pedir confirmación y guardar selección
        if st.button("📤 Subir casos a TestRail", key="btn_subir_preconfirm"):
            st.session_state["confirm_subida"] = {
                "proyecto": sel_proy,
                "suite": sel_suite,
                "seccion": sel_seccion,
                "section_id": section_id,
                "total": len(df)
            }
            st.rerun()

        # 2) Si hay confirmación pendiente, mostrar resumen + Confirmar/Cancelar
        confirm_ctx = st.session_state.get("confirm_subida")
        if confirm_ctx:
            st.markdown("#### 🔎 Confirma antes de subir")
            st.info(
                f"**Proyecto:** {confirm_ctx['proyecto']}\n\n"
                f"**Suite:** {confirm_ctx['suite']}\n\n"
                f"**Sección:** {confirm_ctx['seccion']}\n\n"
                f"**Casos a subir:** {confirm_ctx['total']}"
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirmar subida", key="btn_confirmar_subida"):
                    with st.spinner("📡 Subiendo casos..."):
                        resultado = enviar_a_testrail(confirm_ctx["section_id"], df)  # usa mapping title/custom_*

                    # Limpiar estado de confirmación
                    st.session_state.pop("confirm_subida", None)

                    if resultado["exito"]:
                        st.success(f"✅ {resultado['subidos']} casos subidos correctamente.")
                        st.rerun()
                    else:
                        st.error(f"❌ Solo se subieron {resultado['subidos']} de {resultado['total']} casos.")
                        if resultado["detalle"]:
                            with st.expander("🔍 Ver detalles del error"):
                                for err in resultado["detalle"]:
                                    st.write(err)
            with c2:
                if st.button("❌ Cancelar", key="btn_cancelar_subida"):
                    st.session_state.pop("confirm_subida", None)
                    st.toast("Operación cancelada", icon="❌")
                    st.rerun()
        # ——————————————————————————————————————————————————————————————
    else:
        st.info("Genera los casos en el Tab '✏️ Generar' y selecciona Proyecto, Suite y Sección.")
