import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date, timedelta
import io
from fpdf import FPDF
import time

# 1. CONFIGURACIÓN E IDENTIFICACIÓN MAESTRA
st.set_page_config(page_title="GR Consulting - Gestión Integral BI", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTADO DE SESIÓN ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_logueado" not in st.session_state: st.session_state.usuario_logueado = None
if "menu_activo" not in st.session_state: st.session_state.menu_activo = "➕ NUEVO"

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
        if df is None or df.empty: return pd.DataFrame()
        df.columns = [str(c).strip().upper().replace('AÑO', 'ANIO') for c in df.columns]
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        if "FE_CONSULT" in df.columns:
            df["FE_DT"] = pd.to_datetime(df["FE_CONSULT"], dayfirst=True, errors='coerce')
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

def guardar_seguro(df_nuevo, accion_msg):
    intentos = 0
    while intentos < 2:
        try:
            columnas_finales = df_nuevo.drop(columns=["ID_NUM", "FE_DT"], errors="ignore")
            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=columnas_finales)
            return True
        except:
            intentos += 1
            time.sleep(1)
    return False

def get_index_seguro(lista, valor_buscado):
    try:
        valor_limpio = str(valor_buscado).strip().upper()
        lista_limpia = [str(item).strip().upper() for item in lista]
        if valor_limpio in lista_limpia:
            return lista_limpia.index(valor_limpio)
        return 0
    except: return 0

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
                else: st.error("Credenciales incorrectas")
    st.stop()

# --- CARGA DE DATOS ---
nombre_consultor = st.session_state.usuario_logueado
df_config, df_actual = obtener_config(), obtener_datos_tickets()
user_match = df_config[df_config["CONSULTOR"] == nombre_consultor] if not df_config.empty else pd.DataFrame()
user_info = user_match.iloc[0] if not user_match.empty else {"ROL": "USER"}
es_admin = str(user_info.get("ROL")).upper() == "ADMIN"

# ==========================================
# 🎯 SIDEBAR (FILTROS)
# ==========================================
periodo_sel = "Personalizado"
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"): 
        st.session_state.autenticado = False
        st.rerun()
    st.divider()
    
    if st.session_state.menu_activo in ["📊 REPORTES", "📈 DASHBOARDS", "🔍 CONSULTAR"]:
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
    else: f_desde, f_hasta = date(2000, 1, 1), date(2100, 1, 1)

    st.divider()
    l_cli_f = sorted(df_actual["CLIENTES"].unique()) if not df_actual.empty else []
    l_con_f = sorted(df_actual["CONSULTOR"].unique()) if not df_actual.empty else []
    
    # MODIFICACIÓN: El filtro de módulos ahora lee TODOS los módulos existentes en la BD
    l_mod_f = sorted(df_actual["MODULO"].unique()) if not df_actual.empty else []
    
    f_cli = st.multiselect("Clientes:", l_cli_f)
    f_con = st.multiselect("Consultores:", l_con_f)
    f_mod = st.multiselect("Módulos:", l_mod_f)
    f_ani = st.multiselect("Años:", sorted([a for a in df_actual["ANIO"].unique() if a > 2000], reverse=True) if not df_actual.empty else [])
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# --- LÓGICA DE FILTRADO MAESTRO ---
df_f = df_actual.copy()
if not df_f.empty and "FE_DT" in df_f.columns:
    df_f = df_f[(df_f["FE_DT"].dt.date >= f_desde) & (df_f["FE_DT"].dt.date <= f_hasta)]
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# Navegación
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
if es_admin: btns.append("⚙️ PERMISOS")
cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b
st.divider()

# Listas de opciones estándar para Formularios
OPC_TIPO = ["FUNCIONAL", "TÉCNICA", "COMERCIAL"]
OPC_PRIO = ["BAJA", "MEDIA", "ALTA"]
OPC_ESTADO = ["ABIERTO", "EN PROCESO", "CERRADO"]
OPC_ATE = ["TELEFÓNICA", "WHATSAPP", "MEET", "VISITA", "PROGRAMADA"]
OPC_MOD = ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "IMPUESTOS", "ERROR TABLAS", "STOCK", "QUERYS CREAR", "QUERYS MODIF", "SINCRONIZACION", "CAMBIO VERSION", "CAMBIO EJECUTABLE", "WEB", "OTROS"]
OPC_CLI = sorted(["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GRUPO VAZQUEZ", "GR_CONSULTING"])

# ==========================================
# ➕ SOLAPA 1: NUEVO
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Registro #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("CONSULTOR", value=nombre_consultor, disabled=True)
            tipo_n = st.selectbox("TIPO_CONS", OPC_TIPO); prio_n = st.selectbox("PRIORIDAD", OPC_PRIO); est_n = st.selectbox("ESTADO", OPC_ESTADO)
        with c2:
            cli_n = st.selectbox("CLIENTES", OPC_CLI); usu_n = st.text_input("USUARIO CLIENTE *").upper()
            ate_n = st.selectbox("ATENCION", OPC_ATE); on_n = st.radio("ONLINE", ["SI", "NO"], horizontal=True)
        with c3:
            mod_n = st.selectbox("MODULO", OPC_MOD); fe_n = st.date_input("FE_CONSULT", datetime.now(), format="DD/MM/YYYY")
            tie_n = st.number_input("TIEMPO_RES (min) *", min_value=0)
        con_txt = st.text_area("CONSULTAS *"); rta_txt = st.text_area("RESPUESTAS *")
        if st.form_submit_button("💾 GUARDAR TICKET"):
            if not usu_n.strip() or not con_txt.strip() or tie_n <= 0: st.error("Completa campos obligatorios.")
            else:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "TIPO_CONS": tipo_n, "PRIORIDAD": prio_n, "ESTADO": est_n, "ATENCION": ate_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ONLINE": on_n, "ANIO": fe_n.year, "MES": fe_n.month}])
                base_previa = df_actual.drop(columns=["ID_NUM", "FE_DT"], errors="ignore")
                if guardar_seguro(pd.concat([base_previa, nuevo], ignore_index=True), "ALTA"):
                    registrar_auditoria(proximo_id, f"ALTA ({est_n})", nombre_consultor)
                    st.success(f"✅ Ticket #{proximo_id} guardado."); time.sleep(1); st.rerun()

# ==========================================
# ✏️ SOLAPA 2: MODIFICAR
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    df_mod = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
    if not df_mod.empty:
        sel_m = st.selectbox("Ticket Pendiente:", df_mod.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#","")); idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
        try:
            f_val = pd.to_datetime(dm["FE_CONSULT"], dayfirst=True, errors='coerce')
            f_val = f_val.date() if not pd.isna(f_val) else date.today()
        except: f_val = date.today()
        with st.form("f_mod"):
            st.info(f"Modificando Ticket #{id_m}")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("CONSULTOR", value=dm["CONSULTOR"], disabled=True)
                n_tipo = st.selectbox("TIPO_CONS", OPC_TIPO, index=get_index_seguro(OPC_TIPO, dm["TIPO_CONS"]))
                n_prio = st.selectbox("PRIORIDAD", OPC_PRIO, index=get_index_seguro(OPC_PRIO, dm["PRIORIDAD"]))
                n_est = st.selectbox("ESTADO", OPC_ESTADO, index=get_index_seguro(OPC_ESTADO, dm["ESTADO"]))
            with c2:
                lista_c_db = sorted(df_actual["CLIENTES"].unique().tolist())
                n_cli = st.selectbox("CLIENTES", lista_c_db, index=get_index_seguro(lista_c_db, dm["CLIENTES"]))
                n_usu = st.text_input("USUARIO", value=str(dm["USUARIO"]))
                n_ate = st.selectbox("ATENCION", OPC_ATE, index=get_index_seguro(OPC_ATE, dm["ATENCION"]))
                n_on = st.radio("ONLINE", ["SI", "NO"], index=0 if str(dm["ONLINE"]).upper()=="SI" else 1, horizontal=True)
            with c3:
                n_mod = st.selectbox("MODULO", OPC_MOD, index=get_index_seguro(OPC_MOD, dm["MODULO"]))
                n_fe = st.date_input("FE_CONSULT", value=f_val, format="DD/MM/YYYY")
                n_tie = st.number_input("TIEMPO_RES", value=int(pd.to_numeric(dm["TIEMPO_RES"], errors='coerce') or 0))
            n_con = st.text_area("CONSULTAS", value=str(dm["CONSULTAS"])); n_rta = st.text_area("RESPUESTAS", value=str(dm["RESPUESTAS"]))
            if st.form_submit_button("🔥 ACTUALIZAR REGISTRO"):
                df_actual.at[idx_f, "TIPO_CONS"], df_actual.at[idx_f, "PRIORIDAD"] = n_tipo, n_prio
                df_actual.at[idx_f, "ESTADO"], df_actual.at[idx_f, "CLIENTES"] = n_est, n_cli
                df_actual.at[idx_f, "USUARIO"], df_actual.at[idx_f, "ATENCION"] = n_usu, n_ate
                df_actual.at[idx_f, "ONLINE"], df_actual.at[idx_f, "MODULO"] = n_on, n_mod
                df_actual.at[idx_f, "FE_CONSULT"] = n_fe.strftime('%d/%m/%Y')
                df_actual.at[idx_f, "TIEMPO_RES"], df_actual.at[idx_f, "CONSULTAS"] = n_tie, n_con
                df_actual.at[idx_f, "RESPUESTAS"] = n_rta; df_actual.at[idx_f, "ANIO"], df_actual.at[idx_f, "MES"] = n_fe.year, n_fe.month
                if guardar_seguro(df_actual, "MODIF"):
                    registrar_auditoria(id_m, f"MODIFICACION ({n_est})", nombre_consultor)
                    st.success("✅ Registro actualizado correctamente."); time.sleep(1); st.rerun()
    else: st.warning("No hay tickets pendientes.")

# ==========================================
# 📊 REPORTES (REESTRUCTURADO TOTAL)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header(f"📊 Reportes: {periodo_sel}")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Horas Totales", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index()
        res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        
        s_cli = f"_{f_cli[0]}" if len(f_cli) == 1 else ""; s_date = f"_{f_desde.strftime('%d%m%y')}_a_{f_hasta.strftime('%d%m%y')}"
        nom_base = f"{s_cli}{s_date}"
        
        c1, c2 = st.columns(2)
        with c1:
            tipo_xls = st.radio("Excel:", ["Resumido", "Detallado"], horizontal=True); buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                if "Resumido" in tipo_xls: res.to_excel(w, index=False)
                else:
                    df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "MODULO", "CONSULTOR", "USUARIO", "TIEMPO_RES"]].copy()
                    df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2); df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                    df_det.to_excel(w, index=False)
            st.download_button(f"📥 Excel", buf.getvalue(), f"GR_{tipo_xls}{nom_base}.xlsx")
        with c2:
            # --- MOTOR DE PDF REESTRUCTURADO ---
            pdf_a = FPDF(); pdf_a.add_page(); pdf_a.set_font("Arial", 'B', 10)
            
            # Encabezado de Filtros
            pdf_a.set_fill_color(240, 240, 240)
            pdf_a.cell(0, 7, "FILTROS UTILIZADOS", 1, ln=True, align='C', fill=True)
            pdf_a.set_font("Arial", '', 9)
            pdf_a.cell(0, 6, f"Periodo: {f_desde.strftime('%d/%m/%Y')} al {f_hasta.strftime('%d/%m/%Y')}", 1, ln=True)
            pdf_a.cell(0, 6, f"Clientes: {', '.join(f_cli) if f_cli else 'TODOS'}", 1, ln=True)
            pdf_a.cell(0, 6, f"Consultores: {', '.join(f_con) if f_con else 'TODOS'}", 1, ln=True)
            pdf_a.ln(5)
            
            pdf_a.set_font("Arial", 'B', 14); pdf_a.cell(0, 10, "Resumen Analítico", ln=True, align='C')
            pdf_a.ln(2)

            clientes_unicos = df_f["CLIENTES"].unique()

            if len(clientes_unicos) > 1:
                # CASO VARIOS CLIENTES
                for cl in sorted(clientes_unicos):
                    df_cl = df_f[df_f["CLIENTES"] == cl]
                    sum_cl = df_cl["TIEMPO_RES"].sum() / 60
                    pdf_a.set_font("Arial", 'B', 10)
                    pdf_a.cell(115, 7, f"CLIENTE: {cl}", 1, 0, fill=True)
                    pdf_a.cell(30, 7, f"{sum_cl:,.2f} hs", 1, ln=True, align='R', fill=True)
                    
                pdf_a.ln(5)
                # Total por Consultor al final
                pdf_a.set_font("Arial", 'B', 11); pdf_a.cell(0, 8, "TOTAL POR CONSULTOR", ln=True)
                pdf_a.set_font("Arial", '', 10)
                res_con = df_f.groupby("CONSULTOR")["TIEMPO_RES"].sum().reset_index()
                for _, r in res_con.iterrows():
                    pdf_a.cell(85, 7, str(r['CONSULTOR']), 1)
                    pdf_a.cell(30, 7, f"{(r['TIEMPO_RES']/60):,.2f} hs", 1, ln=True, align='R')
                
            else:
                # CASO UN SOLO CLIENTE
                cl_name = clientes_unicos[0]
                pdf_a.set_font("Arial", 'B', 12)
                # Recuadro por cliente
                pdf_a.rect(10, pdf_a.get_y(), 190, 12)
                pdf_a.cell(0, 12, f"  CLIENTE: {cl_name}", ln=True)
                pdf_a.ln(2)
                
                # Registro de cada módulo
                pdf_a.set_font("Arial", 'B', 10)
                pdf_a.cell(100, 7, "MÓDULO", 1); pdf_a.cell(30, 7, "HORAS", 1, ln=True, align='C')
                pdf_a.set_font("Arial", '', 10)
                res_mod = df_f.groupby("MODULO")["TIEMPO_RES"].sum().reset_index()
                for _, rm in res_mod.iterrows():
                    pdf_a.cell(100, 7, str(rm['MODULO']), 1)
                    pdf_a.cell(30, 7, f"{(rm['TIEMPO_RES']/60):,.2f}", 1, ln=True, align='R')

            # TOTAL GENERAL FINAL (Para ambos casos)
            pdf_a.ln(5)
            pdf_a.set_font("Arial", 'B', 11)
            pdf_a.set_text_color(255, 0, 0)
            pdf_a.cell(100, 10, "TOTAL GENERAL PROYECTO:", 1, 0, 'R')
            pdf_a.cell(30, 10, f"{t_hs:,.2f} hs", 1, ln=True, align='C')
            pdf_a.set_text_color(0, 0, 0)

            # Pie de página
            pdf_a.ln(10); pdf_a.set_font("Arial", 'I', 8)
            pdf_a.cell(0, 10, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 0, 0, 'C')
            st.download_button("📥 PDF", pdf_a.output(dest='S').encode('latin-1', 'ignore'), f"Analitico_GR{nom_base}.pdf")

# (Resto de Dashboards, Consultar y Permisos se mantienen igual)
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    if not df_f.empty:
        df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA"]], on="CONSULTOR", how="left").fillna(0)
        tab1, tab2, tab3 = st.tabs(["📋 Operativo", "⚡ Performance", "💰 Financiero"])
        with tab1: st.bar_chart(df_dash.groupby("MODULO")["TIEMPO_RES"].sum())
        with tab2:
            df_p = df_dash.groupby(["FE_DT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum"}).reset_index()
            st.line_chart(df_p.set_index("FE_DT")["TIEMPO_RES"])
        with tab3:
            df_dash["COSTO"] = (df_dash["TIEMPO_RES"]/60) * pd.to_numeric(df_dash["VALOR_HORA"], errors='coerce').fillna(0)
            st.metric("Inversión Total", f"$ {df_dash['COSTO'].sum():,.2f}")

elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Ticket:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['ESTADO']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#","")); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"Ticket #{id_c} [{dc['ESTADO']}]")
            v1, v2, v3 = st.columns(3)
            with v1: st.markdown(f"**CONSULTOR:** {dc['CONSULTOR']}\n\n**TIPO:** {dc['TIPO_CONS']}\n\n**PRIORIDAD:** {dc['PRIORIDAD']}")
            with v2: st.markdown(f"**CLIENTE:** {dc['CLIENTES']}\n\n**USUARIO:** {dc['USUARIO']}\n\n**ATENCIÓN:** {dc['ATENCION']}")
            with v3: st.markdown(f"**FECHA:** {dc['FE_CONSULT']}\n\n**TIEMPO:** {dc['TIEMPO_RES']} min\n\n**ONLINE:** {dc['ONLINE']}")
            st.divider(); st.info(f"**Consulta:**\n{dc['CONSULTAS']}"); st.success(f"**Respuesta:**\n{dc['RESPUESTAS']}")

elif st.session_state.menu_activo == "⚙️ PERMISOS" and es_admin:
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar"): conn.update(spreadsheet=url, worksheet="Config_Consultores", data=df_ed); st.rerun()
