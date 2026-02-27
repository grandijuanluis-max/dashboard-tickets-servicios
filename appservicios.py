import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets", layout="wide")

st.title("📋 Sistema de Gestión de Consultas y Tickets")

# 1. Configuración de la URL y Conexión
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Leer datos actuales para cálculos (ID y Modificación)
try:
    df_actual = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios")
except Exception:
    df_actual = pd.DataFrame()

# --- PESTAÑAS PARA ORGANIZAR LA PANTALLA ---
tab1, tab2 = st.tabs(["➕ Nuevo Ticket", "✏️ Modificar Ticket Pendiente"])

# ==========================================
# TAB 1: CARGA DE NUEVO TICKET (CON ID AUTO Y FECHAS AUTO)
# ==========================================
with tab1:
    # Lógica de ID Automático
    if not df_actual.empty:
        ultimo_id = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').max()
        proximo_id = int(ultimo_id) + 1 if not pd.isna(ultimo_id) else 1
    else:
        proximo_id = 1

    st.subheader(f"Cargando Ticket N°: {proximo_id}")
    
    with st.form("nuevo_ticket_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"ID Ticket: {proximo_id}")
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo de Consulta", ["Funcional", "Técnica", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])

        with col2:
            atencion = st.selectbox("Atención", ["Telefónica", "Wasapp", "Meet", "Visita"])
            clientes = st.text_input("Cliente")
            usuario = st.text_input("Usuario")
            modulo = st.selectbox("Módulo", ["Accesos", "Administracion", "Contabilidad", "Compras", "Ventas", "Logistica", "Eccomerce", "Mails", "Programa", "Produccion","Servidor", "Web", "Gerencial", "RRHH", "Sucursal", "Impuestos", "Otros"])
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
        # Aquí se extrae automáticamente el Año y el Mes de la fecha seleccionada
        df_nuevo = pd.DataFrame([{
            "ID_TICKET": proximo_id,
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
            "ANIO": fe_consult.year,  # Automatización del Año
            "MES": fe_consult.month    # Automatización del Mes
        }])

        try:
            df_actualizado = pd.concat([df_actual, df_nuevo], ignore_index=True)
            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actualizado)
            st.balloons()
            st.success(f"✅ Ticket #{proximo_id} guardado con éxito. El año ({fe_consult.year}) y mes ({fe_consult.month}) se registraron automáticamente.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# ==========================================
# TAB 2: MODIFICAR TICKET (ABIERTOS/EN PROCESO)
# ==========================================
with tab2:
    st.subheader("Modificar Tickets Pendientes")
    
    if not df_actual.empty:
        tickets_pendientes = df_actual[df_actual["ESTADO"].isin(["Abierto", "En Proceso"])]
        
        if not tickets_pendientes.empty:
            opciones = tickets_pendientes.apply(lambda x: f"ID: {x['ID_TICKET']} - Cliente: {x['CLIENTES']}", axis=1).tolist()
            seleccion = st.selectbox("Selecciona el ticket a modificar:", opciones)
            
            id_a_editar = int(seleccion.split(" - ")[0].replace("ID: ", ""))
            datos_ticket = df_actual[df_actual["ID_TICKET"].astype(int) == id_a_editar].iloc[0]

            with st.form("edit_form"):
                st.write(f"✏️ Editando Ticket ID: {id_a_editar}")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    nuevo_estado = st.selectbox("Actualizar Estado", ["Abierto", "En Proceso", "Cerrado"], 
                                                index=["Abierto", "En Proceso", "Cerrado"].index(datos_ticket["ESTADO"]))
                    nueva_prioridad = st.select_slider("Actualizar Prioridad", options=["Baja", "Media", "Alta"],
                                                       value=datos_ticket["PRIORIDAD"])
                with col_e2:
                    nueva_rta_fecha = st.date_input("Fecha Respuesta Actualizada", datetime.now())
                    nuevo_tiempo = st.number_input("Tiempo Total (horas/min)", value=int(datos_ticket["TIEMPO_RES"]))

                nuevas_respuestas = st.text_area("Actualizar Detalle de la Respuesta", value=datos_ticket["RESPUESTAS"])
                
                boton_actualizar = st.form_submit_button("Actualizar y Guardar Cambios")

            if boton_actualizar:
                try:
                    idx = df_actual.index[df_actual["ID_TICKET"].astype(int) == id_a_editar].tolist()[0]
                    
                    df_actual.at[idx, "ESTADO"] = nuevo_estado
                    df_actual.at[idx, "PRIORIDAD"] = nueva_prioridad
                    df_actual.at[idx, "FE_RTA"] = str(nueva_rta_fecha)
                    df_actual.at[idx, "TIEMPO_RES"] = nuevo_tiempo
                    df_actual.at[idx, "RESPUESTAS"] = nuevas_respuestas
                    
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                    st.success(f"✅ Ticket #{id_a_editar} actualizado correctamente.")
                except Exception as e:
                    st.error(f"❌ Error al actualizar: {e}")
        else:
            st.info("No hay tickets pendientes para modificar.")
    else:
        st.warning("La base de datos está vacía.")
