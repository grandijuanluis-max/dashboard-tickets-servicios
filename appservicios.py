import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIFICACIÓN MAESTRA
st.set_page_config(page_title="GR Consulting - Gestión Integral BI", layout="wide")
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

# --- FUNCIONES DE CARGA Y NORMALIZACIÓN ---
def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in df.columns:
            # Limpieza para asegurar acceso de JUANLUIS y otros
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

def registrar_auditoria(id_ticket, accion, consultor):
    try:
        try: df_logs = conn.read(spreadsheet=url, worksheet="Log_Auditoria", ttl=0)
        except: df_logs = pd.DataFrame(columns=["ID_TICKET", "CONSULTOR", "FECHA_HORA", "ACCION"])
        nuevo_log = pd.DataFrame([{"ID_TICKET": id_ticket, "CONSULTOR": consultor, "FECHA_HORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "ACCION": accion}])
        conn.update(spreadsheet=url, worksheet="Log_Auditoria", data=pd.concat([df_logs, nuevo_log], ignore_index=True))
    except: pass

# ==========================================
# 🔐 LOGIN (SISTEMA BLINDADO)
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login_form"):
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
user_info = df_config[df_config["CONSULTOR"] == nombre_consultor].iloc[0]

# SIDEBAR: Filtros Maestros
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False; st.rerun()
    st.divider()
    st.header("🎯 Filtros Maestros")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()))
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()))
    f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()))
    f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True))
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# Dataframe Filtrado Maestro (df_f)
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# NAVEGACIÓN
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if user_info.get("ROL") == "ADMIN": btns.append("⚙️ PERMISOS")
cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b
st.divider()

# ==========================================
# SECCIÓN 1: NUEVO
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Consultor", value=nombre_consultor, disabled=True)
            tipo_n = st.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
            prio_n = st.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
            est_n = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            cli_n = st.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
            usu_n = st.text_input("Usuario Cliente *").upper()
            ate_n = st.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
        with c3:
            mod_n = st.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"])
            fe_n = st.date_input("Fecha", datetime.now()); tie_n = st.number_input("Minutos *", min_value=0)
            on_n = st.radio("Online?", ["SI", "NO"], horizontal=True)
        con_txt = st.text_area("Consulta *"); rta_txt = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_txt and rta_txt and tie_n > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "TIPO_CONS": tipo_n, "PRIORIDAD": prio_n, "ESTADO": est_n, "ATENCION": ate_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ONLINE": on_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos_tickets().drop(columns=["ID_NUM"], errors="ignore"), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", nombre_consultor); st.balloons(); st.rerun()

# ==========================================
# SECCIÓN 2: MODIFICAR (REVISADO)
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    # 1. Tomamos los datos que ya pasaron por los Filtros Maestros (df_f)
    # 2. Filtramos solo los que están ABIERTOS o EN PROCESO
    df_mod_list = df_f[df_f["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
    
    if not df_mod_list.empty:
        sel_m = st.selectbox("Seleccione Ticket (Filtrado por Maestro + Estado):", df_mod_list.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {str(r['CONSULTAS'])[:40]}...", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
        with st.form("f_mod"):
            st.warning(f"Modificando Ticket #{id_m}")
            c1, c2 = st.columns(2)
            n_est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]))
            n_tie = c2.number_input("Tiempo (min)", value=int(dm["TIEMPO_RES"]))
            n_con = st.text_area("Consulta", value=dm["CONSULTAS"]); n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
            if st.form_submit_button("🔥 ACTUALIZAR TICKET"):
                df_actual.at[idx_f, "ESTADO"] = n_est; df_actual.at[idx_f, "TIEMPO_RES"] = n_tie
                df_actual.at[idx_f, "CONSULTAS"] = n_con; df_actual.at[idx_f, "RESPUESTAS"] = n_rta
                df_actual.at[idx_f, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                registrar_auditoria(id_m, "MODIFICACION", nombre_consultor); st.success("Guardado."); st.rerun()
    else:
        st.info("No hay tickets ABIERTOS o EN PROCESO bajo los filtros seleccionados.")

# ==========================================
# SECCIÓN 3: CONSULTAR (CON PDF TÉCNICO)
# ==========================================
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Ver Ficha:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#","")); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"Ficha #{id_c}"); st.info(f"**Consulta:** {dc['CONSULTAS']}"); st.success(f"**Respuesta:** {dc['RESPUESTAS']}")
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 15, "GR Consulting - Reporte de Servicio", ln=True, align='C'); pdf.ln(5); pdf.set_font("Arial", size=10)
            pdf.cell(40, 10, "ATENDIDO POR:", 1); pdf.cell(150, 10, str(dc['CONSULTOR']), 1, ln=True)
            pdf.cell(40, 10, "CLIENTE:", 1); pdf.cell(150, 10, str(dc['CLIENTES']), 1, ln=True)
            pdf.cell(40, 10, "FECHA:", 1); pdf.cell(60, 10, str(dc['FE_CONSULT']), 1); pdf.cell(40, 10, "ESTADO:", 1); pdf.cell(50, 10, str(dc['ESTADO']), 1, ln=True)
            pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 10, "DETALLE CONSULTA:", ln=True); pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, str(dc['CONSULTAS']), 1)
            pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 10, "RESPUESTA:", ln=True); pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, str(dc['RESPUESTAS']), 1)
            st.download_button("📥 PDF Ficha", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# ==========================================
# SECCIÓN 4: REPORTES (TOTAL HS Y EXCEL DINÁMICO)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Reportes de Gestión")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60; st.metric("Total Horas Filtradas", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📥 Excel")
            tipo_xls = st.radio("Formato:", ["Resumido (Módulo)", "Detallado (Ticket)"], horizontal=True)
            buf = io.BytesIO(); 
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                if "Resumido" in tipo_xls: res.to_excel(w, index=False)
                else:
                    df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "MODULO", "CONSULTOR", "TIEMPO_RES"]].copy()
                    df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2); df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                    df_det.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", buf.getvalue(), "GR_Reporte.xlsx")
        with c2:
            st.subheader("📥 PDF Analítico")
            pdf_a = FPDF(); pdf_a.add_page(); pdf_a.set_font("Arial", 'B', 11); pdf_a.cell(0, 8, "FILTROS UTILIZADOS:", ln=True); pdf_a.set_font("Arial", size=10)
            pdf_a.cell(0, 6, f"Clientes: {', '.join(f_cli) if f_cli else 'TODOS'}", ln=True); pdf_a.ln(5)
            pdf_a.set_font("Arial", 'B', 14); pdf_a.cell(0, 10, "GR Consulting - Resumen Analítico", ln=True, align='C'); pdf_a.ln(5)
            pdf_a.set_font("Arial", 'B', 9); pdf_a.cell(45, 8, "Cliente", 1); pdf_a.cell(40, 8, "Modulo", 1); pdf_a.cell(45, 8, "Consultor", 1); pdf_a.cell(30, 8, "Horas", 1, ln=True); pdf_a.set_font("Arial", size=9)
            for _, r in res.iterrows(): pdf_a.cell(45, 7, str(r['CLIENTES']), 1); pdf_a.cell(40, 7, str(r['MODULO']), 1); pdf_a.cell(45, 7, str(r['CONSULTOR']), 1); pdf_a.cell(30, 7, str(r['HORAS']), 1, ln=True)
            pdf_a.ln(5); pdf_a.set_font("Arial", 'B', 12); pdf_a.cell(0, 10, f"TOTAL GENERAL: {t_hs:,.2f} hs", align='R')
            st.download_button("📥 PDF Analítico", pdf_a.output(dest='S').encode('latin-1'), "Analitico_GR.pdf")

# ==========================================
# SECCIÓN 5: DASHBOARDS (TODOS ABIERTOS)
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    st.header("📈 Centro Operativo")
    df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
    tab1, tab2, tab3 = st.tabs(["📋 Operativo", "⚡ Performance", "💰 Financiero"])
    with tab1:
        st.subheader("Carga por Módulo"); st.bar_chart(df_dash.groupby("MODULO")["TIEMPO_RES"].sum())
    with tab2:
        st.subheader("Tiempo Real vs Disponible"); df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index(); st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
    with tab3:
        df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * pd.to_numeric(df_dash["VALOR_HORA"]); st.metric("Inversión Total", f"$ {df_dash['COSTO'].sum():,.2f}"); st.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())

# --- PERMISOS ---
elif st.session_state.menu_activo == "⚙️ PERMISOS":
    st.header("⚙️ Gestión de Usuarios")
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar"): conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed); st.rerun()
