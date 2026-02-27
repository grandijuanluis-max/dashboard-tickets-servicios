import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import getpass 

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets", layout="wide")

st.title("📋 Sistema de Gestión de Consultas y Tickets")

# 1. Configuración de la URL y Conexión
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "input_busqueda" not in st.session_state:
    st.session_state.input_busqueda = ""

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

def formato_historial(valor):
    v = str(valor).strip()
    if v == "" or v.lower() == "nan" or v == "None":
        return "Sin registro"
    return v

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    df_actual = pd.DataFrame()

tab1, tab2 = st.tabs(["➕ Nuevo Ticket", "✏️ Modificar Ticket Pendiente"])

# ==========================================
# TAB 1: CARGA DE NUEVO TICKET
# ==========================================
with tab1:
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_numericos = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
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
            clientes = st.text_input("Cliente *")
            usuario = st.text_input("Usuario *")
            modulo = st.selectbox("Módulo", ["Accesos", "Administracion", "Contabilidad", "Compras", "Ventas", "Logistica", "Eccomerce", "Mails", "Programa", "Produccion","Servidor", "Web", "Gerencial", "RRHH", "Sucursal", "Otros"])
            online = st.checkbox("¿Se resolvió Online?")
        with col3:
            fe_consult = st.date_input("Fecha Consulta", datetime.now())
            fe_rta = st.date_input("Fecha Respuesta", datetime.now())
            tiempo_res = st.number_input("Tiempo Respuesta (horas/min) *", min_value=0)

        st.divider()
        consultas = st.text_area("Detalle de la Consulta *")
        respuestas = st.text_area("Detalle de la Respuesta *")
        
        enviar_nuevo = st.form_submit_button("Guardar Registro")

    if enviar_nuevo:
        if not (clientes.strip() and usuario.strip() and consultas.strip() and respuestas.strip() and tiempo_res > 0):
            st.error("⚠️ Faltan campos obligatorios o el tiempo es 0.")
        else:
            df_nuevo = pd.DataFrame([{
                "ID_TICKET": proximo_id,
                "CONSULTOR": consultor.upper(),
                "TIPO_CONS": tipo_cons.upper(),
                "PRIORIDAD": prioridad.upper(),
                "ESTADO": estado.upper(),
                "ATENCION": atencion.upper(),
                "CLIENTES": clientes.upper(),
                "USUARIO": usuario.upper(),
                "FE_CONSULT": fe_consult.strftime('%d/%m/%Y'), # Formato dd/mm/año
                "FE_RTA": fe_rta.strftime('%d/%m/%Y'),       # Formato dd/mm/año
                "MODULO": modulo.upper(),
                "CONSULTAS": consultas,
                "RESPUESTAS": respuestas,
                "TIEMPO_RES": tiempo_res,
                "ONLINE": "SI" if online else "NO",
                "ANIO": int(fe_consult.year),
                "MES": int(fe_consult.month),
                "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "MODIFICADO_POR": usuario_pc
            }])
            try:
                df_final = pd.concat([obtener_datos(), df_nuevo], ignore_index=True)
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
                st.balloons()
                st.rerun() 
            except Exception as e:
                st.error(f"❌ Error: {e}")

# ==========================================
# TAB 2: MODIFICAR TICKET
# ==========================================
with tab2:
    st.subheader("Búsqueda y Edición de Tickets")
    
    if not df_actual.empty:
        df_actual["ESTADO_UP"] = df_actual["ESTADO"].str.upper()
        pendientes = df_actual[df_actual["ESTADO_UP"].isin(["ABIERTO", "EN PROCESO"])].copy()
        
        if not pendientes.empty:
            busqueda = st.text_input("🔍 Buscar por nombre de Cliente:", placeholder="Escribe para filtrar...", key="input_busqueda")
            
            if busqueda:
                pendientes = pendientes[pendientes["CLIENTES"].str.contains(busqueda, case=False, na=False)]
            
            pendientes["ID_NUM"] = pd.to_numeric(pendientes["ID_TICKET"], errors='coerce')
            pendientes = pendientes.sort_values(by=["CLIENTES", "ID_NUM"])

            if not pendientes.empty:
                opciones = pendientes.apply(lambda r: f"{r['CLIENTES']} | #{int(r['ID_NUM'])} | Usuario: {r['USUARIO']}", axis=1).tolist()
                seleccion = st.selectbox("Selecciona el ticket para editar:", opciones)
                
                id_sel = int(seleccion.split(" | #")[1].split(" | ")[0])
                fila_idx = df_actual.index[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_sel].tolist()[0]
                d = df_actual.loc[fila_idx]

                st.warning(f"🕒 **Última modificación:** el {formato_historial(d['ULTIMA_MODIF'])} por: **{formato_historial(d['MODIFICADO_POR'])}**")

                with st.form("form_edicion_final"):
                    st.markdown(f"### 🔒 Editando Ticket **#{id_sel}**")
                    ce1, ce2, ce3 = st.columns(3)
                    
                    with ce1:
                        st.text_input("Consultor", value=d["CONSULTOR"], disabled=True)
                        st.text_input("Prioridad", value=d["PRIORIDAD"], disabled=True)
                        lista_est = ["ABIERTO", "EN PROCESO", "CERRADO"]
                        curr_est = str(d["ESTADO"]).upper()
                        idx_est = lista_est.index(curr_est) if curr_est in lista_est else 0
                        nuevo_estado = st.selectbox("Estado (Editable)", lista_est, index=idx_est)
                    
                    with ce2:
                        st.text_input("Cliente", value=d["CLIENTES"], disabled=True)
                        st.text_input("Usuario", value=d["USUARIO"], disabled=True)
                        st.text_input("Módulo", value=d["MODULO"], disabled=True)

                    with ce3:
                        # Lectura de fecha en formato dd/mm/año
                        try:
                            f_rta_dt = datetime.strptime(str(d["FE_RTA"]), '%d/%m/%Y')
                        except:
                            f_rta_dt = datetime.now()
                        
                        nueva_fe_rta = st.date_input("Fecha Respuesta (Editable)", f_rta_dt)
                        nuevo_tiempo = st.number_input("Tiempo (Editable) *", value=int(float(d["TIEMPO_RES"] if d["TIEMPO_RES"] != "" else 0)), min_value=0)

                    st.divider()
                    st.text_area("Detalle de la Consulta", value=d["CONSULTAS"], disabled=True)
                    nueva_rta = st.text_area("Detalle de la Respuesta (Editable) *", value=d["RESPUESTAS"])

                    guardar_cambios = st.form_submit_button("💾 GUARDAR CAMBIOS EN TICKET")

                if guardar_cambios:
                    if not (nueva_rta.strip() and nuevo_tiempo > 0):
                        st.error("⚠️ La Respuesta y el Tiempo son obligatorios.")
                    else:
                        try:
                            df_actual.at[fila_idx, "ESTADO"] = nuevo_estado.upper()
                            df_actual.at[fila_idx, "FE_RTA"] = nueva_fe_rta.strftime('%d/%m/%Y')
                            df_actual.at[fila_idx, "TIEMPO_RES"] = nuevo_tiempo
                            df_actual.at[fila_idx, "RESPUESTAS"] = nueva_rta
                            df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                            
                            df_final_subir = df_actual.drop(columns=["ESTADO_UP", "ID_NUM"], errors="ignore")
                            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final_subir)
                            
                            st.session_state.input_busqueda = "" 
                            st.success("✅ Ticket actualizado correctamente. Formato de fecha aplicado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {e}")
            else:
                st.info("No hay resultados para esa búsqueda.")
        else:
            st.info("No hay tickets pendientes.")
