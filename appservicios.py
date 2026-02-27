import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Registro de Tickets", layout="wide")

st.title("📋 Registro de Consultas y Tickets")

# 1. Configuración de la URL (ID de tu hoja)
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"

# 2. Crear la conexión
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. --- FORMULARIO DE INGRESO ---
with st.expander("➕ Cargar Nuevo Ticket / Consulta", expanded=True):
    with st.form("ticket_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            id_ticket = st.text_input("ID Ticket")
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo de Consulta", ["Funcional", "Técnica", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])

        with col2:
            atencion = st.selectbox("Atención", ["Telefónica", "Wasapp", "Meet", "Visita"])
            clientes = st.text_input("Cliente")
            usuario = st.text_input("Usuario")
            modulo = st.selectbox("Módulo", ["Accesos", "Administracion", "Contabilidad", "Compras", "Ventas", "Logistica", "Eccomerce", "Mails", "Programa", "Produccion","Servidor", "Web", "Gerencial", "RRHH", "Sucursal", "Otros"])
            online = st.checkbox("¿Se resolvió Online?")

        with col3:
            fe_consult = st.date_input("Fecha Consulta", datetime.now())
            fe_rta = st.date_input("Fecha Respuesta", datetime.now())
            tiempo_res = st.number_input("Tiempo Respuesta (horas/min)", min_value=0)

        st.divider()
        consultas = st.text_area("Detalle de la Consulta")
        respuestas = st.text_area("Detalle de la Respuesta")

        enviar = st.form_submit_button("Guardar Registro")

    if enviar:
        # 1. Crear el DataFrame con el nuevo registro
        # Usamos los nombres exactos de tus columnas de Excel
        df_nuevo = pd.DataFrame([{
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
        }])

        try:
            # 2. Leer datos existentes de la pestaña específica
            df_existente = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios")
            
            # 3. Combinar datos nuevos con existentes
            df_actualizado = pd.concat([df_existente, df_nuevo], ignore_index=True)
            
            # 4. Guardar en Google Sheets
            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actualizado)
            
            st.balloons()
            st.success("✅ ¡Registro guardado exitosamente en BD_Dashboard_Servicios!")
            
        except Exception as e:
            st.error(f"❌ Error al conectar o guardar: {e}")
