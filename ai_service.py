import re
import logging
from datetime import datetime, date, time, timedelta
import pytz
from typing import Dict, Any, Optional, List
try:
    from src.config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)

CLIENTES_MAP = {
    "GRUPO VAZQUEZ": ["grupo vazquez", "grupo vázquez", "vazquez", "vázquez", "gv"],
    "GR_CONSULTING": ["gr consulting", "gr_consulting", "gr", "consulting", "consultora"],
    "SG_MONTAGES": ["sg montages", "sg_montages", "sg montajes", "sg_montajes", "montages", "montajes", "sg"],
    "PALAVERSICH": ["palaversich", "palaver", "pala"],
    "KARTONSEC": ["kartonsec", "karton", "cartonsec", "carton"],
    "PETROBONO": ["petrobono", "petro bono", "petro"],
    "MONTARFE": ["montarfe", "montar fe"],
    "CONDIMENTOS": ["condimentos", "condimento"],
    "FREMEC": ["fremec", "freme"],
    "SUAREZ": ["suarez", "suárez"],
    "PASINA": ["pasina", "pazina"],
    "DOPERT": ["dopert", "doper"],
    "ANHSA": ["anhsa", "ansa", "ansha", "ahnsa"],
    "IPR": ["ipr"],
    "PXP": ["pxp"],
    "LGS": ["lgs"]
}

CLIENTES_CONOCIDOS = sorted(list(CLIENTES_MAP.keys()), key=lambda x: len(x), reverse=True)

def detectar_cliente(t: str) -> Optional[str]:
    """Detecta el cliente oficial a partir de texto o audio, contemplando variantes fonéticas y sin acento."""
    t_clean = t.lower()
    for cliente_oficial, aliases in CLIENTES_MAP.items():
        sorted_aliases = sorted(aliases, key=lambda x: len(x), reverse=True)
        for alias in sorted_aliases:
            if re.search(rf"\b{re.escape(alias)}\b", t_clean):
                return cliente_oficial
    return None

NUMEROS_PALABRAS = {
    "media": 0.5,
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10
}

MINUTOS_PALABRAS = {
    "quince": 15, "veinte": 20, "veinticinco": 25, "treinta": 30,
    "cuarenta": 40, "cuarenta y cinco": 45, "cincuenta": 50
}

def extraer_minutos(t: str) -> int:
    """Extrae la duración en minutos interpretando números hablados ('media hora', 'hora y media', 'dos horas') o dígitos ('2 hs', '30 min')."""
    t_clean = t.lower()
    
    # Expresiones compuestas de duración
    if re.search(r"\b(?:1|una|un)?\s*hora\s+y\s+media\b", t_clean):
        return 90
    if re.search(r"\b(?:2|dos)\s*horas\s+y\s+media\b", t_clean):
        return 150
    if re.search(r"\b(?:media\s+hora|media\s+horita|medio\s+hora)\b", t_clean):
        return 30
    if re.search(r"\b(?:un\s+cuarto\s+de\s+hora|cuarto\s+de\s+hora)\b", t_clean):
        return 15
    if re.search(r"\b(?:tres\s+cuartos\s+de\s+hora|3/4\s+de\s+hora)\b", t_clean):
        return 45

    # Horas con número en palabras: "dos horas", "tres horas", "una hora"
    for pal, val in NUMEROS_PALABRAS.items():
        if re.search(rf"\b{pal}\s*(?:hs|hora|horas)\b", t_clean):
            return int(val * 60)

    # Minutos con número en palabras: "quince minutos", "treinta minutos"
    for pal, val in MINUTOS_PALABRAS.items():
        if re.search(rf"\b{pal}\s*(?:min|minuto|minutos)\b", t_clean):
            return val

    # Horas numéricas estándar: "2 horas", "1.5 hs", "2,5 horas", "3hs"
    m_hs = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:hs|hora|horas)", t_clean)
    if m_hs:
        hs_val = float(m_hs.group(1).replace(",", "."))
        return int(hs_val * 60)

    # Minutos numéricos: "30 min", "45 minutos"
    m_min = re.search(r"(\d+)\s*(?:min|minuto|minutos)", t_clean)
    if m_min:
        return int(m_min.group(1))

    # Default a 60 min si no especificó
    return 60

def limpiar_detalle_tarea(texto_original: str, cliente: Optional[str] = None) -> str:
    """Limpia el texto conversacional (saludos, verbos de carga, tiempo, cliente) para dejar una descripción clara de la tarea en el Dashboard."""
    limpio = texto_original.strip()

    # Quitar saludos iniciales comunes
    limpio = re.sub(
        r"(?i)^(?:hola|buenas\s*tardes|buenas\s*noches|buen\s*d[ií]a|buenas|che|por\s*favor|porfa)\s*[,.:;]?\s*",
        "",
        limpio
    )

    # Quitar comandos típicos de inicio
    patrones_comando = [
        r"(?i)^(?:te\s*paso\s*una\s*tarea|anot[aá]\s*una\s*tarea|anotame\s*una\s*tarea|cargame\s*una\s*tarea|carg[aá]\s*una\s*tarea|nueva\s*tarea|tarea\s*nueva|cargar\s*tarea|guardar\s*tarea)\s*[,.:;]?\s*",
        r"(?i)^(?:cargame|carg[aá]|registrame|registr[aá]|anotame|anot[aá]|guard[aá]|agreg[aá]|pon[eé]|ponele|cargale|anotale)\s+",
        r"(?i)^(?:estuve\s*trabajando|estuve|hice|trabaj[eé]|labur[eé]|dediqu[eé])\s+",
        r"(?i)^(?:quiero\s*cargar|quisiera\s*cargar|necesito\s*cargar|carguemos)\s+"
    ]
    for pat in patrones_comando:
        limpio = re.sub(pat, "", limpio).strip()

    # Quitar destinatario si quedó al inicio (ej: "a Juan Luis", "a Melani")
    limpio = re.sub(r"(?i)^(?:a\s+juan\s+luis|a\s+juanluis|al\s+jefe|a\s+melani|a\s+meli)\s*[,.:;]?\s*", "", limpio).strip()

    # Quitar expresiones de tiempo
    patrones_tiempo = [
        r"(?i)\b(?:1|una|un)?\s*hora\s+y\s+media\b",
        r"(?i)\b(?:2|dos)\s*horas\s+y\s+media\b",
        r"(?i)\b(?:media\s+hora|media\s+horita|medio\s+hora|un\s+cuarto\s+de\s+hora|tres\s+cuartos\s+de\s+hora)\b",
        r"(?i)\b\d+(?:[.,]\d+)?\s*(?:hs|hora|horas|min|minuto|minutos)\b",
        r"(?i)\b(?:una|dos|tres|cuatro|cinco|seis|siete|ocho)\s*(?:hs|hora|horas)\b",
        r"(?i)\b(?:quince|veinte|veinticinco|treinta|cuarenta|cuarenta\s+y\s+cinco|cincuenta)\s*(?:min|minuto|minutos)\b"
    ]
    for pat in patrones_tiempo:
        limpio = re.sub(pat, "", limpio)

    # Quitar mención al cliente
    if cliente:
        aliases = sorted(CLIENTES_MAP.get(cliente, [cliente.lower()]), key=lambda x: len(x), reverse=True)
        for alias in aliases:
            limpio = re.sub(rf"(?i)\b(?:en|para|con|de|al\s+cliente)?\s*{re.escape(alias)}\b", "", limpio)

    # Quitar comandos secundarios que hayan quedado
    for pat in patrones_comando:
        limpio = re.sub(pat, "", limpio).strip()

    # Quitar conectores iniciales sobrantes como "por ", "en ", "haciendo ", "con "
    limpio = re.sub(r"(?i)^(?:por|en|haciendo|con|sobre|de|que)\s+", "", limpio.strip())
    limpio = re.sub(r"^[,.:;\-\s]+", "", limpio).strip()

    # Si quedó algo significativo (más de 3 letras), capitalizar
    if len(limpio) >= 4:
        return limpio[0].upper() + limpio[1:]

    # Fallback sin saludos
    fallback = re.sub(r"(?i)^(?:hola|buenas\s*tardes|buenas\s*noches|buen\s*d[ií]a|buenas)\s*[,.:;]?\s*", "", texto_original).strip()
    return fallback[0].upper() + fallback[1:] if fallback else texto_original

MODULOS_CONOCIDOS = sorted([
    "ACCESOS", "ADMINISTRACION", "ANYDESK", "GR CONSULTING", "CONTABILIDAD", 
    "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", 
    "IMPUESTOS", "ERROR TABLAS", "STOCK", "QUERYS CREAR", "QUERYS MODIF", 
    "SINCRONIZACION", "CAMBIO VERSION", "CAMBIO EJECUTABLE", "INVESTIGACION", 
    "ANALISIS", "CRM/WORKFLOW", "FACT.ELECT", "CONFIGURACIONES", "REPORTES", 
    "FACTURACION", "WEB", "OTROS"
], key=lambda x: len(x), reverse=True)

MESES_NOMBRE = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

NOMBRES_MESES_ESP = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

INTERROGATIVAS = [
    "cuanto", "cuánto", "cuanta", "cuánta", "cuantos", "cuántos", "cuantas", "cuántas",
    "que", "qué", "q", "como", "cómo", "quien", "quién", "quienes", "quiénes",
    "donde", "dónde", "cual", "cuál", "cuales", "cuáles"
]

PALABRAS_CONSULTA = [
    "decime", "mostrame", "mostrá", "fijate", "revisa", "revisá",
    "consultar", "consulta", "saber", "quiero saber", "ver", "listar", "lista",
    "total", "balance", "resumen", "hubo", "demando", "demandó", "demanda",
    "demandaron", "ranking", "top", "consumio", "consumió", "llevo", "llevó"
]

PALABRAS_CLAVE_BUSQUEDA = sorted([
    "padron", "padrones", "cheque", "cheques", "hischeque", "recibo", "recibos", 
    "factura", "facturas", "facturacion", "facturación", "cursor", "query", "querys",
    "sincroniz", "index", "error", "permiso", "permisos", "auditoria", "cupon", "cupones",
    "retencion", "retenciones", "percepcion", "percepciones", "tabla", "tablas", "presea", "vdx"
], key=lambda x: len(x), reverse=True)

def resolver_periodo(t: str, ahora: datetime) -> Dict[str, Any]:
    """Resuelve con precisión el período solicitado (día, semana, mes, año) a partir de lenguaje natural."""
    hoy = ahora.date()

    # 1. DÍA ESPECÍFICO (ayer, anteayer, hoy, en el día, etc.)
    if any(p in t for p in ["en el dia de ayer", "el dia de ayer", "el día de ayer", "ayer"]):
        target = hoy - timedelta(days=1)
        return {"periodo_tipo": "DIA", "fecha": target, "etiqueta": f"Ayer ({target.strftime('%d/%m/%Y')})"}

    if any(p in t for p in ["anteayer", "antes de ayer"]):
        target = hoy - timedelta(days=2)
        return {"periodo_tipo": "DIA", "fecha": target, "etiqueta": f"Anteayer ({target.strftime('%d/%m/%Y')})"}

    if any(p in t for p in [
        "en el dia de hoy", "en el día de hoy", "el dia de hoy", "el día de hoy",
        "en el dia", "en el día", "del dia", "del día", "en el día actual", "en el dia actual", "de hoy", "hoy"
    ]):
        return {"periodo_tipo": "DIA", "fecha": hoy, "etiqueta": f"Hoy ({hoy.strftime('%d/%m/%Y')})"}

    # Fecha explícita DD/MM o DD/MM/YYYY
    m_fecha = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", t)
    if m_fecha:
        try:
            d = int(m_fecha.group(1))
            m = int(m_fecha.group(2))
            y = int(m_fecha.group(3)) if m_fecha.group(3) else ahora.year
            if y < 100: y += 2000
            target = date(y, m, d)
            return {"periodo_tipo": "DIA", "fecha": target, "etiqueta": target.strftime("%d/%m/%Y")}
        except Exception:
            pass

    # 2. SEMANA (esta semana, semana pasada)
    if any(p in t for p in ["semana pasada", "la semana que paso", "la semana que pasó", "semana anterior"]):
        lunes = hoy - timedelta(days=hoy.weekday() + 7)
        domingo = lunes + timedelta(days=6)
        return {
            "periodo_tipo": "SEMANA",
            "fecha_desde": lunes,
            "fecha_hasta": domingo,
            "etiqueta": f"Semana Pasada ({lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')})"
        }

    if any(p in t for p in ["esta semana", "en la semana", "de la semana", "semana actual"]):
        lunes = hoy - timedelta(days=hoy.weekday())
        domingo = lunes + timedelta(days=6)
        return {
            "periodo_tipo": "SEMANA",
            "fecha_desde": lunes,
            "fecha_hasta": domingo,
            "etiqueta": f"Esta Semana ({lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')})"
        }

    # 3. DETECCIÓN DE MES Y AÑO
    mes_nom_encontrado = None
    for nom, num in MESES_NOMBRE.items():
        if re.search(rf"\b{nom}\b", t):
            mes_nom_encontrado = num
            break

    es_mes_pasado = any(p in t for p in ["mes pasado", "mes anterior", "el mes que paso", "el mes que pasó"])
    es_este_mes = any(p in t for p in ["este mes", "en el mes", "del mes", "mes actual", "el mes"])

    m_anio = re.search(r"\b(202\d)\b", t)
    anio_especifico = int(m_anio.group(1)) if m_anio else None
    es_anio_pasado = any(p in t for p in ["año pasado", "anio pasado", "año anterior", "anio anterior", "el año que paso", "el año que pasó"])
    es_este_anio = any(p in t for p in [
        "este año", "este anio", "en el año", "en el anio", "del año", "del anio",
        "año actual", "anio actual", "lo que va del año", "lo que va del anio",
        "en lo que va del año", "en lo que va del anio", "todo el año", "todo el anio", "anual"
    ])

    if mes_nom_encontrado:
        anio = anio_especifico or (ahora.year - 1 if es_anio_pasado else ahora.year)
        return {
            "periodo_tipo": "MES",
            "mes": mes_nom_encontrado,
            "anio": anio,
            "etiqueta": f"{NOMBRES_MESES_ESP[mes_nom_encontrado]} {anio}"
        }

    if es_mes_pasado:
        if ahora.month == 1:
            mes = 12
            anio = ahora.year - 1
        else:
            mes = ahora.month - 1
            anio = ahora.year
        return {
            "periodo_tipo": "MES",
            "mes": mes,
            "anio": anio,
            "etiqueta": f"Mes Pasado ({NOMBRES_MESES_ESP[mes]} {anio})"
        }

    # 4. AÑO COMPLETO
    if es_anio_pasado:
        anio = ahora.year - 1
        return {"periodo_tipo": "ANIO", "mes": None, "anio": anio, "etiqueta": f"Año Pasado ({anio})"}

    if es_este_anio:
        anio = ahora.year
        return {"periodo_tipo": "ANIO", "mes": None, "anio": anio, "etiqueta": f"Este Año ({anio})"}

    if anio_especifico:
        return {"periodo_tipo": "ANIO", "mes": None, "anio": anio_especifico, "etiqueta": f"Año {anio_especifico}"}

    if es_este_mes:
        return {
            "periodo_tipo": "MES",
            "mes": ahora.month,
            "anio": ahora.year,
            "etiqueta": f"Este Mes ({NOMBRES_MESES_ESP[ahora.month]} {ahora.year})"
        }

    # Default a mes actual
    return {
        "periodo_tipo": "MES",
        "mes": ahora.month,
        "anio": ahora.year,
        "etiqueta": f"Este Mes ({NOMBRES_MESES_ESP[ahora.month]} {ahora.year})"
    }

def resolver_mes_anio(t: str, ahora: datetime) -> tuple[Optional[int], int]:
    """Resuelve el mes y año según expresiones relativas ('mes pasado', 'este mes', 'este año') o nombres de meses."""
    p = resolver_periodo(t, ahora)
    return p.get("mes"), p.get("anio", ahora.year)

DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
    "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
}

def resolver_fecha_agenda(t: str, ahora: datetime) -> Dict[str, Any]:
    """Resuelve la fecha consultada para la agenda."""
    hoy = ahora.date()
    if "pasado mañana" in t or "pasado manana" in t:
        target = hoy + timedelta(days=2)
        return {"fecha": "PASADO_MANANA", "fecha_iso": target.isoformat(), "etiqueta": f"Pasado Mañana ({target.strftime('%d/%m/%Y')})"}
    elif "mañana" in t or "manana" in t:
        target = hoy + timedelta(days=1)
        return {"fecha": "MANANA", "fecha_iso": target.isoformat(), "etiqueta": f"Mañana ({target.strftime('%d/%m/%Y')})"}
    elif "ayer" in t:
        target = hoy - timedelta(days=1)
        return {"fecha": "AYER", "fecha_iso": target.isoformat(), "etiqueta": f"Ayer ({target.strftime('%d/%m/%Y')})"}
    
    # Días de la semana
    for dia_nom, dia_num in DIAS_SEMANA.items():
        if re.search(rf"\b{dia_nom}\b", t):
            dias_adelante = (dia_num - ahora.weekday()) % 7
            if dias_adelante == 0:
                dias_adelante = 7
            target = hoy + timedelta(days=dias_adelante)
            return {"fecha": "EXACTA", "fecha_iso": target.isoformat(), "etiqueta": f"{dia_nom.capitalize()} ({target.strftime('%d/%m/%Y')})"}

    # Fecha explícita DD/MM
    m_fecha = re.search(r"(\d{1,2})[/.-](\d{1,2})", t)
    if m_fecha:
        try:
            target = date(ahora.year, int(m_fecha.group(2)), int(m_fecha.group(1)))
            return {"fecha": "EXACTA", "fecha_iso": target.isoformat(), "etiqueta": f"{target.strftime('%d/%m/%Y')}"}
        except Exception:
            pass

    return {"fecha": "HOY", "fecha_iso": hoy.isoformat(), "etiqueta": f"Hoy ({hoy.strftime('%d/%m/%Y')})"}

def resolver_destinatario(t: str, user_name: str = "MELANI") -> Dict[str, Any]:
    """
    Distingue si el mensaje se refiere en singular (al usuario o a su jefe) o en plural (a ambos / equipo).
    - Plural ("hicimos", "cargamos", "ambos", "los dos", "equipo") -> AMBOS (Melani y Juan Luis).
    - Mención del jefe ("mi jefe", "el jefe", "Juan Luis", "JL") -> JUANLUIS.
    - Mención de Melani ("Melani", "Meli") -> MELANI.
    - Singular propio o por defecto sin plural -> a la persona que habla individualmente.
    """
    t_clean = t.lower()

    # 1. PLURAL (ambos / los dos / equipo / nosotros)
    es_plural = any(p in t_clean for p in [
        "hicimos", "cargamos", "trabajamos", "laburamos", "metimos", "dedicamos", 
        "estuvimos", "llevamos", "tenemos", "sumamos", "entre los dos", "entre ambos",
        "ambos", "ambas", "los dos", "los 2", "las dos", "las 2", "juntos", "juntas",
        "nosotros", "equipo", "el equipo", "del equipo", "de los dos", "total de ambos",
        "en conjunto", "los chicos"
    ])
    if es_plural:
        return {"modo": "AMBOS", "consultor": "TODOS", "etiqueta": "ambos (Melani y Juan Luis)"}

    # 2. REFERENCIA EXPLÍCITA AL JEFE (singular)
    es_jefe = any(p in t_clean for p in [
        "mi jefe", "el jefe", "al jefe", "del jefe", "su jefe", "jefe",
        "juan luis", "juanluis", "juan", "jl"
    ])
    if es_jefe:
        return {"modo": "JEFE", "consultor": "JUANLUIS", "etiqueta": "tu jefe (Juan Luis)"}

    # 3. REFERENCIA EXPLÍCITA A MELANI (singular)
    es_melani = any(p in t_clean for p in [
        "melani", "meli", "la colaboradora", "a melani", "de melani"
    ])
    if es_melani:
        return {"modo": "COLABORADOR", "consultor": "MELANI", "etiqueta": "Melani"}

    # 4. PRIMERA PERSONA SINGULAR (yo / a mí)
    es_propio = any(w in t_clean.split() for w in [
        "hice", "cargue", "cargué", "trabaje", "trabajé", "labure", "laburé", 
        "meti", "metí", "dedique", "dediqué", "estuve", "llevo", "tengo", "meto", "sume", "sumé"
    ]) or any(p in t_clean for p in [
        "mis horas", "mi tiempo", "mi resumen", "mis tickets", "mi balance", 
        "para mi", "para mí", "yo solo", "yo sola", "a mi", "a mí", "lo mio", "lo mío"
    ])
    if es_propio:
        return {"modo": "MIO", "consultor": user_name, "etiqueta": f"vos ({user_name})"}

    # 5. SINGULAR POR DEFECTO (si no mencionó plural ni al otro, se refiere a quien habla)
    return {"modo": "MIO", "consultor": user_name, "etiqueta": f"vos ({user_name})"}

HORAS_PALABRAS = {
    "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veintiuna": 21,
    "veintidos": 22, "veintidós": 22, "veintitres": 23, "veintitrés": 23
}

def _extraer_fecha_evento(t: str, ahora: datetime) -> date:
    """Extrae la fecha objetivo para un evento de Google Calendar."""
    if "pasado mañana" in t or "pasado manana" in t:
        return ahora.date() + timedelta(days=2)
    if "mañana" in t or "manana" in t:
        return ahora.date() + timedelta(days=1)
    if re.search(r"\bhoy\b", t):
        return ahora.date()

    for dia_nom, dia_num in DIAS_SEMANA.items():
        if re.search(rf"\b{dia_nom}\b", t):
            dias_adelante = (dia_num - ahora.weekday()) % 7
            if dias_adelante == 0:
                dias_adelante = 7
            return ahora.date() + timedelta(days=dias_adelante)

    # Fecha textual: "15 de noviembre"
    meses_pat = "|".join(MESES_NOMBRE.keys())
    m_mes_txt = re.search(rf"\b(\d{{1,2}})\s+de\s+({meses_pat})(?:\s+de\s+(\d{{4}}))?\b", t)
    if m_mes_txt:
        try:
            d_val = int(m_mes_txt.group(1))
            m_val = MESES_NOMBRE[m_mes_txt.group(2)]
            y_val = int(m_mes_txt.group(3)) if m_mes_txt.group(3) else ahora.year
            return date(y_val, m_val, d_val)
        except Exception:
            pass

    m_fecha = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", t)
    if m_fecha:
        try:
            d_val = int(m_fecha.group(1))
            m_val = int(m_fecha.group(2))
            y_val = int(m_fecha.group(3)) if m_fecha.group(3) else ahora.year
            if y_val < 100:
                y_val += 2000
            return date(y_val, m_val, d_val)
        except Exception:
            pass

    return ahora.date() + timedelta(days=1)

def _extraer_hora_evento(t: str) -> tuple[int, int]:
    """Extrae (hora, minuto) en formato 24h soportando dígitos, palabras de audio y AM/PM."""
    hora = 10
    minuto = 0
    encontrada = False

    m_hora_precisa = re.search(r"\b(?:a\s+las|las)\s+(\d{1,2})(?:[:.](\d{2}))?\b", t)
    if not m_hora_precisa:
        m_hora_precisa = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(?:hs|hrs|h)\b", t)

    if m_hora_precisa:
        h_val = int(m_hora_precisa.group(1))
        if 0 <= h_val <= 23:
            hora = h_val
            encontrada = True
            if m_hora_precisa.group(2):
                minuto = int(m_hora_precisa.group(2))
    else:
        horas_pat = "|".join(sorted(HORAS_PALABRAS.keys(), key=len, reverse=True))
        m_pal = re.search(rf"\b(?:a\s+las|las)\s+({horas_pat})\b", t)
        if m_pal:
            hora = HORAS_PALABRAS[m_pal.group(1)]
            encontrada = True

    if encontrada:
        if "y media" in t and minuto == 0:
            minuto = 30
        elif "y cuarto" in t and minuto == 0:
            minuto = 15
        elif "menos cuarto" in t and minuto == 0 and hora > 0:
            hora -= 1
            minuto = 45

        if any(p in t for p in ["de la tarde", "a la tarde", "por la tarde", "de la noche", "a la noche", "pm", "p.m."]):
            if 1 <= hora <= 11:
                hora += 12
        elif "mediodia" in t or "mediodía" in t:
            if hora == 0 or hora == 12:
                hora = 12

    return hora, minuto

def parsear_crear_evento(t: str, user_text: str, ahora: datetime, tz) -> Optional[Dict[str, Any]]:
    """Detecta si se quiere crear/agendar un evento en Google Calendar."""
    # 0. Descartar consultas puras de agenda o preguntas sobre reuniones existentes
    es_pregunta_agenda = any(p in t for p in [
        "ver agenda", "mostrar agenda", "revisar agenda", "consultar agenda",
        "como viene la agenda", "cómo viene la agenda", "que hay en la agenda", "qué hay en la agenda",
        "que hay hoy", "qué hay hoy", "como viene hoy", "cómo viene hoy",
        "como viene mañana", "cómo viene mañana",
        "a que hora es la reunion", "a qué hora es la reunión", "cuando es la reunion", "cuándo es la reunión",
        "que reuniones", "qué reuniones", "tenemos reunion", "tenemos reunión", "hay reunion", "hay reunión"
    ]) or t.strip() in ["agenda", "calendario", "ver calendario", "mostrar calendario"]

    tiene_verbo_crear_agenda = (
        re.search(r"\b(?:agend(?:á(?:me|te|lo|la)?|a(?:me|te|lo|la)|ar)|registr[aá](?:me|te|lo|la)?|registrar|anot[aá](?:me|te|lo|la)?|anotar|cre[aá]|crear|sum[aá](?:me)?|sumar|program[aá](?:me)?|programar|poneme|poner)\b", t) is not None
        or any(p in t for p in [
            "cargar en la agenda", "cargar en agenda", "cargar a la agenda", "cargar la agenda",
            "cargá en la agenda", "cargá en agenda", "cargame en la agenda",
            "cargar en google", "cargá en google", "cargame en google",
            "cargar en el calendar", "cargá en el calendar", "cargame en el calendar"
        ])
    )

    if es_pregunta_agenda and not tiene_verbo_crear_agenda:
        return None
    if ("?" in t or "¿" in t) and not tiene_verbo_crear_agenda:
        return None

    # Si habla explícitamente de "tarea(s)" sin mencionar reunión/evento/meet/llamada/visita/turno, dejarlo a compromisos
    menciona_evento_cal = any(w in t for w in ["reunion", "reunión", "evento", "meet", "call", "llamada", "visita", "turno", "cita"])
    if re.search(r"\btareas?\b", t) and not menciona_evento_cal:
        return None

    # Si parece carga de horas/ticket (ej: "Cargué 1 hora en Pasina por reunión") y no menciona calendar/agenda/agendar, no es evento
    es_carga_horas = (
        any(w in t.split() for w in ["cargue", "cargué", "hice", "estuve", "trabaje", "trabajé", "labure", "laburé", "dedique", "dediqué"])
        and any(u in t for u in ["hora", "horas", "hs", "min", "minuto", "minutos"])
        and detectar_cliente(t) is not None
        and not any(c in t for c in ["agend", "calendar", "calendario", "agenda"])
    )
    if es_carga_horas:
        return None

    # Requiere intención explícita de agendar/crear evento
    patron_crear = (
        r"\b(agend(?:á(?:me|te|lo|la)?|a(?:me|te|lo|la)|ar)|"
        r"(?:cargar|carg[aá]|cargame|registrar|registr[aá]|registrame|anotar|anot[aá]|anotame|poner|poneme|sumar|sum[aá]|sumame|crear|cre[aá]|programar|program[aá]|armar|arm[aá])\s+(?:un[ao]?\s+)?(?:reuni[oó]n|evento|llamada|meet|call|visita|turno|cita)|"
        r"(?:cargar|carg[aá]|cargame|registrar|registr[aá]|registrame|anotar|anot[aá]|anotame|poner|poneme|sumar|sum[aá]|sumame)\s+(?:en\s+(?:el\s+|la\s+)?|a\s+(?:la\s+)?)?(?:agenda|calendario|google\s+calend(?:ar|er)|calendar)|"
        r"(?:tengo|tenemos)\s+(?:un[ao]?\s+)?(?:reuni[oó]n|meet|call|visita|turno|cita)|"
        r"(?:reuni[oó]n|meet|call|visita)\s+(?:con\s+\w+\s+)?(?:para\s+)?(?:hoy|mañana|manana|pasado|el\s+\w+|a\s+las\s+\w+|\d{1,2}\s*hs))\b"
    )
    menciona_calendar_y_accion = (
        (
            any(cal_w in t for cal_w in ["google calendar", "google calender", "calendario", "calendar", "en la agenda", "a la agenda"])
            or menciona_evento_cal
        )
        and tiene_verbo_crear_agenda
        and ("?" not in t and "¿" not in t)
    )
    if not re.search(patron_crear, t) and not menciona_calendar_y_accion:
        return None

    # Si es solo una palabra suelta sin datos
    if t.strip() in ["agenda", "agendar", "crear evento", "reunion", "reunión"]:
        return None

    # 1. Determinar Fecha y Hora
    target_date = _extraer_fecha_evento(t, ahora)
    hora, minuto = _extraer_hora_evento(t)
    start_dt = tz.localize(datetime.combine(target_date, time(hora, minuto)))

    # 2. Duración
    duracion = 60
    m_dur = re.search(r"(\d+)\s*(?:min|minutos)", t)
    if m_dur:
        duracion = int(m_dur.group(1))

    # 3. Título limpio
    clean_title = user_text
    clean_title = re.sub(
        r"(?i)^(?:hola|buenas|che|por\s+favor|porfa)[,.:;\s]*",
        "",
        clean_title
    )
    clean_title = re.sub(
        r"(?i)\b(?:quiero|necesito|pod[eé]s|me\s+pod[eé]s|quisiera)\s+",
        "",
        clean_title
    )
    frases_quitar = [
        "en el google calendar", "en google calendar", "en el google calender", "en google calender",
        "al google calendar", "en el calendar", "en calendar", "en el calendario", "al calendario",
        "la agenda de google", "en la agenda", "a la agenda", "la agenda",
        "por favor", "porfa",
        "agendá reunión", "agendame reunión", "agendar reunión", "agendá una reunión", "agendame una reunión",
        "agendá llamada", "agendame llamada", "agendame", "agendate", "agendá", "agendar",
        "registrame una reunión", "registra una reunión", "registrá una reunión", "registrar una reunión",
        "registrame", "registrá", "registrar",
        "anotame una reunión", "anotar reunión", "anotame", "anotá", "anotar",
        "poneme una reunión", "poneme", "poner en la agenda", "sumar a la agenda",
        "crear evento", "creá evento", "programar reunión", "programá reunión"
    ]
    for prefix in sorted(frases_quitar, key=len, reverse=True):
        clean_title = re.sub(rf"(?i)\b{re.escape(prefix)}\b", "", clean_title)

    meses_pat = "|".join(MESES_NOMBRE.keys())
    horas_pat = "|".join(sorted(HORAS_PALABRAS.keys(), key=len, reverse=True))
    clean_title = re.sub(
        rf"(?i)\b(?:para\s+)?(?:el\s+)?(?:pasado\s+mañana|pasado\s+manana|mañana|manana|hoy|lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo|\d{{1,2}}\s+de\s+(?:{meses_pat})(?:\s+de\s+\d{{4}})?|\d{{1,2}}[/.-]\d{{1,2}}(?:[/.-]\d{{2,4}})?)\b",
        "",
        clean_title
    )
    clean_title = re.sub(
        rf"(?i)\b(?:(?:a\s+las|las)\s+(?:\d{{1,2}}(?:[:.]\d{{2}})?|{horas_pat})(?:\s*(?:hs|hrs|h))?|\d{{1,2}}(?:[:.]\d{{2}})?\s*(?:hs|hrs|h))\b(?:\s*(?:y\s+media|y\s+cuarto|menos\s+cuarto))?(?:\s*(?:de\s+la\s+tarde|a\s+la\s+tarde|por\s+la\s+tarde|de\s+la\s+mañana|a\s+la\s+mañana|de\s+la\s+noche|a\s+la\s+noche|del\s+mediod[ií]a|pm|am))?",
        "",
        clean_title
    )
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    clean_title = re.sub(r"^[\s,.-]+|[\s,.-]+$", "", clean_title)
    clean_title = re.sub(r"(?i)^(?:para|una|un|de|a\s+las|las)\s+", "", clean_title).strip()

    if clean_title.lower().startswith("con "):
        clean_title = "Reunión " + clean_title
    elif not clean_title or len(clean_title) < 3:
        clean_title = "Reunión de Consultoría"
    else:
        clean_title = clean_title[0].upper() + clean_title[1:]

    return {
        "intencion": "CREAR_EVENTO",
        "datos": {
            "titulo": clean_title,
            "fecha_hora": start_dt.isoformat(),
            "duracion_minutos": duracion,
            "descripcion": f"Agendado vía Asistente de Telegram: {user_text}"
        }
    }

def _extraer_contexto_tarea(t: str) -> Dict[str, Any]:
    """Extrae cliente, módulo y duración explícita (si fue mencionada) de un pedido de tarea."""
    cliente = detectar_cliente(t)
    modulo = None
    for m in MODULOS_CONOCIDOS:
        if m.lower() in t:
            modulo = m
            break
    tiene_duracion = bool(
        re.search(r"\b(?:hora|horas|hs|min|minuto|minutos)\b|media\s+hora|cuarto\s+de\s+hora|\d+\s*(?:h|hs|m)\b", t)
    )
    minutos = extraer_minutos(t) if tiene_duracion else None
    return {
        "cliente": cliente,
        "modulo": modulo,
        "minutos": minutos,
    }


def parsear_compromisos(t: str, user_text: str, ahora: datetime) -> Optional[Dict[str, Any]]:
    """Detecta carga, consulta o completitud de compromisos/tareas diarias (Horizonte), permitiendo asignar tareas entre consultores."""
    # 1. Completar o tachar tarea: ej "marcar como hecha tarea 3", "completar tarea 3", "tarea 3 lista", "/completar 3"
    m_comp = re.search(
        r"(?:completar|marcar\s+(?:como\s+)?(?:hecha|list[oa])|cerrar|liquidar|finaliz(?:ar|é|e)|termin(?:ar|é|e)|ya\s+hice)\s+(?:el\s+|la\s+)?(?:tarea|compromiso)\s*#?\s*(\d+)",
        t,
    )
    if not m_comp:
        m_comp = re.search(
            r"(?:tarea|compromiso)\s*#?\s*(\d+)\s*(?:lista|listo|hecha|hecho|completada|completado|terminada|terminado|ok|check)",
            t,
        )
    if not m_comp:
        m_comp = re.match(r"^/completar\s*#?(\d+)", t)
    if m_comp:
        ctx_t = _extraer_contexto_tarea(t)
        return {
            "intencion": "COMPLETAR_COMPROMISO",
            "datos": {
                "id_compromiso": int(m_comp.group(1)),
                "minutos": ctx_t["minutos"],
                "cliente": ctx_t["cliente"],
                "modulo": ctx_t["modulo"],
            }
        }

    # Detectar destinatario objetivo si se menciona explícitamente a Juan Luis o Melani
    destinatario = None
    if re.search(r"(?:\b(?:a|para|de)\s+|/tarea\s+(?:a\s+|para\s+)?)(?:juan\s*luis|juan|jl|al\s+jefe|el\s+jefe)\b", t) or \
       re.search(r"\b(?:dejale|dejarle|anotale|cargale|pasale|ponele|ponéle)\s+(?:a\s+)?(?:juan\s*luis|juan|jl|al\s+jefe|el\s+jefe)\b", t):
        destinatario = "JUANLUIS"
    elif re.search(r"(?:\b(?:a|para|de)\s+|/tarea\s+(?:a\s+|para\s+)?)(?:melani|meli|la\s+colaboradora)\b", t) or \
         re.search(r"\b(?:dejale|dejarle|anotale|cargale|pasale|ponele|ponéle)\s+(?:a\s+)?(?:melani|meli)\b", t):
        destinatario = "MELANI"

    # 2. Carga de compromisos
    patrones_carga = [
        # Asignación directa a alguien
        r"(?:dejale|dejarle|asignale|asignarle|anotale|anotarle|cargale|cargarle|pasale|pasarle|ponele|ponéle)\s+(?:una\s+)?tareas?\s+(?:a|para)\s+(?:juan\s*luis|juan|jl|el\s+jefe|melani|meli)[\s:]*",
        r"(?:dejale|dejarle|anotale|anotarle|cargale|cargarle|pasale|pasarle|ponele|ponéle)\s+(?:a|para)\s+(?:juan\s*luis|juan|jl|el\s+jefe|melani|meli)\s+(?:la\s+tarea|las\s+tareas)?[\s:]*",
        r"(?:tarea|tareas|nueva\s+tarea)\s+(?:para|a)\s+(?:juan\s*luis|juan|jl|el\s+jefe|melani|meli)[\s:]*",
        # Carga por fecha / general
        r"(?:tareas?|compromisos?|pendientes?|horizonte)\s+para\s+(?:el\s+)?(mañana|manana|hoy|pasado mañana|pasado manana)[\s:]*",
        r"(?:tareas?|compromisos?|pendientes?)\s+de\s+(?:el\s+)?(mañana|manana|hoy|pasado mañana|pasado manana)[\s:]*",
        r"(?:anota(?:r|me|le)?|guardar?|cargar?)\s+(?:para\s+)?(mañana|manana|hoy|pasado mañana|pasado manana)\s+(?:las\s+)?(?:tareas?|compromisos?|pendientes?)?[\s:]*",
        r"(?:anota(?:r|me|le)?|guardar?|cargar?)\s+(?:una\s+)?(?:tarea|compromiso|pendiente)[\s:]*",
        r"(?:tengo\s+que\s+(?:hacer|sacar)|sacar\s+s[ií]\s+o\s+s[ií]|hay\s+que\s+hacer)\s+(?:para\s+)?(mañana|manana|hoy|pasado mañana|pasado manana)?[\s:]*",
        r"^/tarea\b[\s:]*"
    ]
    
    match_carga = False
    fecha_palabra = "hoy"
    sub_text = ""

    # Caso comando /tarea
    if t.startswith("/tarea ") or t.startswith("/tarea:"):
        match_carga = True
        sub_text = re.sub(r"^/tarea\s+(?:(?:a|para)\s+)?(?:juan\s*luis|juan|jl|el\s+jefe|melani|meli)\s*", "", user_text, flags=re.IGNORECASE)
        sub_text = re.sub(r"^/tarea\s*", "", sub_text, flags=re.IGNORECASE).strip()
        if ":" in sub_text:
            sub_text = sub_text.split(":", 1)[1].strip()

    if not match_carga:
        for pat in patrones_carga:
            m = re.search(pat, t)
            if m:
                match_carga = True
                try:
                    fp = m.group(1).lower()
                    if fp: fecha_palabra = fp
                except Exception:
                    pass
                pos_end = m.end()
                sub_text = user_text[pos_end:].strip()
                if sub_text.startswith(":") or sub_text.startswith("-"):
                    sub_text = sub_text[1:].strip()
                break

    if not match_carga:
        if t.startswith("tareas:") or t.startswith("tareas para mañana") or t.startswith("tareas para manana") or t.startswith("tareas de hoy:") or t.startswith("tareas hoy:"):
            if "mañana" in t or "manana" in t:
                fecha_palabra = "mañana"
            else:
                fecha_palabra = "hoy"
            parts = user_text.split(":", 1)
            if len(parts) > 1:
                match_carga = True
                sub_text = parts[1].strip()

    # Si encontramos sub_text para cargar
    if match_carga and sub_text:
        # Detectar fecha en sub_text si dice "para mañana" o similar
        if "pasado" in fecha_palabra or "pasado mañana" in t or "pasado manana" in t:
            fecha_obj = (ahora + timedelta(days=2)).date()
        elif "mañana" in fecha_palabra or "manana" in fecha_palabra or "para mañana" in t or "para manana" in t:
            fecha_obj = (ahora + timedelta(days=1)).date()
        else:
            fecha_obj = ahora.date()

        # Limpiar prefijos residuales como "de", "que", etc.
        sub_text = re.sub(r"^(?:de|que|es)\s+", "", sub_text, flags=re.IGNORECASE).strip()

        lineas = [l.strip() for l in sub_text.split("\n") if l.strip()]
        tareas_extraidas = []

        if len(lineas) > 1:
            for l in lineas:
                limpia = re.sub(r"^[\d\.\)\-\*•\s]+", "", l).strip()
                if len(limpia) >= 3:
                    tareas_extraidas.append(limpia)
        else:
            partes_num = re.split(r"(?:^|\s)(?:\d+[\.\)]|\-|\*|•)\s+", sub_text)
            partes_num = [p.strip() for p in partes_num if p.strip()]
            if len(partes_num) > 1:
                for p in partes_num:
                    limpia = re.sub(r"^[\d\.\)\-\*•\s]+", "", p).strip()
                    if len(limpia) >= 3:
                        tareas_extraidas.append(limpia)
            else:
                partes_coma = [c.strip() for c in sub_text.split(",") if c.strip()]
                if len(partes_coma) > 1:
                    for c in partes_coma:
                        limpia = re.sub(r"^[\d\.\)\-\*•\s]+", "", c).strip()
                        if len(limpia) >= 3:
                            tareas_extraidas.append(limpia)
                else:
                    limpia = re.sub(r"^[\d\.\)\-\*•\s]+", "", sub_text).strip()
                    if len(limpia) >= 3:
                        tareas_extraidas.append(limpia)

        if tareas_extraidas:
            ctx_t = _extraer_contexto_tarea(t)
            return {
                "intencion": "REGISTRAR_COMPROMISOS",
                "datos": {
                    "fecha_objetivo": fecha_obj.isoformat(),
                    "tareas": tareas_extraidas,
                    "destinatario": destinatario,
                    "cliente": ctx_t["cliente"] or "GENERAL",
                    "modulo": ctx_t["modulo"] or "OTROS",
                    "minutos": ctx_t["minutos"] if ctx_t["minutos"] is not None else 60,
                }
            }

    # 3. Consulta de compromisos / tareas
    es_consulta_tareas = (
        t in ["/tareas", "/compromisos", "/horizonte", "tareas", "compromisos", "horizonte"] or
        any(p in t for p in [
            "mis tareas", "tareas de hoy", "tareas para hoy", "tareas para mañana", "tareas para manana",
            "tareas de mañana", "tareas de manana", "compromisos de hoy", "compromisos para hoy",
            "compromisos de mañana", "compromisos de manana", "compromisos para mañana", "compromisos para manana",
            "que tengo que hacer", "qué tengo que hacer", "que tenemos que hacer", "qué tenemos que hacer",
            "que tengo pendiente", "qué tengo pendiente", "que tenemos pendiente", "qué tenemos pendiente",
            "que tengo para hoy", "qué tengo para hoy", "que tenemos para hoy", "qué tenemos para hoy",
            "que tengo hoy", "qué tengo hoy", "que hay para hoy", "qué hay para hoy",
            "que tengo para mañana", "qué tengo para mañana", "que tenemos para mañana", "qué tenemos para mañana",
            "que hay que sacar", "qué hay que sacar", "cuales son mis tareas", "cuáles son mis tareas",
            "ver tareas", "ver compromisos", "mostrar tareas", "mostrar compromisos", "lista de tareas",
            "tareas pendientes", "pendientes de hoy", "pendientes para hoy",
            "tareas de juan luis", "tareas de juan", "tareas del jefe", "tareas de melani",
            "que tiene que hacer juan", "que tiene que hacer melani", "que tiene juan", "que tiene melani"
        ])
    )
    if es_consulta_tareas:
        if "mañana" in t or "manana" in t:
            f_obj = (ahora + timedelta(days=1)).date()
        else:
            f_obj = ahora.date()

        # Determinar si filtra por alguien específico o ambos
        filtro = None
        if "mis tareas" in t or "que tengo" in t or "tengo que hacer" in t:
            filtro = "MIO"
        elif destinatario:
            filtro = destinatario

        return {
            "intencion": "CONSULTAR_COMPROMISOS",
            "datos": {
                "fecha_objetivo": f_obj.isoformat(),
                "consultor_filtro": filtro
            }
        }

    return None

    return None

class AIService:
    def __init__(self):
        logger.info("Motor NLP local instantáneo inicializado (< 0.1s).")

    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> Optional[str]:
        """Transcribe un mensaje de audio a texto usando Gemini."""
        if not settings.GEMINI_API_KEY:
            logger.warning("No hay GEMINI_API_KEY configurada para transcripción de audio.")
            return None
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = (
                "Transcribe de forma fiel y exacta lo que se dice en este audio en español argentino/latinoamericano. "
                "Devuelve ÚNICAMENTE el texto transcripto, sin comentarios, sin introducciones y sin comillas adicionales."
            )
            modelos = ["gemini-3.5-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite"]
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
            for model_name in modelos:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                            prompt
                        ],
                        config=config
                    )
                    texto = ""
                    if response and response.candidates:
                        for cand in response.candidates:
                            if cand.content and cand.content.parts:
                                for part in cand.content.parts:
                                    if hasattr(part, "text") and part.text:
                                        texto += part.text + " "
                    if not texto and response and response.text:
                        texto = response.text

                    texto = texto.strip().strip('"').strip("'")
                    if texto:
                        logger.info(f"Audio transcripto con éxito ({model_name}): {texto}")
                        return texto
                except Exception as ex_m:
                    logger.warning(f"Error transcribiendo con {model_name}: {ex_m}")
                    continue
            return None
        except Exception as e:
            logger.error(f"Error transcribiendo audio con Gemini: {e}")
            return None

    def parse_user_message(self, user_text: str, user_name: str = "Usuario") -> Dict[str, Any]:
        """Analiza la consulta en menos de 1ms de forma local y ultra precisa."""
        t = user_text.lower().strip()
        tz = pytz.timezone(settings.TIMEZONE)
        ahora = datetime.now(tz)

        # Determinar destinatario (singular para uno mismo, singular para el jefe, o plural para ambos)
        dest = resolver_destinatario(t, user_name)

        # 0. BORRAR / DESHACER ÚLTIMO TICKET
        if any(p in t for p in [
            "borra el ultimo ticket", "borrá el último ticket", "borrar el ultimo ticket", "borrar el último ticket",
            "borra ultimo ticket", "borrá último ticket", "borrar ultimo ticket", "borrar último ticket",
            "elimina el ultimo ticket", "eliminá el último ticket", "eliminar el ultimo ticket", "eliminar el último ticket",
            "elimina ultimo ticket", "eliminá último ticket", "eliminar ultimo ticket", "eliminar último ticket",
            "deshacer ticket", "deshacer el ultimo ticket", "deshacer el último ticket"
        ]):
            return {
                "intencion": "BORRAR_ULTIMO_TICKET",
                "datos": {}
            }

        # 0.1 AGENDAR EN GOOGLE CALENDAR (antes de compromisos para no confundir "anotame reunión mañana" con tarea)
        evento_calendar = parsear_crear_evento(t, user_text, ahora, tz)
        if evento_calendar:
            return evento_calendar

        # 0.2 COMPROMISOS / TAREAS DIARIAS (HORIZONTE)
        comp = parsear_compromisos(t, user_text, ahora)
        if comp:
            return comp

        # 2. Detectar cliente si está en el texto
        cliente_detectado = detectar_cliente(t)

        # Detectar palabra clave técnica
        kw_detectada = None
        for kw in PALABRAS_CLAVE_BUSQUEDA:
            if kw in t:
                # normalizar singulares útiles
                if kw == "padrones": kw_detectada = "padron"
                elif kw == "recibos": kw_detectada = "recibo"
                elif kw == "facturas": kw_detectada = "factura"
                elif kw == "tablas": kw_detectada = "tabla"
                elif kw == "cupones": kw_detectada = "cupon"
                else: kw_detectada = kw
                break

        # 3. Detección rigurosa de si es PREGUNTA / CONSULTA
        signo_pregunta = "?" in t or "¿" in t
        empieza_interrogativa = any(t.startswith(w) for w in [
            "cuant", "que ", "qué ", "q ", "como ", "cómo ", "quien", "quién", "cual", "cuál", "donde", "dónde"
        ])
        contiene_interrogativa = any(re.search(rf"\b{re.escape(w)}\b", t) for w in INTERROGATIVAS)
        contiene_palabra_consulta = any(re.search(rf"\b{re.escape(w)}\b", t) for w in PALABRAS_CONSULTA)
        
        es_frase_consulta = any(p in t for p in [
            "cuantas horas", "cuántas horas", "cuantas hs", "cuántas hs", "cuanto tiempo", "cuánto tiempo",
            "que se hizo", "qué se hizo", "que hicimos", "qué hicimos", "que hizo", "qué hizo", "que cargo", "qué cargó",
            "que cargamos", "qué cargamos", "en que trabajamos", "en qué trabajamos",
            "horas de ayer", "horas ayer", "horas de hoy", "horas hoy", "horas del mes", "horas en el mes",
            "tickets de ayer", "tickets de hoy", "tickets del mes", "resumen de ayer", "resumen de hoy",
            "que hay hoy", "qué hay hoy", "que tenemos hoy", "qué tenemos hoy",
            "que hay mañana", "qué hay mañana", "que tenemos mañana", "qué tenemos mañana",
            "demando mas", "demandó más", "mayor demanda", "ranking", "top clientes"
        ])

        es_pregunta = signo_pregunta or empieza_interrogativa or contiene_interrogativa or contiene_palabra_consulta or es_frase_consulta

        # 4. AGENDA / CALENDARIO (CONSULTAR)
        es_consulta_agenda = (
            any(re.search(rf"\b{re.escape(w)}\b", t) for w in ["agenda", "calendario", "reuniones", "turnos", "compromisos"]) or
            (es_pregunta and any(re.search(rf"\b{re.escape(w)}\b", t) for w in ["reunion", "reunión"])) or
            any(p in t for p in [
                "que hay hoy", "qué hay hoy", "que tenemos hoy", "qué tenemos hoy", "como viene hoy", "cómo viene hoy",
                "que hay mañana", "qué hay mañana", "que tenemos mañana", "qué tenemos mañana", "como viene mañana", "cómo viene mañana",
                "que hay pasado mañana", "qué hay pasado mañana"
            ])
        )
        if es_consulta_agenda:
            return {
                "intencion": "CONSULTAR_AGENDA",
                "datos": resolver_fecha_agenda(t, ahora)
            }

        # 5. REGISTRAR TICKET (SOLO si NO es pregunta y tiene orden de carga o declaración explícita de horas)
        if not es_pregunta:
            tiene_verbo_carga = (
                any(v in t for v in [
                    "cargá", "carga ", "cargar ", "cargame", "cargale", "carguemos",
                    "registrá", "registrar ", "registrame", "registrale",
                    "anotá", "anota ", "anotar ", "anotame", "anotale",
                    "guardar ticket", "guardá ticket", "agregar ticket", "agregá ticket",
                    "te paso una tarea", "te paso tarea", "nueva tarea", "anotar tarea", "cargar tarea",
                    "cargame una tarea", "cargá una tarea", "anotá una tarea", "anotame una tarea",
                    "cargale una tarea", "anotale una tarea", "poner tarea", "poné una tarea", "pone una tarea"
                ]) or
                any(t.startswith(v) for v in ["carg", "registr", "anot", "guard", "agreg"])
            )
            tiene_mencion_duracion = any(w in t for w in [
                "hora", "horas", "hs", "min", "minuto", "minutos",
                "media hora", "hora y media", "un cuarto de hora", "tres cuartos de hora"
            ])
            declaracion_horas = (
                any(w in t.split() for w in ["hice", "estuve", "trabaje", "trabajé", "labure", "laburé", "dedique", "dediqué"]) and
                tiene_mencion_duracion and
                (cliente_detectado is not None or any(m.lower() in t for m in MODULOS_CONOCIDOS))
            )
            carga_directa = (cliente_detectado is not None and tiene_mencion_duracion)

            if tiene_verbo_carga or declaracion_horas or carga_directa:
                minutos = extraer_minutos(t)

                modulo_detectado = "OTROS"
                for m in MODULOS_CONOCIDOS:
                    if m.lower() in t:
                        modulo_detectado = m
                        break

                consultor_asignado = "JUANLUIS" if dest["modo"] == "JEFE" else ("MELANI" if dest["modo"] == "COLABORADOR" else user_name)

                detalle_limpio = limpiar_detalle_tarea(user_text, cliente_detectado)

                return {
                    "intencion": "REGISTRAR_TICKET",
                    "datos": {
                        "cliente": cliente_detectado or "GENERAL",
                        "minutos": minutos,
                        "consultas": detalle_limpio,
                        "respuestas": "Resuelto según requerimiento",
                        "modulo": modulo_detectado,
                        "usuario_cliente": "GENERAL",
                        "atencion": "WHATSAPP",
                        "consultor_asignado": consultor_asignado
                    }
                }

        # 5. DEMANDA O RANKING DE CLIENTES (ej: "qué cliente demandó más el mes pasado", "q cliente demando mas este año", "qué cliente demandó más en el día", "ranking de clientes")
        es_consulta_demanda = (
            any(p in t for p in [
                "demando mas", "demandó más", "demando más", "demandó mas",
                "mas demando", "más demandó", "mas demandó", "más demando",
                "mayor demanda", "mas demanda", "más demanda",
                "demandaron mas", "demandaron más", "mayor carga",
                "mas consumo", "más consumo", "mas consumio", "más consumió",
                "mas insumio", "más insumió",
                "mas horas", "más horas", "mas hs", "más hs", "mas tiempo", "más tiempo", "mayor tiempo",
                "mas se trabajo", "más se trabajó", "mas laburo", "más laburo",
                "mas trabajamos", "más trabajamos", "mas dedicamos", "más dedicamos",
                "mas se dedico", "más se dedicó", "mas pedidos", "más pedidos",
                "mas tickets", "más tickets", "ranking", "top clientes", "top de clientes",
                "primeros clientes", "principales clientes"
            ]) and (
                any(p in t for p in ["cliente", "clientes", "empresa", "empresas", "cuenta", "cuentas"]) or
                any(t.startswith(w) for w in ["que ", "qué ", "q ", "cual ", "cuál ", "quien ", "quién "]) or
                any(w in t.split() for w in ["quien", "quién", "cual", "cuál"]) or
                t.startswith("ranking") or t.startswith("top") or "top" in t.split() or
                "demando" in t or "demandó" in t or "demanda" in t
            )
        )
        if es_consulta_demanda:
            info_periodo = resolver_periodo(t, ahora)
            return {
                "intencion": "RANKING_CLIENTES",
                "datos": {
                    "periodo_tipo": info_periodo["periodo_tipo"],
                    "fecha": info_periodo.get("fecha"),
                    "fecha_desde": info_periodo.get("fecha_desde"),
                    "fecha_hasta": info_periodo.get("fecha_hasta"),
                    "mes": info_periodo.get("mes"),
                    "anio": info_periodo.get("anio"),
                    "etiqueta": info_periodo.get("etiqueta"),
                    "cliente": cliente_detectado
                }
            }

        # 6. CONSULTA DE HORAS (AYER / HOY / ANTEAYER / EN EL DÍA / GENERAL)
        if (
            any(w in t for w in ["ayer", "hoy", "anteayer", "en el dia", "en el día", "del dia", "del día"]) or
            any(p in t for p in ["cuantas horas", "cuántas horas", "cuantas hs", "cuántas hs", "cuanto tiempo", "cuánto tiempo", "cuanto llevamos", "cuánto llevamos"])
        ):
            # Si pregunta explícitamente por HORAS / TIEMPO / TOTAL / BALANCE / RESUMEN
            if any(w in t for w in ["hora", "horas", "hs", "tiempo", "total", "balance", "cuanto", "cuánto", "resumen", "informe", "reporte"]):
                fecha_modo = "ANTEAYER" if "anteayer" in t else ("AYER" if "ayer" in t else "HOY")
                return {
                    "intencion": "CONSULTAR_HORAS",
                    "datos": {
                        "fecha": fecha_modo,
                        "consultor": dest["consultor"],
                        "modo_sujeto": dest["modo"]
                    }
                }

        # 6. CONSULTA DE TAREAS / QUÉ SE HIZO AYER / HOY
        if any(w in t for w in ["ayer", "hoy", "anteayer", "en el dia", "en el día"]):
            if any(p in t for p in [
                "que se hizo", "qué se hizo", "que hicimos", "qué hicimos", "que hizo", "qué hizo",
                "que cargo", "qué cargó", "que cargamos", "qué cargamos", "que hicieron", "qué hicieron",
                "trabajamos", "hicimos", "tareas", "tickets", "hice", "cargo", "cargó"
            ]):
                fecha_modo = "ANTEAYER" if "anteayer" in t else ("AYER" if "ayer" in t else "HOY")
                filtro_con = None if dest["modo"] == "AMBOS" else dest["consultor"]
                return {
                    "intencion": "BUSCAR_HISTORIAL",
                    "datos": {
                        "fecha_relativa": fecha_modo,
                        "es_consulta_horas": False,
                        "cliente": cliente_detectado,
                        "consultor": filtro_con,
                        "modo_sujeto": dest["modo"],
                        "texto_busqueda": kw_detectada
                    }
                }

        # 7. HORAS / RESUMEN DEL MES O AÑO (ej: "resumen del mes pasado", "cuántas horas en el mes", "horas de este año", "total del año")
        if any(w in t for w in ["mes", "mensual", "30 dias", "31 dias", "año", "anio", "anual", "202"]) or any(m in t for m in MESES_NOMBRE.keys()):
            if any(w in t for w in ["hora", "horas", "hs", "total", "cuanto", "cuánto", "tiempo", "hice", "hicimos", "cargo", "cargó", "cargamos", "balance", "resumen", "informe", "reporte", "actividad"]):
                mes_num, anio_num = resolver_mes_anio(t, ahora)
                filtro_con = None if dest["modo"] == "AMBOS" else dest["consultor"]
                return {
                    "intencion": "BUSCAR_HISTORIAL",
                    "datos": {
                        "es_consulta_horas": True,
                        "cliente": cliente_detectado,
                        "consultor": filtro_con,
                        "modo_sujeto": dest["modo"],
                        "mes": mes_num,
                        "anio": anio_num,
                        "texto_busqueda": None
                    }
                }

        # 8. QUÉ SE HIZO / TAREAS (ej: "qué se hizo en Montarfe", "qué se hizo en el mes", "en qué trabajamos", "qué se hizo el mes pasado")
        if any(p in t for p in [
            "que se hizo", "qué se hizo", "que hicimos", "qué hicimos", "que hizo", "qué hizo",
            "que cargo", "qué cargó", "que cargamos", "qué cargamos", "trabajamos", "tareas", "tickets de", "hice", "cargo", "cargó"
        ]):
            mes_num, anio_num = resolver_mes_anio(t, ahora)
            filtro_con = None if dest["modo"] == "AMBOS" else dest["consultor"]
            return {
                "intencion": "BUSCAR_HISTORIAL",
                "datos": {
                    "es_consulta_horas": False,
                    "cliente": cliente_detectado,
                    "consultor": filtro_con,
                    "modo_sujeto": dest["modo"],
                    "mes": mes_num if not kw_detectada else None,
                    "anio": anio_num,
                    "texto_busqueda": kw_detectada
                }
            }

        # 9. RESUMEN O BALANCE GENERAL (ej: "me haces un resumen del mes pasado", "haceme un resumen", "resumen de pasina")
        if any(w in t for w in ["resumen", "balance", "informe", "reporte"]):
            mes_num, anio_num = resolver_mes_anio(t, ahora)
            filtro_con = None if dest["modo"] == "AMBOS" else dest["consultor"]
            return {
                "intencion": "BUSCAR_HISTORIAL",
                "datos": {
                    "es_consulta_horas": True,
                    "cliente": cliente_detectado,
                    "consultor": filtro_con,
                    "modo_sujeto": dest["modo"],
                    "mes": mes_num,
                    "anio": anio_num,
                    "texto_busqueda": None
                }
            }

        # 9. BÚSQUEDA POR PALABRA CLAVE O TEMA ESPECÍFICO (ej: "padrones", "hischeque", "cheques", "recibo", "factura")
        if kw_detectada:
            return {
                "intencion": "BUSCAR_HISTORIAL",
                "datos": {
                    "es_consulta_horas": False,
                    "cliente": cliente_detectado,
                    "consultor": None,
                    "mes": None, # Buscar en cualquier mes
                    "anio": ahora.year,
                    "texto_busqueda": kw_detectada
                }
            }

        # 10. SI MENCIONÓ UN CLIENTE SOLO (ej: "Montarfe", "Palaversich")
        if cliente_detectado:
            return {
                "intencion": "BUSCAR_HISTORIAL",
                "datos": {
                    "es_consulta_horas": False,
                    "cliente": cliente_detectado,
                    "consultor": None,
                    "mes": ahora.month,
                    "anio": ahora.year,
                    "texto_busqueda": None
                }
            }

        # 11. Fallback conversacional
        return {
            "intencion": "CONVERSACION_GENERAL",
            "datos": {
                "texto_original": user_text
            }
        }

    def responder_conversacion_ia(self, user_text: str, user_name: str = "Melani") -> str:
        """Genera una respuesta conversacional natural, descontracturada y con onda argentina usando Gemini."""
        nombre_amigable = "Melani" if "MELANI" in user_name.upper() else ("Juan Luis" if "JUAN" in user_name.upper() else user_name)
        if not settings.GEMINI_API_KEY:
            return f"¡Buenas {nombre_amigable}! 👋 Todo tranqui por acá. Decime nomás si cargamos horas, tareas o chequeamos la agenda."
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
            system_prompt = (
                "Sos el asistente virtual del equipo Grandi (Melani y Juan Luis). "
                "Tu personalidad es relajada, simpática, descontracturada y muy compañera, con tono argentino natural (usás voseo: 'dale', 'che', 'joya', 'de una', 'tranqui', 'decime', '¡buenas!'). "
                "Respondé de forma concisa, cálida y directa (máximo 1 o 2 oraciones breves, sin rodeos ni parrafadas). "
                "NUNCA hables como un robot ni menciones tablas de base de datos como 'bd_dashboard_servicios' ni 'USER'. "
                f"Estás hablando con {nombre_amigable}. "
                "Si te saludan, te agradecen o te hacen charla, respondé con buena onda y deciles que estás listo para darles una mano con lo que haga falta (horas, tareas, reuniones o clientes)."
            )
            
            modelos = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3-flash-preview"]
            for m in modelos:
                try:
                    res = client.models.generate_content(
                        model=m,
                        contents=[user_text],
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                            temperature=0.7,
                            max_output_tokens=150
                        )
                    )
                    texto_out = ""
                    if res and res.candidates:
                        for c in res.candidates:
                            if c.content and c.content.parts:
                                for p in c.content.parts:
                                    if getattr(p, "text", None):
                                        texto_out += p.text
                    if not texto_out and res and getattr(res, "text", None):
                        texto_out = res.text
                    if texto_out and texto_out.strip():
                        return texto_out.strip()
                except Exception as model_err:
                    logger.debug(f"Error con modelo {m}: {model_err}")
            return f"¡Buenas {nombre_amigable}! 👋 Todo tranqui por acá. Decime qué necesitás y lo vemos al toque."
        except Exception as e:
            logger.error(f"Error generando respuesta conversacional: {e}")
            return f"¡Buenas {nombre_amigable}! Decime nomás en qué te doy una mano."

ai_service = AIService()
