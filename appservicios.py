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

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df

# Obtener el nombre del usuario de la computadora
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
            "CONSULTOR": consultor.upper(),
            "TIPO_CONS": tipo_cons.upper(),
            "PRIORIDAD": prioridad.upper(),
            "ESTADO": estado.upper(),
            "ATENCION": atencion.upper(),
            "CLIENTES": clientes.upper(),
            "USUARIO": usuario.upper(),
            "FE_CONSULT": str(fe_consult),
            "FE_RTA": str(fe_rta),
            "MODULO": modulo.upper(),
            "CONSULTAS": consultas,
            "RESPUESTAS": respuestas,
            "TIEMPO_RES": tiempo_res,
            "ONLINE": "SI" if online else "NO",
            "ANIO": int(fe_consult.year),
            "MES": int(fe_consult.month),
            "ULTIMA_MODIF": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "MODIFICADO_POR": usuario_pc
        }])
        try:
            df_final = pd.concat([obtener_datos(), df_nuevo], ignore_index=True)
            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
            st.balloons()
            st.success(f"✅ Ticket #{proximo_id} guardado.")
            st.rerun() 
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

# ==========================================
# TAB 2: MODIFICAR TICKET (Con Buscador de Cliente)
# ==========================================
with tab2:
    st.subheader("Búsqueda y Edición de Tickets")
    
    if not df_actual.empty:
        # 1. Filtramos los pendientes
        pendientes = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        
        if not pendientes.empty:
            # --- NUEVO: BUSCADOR DE TEXTO ---
            busqueda = st.text_input("🔍 Buscar por nombre de Cliente:", placeholder="Escribe las primeras letras...")
            
            # 2. Aplicamos el filtro si el usuario escribió algo
            if busqueda:
                pendientes = pendientes[pendientes["CLIENTES"].str.contains(busqueda, case=False, na=False)]
            
            # 3. Ordenamiento por Cliente e ID
            pendientes["ID_TICKET"] = pd.to_numeric(pendientes["ID_TICKET"], errors='coerce')
            pendientes = pendientes.sort_values(by=["CLIENTES", "ID_TICKET"], ascending=[True, True])
            
            if not pendientes.empty:
                def crear_etiqueta(row):
                    primer_renglon = str(row['CONSULTAS']).split('\n')[0][:50]
                    return f"{row['CLIENTES']} | #{int(row['ID_TICKET'])} | Usuario: {row['USUARIO']} | Obs: {primer_renglon}..."

                opciones = pendientes.apply(crear_etiqueta, axis=1).tolist()
                seleccion = st.selectbox("Selecciona el ticket:", opciones)
                
                # Extracción segura del ID
                id_sel = int(seleccion.split(" | #")[1].split(" | ")[0])
                fila_idx = df_actual.index[df_actual["ID_TICKET"].astype(float).astype(int) == id_sel].tolist()[0]
                d = df_actual.loc[fila_idx]

                # Historial de modificación
                fecha_mod = d["ULTIMA_MODIF"] if "ULTIMA_MODIF" in d and not pd.isna(d["ULTIMA_MODIF"]) else "Sin registro"
                quien_mod = d["MODIFICADO_POR"] if "MODIFICADO_POR" in d and not pd.isna(d["MODIFICADO_POR"]) else "Desconocido"
                st.warning(f"🕒 **Última modificación:** el {fecha_mod} por: **{quien_mod}**")

                with st.form("edit_form_final"):
                    st.markdown(f"### 🔒 Editando Ticket **#{id_sel}**")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.text_input("Consultor", value=d["CONSULTOR"], disabled=True)
                        st.text_input("Prioridad", value=d["PRIORIDAD"], disabled=True)
                        lista_estados = ["ABIERTO", "EN PROCESO", "CERRADO"]
                        idx_estado = lista_estados.index(d["ESTADO"].upper()) if d["ESTADO"].upper() in lista_estados else 0
                        e_estado = st.selectbox("Estado (Editable)", lista_estados, index=idx_estado)
                    
                    with c2:
                        st.text_input("Cliente", value=d["CLIENTES"], disabled=True)
                        st.text_input("Usuario", value=d["USUARIO"], disabled=True)
                        st.text_input("Módulo", value=d["MODULO"], disabled=True)

                    with c3:
                        f_cons_dt = datetime.strptime(str(d["FE_CONSULT"]), '%Y-%m-%d') if d["FE_CONSULT"] else datetime.now()
                        st.date_input("Fecha Consulta", f_cons_dt, disabled=True)
                        f_rta_dt = datetime.strptime(str(d["FE_RTA"]), '%Y-%m-%d') if d["FE_RTA"] else datetime.now()
                        e_fe_rta = st.date_input("Fecha Respuesta (Editable)", f_rta_dt)
                        e_tiempo = st.number_input("Tiempo (Editable)", value=int(float(d["TIEMPO_RES"])))

                    st.divider()
                    st.text_area("Detalle de la Consulta", value=d["CONSULTAS"], disabled=True)
                    e_respuestas = st.text_area("Detalle de la Respuesta (Editable)", value=d["RESPUESTAS"])
                    
                    btn_update = st.form_submit_button("💾 GUARDAR CAMBIOS")

                if btn_update:
                    try:
                        df_actual.at[fila_idx, "ESTADO"] = e_estado.upper()
                        df_actual.at[fila_idx, "FE_RTA"] = str(e_fe_rta)
                        df_actual.at[fila_idx, "TIEMPO_RES"] = e_tiempo
                        df_actual.at[fila_idx, "RESPUESTAS"] = e_respuestas
                        df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                        
                        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                        st.success(f"✅ Ticket #{id_sel} actualizado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar: {e}")
            else:
                st.info("No se encontraron clientes que coincidan con tu búsqueda.")
        else:
            st.info("No hay tickets pendientes.")
    else:
        st.warning("La base de datos está vacía.")
