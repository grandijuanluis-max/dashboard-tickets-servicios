import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import io
from fpdf import FPDF

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets", layout="wide")

# 1. Conexión y Carga de Datos
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

def formato_historial(valor):
    v = str(valor).strip()
    return v if v and v.lower() != "nan" else "Sin registro"

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error de conexión: {e}")
    df_actual = pd.DataFrame()

# ==========================================
# NAVEGACIÓN ESTABLE (Sidebar)
# ==========================================
# Cambiamos pestañas por radio en el sidebar para evitar saltos accidentales
st.sidebar.title("Navegación")
menu = st.sidebar.radio("Ir a:", ["➕ Nuevo Ticket", "✏️ Modificar Ticket", "🔍 Consultar Tickets", "📊 Reportes"])

# ==========================================
# OPCIÓN: NUEVO TICKET
# ==========================================
if menu == "➕ Nuevo Ticket":
    st.header("➕ Carga de Nuevo Ticket")
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_num = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_num.max()) + 1 if not ids_num.empty else 1
    else: proximo_id = 1

    with st.form("nuevo_form", clear_on_submit=True):
        st.subheader(f"Ticket N°: {proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo", ["Funcional", "Técnica", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])
        with c2:
            atencion = st.selectbox("Atención", ["Telefónica", "Wasapp", "Meet", "Programada", "Visita"])
            clientes_lista = ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]
            cliente_sel = st.selectbox("Cliente", clientes_lista)
            usuario_n = st.text_input("Usuario *")
            modulo_n = st.selectbox("Módulo", ["Accesos", "Contabilidad", "Ventas", "Logistica", "Produccion", "Otros"])
        with c3:
            f_c = st.date_input("Fecha Consulta", datetime.now())
            f_r = st.date_input("Fecha Respuesta", datetime.now())
            t_r = st.number_input("Tiempo (min) *", min_value=0)

        det_c = st.text_area("Consulta *")
        det_r = st.text_area("Respuesta *")
        
        if st.form_submit_button("Guardar Registro"):
            if not (usuario_n.strip() and det_c.strip() and det_r.strip() and t_r > 0):
                st.error("Campos obligatorios incompletos.")
            else:
                nuevo_reg = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor.upper(), "TIPO_CONS": tipo_cons.upper(),
                    "PRIORIDAD": prioridad.upper(), "ESTADO": estado.upper(), "ATENCION": atencion.upper(),
                    "CLIENTES": cliente_sel.upper(), "USUARIO": usuario_n.upper(), 
                    "FE_CONSULT": f_c.strftime('%d/%m/%Y'), "FE_RTA": f_r.strftime('%d/%m/%Y'),
                    "MODULO": modulo_n.upper(), "CONSULTAS": det_c, "RESPUESTAS": det_r,
                    "TIEMPO_RES": t_r, "ONLINE": "NO", "ANIO": int(f_c.year), "MES": int(f_c.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                df_f = pd.concat([obtener_datos(), nuevo_reg], ignore_index=True)
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_f)
                st.balloons()
                st.rerun()

# ==========================================
# OPCIÓN: MODIFICAR TICKET
# ==========================================
elif menu == "✏️ Modificar Ticket":
    st.header("✏️ Modificar Ticket Pendiente")
    if not df_actual.empty:
        pendientes = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not pendientes.empty:
            busq = st.text_input("🔍 Filtrar Cliente:", key="mod_busq")
            if busq: pendientes = pendientes[pendientes["CLIENTES"].str.contains(busq, case=False)]
            
            op_e = pendientes.apply(lambda r: f"{r['CLIENTES']} | #{int(float(r['ID_TICKET']))} | {r['USUARIO']}", axis=1).tolist()
            sel_e = st.selectbox("Selecciona Ticket:", op_e)
            id_e = int(sel_e.split(" | #")[1].split(" | ")[0])
            idx_e = df_actual.index[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_e].tolist()[0]
            de = df_actual.loc[idx_e]

            with st.form("edit_form"):
                st.warning(f"🕒 Historial: {formato_historial(de['ULTIMA_MODIF'])} por {formato_historial(de['MODIFICADO_POR'])}")
                ce1, ce2 = st.columns(2)
                with ce1:
                    est_e = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=0)
                    t_e = st.number_input("Tiempo (min)", value=int(float(de["TIEMPO_RES"] if de["TIEMPO_RES"]!="" else 0)))
                with ce2:
                    try: fr_dt = datetime.strptime(str(de["FE_RTA"]), '%d/%m/%Y')
                    except: fr_dt = datetime.now()
                    fe_r_e = st.date_input("F. Respuesta", fr_dt)
                
                rta_e = st.text_area("Nueva Respuesta", value=de["RESPUESTAS"])
                if st.form_submit_button("Actualizar"):
                    df_actual.at[idx_e, "ESTADO"] = est_e.upper()
                    df_actual.at[idx_e, "FE_RTA"] = fe_r_e.strftime('%d/%m/%Y')
                    df_actual.at[idx_e, "TIEMPO_RES"] = t_e
                    df_actual.at[idx_e, "RESPUESTAS"] = rta_e
                    df_actual.at[idx_e, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    df_actual.at[idx_e, "MODIFICADO_POR"] = usuario_pc
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                    st.rerun()

# ==========================================
# OPCIÓN: CONSULTAR TICKETS (SIN ERRORES)
# ==========================================
elif menu == "🔍 Consultar Tickets":
    st.header("🔍 Consulta General")
    if not df_actual.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            lista_cli = ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique()))
            f_cli = st.selectbox("Cliente:", lista_cli)
        with c2:
            f_d = st.date_input("Desde:", value=date(2025, 1, 1))
        with c3:
            f_h = st.date_input("Hasta:", value=datetime.now().date())

        # Lógica de Filtrado Corregida
        df_f = df_actual.copy()
        if f_cli != "TODOS":
            df_f = df_f[df_f["CLIENTES"] == f_cli]
        
        # Solución al TypeError: Aseguramos que la columna sea tipo 'date'
        df_f['FECHA_DT'] = pd.to_datetime(df_f['FE_CONSULT'], format='%d/%m/%Y', errors='coerce').dt.date
        df_f = df_f.dropna(subset=['FECHA_DT'])
        df_f = df_f[(df_f['FECHA_DT'] >= f_d) & (df_f['FECHA_DT'] <= f_h)]
        
        if not df_f.empty:
            st.write(f"Resultados: {len(df_f)} tickets.")
            op_c = df_f.apply(lambda r: f"#{int(float(r['ID_TICKET']))} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1).tolist()
            sel_c = st.selectbox("Ver Ficha Detallada:", op_c)
            
            id_c = int(sel_c.split(" | ")[0].replace("#", ""))
            dc = df_f[pd.to_numeric(df_f["ID_TICKET"], errors='coerce') == id_c].iloc[0]
            
            # Ficha de Solo Lectura
            with st.container(border=True):
                st.subheader(f"Ficha Ticket #{id_c}")
                v1, v2 = st.columns(2)
                with v1:
                    st.text_input("Consultor ", value=dc["CONSULTOR"], disabled=True)
                    st.text_input("Usuario ", value=dc["USUARIO"], disabled=True)
                    st.text_area("Consulta ", value=dc["CONSULTAS"], disabled=True)
                with v2:
                    st.text_input("Estado ", value=dc["ESTADO"], disabled=True)
                    st.text_input("Tiempo (min) ", value=dc["TIEMPO_RES"], disabled=True)
                    st.text_area("Respuesta ", value=dc["RESPUESTAS"], disabled=True)
                
                # Botones Exportar
                pdf = FPDF()
                pdf.add_page(); pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt=f"TICKET #{id_cons if 'id_cons' in locals() else id_c}", ln=True, align='C')
                st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")
        else:
            st.info("No hay tickets en ese rango o cliente.")

# ==========================================
# OPCIÓN: REPORTES
# ==========================================
else:
    st.header("📊 Reportes Mensuales")
    if not df_actual.empty:
        c_sel = st.selectbox("Seleccionar Cliente:", sorted(df_actual["CLIENTES"].unique()))
        df_r = df_actual[df_actual["CLIENTES"] == c_sel].copy()
        df_r["TIEMPO_RES"] = pd.to_numeric(df_r["TIEMPO_RES"], errors='coerce').fillna(0)
        
        res = df_r.groupby(["CLIENTES", "USUARIO", "MODULO"])["TIEMPO_RES"].sum().reset_index()
        st.table(res)
        
        t_m = res["TIEMPO_RES"].sum()
        st.metric("Total Acumulado", f"{t_m} min", f"{t_m/60:.2f} horas")
