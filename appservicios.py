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

# 2. FUNCIÓN PARA LEER DATOS SIN CACHÉ (Fundamental para el ID y Modificaciones)
def obtener_datos():
    # ttl=0 obliga a la app a leer los datos reales de Google Sheets cada vez
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    # Limpiamos espacios en los nombres de las columnas para evitar errores
    df.columns = df.columns.str.strip()
    return df

# Intentamos obtener los datos actuales al cargar la página
try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    df_actual = pd.DataFrame()

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["➕ Nuevo Ticket", "✏️ Modificar Ticket Pendiente"])

# ==========================================
# TAB 1: CARGA DE NUEVO TICKET
# ==========================================
with tab1:
    # Lógica de ID Robusta
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_numericos = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        if not ids_numericos.empty:
            proximo_id = int(ids_numericos.max()) + 1
        else:
            proximo_id = 1
    else:
        proximo_id = 1

    st.subheader(f"Cargando Ticket N°: {proximo_id}")
    
    with st.form("nuevo_ticket_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"ID Automático: {proximo_id}")
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
        # Aquí se graban el Año y el Mes automáticamente de la fecha de consulta
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
            "ANIO": int(fe_consult.year),
            "MES": int(fe_consult.month)
        }])

        try:
            # Re-leemos justo antes de guardar para evitar pisar datos de otros usuarios
            df_final = pd.concat([obtener_datos(), df_nuevo], ignore_index=True)
            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
            st.balloons()
            st.success(f"✅ Ticket #{proximo_id} guardado. Año: {fe_consult.year}, Mes: {fe_consult.month}")
            st.rerun() 
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

# ==========================================
# TAB 2: MODIFICAR TICKET (PENDIENTES)
# ==========================================
with tab2:
    st.subheader("Modificar Tickets Pendientes")
    
    if not df_actual.empty:
        # Filtramos los que están abiertos o en proceso
        pendientes = df_actual[df_actual["ESTADO"].isin(["Abierto", "En Proceso"])]
        
        if not pendientes.empty:
            # Lista desplegable para elegir el ticket
            opciones = pendientes.apply(lambda x: f"ID: {x['ID_TICKET']} - {x['CLIENTES']}", axis=1).tolist()
            seleccion = st.selectbox("Selecciona el ticket para actualizar:", opciones)
            
            # Extraer el ID real
            id_sel = int(seleccion.split(" - ")[0].replace("ID: ", ""))
            # Buscar la fila exacta en el dataframe
            fila_idx = df_actual.index[df_actual["ID_TICKET"].astype(int) == id_sel].tolist()[0]
            datos_viejos = df_actual.loc[fila_idx]

            with st.form("edit_form"):
                st.info(f"Editando Ticket ID: {id_sel}")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    nuevo_estado = st.selectbox("Nuevo Estado", ["Abierto", "En Proceso", "Cerrado"], 
                                                index=["Abierto", "En Proceso", "Cerrado"].index(datos_viejos["ESTADO"]))
                    nueva_prioridad = st.select_slider("Nueva Prioridad", options=["Baja", "Media", "Alta"],
                                                       value=datos_viejos["PRIORIDAD"])
                with col_e2:
                    nueva_fecha_rta = st.date_input("Nueva Fecha Respuesta", datetime.now())
                    nuevo_tiempo = st.number_input("Tiempo Total (horas/min)", value=int(datos_viejos["TIEMPO_RES"]))
                
                nueva_respuesta_det = st.text_area("Actualizar Detalle de Respuesta", value=datos_viejos["RESPUESTAS"])
                boton_upd = st.form_submit_button("Guardar Cambios en Ticket")

            if boton_upd:
                try:
                    # Actualizamos los valores en el dataframe actual
                    df_actual.at[fila_idx, "ESTADO"] = nuevo_estado
                    df_actual.at[idx, "PRIORIDAD"] = nueva_prioridad
                    df_actual.at[fila_idx, "FE_RTA"] = str(nueva_fecha_rta)
                    df_actual.at[fila_idx, "TIEMPO_RES"] = nuevo_tiempo
                    df_actual.at[fila_idx, "RESPUESTAS"] = nueva_respuesta_det
                    
                    # Subimos la hoja completa actualizada
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                    st.success(f"✅ Ticket #{id_sel} actualizado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al actualizar: {e}")
        else:
            st.info("No hay tickets pendientes (Abiertos o En Proceso) para modificar.")
    else:
        st.warning("La base de datos está vacía.")
