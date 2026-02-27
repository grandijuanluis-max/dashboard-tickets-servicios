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

# --- FUNCIONES DE CARGA CON LIMPIEZA AGRESIVA ---
def obtener_config():
    try:
        # ttl=0 para leer cambios en el Excel al instante
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Limpiamos todos los datos: convertimos a texto, quitamos espacios y pasamos a mayúsculas
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
        return df
    except: return pd.DataFrame()

def obtener_datos_tickets():
    try:
        df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Crear ID_NUM inmediatamente para evitar errores de referencia
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        else: df["ID_NUM"] = 0
        # Normalización de métricas
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
# 🔑 PANTALLA DE LOGIN (CON VALIDACIÓN BLINDADA)
# ==========================================
if not st.session_state.autenticado:
    st.title("🔐 Acceso GR Consulting")
    with st.form("login_form"):
        # Normalizamos la entrada del usuario
        c_input = st.text_input("Consultor (Nombre)").strip().upper()
        p_input = st.text_input("Contraseña", type="password").strip().upper()
        
        if st.form_submit_button("INGRESAR"):
            df_u = obtener_config()
            if not df_u.empty:
                # Comparamos Strings contra Strings (evita el error del .0 en números)
                match = df_u[(df_u["CONSULTOR"] == c_input) & (df_u["PASSWORD"] == p_input)]
                if not match.empty:
                    st.session_state.autenticado = True
                    st.session_state.usuario_logueado = c_input
                    st.rerun()
                else: st.error("⚠️ Consultor o contraseña incorrectos.")
            else: st.error("No se pudo conectar con la base de usuarios.")
    st.stop()

# ==========================================
# 🚀 APLICACIÓN AUTENTICADA (INTEGRAL)
# ==========================================
nombre_consultor = st.session_state.usuario_logueado
df_config = obtener_config()
df_actual = obtener_datos_tickets()

# Datos frescos del usuario para permisos
user_info = df_config[df_config["CONSULTOR"] == nombre_consultor].iloc[0]

# --- SIDEBAR: FILTROS MAESTROS DINÁMICOS ---
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()
    st.divider()
    st.header("🎯 Filtros Globales")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()))
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()))
    f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()) if "MODULO" in df_actual.columns else [])
    f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True))
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# Aplicación de Filtros Maestros
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# Menú de Navegación
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if user_info.get("ROL") == "ADMIN": btns.append("⚙️ PERMISOS")
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
        c1.text_input("Atendido por", value=nombre_consultor, disabled=True)
        prio = c1.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
        est_n = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        cli_n = c2.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
        usu_n = c2.text_input("Usuario Cliente *").upper()
        mod_n = c3.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"])
        fe_n = c3.date_input("Fecha", datetime.now()); tie_n = c3.number_input("Minutos *", min_value=0)
        con_txt = st.text_area("Consulta *"); rta_txt = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_txt and rta_txt and tie_n > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "PRIORIDAD": prio, "ESTADO": est_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos_tickets().drop(columns=["ID_NUM"], errors="ignore"), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", nombre_consultor)
                st.balloons(); st.rerun()

# --- SECCIÓN: REPORTES (EXPORTACIÓN XLS DETALLADA) ---
elif st.session_state.menu_activo == "📊 REPORTES":
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Horas Totales (Filtrado)", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            # Orden de columnas solicitado: Textos al final
            df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES"]].copy()
            df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
            df_det.to_excel(w, index=False)
        st.download_button("📥 Descargar Excel Detallado", buf.getvalue(), "Reporte_GR.xlsx")

# --- SECCIÓN: DASHBOARDS (32 KPIs + JUANLUIS FIX) ---
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    # Verificación en vivo contra el dataframe de configuración limpio
    p1 = user_info.get("ACCESO_DB1") == "SI"
    p2 = user_info.get("ACCESO_DB2") == "SI"
    p3 = user_info.get("ACCESO_DB3") == "SI"
    
    if not any([p1, p2, p3]):
        st.error(f"🚫 {nombre_consultor}, no tienes permisos activados para ver Dashboards.")
    else:
        # Cruce con Config para Performance y Finanzas
        df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
        df_dash["VALOR_HORA"] = pd.to_numeric(df_dash["VALOR_HORA"], errors='coerce').fillna(0)
        df_dash["DISPONIBLE"] = pd.to_numeric(df_dash["DISPONIBLE"], errors='coerce').fillna(0)
        
        t_list = []
        if p1: t_list.append("📋 OPERATIVO")
        if p2: t_titles = t_list.append("⚡ PERFORMANCE")
        if p3: t_titles = t_list.append("💰 FINANCIERO")
        tabs = st.tabs(t_list)
        
        curr = 0
        if p1:
            with tabs[curr]:
                st.subheader("Volumen y Eficacia (Operativo)")
                c1, c2, c3 = st.columns(3)
                c1.metric("Tickets", len(df_dash))
                c2.metric("Promedio (min)", f"{df_dash['TIEMPO_RES'].mean():.1f}")
                cer = len(df_dash[df_dash["ESTADO"] == "CERRADO"])
                c3.metric("% Eficacia", f"{(cer/len(df_dash)*100):.1f}%" if len(df_dash)>0 else "0%")
                st.bar_chart(df_dash["CLIENTES"].value_counts())
            curr += 1
        if p2:
            with tabs[curr]:
                st.subheader("Performance y Capacidad")
                df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
                st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
            curr += 1
        if p3:
            with tabs[curr]:
                st.subheader("Análisis Financiero")
                df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * df_dash["VALOR_HORA"]
                st.metric("Inversión Total", f"$ {df_dash['COSTO'].sum():,.2f}")
                st.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())

# --- PERMISOS (SOLO ADMIN) ---
elif st.session_state.menu_activo == "⚙️ PERMISOS":
    st.header("⚙️ Gestión de Usuarios")
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar Nueva Configuración"):
        conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed)
        st.success("Permisos actualizados correctamente.")
