import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIFICACIÓN MAESTRA
st.set_page_config(page_title="GR Consulting - Gestión Integral", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTADO DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_logueado" not in st.session_state:
    st.session_state.usuario_logueado = None
if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

# --- FUNCIONES DE DATOS (CORRECCIÓN LOGIN Y PERMISOS) ---
def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in df.columns:
            # Limpieza para que JUANLUIS entre con 2371 sin el error del .0
            df[col] = df[col].astype(str).str.strip().str.upper().str.replace(r"\.0$", "", regex=True)
        return df
    except: return pd.DataFrame()

def obtener_datos_tickets():
    try:
        df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        else: df["ID_NUM"] = 0
        df["TIEMPO_RES"] = pd.to_numeric(df.get("TIEMPO_RES", 0), errors='coerce').fillna(0)
        df["ANIO"] = pd.to_numeric(df.get("ANIO", 0), errors='coerce').fillna(0).astype(int)
        df["MES"] = pd.to_numeric(df.get("MES", 0), errors='coerce').fillna(0).astype(int)
        return df.fillna("")
    except: return pd.DataFrame()

# ==========================================
# 🔐 LOGIN (SISTEMA CORREGIDO)
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login_form"):
        # Login blindado para corregir el error de la imagen enviada
        c_input = st.text_input("Consultor (Nombre)").strip().upper()
        p_input = st.text_input("Contraseña", type="password").strip()
        if st.form_submit_button("INGRESAR"):
            df_u = obtener_config()
            match = df_u[(df_u["CONSULTOR"] == c_input) & (df_u["PASSWORD"] == p_input)]
            if not match.empty:
                st.session_state.autenticado = True
                st.session_state.usuario_logueado = c_input
                st.rerun()
            else: st.error("⚠️ Consultor o contraseña incorrectos.")
    st.stop()

# --- CARGA POST-LOGIN ---
nombre_consultor = st.session_state.usuario_logueado
df_actual = obtener_datos_tickets()
df_config = obtener_config()

# SIDEBAR: Filtros Maestros (Controlan todo el sistema)
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()
    st.divider()
    st.header("🎯 Filtros Maestros")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()) if not df_actual.empty else [])
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()) if not df_actual.empty else [])
    f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True) if not df_actual.empty else [])
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# Filtros Globales
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# NAVEGACIÓN
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
cols_menu = st.columns(5)
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b
st.divider()

# ==========================================
# SECCIÓN 1: NUEVO
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Cargando Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        c1.text_input("Consultor", value=nombre_consultor, disabled=True)
        prio = c1.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
        est_n = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        cli_n = c2.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
        usu_n = c2.text_input("Usuario Cliente *").upper()
        fe_n = c3.date_input("Fecha", datetime.now()); tie_n = c3.number_input("Minutos *", min_value=0)
        con_n = st.text_area("Consulta *"); rta_n = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_n and rta_n and tie_n > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "PRIORIDAD": prio, "ESTADO": est_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "CONSULTAS": con_n, "RESPUESTAS": rta_n, "TIEMPO_RES": tie_n, "ANIO": fe_n.year, "MES": fe_n.month}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos_tickets().drop(columns=["ID_NUM"], errors="ignore"), nuevo], ignore_index=True))
                st.balloons(); st.rerun()

# ==========================================
# SECCIÓN 2: MODIFICAR
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    pend = df_actual[df_actual["ESTADO"].str.upper() != "CERRADO"].copy()
    if not pend.empty:
        sel_m = st.selectbox("Ticket:", pend.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {str(r['CONSULTAS'])[:40]}...", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]
        dm = df_actual.loc[idx_f]
        with st.form("f_mod"):
            c1, c2 = st.columns(2)
            n_est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]))
            n_tie = c2.number_input("Tiempo (min)", value=int(dm["TIEMPO_RES"]))
            n_con = st.text_area("Consulta", value=dm["CONSULTAS"])
            n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
            if st.form_submit_button("🔥 ACTUALIZAR"):
                df_actual.at[idx_f, "ESTADO"] = n_est; df_actual.at[idx_f, "TIEMPO_RES"] = n_tie
                df_actual.at[idx_f, "CONSULTAS"] = n_con; df_actual.at[idx_f, "RESPUESTAS"] = n_rta
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                st.success("Ticket actualizado."); st.rerun()

# ==========================================
# SECCIÓN 3: CONSULTAR (REPORTE PDF IDÉNTICO)
# ==========================================
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    st.header("🔍 Consultas de Servicio")
    if not df_f.empty:
        op_c = df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1)
        sel_c = st.selectbox("Seleccione para ver:", op_c)
        id_c = int(sel_c.split(" |")[0].replace("#",""))
        dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        
        with st.container(border=True):
            st.subheader(f"Ticket #{id_c}")
            st.info(f"**Consulta:** {dc['CONSULTAS']}")
            st.success(f"**Respuesta:** {dc['RESPUESTAS']}")
            
            # GENERACIÓN PDF "COPAADO" (Igual a la imagen)
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 18)
            pdf.cell(0, 15, "GR Consulting - Servicios", ln=True, align='C'); pdf.ln(5)
            pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"Ticket #{id_c}", ln=True)
            pdf.set_font("Arial", size=10)
            # Tabla técnica
            pdf.cell(40, 10, "ATENDIDO POR:", 1); pdf.cell(150, 10, str(dc['CONSULTOR']), 1, ln=True)
            pdf.cell(40, 10, "CLIENTE:", 1); pdf.cell(150, 10, str(dc['CLIENTES']), 1, ln=True)
            pdf.cell(40, 10, "USUARIO:", 1); pdf.cell(150, 10, str(dc['USUARIO']), 1, ln=True)
            pdf.cell(40, 10, "FECHA:", 1); pdf.cell(50, 10, str(dc['FE_CONSULT']), 1); pdf.cell(40, 10, "ESTADO:", 1); pdf.cell(60, 10, str(dc['ESTADO']), 1, ln=True)
            pdf.cell(40, 10, "TIEMPO (min):", 1); pdf.cell(150, 10, f"{dc['TIEMPO_RES']} minutos", 1, ln=True); pdf.ln(10)
            # Secciones de texto
            pdf.set_font("Arial", 'B', 11); pdf.cell(0, 10, "DETALLE DE LA CONSULTA:", ln=True)
            pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, str(dc['CONSULTAS']), border=1); pdf.ln(5)
            pdf.set_font("Arial", 'B', 11); pdf.cell(0, 10, "RESPUESTA:", ln=True)
            pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, str(dc['RESPUESTAS']), border=1)
            st.download_button("📥 Descargar PDF Ficha", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# ==========================================
# SECCIÓN 4: REPORTES (XLS Y PDF ANALÍTICO)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Centro de Reportes")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Total de Horas", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        
        c1, c2 = st.columns(2)
        with c1: # EXCEL (Ticket por ticket o Resumen)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                cols_xls = ["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES"]
                df_det = df_f[cols_xls].copy(); df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2)
                df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                df_det.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel Detallado", buf.getvalue(), "Reporte_GR.xlsx")
        with c2: # PDF ANALÍTICO
            pdf_a = FPDF(); pdf_a.add_page(); pdf_a.set_font("Arial", 'B', 14)
            pdf_a.cell(0, 10, "Reporte Analítico de Tiempos", ln=True, align='C'); pdf_a.ln(5)
            pdf_a.set_font("Arial", size=10)
            for _, row in res.iterrows(): pdf_a.cell(0, 8, f"{row['CLIENTES']} | {row['CONSULTOR']}: {row['HORAS']} hs", ln=True, border=1)
            pdf_a.ln(5); pdf_a.set_font("Arial", 'B', 12); pdf_a.cell(0, 10, f"TOTAL GENERAL: {t_hs:,.2f} hs", align='R')
            st.download_button("📥 Descargar PDF Analítico", pdf_a.output(dest='S').encode('latin-1'), "Analitico.pdf")

# ==========================================
# SECCIÓN 5: DASHBOARDS (TODOS ABIERTOS)
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    st.header("📈 Centro Estratégico (Acceso Abierto)")
    df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
    tab1, tab2, tab3 = st.tabs(["📋 DB1: OPERATIVO", "⚡ DB2: PERFORMANCE", "💰 DB3: FINANCIERO"])
    with tab1:
        st.subheader("Volumen y Eficacia")
        st.bar_chart(df_dash["CLIENTES"].value_counts())
    with tab2:
        st.subheader("Performance vs Capacidad")
        df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
        st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
    with tab3:
        st.subheader("Inversión Operativa")
        df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * pd.to_numeric(df_dash["VALOR_HORA"])
        st.metric("Inversión Total", f"$ {df_dash['COSTO'].sum():,.2f}")
        st.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())
