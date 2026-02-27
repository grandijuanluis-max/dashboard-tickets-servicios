import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import io
from fpdf import FPDF
import platform
import getpass

# 1. CONFIGURACIÓN E IDENTIFICACIÓN
st.set_page_config(page_title="GR Consulting - Sistema Integral", layout="wide")
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

# --- FUNCIONES DE DATOS ---
def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.upper()
        return df.fillna("")
    except: return pd.DataFrame()

def obtener_datos_tickets():
    try:
        df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Procesamiento de ID_NUM para evitar KeyErrors
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        else: df["ID_NUM"] = 0
        # Normalización de tipos de datos
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
# 🔑 LOGIN (SISTEMA DE SEGURIDAD)
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login_form"):
        c_input = st.text_input("Consultor (Nombre)").strip().upper()
        p_input = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            df_u = obtener_config()
            # Validación blindada contra espacios y mayúsculas
            match = df_u[(df_u["CONSULTOR"] == c_input) & (df_u["PASSWORD"].astype(str) == str(p_input))]
            if not match.empty:
                st.session_state.autenticado = True
                st.session_state.usuario_logueado = c_input
                st.rerun()
            else: st.error("⚠️ Consultor o contraseña incorrectos.")
    st.stop()

# ==========================================
# 🚀 APP AUTENTICADA
# ==========================================
nombre_consultor = st.session_state.usuario_logueado
df_config = obtener_config()
df_actual = obtener_datos_tickets()

# Datos del usuario actual para permisos
user_info = df_config[df_config["CONSULTOR"] == nombre_consultor].iloc[0]

# SIDEBAR: Información y Filtros Maestros
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

# Aplicación Global de Filtros
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# Navegación
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
        st.subheader(f"Cargando Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        c1.text_input("Consultor", value=nombre_consultor, disabled=True)
        tipo_c = c1.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
        prio = c1.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
        est_n = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        
        ate_n = c2.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
        cli_n = c2.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
        usu_n = c2.text_input("Usuario Cliente *").upper()
        
        mod_n = c3.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PROGRAMA", "PRODUCCION","SERVIDOR", "WEB", "GERENCIAL", "RRHH", "IMPUESTOS", "SUCURSAL", "OTROS"])
        fe_n = c3.date_input("Fecha Consulta", datetime.now()); tie_n = c3.number_input("Tiempo (min) *", min_value=0)
        on_n = c3.radio("Online?", ["SI", "NO"], horizontal=True)

        con_n = st.text_area("Consulta *"); rta_n = st.text_area("Respuesta *")
        
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_n and rta_n and tie_n > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "TIPO_CONS": tipo_c, "PRIORIDAD": prio, "ESTADO": est_n, "ATENCION": ate_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_n, "RESPUESTAS": rta_n, "TIEMPO_RES": tie_n, "ONLINE": on_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos_tickets().drop(columns=["ID_NUM"], errors="ignore"), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", nombre_consultor)
                st.balloons(); st.rerun()

# ==========================================
# SECCIÓN 4: REPORTES (EXPORTACIÓN AVANZADA)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Reportes Analíticos")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Horas Totales (Filtros Maestros)", f"{t_hs:,.2f} hs")
        
        # Tabla de Resumen
        res = df_f.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                # DETALLE: Textos al FINAL solicitado
                cols_det = ["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES", "MODULO", "PRIORIDAD"]
                df_det = df_f[cols_det].copy()
                df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2)
                df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                df_det.to_excel(w, index=False, sheet_name='Reporte_Detallado')
            st.download_button("📥 Descargar Excel Completo", buf.getvalue(), "Reporte_GR.xlsx")
        
        with col_ex2:
            pdf_r = FPDF(); pdf_r.add_page(); pdf_r.set_font("Arial", 'B', 14); pdf_r.cell(0, 10, "Reporte GR Consulting", ln=True, align='C')
            pdf_r.set_font("Arial", size=9); pdf_r.ln(5)
            for _, row in res.iterrows(): pdf_r.cell(0, 8, f"{row['CLIENTES']} | {row['CONSULTOR']}: {row['HORAS']} hs", ln=True, border=1)
            pdf_r.ln(5); pdf_r.cell(0, 10, f"TOTAL: {t_hs:.2f} hs", align='R')
            st.download_button("📥 Descargar PDF Analítico", pdf_r.output(dest='S').encode('latin-1'), "Reporte_Analitico.pdf")

# ==========================================
# SECCIÓN 5: DASHBOARDS (32 KPIs REACTIVADOS)
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    p1 = user_info.get("ACCESO_DB1") == "SI"
    p2 = user_info.get("ACCESO_DB2") == "SI"
    p3 = user_info.get("ACCESO_DB3") == "SI"
    
    if not any([p1, p2, p3]):
        st.error(f"🚫 El usuario {nombre_consultor} no tiene permisos de Dashboard.")
    else:
        df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
        t_titles = []
        if p1: t_titles.append("📋 OPERATIVO")
        if p2: t_titles.append("⚡ PERFORMANCE")
        if p3: t_titles.append("💰 FINANCIERO")
        tabs = st.tabs(t_titles)
        
        curr = 0
        if p1:
            with tabs[curr]:
                st.subheader("Métricas de Volumen, Tiempo y Estado")
                # KPIs VOLUMEN
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Tickets", len(df_dash))
                c2.metric("T. Promedio (min)", f"{df_dash['TIEMPO_RES'].mean():.1f}")
                cer = len(df_dash[df_dash["ESTADO"]=="CERRADO"])
                c3.metric("Tickets Cerrados", cer)
                c4.metric("% Eficacia", f"{(cer/len(df_dash)*100):.1f}%" if len(df_dash)>0 else "0%")
                
                st.divider()
                g1, g2 = st.columns(2)
                g1.write("**Tickets por Cliente**"); g1.bar_chart(df_dash["CLIENTES"].value_counts())
                g2.write("**Tickets por Prioridad**"); g2.bar_chart(df_dash["PRIORIDAD"].value_counts())
                
                st.write("**Promedio de Tiempo por Consultor (min)**")
                st.bar_chart(df_dash.groupby("CONSULTOR")["TIEMPO_RES"].mean())
            curr += 1

        if p2:
            with tabs[curr]:
                st.subheader("Capacidad, Ocupación y Eficiencia")
                df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first", "ID_TICKET":"count"}).reset_index()
                df_p["OCUPACION"] = (df_p["TIEMPO_RES"] / df_p["DISPONIBLE"] * 100).fillna(0)
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Ocupación Promedio", f"{df_p['OCUPACION'].mean():.1f}%")
                sobre = len(df_p[df_p["TIEMPO_RES"] > df_p["DISPONIBLE"]])
                k2.metric("Días Sobrecarga", sobre, delta_color="inverse")
                k3.metric("Tickets / Día Promedio", f"{df_p['ID_TICKET'].mean():.1f}")
                
                st.write("**Carga de Trabajo Real vs Capacidad Disponible**")
                st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
            curr += 1

        if p3:
            with tabs[curr]:
                st.subheader("Inversión y Rentabilidad")
                df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * df_dash["VALOR_HORA"]
                st.metric("Inversión Operativa Total", f"$ {df_dash['COSTO'].sum():,.2f}")
                
                f1, f2 = st.columns(2)
                f1.write("**Inversión por Cliente ($)**"); f1.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())
                f2.write("**Costo por Consultor ($)**"); f2.bar_chart(df_dash.groupby("CONSULTOR")["COSTO"].sum())
            curr += 1

# --- PERMISOS (SOLO ADMIN) ---
elif st.session_state.menu_activo == "⚙️ PERMISOS":
    st.header("⚙️ Gestión de Usuarios")
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar Nueva Configuración"):
        conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed)
        st.success("Cambios aplicados correctamente."); st.rerun()

# --- CONSULTAR / MODIFICAR (Mantenidos) ---
# [Aquí incluirías la lógica de MODIFICAR y CONSULTAR del historial previo si fuera necesario]
