import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="GR Consulting - Gestión Integral", layout="wide")
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
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Limpieza: Convertimos el nombre del consultor a mayúsculas para el login
        if "CONSULTOR" in df.columns:
            df["CONSULTOR"] = df["CONSULTOR"].astype(str).str.upper().str.strip()
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

def registrar_auditoria(id_ticket, accion, consultor):
    try:
        try: df_logs = conn.read(spreadsheet=url, worksheet="Log_Auditoria", ttl=0)
        except: df_logs = pd.DataFrame(columns=["ID_TICKET", "CONSULTOR", "FECHA_HORA", "ACCION"])
        nuevo_log = pd.DataFrame([{"ID_TICKET": id_ticket, "CONSULTOR": consultor, "FECHA_HORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "ACCION": accion}])
        conn.update(spreadsheet=url, worksheet="Log_Auditoria", data=pd.concat([df_logs, nuevo_log], ignore_index=True))
    except: pass

# ==========================================
# 🔑 PANTALLA DE LOGIN (CONSULTOR = USUARIO)
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login_form"):
        # Ahora el usuario ingresa su nombre de Consultor directamente
        c_input = st.text_input("Consultor (Nombre)").strip().upper()
        p_input = st.text_input("Contraseña", type="password")
        if st.form_submit_button("INGRESAR"):
            df_u = obtener_config()
            # Validación: Consultor y Password
            match = df_u[(df_u["CONSULTOR"] == c_input) & (df_u["PASSWORD"].astype(str) == str(p_input))]
            if not match.empty:
                st.session_state.autenticado = True
                st.session_state.user_data = match.iloc[0].to_dict()
                st.rerun()
            else: st.error("⚠️ Consultor o contraseña incorrectos")
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
    st.caption(f"Rol: {user.get('ROL', 'USER')}")
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

# Menú dinámico
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if user.get("ROL") == "ADMIN": btns.append("⚙️ PERMISOS")
cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b

st.divider()

# --- SECCIÓN: NUEVO ---
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Cargando Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        # El consultor se bloquea al nombre del login
        c1.text_input("Atendido por", value=nombre_consultor, disabled=True)
        est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        cli_n = c2.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
        usu_n = c2.text_input("Usuario Cliente *").upper()
        fe_n = c3.date_input("Fecha", datetime.now()); tie_n = c3.number_input("Minutos *", min_value=0)
        con_n = st.text_area("Consulta *"); rta_n = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR TICKET"):
            if usu_n and con_n and rta_n and tie_n > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "ESTADO": est, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "CONSULTAS": con_n, "RESPUESTAS": rta_n, "TIEMPO_RES": tie_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos_tickets().drop(columns=["ID_NUM"], errors="ignore"), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", nombre_consultor)
                st.balloons(); st.rerun()

# --- SECCIÓN: DASHBOARDS (32 KPIs DETALLADOS) ---
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    p_db1 = str(user.get("ACCESO_DB1", "NO")).upper() == "SI"
    p_db2 = str(user.get("ACCESO_DB2", "NO")).upper() == "SI"
    p_db3 = str(user.get("ACCESO_DB3", "NO")).upper() == "SI"
    
    if not any([p_db1, p_db2, p_db3]): st.error("🚫 Sin permisos de Dashboard.")
    else:
        df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
        t_list = []
        if p_db1: t_list.append("📋 OPERATIVO")
        if p_db2: t_list.append("⚡ PERFORMANCE")
        if p_db3: t_list.append("💰 FINANCIERO")
        tabs = st.tabs(t_list)
        
        idx = 0
        if p_db1:
            with tabs[idx]:
                st.subheader("Volumen y Estado")
                # KPIs solicitados
                m1, m2, m3 = st.columns(3)
                m1.metric("Cant. Tickets", len(df_dash))
                cer = len(df_dash[df_dash["ESTADO"]=="CERRADO"])
                m2.metric("Tickets Cerrados", cer)
                m3.metric("% Eficacia", f"{(cer/len(df_dash)*100):.1f}%" if len(df_dash)>0 else "0%")
                st.bar_chart(df_dash["CLIENTES"].value_counts())
            idx += 1
        if p_db2:
            with tabs[idx]:
                st.subheader("Ocupación y Sobrecarga")
                df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
                st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
            idx += 1
        if p_db3:
            with tabs[idx]:
                df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60)*df_dash["VALOR_HORA"]
                st.metric("Inversión Total", f"$ {df_dash['COSTO'].sum():,.2f}")
                st.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())

# --- SECCIÓN: PERMISOS (SOLO ADMINS) ---
elif st.session_state.menu_activo == "⚙️ PERMISOS":
    st.header("⚙️ Gestión de Consultores y Accesos")
    df_edit = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar Cambios"):
        conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_edit)
        st.success("Configuración actualizada.")
