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
            df[col] = df[col].astype(str).str.strip().str.upper().str.replace(r"\.0$", "", regex=True)
        return df
    except: return pd.DataFrame()

def obtener_datos_tickets():
    try:
        df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        df.columns = [str(c).strip().upper().replace('AÑO', 'ANIO') for c in df.columns]
        
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        else: df["ID_NUM"] = 0
        
        # Normalización de Fecha para Filtro Maestro
        df["FE_DT"] = pd.to_datetime(df["FE_CONSULT"], format='%d/%m/%Y', errors='coerce')
        
        df["TIEMPO_RES"] = pd.to_numeric(df.get("TIEMPO_RES", 0), errors='coerce').fillna(0)
        df["ANIO"] = pd.to_numeric(df.get("ANIO", 0), errors='coerce').fillna(0).astype(int)
        df["MES"] = pd.to_numeric(df.get("MES", 0), errors='coerce').fillna(0).astype(int)
        return df.fillna("")
    except: return pd.DataFrame()

# 🛡️ FUNCIÓN DE GUARDADO SEGURO (ANTI-BORRADO)
def guardar_seguro(df_nuevo, accion_msg):
    try:
        base_nube = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
        # Bloqueo si el nuevo DF tiene menos registros que la nube (evita sobrescritura vacía)
        if not base_nube.empty and len(df_nuevo) < len(base_nube) and "MODIFICACION" not in accion_msg:
            st.error("🚨 BLOQUEO DE SEGURIDAD: Operación cancelada por riesgo de pérdida de datos.")
            return False
        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_nuevo)
        return True
    except:
        st.error("❌ Error de comunicación con la base de datos.")
        return False

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
    
    # --- FILTRO MAESTRO DE FECHAS ---
    st.header("📅 Rango de Fechas")
    fecha_min = df_actual["FE_DT"].min().date() if not df_actual.empty else date.today()
    f_desde = st.date_input("Desde Fecha:", value=fecha_min)
    f_hasta = st.date_input("Hasta Fecha:", value=date.today())
    
    st.divider()
    st.header("🎯 Filtros por Categoría")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()))
    f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()))
    f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()))
    
    anios_lista = sorted([a for a in df_actual["ANIO"].unique() if a > 2000], reverse=True)
    f_ani = st.multiselect("Años:", anios_lista)
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# APLICACIÓN DEL FILTRO MAESTRO (df_f)
df_f = df_actual.copy()
# Aplicar Rango de Fechas
df_f = df_f[(df_f["FE_DT"].dt.date >= f_desde) & (df_f["FE_DT"].dt.date <= f_hasta)]

if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# NAVEGACIÓN
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
es_admin = str(user_info.get("ROL")).upper() == "ADMIN"
if es_admin: btns.append("⚙️ PERMISOS")

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
            fe_n = st.date_input("Fecha Consulta", datetime.now()); tie_n = st.number_input("Minutos *", min_value=0)
            on_n = st.radio("Online?", ["SI", "NO"], horizontal=True)
        con_txt = st.text_area("Consulta *"); rta_txt = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_txt and rta_txt and tie_n > 0:
                base_completa = obtener_datos_tickets().drop(columns=["ID_NUM", "FE_DT"], errors="ignore")
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "TIPO_CONS": tipo_n, "PRIORIDAD": prio_n, "ESTADO": est_n, "ATENCION": ate_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ONLINE": on_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}])
                df_final = pd.concat([base_completa, nuevo], ignore_index=True)
                if guardar_seguro(df_final, f"ALTA TICKET {proximo_id}"):
                    registrar_auditoria(proximo_id, "ALTA", nombre_consultor); st.balloons(); st.rerun()

# ==========================================
# SECCIÓN 2: MODIFICAR (ACTUALIZACIÓN DE FECHA)
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    # Ahora permite elegir cualquier ticket (Abierto o Cerrado) dentro de los filtros maestros
    if not df_f.empty:
        sel_m = st.selectbox("Seleccione Ticket:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {str(r['CONSULTAS'])[:40]}...", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
        with st.form("f_mod"):
            st.warning(f"Modificando Ticket #{id_m}")
            c1, c2 = st.columns(2)
            n_est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]))
            n_tie = c2.number_input("Tiempo (min)", value=int(dm["TIEMPO_RES"]))
            n_con = st.text_area("Consulta", value=dm["CONSULTAS"]); n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
            if st.form_submit_button("🔥 ACTUALIZAR TICKET"):
                # Actualización de la Fecha de Consulta al día de hoy solicitado
                hoy = datetime.now()
                df_actual.at[idx_f, "ESTADO"] = n_est
                df_actual.at[idx_f, "TIEMPO_RES"] = n_tie
                df_actual.at[idx_f, "CONSULTAS"] = n_con
                df_actual.at[idx_f, "RESPUESTAS"] = n_rta
                df_actual.at[idx_f, "FE_CONSULT"] = hoy.strftime("%d/%m/%Y")
                df_actual.at[idx_f, "ANIO"] = hoy.year
                df_actual.at[idx_f, "MES"] = hoy.month
                df_actual.at[idx_f, "ULTIMA_MODIF"] = hoy.strftime("%d/%m/%Y %H:%M:%S")
                
                if guardar_seguro(df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore"), f"MODIFICACION TICKET {id_m}"):
                    registrar_auditoria(id_m, "MODIFICACION", nombre_consultor); st.success("¡Ticket y Fecha actualizados!"); st.rerun()
    else: st.info("No hay tickets en este rango de fechas o filtros.")

# ==========================================
# SECCIÓN 3: CONSULTAR
# ==========================================
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Ver Ficha:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#","")); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"Ticket #{id_c}")
            v1, v2, v3 = st.columns(3)
            v1.write(f"**Cliente:** {dc['CLIENTES']}\n\n**Usuario:** {dc['USUARIO']}")
            v2.write(f"**Atendido por:** {dc['CONSULTOR']}\n\n**Estado:** {dc['ESTADO']}")
            v3.write(f"**Fecha:** {dc['FE_CONSULT']}\n\n**Tiempo:** {dc['TIEMPO_RES']} min")
            st.divider()
            st.info(f"**Consulta:**\n{dc['CONSULTAS']}")
            st.success(f"**Respuesta:**\n{dc['RESPUESTAS']}")
            # PDF Ficha
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 15, "GR Consulting", ln=True, align='C')
            pdf.set_font("Arial", size=10); pdf.ln(5); pdf.cell(0, 10, f"Ticket #{id_c} - {dc['CLIENTES']}", border=1, ln=True)
            pdf.multi_cell(0, 10, f"CONSULTA: {dc['CONSULTAS']}", border=1)
            pdf.multi_cell(0, 10, f"RESPUESTA: {dc['RESPUESTAS']}", border=1)
            st.download_button("📥 PDF Ficha", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# ==========================================
# SECCIÓN 4: REPORTES (INCLUYE FILTRO FECHA EN PDF)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Centro de Reportes Analíticos")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60; st.metric("Horas Totales en el Periodo", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📥 Excel")
            tipo_xls = st.radio("Formato:", ["Resumido", "Detallado"], horizontal=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                if "Resumido" in tipo_xls: res.to_excel(w, index=False)
                else:
                    df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "MODULO", "CONSULTOR", "TIEMPO_RES"]].copy()
                    df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2); df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                    df_det.to_excel(w, index=False)
            st.download_button("📥 Descargar Excel", buf.getvalue(), f"GR_Reporte_{tipo_xls}.xlsx")
        
        with c2:
            st.subheader("📥 PDF Analítico")
            pdf_a = FPDF(); pdf_a.add_page(); pdf_a.set_font("Arial", 'B', 11); pdf_a.cell(0, 8, "FILTROS UTILIZADOS:", ln=True)
            pdf_a.set_font("Arial", size=10); pdf_a.cell(0, 6, f"Clientes: {', '.join(f_cli) if f_cli else 'TODOS'}", ln=True)
            pdf_a.cell(0, 6, f"Periodo: {f_desde.strftime('%d/%m/%Y')} al {f_hasta.strftime('%d/%m/%Y')}", ln=True); pdf_a.ln(10)
            # Tabla del PDF Analítico igual al archivo cargado
            pdf_a.set_font("Arial", 'B', 9); pdf_a.cell(45, 8, "Cliente", 1); pdf_a.cell(40, 8, "Modulo", 1); pdf_a.cell(45, 8, "Consultor", 1); pdf_a.cell(30, 8, "Horas", 1, ln=True); pdf_a.set_font("Arial", size=9)
            for _, r in res.iterrows(): pdf_a.cell(45, 7, str(r['CLIENTES']), 1); pdf_a.cell(40, 7, str(r['MODULO']), 1); pdf_a.cell(45, 7, str(r['CONSULTOR']), 1); pdf_a.cell(30, 7, str(r['HORAS']), 1, ln=True)
            pdf_a.ln(5); pdf_a.set_font("Arial", 'B', 12); pdf_a.cell(0, 10, f"TOTAL: {t_hs:,.2f} hs", align='R')
            st.download_button("📥 PDF Analítico", pdf_a.output(dest='S').encode('latin-1'), "Reporte_GR.pdf")

# ==========================================
# SECCIÓN 5: DASHBOARDS
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    st.header("📈 Centro Operativo")
    df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
    tab1, tab2 = st.tabs(["📋 Operativo", "💰 Financiero"])
    with tab1: st.bar_chart(df_dash.groupby("MODULO")["TIEMPO_RES"].sum())
    with tab2:
        df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * pd.to_numeric(df_dash["VALOR_HORA"])
        st.metric("Inversión en el Periodo", f"$ {df_dash['COSTO'].sum():,.2f}")

# ==========================================
# SECCIÓN 6: PERMISOS (SOLO ADMIN)
# ==========================================
elif st.session_state.menu_activo == "⚙️ PERMISOS" and es_admin:
    st.header("⚙️ Gestión de Usuarios")
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar"): conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed); st.rerun()
