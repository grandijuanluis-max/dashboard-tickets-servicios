import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import getpass
import io
from fpdf import FPDF

# Configuración de la página
st.set_page_config(page_title="Gestión de Tickets", layout="wide")

st.title("📋 Sistema de Gestión de Consultas y Tickets")

# 1. Configuración de la URL y Conexión
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "input_busqueda" not in st.session_state:
    st.session_state.input_busqueda = ""

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
    st.error(f"Error al conectar con la base de datos: {e}")
    df_actual = pd.DataFrame()

# DEFINICIÓN DE LAS 4 PESTAÑAS
tab1, tab2, tab3, tab4 = st.tabs(["➕ Nuevo", "✏️ Modificar", "🔍 Consultar", "📊 Reportes"])

# ==========================================
# TAB 1: CARGA DE NUEVO TICKET
# ==========================================
with tab1:
    if not df_actual.empty and "ID_TICKET" in df_actual.columns:
        ids_num = pd.to_numeric(df_actual["ID_TICKET"], errors='coerce').dropna()
        proximo_id = int(ids_num.max()) + 1 if not ids_num.empty else 1
    else: proximo_id = 1

    with st.form("nuevo_ticket_form", clear_on_submit=True):
        st.subheader(f"Cargando Ticket N°: {proximo_id}")
        col1, col2, col3 = st.columns(3)
        with col1:
            consultor = st.text_input("Consultor")
            tipo_cons = st.selectbox("Tipo de Consulta", ["Funcional", "Técnica", "Comercial"])
            prioridad = st.select_slider("Prioridad", options=["Baja", "Media", "Alta"])
            estado = st.selectbox("Estado", ["Abierto", "En Proceso", "Cerrado"])
        with col2:
            atencion = st.selectbox("Atención", ["Telefónica", "Wasapp", "Meet", "Programada", "Visita"])
            clientes_opc = ["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GR_CONSULTING"]
            clientes = st.selectbox("Clientes", clientes_opc)
            usuario = st.text_input("Usuario *")
            modulo_opc = ["Accesos", "Administracion", "Contabilidad", "Compras", "Ventas", "Logistica", "Eccomerce", "Mails", "Programa", "Produccion","Servidor", "Web", "Gerencial", "RRHH", "Impuestos", "Sucursal", "Otros"]
            modulo = st.selectbox("Módulo", modulo_opc)
        with col3:
            fe_consult = st.date_input("Fecha Consulta", datetime.now())
            fe_rta = st.date_input("Fecha Respuesta", datetime.now())
            tiempo_res = st.number_input("Tiempo Respuesta (min) *", min_value=0)

        consultas = st.text_area("Detalle de la Consulta *")
        respuestas = st.text_area("Detalle de la Respuesta *")
        if st.form_submit_button("Guardar Registro"):
            if not (usuario.strip() and consultas.strip() and respuestas.strip() and tiempo_res > 0):
                st.error("Faltan campos obligatorios.")
            else:
                nuevo = pd.DataFrame([{
                    "ID_TICKET": proximo_id, "CONSULTOR": consultor.upper(), "TIPO_CONS": tipo_cons.upper(),
                    "PRIORIDAD": prioridad.upper(), "ESTADO": estado.upper(), "ATENCION": atencion.upper(),
                    "CLIENTES": clientes.upper(), "USUARIO": usuario.upper(), "FE_CONSULT": fe_consult.strftime('%d/%m/%Y'),
                    "FE_RTA": fe_rta.strftime('%d/%m/%Y'), "MODULO": modulo.upper(), "CONSULTAS": consultas,
                    "RESPUESTAS": respuestas, "TIEMPO_RES": tiempo_res, "ONLINE": "NO",
                    "ANIO": int(fe_consult.year), "MES": int(fe_consult.month),
                    "ULTIMA_MODIF": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), "MODIFICADO_POR": usuario_pc
                }])
                df_final = pd.concat([obtener_datos(), nuevo], ignore_index=True)
                conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_final)
                st.balloons()
                st.rerun()

# ==========================================
# TAB 2: MODIFICAR TICKET
# ==========================================
with tab2:
    if not df_actual.empty:
        pendientes = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
        if not pendientes.empty:
            busqueda = st.text_input("🔍 Buscar Cliente:", key="input_busqueda")
            if busqueda: pendientes = pendientes[pendientes["CLIENTES"].str.contains(busqueda, case=False)]
            pendientes["ID_NUM"] = pd.to_numeric(pendientes["ID_TICKET"], errors='coerce')
            pendientes = pendientes.sort_values(by=["CLIENTES", "ID_NUM"])
            
            opciones = pendientes.apply(lambda r: f"{r['CLIENTES']} | #{int(r['ID_NUM'])} | {r['USUARIO']}", axis=1).tolist()
            seleccion = st.selectbox("Selecciona para editar:", opciones)
            id_sel = int(seleccion.split(" | #")[1].split(" | ")[0])
            fila_idx = df_actual.index[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_sel].tolist()[0]
            d = df_actual.loc[fila_idx]

            with st.form("form_edicion"):
                st.warning(f"🕒 Modificado: {formato_historial(d['ULTIMA_MODIF'])} por {formato_historial(d['MODIFICADO_POR'])}")
                ce1, ce2, ce3 = st.columns(3)
                with ce1:
                    nuevo_estado = st.selectbox("Estado", ["ABIERTO", "EN PROCESO", "CERRADO"], index=["ABIERTO", "EN PROCESO", "CERRADO"].index(d["ESTADO"].upper()) if d["ESTADO"].upper() in ["ABIERTO", "EN PROCESO", "CERRADO"] else 0)
                with ce3:
                    try: fr_dt = datetime.strptime(str(d["FE_RTA"]), '%d/%m/%Y')
                    except: fr_dt = datetime.now()
                    n_fe_rta = st.date_input("Fecha Rta", fr_dt)
                    n_tiempo = st.number_input("Tiempo *", value=int(float(d["TIEMPO_RES"] if d["TIEMPO_RES"]!="" else 0)))
                n_rta = st.text_area("Respuesta *", value=d["RESPUESTAS"])
                if st.form_submit_button("Guardar"):
                    df_actual.at[fila_idx, "ESTADO"] = nuevo_estado.upper()
                    df_actual.at[fila_idx, "FE_RTA"] = n_fe_rta.strftime('%d/%m/%Y')
                    df_actual.at[fila_idx, "TIEMPO_RES"] = n_tiempo
                    df_actual.at[fila_idx, "RESPUESTAS"] = n_rta
                    df_actual.at[fila_idx, "ULTIMA_MODIF"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    df_actual.at[fila_idx, "MODIFICADO_POR"] = usuario_pc
                    conn.update(spreadsheet=url, worksheet="BD_Dashboard_Servicios", data=df_actual)
                    st.rerun()

# ==========================================
# TAB 3: CONSULTAR Y EXPORTAR TICKET INDIVIDUAL
# ==========================================
with tab3:
    st.subheader("🔍 Consulta Individual")
    if not df_actual.empty:
        id_query = st.selectbox("Selecciona Ticket:", df_actual.apply(lambda r: f"#{int(float(r['ID_TICKET']))} | {r['CLIENTES']}", axis=1))
        id_cons = int(id_query.split(" | ")[0].replace("#", ""))
        dc = df_actual[pd.to_numeric(df_actual["ID_TICKET"], errors='coerce') == id_cons].iloc[0]
        
        st.info(f"Ficha del Ticket #{id_cons}")
        st.write(dc.to_frame().T)

        col_ex1, col_ex2 = st.columns(2)
        
        # --- EXPORTAR TICKET A EXCEL ---
        with col_ex1:
            buffer_xlsx = io.BytesIO()
            with pd.ExcelWriter(buffer_xlsx, engine='openpyxl') as writer:
                dc.to_frame().T.to_excel(writer, index=False, sheet_name='Ticket')
            st.download_button(label="📥 Exportar Ticket a Excel", data=buffer_xlsx.getvalue(), file_name=f"Ticket_{id_cons}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # --- EXPORTAR TICKET A PDF ---
        with col_ex2:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt=f"FICHA DE TICKET #{id_cons}", ln=True, align='C')
            pdf.set_font("Arial", size=12)
            pdf.ln(10)
            for col in dc.index:
                pdf.multi_cell(0, 10, txt=f"{col}: {dc[col]}")
            pdf_out = pdf.output(dest='S').encode('latin-1')
            st.download_button(label="📥 Exportar Ticket a PDF", data=pdf_out, file_name=f"Ticket_{id_cons}.pdf", mime="application/pdf")

# ==========================================
# TAB 4: REPORTES POR CLIENTE
# ==========================================
with tab4:
    st.subheader("📊 Resumen de Tiempos por Cliente")
    if not df_actual.empty:
        cli_sel = st.selectbox("Selecciona Cliente para el Resumen:", sorted(df_actual["CLIENTES"].unique()))
        
        # Filtrar datos del cliente
        df_cli = df_actual[df_actual["CLIENTES"] == cli_sel].copy()
        df_cli["TIEMPO_RES"] = pd.to_numeric(df_cli["TIEMPO_RES"], errors='coerce').fillna(0)
        
        # Crear Resumen: Nombre Cliente, Usuario, Modulo, Tiempo Total
        resumen = df_cli.groupby(["CLIENTES", "USUARIO", "MODULO"])["TIEMPO_RES"].sum().reset_index()
        st.dataframe(resumen, use_container_width=True)
        
        # Cálculos Finales
        total_minutos = resumen["TIEMPO_RES"].sum()
        total_horas = total_minutos / 60
        
        st.metric("Total Tiempo (Minutos)", f"{total_minutos} min")
        st.metric("Total Tiempo (Horas)", f"{total_horas:.2f} hs")
        
        # LaTeX para la fórmula solicitada
        st.latex(r"Total\ Horas = \frac{\sum Tiempo\ Res}{60}")

        # Botones de Exportación del Resumen
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            # Excel Resumen con totales al final
            df_final_res = resumen.append({"CLIENTES": "TOTAL", "TIEMPO_RES": total_minutos}, ignore_index=True)
            df_final_res["HORAS_TOTAL"] = df_final_res["TIEMPO_RES"] / 60
            
            buffer_res = io.BytesIO()
            with pd.ExcelWriter(buffer_res, engine='openpyxl') as writer:
                df_final_res.to_excel(writer, index=False, sheet_name='Resumen')
            st.download_button(label="📥 Descargar Resumen Excel", data=buffer_res.getvalue(), file_name=f"Resumen_{cli_sel}.xlsx")

        with col_res2:
            # PDF Resumen
            pdf_res = FPDF()
            pdf_res.add_page()
            pdf_res.set_font("Arial", 'B', 14)
            pdf_res.cell(200, 10, txt=f"RESUMEN DE TIEMPOS - CLIENTE: {cli_sel}", ln=True, align='C')
            pdf_res.ln(10)
            pdf_res.set_font("Arial", size=10)
            # Cabeceras
            pdf_res.cell(50, 10, "Usuario", 1)
            pdf_res.cell(50, 10, "Modulo", 1)
            pdf_res.cell(40, 10, "Tiempo (Min)", 1)
            pdf_res.ln()
            for i, row in resumen.iterrows():
                pdf_res.cell(50, 10, str(row['USUARIO']), 1)
                pdf_res.cell(50, 10, str(row['MODULO']), 1)
                pdf_res.cell(40, 10, str(row['TIEMPO_RES']), 1)
                pdf_res.ln()
            pdf_res.ln(5)
            pdf_res.set_font("Arial", 'B', 12)
            pdf_res.cell(0, 10, txt=f"TOTAL MINUTOS: {total_minutos}", ln=True)
            pdf_res.cell(0, 10, txt=f"TOTAL HORAS: {total_horas:.2f}", ln=True)
            
            pdf_res_out = pdf_res.output(dest='S').encode('latin-1')
            st.download_button(label="📥 Descargar Resumen PDF", data=pdf_res_out, file_name=f"Resumen_{cli_sel}.pdf", mime="application/pdf")
