# utils_testrail.py
import requests
import streamlit as st

def _testrail_cfg():
    """
    Devuelve credenciales de TestRail desde st.secrets.
    Se espera en .streamlit/secrets.toml:
        testrail_url = "https://..."
        testrail_email = "usuario@empresa.com"
        testrail_api_key = "API_KEY"
    """
    url   = st.secrets.get("testrail_url")
    email = st.secrets.get("testrail_email")
    api_key = st.secrets.get("testrail_api_key")

    missing = [k for k, v in {
        "testrail_url": url, "testrail_email": email, "testrail_api_key": api_key
    }.items() if not v]
    if missing:
        st.error(f"❌ Faltan claves en secrets.toml: {', '.join(missing)}")
        st.stop()

    return {"url": url, "email": email, "api_key": api_key}


def _auth_headers(cfg):
    return {
        "Content-Type": "application/json",
    }, (cfg["email"], cfg["api_key"])


# Ejemplos de funciones usando esa config
def obtener_proyectos():
    cfg = _testrail_cfg()
    headers, auth = _auth_headers(cfg)
    resp = requests.get(f"{cfg['url']}/index.php?/api/v2/get_projects", headers=headers, auth=auth)
    if resp.status_code != 200:
        st.error(f"Error obteniendo proyectos: {resp.status_code} - {resp.text}")
        return []
    return resp.json()


def obtener_suites(project_id: int):
    cfg = _testrail_cfg()
    headers, auth = _auth_headers(cfg)
    resp = requests.get(f"{cfg['url']}/index.php?/api/v2/get_suites/{project_id}", headers=headers, auth=auth)
    return resp.json()


def obtener_secciones(project_id: int, suite_id: int):
    cfg = _testrail_cfg()
    headers, auth = _auth_headers(cfg)
    resp = requests.get(f"{cfg['url']}/index.php?/api/v2/get_sections/{project_id}&suite_id={suite_id}", headers=headers, auth=auth)
    return resp.json()


def enviar_a_testrail(suite_id: int, section_id: int, cases: list):
    """
    cases = [
        {"title": "...", "custom_preconds": "...", "custom_steps": "..."}
    ]
    """
    cfg = _testrail_cfg()
    headers, auth = _auth_headers(cfg)

    results = []
    for case in cases:
        payload = {
            "title": case.get("title", ""),
            "custom_preconds": case.get("custom_preconds", ""),
            "custom_steps": case.get("custom_steps", "")
        }
        resp = requests.post(
            f"{cfg['url']}/index.php?/api/v2/add_case/{section_id}",
            headers=headers, auth=auth, json=payload
        )
        if resp.status_code == 200:
            results.append(resp.json())
        else:
            st.error(f"Error creando caso: {resp.status_code} - {resp.text}")
    return results


