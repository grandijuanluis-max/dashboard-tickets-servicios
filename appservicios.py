import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import io
from fpdf import FPDF

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets", layout="wide")

# 1. Conexión y Control de Estado de Navegación
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

# MEMORIA DE NAVEGACIÓN
if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"
if "db_estandarizada" not in st.session_state:
    st.session_state.db_estandarizada = False

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

def limpiar_fecha(f):
    if not f or str(f).lower() == "nan" or str(f).strip() == "": return ""
    try:
        dt = pd.to_datetime(f, dayfirst=True, errors='coerce')
        return dt.strftime('%d/%m/%Y') if not pd.isna(dt) else str(f)
    except: return str(f)

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
    # Aseguramos que Año y Mes sean numéricos para los filtros
    if not df_actual.empty:
        df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
        df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    df_actual = pd.DataFrame()

# ==========================================
# TÍTULO Y MENÚ DE NAVEGACIÓN ESTABLE
# ==========================================
st.title("📋 Sistema de Gestión de Consultas y Tickets")

cols = st.columns(4)
if cols[0].button("➕ NUEVO TICKET", use_container_width=True): st.session_state.menu_activo = "➕ NUEVO"
if cols[1].button("✏️ MODIFICAR TICKET", use_container_width=True): st.session_state.menu_activo = "✏️ MODIFICAR"
if cols[2].button("🔍 CONSULTAR TICKETS", use_container_width=True): st.session_state.menu_activo = "🔍 CONSULTAR"
if cols[3].button("📊 REPORTES", use_container_width=True): st.session_state.menu_activo = "📊 REPORTES"

st.markdown(f"📍 Estás en: **{st.session_state.menu_activo}**")
st.divider()

# ==========================================
# SECCIÓN: NUEVO TICKET
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_num = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_num.max()) + 1 if not ids_num.empty else 1
    else: proximo_id = 1

    with st.form("form_nuevo", clear_on_submit=True):
        st.subheader(f"Cargando Ticket N°: {proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            consultor = st.text_input("Consultor").upper()
            tipo_c = st.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
            prio = st.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
            est = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            ate = st.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
            cli_opc = ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]
            cliente = st.selectbox("Cliente", cli_opc)
            usuario_n = st.text_input("Usuario *").upper()
        with c3:
            mod_opc = ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PROGRAMA", "PRODUCCION","SERVIDOR", "WEB", "GERENCIAL", "RRHH", "IMPUESTOS", "SUCURSAL", "OTROS"]
            modulo = st.selectbox("Módulo", mod_opc)
            fe_c = st.date_input("Fecha Consulta", datetime.now())
            t_res = st.number_input("Tiempo (min) *", min_value=0)

        con_det = st.text_area("Consulta *")
        rta_det = st.text_area("Respuesta *")
        
        if st.form_submit_button("💾 GUARDAR NUEVO TICKET"):
            if not (usuario_n.strip() and con_det.strip() and rta_det.strip() and t_res > 0):
                st.error("⚠️ Faltan datos obligatorios.")
            else:
                nuevo_reg = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor, "TIPO_CONS": tipo_c,
                    "PRIORIDAD": prio, "ESTADO": est, "ATENCION": ate, "CLIENTES": cliente,
                    "USUARIO": usuario_n, "FE_CONSULT": fe_c.strftime('%d/%m/%Y'),
                    "FE_RTA": fe_c.strftime('%d/%m/%Y'), "MODULO": modulo, "CONSULTAS": con_det,
                    "RESPUESTAS": rta_det, "TIEMPO_RES": t_res, "ONLINE": "NO",
                    "ANIO": int(fe_c.year), "MES": int(fe_c.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo_reg], ignore_index=True))
                st.balloons()
                st.rerun()

# ==========================================
# SECCIÓN: MODIFICAR TICKET
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    if not df_actual.empty:
        df_actual["ID_NUM"] = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        pend = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        
        if not pend.empty:
            busq_m = st.text_input("🔍 Buscar Cliente:")
            if busq_m: pend = pend[pend["CLIENTES"].str.contains(busq_m, case=False)]
            pend = pend.sort_values(by=["CLIENTES", "ID_NUM"])
            
            if not pend.empty:
                def etiqueta_mod(r):
                    obs = str(r['CONSULTAS']).strip().replace('\n', ' ')[:40]
                    return f"{r['CLIENTES']} | #{r['ID_NUM']} | {r['USUARIO']} | Obs: {obs}..."

                op_m = pend.apply(etiqueta_mod, axis=1).tolist()
                sel_m = st.selectbox("Selecciona Ticket:", op_m)
                
                id_m = int(sel_m.split(" | #")[1].split(" | ")[0])
                fila_idx = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]
                dm = df_actual.loc[fila_idx]

                with st.form("form_edit"):
                    st.warning(f"🕒 Modificado: {dm['ULTIMA_MODIF']} por {dm['MODIFICADO_POR']}")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        est_m = st.selectbox("Nuevo Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
                        t_m = st.number_input("Tiempo (min)", value=int(float(dm["TIEMPO_RES"] if dm["TIEMPO_RES"]!="" else 0)))
                    with ce2:
                        st.text_input("Usuario", value=dm["USUARIO"], disabled=True)
                        fe_r_m = st.date_input("F. Respuesta", datetime.now())
                    with ce3:
                        st.text_input("Cliente", value=dm["CLIENTES"], disabled=True)
                    
                    st.divider()
                    n_consulta_m = st.text_area("Detalle Consulta (Editable) *", value=dm["CONSULTAS"])
                    rta_m = st.text_area("Respuesta (Editable) *", value=dm["RESPUESTAS"])
                    
                    if st.form_submit_button("🔥 ACTUALIZAR TICKET"):
                        df_actual.at[fila_idx, "ESTADO"] = est_m
                        df_actual.at[fila_idx, "FE_RTA"] = fe_r_m.strftime('%d/%m/%Y')
                        df_actual.at[fila_idx, "TIEMPO_RES"] = t_m
                        df_actual.at[fila_idx, "CONSULTAS"] = n_consulta_m
                        df_actual.at[fila_idx, "RESPUESTAS"] = rta_m
                        df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                        df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                        conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ID_NUM"], errors="ignore"))
                        st.rerun()

# ==========================================
# SECCIÓN: CONSULTAR TICKETS (FILTROS MES/AÑO)
# ==========================================
elif st.session_state.menu_activo == "🔍 CONSULTAR":
    st.header("🔍 Consulta General de Tickets")
    
    if not df_actual.empty:
        # --- NUEVOS FILTROS DINÁMICOS ---
        c1, c2, c3 = st.columns(3)
        with c1:
            lista_cli = ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique()))
            f_cli = st.selectbox("Filtrar Cliente:", lista_cli)
        
        with c2:
            # Selector de Años (Default: Año actual) [cite: 2026-02-27]
            anios_disponibles = sorted(df_actual["ANIO"].unique(), reverse=True)
            anio_actual = datetime.now().year
            default_anio = [anio_actual] if anio_actual in anios_disponibles else []
            f_anios = st.multiselect("Seleccionar Año(s):", options=anios_disponibles, default=default_anio)
            
        with c3:
            # Selector de Meses
            meses_opc = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 
                         7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
            f_meses = st.multiselect("Seleccionar Mes(es):", options=list(meses_opc.keys()), 
                                     format_func=lambda x: meses_opc[x])

        # --- LÓGICA DE FILTRADO ---
        df_f = df_actual.copy()
        
        if f_cli != "TODOS":
            df_f = df_f[df_f["CLIENTES"] == f_cli]
        
        if f_anios:
            df_f = df_f[df_f["ANIO"].isin(f_anios)]
            
        if f_meses:
            df_f = df_f[df_f["MES"].isin(f_meses)]
            
        st.divider()
        
        if not df_f.empty:
            st.write(f"Resultados encontrados: **{len(df_f)}** tickets.")
            
            # Selector con detalle
            df_f["ID_NUM"] = pd.to_numeric(df_f["ID_TICKET"], errors='coerce').fillna(0).astype(int)
            def etiqueta_cons(r):
                obs = str(r['CONSULTAS']).strip().replace('\n', ' ')[:40]
                return f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']} | Obs: {obs}..."

            op_c = df_f.apply(etiqueta_cons, axis=1).tolist()
            sel_c = st.selectbox("Selecciona Ticket para ver detalle:", op_c)
            
            id_c = int(sel_c.split(" | ")[0].replace("#", ""))
            dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
            
            # --- FICHA VISUAL ---
            with st.container(border=True):
                st.subheader(f"🔍 Ficha Ticket #{id_c}")
                v1, v2, v3 = st.columns(3)
                with v1:
                    st.text_input("Atendido por ", value=dc["CONSULTOR"], disabled=True)
                    st.text_input("Estado ", value=dc["ESTADO"], disabled=True)
                with v2:
                    st.text_input("Cliente ", value=dc["CLIENTES"], disabled=True)
                    st.text_input("Usuario Registrado ", value=dc["USUARIO"], disabled=True)
                with v3:
                    st.text_input("Fecha Consulta ", value=dc["FE_CONSULT"], disabled=True)
                    st.text_input("Tiempo (min) ", value=str(dc["TIEMPO_RES"]), disabled=True)
                
                st.text_area("Detalle Consulta ", value=dc["CONSULTAS"], disabled=True)
                st.text_area("Detalle Respuesta ", value=dc["RESPUESTAS"], disabled=True)
                
                # --- PDF PROFESIONAL GR CONSULTING ---
                pdf = FPDF()
                pdf.add_page()
                pdf.set_draw_color(200, 200, 200)
                pdf.set_font("Arial", 'B', 18)
                pdf.cell(0, 15, txt="GR Consulting - Servicios", ln=True, align='C')
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, txt=f"Ticket #{id_c}", ln=True, align='L')
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(50, 10, "ATENDIDO POR:", 1); pdf.cell(140, 10, str(dc['CONSULTOR']), 1, ln=True)
                pdf.cell(50, 10, "CLIENTE:", 1); pdf.cell(140, 10, str(dc['CLIENTES']), 1, ln=True)
                pdf.cell(50, 10, "USUARIO:", 1); pdf.cell(140, 10, str(dc['USUARIO']), 1, ln=True)
                pdf.cell(50, 10, "FECHA:", 1); pdf.cell(60, 10, str(dc['FE_CONSULT']), 1); pdf.cell(30, 10, "ESTADO:", 1); pdf.cell(50, 10, str(dc['ESTADO']), 1, ln=True)
                pdf.cell(50, 10, "TIEMPO (min):", 1); pdf.cell(140, 10, f"{dc['TIEMPO_RES']} minutos", 1, ln=True)
                pdf.ln(10)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 8, "DETALLE DE LA CONSULTA:", ln=True)
                pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 8, txt=str(dc["CONSULTAS"]), border=1)
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(0, 8, "RESPUESTA:", ln=True)
                pdf.set_font("Arial", size=10)
                pdf.multi_cell(0, 8, txt=str(dc["RESPUESTAS"]), border=1)
                st.download_button("📥 Descargar Reporte PDF", pdf.output(dest='S').encode('latin-1'), f"Reporte_Ticket_{id_c}.pdf")
        else:
            st.info("No se encontraron tickets para los filtros seleccionados.")

# ==========================================
# SECCIÓN: REPORTES
# ==========================================
else:
    st.header("📊 Resumen de Tiempos Acumulados")
    if not df_actual.empty:
        c_r = st.selectbox("Filtrar por Cliente:", sorted(df_actual["CLIENTES"].unique()))
        df_r = df_actual[df_actual["CLIENTES"] == c_r].copy()
        df_r["TIEMPO_RES"] = pd.to_numeric(df_r["TIEMPO_RES"], errors='coerce').fillna(0)
        res = df_r.groupby(["CLIENTES", "USUARIO", "MODULO"])["TIEMPO_RES"].sum().reset_index()
        st.table(res)
        tot = res["TIEMPO_RES"].sum()
        st.metric("Total Acumulado", f"{tot} min", f"{tot/60:.2f} hs")
