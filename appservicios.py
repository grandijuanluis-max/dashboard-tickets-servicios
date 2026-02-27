import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import io
from fpdf import FPDF

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
    return v if v and v.lower() != "nan" and v != "None" else "Sin registro"

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    df_actual = pd.DataFrame()

# MEJORA 1: Agregamos una key para que Streamlit mantenga la solapa activa
tab1, tab2, tab3, tab4 = st.tabs(["➕ Nuevo Ticket", "✏️ Modificar Ticket", "🔍 Consultar Tickets", "📊 Reportes"])

# ==========================================
# TAB 1: CARGA DE NUEVO TICKET
# ==========================================
with tab1:
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_num = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_num.max()) + 1 if not ids_num.empty else 1
    else: proximo_id = 1

    st.subheader(f"Cargando Ticket N°: {proximo_id}")
    with st.form("nuevo_ticket_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo de Consulta", ["Funcional", "Técnica", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])
        with col2:
            atencion = st.selectbox("Atención", ["Telefónica", "Wasapp", "Meet", "Programada", "Visita"])
            clientes_opc = ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]
            clientes = st.selectbox("Clientes", clientes_opc)
            usuario = st.text_input("Usuario *")
            modulo_opc = ["Accesos", "Administracion", "Contabilidad", "Compras", "Ventas", "Logistica", "Eccomerce", "Mails", "Programa", "Produccion","Servidor", "Web", "Gerencial", "RRHH", "Impuestos", "Sucursal", "Otros"]
            modulo = st.selectbox("Módulo", modulo_opc)
        with col3:
            fe_consult = st.date_input("Fecha Consulta", datetime.now())
            fe_rta = st.date_input("Fecha Respuesta", datetime.now())
            tiempo_res = st.number_input("Tiempo Respuesta (min) *", min_value=0)

        st.divider()
        consultas = st.text_area("Detalle de la Consulta *")
        respuestas = st.text_area("Detalle de la Respuesta *")
        if st.form_submit_button("Guardar Registro"):
            if not (usuario.strip() and consultas.strip() and respuestas.strip() and tiempo_res > 0):
                st.error("⚠️ Faltan campos obligatorios.")
            else:
                nuevo = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor.upper(), "TIPO_CONS": tipo_cons.upper(),
                    "PRIORIDAD": prioridad.upper(), "ESTADO": estado.upper(), "ATENCION": atencion.upper(),
                    "CLIENTES": clientes.upper(), "USUARIO": usuario.upper(), 
                    "FE_CONSULT": fe_consult.strftime('%d/%m/%Y'), "FE_RTA": fe_rta.strftime('%d/%m/%Y'),
                    "MODULO": modulo.upper(), "CONSULTAS": consultas, "RESPUESTAS": respuestas,
                    "TIEMPO_RES": tiempo_res, "ONLINE": "NO", "ANIO": int(fe_consult.year), "MES": int(fe_consult.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                try:
                    df_final = pd.concat([obtener_datos(), nuevo], ignore_index=True)
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
                    st.balloons()
                    st.rerun() 
                except Exception as e: st.error(f"Error: {e}")

# ==========================================
# TAB 2: MODIFICAR TICKET
# ==========================================
with tab2:
    st.subheader("Búsqueda y Edición")
    if not df_actual.empty:
        pendientes = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not pendientes.empty:
            busqueda = st.text_input("🔍 Buscar Cliente:", key="input_busqueda")
            if busqueda: pendientes = pendientes[pendientes["CLIENTES"].str.contains(busqueda, case=False)]
            pendientes["ID_NUM"] = pd.to_numeric(pendientes["ID_TICKET"], errors='coerce')
            pendientes = pendientes.sort_values(by=["CLIENTES", "ID_NUM"])
            
            if not pendientes.empty:
                opciones = pendientes.apply(lambda r: f"{r['CLIENTES']} | #{int(r['ID_NUM'])} | {r['USUARIO']}", axis=1).tolist()
                seleccion = st.selectbox("Selecciona para editar:", opciones)
                id_sel = int(seleccion.split(" | #")[1].split(" | ")[0])
                fila_idx = df_actual.index[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_sel].tolist()[0]
                d = df_actual.loc[fila_idx]

                st.warning(f"🕒 Última modificación: {formato_historial(d['ULTIMA_MODIF'])} por {formato_historial(d['MODIFICADO_POR'])}")

                with st.form("form_edicion"):
                    st.markdown(f"### ✏️ Ticket **#{id_sel}**")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        st.text_input("Consultor", value=d["CONSULTOR"], disabled=True)
                        lista_est = ["ABIERTO", "EN PROCESO", "CERRADO"]
                        idx_est = lista_est.index(d["ESTADO"].upper()) if d["ESTADO"].upper() in lista_est else 0
                        n_estado = st.selectbox("Estado", lista_est, index=idx_est)
                    with ce2:
                        st.text_input("Cliente", value=d["CLIENTES"], disabled=True)
                        st.text_input("Usuario", value=d["USUARIO"], disabled=True)
                    with ce3:
                        try: fr_dt = datetime.strptime(str(d["FE_RTA"]), '%d/%m/%Y')
                        except: fr_dt = datetime.now()
                        n_fe_rta = st.date_input("Fecha Respuesta", fr_dt)
                        n_tiempo = st.number_input("Tiempo (min) *", value=int(float(d["TIEMPO_RES"] if d["TIEMPO_RES"]!="" else 0)), min_value=0)
                    
                    st.divider()
                    st.text_area("Consulta Original", value=d["CONSULTAS"], disabled=True)
                    n_rta = st.text_area("Respuesta (Editable) *", value=d["RESPUESTAS"])

                    if st.form_submit_button("💾 GUARDAR CAMBIOS"):
                        if not (n_rta.strip() and n_tiempo > 0): st.error("⚠️ Datos obligatorios faltantes.")
                        else:
                            df_actual.at[fila_idx, "ESTADO"] = n_estado.upper()
                            df_actual.at[fila_idx, "FE_RTA"] = n_fe_rta.strftime('%d/%m/%Y')
                            df_actual.at[fila_idx, "TIEMPO_RES"] = n_tiempo
                            df_actual.at[fila_idx, "RESPUESTAS"] = n_rta
                            df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                            df_final_subir = df_actual.drop(columns=["ESTADO_UP", "ID_NUM"], errors="ignore")
                            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final_subir)
                            st.session_state.input_busqueda = "" 
                            st.success("✅ Ticket actualizado correctamente.")
                            st.rerun()

# ==========================================
# TAB 3: CONSULTAR TICKETS (SOLUCIÓN TYPEERROR)
# ==========================================
with tab3:
    st.subheader("🔍 Filtros de Consulta")
    if not df_actual.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            lista_clientes = ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique()))
            f_cliente = st.selectbox("Seleccionar Cliente:", lista_clientes)
        with col2:
            f_desde = st.date_input("Desde Fecha:", value=date(2026, 1, 1))
        with col3:
            f_hasta = st.date_input("Hasta Fecha:", value=datetime.now().date())

        df_filtro = df_actual.copy()
        if f_cliente != "TODOS":
            df_filtro = df_filtro[df_filtro["CLIENTES"] == f_cliente]
        
        # MEJORA 2: Solución al TypeError de comparación de fechas
        # Convertimos la columna a datetime y luego a objetos date de Python para comparar con st.date_input
        df_filtro['FECHA_COMPARAR'] = pd.to_datetime(df_filtro['FE_CONSULT'], format='%d/%m/%Y', errors='coerce').dt.date
        
        # Filtrado seguro ignorando valores nulos (NaT)
        df_filtro = df_filtro.dropna(subset=['FECHA_COMPARAR'])
        df_filtro = df_filtro[(df_filtro['FECHA_COMPARAR'] >= f_desde) & (df_filtro['FECHA_COMPARAR'] <= f_hasta)]
        
        st.divider()
        if not df_filtro.empty:
            st.write(f"Se encontraron **{len(df_filtro)}** tickets.")
            opciones_cons = df_filtro.apply(lambda r: f"#{int(float(r['ID_TICKET']))} | {r['CLIENTES']} | {r['USUARIO']}", axis=1).tolist()
            id_query = st.selectbox("Ver detalle:", opciones_cons, key="query_select")
            id_cons = int(id_query.split(" | ")[0].replace("#", ""))
            dc = df_filtro[pd.to_numeric(df_filtro["ID_TICKET"], errors='coerce') == id_cons].iloc[0]
            
            st.info(f"Ficha del Ticket #{id_cons}")
            v1, v2, v3 = st.columns(3)
            with v1:
                st.text_input("Consultor ", value=dc["CONSULTOR"], disabled=True)
                st.text_input("Estado ", value=dc["ESTADO"], disabled=True)
            with v2:
                st.text_input("Cliente ", value=dc["CLIENTES"], disabled=True)
                st.text_input("Usuario ", value=dc["USUARIO"], disabled=True)
            with v3:
                st.text_input("Fecha Consulta ", value=dc["FE_CONSULT"], disabled=True)
                st.text_input("Tiempo (min) ", value=dc["TIEMPO_RES"], disabled=True)
            
            st.text_area("Detalle Consulta ", value=dc["CONSULTAS"], disabled=True)
            st.text_area("Detalle Respuesta ", value=dc["RESPUESTAS"], disabled=True)
        else:
            st.info("No hay tickets que coincidan con los filtros.")

# ==========================================
# TAB 4: REPORTES POR CLIENTE
# ==========================================
with tab4:
    st.subheader("📊 Reporte de Tiempos")
    if not df_actual.empty:
        cli_sel = st.selectbox("Filtrar Cliente para Reporte:", sorted(df_actual["CLIENTES"].unique()), key="rep_cli")
        df_cli = df_actual[df_actual["CLIENTES"] == cli_sel].copy()
        df_cli["TIEMPO_RES"] = pd.to_numeric(df_cli["TIEMPO_RES"], errors='coerce').fillna(0)
        
        resumen = df_cli.groupby(["CLIENTES", "USUARIO", "MODULO"])["TIEMPO_RES"].sum().reset_index()
        st.dataframe(resumen, use_container_width=True)
        
        total_minutos = resumen["TIEMPO_RES"].sum()
        st.metric("Total Tiempo", f"{total_minutos} min (~{total_minutos/60:.2f} hs)")

        fila_total = pd.DataFrame([{"CLIENTES": "TOTAL", "USUARIO": "-", "MODULO": "-", "TIEMPO_RES": total_minutos}])
        df_final_res = pd.concat([resumen, fila_total], ignore_index=True)
        df_final_res["HORAS_TOTAL"] = df_final_res["TIEMPO_RES"] / 60

        col_res1, col_res2 = st.columns(2)
        with col_res1:
            buf_res = io.BytesIO()
            with pd.ExcelWriter(buf_res, engine='openpyxl') as writer:
                df_final_res.to_excel(writer, index=False, sheet_name='Resumen')
            st.download_button(label="📥 Descargar Excel", data=buf_res.getvalue(), file_name=f"Reporte_{cli_sel}.xlsx")
        with col_res2:
            pdf_res = FPDF()
            pdf_res.add_page(); pdf_res.set_font("Arial", 'B', 12)
            pdf_res.cell(200, 10, txt=f"REPORTE: {cli_sel}", ln=True, align='C')
            pdf_res_out = pdf_res.output(dest='S').encode('latin-1')
            st.download_button(label="📥 Descargar PDF", data=pdf_res_out, file_name=f"Reporte_{cli_sel}.pdf")
