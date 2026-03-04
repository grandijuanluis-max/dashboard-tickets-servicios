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
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_logueado" not in st.session_state: st.session_state.usuario_logueado = None
if "menu_activo" not in st.session_state: st.session_state.menu_activo = "➕ NUEVO"

# Persistencia de fechas (Se mantiene igual)
if "f_desde" not in st.session_state: st.session_state.f_desde = date(2020, 1, 1)
if "f_hasta" not in st.session_state: st.session_state.f_hasta = date.today()

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

def guardar_seguro(df_nuevo, accion_msg):
    try:
        base_nube = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        if not base_nube.empty and len(df_nuevo) < len(base_nube) and "MODIFICACION" not in accion_msg:
            st.error("🚨 BLOQUEO DE SEGURIDAD: Operación cancelada por riesgo de pérdida de datos.")
            return False
        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_nuevo)
        return True
    except: return False

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
user_match = df_config[df_config["CONSULTOR"] == nombre_consultor] if not df_config.empty else pd.DataFrame()
user_info = user_match.iloc[0] if not user_match.empty else {"ROL": "USER"}
es_admin = str(user_info.get("ROL")).upper() == "ADMIN"

# ==========================================
# 🎯 SIDEBAR (FILTROS Y PERIODOS)
# ==========================================
periodo_sel = "Personalizado"

with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"): st.session_state.autenticado = False; st.rerun()
    st.divider()
    
    if st.session_state.menu_activo in ["📊 REPORTES", "📈 DASHBOARDS"]:
        st.header("📅 Rango y Periodos")
        hoy_dt = date.today()
        periodo_sel = st.selectbox("Accesos Rápidos:", ["Personalizado", "Hoy", "Ayer", "Mes Actual", "Mes Anterior"])
        if periodo_sel == "Hoy": st.session_state.f_desde = st.session_state.f_hasta = hoy_dt
        elif periodo_sel == "Ayer": st.session_state.f_desde = st.session_state.f_hasta = hoy_dt - timedelta(days=1)
        elif periodo_sel == "Mes Actual": st.session_state.f_desde, st.session_state.f_hasta = hoy_dt.replace(day=1), hoy_dt
        elif periodo_sel == "Mes Anterior":
            ult = hoy_dt.replace(day=1) - timedelta(days=1)
            st.session_state.f_desde, st.session_state.f_hasta = ult.replace(day=1), ult
        f_desde = st.date_input("Desde:", value=st.session_state.f_desde, format="DD/MM/YYYY")
        f_hasta = st.date_input("Hasta:", value=st.session_state.f_hasta, format="DD/MM/YYYY")
        st.session_state.f_desde, st.session_state.f_hasta = f_desde, f_hasta
    else:
        f_desde, f_hasta = date(2020, 1, 1), date.today()

    st.divider()
    st.header("🎯 Filtros Globales")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()) if not df_actual.empty else [])
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()) if not df_actual.empty else [])
    f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()) if not df_actual.empty else [])
    anios_ok = sorted([a for a in df_actual["ANIO"].unique() if a > 2000], reverse=True) if not df_actual.empty else []
    f_ani = st.multiselect("Años:", anios_ok)
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# Filtrado Maestro
df_f = df_actual.copy()
if not df_f.empty and "FE_DT" in df_f.columns:
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
# ➕ SOLAPA 1: NUEVO (Campos Consultor y Estado Agregados)
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Consultor Atendiendo", value=nombre_consultor, disabled=True)
            est_n = st.selectbox("Estado Inicial", ["ABIERTO", "EN PROCESO"])
        with c2:
            cli_n = st.selectbox("Cliente", sorted(["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]))
            usu_n = st.text_input("Usuario Cliente *").upper()
        with c3:
            mod_n = st.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"])
            fe_n = st.date_input("Fecha", datetime.now(), format="DD/MM/YYYY")
            tie_n = st.number_input("Minutos *", min_value=0)
        
        con_txt = st.text_area("Consulta *")
        rta_txt = st.text_area("Respuesta *")
        
        if st.form_submit_button("💾 GUARDAR TICKET"):
            if usu_n and con_txt and rta_txt and tie_n > 0:
                base_clean = df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore")
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "ESTADO": est_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ANIO": fe_n.year, "MES": fe_n.month}])
                if guardar_seguro(pd.concat([base_clean, nuevo], ignore_index=True), "ALTA"): st.balloons(); st.rerun()

# ==========================================
# ✏️ SOLAPA 2: MODIFICAR (Todos los campos visibles)
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    df_mod = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
    if not df_mod.empty:
        sel_m = st.selectbox("Seleccione Ticket Pendiente:", df_mod.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
        
        with st.form("f_mod"):
            st.warning(f"Modificando Ticket #{id_m} - Registrado originalmente por: {dm['CONSULTOR']}")
            c1, c2, c3 = st.columns(3)
            # Permite modificar campos clave
            n_cli = c1.selectbox("Cliente", sorted(df_actual["CLIENTES"].unique().tolist()), index=sorted(df_actual["CLIENTES"].unique().tolist()).index(dm["CLIENTES"]) if dm["CLIENTES"] in df_actual["CLIENTES"].unique() else 0)
            n_usu = c1.text_input("Usuario Cliente", value=dm["USUARIO"])
            n_mod = c2.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"], index=["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"].index(dm["MODULO"]) if dm["MODULO"] in ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "WEB", "OTROS"] else 0)
            n_est = c2.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]))
            n_tie = c3.number_input("Minutos", value=int(dm["TIEMPO_RES"]))
            
            n_con = st.text_area("Consulta", value=dm["CONSULTAS"])
            n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
            
            if st.form_submit_button("🔥 ACTUALIZAR TICKET (FECHA DE HOY)"):
                hoy = datetime.now()
                df_actual.at[idx_f, "CLIENTES"], df_actual.at[idx_f, "USUARIO"] = n_cli, n_usu
                df_actual.at[idx_f, "MODULO"], df_actual.at[idx_f, "ESTADO"] = n_mod, n_est
                df_actual.at[idx_f, "TIEMPO_RES"], df_actual.at[idx_f, "CONSULTAS"] = n_tie, n_con
                df_actual.at[idx_f, "RESPUESTAS"], df_actual.at[idx_f, "FE_CONSULT"] = n_rta, hoy.strftime("%d/%m/%Y")
                df_actual.at[idx_f, "ANIO"], df_actual.at[idx_f, "MES"] = hoy.year, hoy.month
                if guardar_seguro(df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore"), "MODIFICACION"): st.success("¡Listo!"); st.rerun()
    else: st.info("No hay tickets pendientes bajo estos filtros.")

# ==========================================
# 🔍 SOLAPA 3: CONSULTAR (Visualización de Todos los Campos)
# ==========================================
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Ver Ficha Completa:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#","")); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        
        with st.container(border=True):
            st.subheader(f"Ficha Integral Ticket #{id_c}")
            v1, v2, v3 = st.columns(3)
            with v1:
                st.markdown(f"**Consultor:** {dc['CONSULTOR']}")
                st.markdown(f"**Cliente:** {dc['CLIENTES']}")
                st.markdown(f"**Usuario:** {dc['USUARIO']}")
            with v2:
                st.markdown(f"**Módulo:** {dc['MODULO']}")
                st.markdown(f"**Estado:** {dc['ESTADO']}")
                st.markdown(f"**Tiempo:** {dc['TIEMPO_RES']} minutos")
            with v3:
                st.markdown(f"**Fecha Consulta:** {dc['FE_CONSULT']}")
                st.markdown(f"**Año:** {dc['ANIO']} | **Mes:** {dc['MES']}")
            
            st.divider()
            st.info(f"**DETALLE DE LA CONSULTA:**\n\n{dc['CONSULTAS']}")
            st.success(f"**SOLUCIÓN / RESPUESTA:**\n\n{dc['RESPUESTAS']}")

# ==========================================
# 📊 SOLAPA 4: REPORTES (Mantiene Lógica Anterior)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header(f"📊 Reportes Analíticos: {periodo_sel}")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric(f"Horas Totales del Periodo", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        # Excel y PDF permanecen igual...

# ==========================================
# 📈 SOLAPA 5: DASHBOARDS (3 TABLEROS)
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA"]], on="CONSULTOR", how="left").fillna(0)
    tab1, tab2, tab3 = st.tabs(["📋 Operativo", "⚡ Performance", "💰 Financiero"])
    with tab1: st.bar_chart(df_dash.groupby("MODULO")["TIEMPO_RES"].sum())
    with tab2:
        if not df_dash.empty and "FE_CONSULT" in df_dash.columns:
            st.line_chart(df_dash.groupby("FE_CONSULT")["TIEMPO_RES"].sum())
    with tab3:
        df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * pd.to_numeric(df_dash["VALOR_HORA"])
        st.metric("Inversión en Periodo", f"$ {df_dash['COSTO'].sum():,.2f}")

# ⚙️ SOLAPA 6: PERMISOS (SOLO ADMIN)
elif st.session_state.menu_activo == "⚙️ PERMISOS" and es_admin:
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar Cambios"): conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed); st.rerun()
