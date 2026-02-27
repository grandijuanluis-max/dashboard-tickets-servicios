import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import platform 
import io
from fpdf import FPDF

# 1. Configuración y Conexión
st.set_page_config(page_title="Gestión de Tickets - GR Consulting", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

# Variables Globales
mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
id_maquina_actual = f"{platform.node()}\\{getpass.getuser()}".upper()

# --- FUNCIONES NATIVAS ---
def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = df.columns.str.strip()
        df["CONSULTOR"] = df["CONSULTOR"].astype(str).str.upper().str.strip()
        df["ID_EQUIPO"] = df["ID_EQUIPO"].astype(str).str.upper().str.strip()
        df["VALOR_HORA"] = pd.to_numeric(df["VALOR_HORA"], errors='coerce').fillna(0)
        df["DISPONIBLE"] = pd.to_numeric(df["DISPONIBLE"], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def registrar_auditoria(id_ticket, accion, consultor):
    try:
        try: df_logs = conn.read(spreadsheet=url, worksheet="Log_Auditoria", ttl=0)
        except: df_logs = pd.DataFrame(columns=["ID_TICKET", "ID_EQUIPO", "CONSULTOR", "FECHA_HORA", "ACCION"])
        nuevo_log = pd.DataFrame([{"ID_TICKET": id_ticket, "ID_EQUIPO": id_maquina_actual, "CONSULTOR": consultor, "FECHA_HORA": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "ACCION": accion}])
        conn.update(spreadsheet=url, worksheet="Log_Auditoria", data=pd.concat([df_logs, nuevo_log], ignore_index=True))
    except: pass

# --- PROCESAMIENTO INICIAL ---
df_actual = obtener_datos()
df_config = obtener_config()

# Identificar Usuario y Permisos
nombre_usuario = "DESCONOCIDO"
permisos = {"DB1": False, "DB2": False, "DB3": False}
if not df_config.empty:
    u_row = df_config[df_config["ID_EQUIPO"] == id_maquina_actual]
    if not u_row.empty:
        nombre_usuario = u_row["CONSULTOR"].values[0]
        permisos["DB1"] = str(u_row["ACCESO_DB1"].values[0]).upper() == "SI"
        permisos["DB2"] = str(u_row["ACCESO_DB2"].values[0]).upper() == "SI"
        permisos["DB3"] = str(u_row["ACCESO_DB3"].values[0]).upper() == "SI"

if not df_actual.empty:
    df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
    df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)
    df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
    df_actual["ID_NUM"] = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').fillna(0).astype(int)

# ==========================================
# INTERFAZ DE USUARIO
# ==========================================
st.title("📋 Sistema de Gestión GR Consulting")
cols = st.columns(5)
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
for i, b in enumerate(btns):
    if cols[i].button(b, use_container_width=True): st.session_state.menu_activo = b

with st.sidebar:
    st.info(f"👤 **Consultor:** {nombre_usuario}")
    st.caption(f"💻 **Equipo:** {id_maquina_actual}")

st.markdown(f"📍 Sección: **{st.session_state.menu_activo}**")
st.divider()

# --- NUEVO TICKET ---
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Cargando Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            lista_c = sorted(df_config["CONSULTOR"].unique()) if not df_config.empty else [nombre_usuario]
            idx_u = lista_c.index(nombre_usuario) if nombre_usuario in lista_c else 0
            cons_sel = st.selectbox("Consultor", options=lista_c, index=idx_u)
            est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            cli = st.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
            usu = st.text_input("Usuario Cliente").upper()
        with c3:
            fe = st.date_input("Fecha", datetime.now()); tie = st.number_input("Minutos", min_value=0)
        
        con = st.text_area("Consulta"); rta = st.text_area("Respuesta")
        if st.form_submit_button("💾 GUARDAR"):
            if usu and con and rta and tie > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": cons_sel, "ESTADO": est, "CLIENTES": cli, "USUARIO": usu, "FE_CONSULT": fe.strftime('%d/%m/%Y'), "CONSULTAS": con, "RESPUESTAS": rta, "TIEMPO_RES": tie, "ANIO": fe.year, "MES": fe.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": id_maquina_actual}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", cons_sel)
                st.balloons(); st.rerun()

# --- MODIFICAR ---
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    pend = df_actual[df_actual["ESTADO"].str.upper() != "CERRADO"].copy()
    if not pend.empty:
        sel_m = st.selectbox("Ticket:", pend.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {str(r['CONSULTAS'])[:30]}", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]
        dm = df_actual.loc[idx_f]
        with st.form("f_mod"):
            c1, c2 = st.columns(2)
            n_est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]) if dm["ESTADO"] in ["ABIERTO", "EN PROCESO", "CERRADO"] else 0)
            n_tie = c2.number_input("Minutos", value=int(dm["TIEMPO_RES"]))
            n_con = st.text_area("Consulta (Editable)", value=dm["CONSULTAS"])
            n_rta = st.text_area("Respuesta (Editable)", value=dm["RESPUESTAS"])
            if st.form_submit_button("🔥 ACTUALIZAR"):
                df_actual.at[idx_f, "ESTADO"] = n_est; df_actual.at[idx_f, "TIEMPO_RES"] = n_tie
                df_actual.at[idx_f, "CONSULTAS"] = n_con; df_actual.at[idx_f, "RESPUESTAS"] = n_rta
                df_actual.at[idx_f, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                registrar_auditoria(id_m, "MODIFICACION", nombre_usuario)
                st.rerun()

# --- CONSULTAR ---
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    c1, c2 = st.columns(2)
    f_cli = c1.selectbox("Cliente", ["TODOS"] + sorted(df_actual["CLIENTES"].unique().tolist()))
    f_mes = c2.multiselect("Meses", options=list(mes_d.keys()), format_func=lambda x: mes_d[x], default=[datetime.now().month])
    df_f = df_actual.copy()
    if f_cli != "TODOS": df_f = df_f[df_f["CLIENTES"] == f_cli]
    if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]
    if not df_f.empty:
        sel_c = st.selectbox("Ficha:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#",""))
        dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.write(f"### Ticket #{id_c} - {dc['CLIENTES']}")
            st.write(f"**Consultor:** {dc['CONSULTOR']} | **Usuario:** {dc['USUARIO']} | **Tiempo:** {dc['TIEMPO_RES']} min")
            st.info(f"**Consulta:** {dc['CONSULTAS']}")
            st.success(f"**Respuesta:** {dc['RESPUESTAS']}")
            # PDF Individual
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "GR Consulting - Servicios", ln=True, align='C')
            pdf.set_font("Arial", size=10); pdf.ln(5)
            pdf.cell(0, 10, f"Ticket: #{id_c} | Cliente: {dc['CLIENTES']} | Fecha: {dc['FE_CONSULT']}", border=1, ln=True)
            pdf.multi_cell(0, 10, f"CONSULTA: {dc['CONSULTAS']}", border=1)
            pdf.multi_cell(0, 10, f"RESPUESTA: {dc['RESPUESTAS']}", border=1)
            pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"CANTIDAD DE HS INSUMIDAS: {float(dc['TIEMPO_RES'])/60:.2f} hs", align='R')
            st.download_button("📥 PDF Ticket", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# --- REPORTES ---
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Reportes y Exportación")
    f_cli_r = st.multiselect("Clientes", sorted(df_actual["CLIENTES"].unique()))
    df_r = df_actual.copy()
    if f_cli_r: df_r = df_r[df_r["CLIENTES"].isin(f_cli_r)]
    if not df_r.empty:
        # Tabla agrupada
        res = df_r.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index()
        res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True)
        # Exportación XLSX Detallada (Consultas al final)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_det = df_r[["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES"]]
            df_det["CONSULTAS"] = df_r["CONSULTAS"]
            df_det["RESPUESTAS"] = df_r["RESPUESTAS"]
            df_det.to_excel(w, index=False)
        st.download_button("📥 Excel Detallado", buf.getvalue(), "Reporte_GR.xlsx")

# --- DASHBOARDS ---
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    if not any(permisos.values()): st.error("🚫 Acceso Denegado")
    else:
        st.header("📈 Centro de Control Estratégico")
        t_n = [k for k, v in permisos.items() if v]
        tabs = st.tabs([f"Grupo {x}" for x in t_n])
        df_d = pd.merge(df_actual, df_config, on="CONSULTOR", how="left").fillna(0)
        for i, nom in enumerate(t_n):
            with tabs[i]:
                if nom == "DB1": st.bar_chart(df_d.groupby("CLIENTES")["TIEMPO_RES"].sum()/60)
                if nom == "DB2": st.line_chart(df_d.groupby(["FE_CONSULT", "CONSULTOR"])["TIEMPO_RES"].sum().unstack())
                if nom == "DB3": 
                    df_d["COSTO"] = (df_d["TIEMPO_RES"]/60)*df_d["VALOR_HORA"]
                    st.metric("Inversión Total", f"$ {df_d['COSTO'].sum():,.2f}")
                    st.bar_chart(df_d.groupby("CONSULTOR")["COSTO"].sum())
