import streamlit as st
from contextlib import contextmanager

# 🎛️ Título de sección
def titulo_seccion(texto, emoji="🔧"):
    st.markdown(f"### {emoji} {texto}")

# 📦 Botón con ícono
def boton_con_icono(label, emoji="🚀"):
    return st.button(f"{emoji} {label}")

# 📋 Tabs personalizados con emojis
def crear_tabs(titulos_emojis):
    return st.tabs([f"{emoji} {titulo}" for titulo, emoji in titulos_emojis])

# 📝 TextArea estilizado
def textarea_estilizada(titulo, contenido="", altura=250):
    st.text_area(titulo, value=contenido, height=altura)

# ⚠️ Alerta visual de advertencia
def alerta_advertencia(texto):
    st.warning(f"⚠️ {texto}")

# 🧠 Spinner con mensaje visual
class SpinnerAccion:
    def __init__(self, mensaje):
        self.mensaje = mensaje

    def __enter__(self):
        self.spinner = st.spinner(self.mensaje)
        self.spinner.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.spinner.__exit__(exc_type, exc_val, exc_tb)

def spinner_accion(mensaje):
    return SpinnerAccion(mensaje)
