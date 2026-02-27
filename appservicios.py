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

# 2. FUNCIÓN PARA LEER DATOS SIN CACHÉ (Fundamental para el ID)
def obtener_datos():
    # ttl=0 obliga a la app a leer los datos reales de Google Sheets cada vez
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    # Limpiamos espacios en los nombres de las columnas para evitar errores
    df.columns = df.columns.str.strip()
    return df

# Intentamos obtener los datos actuales
try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    df_actual = pd.DataFrame()

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["➕ Nuevo Ticket", "✏️ Modificar Ticket Pendiente"])

# ==========================================
# TAB 1: CARGA DE NUEVO TICKET (ID CORREGIDO)
# ==========================================
with tab1:
    # Lógica de ID Robusta: Buscamos el valor más alto real
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        # Convertimos la columna ID a números, ignorando errores (letras o vacíos)
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
            "ANIO": fe_consult.year,
            "MES": fe_consult.month
        }])

        try:
            # Re-leemos justo antes de guardar para evitar colisiones
            df_final = pd.concat([obtener_datos(), df_nuevo], ignore_index=True)
            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
            st.balloons()
            st.success(f"✅ Ticket #{proximo_id} guardado. Año: {fe_consult.year}, Mes: {fe_consult.month}")
            st.rerun() # Reinicia la app para actualizar el contador
        except Exception as e:
            st.error(f"❌ Error: {e}")

# ==========================================
# TAB 2: MODIFICAR TICKET (PENDIENTES)
# ==========================================
with tab2:
    st.subheader("Modificar Tickets Pendientes")
    
    if not df_actual.empty:
        # Filtramos los que están abiertos o en proceso
        pendientes = df_actual[df_actual["ESTADO"].isin(["Abierto", "En Proceso"])]
        
        if not pendientes.empty:
            opciones = pendientes.apply(lambda x: f"ID: {x['ID_TICKET']} - {x['CLIENTES']}", axis=1).tolist()
            seleccion = st.selectbox("Ticket a editar:", opciones)
            
            id_sel = int(seleccion.split(" - ")[0].replace("ID: ", ""))
            fila_idx = df_actual.index[df_actual["ID_TICKET"].astype(int) == id_sel].tolist()[0]
            datos = df_actual.loc[fila_idx]

            with st.form("edit_form"):
                st.info(f"Editando Ticket ID: {id_sel}")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    nuevo_estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"], 
                                                index=["Abierto", "En Proceso", "Cerrado"].index(datos["ESTADO"]))
                with col_e2:
                    nuevo_tiempo = st.number_input("Tiempo Total", value=int(datos["TIEMPO_RES"]))
                
                nueva_rta = st.text_area("Detalle Respuesta", value=datos["RESPUESTAS"])
                boton_upd = st.form_submit_button("Actualizar Ticket")

            if boton_upd:
                try:
                    df_actual.at[fila_idx, "ESTADO"] = nuevo_estado
                    df_actual.at[fila_idx, "TIEMPO_RES"] = nuevo_tiempo
                    df_actual.at[fila_idx, "RESPUESTAS"] = nueva_rta
                    
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                    st.success(f"✅ Ticket #{id_sel} actualizado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            st.info("No hay tickets pendientes.")
