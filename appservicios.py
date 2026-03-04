import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
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

# Inicialización de fechas (Persistencia)
if "f_desde" not in st.session_state:
    st.session_state.f_desde = date(2020, 1, 1)
if "f_hasta" not in st.session_state:
    st.session_state.f_hasta = date.today()

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

# --- FUNCIONES DE CARGA Y PROTECCIÓN ---
def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        if df.empty: return pd.DataFrame()
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper().str.replace(r"\.0$", "", regex=True)
        return df
    except: return pd.DataFrame()

def obtener_datos_tickets():
    try:
        df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        if df.empty: df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        if df.empty: return pd.DataFrame()
        
        df.columns = [str(c).strip().upper().replace('AÑO', 'ANIO') for c in df.columns]
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        
        if "FE_CONSULT" in df.columns:
            df["FE_DT"] = pd.to_datetime(df["FE_CONSULT"], format='%d/%m/%Y', errors='coerce')
        
        df["TIEMPO_RES"] = pd.to_numeric(df.get("TIEMPO_RES", 0), errors='coerce').fillna(0)
        df["ANIO"] = pd.to_numeric(df.get("ANIO", 0), errors='coerce').fillna(0).astype(int)
        df["MES"] = pd.to_numeric(df.get("MES", 0), errors='coerce').fillna(0).astype(int)
        return df.fillna("")
    except: return pd.DataFrame()

# 🛡️ FUNCIÓN DE GUARDADO SEGURO
def guardar_seguro(df_nuevo, accion_msg):
    try:
        base_nube = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        if not base_nube.empty and len(df_nuevo) < len(base_nube) and "MODIFICACION" not in accion_msg:
            st.error("🚨 BLOQUEO DE SEGURIDAD: Operación cancelada para proteger los registros.")
            return False
        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_nuevo)
        return True
    except:
        st.error("❌ Error de comunicación con la base de datos.")
        return False

# ==========================================
# 🔐 LOGIN
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login"):
        c_in = st.text_input("Consultor").strip().upper()
        p_in = st.text_input("Contraseña", type="password").strip()
        if st.form_submit_button("INGRESAR"):
            df_u = obtener_config()
            if not df_u.empty and "CONSULTOR" in df_u.columns:
                match = df_u[(df_u["CONSULTOR"] == c_in) & (df_u["PASSWORD"] == p_in)]
                if not match.empty:
                    st.session_state.autenticado, st.session_state.usuario_logueado = True, c_in
                    st.rerun()
    st.stop()

# --- CARGA POST-LOGIN ---
nombre_consultor = st.session_state.usuario_logueado
df_config, df_actual = obtener_config(), obtener_datos_tickets()
user_info = df_config[df_config["CONSULTOR"] == nombre_consultor].iloc[0] if not df_config.empty else {"ROL": "USER"}
es_admin = str(user_info.get("ROL")).upper() == "ADMIN"

# ==========================================
# 🎯 SIDEBAR (FILTROS Y VARIABLES TEMPORALES)
# ==========================================
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False; st.rerun()
    st.divider()
    
    # 📅 SECCIÓN DE FECHAS (Solo en Reportes y Dashboard)
    if st.session_state.menu_activo in ["📊 REPORTES", "📈 DASHBOARDS"]:
        st.header("📅 Rango y Periodos")
        
        # VARIABLES SOLICITADAS: Hoy, Ayer, Mes Actual, Mes Anterior
        hoy_dt = date.today()
        opciones_periodo = ["Personalizado", "Hoy", "Ayer", "Mes Actual", "Mes Anterior"]
        periodo_sel = st.selectbox("Accesos Rápidos:", opciones_periodo)
        
        if periodo_sel == "Hoy":
            st.session_state.f_desde, st.session_state.f_hasta = hoy_dt, hoy_dt
        elif periodo_sel == "Ayer":
            ayer = hoy_dt - timedelta(days=1)
            st.session_state.f_desde, st.session_state.f_hasta = ayer, ayer
        elif periodo_sel == "Mes Actual":
            st.session_state.f_desde = hoy_dt.replace(day=1)
            st.session_state.f_hasta = hoy_dt
        elif periodo_sel == "Mes Anterior":
            ultimo_dia_mes_ant = hoy_dt.replace(day=1) - timedelta(days=1)
            st.session_state.f_desde = ultimo_dia_mes_ant.replace(day=1)
            st.session_state.f_hasta = ultimo_dia_mes_ant
        
        if st.button("🔄 Ver Histórico Total"):
            st.session_state.f_desde = date(2020, 1, 1)
            st.session_state.f_hasta = hoy_dt; st.rerun()

        f_desde = st.date_input("Desde:", value=st.session_state.f_desde, format="DD/MM/YYYY")
        f_hasta = st.date_input("Hasta:", value=st.session_state.f_hasta, format="DD/MM/YYYY")
        st.session_state.f_desde, st.session_state.f_hasta = f_desde, f_hasta
    else:
        f_desde, f_hasta = date(2020, 1, 1), date.today()

    st.divider()
    st.header("🎯 Filtros Globales")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()) if "CLIENTES" in df_actual.columns else [])
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()) if "CONSULTOR" in df_actual.columns else [])
    f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()) if "MODULO" in df_actual.columns else [])
    anios_ok = sorted([a for a in df_actual["ANIO"].unique() if a > 2000], reverse=True) if "ANIO" in df_actual.columns else []
    f_ani = st.multiselect("Años:", anios_ok)
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# Filtrado Maestro
df_f = df_actual.copy()
if "FE_DT" in df_f.columns:
    df_f = df_f[(df_f["FE_DT"].dt.date >= f_desde) & (df_f["FE_DT"].dt.date <= f_hasta)]
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# NAVEGACIÓN
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if es_admin: btns.append("⚙️ PERMISOS")
cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b
st.divider()

# ==========================================
# SOLAPAS DINÁMICAS (REPORTES Y DASHBOARD AFECTADOS)
# ==========================================

if st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Reportes Analíticos")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric(f"Horas Totales ({periodo_sel})", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        # Botones de exportación PDF y Excel se mantienen igual...

elif st.session_state.menu_activo == "📈 DASHBOARDS":
    st.header(f"📈 Tableros de Control: {periodo_sel}")
    df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
    t1, t2, t3 = st.tabs(["📋 Operativo", "⚡ Performance", "💰 Financiero"])
    with t1: st.bar_chart(df_dash.groupby("MODULO")["TIEMPO_RES"].sum())
    with t2:
        df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
        st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
    with t3:
        df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * pd.to_numeric(df_dash["VALOR_HORA"])
        st.metric("Inversión en Periodo", f"$ {df_dash['COSTO'].sum():,.2f}")

elif st.session_state.menu_activo == "✏️ MODIFICAR":
    df_mod = df_f[df_f["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
    if not df_mod.empty:
        sel_m = st.selectbox("Ticket:", df_mod.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
        with st.form("f_mod"):
            n_est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]))
            n_tie = st.number_input("Minutos", value=int(dm["TIEMPO_RES"]))
            n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
            if st.form_submit_button("🔥 ACTUALIZAR A FECHA DE HOY"):
                hoy = datetime.now()
                df_actual.at[idx_f, "ESTADO"], df_actual.at[idx_f, "TIEMPO_RES"] = n_est, n_tie
                df_actual.at[idx_f, "RESPUESTAS"], df_actual.at[idx_f, "FE_CONSULT"] = n_rta, hoy.strftime("%d/%m/%Y")
                df_actual.at[idx_f, "ANIO"], df_actual.at[idx_f, "MES"] = hoy.year, hoy.month
                if guardar_seguro(df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore"), f"MODIF {id_m}"):
                    st.success("Actualizado."); st.rerun()

# Resto de solapas (NUEVO, CONSULTAR, PERMISOS) conservan su lógica íntegra...
