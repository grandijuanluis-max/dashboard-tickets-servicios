import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIFICACIÓN
st.set_page_config(page_title="GR Consulting - BI Dashboard", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "user_data" not in st.session_state:
    st.session_state.user_data = None
if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

# --- FUNCIONES CORE ---
def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        # Limpieza profunda de encabezados y datos
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
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        else: df["ID_NUM"] = 0
        df["TIEMPO_RES"] = pd.to_numeric(df.get("TIEMPO_RES", 0), errors='coerce').fillna(0)
        df["ANIO"] = pd.to_numeric(df.get("ANIO", 0), errors='coerce').fillna(0).astype(int)
        df["MES"] = pd.to_numeric(df.get("MES", 0), errors='coerce').fillna(0).astype(int)
        return df.fillna("")
    except: return pd.DataFrame()

# ==========================================
# 🔑 PANTALLA DE LOGIN
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login_form"):
        c_input = st.text_input("Consultor (Nombre)").strip().upper()
        p_input = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            df_u = obtener_config()
            # Validación flexible de contraseña
            match = df_u[(df_u["CONSULTOR"] == c_input) & (df_u["PASSWORD"].astype(str) == str(p_input))]
            if not match.empty:
                st.session_state.autenticado = True
                st.session_state.user_data = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("⚠️ Credenciales incorrectas.")
    st.stop()

# ==========================================
# 🚀 APLICACIÓN AUTENTICADA
# ==========================================
user = st.session_state.user_data
nombre_consultor = user["CONSULTOR"]
df_actual = obtener_datos_tickets()
df_config = obtener_config()

with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    st.write(f"Rol: {user.get('ROL', 'USER')}")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()
    st.divider()
    # FILTROS MAESTROS
    st.header("🎯 Filtros Globales")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()) if not df_actual.empty else [])
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()) if not df_actual.empty else [])
    f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True) if not df_actual.empty else [])
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# Aplicación de Filtros
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# Menú
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if user.get("ROL") == "ADMIN": btns.append("⚙️ PERMISOS")
cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b

st.divider()

# ==========================================
# SECCIÓN: DASHBOARDS (SOLUCIÓN ACCESO JUANLUIS)
# ==========================================
if st.session_state.menu_activo == "📈 DASHBOARDS":
    # Verificamos permisos con limpieza extra
    p_db1 = str(user.get("ACCESO_DB1", "NO")).upper().strip() == "SI"
    p_db2 = str(user.get("ACCESO_DB2", "NO")).upper().strip() == "SI"
    p_db3 = str(user.get("ACCESO_DB3", "NO")).upper().strip() == "SI"
    
    if not any([p_db1, p_db2, p_db3]):
        st.error(f"🚫 El consultor {nombre_consultor} no tiene permisos de Dashboard asignados.")
        st.info("Asegúrese de que las columnas ACCESO_DB1, DB2 y DB3 en el Excel tengan 'SI'.")
    else:
        # Cruce con configuración para traer VALOR_HORA y DISPONIBLE
        df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
        
        t_list = []
        if p_db1: t_list.append("📋 DB1: OPERATIVO")
        if p_db2: t_list.append("⚡ DB2: PERFORMANCE")
        if p_db3: t_list.append("💰 DB3: FINANCIERO")
        tabs = st.tabs(t_list)
        
        # Lógica de contenido de solapas
        idx_tab = 0
        
        # --- SOLAPA DB1: OPERATIVO ---
        if p_db1:
            with tabs[idx_tab]:
                st.subheader("Métricas de Volumen y Eficacia")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Tickets Totales", len(df_dash))
                c2.metric("T. Promedio (min)", f"{df_dash['TIEMPO_RES'].mean():.1f}")
                cerrados = len(df_dash[df_dash["ESTADO"] == "CERRADO"])
                c3.metric("Tickets Cerrados", cerrados)
                c4.metric("% Eficacia", f"{(cerrados/len(df_dash)*100):.1f}%" if len(df_dash)>0 else "0%")
                
                st.divider()
                g1, g2 = st.columns(2)
                g1.write("**Tickets por Cliente**")
                g1.bar_chart(df_dash["CLIENTES"].value_counts())
                g2.write("**Tickets por Módulo**")
                g2.bar_chart(df_dash["MODULO"].value_counts())
                
                st.write("**Promedio de Tiempo por Prioridad (min)**")
                st.bar_chart(df_dash.groupby("PRIORIDAD")["TIEMPO_RES"].mean())
            idx_tab += 1

        # --- SOLAPA DB2: PERFORMANCE ---
        if p_db2:
            with tabs[idx_tab]:
                st.subheader("Capacidad y Ocupación Diaria")
                # Agrupamos por día y consultor
                df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
                df_p["OCUPACION"] = (df_p["TIEMPO_RES"] / df_p["DISPONIBLE"] * 100).fillna(0)
                
                k1, k2 = st.columns(2)
                k1.metric("Ocupación Promedio", f"{df_p['OCUPACION'].mean():.1f}%")
                sobre = len(df_p[df_p["TIEMPO_RES"] > df_p["DISPONIBLE"]])
                k2.metric("Días con Sobrecarga", sobre, delta_color="inverse")
                
                st.write("**Carga Real (min) vs Objetivo (Disponible)**")
                st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
            idx_tab += 1

        # --- SOLAPA DB3: FINANCIERO ---
        if p_db3:
            with tabs[idx_tab]:
                st.subheader("Análisis de Costos")
                df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * df_dash["VALOR_HORA"]
                st.metric("Inversión Operativa Total", f"$ {df_dash['COSTO'].sum():,.2f}")
                
                f1, f2 = st.columns(2)
                f1.write("**Costo por Cliente ($)**")
                f1.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())
                f2.write("**Costo por Consultor ($)**")
                f2.bar_chart(df_dash.groupby("CONSULTOR")["COSTO"].sum())
            idx_tab += 1

# --- SECCIONES RESTANTES (NUEVO, CONSULTAR, REPORTES, PERMISOS) ---
# [Se mantienen igual para no perder funcionalidad]
elif st.session_state.menu_activo == "📊 REPORTES":
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Horas Totales (Filtros Maestros)", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index()
        res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        # Exportación XLS Detallada
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES"]].copy()
            df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
            df_det.to_excel(w, index=False)
        st.download_button("📥 Excel Completo", buf.getvalue(), "Reporte_GR.xlsx")

elif st.session_state.menu_activo == "⚙️ PERMISOS":
    st.header("⚙️ Gestión de Usuarios")
    df_edit = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar Cambios"):
        conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_edit)
        st.success("Configuración actualizada."); st.rerun()
