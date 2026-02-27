import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import getpass
import platform 
import io
from fpdf import FPDF

# 1. CONFIGURACIÓN
st.set_page_config(page_title="KPI Dashboard - GR Consulting", layout="wide")
url = "https://docs.google.com/spreadsheets/d/1VawCQZ7dsadzZz_BoGyZwX_8he9RqvmAESHvd_B1pj0/"
conn = st.connection("gsheets", type=GSheetsConnection)

if "menu_activo" not in st.session_state:
    st.session_state.menu_activo = "➕ NUEVO"

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
id_maquina_actual = f"{platform.node()}\\{getpass.getuser()}".upper()

# --- FUNCIONES DE DATOS ---
def obtener_datos():
    df = conn.read(spreadsheet=url, worksheet="BD_Dashboard_Servicios", ttl=0)
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df.fillna("")

def obtener_config():
    try:
        df = conn.read(spreadsheet=url, worksheet="Config_Consultores", ttl=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        df["VALOR_HORA"] = pd.to_numeric(df["VALOR_HORA"], errors='coerce').fillna(0)
        df["DISPONIBLE"] = pd.to_numeric(df["DISPONIBLE"], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

df_actual = obtener_datos()
df_config = obtener_config()

# Normalización
if not df_actual.empty:
    df_actual["TIEMPO_RES"] = pd.to_numeric(df_actual["TIEMPO_RES"], errors='coerce').fillna(0)
    df_actual["ANIO"] = pd.to_numeric(df_actual["ANIO"], errors='coerce').fillna(0).astype(int)
    df_actual["MES"] = pd.to_numeric(df_actual["MES"], errors='coerce').fillna(0).astype(int)

# ==========================================
# MENÚ PRINCIPAL
# ==========================================
st.title("📊 GR Consulting - Business Intelligence")
cols = st.columns(5)
btns = ["➕ NUEVO", "✏️ MODIFICAR", "🔍 CONSULTAR", "📊 REPORTES", "📈 DASHBOARDS"]
for i, b in enumerate(btns):
    if cols[i].button(b, use_container_width=True): st.session_state.menu_activo = b

# Filtros Globales (Afectan a Reportes y Dashboards)
with st.sidebar:
    st.header("🔍 Filtros Maestros")
    f_cli = st.multiselect("Clientes:", sorted(df_actual["CLIENTES"].unique()) if not df_actual.empty else [])
    f_ani = st.multiselect("Años:", sorted(df_actual["ANIO"].unique(), reverse=True) if not df_actual.empty else [])
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

st.divider()

# --- LÓGICA DE FILTRADO ---
df_f = df_actual.copy()
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# ==========================================
# SECCIÓN: DASHBOARDS (LOS 3 GRUPOS)
# ==========================================
if st.session_state.menu_activo == "📈 DASHBOARDS":
    if df_f.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        t1, t2, t3 = st.tabs(["📋 DB1: OPERATIVO", "⚡ DB2: PERFORMANCE", "💰 DB3: FINANCIERO"])
        
        with t1:
            st.header("Metas de Volumen y Tiempo")
            # 1-8. VOLUMEN
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Tickets", len(df_f))
            c2.metric("T. Promedio (min)", f"{df_f['TIEMPO_RES'].mean():.1f}")
            c3.metric("Total Horas", f"{df_f['TIEMPO_RES'].sum()/60:,.2f}")
            
            cerrados = len(df_f[df_f["ESTADO"].str.upper() == "CERRADO"])
            c4.metric("% Eficacia (Cerrados)", f"{(cerrados/len(df_f)*100) if len(df_f)>0 else 0:.1f}%")

            col_a, col_b = st.columns(2)
            col_a.subheader("Tickets por Cliente")
            col_a.bar_chart(df_f["CLIENTES"].value_counts())
            
            col_b.subheader("Tickets por Módulo")
            col_b.bar_chart(df_f["MODULO"].value_counts())

            st.subheader("Tiempo Promedio de Resolución por Prioridad (min)")
            st.bar_chart(df_f.groupby("PRIORIDAD")["TIEMPO_RES"].mean())

        with t2:
            st.header("Análisis de Performance y Capacidad")
            # Merge con config para DISPONIBLE
            df_p = pd.merge(df_f, df_config[["CONSULTOR", "DISPONIBLE"]], on="CONSULTOR", how="left").fillna(0)
            
            # Agrupación Diaria
            df_diario = df_p.groupby(["FE_CONSULT", "CONSULTOR"]).agg({
                "TIEMPO_RES": "sum",
                "DISPONIBLE": "first",
                "ID_TICKET": "count"
            }).reset_index()
            
            # Cálculos de Performance
            df_diario["OCUPACION"] = (df_diario["TIEMPO_RES"] / df_diario["DISPONIBLE"] * 100).fillna(0)
            df_diario["OCIOSO"] = (df_diario["DISPONIBLE"] - df_diario["TIEMPO_RES"]).clip(lower=0)
            
            # 9-10. RIESGO OPERATIVO
            sobrecarga = len(df_diario[df_diario["TIEMPO_RES"] > df_diario["DISPONIBLE"]])
            subutiliz = len(df_diario[df_diario["TIEMPO_RES"] < 300])
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Días con Sobrecarga", sobrecarga, delta_color="inverse")
            k2.metric("Días Subutilizados (<5hs)", subutiliz)
            k3.metric("Ocupación Promedio", f"{df_diario['OCUPACION'].mean():.1f}%")

            st.subheader("Minutos Productivos Reales vs Objetivo por Consultor")
            st.line_chart(df_diario.set_index("FE_CONSULT")[["TIEMPO_RES", "DISPONIBLE"]])

        with t3:
            st.header("Métricas Financieras de Operación")
            # Merge con config para VALOR_HORA
            df_money = pd.merge(df_f, df_config[["CONSULTOR", "VALOR_HORA"]], on="CONSULTOR", how="left").fillna(0)
            df_money["COSTO"] = (df_money["TIEMPO_RES"] / 60) * df_money["VALOR_HORA"]
            
            total_costo = df_money["COSTO"].sum()
            st.metric("Inversión Total en Servicios", f"$ {total_costo:,.2f}")
            
            m1, m2 = st.columns(2)
            m1.subheader("Costo Insumido por Cliente")
            m1.bar_chart(df_money.groupby("CLIENTES")["COSTO"].sum())
            
            m2.subheader("Costo por Consultor")
            m2.bar_chart(df_money.groupby("CONSULTOR")["COSTO"].sum())

# --- RESTO DE SECCIONES (NUEVO, MODIFICAR, ETC) SE MANTIENEN IGUAL ---
elif st.session_state.menu_activo == "➕ NUEVO":
    # (Lógica de carga de tickets anterior...)
    st.info("Utilice el formulario para cargar nuevos tickets.")
