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

def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = df.columns.str.strip()
    return df.fillna("")

usuario_pc = getpass.getuser().upper()

try:
    df_actual = obtener_datos()
    if not df_actual.empty:
        # Aseguramos tipos numéricos para cálculos y filtros
        df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
        df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)
        df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    df_actual = pd.DataFrame()

# ==========================================
# MENÚ DE NAVEGACIÓN ESTABLE
# ==========================================
st.title("📋 Sistema de Gestión de Consultas y Tickets")
cols = st.columns(4)
if cols[0].button("➕ NUEVO TICKET", use_container_width=True): st.session_state.menu_activo = "➕ NUEVO"
if cols[1].button("✏️ MODIFICAR TICKET", use_container_width=True): st.session_state.menu_activo = "✏️ MODIFICAR"
if cols[2].button("🔍 CONSULTAR TICKETS", use_container_width=True): st.session_state.menu_activo = "🔍 CONSULTAR"
if cols[3].button("📊 REPORTES", use_container_width=True): st.session_state.menu_activo = "📊 REPORTES"

st.markdown(f"📍 Estás en: **{st.session_state.menu_activo}**")
st.divider()

# --- Lógica de Secciones ---
if st.session_state.menu_activo == "➕ NUEVO":
    # (Se mantiene código previo de carga de tickets...)
    st.subheader("Carga de Nuevo Registro")
    # ... [lógica omitida para brevedad pero funcional en tu archivo] ...

elif st.session_state.menu_activo == "✏️ MODIFICAR":
    # (Se mantiene código previo de modificación con edición de detalle de consulta...)
    st.subheader("Edición de Tickets Pendientes")
    # ... [lógica omitida para brevedad pero funcional en tu archivo] ...

elif st.session_state.menu_activo == "🔍 CONSULTAR":
    # (Se mantiene código previo de consulta individual y PDF de GR Consulting...)
    st.subheader("Búsqueda Histórica de Tickets")
    # ... [lógica omitida para brevedad pero funcional en tu archivo] ...

# ==========================================
# SECCIÓN: REPORTES ANALÍTICOS (Nueva Mejora)
# ==========================================
else:
    st.header("📊 Reportes Operativos y Analíticos")
    if not df_actual.empty:
        st.info("💡 Usa los filtros de abajo para cruzar datos. Si no seleccionas nada en un filtro, se tomarán 'TODOS'.")
        
        # --- FILTROS MULTIDIMENSIONALES ---
        f1, f2, f3 = st.columns(3)
        with f1:
            f_cli = st.multiselect("Clientes:", options=sorted(df_actual["CLIENTES"].unique()))
            f_con = st.multiselect("Consultores:", options=sorted(df_actual["CONSULTOR"].unique()))
        with f2:
            f_mod = st.multiselect("Módulos:", options=sorted(df_actual["MODULO"].unique()))
            f_ani = st.multiselect("Años:", options=sorted(df_actual["ANIO"].unique(), reverse=True))
        with f3:
            meses_nombres = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
            f_mes = st.multiselect("Meses:", options=sorted(df_actual["MES"].unique()), format_func=lambda x: meses_nombres.get(x, x))

        # --- APLICACIÓN DE FILTROS ---
        df_rep = df_actual.copy()
        if f_cli: df_rep = df_rep[df_rep["CLIENTES"].isin(f_cli)]
        if f_mod: df_rep = df_rep[df_rep["MODULO"].isin(f_mod)]
        if f_con: df_rep = df_rep[df_rep["CONSULTOR"].isin(f_con)]
        if f_ani: df_rep = df_rep[df_rep["ANIO"].isin(f_ani)]
        if f_mes: df_rep = df_rep[df_rep["MES"].isin(f_mes)]

        if not df_rep.empty:
            # --- CÁLCULOS Y MÉTRICAS ---
            total_min = df_rep["TIEMPO_RES"].sum()
            total_hs = total_min / 60
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Tickets Analizados", len(df_rep))
            m2.metric("Total Minutos", f"{total_min:,.0f} min")
            m3.metric("Total Horas", f"{total_hs:,.2f} hs")
            
            st.divider()
            
            # --- TABLA DE ANÁLISIS TIPO TABLA DINÁMICA ---
            st.subheader("Análisis de Tiempos por Categoría")
            
            # Agrupamos por todas las dimensiones solicitadas
            resumen_tabla = df_rep.groupby(["CLIENTES", "MODULO", "CONSULTOR", "ANIO", "MES"])["TIEMPO_RES"].sum().reset_index()
            
            # Añadimos columna de horas al reporte
            resumen_tabla["TIEMPO_HS"] = (resumen_tabla["TIEMPO_RES"] / 60).round(2)
            
            # Ordenamos para mejor lectura
            resumen_tabla = resumen_tabla.sort_values(by=["CLIENTES", "TIEMPO_RES"], ascending=[True, False])
            
            st.dataframe(resumen_tabla, use_container_width=True, hide_index=True)

            # --- EXPORTACIÓN DE REPORTE ANALÍTICO ---
            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                buf_xlsx = io.BytesIO()
                with pd.ExcelWriter(buf_xlsx, engine='openpyxl') as writer:
                    resumen_tabla.to_excel(writer, index=False, sheet_name='Analisis_Tiempos')
                st.download_button("📥 Descargar Tabla en Excel", buf_xlsx.getvalue(), "Reporte_Analitico.xlsx")
            
            with col_ex2:
                # PDF Resumen Pro (GR Consulting)
                pdf_r = FPDF()
                pdf_r.add_page(); pdf_r.set_font("Arial", 'B', 14)
                pdf_r.cell(0, 10, "GR Consulting - Reporte Analítico de Tiempos", ln=True, align='C')
                pdf_r.set_font("Arial", size=10)
                pdf_r.ln(5)
                # Cabecera simple
                pdf_r.cell(40, 8, "Cliente", 1); pdf_r.cell(40, 8, "Modulo", 1); pdf_r.cell(40, 8, "Consultor", 1); pdf_r.cell(30, 8, "Minutos", 1); pdf_r.cell(30, 8, "Horas", 1); pdf_r.ln()
                for i, row in resumen_tabla.head(30).iterrows(): # Limitamos filas en PDF por espacio
                    pdf_r.cell(40, 8, str(row['CLIENTES'])[:18], 1); pdf_r.cell(40, 8, str(row['MODULO'])[:18], 1)
                    pdf_r.cell(40, 8, str(row['CONSULTOR'])[:18], 1); pdf_r.cell(30, 8, str(row['TIEMPO_RES']), 1)
                    pdf_r.cell(30, 8, str(row['TIEMPO_HS']), 1); pdf_r.ln()
                
                pdf_r.ln(5); pdf_r.set_font("Arial", 'B', 11)
                pdf_r.cell(0, 10, f"TOTAL GENERAL: {total_min} min / {total_hs:.2f} hs", ln=True)
                st.download_button("📥 Descargar Resumen PDF", pdf_r.output(dest='S').encode('latin-1'), "Reporte_Analitico.pdf")
        else:
            st.warning("No hay datos para la combinación de filtros seleccionada.")
