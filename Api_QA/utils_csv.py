import io
import csv
import pandas as pd
import streamlit as st
import datetime
import re
from io import StringIO


def limpiar_csv_con_formato(texto_csv: str, columnas_esperadas: int = 6) -> str:
    import csv, io

    lineas = texto_csv.strip().split("\n")
    filas_validas = []

    reader = csv.reader(lineas, skipinitialspace=True)
    for fila in reader:
        if len(fila) == columnas_esperadas:
            filas_validas.append([campo.replace("\n", " ").strip() for campo in fila])

    if not filas_validas:
        raise ValueError("❌ Gemini generó CSV inválido o vacío.")

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerows(filas_validas)

    return output.getvalue()




def leer_csv_seguro(texto_csv: str, columnas_esperadas: int = 4) -> pd.DataFrame:
    f = StringIO(texto_csv)
    reader = csv.reader(f, quotechar='"', escapechar='\\')
    filas_validas = [row for row in reader if len(row) == columnas_esperadas]

    if not filas_validas:
        raise ValueError("❌ El CSV no contiene filas válidas.")

    return pd.DataFrame(filas_validas[1:], columns=filas_validas[0])


def corregir_csv_con_comas(texto_csv: str, columnas_objetivo: int = 6) -> str:
    """
    Encierra en comillas los campos de cada línea si hay columnas de más o mal separadas.
    """
    import csv
    import io

    lineas = texto_csv.strip().split("\n")
    corregido = []

    for linea in lineas:
        campos = list(csv.reader([linea]))[0]

        if len(campos) != columnas_objetivo:
            # Encierra todo campo entre comillas si no lo está
            campos = [f'"{campo.strip()}"' if not campo.strip().startswith('"') else campo for campo in campos]
            nueva_linea = ",".join(campos)
            corregido.append(nueva_linea)
        else:
            corregido.append(linea)

    return "\n".join(corregido)


def normalizar_steps(steps):
    if not isinstance(steps, str):
        return ""
    pasos_separados = re.sub(r'\s*(\d+\.\s)', r'\n\1', steps).strip()
    return pasos_separados



def validar_lineas_csv(texto_csv: str, columnas_esperadas: int) -> str:
    lineas = texto_csv.strip().splitlines()
    filtradas = [l for l in lineas if l.count(",") == columnas_esperadas - 1]
    return "\n".join(filtradas)



def limpiar_csv_sugerencias(csv_text, columnas_esperadas=4):
    """
    Elimina líneas que no tengan el número correcto de columnas.
    """
    lineas = csv_text.strip().splitlines()
    resultado = []

    for linea in lineas:
        partes = list(csv.reader([linea]))[0]
        if len(partes) == columnas_esperadas:
            resultado.append(",".join(partes))

    return "\n".join(resultado)



    """
    Convierte un texto plano separado por puntos o comas en una lista numerada con saltos de línea.
    """
    if not texto or not isinstance(texto, str):
        return texto

    delimitadores = [". ", "; ", "\n"]
    for delim in delimitadores:
        if delim in texto:
            partes = [p.strip() for p in texto.split(delim) if p.strip()]
            break
    else:
        partes = [texto.strip()]

    return "\n".join([f"{i+1}. {parte}" for i, parte in enumerate(partes)])


def limpiar_markdown_csv(respuesta):
    """
    Elimina delimitadores Markdown y valida que haya contenido CSV real.
    """
    if "```csv" in respuesta:
        partes = respuesta.split("```csv")
        respuesta = partes[1] if len(partes) > 1 else ""

    if "```" in respuesta:
        respuesta = respuesta.split("```")[0]

    respuesta = respuesta.strip()

    # Validar que tenga al menos una coma (separador CSV)
    if "," not in respuesta:
        return ""

    return respuesta




def generar_csv_descargable(csv_raw):
    """
    Ordena los escenarios por prioridad y devuelve un archivo CSV descargable.
    """
    df = pd.read_csv(io.StringIO(csv_raw))
    
    # Orden descendente por prioridad (Alta > Media > Baja)
    prioridad_orden = {"Alta": 3, "Media": 2, "Baja": 1}
    df["orden"] = df["Priority"].map(prioridad_orden)
    df = df.sort_values(by="orden", ascending=False).drop(columns=["orden"])

    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()

def validar_csv_qa(csv_raw):
    lines = csv_raw.strip().splitlines()
    header_line = lines[0].replace("\t", ",").strip()
    header = [h.strip() for h in header_line.split(",")]

    expected_cols = ["Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"]

    if header != expected_cols:
        raise ValueError(f"❌ Las columnas del CSV no coinciden con el formato requerido.\nSe recibió: {header}")
    
    for i, line in enumerate(lines[1:], start=2):
        row = list(csv.reader([line]))[0]
        if len(row) != len(expected_cols):
            raise ValueError(f"❌ Fila {i} tiene {len(row)} columnas, se esperaban {len(expected_cols)}.")
        if any(not cell.strip() for cell in row):
            raise ValueError(f"⚠️ Fila {i} tiene campos vacíos.")

    return True


# 🔍 Extraer solo el contenido del CSV
def extraer_csv(texto_generado):
    """
    Recorta encabezados o texto adicional fuera del CSV, dejando solo la tabla.
    """
    lineas = texto_generado.strip().split("\n")
    lineas_csv = []

    encabezados = ["Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"]
    encabezado_detectado = False

    for linea in lineas:
        if not encabezado_detectado and all(col in linea for col in encabezados):
            encabezado_detectado = True

        if encabezado_detectado:
            lineas_csv.append(linea)

    return "\n".join(lineas_csv)


# 🛡️ Corregir CSV con comas internas mal escapadas
def corregir_csv_con_comas(texto_csv, columnas_objetivo):
    """
    Encierra en comillas los campos de cada línea si la cantidad de columnas no coincide.
    """
    lineas = texto_csv.strip().split("\n")
    corregido = []

    for linea in lineas:
        campos = list(csv.reader([linea]))[0]

        if len(campos) != columnas_objetivo:
            campos = [f'"{campo.strip()}"' if not campo.strip().startswith('"') else campo for campo in campos]
            nueva_linea = ",".join(campos)
            corregido.append(nueva_linea)
        else:
            corregido.append(linea)

    return "\n".join(corregido)


# 🧪 Convertir el CSV en DataFrame blindado
def procesar_csv_seguro(csv_raw, columnas_esperadas=6):
    """
    Convierte un CSV generado por Gemini en un DataFrame limpio y lo guarda en session_state.
    """
    if not csv_raw or not csv_raw.strip():
        st.error("❌ El CSV recibido está vacío.")
        st.session_state.df_editable = None
        st.session_state.generado = False
        return

    try:
        csv_limpio = extraer_csv(csv_raw)
    except Exception as e:
        st.error("❌ Error al limpiar el CSV.")
        st.text_area("Respuesta cruda", csv_raw, height=300)
        return

    try:
        csv_corregido = corregir_csv_con_comas(csv_limpio, columnas_esperadas)
        df = pd.read_csv(io.StringIO(csv_corregido))

        columnas_clave = ["Title", "Preconditions", "Steps", "Expected Result", "Type", "Priority"]
        for col in columnas_clave:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].fillna("").astype(str)

        if "Steps" in df.columns:
            df["Steps"] = df["Steps"].apply(lambda t: str(t).replace("\\n", "\n").strip())

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.historial.append({"ts": ts, "df": df})
        st.session_state.df_editable = df
        st.session_state.ultimo_ts = ts
        st.session_state.generado = True

        st.success(f"✅ Se generaron {len(df)} escenarios.")
        st.dataframe(df)

    except Exception as e:
        st.error(f"❌ Error al procesar CSV: {e}")
        st.text_area("CSV corregido", csv_corregido, height=300)
        st.session_state.df_editable = None
        st.session_state.generado = False


def corregir_csv_gemini(csv_raw):
    """
    Limpia y corrige el CSV generado por Gemini para que tenga el número correcto de columnas.
    """
    lines = csv_raw.strip().splitlines()
    header = lines[0].split(",")
    num_cols = len(header)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(header)

    for line in lines[1:]:
        row = list(csv.reader([line]))[0]
        if len(row) == num_cols:
            writer.writerow(row)
        else:
            # Intenta recomponer la fila si tiene comas internas
            fixed_row = []
            buffer = ""
            for item in row:
                buffer += item
                if buffer.count('"') % 2 == 0:
                    fixed_row.append(buffer.strip())
                    buffer = ""
            if len(fixed_row) == num_cols:
                writer.writerow(fixed_row)

    return output.getvalue()