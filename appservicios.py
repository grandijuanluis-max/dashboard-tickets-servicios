import streamlit as st
import altair as alt
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, date, timedelta
import io
from fpdf import FPDF
import time
import os

# 1. CONFIGURACIÓN E IDENTIFICACIÓN MAESTRA
st.set_page_config(page_title="GR Consulting - Gestión Integral BI", layout="wide", page_icon="📈")

def cargar_estilos_claros():
    import base64, os
    bg_encoded = ""
    # Ruta estática relativa para garantizar que funcione en Streamlit Cloud
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bg_path = os.path.join(base_dir, "bg_premium.png")
    
    if os.path.exists(bg_path):
        try:
            with open(bg_path, "rb") as f:
                bg_encoded = base64.b64encode(f.read()).decode()
        except: pass

    if bg_encoded:
        st.markdown(f'''
        <style>
        /* Desacoplar el contenedor nativo de streamlit para que deje ver el HTML debajo */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .fixed-bg {{
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: url('data:image/png;base64,{bg_encoded}');
            background-size: cover;
            background-position: center;
            opacity: 0.55; /* Fondo más fuerte a pedido del usuario */
            z-index: -999;
        }}
        .bg-overlay {{
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(255, 255, 255, 0.1); 
            z-index: -998;
            pointer-events: none;
        }}
        .block-container {{
            position: relative;
            z-index: 1;
        }}
        </style>
        <div class="fixed-bg"></div>
        <div class="bg-overlay"></div>
        ''', unsafe_allow_html=True)
    else:
        # Fallback si no está la imagen
        st.markdown('''
        <style>
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #F8FAFC !important;
            background-image: radial-gradient(#CBD5E1 1px, transparent 1px) !important;
            background-size: 20px 20px !important;
        }
        .block-container {
            position: relative;
            z-index: 1;
        }
        </style>
        ''', unsafe_allow_html=True)


    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #1E293B; /* Texto oscuro/azulado */
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Outfit', sans-serif !important;
    color: #0F172A !important;
}

.block-container {
    padding-top: 2rem !important;
}
p, span, div, label {
    color: #334155 !important;
}
/* Botones de Navegación Transmisión Glassmorphism */
.stButton > button, .stDownloadButton > button {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    border-radius: 8px !important;
    color: #0284C7 !important; /* Celeste Encendido */
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05) !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: rgba(255, 255, 255, 0.3) !important; 
    border-color: #0284C7 !important;
    color: #0369A1 !important; /* Azul más fuerte */
}
/* Formularios Claros Semitransparentes */
.stTextInput > div > div > input, 
.stSelectbox > div > div > div, 
.stNumberInput > div > div > input, 
.stDateInput > div > div > input,
.stTextArea > div > div > textarea {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    color: #0F172A !important;
    border-radius: 6px !important;
}
.stTextInput > div > div > input:focus,
.stSelectbox > div > div > div:focus,
.stTextArea > div > div > textarea:focus {
    border: 1px solid #0284C7 !important; /* Resalta en Celeste */
    box-shadow: 0 0 0 2px rgba(2, 132, 199, 0.2) !important;
}
.stTextInput label, .stSelectbox label, .stNumberInput label, .stDateInput label, .stTextArea label {
    color: #1E293B !important; 
    font-weight: 600 !important;
}
/* Métricas Totales transparentes */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    border-left: 5px solid #0284C7 !important; /* Linea lateral celeste */
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.05);
}
[data-testid="stMetricValue"] { color: #0F172A !important; font-family: 'Outfit', sans-serif; }
[data-testid="stMetricLabel"] { color: #64748B !important; font-weight: bold; text-transform: uppercase; }
/* Dataframes / Tablas translucidas */
[data-testid="stDataFrame"] {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
}
/* Esto ayuda a trasparentar la grilla interna si Streamlit lo permite */
[data-testid="stDataFrame"] > div {
    background: transparent !important;
}
/* Desplegables oscuros sobre claro */
[data-baseweb="popover"] div, 
[data-baseweb="popover"] span, 
[data-baseweb="menu"] div, 
[data-baseweb="menu"] span {
    color: #1a1a1a !important;
}
/* Sidebar */
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: blur(15px);
    border-right: 1px solid rgba(255, 255, 255, 0.3);
}
/* Separadores */
hr { border-color: rgba(255, 255, 255, 0.3) !important; margin: 2em 0px; }
/* Caja Info */
.stAlert {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: blur(10px) !important;
    color: #1E293B !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255, 255, 255, 0.3) !important;
}
/* Botones Principales -> NARANJA VIBRANTE */
button[kind="primary"] {
    background: #F97316 !important; 
    color: #FFFFFF !important;
    font-weight: bold !important;
    border: none !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 15px rgba(249, 115, 22, 0.4) !important;
    transition: all 0.3s ease !important;
}
button[kind="primary"]:hover {
    background: #EA580C !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(249, 115, 22, 0.6) !important;
}
</style>
""", unsafe_allow_html=True)

cargar_estilos_claros()

@st.cache_resource
def init_supabase():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    return create_client(url, key) if url and key else None

supabase: Client = init_supabase()

# --- ESTADO DE SESIÓN ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_logueado" not in st.session_state: st.session_state.usuario_logueado = None
if "menu_activo" not in st.session_state: st.session_state.menu_activo = "➕ NUEVO"

if "f_desde" not in st.session_state: st.session_state.f_desde = date(2020, 1, 1)
if "f_hasta" not in st.session_state: st.session_state.f_hasta = date.today()

mes_d = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

# --- FUNCIONES DE CARGA Y PROTECCIÓN ---
def obtener_config():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("config_consultores").select("*").execute()
        if not response.data: return pd.DataFrame()
        df = pd.DataFrame(response.data)
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Preservar el tipo numérico para las columnas financieras y de objetivos
        cols_numericas = ["VALOR_HORA", "OBJ_DIARIO"]
        for col in cols_numericas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        # Mantener el texto limpio y en mayúsculas para el resto
        for col in df.columns:
            if col not in cols_numericas:
                df[col] = df[col].astype(str).str.strip().str.upper().str.replace(r"\.0$", "", regex=True)
                
        return df
    except: return pd.DataFrame()

def obtener_datos_tickets():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("bd_dashboard_servicios").select("*").execute()
        if not response.data: return pd.DataFrame()
        df = pd.DataFrame(response.data)
        df.columns = [str(c).strip().upper().replace('AÑO', 'ANIO') for c in df.columns]
        if "ID_TICKET" in df.columns:
            df["ID_NUM"] = pd.to_numeric(df["ID_TICKET"], errors='coerce').fillna(0).astype(int)
        if "FE_CONSULT" in df.columns:
            df["FE_DT"] = pd.to_datetime(df["FE_CONSULT"], dayfirst=True, errors='coerce')
        df["TIEMPO_RES"] = pd.to_numeric(df.get("TIEMPO_RES", 0), errors='coerce').fillna(0)
        df["ANIO"] = pd.to_numeric(df.get("ANIO", 0), errors='coerce').fillna(0).astype(int)
        df["MES"] = pd.to_numeric(df.get("MES", 0), errors='coerce').fillna(0).astype(int)
        return df.fillna("")
    except: return pd.DataFrame()

def registrar_auditoria(id_ticket, accion, consultor):
    if not supabase: return
    try:
        data = {
            "id_ticket": int(id_ticket), 
            "consultor": consultor, 
            "fecha_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 
            "accion": accion
        }
        supabase.table("log_auditoria").insert(data).execute()
    except: pass

def guardar_seguro(data_dict, accion_msg):
    if not supabase: return False
    intentos = 0
    while intentos < 2:
        try:
            clean_dict = {k.lower(): v for k, v in data_dict.items() if k.upper() not in ["ID_NUM", "FE_DT"]}
            supabase.table("bd_dashboard_servicios").upsert(clean_dict).execute()
            return True
        except Exception as e:
            intentos += 1
            time.sleep(1)
    return False

def get_index_seguro(lista, valor_buscado):
    try:
        valor_limpio = str(valor_buscado).strip().upper()
        lista_limpia = [str(item).strip().upper() for item in lista]
        if valor_limpio in lista_limpia:
            return lista_limpia.index(valor_limpio)
        return 0
    except: return 0

# ==========================================
# 🔐 LOGIN
# ==========================================
if not st.session_state.autenticado:
    st.write("")
    st.write("")
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        hora_actual = datetime.now().hour
        dia_mes = datetime.now().day
        
        frases_motiv = [
            "Toda la energía para hoy", "A conquistar la jornada", "A dar el 100% hoy", 
            "Vamos a romperla", "Con actitud positiva todo es posible", "Un paso más cerca del éxito",
            "Hoy es un gran día para destacar", "La productividad al máximo", "Hagamos que las cosas pasen",
            "A brillar en cada tarea", "La excelencia es nuestro hábito", "Conectados y listos para triunfar",
            "Vamos por esos objetivos", "Innovando y resolviendo", "Energía positiva activada",
            "Un nuevo día, nuevos logros", "A seguir sumando éxitos", "El esfuerzo de hoy suma mañana",
            "Enfocados en la meta", "Dando lo mejor en cada detalle", "El éxito nos espera",
            "Listos para un desempeño estelar", "Aportando valor desde el minuto uno", "Motivación al 1000%",
            "Vamos a marcar la diferencia", "Liderando con resultados", "Cada ticket es una oportunidad",
            "Optimizando y resolviendo a fondo", "Creciendo profesionalmente hoy", "Siempre en un nivel premium",
            "Cierre espectacular de jornada"
        ]
        
        frase_elegida = frases_motiv[(dia_mes - 1) % len(frases_motiv)]
        
        if 5 <= hora_actual < 12: base = "¡Buenos días! ☀️"
        elif 12 <= hora_actual < 19: base = "¡Buenas tardes! 🚀"
        else: base = "¡Buenas noches! 🌙"
            
        st.markdown(f"<h2 style='text-align: center; color: #10B981;'>{base} {frase_elegida}</h2>", unsafe_allow_html=True)
        with st.form("login"):
            c_in = st.text_input("Consultor").strip().upper()
            p_in = st.text_input("Contraseña", type="password").strip()
            if st.form_submit_button("INGRESAR", use_container_width=True):
                df_u = obtener_config()
                if not df_u.empty and "CONSULTOR" in df_u.columns:
                    match = df_u[(df_u["CONSULTOR"] == c_in) & (df_u["PASSWORD"] == p_in)]
                    if not match.empty:
                        st.session_state.autenticado, st.session_state.usuario_logueado = True, c_in
                        st.rerun()
                    else: st.error("Credenciales incorrectas")
    st.stop()

# --- CARGA DE DATOS ---
nombre_consultor = st.session_state.usuario_logueado
df_config, df_actual = obtener_config(), obtener_datos_tickets()
user_match = df_config[df_config["CONSULTOR"] == nombre_consultor] if not df_config.empty else pd.DataFrame()
user_info = user_match.iloc[0] if not user_match.empty else {"ROL": "USER"}
es_admin = str(user_info.get("ROL")).upper() == "ADMIN"

# ==========================================
# 🗺 NAVEGACIÓN SUPERIOR
# ==========================================
btns = []
if str(user_info.get("NUEVO", "NO")).strip().upper() == "SI": btns.append("➕ NUEVO")
if str(user_info.get("MODIFICAR", "NO")).strip().upper() == "SI": btns.append("✏️ MODIFICAR")
if str(user_info.get("CONSULTAS", "NO")).strip().upper() == "SI": btns.append("🔍 CONSULTAR")
if str(user_info.get("REPORTES", "NO")).strip().upper() == "SI": btns.append("📊 REPORTES")
if str(user_info.get("DASHBOARDS", user_info.get("DASHBOARD", "NO"))).strip().upper() == "SI": btns.append("📈 DASHBOARDS")
if str(user_info.get("PERMISOS", "NO")).strip().upper() == "SI" or es_admin: btns.append("⚙️ PERMISOS")

if not btns:
    st.warning("Usuario sin permisos en ningún módulo.")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()
    st.stop()

if st.session_state.menu_activo not in btns:
    st.session_state.menu_activo = btns[0]

cols_menu = st.columns(len(btns))
for i, b in enumerate(btns):
    # Usamos on_click nativo o chequeo en cascada
    if cols_menu[i].button(b, use_container_width=True): 
        st.session_state.menu_activo = b

st.divider()

# ==========================================
# 🎯 SIDEBAR (FILTROS)
# ==========================================
with st.sidebar:
    st.success(f"👤 **{nombre_consultor}**")
    if st.button("🚪 Cerrar Sesión"): 
        st.session_state.autenticado = False
        st.rerun()
    st.divider()
    
    if st.session_state.menu_activo in ["📊 REPORTES", "📈 DASHBOARDS", "🔍 CONSULTAR"]:
        st.header("📅 Rango y Periodos")
        hoy_dt = date.today()
        # "Mes Actual" ahora es el primero en la lista (Default)
        periodo_sel = st.selectbox("Accesos Rápidos:", ["Mes Actual", "Hoy", "Ayer", "Mes Anterior", "Personalizado"])
        
        if periodo_sel == "Hoy": st.session_state.f_desde = st.session_state.f_hasta = hoy_dt
        elif periodo_sel == "Ayer": st.session_state.f_desde = st.session_state.f_hasta = hoy_dt - timedelta(days=1)
        elif periodo_sel == "Mes Actual": st.session_state.f_desde, st.session_state.f_hasta = hoy_dt.replace(day=1), hoy_dt
        elif periodo_sel == "Mes Anterior":
            ult = hoy_dt.replace(day=1) - timedelta(days=1)
            st.session_state.f_desde, st.session_state.f_hasta = ult.replace(day=1), ult
            
        f_desde = st.date_input("Desde:", value=st.session_state.f_desde, format="DD/MM/YYYY")
        f_hasta = st.date_input("Hasta:", value=st.session_state.f_hasta, format="DD/MM/YYYY")
        
        st.session_state.f_desde, st.session_state.f_hasta = f_desde, f_hasta
    else: f_desde, f_hasta = date(2000, 1, 1), date(2100, 1, 1)

    st.divider()
    l_cli_f = sorted(df_actual["CLIENTES"].unique()) if not df_actual.empty else []
    l_con_f = sorted(df_actual["CONSULTOR"].unique()) if not df_actual.empty else []
    l_mod_f = sorted(df_actual["MODULO"].unique()) if not df_actual.empty else []
    
    f_cli = st.multiselect("Clientes:", l_cli_f)
    f_con = st.multiselect("Consultores:", l_con_f)
    f_mod = st.multiselect("Módulos:", l_mod_f)
    f_ani = st.multiselect("Años:", sorted([a for a in df_actual["ANIO"].unique() if a > 2000], reverse=True) if not df_actual.empty else [])
    f_mes = st.multiselect("Meses:", options=list(mes_d.keys()), format_func=lambda x: mes_d[x])

# --- LÓGICA DE FILTRADO MAESTRO ---
df_f = df_actual.copy()
if not df_f.empty and "FE_DT" in df_f.columns:
    df_f = df_f[(df_f["FE_DT"].dt.date >= f_desde) & (df_f["FE_DT"].dt.date <= f_hasta)]
if f_cli: df_f = df_f[df_f["CLIENTES"].isin(f_cli)]
if f_con: df_f = df_f[df_f["CONSULTOR"].isin(f_con)]
if f_mod: df_f = df_f[df_f["MODULO"].isin(f_mod)]
if f_ani: df_f = df_f[df_f["ANIO"].isin(f_ani)]
if f_mes: df_f = df_f[df_f["MES"].isin(f_mes)]

# Listas de opciones estándar para Formularios
OPC_TIPO = ["FUNCIONAL", "TÉCNICA", "COMERCIAL"]
OPC_PRIO = ["BAJA", "MEDIA", "ALTA"]
OPC_ESTADO = ["ABIERTO", "EN PROCESO", "CERRADO"]
OPC_ATE = ["TELEFÓNICA", "WHATSAPP", "MEET", "VISITA", "PROGRAMADA"]
OPC_MOD = ["ACCESOS", "ADMINISTRACION", "ANYDESK", "GR CONSULTING", "CONTABILIDAD", "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", "IMPUESTOS", "ERROR TABLAS", "STOCK", "QUERYS CREAR", "QUERYS MODIF", "SINCRONIZACION", "CAMBIO VERSION", "CAMBIO EJECUTABLE", "INVESTIGACION", "ANALISIS", "CRM/WORKFLOW", "FACT.ELECT", "CONFIGURACIONES", "REPORTES", "FACTURACION", "WEB", "OTROS"]
OPC_CLI = sorted(["PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC","SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GRUPO VAZQUEZ", "GR_CONSULTING"])

# ==========================================
# ➕ SOLAPA 1: NUEVO
# ==========================================
if st.session_state.menu_activo == "➕ NUEVO":
    proximo_id = int(df_actual["ID_NUM"].max()) + 1 if not df_actual.empty else 1
    with st.form("f_nuevo", clear_on_submit=True):
        st.subheader(f"Nuevo Registro #{proximo_id}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("CONSULTOR", value=nombre_consultor, disabled=True)
            tipo_n = st.selectbox("TIPO_CONS", OPC_TIPO); prio_n = st.selectbox("PRIORIDAD", OPC_PRIO); est_n = st.selectbox("ESTADO", OPC_ESTADO)
        with c2:
            cli_n = st.selectbox("CLIENTES", OPC_CLI); usu_n = st.text_input("USUARIO CLIENTE *").upper()
            ate_n = st.selectbox("ATENCION", OPC_ATE); on_n = st.radio("ONLINE", ["SI", "NO"], horizontal=True)
        with c3:
            mod_n = st.selectbox("MODULO", OPC_MOD); fe_n = st.date_input("FE_CONSULT", datetime.now(), format="DD/MM/YYYY")
            tie_n = st.number_input("TIEMPO_RES (min) *", min_value=0)
        con_txt = st.text_area("CONSULTAS *"); rta_txt = st.text_area("RESPUESTAS *")
        if st.form_submit_button("💾 GUARDAR TICKET"):
            if not usu_n.strip() or not con_txt.strip() or tie_n <= 0: st.error("Completa campos obligatorios.")
            else:
                nuevo_dict = {"ID_TICKET": proximo_id, "CONSULTOR": nombre_consultor, "TIPO_CONS": tipo_n, "PRIORIDAD": prio_n, "ESTADO": est_n, "ATENCION": ate_n, "CLIENTES": cli_n, "USUARIO": usu_n, "FE_CONSULT": fe_n.strftime('%d/%m/%Y'), "MODULO": mod_n, "CONSULTAS": con_txt, "RESPUESTAS": rta_txt, "TIEMPO_RES": tie_n, "ONLINE": on_n, "ANIO": fe_n.year, "MES": fe_n.month}
                if guardar_seguro(nuevo_dict, "ALTA"):
                    registrar_auditoria(proximo_id, f"ALTA ({est_n})", nombre_consultor)
                    st.success(f"✅ Ticket #{proximo_id} guardado."); time.sleep(1); st.rerun()

# ==========================================
# ✏️ SOLAPA 2: MODIFICAR
# ==========================================
elif st.session_state.menu_activo == "✏️ MODIFICAR":
    df_mod = df_actual[df_actual["ESTADO"].str.upper().isin(["ABIERTO", "EN PROCESO"])].copy()
    if not df_mod.empty:
        sel_m = st.selectbox("Ticket Pendiente:", df_mod.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['FE_CONSULT']}", axis=1))
        id_m = int(sel_m.split(" |")[0].replace("#","")); idx_f = df_actual.index[df_actual["ID_NUM"] == id_m].tolist()[0]; dm = df_actual.loc[idx_f]
        try:
            f_val = pd.to_datetime(dm["FE_CONSULT"], dayfirst=True, errors='coerce')
            f_val = f_val.date() if not pd.isna(f_val) else date.today()
        except: f_val = date.today()
        with st.form("f_mod"):
            st.info(f"Modificando Ticket #{id_m}")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.text_input("CONSULTOR", value=dm["CONSULTOR"], disabled=True)
                n_tipo = st.selectbox("TIPO_CONS", OPC_TIPO, index=get_index_seguro(OPC_TIPO, dm["TIPO_CONS"]))
                n_prio = st.selectbox("PRIORIDAD", OPC_PRIO, index=get_index_seguro(OPC_PRIO, dm["PRIORIDAD"]))
                n_est = st.selectbox("ESTADO", OPC_ESTADO, index=get_index_seguro(OPC_ESTADO, dm["ESTADO"]))
            with c2:
                lista_c_db = sorted(df_actual["CLIENTES"].unique().tolist())
                n_cli = st.selectbox("CLIENTES", lista_c_db, index=get_index_seguro(lista_c_db, dm["CLIENTES"]))
                n_usu = st.text_input("USUARIO", value=str(dm["USUARIO"]))
                n_ate = st.selectbox("ATENCION", OPC_ATE, index=get_index_seguro(OPC_ATE, dm["ATENCION"]))
                n_on = st.radio("ONLINE", ["SI", "NO"], index=0 if str(dm["ONLINE"]).upper()=="SI" else 1, horizontal=True)
            with c3:
                n_mod = st.selectbox("MODULO", OPC_MOD, index=get_index_seguro(OPC_MOD, dm["MODULO"]))
                n_fe = st.date_input("FE_CONSULT", value=f_val, format="DD/MM/YYYY")
                n_tie = st.number_input("TIEMPO_RES", value=int(pd.to_numeric(dm["TIEMPO_RES"], errors='coerce') or 0))
            n_con = st.text_area("CONSULTAS", value=str(dm["CONSULTAS"])); n_rta = st.text_area("RESPUESTAS", value=str(dm["RESPUESTAS"]))
            if st.form_submit_button("🔥 ACTUALIZAR REGISTRO"):
                upd_dict = {
                    "ID_TICKET": int(id_m), "CONSULTOR": dm["CONSULTOR"], "TIPO_CONS": n_tipo, 
                    "PRIORIDAD": n_prio, "ESTADO": n_est, "ATENCION": n_ate, "CLIENTES": n_cli,
                    "USUARIO": n_usu, "FE_CONSULT": n_fe.strftime('%d/%m/%Y'), "MODULO": n_mod,
                    "CONSULTAS": n_con, "RESPUESTAS": n_rta, "TIEMPO_RES": n_tie, "ONLINE": n_on,
                    "ANIO": n_fe.year, "MES": n_fe.month
                }
                if guardar_seguro(upd_dict, "MODIF"):
                    registrar_auditoria(id_m, f"MODIFICACION ({n_est})", nombre_consultor)
                    st.success("✅ Registro actualizado correctamente."); time.sleep(1); st.rerun()
    else: st.warning("No hay tickets pendientes.")

# ==========================================
# 📊 REPORTES (REESTRUCTURADO TOTAL)
# ==========================================
elif st.session_state.menu_activo == "📊 REPORTES":
    st.header(f"📊 Reportes: {periodo_sel}")
    if not df_f.empty:
        t_hs = df_f["TIEMPO_RES"].sum() / 60
        st.metric("Horas Totales", f"{t_hs:,.2f} hs")
        res = df_f.groupby(["CLIENTES", "MODULO", "CONSULTOR"])["TIEMPO_RES"].sum().reset_index()
        res["HORAS"] = (res["TIEMPO_RES"]/60).round(2)
        st.dataframe(res.drop(columns=["TIEMPO_RES"]), use_container_width=True, hide_index=True)
        
        s_cli = f"_{f_cli[0]}" if len(f_cli) == 1 else ""; s_date = f"_{f_desde.strftime('%d%m%y')}_a_{f_hasta.strftime('%d%m%y')}"
        nom_base = f"{s_cli}{s_date}"
        
        tipo_xls = st.radio("Excel:", ["Resumido", "Detallado"], horizontal=True); buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            if "Resumido" in tipo_xls: res.to_excel(w, index=False)
            else:
                df_det = df_f[["ID_TICKET", "FE_CONSULT", "CLIENTES", "MODULO", "CONSULTOR", "USUARIO", "TIEMPO_RES"]].copy()
                df_det["HORAS"] = (df_det["TIEMPO_RES"]/60).round(2); df_det["CONSULTAS"] = df_f["CONSULTAS"]; df_det["RESPUESTAS"] = df_f["RESPUESTAS"]
                df_det.to_excel(w, index=False)
        
        # --- MOTOR DE PDF REESTRUCTURADO ---
        pdf_a = FPDF(); pdf_a.add_page(); pdf_a.set_font("Arial", 'B', 10)
        
        # Encabezado de Filtros
        pdf_a.set_fill_color(240, 240, 240)
        pdf_a.cell(0, 7, "FILTROS UTILIZADOS", 1, ln=True, align='C', fill=True)
        pdf_a.set_font("Arial", '', 9)
        pdf_a.cell(0, 6, f"Periodo: {f_desde.strftime('%d/%m/%Y')} al {f_hasta.strftime('%d/%m/%Y')}", 1, ln=True)
        pdf_a.cell(0, 6, f"Clientes: {', '.join(f_cli) if f_cli else 'TODOS'}", 1, ln=True)
        pdf_a.cell(0, 6, f"Consultores: {', '.join(f_con) if f_con else 'TODOS'}", 1, ln=True)
        pdf_a.ln(5)
        
        pdf_a.set_font("Arial", 'B', 14); pdf_a.cell(0, 10, "Resumen Analítico", ln=True, align='C')
        pdf_a.ln(2)

        clientes_unicos = df_f["CLIENTES"].unique()

        if len(clientes_unicos) > 1:
            # CASO VARIOS CLIENTES
            for cl in sorted(clientes_unicos):
                df_cl = df_f[df_f["CLIENTES"] == cl]
                sum_cl = df_cl["TIEMPO_RES"].sum() / 60
                pdf_a.set_font("Arial", 'B', 10)
                pdf_a.cell(115, 7, f"CLIENTE: {cl}", 1, 0, fill=True)
                pdf_a.cell(30, 7, f"{sum_cl:,.2f} hs", 1, ln=True, align='R', fill=True)
                
            pdf_a.ln(5)
            # Total por Consultor al final
            pdf_a.set_font("Arial", 'B', 11); pdf_a.cell(0, 8, "TOTAL POR CONSULTOR", ln=True)
            pdf_a.set_font("Arial", '', 10)
            res_con = df_f.groupby("CONSULTOR")["TIEMPO_RES"].sum().reset_index()
            for _, r in res_con.iterrows():
                pdf_a.cell(85, 7, str(r['CONSULTOR']), 1)
                pdf_a.cell(30, 7, f"{(r['TIEMPO_RES']/60):,.2f} hs", 1, ln=True, align='R')
            
        else:
            # CASO UN SOLO CLIENTE
            cl_name = clientes_unicos[0]
            pdf_a.set_font("Arial", 'B', 12)
            # Recuadro por cliente
            pdf_a.rect(10, pdf_a.get_y(), 190, 12)
            pdf_a.cell(0, 12, f"  CLIENTE: {cl_name}", ln=True)
            pdf_a.ln(2)
            
            # Registro de cada módulo
            pdf_a.set_font("Arial", 'B', 10)
            pdf_a.cell(100, 7, "MÓDULO", 1); pdf_a.cell(30, 7, "HORAS", 1, ln=True, align='C')
            pdf_a.set_font("Arial", '', 10)
            res_mod = df_f.groupby("MODULO")["TIEMPO_RES"].sum().reset_index()
            for _, rm in res_mod.iterrows():
                pdf_a.cell(100, 7, str(rm['MODULO']), 1)
                pdf_a.cell(30, 7, f"{(rm['TIEMPO_RES']/60):,.2f}", 1, ln=True, align='R')

        # TOTAL GENERAL FINAL (Para ambos casos)
        pdf_a.ln(5)
        pdf_a.set_font("Arial", 'B', 11)
        pdf_a.set_text_color(255, 0, 0)
        pdf_a.cell(100, 10, "TOTAL GENERAL PROYECTO:", 1, 0, 'R')
        pdf_a.cell(30, 10, f"{t_hs:,.2f} hs", 1, ln=True, align='C')
        pdf_a.set_text_color(0, 0, 0)

        # Pie de página
        pdf_a.ln(10); pdf_a.set_font("Arial", 'I', 8)
        pdf_a.cell(0, 10, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", 0, 0, 'C')
        
        st.divider()
        st.markdown("#### 📥 Opciones de Exportación")
        col_down, col_vacia = st.columns([1, 2])
        with col_down:
            st.download_button(f"📊 Exportar Excel", buf.getvalue(), f"GR_{tipo_xls}{nom_base}.xlsx", use_container_width=True)
            st.download_button("📄 Exportar PDF", pdf_a.output(dest='S').encode('latin-1', 'ignore'), f"Analitico_GR{nom_base}.pdf", use_container_width=True)

# (Resto de Dashboards, Consultar y Permisos se mantienen igual)
elif st.session_state.menu_activo == "📈 DASHBOARDS":
    if not df_f.empty:
        cols_traer = ["CONSULTOR", "VALOR_HORA"]
        if "OBJ_DIARIO" in df_config.columns: cols_traer.append("OBJ_DIARIO")
        
        df_dash = pd.merge(df_f, df_config[cols_traer], on="CONSULTOR", how="left").fillna(0)
        df_dash["HORAS"] = df_dash["TIEMPO_RES"] / 60
        
        tab1, tab2, tab3, tab4 = st.tabs(["🏆 Productividad", "👥 Consumo Clientes", "🧩 Consumo Modulos", "💰 Financiero"])
        
        with tab1:
            st.markdown("### 🏆 Productividad por Consultor")
            modo_prod = st.radio("Agrupar Rendimiento por:", ["Día", "Semana", "Mes"], horizontal=True)
            
            # Objetivo logico
            if "OBJ_DIARIO" in df_dash.columns:
                df_dash["OBJ_DIARIO_NUM"] = pd.to_numeric(df_dash["OBJ_DIARIO"], errors='coerce').fillna(8.0)
            else:
                df_dash["OBJ_DIARIO_NUM"] = 8.0 # default
                
            df_prod = df_dash.copy()
            df_prod["FE_DT"] = pd.to_datetime(df_prod["FE_DT"], errors="coerce")
            df_prod = df_prod.dropna(subset=["FE_DT"])
            
            if not df_prod.empty:
                meses_str = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}
                
                if modo_prod == "Día":
                    df_prod["FECHA_ORDEN"] = df_prod["FE_DT"].dt.strftime("%Y-%m-%d")
                    df_prod["GRUPO_FECHA"] = df_prod["FE_DT"].dt.strftime("%d/%m/%Y")
                    mult_obj = 1
                elif modo_prod == "Semana":
                    df_prod["FECHA_ORDEN"] = df_prod["FE_DT"].dt.strftime("%Y-%W")
                    df_prod["GRUPO_FECHA"] = "Sem " + df_prod["FE_DT"].dt.isocalendar().week.astype(str)
                    mult_obj = 5
                elif modo_prod == "Mes":
                    df_prod["FECHA_ORDEN"] = df_prod["FE_DT"].dt.strftime("%Y-%m")
                    df_prod["GRUPO_FECHA"] = df_prod["FE_DT"].dt.month.map(meses_str) + " " + df_prod["FE_DT"].dt.year.astype(str)
                    mult_obj = 20
                    
                res_prod = df_prod.groupby(["FECHA_ORDEN", "GRUPO_FECHA", "CONSULTOR"]).agg(
                    HORAS_REALES=("TIEMPO_RES", lambda x: x.sum() / 60),
                    OBJ_DIARIO_MAX=("OBJ_DIARIO_NUM", "max")
                ).reset_index()
                
                res_prod["OBJ_META"] = res_prod["OBJ_DIARIO_MAX"] * mult_obj
                res_prod["PCT_LOGRO"] = (res_prod["HORAS_REALES"] / res_prod["OBJ_META"].replace(0, 1)) * 100
                res_prod["PCT_FORMAT"] = res_prod["PCT_LOGRO"].round(1).astype(str) + "%"
                res_prod["HORAS_REALES"] = res_prod["HORAS_REALES"].round(2)
                
                def f_color(pct):
                    if pct < 50: return "#EF4444"
                    elif pct <= 99: return "#F59E0B"
                    elif pct <= 105: return "#10B981"
                    else: return "#F97316"
                    
                res_prod["COLOR"] = res_prod["PCT_LOGRO"].apply(f_color)
                
                res_prod["MID_HORAS"] = res_prod["HORAS_REALES"] / 2
                res_prod["OBJ_META_MD"] = res_prod["OBJ_META"].max() # Usar el maximo como meta global
                
                base = alt.Chart(res_prod).encode(
                    x=alt.X("GRUPO_FECHA:O", title="Periodo", sort=alt.SortField("FECHA_ORDEN", order="ascending")),
                    xOffset="CONSULTOR:N"
                )
                
                bars = base.mark_bar(opacity=0.9).encode(
                    y=alt.Y("HORAS_REALES:Q", title="Horas Trabajadas"),
                    color=alt.Color("COLOR:N", scale=None, legend=None),
                    tooltip=["CONSULTOR", "GRUPO_FECHA", "HORAS_REALES", "OBJ_META", "PCT_FORMAT"]
                )
                
                bars_text = base.mark_text(align='center', baseline='middle', angle=270, color='#1E293B', fontSize=10).encode(
                    y=alt.Y("MID_HORAS:Q"),
                    text="CONSULTOR:N"
                )
                
                # Regla Global transversal
                global_rule = alt.Chart(res_prod).mark_rule(color='#1E293B', strokeDash=[5,5]).encode(
                    y="OBJ_META_MD:Q"
                )
                # Texto de leyenda "OBJETIVO"
                rule_text = alt.Chart(res_prod).mark_text(align='left', dx=5, dy=-10, color='#1E293B', fontSize=12).encode(
                    y="OBJ_META_MD:Q",
                    text=alt.value("OBJETIVO")
                )
                
                chart = alt.layer(bars, bars_text, global_rule, rule_text).properties(
                    height=350
                ).configure_view(
                    stroke="transparent"
                )
                
                st.altair_chart(chart, use_container_width=True)

        with tab2:
            st.markdown("### 👥 Consumo por Cliente")
            t_horas_cli = df_dash["HORAS"].sum()
            st.metric("Total Horas Consumidas", f"{t_horas_cli:,.2f} hs")
            
            df_clientes = df_dash.groupby("CLIENTES")["HORAS"].sum().reset_index()
            chart_cli = alt.Chart(df_clientes).mark_bar(color="#0284C7").encode(
                x=alt.X("CLIENTES:N", sort="-y", title="Cliente"),
                y=alt.Y("HORAS:Q", title="Horas Consumidas"),
                tooltip=["CLIENTES", alt.Tooltip("HORAS:Q", format=".2f", title="Horas")]
            ).properties(height=350)
            st.altair_chart(chart_cli, use_container_width=True)

        with tab3:
            st.markdown("### 🧩 Consumo por Módulos")
            st.markdown("#### Horas por Módulo")
            df_modulos = df_dash.groupby("MODULO")["HORAS"].sum().reset_index()
            chart_mod = alt.Chart(df_modulos).mark_bar(color="#10B981").encode(
                x=alt.X("MODULO:N", sort="-y", title="Módulo"),
                y=alt.Y("HORAS:Q", title="Horas Consumidas"),
                tooltip=["MODULO", alt.Tooltip("HORAS:Q", format=".2f", title="Horas")]
            ).properties(height=300)
            st.altair_chart(chart_mod, use_container_width=True)
            
            st.markdown("#### Horas por Módulo y Cliente")
            chart_mod_cli = alt.Chart(df_dash).mark_bar().encode(
                x=alt.X("sum(HORAS):Q", title="Horas Consumidas"),
                y=alt.Y("MODULO:N", title="Módulo", sort='-x'),
                color=alt.Color("CLIENTES:N", title="Cliente", scale=alt.Scale(scheme='category20')),
                tooltip=["MODULO", "CLIENTES", alt.Tooltip("sum(HORAS):Q", format=".2f", title="Horas")]
            ).properties(height=400)
            st.altair_chart(chart_mod_cli, use_container_width=True)

        with tab4:
            st.markdown("### 💰 Resumen Financiero")
            df_dash["COSTO"] = df_dash["HORAS"] * pd.to_numeric(df_dash["VALOR_HORA"], errors='coerce').fillna(0)
            st.metric("Inversión Total", f"$ {df_dash['COSTO'].sum():,.2f}")

elif st.session_state.menu_activo == "🔍 CONSULTAR":
    if not df_f.empty:
        sel_c = st.selectbox("Ticket:", df_f.apply(lambda r: f"#{r['ID_NUM']} | {r['CLIENTES']} | {r['ESTADO']}", axis=1))
        id_c = int(sel_c.split(" |")[0].replace("#","")); dc = df_f[df_f["ID_NUM"] == id_c].iloc[0]
        with st.container(border=True):
            st.subheader(f"Ticket #{id_c} [{dc['ESTADO']}]")
            v1, v2, v3 = st.columns(3)
            with v1: st.markdown(f"**CONSULTOR:** {dc['CONSULTOR']}\n\n**TIPO:** {dc['TIPO_CONS']}\n\n**PRIORIDAD:** {dc['PRIORIDAD']}")
            with v2: st.markdown(f"**CLIENTE:** {dc['CLIENTES']}\n\n**USUARIO:** {dc['USUARIO']}\n\n**ATENCIÓN:** {dc['ATENCION']}")
            with v3: st.markdown(f"**FECHA:** {dc['FE_CONSULT']}\n\n**TIEMPO:** {dc['TIEMPO_RES']} min\n\n**ONLINE:** {dc['ONLINE']}")
            st.divider(); st.info(f"**Consulta:**\n{dc['CONSULTAS']}"); st.success(f"**Respuesta:**\n{dc['RESPUESTAS']}")

elif st.session_state.menu_activo == "⚙️ PERMISOS" and es_admin:
    df_ed = st.data_editor(df_config, num_rows="dynamic", hide_index=True)
    if st.button("💾 Guardar", use_container_width=True):
        if supabase:
            exito = True
            map_cols = {
                "CONSULTOR": "consultor", "PASSWORD": "password", "ROL": "rol", "VALOR_HORA": "valor_hora",
                "NUEVO": "Nuevo", "MODIFICAR": "modificar", "CONSULTAS": "consultas", "REPORTES": "reportes",
                "DASHBOARDS": "dashboards", "PERMISOS": "permisos", "OBJ_DIARIO": "OBJ_DIARIO"
            }
            
            for _, row in df_ed.iterrows():
                try:
                    row_dict = {}
                    for k, v in row.items():
                        k_upper = str(k).strip().upper()
                        # Si no está en el mapa, probamos en minúscula por default
                        row_dict[map_cols.get(k_upper, k_upper.lower())] = v
                    
                    # Asegurar la limpieza e integridad de la clave primaria
                    if "consultor" not in row_dict or not str(row_dict["consultor"]).strip():
                        continue # Evitamos problemas si hay filas vacías
                        
                    # Casting explícito de las variables numéricas antes de enviarlas
                    if "valor_hora" in row_dict:
                        try: row_dict["valor_hora"] = float(row_dict["valor_hora"])
                        except: row_dict["valor_hora"] = 0.0
                    else:
                        row_dict["valor_hora"] = 0.0 # Valor por default
                        
                    if "OBJ_DIARIO" in row_dict:
                        try: row_dict["OBJ_DIARIO"] = float(row_dict["OBJ_DIARIO"])
                        except: row_dict["OBJ_DIARIO"] = 8.0 # Default a 8 hs
                        
                    # Fix para campos de texto limpios (strip)
                    for k_text in ["Nuevo", "modificar", "consultas", "reportes", "dashboards", "permisos"]:
                        if k_text in row_dict and isinstance(row_dict[k_text], str):
                            row_dict[k_text] = row_dict[k_text].strip().lower()

                    response = supabase.table("config_consultores").upsert(row_dict).execute()
                except Exception as e:
                    exito = False
                    st.error(f"Error detallado en {row.get('CONSULTOR', '')}: {str(e)}")
            
            if exito: st.success("✅ ¡Cambios Guardados Cómodamente!")
            time.sleep(1)
            st.rerun()
