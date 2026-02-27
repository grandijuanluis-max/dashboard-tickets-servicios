import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import platform 
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN E IDENTIFICACIÓN
st.set_page_config(page_title="Gestión de Tickets - GR Consulting", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

# Variables Globales y Diccionarios
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
        # Limpieza de datos clave
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

lista_cons = sorted(df_config["CONSULTOR"].unique()) if not df_config.empty else [nombre_operador]

if not df_actual.empty:
    df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
    df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)
    df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
    df_actual["ID_NUM"] = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').fillna(0).astype(int)

# ==========================================
# MENÚ Y SIDEBAR
# ==========================================
st.title("📋 GR Consulting - Gestión Integral de Tickets")
with st.sidebar:
    st.info(f"👤 **Operador:** {nombre_operador}\n\n💻 **Equipo:** {id_maquina_actual}")
    st.divider()
    if st.button("🔄 Refrescar Todo"): st.rerun()

cols = st.columns(5)
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
for i, b in enumerate(btns):
    if cols[i].button(b, use_container_width=True): st.session_state.menu_activo = b

st.markdown(f"📍 Sección actual: **{st.session_state.menu_activo}**")
st.divider()

# ==========================================
# SECCIÓN 1: NUEVO
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Cargando Ticket #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            idx_u = lista_cons.index(nombre_operador) if nombre_operador in lista_cons else 0
            cons_sel = st.selectbox("Consultor *", options=lista_cons, index=idx_u)
            est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            cli = st.selectbox("Cliente", ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"])
            usu = st.text_input("Usuario Cliente *").upper()
        with c3:
            fe = st.date_input("Fecha Consulta", datetime.now()); tie = st.number_input("Tiempo (min) *", min_value=0)
        
        con_det = st.text_area("Detalle de Consulta *")
        rta_det = st.text_area("Respuesta / Solución *")
        
        if st.form_submit_button("💾 GUARDAR TICKET"):
            if usu and con_det and rta_det and tie > 0:
                nuevo = pd.DataFrame([{"ID_TICKET": proximo_id, "CONSULTOR": cons_sel, "ESTADO": est, "CLIENTES": cli, "USUARIO": usu, "FE_CONSULT": fe.strftime('%d/%m/%Y'), "CONSULTAS": con_det, "RESPUESTAS": rta_det, "TIEMPO_RES": tie, "ANIO": fe.year, "MES": fe.month, "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": id_maquina_actual}])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo], ignore_index=True))
                registrar_auditoria(proximo_id, "ALTA", cons_sel)
                st.balloons(); st.rerun()
            else: st.error("⚠️ Complete todos los campos marcados con *")

# ==========================================
# SECCIÓN 2: MODIFICAR
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    pend = df_actual[df_actual["ESTADO"].str.upper() != "CERRADO"].copy()
    if not pend.empty:
        sel_m = st.selectbox("Buscar Ticket Abierto:", pend.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {str(r['CONSULTAS'])[:40]}...", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#",""))
        idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]
        dm = df_actual.loc[idx_f]
        with st.form("f_mod"):
            st.warning(f"Última edición: {dm['ULTIMA_MODIF']} por {dm['MODIFICADO_POR']}")
            c1, c2 = st.columns(2)
            n_est = c1.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(dm["ESTADO"]) if dm["ESTADO"] in ["ABIERTO", "EN PROCESO", "CERRADO"] else 0)
            n_tie = c2.number_input("Tiempo Insumido (min)", value=int(dm["TIEMPO_RES"]))
            n_con = st.text_area("Consulta (Editable)", value=dm["CONSULTAS"])
            n_rta = st.text_area("Respuesta (Editable)", value=dm["RESPUESTAS"])
            if st.form_submit_button("🔥 ACTUALIZAR TICKET"):
                df_actual.at[idx_f, "ESTADO"] = n_est; df_actual.at[idx_f, "TIEMPO_RES"] = n_tie
                df_actual.at[idx_f, "CONSULTAS"] = n_con; df_actual.at[idx_f, "RESPUESTAS"] = n_rta
                df_actual.at[idx_f, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                registrar_auditoria(id_m, "MODIFICACION", nombre_operador)
                st.success("Cambios guardados."); st.rerun()

# ==========================================
# SECCIÓN 3: CONSULTAR (CON FILTROS Y PDF)
# ==========================================
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    st.header("🔍 Buscador de Tickets")
    c1, c2, c3 = st.columns(3)
    with c1: f_cli_c = st.selectbox("Cliente:", ["TODOS"] + sorted(df_actual["CLIENTES"].unique().tolist()))
    with c2: f_ani_c = st.multiselect("Año(s):", options=sorted(df_actual["ANIO"].unique(), reverse=True))
    with c3: f_mes_c = st.multiselect("Mes(es):", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])
    
    df_f = df_actual.copy()
    if f_cli_c != "TODOS": df_f = df_f[df_f["CLIENTES"] == f_cli_c]
    if f_ani_c: df_f = df_f[df_f["ANIO"].isin(f_ani_c)]
    if f_mes_c: df_f = df_f[df_f["MES"].isin(f_mes_c)]
    
    if not df_f.empty:
        sel_c = st.selectbox("Seleccione para ver Ficha:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#",""))
        dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            v1, v2 = st.columns(2)
            v1.write(f"**Consultor:** {dc['CONSULTOR']} | **Estado:** {dc['ESTADO']}")
            v2.write(f"**Usuario:** {dc['USUARIO']} | **Tiempo:** {dc['TIEMPO_RES']} min")
            st.info(f"**Consulta:**\n{dc['CONSULTAS']}")
            st.success(f"**Respuesta:**\n{dc['RESPUESTAS']}")
            # PDF Individual con Cierre de Horas
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 15, "GR Consulting - Servicios", ln=True, align='C')
            pdf.set_font("Arial", size=10); pdf.ln(5)
            pdf.cell(0, 10, f"Ticket: #{id_c} | Cliente: {dc['CLIENTES']} | Fecha: {dc['FE_CONSULT']}", border=1, ln=True)
            pdf.multi_cell(0, 10, f"CONSULTA: {dc['CONSULTAS']}", border=1)
            pdf.multi_cell(0, 10, f"RESPUESTA: {dc['RESPUESTAS']}", border=1)
            pdf.ln(5); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, f"TOTAL HS INSUMIDAS: {float(dc['TIEMPO_RES'])/60:.2f} hs", align='R')
            st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# ==========================================
# SECCIÓN 4: REPORTES (TOTALIZADOS Y XLS)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header("📊 Generador de Reportes Analíticos")
    # Filtros avanzados solicitados
    c1, c2, c3 = st.columns(3)
    with c1: f_cli_r = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique())); f_con_r = st.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()))
    with c2: f_mod_r = st.multiselect("Módulos:", sorted(df_actual["MODULO"].unique()) if "MODULO" in df_actual.columns else []); f_ani_r = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True))
    with c3: f_mes_r = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])
    
    df_r = df_actual.copy()
    if f_cli_r: df_r = df_r[df_r["CLIENTES"].isin(f_cli_r)]
    if f_con_r: df_r = df_r[df_r["CONSULTOR"].isin(f_con_r)]
    if f_mod_r: df_r = df_r[df_r["MODULO"].isin(f_mod_r)]
    if f_ani_r: df_r = df_r[df_r["ANIO"].isin(f_ani_r)]
    if f_mes_r: df_r = df_r[df_r["MES"].isin(f_mes_r)]
    
    if not df_r.empty:
        t_hs = df_r["TIEMPO_RES"].sum() / 60
        st.metric("Total de Horas Filtradas", f"{t_hs:,.2f} hs")
        
        # Tabla agrupada de resumen
        res = df_r.groupby(["CLIENTES", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index()
        res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res, use_container_width=True, hide_index=True)
        
        st.divider()
        tipo_ex = st.radio("Tipo de Exportación Excel:", ["Resumen Agrupado", "Detalle Ticket por Ticket"], horizontal=True)
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                if "Resumen" in tipo_ex:
                    res.to_excel(w, index=False, sheet_name='Resumen')
                else:
                    # REVISIÓN: Consultas y Respuestas al FINAL
                    cols_det = ["ID_TICKET", "FE_CONSULT", "CLIENTES", "USUARIO", "CONSULTOR", "TIEMPO_RES"]
                    df_det = df_r[cols_det].copy()
                    df_det["TIEMPO_HS"] = (df_det["TIEMPO_RES"]/60).round(2)
                    df_det["CONSULTAS"] = df_r["CONSULTAS"]
                    df_det["RESPUESTAS"] = df_r["RESPUESTAS"]
                    df_det.to_excel(w, index=False, sheet_name='Detalle')
            st.download_button("📥 Descargar Excel (.xlsx)", buf.getvalue(), f"Reporte_GR_{datetime.now().strftime('%Y%m%d')}.xlsx")
        
        with col_ex2:
            # PDF Analítico con Encabezado de Filtros
            pdf_r = FPDF(); pdf_r.add_page(); pdf_r.set_font("Arial", 'B', 14); pdf_r.cell(0, 10, "Reporte Consolidado GR Consulting", ln=True, align='C')
            pdf_r.set_font("Arial", size=9); pdf_r.ln(2)
            pdf_r.cell(0, 8, f"Filtros: Clientes({len(f_cli_r) if f_cli_r else 'Todos'}) | Consultores({len(f_con_r) if f_con_r else 'Todos'})", ln=True)
            pdf_r.ln(5); pdf_r.set_font("Arial", 'B', 10)
            pdf_r.cell(60, 8, "Cliente", 1); pdf_r.cell(60, 8, "Consultor", 1); pdf_r.cell(30, 8, "Horas", 1, ln=True)
            pdf_r.set_font("Arial", size=9)
            for _, row in res.iterrows():
                pdf_r.cell(60, 8, str(row['CLIENTES']), 1); pdf_r.cell(60, 8, str(row['CONSULTOR']), 1); pdf_r.cell(30, 8, str(row['HORAS']), 1, ln=True)
            pdf_r.ln(5); pdf_r.set_font("Arial", 'B', 11); pdf_r.cell(0, 10, f"TOTAL GENERAL: {t_hs:.2f} hs", align='R')
            st.download_button("📥 Descargar PDF Analítico", pdf_r.output(dest='S').encode('latin-1'), "Reporte_Analitico.pdf")

# ==========================================
# SECCIÓN 5: DASHBOARDS (CON LOS MISMOS FILTROS)
# ==========================================
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    st.header("📈 Centro de Control Estratégico")
    
    # REVISIÓN: Agregando filtros a Dashboards
    with st.expander("🔍 Filtros de Dashboard", expanded=False):
        c1, c2, c3 = st.columns(3)
        f_cli_d = c1.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()), key="d_cli")
        f_con_d = c1.multiselect("Consultores:", sorted(df_actual["CONSULTOR"].unique()), key="d_con")
        f_ani_d = c2.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True), key="d_ani")
        f_mes_d = c3.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x], key="d_mes")

    df_d = pd.merge(df_actual, df_config, on="CONSULTOR", how="left").fillna(0)
    if f_cli_d: df_d = df_d[df_d["CLIENTES"].isin(f_cli_d)]
    if f_con_d: df_d = df_d[df_d["CONSULTOR"].isin(f_con_d)]
    if f_ani_d: df_d = df_d[df_d["ANIO"].isin(f_ani_d)]
    if f_mes_d: df_d = df_d[df_d["MES"].isin(f_mes_d)]
    
    t1, t2, t3 = st.tabs(["DB1 Operativo", "DB2 Performance", "DB3 Financiero"])
    
    with t1:
        st.subheader("Distribución de Horas por Cliente")
        st.bar_chart(df_d.groupby("CLIENTES")["TIEMPO_RES"].sum() / 60)
    with t2:
        st.subheader("Carga Diaria vs Objetivo (Disponible)")
        df_perf = df_d.groupby(["FE_CONSULT", "CONSULTOR"]).agg({"TIEMPO_RES":"sum", "DISPONIBLE":"first"}).reset_index()
        st.line_chart(df_perf.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])
    with t3:
        st.subheader("Inversión Operativa ($)")
        df_d["COSTO"] = (df_d["TIEMPO_RES"]/60) * df_d["VALOR_HORA"]
        st.metric("Total Invertido", f"$ {df_d['COSTO'].sum():,.2f}")
        st.bar_chart(df_d.groupby("CONSULTOR")["COSTO"].sum())
