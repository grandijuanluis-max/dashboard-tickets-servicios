import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import io
from fpdf import FPDF

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets - GR Consulting", layout="wide")

# 1. Conexión y Control de Estado de Navegación
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
    if not df_actual.empty:
        # Estandarización de tipos para cálculos analíticos
        df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
        df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)
        df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
        df_actual["ID_NUM"] = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').fillna(0).astype(int)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    df_actual = pd.DataFrame()

# ==========================================
# MENÚ DE NAVEGACIÓN ESTABLE
# ==========================================
st.title("📋 Sistema de Gestión de Consultas y Tickets")
cols = st.columns(4)
if cols[0].button("➕ NUEVO TICKET", use_container_width=True): st.session_state.menu_activo = "➕ NUEVO"
if cols[1].button("✏️ MODIFICAR TICKET", use_container_width=True): st.session_state.menu_activo = "✏️ MODIFICAR"
if cols[2].button("🔍 CONSULTAR TICKETS", use_container_width=True): st.session_state.menu_activo = "🔍 CONSULTAR"
if cols[3].button("📊 REPORTES", use_container_width=True): st.session_state.menu_activo = "📊 REPORTES"

st.markdown(f"📍 Estás en: **{st.session_state.menu_activo}**")
st.divider()

# --- LÓGICA DE SECCIONES ---
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("form_nuevo", clear_on_submit=True):
        st.subheader(f"Cargando Ticket N°: {proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            consultor = st.text_input("Consultor").upper()
            tipo_c = st.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
            prio = st.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
            est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            ate = st.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
            cliente = st.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
            usuario_n = st.text_input("Usuario *").upper()
        with c3:
            modulo = st.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PROGRAMA", "PRODUCCION","SERVIDOR", "WEB", "GERENCIAL", "RRHH", "IMPUESTOS", "SUCURSAL", "OTROS"])
            fe_c = st.date_input("Fecha Consulta", datetime.now())
            t_res = st.number_input("Tiempo (min) *", min_value=0)
        con_det = st.text_area("Consulta *")
        rta_det = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR NUEVO TICKET"):
            if not (usuario_n.strip() and con_det.strip() and rta_det.strip() and t_res > 0):
                st.error("⚠️ Datos obligatorios incompletos.")
            else:
                nuevo_reg = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor, "TIPO_CONS": tipo_c,
                    "PRIORIDAD": prio, "ESTADO": est, "ATENCION": ate, "CLIENTES": cliente,
                    "USUARIO": usuario_n, "FE_CONSULT": fe_c.strftime('%d/%m/%Y'),
                    "FE_RTA": fe_c.strftime('%d/%m/%Y'), "MODULO": modulo, "CONSULTAS": con_det,
                    "RESPUESTAS": rta_det, "TIEMPO_RES": t_res, "ONLINE": "NO",
                    "ANIO": int(fe_c.year), "MES": int(fe_c.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo_reg], ignore_index=True))
                st.balloons(); st.rerun()

elif st.session_state.menu_activo == "✏️ MODIFICAR":
    if not df_actual.empty:
        pend = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not pend.empty:
            busq_m = st.text_input("🔍 Buscar Cliente:")
            if busq_m: pend = pend[pend["CLIENTES"].str.contains(busq_m, case=False)]
            pend = pend.sort_values(by=["CLIENTES", "ID_NUM"])
            if not pend.empty:
                op_m = pend.apply(lambda r: f"{r['CLIENTES']} | #{r['ID_NUM']} | {r['USUARIO']} | Obs: {str(r['CONSULTAS'])[:30]}...", axis=1).tolist()
                sel_m = st.selectbox("Selecciona Ticket:", op_m)
                id_m = int(sel_m.split(" | #")[1].split(" | ")[0])
                fila_idx = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]
                dm = df_actual.loc[fila_idx]
                with st.form("form_edit"):
                    st.warning(f"🕒 Última Modificación: {dm['ULTIMA_MODIF']} por {dm['MODIFICADO_POR']}")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        est_m = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
                        t_m = st.number_input("Tiempo (min)", value=int(float(dm["TIEMPO_RES"])))
                    with ce2:
                        st.text_input("Usuario", value=dm["USUARIO"], disabled=True)
                        fe_r_m = st.date_input("F. Respuesta", datetime.now())
                    with ce3: st.text_input("Cliente", value=dm["CLIENTES"], disabled=True)
                    st.divider()
                    n_consulta_m = st.text_area("Detalle Consulta (Editable) *", value=dm["CONSULTAS"])
                    rta_m = st.text_area("Respuesta (Editable) *", value=dm["RESPUESTAS"])
                    if st.form_submit_button("🔥 ACTUALIZAR TICKET"):
                        df_actual.at[fila_idx, "ESTADO"] = est_m
                        df_actual.at[fila_idx, "FE_RTA"] = fe_r_m.strftime('%d/%m/%Y')
                        df_actual.at[fila_idx, "TIEMPO_RES"] = t_m
                        df_actual.at[fila_idx, "CONSULTAS"] = n_consulta_m
                        df_actual.at[fila_idx, "RESPUESTAS"] = rta_m
                        df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                        st.rerun()

elif st.session_state.menu_activo == "🔍 CONSULTAR":
    st.header("🔍 Búsqueda Histórica")
    c1, c2, c3 = st.columns(3)
    with c1: f_cli = st.selectbox("Cliente:", ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique())))
    with c2: f_anios = st.multiselect("Año(s):", options=sorted(df_actual["ANIO"].unique(), reverse=True), default=[2026] if 2026 in df_actual["ANIO"].unique() else [])
    with c3: 
        mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
        f_meses = st.multiselect("Mes(es):", options=sorted(df_actual["MES"].unique()), format_func=lambda x: mes_d.get(x, x))
    
    df_f = df_actual.copy()
    if f_cli != "TODOS": df_f = df_f[df_f["CLIENTES"] == f_cli]
    if f_anios: df_f = df_f[df_f["ANIO"].isin(f_anios)]
    if f_meses: df_f = df_f[df_f["MES"].isin(f_meses)]
    
    if not df_f.empty:
        op_c = df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | Obs: {str(r['CONSULTAS'])[:30]}...", axis=1).tolist()
        sel_c = st.selectbox("Ver Ficha:", op_c)
        id_c = int(sel_c.split("#")[1].split(" |")[0])
        dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"🔍 Ficha Ticket #{id_c}")
            v1, v2, v3 = st.columns(3)
            with v1: st.text_input("Consultor", dc["CONSULTOR"], disabled=True); st.text_input("Estado", dc["ESTADO"], disabled=True)
            with v2: st.text_input("Cliente", dc["CLIENTES"], disabled=True); st.text_input("Usuario", dc["USUARIO"], disabled=True)
            with v3: st.text_input("Fecha", dc["FE_CONSULT"], disabled=True); st.text_input("Tiempo (min)", str(dc["TIEMPO_RES"]), disabled=True)
            st.text_area("Consulta", dc["CONSULTAS"], disabled=True); st.text_area("Respuesta", dc["RESPUESTAS"], disabled=True)
            
            pdf = FPDF()
            pdf.add_page(); pdf.set_draw_color(180, 180, 180); pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 15, txt="GR Consulting - Servicios", ln=True, align='C')
            pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, txt=f"Ticket #{id_c}", ln=True, align='L'); pdf.ln(5)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(50, 10, "ATENDIDO POR:", 1); pdf.cell(140, 10, str(dc['CONSULTOR']), 1, ln=True)
            pdf.cell(50, 10, "CLIENTE:", 1); pdf.cell(140, 10, str(dc['CLIENTES']), 1, ln=True)
            pdf.cell(50, 10, "USUARIO:", 1); pdf.cell(140, 10, str(dc['USUARIO']), 1, ln=True)
            pdf.cell(50, 10, "FECHA:", 1); pdf.cell(60, 10, str(dc['FE_CONSULT']), 1); pdf.cell(30, 10, "ESTADO:", 1); pdf.cell(50, 10, str(dc['ESTADO']), 1, ln=True)
            pdf.cell(50, 10, "TIEMPO (min):", 1); pdf.cell(140, 10, f"{dc['TIEMPO_RES']} minutos", 1, ln=True)
            pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, "DETALLE DE LA CONSULTA:", ln=True)
            pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, txt=str(dc["CONSULTAS"]), border=1)
            pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, "RESPUESTA:", ln=True)
            pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, txt=str(dc["RESPUESTAS"]), border=1)
            st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# ==========================================
# SECCIÓN 4: REPORTES ANALÍTICOS (NUEVA LÓGICA EXPORT)
# ==========================================
else:
    st.header("📊 Reportes Operativos")
    f1, f2, f3 = st.columns(3)
    with f1: f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique())); f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()))
    with f2: f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique())); f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True))
    with f3: f_mes = st.multiselect("Meses:", sorted(df_actual["MES"].unique()), format_func=lambda x: mes_d.get(x, x))
    
    df_rep = df_actual.copy()
    if f_cli: df_rep = df_rep[df_rep["CLIENTES"].isin(f_cli)]
    if f_mod: df_rep = df_rep[df_rep["MODULO"].isin(f_mod)]
    if f_con: df_rep = df_rep[df_con["CONSULTOR"].isin(f_con)]
    if f_ani: df_rep = df_rep[df_rep["ANIO"].isin(f_ani)]
    if f_mes: df_rep = df_rep[df_rep["MES"].isin(f_mes)]
    
    if not df_rep.empty:
        t_min = df_rep["TIEMPO_RES"].sum(); t_hs = t_min / 60
        m1, m2, m3 = st.columns(3); m1.metric("Tickets", len(df_rep)); m2.metric("Minutos", f"{t_min:,.0f}"); m3.metric("Horas", f"{t_hs:,.2f}")
        
        # Tabla agrupada (Lo que se ve en pantalla)
        res_agrupado = df_rep.groupby(["CLIENTES", "MODULO", "CONSULTOR", "ANIO", "MES"])["TIEMPO_RES"].sum().reset_index()
        res_agrupado["HORAS"] = (res_agrupado["TIEMPO_RES"] / 60).round(2)
        st.subheader("Vista Agrupada")
        st.dataframe(res_agrupado, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Exportar Reporte")
        
        # Pregunta si quiere agrupado o detallado
        tipo_ex = st.radio("Selecciona el nivel de detalle para Excel:", ["Agrupado (Resumen)", "Detallado (Ticket por Ticket)"], horizontal=True)
        
        col_ex1, col_ex2 = st.columns(2)
        
        with col_ex1:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                if "Agrupado" in tipo_ex:
                    res_agrupado.to_excel(w, index=False, sheet_name='Resumen_Agrupado')
                    nombre_f = "Reporte_Agrupado_GR.xlsx"
                else:
                    # Detallado: Incluye fecha, consulta y respuesta
                    columnas_det = ["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "MODULO", "CONSULTAS", "RESPUESTAS", "TIEMPO_RES"]
                    df_detallado = df_rep[columnas_det].copy()
                    df_detallado.to_excel(w, index=False, sheet_name='Detalle_Tickets')
                    nombre_f = "Reporte_Detallado_GR.xlsx"
            
            st.download_button(label="📥 Descargar Excel (.xlsx)", data=buf.getvalue(), file_name=nombre_f, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with col_ex2:
            # Reporte PDF (Resumen Institucional)
            pdf_r = FPDF()
            pdf_r.add_page(); pdf_r.set_font("Arial", 'B', 14)
            pdf_r.cell(0, 10, "GR Consulting - Resumen de Servicios", ln=True, align='C')
            pdf_r.set_font("Arial", size=9); pdf_r.ln(5)
            # Cabecera PDF
            pdf_r.cell(50, 8, "Cliente", 1); pdf_r.cell(40, 8, "Modulo", 1); pdf_r.cell(40, 8, "Consultor", 1); pdf_r.cell(25, 8, "Minutos", 1); pdf_r.cell(25, 8, "Horas", 1); pdf_r.ln()
            for i, row in res_agrupado.head(40).iterrows():
                pdf_r.cell(50, 8, str(row['CLIENTES'])[:20], 1); pdf_r.cell(40, 8, str(row['MODULO'])[:15], 1)
                pdf_r.cell(40, 8, str(row['CONSULTOR'])[:15], 1); pdf_r.cell(25, 8, str(row['TIEMPO_RES']), 1)
                pdf_r.cell(25, 8, str(row['HORAS']), 1); pdf_r.ln()
            pdf_r.ln(5); pdf_r.set_font("Arial", 'B', 10)
            pdf_r.cell(0, 10, f"TOTAL: {t_min} min / {t_hs:.2f} hs", ln=True)
            st.download_button("📥 Descargar PDF (.pdf)", pdf_r.output(dest='S').encode('latin-1'), "Resumen_Servicios_GR.pdf", mime="application/pdf")
    else:
        st.info("No hay datos para exportar con los filtros actuales.")
