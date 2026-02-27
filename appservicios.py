import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, date
import getpass
import io
from fpdf import FPDF

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets", layout="wide")

st.title("📋 Sistema de Gestión de Consultas y Tickets")

# 1. Conexión
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- MEMORIA DE NAVEGACIÓN (Para que no salte de solapa) ---
if "tab_activa" not in st.session_state:
    st.session_state.tab_activa = 0

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

# Función para convertir CUALQUIER fecha a dd/mm/yyyy de forma segura
def normalizar_fecha(fecha_str):
    if not fecha_str or str(fecha_str).lower() == "nan": return ""
    try:
        # Intenta detectar automáticamente el formato (ISO, dd/mm/yyyy, etc)
        dt = pd.to_datetime(fecha_str, dayfirst=True, errors='coerce')
        return dt.strftime('%d/%m/%Y') if not pd.isna(dt) else str(fecha_str)
    except:
        return str(fecha_str)

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
except Exception as e:
    st.error(f"Error: {e}")
    df_actual = pd.DataFrame()

# NAVEGACIÓN POR TABS (Con persistencia de estado)
# Usamos un contenedor para que el cambio de solapa sea manual
tabs = ["➕ Nuevo Ticket", "✏️ Modificar Ticket", "🔍 Consultar Tickets", "📊 Reportes"]
tab_nueva, tab_mod, tab_cons, tab_rep = st.tabs(tabs)

# ==========================================
# SOLAPA 1: NUEVO TICKET
# ==========================================
with tab_nueva:
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_num = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_num.max()) + 1 if not ids_num.empty else 1
    else: proximo_id = 1

    with st.form("form_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Ticket N°: {proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            consultor = st.text_input("Consultor").upper()
            tipo_c = st.selectbox("Tipo", ["FUNCIONAL", "TÉCNICA", "COMERCIAL"])
            prioridad = st.select_slider("Prioridad", options=["BAJA", "MEDIA", "ALTA"])
            estado = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
        with c2:
            atencion = st.selectbox("Atención", ["TELEFÓNICA", "WASAPP", "MEET", "PROGRAMADA", "VISITA"])
            cli_opc = ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]
            cliente = st.selectbox("Cliente", cli_opc)
            usuario = st.text_input("Usuario *").upper()
            mod_opc = ["ACCESOS", "ADMINISTRACION", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PROGRAMA", "PRODUCCION","SERVIDOR", "WEB", "GERENCIAL", "RRHH", "IMPUESTOS", "SUCURSAL", "OTROS"]
            modulo = st.selectbox("Módulo", mod_opc)
        with c3:
            fe_c = st.date_input("Fecha Consulta", datetime.now())
            fe_r = st.date_input("Fecha Respuesta", datetime.now())
            t_res = st.number_input("Tiempo (min) *", min_value=0)

        det_c = st.text_area("Consulta *")
        det_r = st.text_area("Respuesta *")
        
        if st.form_submit_button("Guardar Registro"):
            if not (usuario.strip() and det_c.strip() and det_r.strip() and t_res > 0):
                st.error("Campos obligatorios incompletos.")
            else:
                nuevo_reg = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor, "TIPO_CONS": tipo_c,
                    "PRIORIDAD": prioridad, "ESTADO": estado, "ATENCION": atencion,
                    "CLIENTES": cliente, "USUARIO": usuario, "FE_CONSULT": fe_c.strftime('%d/%m/%Y'),
                    "FE_RTA": fe_r.strftime('%d/%m/%Y'), "MODULO": modulo, "CONSULTAS": det_c,
                    "RESPUESTAS": det_r, "TIEMPO_RES": t_res, "ONLINE": "NO",
                    "ANIO": int(fe_c.year), "MES": int(fe_c.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=pd.concat([obtener_datos(), nuevo_reg], ignore_index=True))
                st.balloons()
                st.rerun()

# ==========================================
# SOLAPA 2: MODIFICAR
# ==========================================
with tab_mod:
    if not df_actual.empty:
        df_actual["ESTADO_UP"] = df_actual["ESTADO"].str.upper().str.strip()
        pend = df_actual[df_actual["ESTADO_UP"].isin(["ABIERTO", "EN PROCESO"])].copy()
        
        if not pend.empty:
            busq_m = st.text_input("🔍 Filtrar Cliente p/ Editar:", key="busq_mod")
            if busq_m: pend = pend[pend["CLIENTES"].str.contains(busq_m, case=False)]
            
            pend["ID_NUM"] = pd.to_numeric(pend["ID_TICKET"], errors='coerce')
            pend = pend.sort_values(by=["CLIENTES", "ID_NUM"])
            
            op_m = pend.apply(lambda r: f"{r['CLIENTES']} | #{int(r['ID_NUM'])} | {r['USUARIO']}", axis=1).tolist()
            sel_m = st.selectbox("Selecciona Ticket:", op_m)
            id_m = int(sel_m.split(" | #")[1].split(" | ")[0])
            idx_m = df_actual.index[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_m].tolist()[0]
            dm = df_actual.loc[idx_m]

            with st.form("form_edit"):
                st.warning(f"🕒 Modificado: {dm['ULTIMA_MODIF']} por {dm['MODIFICADO_POR']}")
                c1, c2 = st.columns(2)
                with c1:
                    est_m = st.selectbox("Nuevo Estado", ["ABIERTO", "EN PROCESO", "CERRADO"])
                    t_m = st.number_input("Tiempo (min)", value=int(float(dm["TIEMPO_RES"] if dm["TIEMPO_RES"]!="" else 0)))
                with c2:
                    try: fr_dt = pd.to_datetime(dm["FE_RTA"], dayfirst=True)
                    except: fr_dt = datetime.now()
                    fe_r_m = st.date_input("F. Respuesta", fr_dt)
                
                rta_m = st.text_area("Respuesta", value=dm["RESPUESTAS"])
                if st.form_submit_button("Actualizar"):
                    df_actual.at[idx_m, "ESTADO"] = est_m
                    df_actual.at[idx_m, "FE_RTA"] = fe_r_m.strftime('%d/%m/%Y')
                    df_actual.at[idx_m, "TIEMPO_RES"] = t_m
                    df_actual.at[idx_m, "RESPUESTAS"] = rta_m
                    df_actual.at[idx_m, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    df_actual.at[idx_m, "MODIFICADO_POR"] = usuario_pc
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual.drop(columns=["ESTADO_UP", "ID_NUM"], errors="ignore"))
                    st.rerun()

# ==========================================
# SOLAPA 3: CONSULTAR Y LIMPIEZA DE BASE
# ==========================================
with tab_cons:
    st.header("🔍 Consulta General")
    
    # BOTÓN DE MANTENIMIENTO: Estandariza TODA la base de datos
    if st.button("🧹 Estandarizar Formatos Históricos (Mayúsculas y Fechas)"):
        with st.spinner("Limpiando base de datos..."):
            df_limpio = df_actual.copy()
            text_cols = ["CONSULTOR", "TIPO_CONS", "PRIORIDAD", "ESTADO", "ATENCION", "CLIENTES", "USUARIO", "MODULO"]
            date_cols = ["FE_CONSULT", "FE_RTA"]
            
            for col in text_cols:
                if col in df_limpio.columns:
                    df_limpio[col] = df_limpio[col].astype(str).str.upper().str.strip().replace("NAN", "")
            
            for col in date_cols:
                if col in df_limpio.columns:
                    df_limpio[col] = df_limpio[col].apply(normalizar_fecha)
            
            # Recalcular ANIO y MES
            df_limpio["FECHA_OBJ"] = pd.to_datetime(df_limpio["FE_CONSULT"], dayfirst=True, errors='coerce')
            df_limpio["ANIO"] = df_limpio["FECHA_OBJ"].dt.year.fillna(0).astype(int)
            df_limpio["MES"] = df_limpio["FECHA_OBJ"].dt.month.fillna(0).astype(int)
            df_limpio = df_limpio.drop(columns=["FECHA_OBJ"])

            conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_limpio)
            st.success("✅ Base de datos estandarizada. Todos los campos ahora están en MAYÚSCULAS y las fechas en DD/MM/AAAA.")
            st.rerun()

    if not df_actual.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            lista_c = ["TODOS"] + sorted(list(df_actual["CLIENTES"].unique()))
            f_cli = st.selectbox("Cliente:", lista_c)
        with c2:
            f_d = st.date_input("Desde:", value=date(2020, 1, 1))
        with c3:
            f_h = st.date_input("Hasta:", value=datetime.now().date())

        # Filtrado Inteligente (Detecta múltiples formatos de fecha históricos)
        df_f = df_actual.copy()
        if f_cli != "TODOS":
            df_f = df_f[df_f["CLIENTES"] == f_cli]
        
        # Convertimos para comparar sin importar el formato en la celda
        df_f['FECHA_DT'] = pd.to_datetime(df_f['FE_CONSULT'], dayfirst=True, errors='coerce').dt.date
        df_f = df_f.dropna(subset=['FECHA_DT'])
        df_f = df_f[(df_f['FECHA_DT'] >= f_d) & (df_f['FECHA_DT'] <= f_h)]
        
        st.write(f"Resultados: **{len(df_f)}** tickets.")
        
        if not df_f.empty:
            df_f["ID_NUM"] = pd.to_numeric(df_f["ID_TICKET"], errors='coerce')
            df_f = df_f.sort_values(by=["CLIENTES", "ID_NUM"])
            op_c = df_f.apply(lambda r: f"#{int(r['ID_NUM'])} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1).tolist()
            sel_c = st.selectbox("Ver Ficha Detallada:", op_c)
            
            id_c = int(sel_c.split(" | ")[0].replace("#", ""))
            dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
            
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
                
                pdf = FPDF()
                pdf.add_page(); pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt=f"TICKET #{id_c}", ln=True, align='C')
                st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Ticket_{id_c}.pdf")

# ==========================================
# SOLAPA 4: REPORTES
# ==========================================
with tab_rep:
    st.header("📊 Reportes")
    if not df_actual.empty:
        c_r = st.selectbox("Cliente:", sorted(df_actual["CLIENTES"].unique()))
        df_r = df_actual[df_actual["CLIENTES"] == c_r].copy()
        df_r["TIEMPO_RES"] = pd.to_numeric(df_r["TIEMPO_RES"], errors='coerce').fillna(0)
        res = df_r.groupby(["CLIENTES", "USUARIO", "MODULO"])["TIEMPO_RES"].sum().reset_index()
        st.table(res)
        t_m = res["TIEMPO_RES"].sum()
        st.metric("Total", f"{t_m} min", f"{t_m/60:.2f} hs")
