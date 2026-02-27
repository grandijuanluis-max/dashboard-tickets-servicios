import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import platform 
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIFICACIÓN
st.set_page_config(page_title="GR Consulting - BI Dashboard", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
id_maquina_actual = f"{platform.node()}\\{getpass.getuser()}".upper()

# --- FUNCIONES CORE ---
def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df.fillna("")

def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for col in ["CONSULTOR", "ID_EQUIPO"]:
            if col in df.columns: df[col] = df[col].astype(str).str.upper().str.strip()
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

# Identificación del operador
nombre_operador = "DESCONOCIDO"
if not df_config.empty and "ID_EQUIPO" in df_config.columns:
    u_match = df_config[df_config["ID_EQUIPO"] == id_maquina_actual]
    if not u_match.empty: nombre_operador = u_match["CONSULTOR"].values[0]

lista_cons_config = sorted(df_config["CONSULTOR"].unique()) if not df_config.empty else [nombre_operador]

if not df_actual.empty:
    df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
    df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
    df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)

# ==========================================
# 🎯 FILTROS MAESTROS (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("🎯 Filtros Maestros")
    st.info(f"👤 **Operador:** {nombre_operador}")
    
    if not df_actual.empty:
        f_cli = st.multiselect("Filtrar Clientes:", sorted(df_actual["CLIENTES"].unique()))
        f_con = st.multiselect("Filtrar Consultores:", sorted(df_actual["CONSULTOR"].unique()))
        f_mod = st.multiselect("Filtrar Módulos:", sorted(df_actual["MODULO"].unique()) if "MODULO" in df_actual.columns else [])
        f_ani = st.multiselect("Filtrar Años:", sorted(df_actual["ANIO"].unique(), reverse=True))
        f_mes = st.multiselect("Filtrar Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])
    
    st.divider()
    if st.button("🔄 Refrescar Todo"): st.rerun()

# APLICACIÓN GLOBAL DE FILTROS
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# ==========================================
# MENÚ PRINCIPAL
# ==========================================
st.title("📋 GR Consulting - Inteligencia de Negocios")
cols_menu = st.columns(5)
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
for i, b in enumerate(btns):
    if cols_menu[i].button(b, use_container_width=True): st.session_state.menu_activo = b

st.markdown(f"📍 Sección: **{st.session_state.menu_activo}**")
st.divider()

# --- SECCIÓN 1: NUEVO ---
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            idx_u = lista_cons_config.index(nombre_operador) if nombre_operador in lista_cons_config else 0
            cons_sel = st.selectbox("Consultor *", options=lista_cons_config, index=idx_u)
            est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            cli_n = st.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
            usu_n = st.text_input("Usuario Cliente *").upper()
        with c3:
            fe_n = st.date_input("Fecha", datetime.now()); tie_n = st.number_input("Minutos *", min_value=0)
        
        con_txt = st.text_area("Detalle Consulta *"); rta_txt = st.text_area("Respuesta *")
        if st.form_submit_button("💾 GUARDAR"):
            if usu_n and con_txt and rta_txt and tie_n > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": cons_sel, "ESTADO": est, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ANIO": fe_n.year, "MES": fe_n.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": id_maquina_actual}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", cons_sel)
                st.balloons(); st.rerun()

# --- SECCIÓN 3: CONSULTAR ---
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Seleccione Ticket Filtrado:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#",""))
        dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.write(f"### Ficha #{id_c}"); v1, v2 = st.columns(2)
            v1.write(f"**Consultor:** {dc['CONSULTOR']} | **Estado:** {dc['ESTADO']}")
            v2.write(f"**Cliente:** {dc['CLIENTES']} | **Tiempo:** {dc['TIEMPO_RES']} min")
            st.info(f"**Consulta:** {dc['CONSULTAS']}"); st.success(f"**Respuesta:** {dc['RESPUESTAS']}")
            # PDF Institucional
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "GR Consulting", ln=True, align='C')
            pdf.ln(10); pdf.set_font("Arial", size=10); pdf.cell(0, 10, f"Ticket: #{id_c} | Cliente: {dc['CLIENTES']}", border=1, ln=True)
            pdf.multi_cell(0, 10, f"DETALLE: {dc['CONSULTAS']}", border=1)
            pdf.multi_cell(0, 10, f"SOLUCION: {dc['RESPUESTAS']}", border=1)
            pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"TOTAL: {float(dc['TIEMPO_RES'])/60:.2f} hs", align='R')
            st.download_button("📥 PDF Individual", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# --- SECCIÓN 4: REPORTES ---
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Reportes y Exportación")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Horas Totales (Bajo Filtros)", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index(); res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                # DETALLE: Textos al FINAL
                df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES"]].copy()
                df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2)
                df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                df_det.to_excel(w, index=False)
            st.download_button("📥 Excel Detallado", buf.getvalue(), "Reporte_GR_Full.xlsx")
        
        with col2:
            pdf_r = FPDF(); pdf_r.add_page(); pdf_r.set_font("Arial", 'B', 14); pdf_r.cell(0, 10, "Resumen Analítico GR", ln=True, align='C')
            pdf_r.set_font("Arial", size=9); pdf_r.ln(5)
            for _, row in res.iterrows():
                pdf_r.cell(0, 8, f"{row['CLIENTES']} | {row['CONSULTOR']}: {row['HORAS']} hs", ln=True, border=1)
            pdf_r.ln(5); pdf_r.cell(0, 10, f"TOTAL: {t_hs:.2f} hs", align='R')
            st.download_button("📥 PDF Analítico", pdf_r.output(dest='S').encode('latin-1'), "Reporte_Analitico.pdf")

# ==========================================
# 📈 DASHBOARDS DINÁMICOS
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    if df_f.empty:
        st.warning("Ajuste los Filtros Maestros para visualizar métricas.")
    else:
        # Unión con configuración para KPIs financieros y de performance
        df_dash = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
        
        tab1, tab2, tab3 = st.tabs(["📋 DB1: OPERATIVO", "⚡ DB2: PERFORMANCE", "💰 DB3: FINANCIERO"])
        
        with tab1:
            st.subheader("Volumen y Estado (Dinámico)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tickets", len(df_dash))
            c2.metric("Promedio min", f"{df_dash['TIEMPO_RES'].mean():.1f}")
            c3.metric("Cerrados", len(df_dash[df_dash["ESTADO"] == "CERRADO"]))
            c4.metric("% Eficacia", f"{(len(df_dash[df_dash['ESTADO'] == 'CERRADO'])/len(df_dash)*100):.1f}%")
            
            st.divider()
            col_a, col_b = st.columns(2)
            col_a.write("**Tickets por Cliente**")
            col_a.bar_chart(df_dash["CLIENTES"].value_counts())
            col_b.write("**Tickets por Módulo**")
            col_b.bar_chart(df_dash["MODULO"].value_counts())

        with tab2:
            st.subheader("Performance y Capacidad Diaria")
            df_p = df_dash.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES": "sum", "DISPONIBLE": "first"}).reset_index()
            
            # KPI de Ocupación
            df_p["OCUPACION"] = (df_p["TIEMPO_RES"] / df_p["DISPONIBLE"] * 100).fillna(0)
            st.metric("Ocupación Promedio", f"{df_p['OCUPACION'].mean():.1f}%")
            
            st.write("**Gráfico de Carga Real vs Objetivo Diario**")
            st.line_chart(df_p.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])

        with tab3:
            st.subheader("Análisis Financiero")
            df_dash["COSTO"] = (df_dash["TIEMPO_RES"] / 60) * df_dash["VALOR_HORA"]
            st.metric("Inversión Operativa Total", f"$ {df_dash['COSTO'].sum():,.2f}")
            
            f1, f2 = st.columns(2)
            f1.write("**Inversión por Cliente ($)**")
            f1.bar_chart(df_dash.groupby("CLIENTES")["COSTO"].sum())
            f2.write("**Costo por Consultor ($)**")
            f2.bar_chart(df_dash.groupby("CONSULTOR")["COSTO"].sum())
