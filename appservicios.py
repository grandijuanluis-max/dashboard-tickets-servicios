import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import io
from fpdf import FPDF

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets - GR Consulting", layout="wide")

# 1. Conexión y Control de Estado
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

# --- FUNCIONES DE CARGA ---
def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

def obtener_config_consultores():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = df.columns.str.strip()
        df["CONSULTOR"] = df["CONSULTOR"].astype(str).str.upper().str.strip()
        df["VALOR_HORA"] = pd.to_numeric(df["VALOR_HORA"], errors='coerce').fillna(0)
        df["DISPONIBLE"] = pd.to_numeric(df["DISPONIBLE"], errors='coerce').fillna(0)
        # Limpieza de columnas de acceso
        for col in ["ACCESO_DB1", "ACCESO_DB2", "ACCESO_DB3"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.upper().str.strip()
        return df
    except:
        return pd.DataFrame()

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
    df_config = obtener_config_consultores()
    
    # Lógica de Seguridad Triple
    permisos = {"DB1": False, "DB2": False, "DB3": False}
    if not df_config.empty:
        u_data = df_config[df_config["CONSULTOR"] == usuario_pc]
        if not u_data.empty:
            permisos["DB1"] = u_data["ACCESO_DB1"].values[0] == "SI"
            permisos["DB2"] = u_data["ACCESO_DB2"].values[0] == "SI"
            permisos["DB3"] = u_data["ACCESO_DB3"].values[0] == "SI"

    lista_cons = sorted(df_config["CONSULTOR"].unique()) if not df_config.empty else ["CONFIGURAR EXCEL"]
    
    if not df_actual.empty:
        df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
        df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)
        df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
        df_actual["ID_NUM"] = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').fillna(0).astype(int)
except Exception as e:
    st.error(f"Error General: {e}")
    df_actual = pd.DataFrame()

# ==========================================
# MENÚ DE NAVEGACIÓN
# ==========================================
st.title("📋 Sistema de Gestión GR Consulting")
cols = st.columns(5)
if cols[0].button("➕ NUEVO", use_container_width=True): st.session_state.menu_activo = "➕ NUEVO"
if cols[1].button("✏️ MODIFICAR", use_container_width=True): st.session_state.menu_activo = "✏️ MODIFICAR"
if cols[2].button("🔍 CONSULTAR", use_container_width=True): st.session_state.menu_activo = "🔍 CONSULTAR"
if cols[3].button("📊 REPORTES", use_container_width=True): st.session_state.menu_activo = "📊 REPORTES"
if cols[4].button("📈 DASHBOARDS", use_container_width=True): st.session_state.menu_activo = "📈 DASHBOARDS"

st.markdown(f"📍 Sección: **{st.session_state.menu_activo}** | Usuario: **{usuario_pc}**")
st.divider()

# --- SECCIONES 1 A 4 (NUEVO, MODIFICAR, CONSULTAR, REPORTES) ---
# [Lógica anterior intacta]

if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("form_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket N°: {proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            consultor = st.selectbox("Consultor *", options=lista_cons)
            tipo_c = st.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
            prio = st.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
            est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            ate = st.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
            cliente = st.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
            usuario_n = st.text_input("Usuario *").upper()
        with c3:
            modulo = st.selectbox("Módulo", ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PROGRAMA", "PRODUCCION","SERVIDOR", "WEB", "GERENCIAL", "RRHH", "IMPUESTOS", "SUCURSAL", "OTROS"])
            fe_c = st.date_input("Fecha Consulta", datetime.now()); t_res = st.number_input("Tiempo (min) *", min_value=0)
        con_det = st.text_area("Consulta *"); rta_det = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usuario_n.strip() and con_det.strip() and rta_det.strip() and t_res > 0:
                nuevo_reg = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": consultor, "TIPO_CONS": tipo_c, "PRIORIDAD": prio, "ESTADO": est, "ATENCION": ate, "CLIENTES": cliente, "USUARIO": usuario_n, "FE_CONSULT": fe_c.strftime('%d/%m/%Y'), "FE_RTA": fe_c.strftime('%d/%m/%Y'), "MODULO": modulo, "CONSULTAS": con_det, "RESPUESTAS": rta_det, "TIEMPO_RES": t_res, "ONLINE": "NO", "ANIO": int(fe_c.year), "MES": int(fe_c.month), "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo_reg], ignore_index=True))
                st.balloons(); st.rerun()

elif st.session_state.menu_activo == "✏️ MODIFICAR":
    if not df_actual.empty:
        pend = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not pend.empty:
            busq_m = st.text_input("🔍 Buscar Cliente:")
            if busq_m: pend = pend[pend["CLIENTES"].str.contains(busq_m, case=False)]
            pend = pend.sort_values(by=["CLIENTES", "ID_NUM"])
            if not pend.empty:
                op_m = pend.apply(lambda r: f"{r['CLIENTES']} | #{r['ID_NUM']} | {r['USUARIO']} | Obs: {str(r['CONSULTAS'])[:30]}...", axis=1).tolist()
                sel_m = st.selectbox("Selecciona Ticket:", op_m)
                id_m = int(sel_m.split(" | #")[1].split(" | ")[0])
                fila_idx = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]
                dm = df_actual.loc[fila_idx]
                with st.form("form_edit"):
                    st.warning(f"🕒 Modificado: {dm['ULTIMA_MODIF']} por {dm['MODIFICADO_POR']}")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1: est_m = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"]); t_m = st.number_input("Tiempo (min)", value=int(float(dm["TIEMPO_RES"])))
                    with ce2: st.text_input("Usuario", value=dm["USUARIO"], disabled=True); fe_r_m = st.date_input("F. Respuesta", datetime.now())
                    with ce3: st.text_input("Cliente", value=dm["CLIENTES"], disabled=True)
                    st.divider()
                    n_con = st.text_area("Detalle Consulta", value=dm["CONSULTAS"]); n_rta = st.text_area("Respuesta", value=dm["RESPUESTAS"])
                    if st.form_submit_button("🔥 ACTUALIZAR"):
                        df_actual.at[fila_idx, "ESTADO"] = est_m; df_actual.at[fila_idx, "FE_RTA"] = fe_r_m.strftime('%d/%m/%Y')
                        df_actual.at[fila_idx, "TIEMPO_RES"] = t_m; df_actual.at[fila_idx, "CONSULTAS"] = n_con; df_actual.at[fila_idx, "RESPUESTAS"] = n_rta
                        df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S"); df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                        st.rerun()

elif st.session_state.menu_activo == "🔍 CONSULTAR":
    c1, c2, c3 = st.columns(3)
    with c1: f_cli_c = st.selectbox("Cliente:", ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique())))
    with c2: f_ani_c = st.multiselect("Año(s):", options=sorted(df_actual["ANIO"].unique(), reverse=True), default=[2026] if 2026 in df_actual["ANIO"].unique() else [])
    with c3: f_mes_c = st.multiselect("Mes(es):", options=sorted(df_actual["MES"].unique()), format_func=lambda x: mes_d.get(x, x))
    df_f = df_actual.copy()
    if f_cli_c != "TODOS": df_f = df_f[df_f["CLIENTES"] == f_cli_c]
    if f_ani_c: df_f = df_f[df_f["ANIO"].isin(f_ani_c)]
    if f_mes_c: df_f = df_f[df_f["MES"].isin(f_mes_c)]
    if not df_f.empty:
        op_c = df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | Obs: {str(r['CONSULTAS'])[:30]}...", axis=1).tolist()
        sel_c = st.selectbox("Ver Ficha:", op_c); id_c = int(sel_c.split("#")[1].split(" |")[0]); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"🔍 Ficha Ticket #{id_c}")
            v1, v2, v3 = st.columns(3)
            with v1: st.text_input("Consultor", dc["CONSULTOR"], disabled=True); st.text_input("Estado", dc["ESTADO"], disabled=True)
            with v2: st.text_input("Cliente", dc["CLIENTES"], disabled=True); st.text_input("Usuario", dc["USUARIO"], disabled=True)
            with v3: st.text_input("Fecha", dc["FE_CONSULT"], disabled=True); st.text_input("Tiempo (min)", str(dc["TIEMPO_RES"]), disabled=True)
            st.text_area("Consulta", dc["CONSULTAS"], disabled=True); st.text_area("Respuesta", dc["RESPUESTAS"], disabled=True)
            pdf = FPDF(); pdf.add_page(); pdf.set_draw_color(180, 180, 180); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 15, txt="GR Consulting - Servicios", ln=True, align='C')
            pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, txt=f"Ticket #{id_c}", ln=True, align='L'); pdf.ln(5)
            pdf.set_font("Arial", 'B', 10); pdf.cell(50, 10, "ATENDIDO POR:", 1); pdf.cell(140, 10, str(dc['CONSULTOR']), 1, ln=True); pdf.cell(50, 10, "CLIENTE:", 1); pdf.cell(140, 10, str(dc['CLIENTES']), 1, ln=True); pdf.cell(50, 10, "USUARIO:", 1); pdf.cell(140, 10, str(dc['USUARIO']), 1, ln=True)
            pdf.cell(50, 10, "FECHA:", 1); pdf.cell(60, 10, str(dc['FE_CONSULT']), 1); pdf.cell(30, 10, "ESTADO:", 1); pdf.cell(50, 10, str(dc['ESTADO']), 1, ln=True); pdf.cell(50, 10, "TIEMPO (min):", 1); pdf.cell(140, 10, f"{dc['TIEMPO_RES']} min", 1, ln=True)
            pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, "CONSULTA:", ln=True); pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, txt=str(dc["CONSULTAS"]), border=1); pdf.ln(5); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, "RESPUESTA:", ln=True); pdf.set_font("Arial", size=10); pdf.multi_cell(0, 8, txt=str(dc["RESPUESTAS"]), border=1)
            pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, txt=f"CANTIDAD DE HS: {float(dc['TIEMPO_RES'])/60:.2f} hs", align='R')
            st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Reporte_{id_c}.pdf")

elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Análisis Operativo")
    f1, f2, f3 = st.columns(3)
    with f1: f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique())); f_con = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()))
    with f2: f_mod = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique())); f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True))
    with f3: f_mes = st.multiselect("Meses:", sorted(df_actual["MES"].unique()), format_func=lambda x: mes_d.get(x, x))
    df_rep = df_actual.copy()
    if f_cli: df_rep = df_rep[df_rep["CLIENTES"].isin(f_cli)]
    if f_mod: df_rep = df_rep[df_rep["MODULO"].isin(f_mod)]
    if f_con: df_rep = df_rep[df_rep["CONSULTOR"].isin(f_con)]
    if f_ani: df_rep = df_rep[df_rep["ANIO"].isin(f_ani)]
    if f_mes: df_rep = df_rep[df_rep["MES"].isin(f_mes)]
    if not df_rep.empty:
        t_min = df_rep["TIEMPO_RES"].sum(); t_hs = t_min / 60
        m1, m2 = st.columns(2); m1.metric("Tickets", len(df_rep)); m2.metric("Total Horas", f"{t_hs:,.2f} hs")
        res = df_rep.groupby(["CLIENTES", "MODULO", "CONSULTOR", "ANIO", "MES"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"] / 60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        tipo_ex = st.radio("Exportar:", ["Agrupado", "Detallado"], horizontal=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            if "Agrupado" in tipo_ex: res.to_excel(w, index=False)
            else: df_det = df_rep[["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "MODULO", "TIEMPO_RES", "CONSULTAS", "RESPUESTAS"]]; df_det.to_excel(w, index=False)
        st.download_button("📥 Descargar Excel", buf.getvalue(), f"Reporte_{tipo_ex}.xlsx")

# ==========================================
# SECCIÓN 5: DASHBOARDS (FILTRADO POR ACCESO DB1, DB2, DB3)
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    st.header("📊 Centro de Control Estratégico")
    
    # Verificamos si tiene al menos un acceso
    if not any(permisos.values()):
        st.error("🚫 ACCESO DENEGADO")
        st.warning(f"El usuario **{usuario_pc}** no tiene permisos asignados en Config_Consultores.")
    else:
        # Pestañas condicionales según permisos
        tabs_disponibles = [k for k, v in permisos.items() if v]
        tabs = st.tabs([f"Grupo {t}" for t in tabs_disponibles])
        
        # Unimos datos financieros para los dashboards
        df_dash = pd.merge(df_actual, df_config, on="CONSULTOR", how="left").fillna(0)
        df_dash["COSTO"] = (df_dash["TIEMPO_RES"] / 60) * df_dash["VALOR_HORA"]

        for i, t_name in enumerate(tabs_disponibles):
            with tabs[i]:
                # --- GRUPO DB1: MÉTRICAS OPERATIVAS ---
                if t_name == "DB1":
                    st.subheader("🛠️ Operación: Horas por Cliente y Módulo")
                    c1, c2 = st.columns(2)
                    with c1:
                        df_cli_hs = df_dash.groupby("CLIENTES")["TIEMPO_RES"].sum() / 60
                        st.bar_chart(df_cli_hs.sort_values(ascending=False), color="#29b5e8")
                    with c2:
                        df_mod_hs = df_dash.groupby("MODULO")["TIEMPO_RES"].sum() / 60
                        st.bar_chart(df_mod_hs.sort_values(ascending=False), color="#ffa500")

                # --- GRUPO DB2: PERFORMANCE Y OBJETIVOS ---
                elif t_name == "DB2":
                    st.subheader("⏱️ Performance: Real vs. Objetivo Diario")
                    df_perf = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
                    st.line_chart(df_perf.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
                    st.caption("Nota: La línea 'DISPONIBLE' indica el objetivo diario cargado en Config_Consultores.")

                # --- GRUPO DB3: FINANZAS Y RENTABILIDAD ---
                elif t_name == "DB3":
                    st.subheader("💰 Finanzas: Costo Operativo Insumido")
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        total_inv = df_dash["COSTO"].sum()
                        st.metric("Inversión Total", f"$ {total_inv:,.2f}")
                        st.metric("Promedio por Ticket", f"$ {total_inv/len(df_dash) if not df_dash.empty else 0:,.2f}")
                    with col2:
                        df_cost_con = df_dash.groupby("CONSULTOR")["COSTO"].sum()
                        st.bar_chart(df_cost_con, color="#ff4b4b")
