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

# Inicialización de fechas
if "f_desde" not in st.session_state:
    st.session_state.f_desde = date(2020, 1, 1)
if "f_hasta" not in st.session_state:
    st.session_state.f_hasta = date.today()

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

# --- FUNCIONES DE CARGA CON PROTECCIÓN (EVITA KEYERROR) ---
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
        
        # Normalización de Fecha D/M/A
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
            st.error("🚨 BLOQUEO DE SEGURIDAD: Operación cancelada para evitar pérdida de registros.")
            return False
        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_nuevo)
        return True
    except:
        st.error("❌ Error al conectar con Google Sheets.")
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
                    st.session_state.autenticado = True
                    st.session_state.usuario_logueado = c_in
                    st.rerun()
                else: st.error("⚠️ Credenciales incorrectas.")
    st.stop()

# --- CARGA POST-LOGIN ---
nombre_consultor = st.session_state.usuario_logueado
df_config = obtener_config()
df_actual = obtener_datos_tickets()

# Protección contra KeyError de identidad
if df_config.empty or "CONSULTOR" not in df_config.columns:
    st.error("Error en hoja 'Config_Consultores'. Falta columna 'CONSULTOR'.")
    st.stop()

user_match = df_config[df_config["CONSULTOR"] == nombre_consultor]
user_info = user_match.iloc[0] if not user_match.empty else {"ROL": "USER"}
es_admin = str(user_info.get("ROL")).upper() == "ADMIN"

# ==========================================
# 🎯 SIDEBAR (FILTROS MAESTROS CONDICIONALES)
# ==========================================
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False; st.rerun()
    st.divider()
    
    # RESTRICCIÓN SOLICITADA: Fecha solo en Reportes o Dashboards
    if st.session_state.menu_activo in ["📊 REPORTES", "📈 DASHBOARDS"]:
        st.header("📅 Rango de Fechas")
        if st.button("🔄 Limpiar Rango"):
            st.session_state.f_desde = date(2020, 1, 1)
            st.session_state.f_hasta = date.today()
            st.rerun()
        
        f_desde = st.date_input("Desde:", value=st.session_state.f_desde, format="DD/MM/YYYY")
        f_hasta = st.date_input("Hasta:", value=st.session_state.f_hasta, format="DD/MM/YYYY")
        st.session_state.f_desde, st.session_state.f_hasta = f_desde, f_hasta
    else:
        # En otras solapas el rango es total por defecto para no ocultar nada
        f_desde = date(2020, 1, 1)
        f_hasta = date.today()

    st.divider()
    st.header("🎯 Otros Filtros")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()) if "CLIENTES" in df_actual.columns else [])
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()) if "CONSULTOR" in df_actual.columns else [])
    f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()) if "MODULO" in df_actual.columns else [])

# Aplicación del Filtro Maestro (df_f)
df_f = df_actual.copy()
if "FE_DT" in df_f.columns:
    df_f = df_f[(df_f["FE_DT"].dt.date >= f_desde) & (df_f["FE_DT"].dt.date <= f_hasta)]

if f_cli and "CLIENTES" in df_f.columns: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con and "CONSULTOR" in df_f.columns: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod and "MODULO" in df_f.columns: df_f = df_f[df_f["MODULO"].isin(f_mod)]

# NAVEGACIÓN
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if es_admin: btns.append("⚙️ PERMISOS")
cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b
st.divider()

# ==========================================
# SOLAPAS (NUEVO / MODIFICAR / REPORTES)
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty and "ID_NUM" in df_actual.columns else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Consultor", value=nombre_consultor, disabled=True)
            tipo_n = st.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
            prio_n = st.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
            est_n = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            cli_n = st.selectbox("Cliente", sorted(["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]))
            usu_n = st.text_input("Usuario Cliente *").upper()
            ate_n = st.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
        with c3:
            mod_n = st.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"])
            fe_n = st.date_input("Fecha", datetime.now(), format="DD/MM/YYYY")
            tie_n = st.number_input("Minutos *", min_value=0)
            on_n = st.radio("Online?", ["SI", "NO"], horizontal=True)
        con_txt = st.text_area("Consulta *"); rta_txt = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_txt and rta_txt and tie_n > 0:
                base_clean = df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore")
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "TIPO_CONS": tipo_n, "PRIORIDAD": prio_n, "ESTADO": est_n, "ATENCION": ate_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ONLINE": on_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}])
                if guardar_seguro(pd.concat([base_clean, nuevo], ignore_index=True), f"ALTA {proximo_id}"):
                    st.balloons(); st.rerun()

elif st.session_state.menu_activo == "✏️ MODIFICAR":
    if not df_f.empty and "ESTADO" in df_f.columns:
        df_mod = df_f[df_f["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not df_mod.empty:
            sel_m = st.selectbox("Ticket:", df_mod.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
            id_m = int(sel_m.split(" |")[0].replace("#",""))
            idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
            with st.form("f_mod"):
                c1, c2 = st.columns(2)
                n_est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]))
                n_tie = c2.number_input("Tiempo (min)", value=int(dm["TIEMPO_RES"]))
                n_con = st.text_area("Consulta", value=dm["CONSULTAS"]); n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
                if st.form_submit_button("🔥 ACTUALIZAR A FECHA DE HOY"):
                    hoy = datetime.now()
                    df_actual.at[idx_f, "ESTADO"] = n_est; df_actual.at[idx_f, "TIEMPO_RES"] = n_tie
                    df_actual.at[idx_f, "CONSULTAS"] = n_con; df_actual.at[idx_f, "RESPUESTAS"] = n_rta
                    df_actual.at[idx_f, "FE_CONSULT"] = hoy.strftime("%d/%m/%Y")
                    df_actual.at[idx_f, "ANIO"] = hoy.year; df_actual.at[idx_f, "MES"] = hoy.month
                    if guardar_seguro(df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore"), f"MODIF {id_m}"):
                        st.success("¡Listo!"); st.rerun()
        else: st.info("No hay tickets pendientes.")

elif st.session_state.menu_activo == "📊 REPORTES":
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60; st.metric("Horas en Periodo Seleccionado", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            tipo_xls = st.radio("Excel:", ["Resumido", "Detallado"], horizontal=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                if "Resumido" in tipo_xls: res.to_excel(w, index=False)
                else:
                    df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "MODULO", "CONSULTOR", "TIEMPO_RES"]].copy()
                    df_det.to_excel(w, index=False)
            st.download_button("📥 Excel", buf.getvalue(), f"GR_Reporte_{tipo_xls}.xlsx")
        with c2:
            pdf_a = FPDF(); pdf_a.add_page(); pdf_a.set_font("Arial", 'B', 11)
            pdf_a.cell(0, 10, f"Periodo: {f_desde.strftime('%d/%m/%Y')} al {f_hasta.strftime('%d/%m/%Y')}", ln=True, align='C')
            pdf_a.set_font("Arial", 'B', 14); pdf_a.cell(0, 10, "GR Consulting - Analítico", ln=True, align='C')
            for _, r in res.iterrows(): pdf_a.cell(0, 8, f"{r['CLIENTES']} | {r['MODULO']}: {r['HORAS']} hs", ln=True, border=1)
            pdf_a.cell(0, 10, f"TOTAL: {t_hs:,.2f} hs", align='R')
            st.download_button("📥 PDF Analítico", pdf_a.output(dest='S').encode('latin-1'), "Analitico.pdf")

elif st.session_state.menu_activo == "📈 DASHBOARDS":
    df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA"]], on="CONSULTOR", how="left").fillna(0)
    st.header("📈 Análisis Visual del Periodo")
    tab1, tab2 = st.tabs(["📋 Operativo", "💰 Financiero"])
    with tab1: st.bar_chart(df_dash.groupby("MODULO")["TIEMPO_RES"].sum())
    with tab2: st.metric("Inversión en Rango", f"$ {((df_dash['TIEMPO_RES']/60)*pd.to_numeric(df_dash['VALOR_HORA'])).sum():,.2f}")

elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Ver Ficha:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#","")); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"Ticket #{id_c}"); st.info(f"**Fecha:** {dc['FE_CONSULT']}"); st.success(f"**Respuesta:** {dc['RESPUESTAS']}")

elif st.session_state.menu_activo == "⚙️ PERMISOS" and es_admin:
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar"): conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed); st.rerun()
