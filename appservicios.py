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

# Inicializamos estados si no existen
if "input_busqueda" not in st.session_state:
    st.session_state.input_busqueda = ""

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

def formato_historial(valor):
    v = str(valor).strip()
    return v if v and v.lower() != "nan" and v != "none" else "Sin registro"

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    df_actual = pd.DataFrame()

# MEJORA: KEY para mantener la solapa activa
tab1, tab2, tab3, tab4 = st.tabs(["➕ Nuevo Ticket", "✏️ Modificar Ticket", "🔍 Consultar Tickets", "📊 Reportes"])

# ==========================================
# TAB 1: NUEVO TICKET
# ==========================================
with tab1:
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_num = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_num.max()) + 1 if not ids_num.empty else 1
    else: proximo_id = 1

    with st.form("nuevo_ticket_form", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket N°: {proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo de Consulta", ["Funcional", "Técnica", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])
        with c2:
            atencion = st.selectbox("Atención", ["Telefónica", "Wasapp", "Meet", "Programada", "Visita"])
            clientes_opc = ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]
            cliente_nuevo = st.selectbox("Clientes", clientes_opc)
            usuario_nuevo = st.text_input("Usuario *")
            modulo_opc = ["Accesos", "Administracion", "Contabilidad", "Compras", "Ventas", "Logistica", "Eccomerce", "Mails", "Programa", "Produccion","Servidor", "Web", "Gerencial", "RRHH", "Impuestos", "Sucursal", "Otros"]
            modulo_nuevo = st.selectbox("Módulo", modulo_opc)
        with c3:
            fe_c = st.date_input("Fecha Consulta", datetime.now())
            fe_r = st.date_input("Fecha Respuesta", datetime.now())
            t_res = st.number_input("Tiempo (min) *", min_value=0)

        det_c = st.text_area("Detalle Consulta *")
        det_r = st.text_area("Detalle Respuesta *")
        
        if st.form_submit_button("Guardar"):
            if not (usuario_nuevo.strip() and det_c.strip() and det_r.strip() and t_res > 0):
                st.error("Campos obligatorios incompletos.")
            else:
                nuevo_reg = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor.upper(), "TIPO_CONS": tipo_cons.upper(),
                    "PRIORIDAD": prioridad.upper(), "ESTADO": estado.upper(), "ATENCION": atencion.upper(),
                    "CLIENTES": cliente_nuevo.upper(), "USUARIO": usuario_nuevo.upper(), 
                    "FE_CONSULT": fe_c.strftime('%d/%m/%Y'), "FE_RTA": fe_r.strftime('%d/%m/%Y'),
                    "MODULO": modulo_nuevo.upper(), "CONSULTAS": det_c, "RESPUESTAS": det_r,
                    "TIEMPO_RES": t_res, "ONLINE": "NO", "ANIO": int(fe_c.year), "MES": int(fe_c.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                df_f = pd.concat([obtener_datos(), nuevo_reg], ignore_index=True)
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_f)
                st.balloons()
                st.rerun()

# ==========================================
# TAB 2: MODIFICAR TICKET
# ==========================================
with tab2:
    if not df_actual.empty:
        pendientes = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not pendientes.empty:
            busq = st.text_input("🔍 Buscar Cliente p/ Editar:", key="input_busqueda")
            if busq: pendientes = pendientes[pendientes["CLIENTES"].str.contains(busq, case=False)]
            pendientes["ID_NUM"] = pd.to_numeric(pendientes["ID_TICKET"], errors='coerce')
            pendientes = pendientes.sort_values(by=["CLIENTES", "ID_NUM"])
            
            if not pendientes.empty:
                op_e = pendientes.apply(lambda r: f"{r['CLIENTES']} | #{int(r['ID_NUM'])} | {r['USUARIO']}", axis=1).tolist()
                sel_e = st.selectbox("Selecciona Ticket:", op_e)
                id_e = int(sel_e.split(" | #")[1].split(" | ")[0])
                idx_e = df_actual.index[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_e].tolist()[0]
                de = df_actual.loc[idx_e]

                with st.form("edit_form"):
                    st.warning(f"🕒 Modificado: {formato_historial(de['ULTIMA_MODIF'])} por {formato_historial(de['MODIFICADO_POR'])}")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        est_e = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(de["ESTADO"].upper()) if de["ESTADO"].upper() in ["ABIERTO", "EN PROCESO", "CERRADO"] else 0)
                    with ce3:
                        try: fr_dt = datetime.strptime(str(de["FE_RTA"]), '%d/%m/%Y')
                        except: fr_dt = datetime.now()
                        fe_r_e = st.date_input("F. Rta", fr_dt)
                        t_e = st.number_input("Tiempo (min) *", value=int(float(de["TIEMPO_RES"] if de["TIEMPO_RES"]!="" else 0)))
                    rta_e = st.text_area("Respuesta *", value=de["RESPUESTAS"])
                    if st.form_submit_button("Guardar Cambios"):
                        df_actual.at[idx_e, "ESTADO"] = est_e.upper()
                        df_actual.at[idx_e, "FE_RTA"] = fe_r_e.strftime('%d/%m/%Y')
                        df_actual.at[idx_e, "TIEMPO_RES"] = t_e
                        df_actual.at[idx_e, "RESPUESTAS"] = rta_e
                        df_actual.at[idx_e, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        df_actual.at[idx_e, "MODIFICADO_POR"] = usuario_pc
                        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                        st.rerun()

# ==========================================
# TAB 3: CONSULTAR TICKETS (CORREGIDA)
# ==========================================
with tab3:
    st.subheader("🔍 Filtros de Consulta")
    if not df_actual.empty:
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            lista_cli = ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique()))
            f_cli = st.selectbox("Seleccionar Cliente:", lista_cli)
        with c_f2:
            # Ampliamos el rango por defecto para que no oculte datos al entrar
            f_d = st.date_input("Desde:", value=date(2020, 1, 1))
        with c_f3:
            f_h = st.date_input("Hasta:", value=datetime.now().date())

        # Lógica de Filtrado
        df_f = df_actual.copy()
        if f_cli != "TODOS":
            df_f = df_f[df_f["CLIENTES"] == f_cli]
        
        # Conversión segura para comparación
        df_f['FECHA_DT'] = pd.to_datetime(df_f['FE_CONSULT'], format='%d/%m/%Y', errors='coerce').dt.date
        df_f = df_f.dropna(subset=['FECHA_DT'])
        df_f = df_f[(df_f['FECHA_DT'] >= f_d) & (df_f['FECHA_DT'] <= f_h)]
        
        st.divider()
        if not df_f.empty:
            st.write(f"Se encontraron **{len(df_f)}** tickets.")
            # Etiqueta detallada para no confundirse
            op_c = df_f.apply(lambda r: f"#{int(float(r['ID_TICKET']))} | {r['CLIENTES']} | {r['USUARIO']} | {r['FE_CONSULT']}", axis=1).tolist()
            sel_c = st.selectbox("Ver detalle del ticket:", op_c)
            
            id_c = int(sel_c.split(" | ")[0].replace("#", ""))
            dc = df_f[pd.to_numeric(df_f["ID_TICKET"], errors='coerce') == id_c].iloc[0]
            
            st.info(f"Ficha del Ticket #{id_c}")
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
            
            st.text_area("Consulta ", value=dc["CONSULTAS"], disabled=True)
            st.text_area("Respuesta ", value=dc["RESPUESTAS"], disabled=True)
            
            # Exportación individual
            ex1, ex2 = st.columns(2)
            with ex1:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w:
                    dc.to_frame().T.to_excel(w, index=False)
                st.download_button("📥 Excel Ticket", buf.getvalue(), f"Ticket_{id_c}.xlsx")
            with ex2:
                pdf = FPDF()
                pdf.add_page(); pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt=f"TICKET #{id_c}", ln=True, align='C')
                pdf.set_font("Arial", size=10)
                for col in dc.index: pdf.multi_cell(0, 8, txt=f"{col}: {dc[col]}")
                st.download_button("📥 PDF Ticket", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")
        else:
            st.info("No hay tickets que coincidan con los filtros.")

# ==========================================
# TAB 4: REPORTES
# ==========================================
with tab4:
    st.subheader("📊 Reporte Acumulado")
    if not df_actual.empty:
        c_sel = st.selectbox("Cliente para Reporte:", sorted(df_actual["CLIENTES"].unique()))
        df_c = df_actual[df_actual["CLIENTES"] == c_sel].copy()
        df_c["TIEMPO_RES"] = pd.to_numeric(df_c["TIEMPO_RES"], errors='coerce').fillna(0)
        
        res = df_c.groupby(["CLIENTES", "USUARIO", "MODULO"])["TIEMPO_RES"].sum().reset_index()
        st.dataframe(res, use_container_width=True)
        t_m = res["TIEMPO_RES"].sum()
        st.metric("Total", f"{t_m} min ({t_m/60:.2f} hs)")

        f_t = pd.DataFrame([{"CLIENTES": "TOTAL", "USUARIO": "-", "MODULO": "-", "TIEMPO_RES": t_m}])
        df_res = pd.concat([res, f_t], ignore_index=True)
        df_res["HORAS"] = df_res["TIEMPO_RES"] / 60

        cr1, cr2 = st.columns(2)
        with cr1:
            b_r = io.BytesIO()
            with pd.ExcelWriter(b_r, engine='openpyxl') as wr:
                df_res.to_excel(wr, index=False)
            st.download_button("📥 Excel Reporte", b_r.getvalue(), f"Reporte_{c_sel}.xlsx")
        with cr2:
            p_r = FPDF()
            p_r.add_page(); p_r.set_font("Arial", 'B', 12)
            p_r.cell(200, 10, txt=f"REPORTE: {c_sel}", ln=True, align='C')
            st.download_button("📥 PDF Reporte", p_r.output(dest='S').encode('latin-1'), f"Reporte_{c_sel}.pdf")
