import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Sistema de Tickets - Servicios", layout="wide")

# URL de tu Google Sheets (Recuerda que debe estar en "Cualquier persona con el enlace")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/edit?gid=0#gid=0"

# Establecemos la conexión
conn = st.connection("gsheets", type=GSheetsConnection)

st.title("📋 Registro de Consultas y Tickets")
st.info(f"Conectado a la hoja: BD_Dashboard_Servicios")

# --- FORMULARIO DE INGRESO ---
with st.expander("➕ Cargar Nuevo Ticket / Consulta", expanded=True):
    with st.form("ticket_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            id_ticket = st.text_input("ID Ticket")
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo de Consulta", ["Técnica", "Funcional", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])

        with col2:
            atencion = st.text_input("Atención")
            clientes = st.text_input("Cliente")
            usuario = st.text_input("Usuario")
            modulo = st.text_input("Módulo")
            online = st.checkbox("¿Es consulta Online?")

        with col3:
            fe_consult = st.date_input("Fecha Consulta", datetime.now())
            fe_rta = st.date_input("Fecha Respuesta", datetime.now())
            tiempo_res = st.number_input("Tiempo Respuesta (horas/min)", min_value=0)

        st.divider()
        consultas = st.text_area("Detalle de la Consulta")
        respuestas = st.text_area("Detalle de la Respuesta")

        enviar = st.form_submit_button("Guardar Registro")

    if enviar:
        # Registro a insertar
        nuevo_registro = {
            "ID_TICKET": id_ticket,
            "CONSULTOR": consultor,
            "TIPO_CONS": tipo_cons,
            "PRIORIDAD": prioridad,
            "ESTADO": estado,
            "ATENCION": atencion,
            "CLIENTES": clientes,
            "USUARIO": usuario,
            "FE_CONSULT": str(fe_consult),
            "FE_RTA": str(fe_rta),
            "MODULO": modulo,
            "CONSULTAS": consultas,
            "RESPUESTAS": respuestas,
            "TIEMPO_RES": tiempo_res,
            "ONLINE": "SI" if online else "NO",
            "ANIO": fe_consult.year,
            "MES": fe_consult.month
        }
        
        # 1. Leer los datos actuales de la pestaña específica
        df_existente = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios")
        
        # 2. Agregar el nuevo registro
        df_nuevo = pd.DataFrame([nuevo_registro])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        
        # 3. Actualizar la hoja en la nube (Requiere configuración de Secrets en Streamlit Cloud)
        # conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
        
        st.success(f"Ticket {id_ticket} guardado en BD_Dashboard_Servicios")
        st.balloons()

# --- VISTA DEL DASHBOARD ---
st.divider()
st.subheader("📊 Datos en Tiempo Real")

# Leemos específicamente la hoja mencionada para mostrar la tabla
df_vista = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios")

if not df_vista.empty:
    st.dataframe(df_vista, use_container_width=True)
    
    # Ejemplo de gráfico rápido: Tickets por Estado
    st.subheader("Resumen por Estado")
    estado_count = df_vista["ESTADO"].value_counts()
    st.bar_chart(estado_count)
else:
    st.warning("La hoja BD_Dashboard_Servicios está vacía o no se encuentra.")
