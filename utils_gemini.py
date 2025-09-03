import streamlit as st
import requests
import certifi
import re
import csv
import io
import csv
import io
import os
import argparse
import streamlit as st
import pandas as pd
import time

from debug_fallback import modo_recuperacion_debug


def prompt_generar_escenarios_profesionales(descripcion_refinada):
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Eres un Analista QA Senior experto en diseño de pruebas funcionales para sistemas empresariales.\n\n"
                            "A partir de la siguiente descripción funcional, genera una tabla en formato **CSV puro**, SIN explicaciones, SIN encabezados adicionales, y SIN comentarios externos.\n\n"
                            "La tabla debe tener exactamente las siguientes columnas:\n"
                            "Title,Preconditions,Steps,Expected Result,Type,Priority\n\n"
                            "🎯 INSTRUCCIONES ESTRICTAS:\n"
                            "- NO escribas texto adicional fuera del CSV.\n"
                            "- NO incluyas cabeceras como 'Escenarios sugeridos:' ni bloques explicativos.\n"
                            "- En 'Preconditions', escribe condiciones reales, no uses 'Ninguna'. Ejemplos:\n"
                            "    • Usuario con sesión iniciada\n"
                            "    • Cliente registrado con movimientos\n"
                            "    • Navegador abierto con filtros activos\n"
                            "- En 'Steps', usa numeración clara: 1. 2. 3. (separadas por punto y espacio)\n"
                            "- Si alguna celda contiene comas, encierra su contenido entre comillas dobles (\"\").\n"
                            "- Usa solo estos valores en 'Type': Funcional, Validación, Seguridad, Usabilidad\n"
                            "- Usa solo estos valores en 'Priority': Alta, Media, Baja\n"
                            "- Todos los escenarios deben ser específicos, profesionales y relacionados directamente con la descripción.\n"
                            "- Genera entre **8 y 12 escenarios distintos**, que incluyan:\n"
                            "    • 1 escenario exitoso (Happy Path)\n"
                            "    • 4-6 escenarios negativos (errores, entradas inválidas, omisiones)\n"
                            "    • 1-2 de Seguridad o Edge Cases\n"
                            "    • 1-2 de Usabilidad o persistencia\n\n"
                            f"📄 Descripción funcional:\n{descripcion_refinada}"
                        )
                    }
                ]
            }
        ]
    }






def prompt_sugerencias_mejora(texto_funcional):
    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Actúa como Analista QA Senior.\n"
                            "Analiza el siguiente texto funcional y genera entre 5 y 10 sugerencias claras para mejorarlo, "
                            "enfocándote en facilitar la generación de escenarios de prueba automatizados.\n\n"
                            "🎯 Las sugerencias deben centrarse en:\n"
                            "- Claridad y especificidad técnica\n"
                            "- Inclusión de validaciones de campos\n"
                            "- Casos límite o alternativos\n"
                            "- Precondiciones explícitas del sistema o del usuario\n"
                            "- Mejorar la redacción hacia comportamiento verificable\n\n"
                            f"📄 Texto funcional:\n{texto_funcional}"
                        )
                    }
                ]
            }
        ]
    }


def generar_sugerencias_con_gemini(texto_funcional):
    prompt = prompt_sugerencias_mejora(texto_funcional)
    respuesta = enviar_a_gemini(prompt)
    texto_sugerencias = extraer_texto_de_respuesta_gemini(respuesta)

    # Separar por líneas o viñetas
    sugerencias = [
        linea.strip("•-1234567890. ") for linea in texto_sugerencias.strip().split("\n")
        if len(linea.strip()) > 5
    ]

    return sugerencias



def respuesta_es_valida(respuesta_json: dict) -> bool:
    """
    Verifica si la respuesta de Gemini contiene la estructura esperada.
    """
    return (
        isinstance(respuesta_json, dict)
        and "candidates" in respuesta_json
        and len(respuesta_json["candidates"]) > 0
        and "content" in respuesta_json["candidates"][0]
        and "parts" in respuesta_json["candidates"][0]["content"]
    )



def extraer_texto_de_respuesta_gemini(respuesta_json: dict) -> str:
    """
    Extrae texto plano desde respuesta Gemini JSON.
    Remueve bloques markdown y limpia espacios innecesarios.
    """
    try:
        texto = respuesta_json['candidates'][0]['content']['parts'][0]['text']

        # Quitar bloques Markdown ```csv ```
        if '```csv' in texto:
            texto = texto.split('```csv')[1]
        if '```' in texto:
            texto = texto.split('```')[0]

        # Limpiar líneas vacías y espacios extras
        lineas = [line.strip() for line in texto.strip().splitlines() if line.strip()]
        return "\n".join(lineas)

    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"❌ No se pudo extraer texto de Gemini: {e}")

def generar_prompt_csv_robusto(texto_funcional):
    prompt = f"""
Actúa como un analista de QA experto.

Genera 3 escenarios de prueba funcionales en formato CSV, usando exactamente estas columnas:
Title,Preconditions,Steps,Expected Result,Type,Priority

⚠️ Instrucciones estrictas:
- No expliques nada.
- No uses formato Markdown.
- Usa comas como separadores.
- Cada línea debe tener contenido realista, técnico y profesional.
- Sin encabezados duplicados. Solo la tabla.

Texto funcional:
\"\"\"{texto_funcional}\"\"\"
    """.strip()
    return prompt


def validar_respuesta_gemini(texto_csv, columnas_esperadas=6):
    lineas = texto_csv.strip().split("\n")
    casos_validos = []

    for i, linea in enumerate(lineas):
        partes = [p.strip() for p in linea.split(",")]
        if len(partes) == columnas_esperadas and all(partes):
            casos_validos.append(linea)

    return casos_validos


def invocar_con_reintento(prompt, max_intentos=3, espera_inicial=2):
    from utils_gemini import llamar_a_gemini
    import time

    for intento in range(1, max_intentos + 1):
        try:
            resultado = llamar_a_gemini(prompt)
            if isinstance(resultado, tuple):
                resultado = resultado[0]
            return resultado
        except ValueError as e:
            if "503" in str(e) and intento < max_intentos:
                time.sleep(espera_inicial * intento)
            else:
                raise


def activar_modo_recuperacion(respuesta_cruda, columnas_esperadas=6):
    st.error("❌ Gemini respondió, pero no generó escenarios válidos con los campos requeridos.")
    st.text_area("📄 Respuesta cruda de Gemini", respuesta_cruda, height=300)
    return modo_recuperacion_debug(respuesta_cruda, columnas_esperadas=columnas_esperadas)


def enviar_a_gemini(prompt_dict, max_intentos=4, espera_inicial=2):

    API_KEY = st.secrets["gemini_api_key"]
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": API_KEY
    }

    intentos = 0
    while intentos < max_intentos:
        try:
            response = requests.post(url, headers=headers, json=prompt_dict)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 503:
                # Si es 503, espera un momento y reintenta
                espera = espera_inicial * (intentos + 1)
                st.warning(f"⚠️ Gemini está saturado (503). Reintentando en {espera} segundos... (Intento {intentos+1}/{max_intentos})")
                time.sleep(espera)
                intentos += 1
            else:
                # Otros errores HTTP, se lanza inmediatamente
                raise ValueError(f"❌ Error HTTP al invocar Gemini: {e}")
        except Exception as e:
            raise ValueError(f"❌ Error general al invocar Gemini: {e}")

    # Si fallaron todos los intentos
    raise ValueError("❌ Gemini no respondió tras varios intentos (503 repetidos).")


def prompt_refinar_descripcion(texto_funcional):
    return {
        "contents": [{
            "parts": [{
                "text": (
                    "Eres un analista experto en QA. Debes reestructurar claramente la siguiente descripción funcional "
                    "en formato técnico y profesional, preparándola para que luego se generen escenarios de prueba. "
                    "Obligatoriamente incluye estas tres secciones claramente separadas y completas:\n\n"
                    "- Módulo: (Nombre breve del módulo o componente involucrado)\n"
                    "- Función: (Acción principal que permite esta funcionalidad)\n"
                    "- Detalle técnico del comportamiento esperado: (Breve pero clara descripción técnica de cómo debería funcionar exactamente la funcionalidad)\n\n"
                    "📌 Ejemplo claro:\n"
                    "- Módulo: Registro de usuarios\n"
                    "- Función: Permitir que usuarios nuevos se registren\n"
                    "- Detalle técnico del comportamiento esperado: El formulario validará campos obligatorios como usuario, correo y contraseña. Se mostrará un mensaje de éxito al completar correctamente el registro y mensajes específicos en caso de error en cualquier validación.\n\n"
                    f"⚠️ Ahora reestructura profesionalmente el siguiente texto:\n\n{texto_funcional}"
                )
            }]
        }]
    }

def obtener_descripcion_refinada(texto_funcional, max_intentos=3):
    intentos = 0
    while intentos < max_intentos:
        respuesta_estructurada = enviar_a_gemini(prompt_refinar_descripcion(texto_funcional))
        descripcion_refinada = extraer_texto_de_respuesta_gemini(respuesta_estructurada).strip()

        if descripcion_refinada:
            return descripcion_refinada

        intentos += 1
        time.sleep(1)  # pequeño retardo antes de reintentar

    # si llega aquí, todos los intentos fallaron
    raise ValueError("⚠️ Gemini no devolvió descripción válida tras varios intentos.")