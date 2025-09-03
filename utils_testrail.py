import requests
import pandas as pd
import streamlit as st

# 🔐 Obtener credenciales desde .streamlit/secrets.toml
TESTRAIL_DOMAIN = st.secrets["testrail_url"]
TESTRAIL_USER = st.secrets["testrail_email"]
TESTRAIL_API_KEY = st.secrets["testrail_api_key"]

HEADERS = {
    "Content-Type": "application/json"
}
AUTH = (TESTRAIL_USER, TESTRAIL_API_KEY)

# 🧩 Obtener lista de proyectos
def obtener_proyectos():
    url = f"{TESTRAIL_DOMAIN}/index.php?/api/v2/get_projects"
    try:
        response = requests.get(url, auth=AUTH)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"❌ Error al obtener proyectos: {e}")
        return None

# 📁 Obtener suites de un proyecto
def obtener_suites(project_id):
    url = f"{TESTRAIL_DOMAIN}/index.php?/api/v2/get_suites/{project_id}"
    try:
        response = requests.get(url, auth=AUTH)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"❌ Error al obtener suites: {e}")
        return None

# 📂 Obtener secciones de una suite
def obtener_secciones(project_id, suite_id):
    url = f"{TESTRAIL_DOMAIN}/index.php?/api/v2/get_sections/{project_id}&suite_id={suite_id}"
    try:
        response = requests.get(url, auth=AUTH)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"❌ Error al obtener secciones: {e}")
        return None

# 🚀 Subir casos de prueba a TestRail
def enviar_a_testrail(section_id, dataframe: pd.DataFrame):
    url = f"{TESTRAIL_DOMAIN}/index.php?/api/v2/add_case/{section_id}"
    exitosos = 0
    errores = []

    for i, fila in dataframe.iterrows():
        datos = {
            "title": fila.get("Title", "Caso sin título"),
            "custom_preconds": fila.get("Preconditions", ""),
            "custom_steps": fila.get("Steps", ""),
            "custom_expected": fila.get("Expected Result", ""),
            "custom_type": fila.get("Type", "Funcionalidad"),
            "custom_priority": fila.get("Priority", "Alta")
        }

        try:
            response = requests.post(url, headers=HEADERS, auth=AUTH, json=datos)
            if response.status_code == 200:
                exitosos += 1
            else:
                errores.append(f"Fila {i}: {response.status_code} - {response.text}")
        except Exception as e:
            errores.append(f"Fila {i}: {e}")

    exito_total = exitosos == len(dataframe)
    return {
        "exito": exito_total,
        "subidos": exitosos,
        "total": len(dataframe),
        "detalle": errores if errores else None
    }
