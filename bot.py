import os
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, time, date, timedelta
from typing import Optional, Dict, Any, List
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

try:
    from src.config import settings
    from src.database import db
    from src.calendar_service import calendar_service
    from src.ai_service import ai_service, resolver_periodo
except ImportError:
    from config import settings
    from database import db
    from calendar_service import calendar_service
    from ai_service import ai_service, resolver_periodo

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO if not settings.DEBUG else logging.DEBUG
)
logger = logging.getLogger(__name__)

async def safe_reply(update_or_message, text: str, parse_mode=ParseMode.MARKDOWN, reply_markup=None):
    """Envía un mensaje intentando Markdown y haciendo fallback si falla el parsing."""
    if hasattr(update_or_message, "callback_query") and update_or_message.callback_query:
        msg = update_or_message.callback_query.message
    elif hasattr(update_or_message, "message") and update_or_message.message:
        msg = update_or_message.message
    else:
        msg = update_or_message

    try:
        return await msg.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Error parseando markdown, enviando texto plano: {e}")
        clean_text = text.replace("*", "").replace("_", "").replace("`", "")
        return await msg.reply_text(clean_text, reply_markup=reply_markup)

async def send_group_safe(bot, chat_id, text: str, parse_mode=ParseMode.MARKDOWN):
    """Envía un mensaje programado al grupo intentando Markdown y haciendo fallback a texto plano si falla."""
    try:
        return await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except Exception as e:
        logger.warning(f"Error enviando mensaje Markdown al grupo {chat_id}, reintentando en texto plano: {e}")
        clean_text = text.replace("*", "").replace("_", "").replace("`", "")
        return await bot.send_message(chat_id=chat_id, text=clean_text)

def _format_calendar_create_error() -> str:
    """Devuelve un mensaje claro explicando por qué falló la creación del evento en Google Calendar."""
    err = calendar_service.last_errors.get("create", "")
    err_l = err.lower()
    if "invalid_grant" in err_l or "jwt" in err_l:
        return (
            "⚠️ *No pude agendar en Google Calendar porque la clave de acceso (`credentials.json`) fue revocada o es inválida (`Invalid JWT Signature`).*\n\n"
            "👉 Hay que generar una nueva clave JSON para la Service Account en Google Cloud Console y reemplazar `credentials.json`."
        )
    if "403" in err_l or "forbidden" in err_l or "writer" in err_l or "requiredaccesslevel" in err_l:
        return (
            "⚠️ *No tengo permisos de escritura en Google Calendar.*\n\n"
            "👉 Compartí el calendario con el email de la Service Account (`credentials.json`) con el permiso *\"Realizar cambios en eventos\"*."
        )
    if "404" in err_l or "notfound" in err_l:
        return "⚠️ *No se encontró el calendario configurado en `GOOGLE_CALENDAR_ID` o no está compartido con la Service Account.*"
    if "no inicializado" in err_l:
        return "⚠️ *Google Calendar no está conectado porque falta un `credentials.json` válido.*"
    return "⚠️ Che, no pude guardar la reunión en Google Calendar. Probemos de nuevo."

# --- COMANDOS BÁSICOS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start y explica cómo vincularse."""
    user = update.effective_user
    
    # Comprobar si ya está vinculado
    consultor_db = db.get_consultant_by_telegram_id(user.id)
    
    if consultor_db:
        c_raw = str(consultor_db.get("consultor", "")).upper()
        nombre = "Melani" if "MELANI" in c_raw else ("Juan Luis" if "JUAN" in c_raw else consultor_db.get("consultor", user.first_name))
        mensaje = (
            f"👋 ¡Buenas, *{nombre}*! ¿Cómo va todo?\n\n"
            f"Acá estoy para darte una mano con el día a día del equipo. Podés hablarme o mandarme audios 🎙️ bien tranqui:\n\n"
            f"• *Cargar horas:* _\"Cargué 1h y media en Pasina por facturación electrónica\"_\n"
            f"• *Tareas compartidas:* `/tareas` o decime:\n"
            f"  _\"Dejale una tarea a Juan Luis: llamar a Cargill\"_\n"
            f"  _\"Anotale a Melani: revisar facturas de Presea\"_\n"
            f"  _\"Tareas de hoy: 1. Llamar cliente 2. Enviar reporte\"_\n"
            f"• *Google Calendar:* _\"Agendá reunión mañana a las 11hs con Palaversich\"_\n"
            f"• *Ver agenda y horas de hoy:* `/hoy`\n"
            f"• *Consultar horas:* `/horas` o _\"¿Cuántas horas metimos ayer?\"_\n"
            f"• *Clientes:* `/ranking` o _\"¿Qué cliente demandó más este año?\"_\n"
            f"• *Deshacer último ticket:* `/borrar_ultimo`\n\n"
            f"¡Cualquier cosa que necesites, decime nomás!"
        )
    else:
        mensaje = (
            f"👋 ¡Hola, *{user.first_name}*!\n\n"
            f"Tu ID de Telegram es: `{user.id}`\n\n"
            f"Para conectarte con el equipo, vinculate con tu nombre:\n"
            f"`/vincular MELANI` o `/vincular JUAN LUIS`\n\n"
            f"¡Apenas lo hagas ya arrancamos!"
        )
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Devuelve el ID del chat actual (ideal para grupos)."""
    chat = update.effective_chat
    tipo = "Grupo" if chat.type in ["group", "supergroup"] else "Chat Privado"
    texto = (
        f"🆔 Información del Chat:\n\n"
        f"• Tipo: {tipo}\n"
        f"• Nombre: {chat.title or 'Privado'}\n"
        f"• ID: {chat.id}\n"
    )
    await update.message.reply_text(texto)

async def vincular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vincula el Telegram ID actual con un registro en config_consultores."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "Uso: `/vincular TU_NOMBRE` (ej: `/vincular MELANI`)",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    nombre = " ".join(context.args)
    consultor_db = db.link_telegram_consultant(nombre, user.id)

    if consultor_db:
        await update.message.reply_text(
            f"✅ ¡Vinculación exitosa!\n\n"
            f"Consultor: *{consultor_db['consultor']}*\n"
            f"Rol: `{consultor_db.get('rol', 'USER')}`\n\n"
            f"Ya podés empezar a enviarme tus tareas, tickets y consultas.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ No encontré al consultor '{nombre}' en la tabla `config_consultores`.\n"
            f"Usá `/consultores` para ver los nombres válidos registrados.",
            parse_mode=ParseMode.MARKDOWN
        )

async def consultores_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lista los consultores registrados en el sistema."""
    consultores = db.get_consultants()
    if not consultores:
        await update.message.reply_text("ℹ️ No se pudieron listar los consultores o no hay registrados.")
        return

    texto = "👥 *Consultores Registrados:*\n\n"
    for c in consultores:
        texto += f"• `{c}`\n"
    texto += "\nPara vincularte escribí: `/vincular TU_NOMBRE`"
    await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)

async def responder_agenda(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    datos: Optional[Dict[str, Any]] = None
):
    """Muestra los eventos de Google Calendar y, si es hoy o anterior, las horas registradas en bd_dashboard_servicios en dos mensajes separados."""
    tz = pytz.timezone(settings.TIMEZONE)
    hoy = datetime.now(tz).date()

    datos = datos or {}
    fecha_iso = datos.get("fecha_iso")
    fecha_modo = datos.get("fecha", "HOY")
    
    if fecha_iso:
        try:
            target_date = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
        except Exception:
            target_date = hoy
    elif fecha_modo == "MANANA":
        target_date = hoy + timedelta(days=1)
    elif fecha_modo == "PASADO_MANANA":
        target_date = hoy + timedelta(days=2)
    elif fecha_modo == "AYER":
        target_date = hoy - timedelta(days=1)
    else:
        target_date = hoy

    if target_date == hoy:
        etiqueta = f"Hoy ({target_date.strftime('%d/%m/%Y')})"
    elif target_date == hoy + timedelta(days=1):
        etiqueta = f"Mañana ({target_date.strftime('%d/%m/%Y')})"
    elif target_date == hoy + timedelta(days=2):
        etiqueta = f"Pasado Mañana ({target_date.strftime('%d/%m/%Y')})"
    elif target_date == hoy - timedelta(days=1):
        etiqueta = f"Ayer ({target_date.strftime('%d/%m/%Y')})"
    else:
        etiqueta = target_date.strftime("%d/%m/%Y")

    # Botones de navegación rápida entre fechas
    keyboard = [
        [
            InlineKeyboardButton("⏪ Ayer", callback_data="agenda_ayer"),
            InlineKeyboardButton("📅 Hoy", callback_data="agenda_hoy"),
            InlineKeyboardButton("⏩ Mañana", callback_data="agenda_manana"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 1. MENSAJE 1: Google Calendar (Compromisos)
    eventos = calendar_service.get_events_for_date(target_date)

    texto_cal = f"📅 *AGENDA DE {etiqueta.upper()}*\n\n"
    texto_cal += "🗓️ *Compromisos en Google Calendar:*\n"
    texto_cal += "───────────────────────────\n"
    if eventos:
        for ev in eventos:
            start_str = ev['start']
            hora = start_str.split("T")[1][:5] if "T" in start_str else "Todo el día"
            texto_cal += f"• ⏰ `{hora}` — *{ev['summary']}*\n"
    elif calendar_service.last_errors:
        texto_cal += "⚠️ *Aviso de sincronización:* Hubo un error al conectar con Google Calendar.\n"
        for cid, err in calendar_service.last_errors.items():
            if "invalid_grant" in err.lower() or "jwt" in err.lower():
                texto_cal += f"• `{cid}`: Clave de credenciales (`credentials.json`) revocada o desincronizada en Google Cloud.\n"
            elif "notfound" in err.lower() or "404" in err:
                texto_cal += f"• `{cid}`: Calendario no encontrado o no compartido con la Service Account.\n"
            else:
                texto_cal += f"• `{cid}`: {err[:60]}...\n"
        texto_cal += "_(Revisá el archivo credentials.json o los permisos del calendario)._\n"
    else:
        texto_cal += f"• _No hay eventos agendados en el calendario para {etiqueta.lower()}._\n"

    # 2. MENSAJE 2: Tickets Supabase (solo si la fecha es hoy o anterior)
    if target_date <= hoy:
        # Enviamos primero el mensaje del calendario
        await safe_reply(update, texto_cal)

        tickets = db.get_tickets_by_date(target_date)
        if target_date == hoy:
            texto_tickets = f"⏱️ *DASHBOARD DE TICKETS (HOY - {target_date.strftime('%d/%m/%Y')}):*\n"
        else:
            texto_tickets = f"⏱️ *DASHBOARD DE TICKETS ({target_date.strftime('%d/%m/%Y')}):*\n"
        texto_tickets += "───────────────────────────\n"
            
        if tickets:
            total_minutos = 0
            for t in tickets:
                mins = int(t.get("tiempo_res") or 0)
                total_minutos += mins
                hs = mins / 60.0
                con = t.get("consultor", "CONSULTOR")
                cli = t.get("clientes", "CLIENTE")
                mod = t.get("modulo", "OTROS")
                desc = t.get("consultas", "Sin detalle")
                texto_tickets += f"• #{t.get('id_ticket')} *{con}* (`{hs:.2f}h` / {mins}m)\n   🏢 _{cli}_ ({mod}): {desc}\n"
            
            total_hs = total_minutos / 60.0
            texto_tickets += f"\n👉 *Total horas equipo:* `{total_hs:.2f} hs` ({total_minutos} min)"
        else:
            if target_date == hoy:
                texto_tickets += "• _Aún no se cargaron tickets hoy en el sistema._"
            else:
                texto_tickets += "• _No se registraron tickets en el sistema para esta fecha._"

        # Enviamos el segundo mensaje con los botones de acceso rápido
        await safe_reply(update, texto_tickets, reply_markup=reply_markup)
    else:
        # En fechas futuras (como mañana), enviamos el mensaje del calendario con los botones
        await safe_reply(update, texto_cal, reply_markup=reply_markup)

async def hoy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /hoy: muestra agenda y tickets de hoy."""
    await responder_agenda(update, context, {"fecha": "HOY"})

async def responder_consulta_horas(
    update: Update, 
    fecha_modo: str = "HOY", 
    consultor_filtro: str = "TODOS", 
    consultor_usuario: str = "USUARIO",
    modo_sujeto: str = "AMBOS"
):
    """Muestra horas de hoy o de ayer, distinguiendo si es para el usuario, para su jefe, o para ambos."""
    tz = pytz.timezone(settings.TIMEZONE)
    hoy = datetime.now(tz).date()

    if "AYER" in str(fecha_modo).upper():
        target_date = hoy - timedelta(days=1)
        etiqueta = f"Ayer ({target_date.strftime('%d/%m/%Y')})"
    elif "ANTEAYER" in str(fecha_modo).upper():
        target_date = hoy - timedelta(days=2)
        etiqueta = f"Anteayer ({target_date.strftime('%d/%m/%Y')})"
    else:
        target_date = hoy
        etiqueta = f"Hoy ({target_date.strftime('%d/%m/%Y')})"

    tickets = db.get_tickets_by_date(target_date)

    # Identificar sujeto consultado
    nombre_jefe = db.get_boss_name() # "JUANLUIS"
    es_consulta_jefe = (
        modo_sujeto == "JEFE" or 
        (isinstance(consultor_filtro, str) and consultor_filtro.strip().upper() in ["JEFE", "JUANLUIS", "JUAN LUIS"])
    )
    es_consulta_propia = (
        modo_sujeto == "MIO" or 
        consultor_filtro == "MIO" or 
        (isinstance(consultor_filtro, str) and consultor_filtro.strip().upper() == consultor_usuario.strip().upper())
    )
    es_consulta_melani = (
        modo_sujeto == "COLABORADOR" or 
        (isinstance(consultor_filtro, str) and "MELANI" in consultor_filtro.strip().upper())
    )

    # 1. CASO INDIVIDUAL: PARA EL JEFE
    if es_consulta_jefe:
        tickets_jefe = [
            t for t in tickets 
            if str(t.get("consultor", "")).strip().upper() == nombre_jefe.strip().upper()
        ]
        if not tickets_jefe:
            await safe_reply(update, f"ℹ️ *{nombre_jefe}* (tu jefe) no tiene tickets registrados para {etiqueta}.")
            return

        total_mins = sum(int(t.get("tiempo_res") or 0) for t in tickets_jefe)
        resp = f"📊 *Horas de tu jefe (Juan Luis) — {etiqueta}:*\n\n"
        resp += f"⏱️ *Total:* `{total_mins/60.0:.2f} hs` ({total_mins} min en {len(tickets_jefe)} tickets)\n\n"
        resp += "*Detalle por cliente:*\n"
        por_cliente = {}
        for t in tickets_jefe:
            cli = t.get("clientes", "CLIENTE")
            mins = int(t.get("tiempo_res") or 0)
            por_cliente[cli] = por_cliente.get(cli, 0) + mins
        for cli, m in sorted(por_cliente.items(), key=lambda x: x[1], reverse=True):
            resp += f"• *{cli}*: `{m/60.0:.2f} hs` ({m} min)\n"
        await safe_reply(update, resp)
        return

    # 2. CASO INDIVIDUAL: PARA MELANI (cuando consulta el jefe u otro)
    if es_consulta_melani and consultor_usuario != "MELANI":
        tickets_mel = [
            t for t in tickets 
            if "MELANI" in str(t.get("consultor", "")).strip().upper()
        ]
        if not tickets_mel:
            await safe_reply(update, f"ℹ️ *Melani* no tiene tickets registrados para {etiqueta}.")
            return
        total_mins = sum(int(t.get("tiempo_res") or 0) for t in tickets_mel)
        resp = f"📊 *Horas de Melani — {etiqueta}:*\n\n"
        resp += f"⏱️ *Total:* `{total_mins/60.0:.2f} hs` ({total_mins} min en {len(tickets_mel)} tickets)\n\n"
        resp += "*Detalle por cliente:*\n"
        por_cliente = {}
        for t in tickets_mel:
            cli = t.get("clientes", "CLIENTE")
            mins = int(t.get("tiempo_res") or 0)
            por_cliente[cli] = por_cliente.get(cli, 0) + mins
        for cli, m in sorted(por_cliente.items(), key=lambda x: x[1], reverse=True):
            resp += f"• *{cli}*: `{m/60.0:.2f} hs` ({m} min)\n"
        await safe_reply(update, resp)
        return

    # 3. CASO INDIVIDUAL: PROPIO (quien está hablando)
    if es_consulta_propia:
        tickets_propios = [
            t for t in tickets 
            if str(t.get("consultor", "")).strip().upper() == consultor_usuario.strip().upper()
        ]
        if not tickets_propios:
            await safe_reply(update, f"ℹ️ *{consultor_usuario}*, no registraste tickets para {etiqueta}.")
            return

        total_mins = sum(int(t.get("tiempo_res") or 0) for t in tickets_propios)
        resp = f"📊 *Tus horas de {etiqueta} ({consultor_usuario}):*\n\n"
        resp += f"⏱️ *Total:* `{total_mins/60.0:.2f} hs` ({total_mins} min en {len(tickets_propios)} tickets)\n\n"
        resp += "*Detalle por cliente:*\n"
        por_cliente = {}
        for t in tickets_propios:
            cli = t.get("clientes", "CLIENTE")
            mins = int(t.get("tiempo_res") or 0)
            por_cliente[cli] = por_cliente.get(cli, 0) + mins
        for cli, m in sorted(por_cliente.items(), key=lambda x: x[1], reverse=True):
            resp += f"• *{cli}*: `{m/60.0:.2f} hs` ({m} min)\n"
        await safe_reply(update, resp)
        return

    # 4. CASO PLURAL: AMBOS (todo el equipo)
    if not tickets:
        await safe_reply(update, f"ℹ️ No hay tickets registrados para {etiqueta}.")
        return

    resumen_consultor = {}
    resumen_cliente = {}
    cliente_por_consultor = {}
    total_mins = 0
    for t in tickets:
        con = t.get("consultor", "CONSULTOR").strip().upper()
        cli = t.get("clientes", "CLIENTE").strip().upper()
        mins = int(t.get("tiempo_res") or 0)
        resumen_consultor[con] = resumen_consultor.get(con, 0) + mins
        resumen_cliente[cli] = resumen_cliente.get(cli, 0) + mins
        if cli not in cliente_por_consultor:
            cliente_por_consultor[cli] = set()
        cliente_por_consultor[cli].add(con)
        total_mins += mins

    resp = f"👥 *Horas de ambos (Equipo) — {etiqueta}:*\n\n"
    resp += "*Por consultor:*\n"
    for c, m in resumen_consultor.items():
        resp += f"• 👤 *{c}*: `{m/60.0:.2f} hs` ({m} min)\n"
    resp += f"\n🏆 *Total acumulado de ambos:* `{total_mins/60.0:.2f} hs` ({total_mins} min en {len(tickets)} tickets)\n\n"
    resp += "*Detalle por cliente:*\n"
    for cli, m in sorted(resumen_cliente.items(), key=lambda x: x[1], reverse=True):
        consultores_cli = ", ".join(cliente_por_consultor.get(cli, []))
        resp += f"• *{cli}*: `{m/60.0:.2f} hs` ({consultores_cli})\n"

    await safe_reply(update, resp)

async def horas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el total de horas (hoy o ayer si se indica)."""
    user = update.effective_user
    consultor_db = db.get_consultant_by_telegram_id(user.id)
    c_nombre = consultor_db["consultor"] if consultor_db else user.first_name.upper()
    modo = "AYER" if context.args and "ayer" in context.args[0].lower() else "HOY"
    await responder_consulta_horas(update, fecha_modo=modo, consultor_filtro="TODOS", consultor_usuario=c_nombre)

NOMBRES_MESES_ESP = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def formatear_resultado_historial(
    tickets: list, 
    cliente_buscado: str = None, 
    texto_buscado: str = None, 
    fecha_exacta: date = None,
    mes: int = None, 
    anio: int = None, 
    es_consulta_horas: bool = False,
    consultor_buscado: str = None,
    modo_sujeto: str = "AMBOS",
    consultor_usuario: str = "USUARIO"
) -> str:
    """Formatea la respuesta de tickets de forma instantánea y legible."""
    nom_mes = NOMBRES_MESES_ESP.get(mes, str(mes)) if mes else ""
    str_periodo_mes = f"{nom_mes} {anio}" if mes else (f"Año {anio}" if anio else "")

    if not tickets:
        suj_txt = ""
        if consultor_buscado:
            if consultor_buscado.strip().upper() == consultor_usuario.strip().upper():
                suj_txt = f" de {consultor_usuario}"
            elif consultor_buscado.strip().upper() == "JUANLUIS":
                suj_txt = " de tu jefe (Juan Luis)"
            else:
                suj_txt = f" de {consultor_buscado}"
        elif modo_sujeto == "AMBOS":
            suj_txt = " del equipo"

        det = f" para *{cliente_buscado}*" if cliente_buscado else ""
        if texto_buscado: det += f" sobre '_{texto_buscado}_'"
        if fecha_exacta:
            periodo = f" el {fecha_exacta.strftime('%d/%m/%Y')}"
        else:
            periodo = f" en {str_periodo_mes}" if str_periodo_mes else ""
        return f"ℹ️ No encontré tickets registrados{suj_txt}{det}{periodo}."

    total_mins = sum(int(t.get("tiempo_res") or 0) for t in tickets)
    total_hs = total_mins / 60.0
    periodo_txt = f"{fecha_exacta.strftime('%d/%m/%Y')}" if fecha_exacta else str_periodo_mes

    # 1. Caso resumen de horas
    if es_consulta_horas:
        if consultor_buscado:
            if consultor_buscado.strip().upper() == consultor_usuario.strip().upper():
                titulo = f"📊 *Tus horas ({periodo_txt})*\n\n"
            elif consultor_buscado.strip().upper() == "JUANLUIS":
                titulo = f"📊 *Horas de tu jefe (Juan Luis) — ({periodo_txt})*\n\n"
            else:
                titulo = f"📊 *Horas de {consultor_buscado} ({periodo_txt})*\n\n"
        else:
            titulo = f"👥 *Balance de Horas de ambos ({periodo_txt})*\n\n"

        resp = titulo
        resp += f"⏱️ *Total:* `{total_hs:.2f} hs` ({total_mins} min en {len(tickets)} tickets)\n\n"
        
        # Desglose por consultor si hay más de uno y no se buscó uno específico
        por_con = {}
        for t in tickets:
            con = t.get("consultor", "CONSULTOR").strip().upper()
            por_con[con] = por_con.get(con, 0) + int(t.get("tiempo_res") or 0)
        
        if len(por_con) > 1 and not consultor_buscado:
            resp += "*Por consultor:*\n"
            for con, m in sorted(por_con.items(), key=lambda x: x[1], reverse=True):
                resp += f"• 👤 *{con}*: `{m/60.0:.2f} hs` ({m} min)\n"
            resp += "\n"

        resp += "*Detalle por cliente:*\n"
        por_cli = {}
        for t in tickets:
            c = t.get("clientes", "CLIENTE").strip().upper()
            por_cli[c] = por_cli.get(c, 0) + int(t.get("tiempo_res") or 0)
        for c, m in sorted(por_cli.items(), key=lambda x: x[1], reverse=True):
            resp += f"• *{c}*: `{m/60.0:.2f} hs` ({m} min)\n"
        return resp

    # 2. Caso tareas o búsqueda por tema
    header = "📋 *Tareas registradas"
    if cliente_buscado: header += f" en {cliente_buscado}"
    if texto_buscado: header += f" sobre '{texto_buscado}'"
    if fecha_exacta:
        periodo_txt = f" ({fecha_exacta.strftime('%d/%m/%Y')})"
    elif mes:
        periodo_txt = f" ({str_periodo_mes})"
    else:
        periodo_txt = ""
    header += f"{periodo_txt}* ({len(tickets)} tickets - `{total_hs:.2f} hs`):\n\n"

    lineas = []
    for t in tickets[:8]:
        t_id = t.get("id_ticket")
        fe = t.get("fe_consult")
        cli = t.get("clientes", "CLIENTE")
        mod = t.get("modulo", "OTROS")
        hs = (int(t.get("tiempo_res") or 0)) / 60.0
        desc = t.get("consultas", "Sin detalle")
        
        prefijo = f"• *#{t_id}* (`{fe}`) *{hs:.2f}h*"
        if not cliente_buscado:
            prefijo += f" _{cli}_"
        prefijo += f" [{mod}]:\n  {desc}\n"
        lineas.append(prefijo)

    res = header + "\n".join(lineas)
    if len(tickets) > 8:
        res += f"\n_(Mostrando 8 de {len(tickets)} tickets encontrados)_"
    return res

async def responder_ranking_clientes(update: Update, datos: Dict[str, Any]):
    """Calcula y muestra el ranking de demanda de clientes para un período determinado."""
    periodo_tipo = datos.get("periodo_tipo", "MES")
    target_fecha = datos.get("fecha")
    fecha_desde = datos.get("fecha_desde")
    fecha_hasta = datos.get("fecha_hasta")
    mes = datos.get("mes")
    anio = datos.get("anio")
    etiqueta = datos.get("etiqueta", "el período")
    cliente_especifico = datos.get("cliente")

    # Obtener tickets según período
    if periodo_tipo == "DIA" and target_fecha:
        tickets = db.search_tickets(fecha=target_fecha, limit=5000)
    elif periodo_tipo == "SEMANA" and fecha_desde and fecha_hasta:
        meses = {fecha_desde.month, fecha_hasta.month}
        anios = {fecha_desde.year, fecha_hasta.year}
        raw_tickets = []
        for a in anios:
            for m in meses:
                raw_tickets.extend(db.search_tickets(mes=m, anio=a, limit=5000))
        tickets = []
        for t in raw_tickets:
            fe_str = t.get("fe_consult")
            if fe_str:
                try:
                    d_t = datetime.strptime(fe_str, "%d/%m/%Y").date()
                    if fecha_desde <= d_t <= fecha_hasta:
                        tickets.append(t)
                except Exception:
                    pass
    elif periodo_tipo == "ANIO" and anio:
        tickets = db.search_tickets(anio=anio, limit=5000)
    elif periodo_tipo == "MES" and mes and anio:
        tickets = db.search_tickets(mes=mes, anio=anio, limit=5000)
    else:
        tz = pytz.timezone(settings.TIMEZONE)
        ahora = datetime.now(tz)
        tickets = db.search_tickets(mes=ahora.month, anio=ahora.year, limit=5000)

    if not tickets:
        await safe_reply(update, f"ℹ️ No se registraron tickets ni demanda de clientes en *{etiqueta}*.")
        return

    # Si se consultó por un cliente específico
    if cliente_especifico:
        tickets_cli = [t for t in tickets if str(t.get("clientes", "")).strip().upper() == cliente_especifico.strip().upper()]
        total_mins_general = sum(int(t.get("tiempo_res") or 0) for t in tickets)
        if not tickets_cli:
            await safe_reply(update, f"ℹ️ *{cliente_especifico}* no tuvo tickets ni demanda registrada en *{etiqueta}*.")
            return

        mins_cli = sum(int(t.get("tiempo_res") or 0) for t in tickets_cli)
        hs_cli = mins_cli / 60.0
        pct_cli = (mins_cli / total_mins_general * 100.0) if total_mins_general > 0 else 0

        resp = f"📊 *Demanda de {cliente_especifico} — {etiqueta}*\n\n"
        resp += f"⏱️ *Tiempo acumulado:* `{hs_cli:.2f} hs` ({mins_cli} min en {len(tickets_cli)} tickets)\n"
        resp += f"📈 *Participación:* `{pct_cli:.1f}%` del total del período (`{total_mins_general/60.0:.2f} hs`)\n"
        await safe_reply(update, resp)
        return

    # Agregación general por cliente
    por_cliente = {}
    tickets_por_cliente = {}
    total_minutos_periodo = 0

    for t in tickets:
        cli = (t.get("clientes") or "GENERAL").strip().upper()
        mins = int(t.get("tiempo_res") or 0)
        por_cliente[cli] = por_cliente.get(cli, 0) + mins
        tickets_por_cliente[cli] = tickets_por_cliente.get(cli, 0) + 1
        total_minutos_periodo += mins

    if total_minutos_periodo == 0:
        await safe_reply(update, f"ℹ️ Se encontraron tickets en *{etiqueta}*, pero sin minutos registrados.")
        return

    ranking = sorted(por_cliente.items(), key=lambda x: x[1], reverse=True)
    ganador_cli, ganador_mins = ranking[0]
    ganador_hs = ganador_mins / 60.0
    ganador_cant = tickets_por_cliente.get(ganador_cli, 0)
    ganador_pct = (ganador_mins / total_minutos_periodo) * 100.0
    total_hs_periodo = total_minutos_periodo / 60.0

    resp = f"📊 *Demanda de Clientes — {etiqueta}*\n\n"
    resp += f"🏆 *Cliente con mayor demanda:*\n"
    resp += f"🥇 *{ganador_cli}*\n"
    resp += f"⏱️ `{ganador_hs:.2f} hs` ({ganador_mins} min • {ganador_cant} tickets • {ganador_pct:.1f}% del total)\n\n"

    if len(ranking) > 1:
        resp += "━━━━━━━━━━━━━━━━━━━\n"
        resp += "📈 *Ranking Completo de Clientes:*\n"
        medallas = ["🥇", "🥈", "🥉"]
        for idx, (cli, mins) in enumerate(ranking, 1):
            hs = mins / 60.0
            cant = tickets_por_cliente.get(cli, 0)
            pct = (mins / total_minutos_periodo) * 100.0
            med = medallas[idx - 1] if idx <= 3 else f"{idx}."
            resp += f"{med} *{cli}*: `{hs:.2f} hs` ({cant} tickets • {pct:.1f}%)\n"
        resp += "\n"

    resp += f"📌 *Total del período:* `{total_hs_periodo:.2f} hs` en `{len(tickets)}` tickets."
    await safe_reply(update, resp)

async def ranking_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ranking [mes pasado | este año | hoy | etc.]: muestra el ranking de demanda de clientes."""
    args_txt = " ".join(context.args) if context.args else ""
    user_text = f"ranking clientes {args_txt}".strip()
    tz = pytz.timezone(settings.TIMEZONE)
    ahora = datetime.now(tz)
    info_p = resolver_periodo(user_text, ahora)
    datos = {
        "periodo_tipo": info_p["periodo_tipo"],
        "fecha": info_p.get("fecha"),
        "fecha_desde": info_p.get("fecha_desde"),
        "fecha_hasta": info_p.get("fecha_hasta"),
        "mes": info_p.get("mes"),
        "anio": info_p.get("anio"),
        "etiqueta": info_p.get("etiqueta")
    }
    await responder_ranking_clientes(update, datos)

# --- MENSAJES DE TEXTO Y LENGUAJE NATURAL ---

def _nombre_corto(nombre: Optional[str]) -> str:
    """Formatea un nombre de consultor para mensajes amigables."""
    n = str(nombre or "").upper()
    if "MELANI" in n:
        return "Melani"
    if "JUAN" in n:
        return "Juan Luis"
    return str(nombre or "Equipo")

async def _ejecutar_completar_compromiso(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id_origen: Optional[int],
    id_comp: int,
    completado_por: str,
    minutos_override: Optional[int] = None,
    cliente_override: Optional[str] = None,
    modulo_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Completa un compromiso, genera su ticket CERRADO y envía notificaciones al grupo y asignador."""
    res = db.completar_compromiso(
        id_comp,
        completado_por=completado_por,
        minutos_override=minutos_override,
        cliente_override=cliente_override,
        modulo_override=modulo_override,
    )
    if not res.get("ok"):
        return res

    comp = res.get("compromiso") or {}
    ticket = res.get("ticket") or {}
    id_ticket = res.get("id_ticket")
    quien = _nombre_corto(res.get("completado_por") or completado_por)
    tarea_txt = comp.get("tarea", f"Tarea #{id_comp}")
    cliente_txt = ticket.get("clientes") or comp.get("cliente") or "GENERAL"
    modulo_txt = ticket.get("modulo") or comp.get("modulo") or "OTROS"
    tiempo_min = ticket.get("tiempo_res") or comp.get("tiempo_estimado_min") or 60

    if id_ticket:
        aviso_ticket = (
            f"🎫 *Ticket #{id_ticket} creado y CERRADO automáticamente*\n"
            f"🏢 *Cliente:* {cliente_txt} | 📁 *Módulo:* {modulo_txt}\n"
            f"⏱️ *Tiempo imputado:* `{tiempo_min} min` (`{float(tiempo_min) / 60.0:.2f} hs`)"
        )
    else:
        aviso_ticket = "⚠️ _La tarea quedó completada, pero no se pudo generar el ticket automático en Supabase._"

    msg_respuesta = (
        f"🎉 *¡Tarea #{id_comp} completada por {quien}!*\n"
        f"📝 *Detalle:* {tarea_txt}\n\n"
        f"{aviso_ticket}"
    )
    res["mensaje"] = msg_respuesta

    group_id_raw = getattr(settings, "TELEGRAM_GROUP_CHAT_ID", None)
    if group_id_raw:
        try:
            group_id = int(str(group_id_raw).strip())
            if chat_id_origen != group_id:
                await send_group_safe(
                    context.bot,
                    group_id,
                    f"📢 *Aviso de tarea completada*\n\n{msg_respuesta}",
                )
        except Exception as e:
            logger.warning(f"No se pudo notificar al grupo sobre tarea #{id_comp}: {e}")

    origen = str(comp.get("origen") or "")
    if origen.startswith("telegram:"):
        asignador = origen.split(":", 1)[1].strip().upper()
        if asignador and asignador != str(completado_por or "").strip().upper():
            tg_asig = db.get_consultant_telegram_id(asignador)
            if tg_asig and tg_asig != chat_id_origen and str(tg_asig) != str(group_id_raw or "").strip():
                try:
                    await send_group_safe(
                        context.bot,
                        tg_asig,
                        f"🔔 *{_nombre_corto(completado_por)} completó la tarea #{id_comp} que le asignaste:*\n"
                        f"📝 {tarea_txt}\n{aviso_ticket}",
                    )
                except Exception as e:
                    logger.warning(f"No se pudo avisar por privado al asignador {asignador}: {e}")

    return res

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    texto_override: Optional[str] = None,
    tipo_entrada: str = "texto",
):
    """Interpreta el mensaje con IA, registra el pedido en Supabase y ejecuta la acción correspondiente."""
    user = update.effective_user
    texto_usuario = texto_override or (update.effective_message.text if update.effective_message else None)
    if not texto_usuario:
        return

    consultor_db = db.get_consultant_by_telegram_id(user.id)
    consultor_nombre = consultor_db["consultor"] if consultor_db else user.first_name.upper()
    chat_id = update.effective_chat.id if update.effective_chat else None

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        analisis = ai_service.parse_user_message(texto_usuario, consultor_nombre)
        intencion = analisis.get("intencion")
        datos = analisis.get("datos", {})
    except Exception as e:
        logger.error(f"Error parseando mensaje: {e}")
        analisis = {"respuesta_amigable": "Disculpá, no pude interpretar ese mensaje."}
        intencion = "CONVERSACION_GENERAL"
        datos = {}

    pedido_logged = False
    reg_destinatario = datos.get("destinatario") or datos.get("consultor_asignado")
    reg_cliente = datos.get("cliente")
    reg_modulo = datos.get("modulo")
    reg_estado = "registrado"
    reg_id_compromiso = None
    reg_id_ticket = None
    reg_detalle = None

    try:
        if intencion == "REGISTRAR_TICKET":
            if not consultor_db:
                reg_estado = "requiere_vinculacion"
                reg_detalle = "Usuario no vinculado"
                await update.message.reply_text(
                    "⚠️ Para registrar tickets en el sistema oficial, primero vinculá tu usuario con:\n"
                    "`/vincular TU_NOMBRE`  _(ej: `/vincular MELANI`)_\n\n"
                    "Usa `/consultores` para ver los nombres válidos.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            cliente = datos.get("cliente", "GENERAL")
            minutos = int(datos.get("minutos", 60))
            consultas = datos.get("consultas", texto_usuario)
            respuestas = datos.get("respuestas", "Resuelto según requerimiento")
            modulo = datos.get("modulo", "OTROS")
            usuario_cliente = datos.get("usuario_cliente", "GENERAL")
            atencion = datos.get("atencion", "WHATSAPP")

            consultor_asignado = datos.get("consultor_asignado") or consultor_nombre
            reg_destinatario = consultor_asignado
            reg_cliente = cliente
            reg_modulo = modulo

            ticket = db.create_ticket(
                consultor=consultor_asignado,
                cliente=cliente,
                tiempo_res_minutos=minutos,
                consultas=consultas,
                respuestas=respuestas,
                usuario_cliente=usuario_cliente,
                modulo=modulo,
                atencion=atencion
            )

            if ticket:
                hs = minutos / 60.0
                id_t = ticket.get('id_ticket')
                reg_id_ticket = id_t
                reg_estado = "ticket_creado"
                reg_detalle = ticket.get('consultas')
                c_tag = str(ticket.get('consultor') or consultor_asignado).upper()
                c_tag_clean = "Melani" if "MELANI" in c_tag else ("Juan Luis" if "JUAN" in c_tag else c_tag)
                resp = (
                    f"✅ *¡Anotadísimo! Cargué `{hs:.2f} hs` en {ticket.get('clientes')}*\n\n"
                    f"👤 *Para:* {c_tag_clean}\n"
                    f"📝 *Detalle:* {ticket.get('consultas')}\n"
                    f"📁 *Módulo:* {ticket.get('modulo')} _(Ticket #{id_t})_"
                )
                kb = [[InlineKeyboardButton("🗑️ Deshacer / Borrar", callback_data=f"borrar_ticket_{id_t}")]]
                await safe_reply(update, resp, reply_markup=InlineKeyboardMarkup(kb))
            else:
                reg_estado = "error"
                reg_detalle = "Error al guardar ticket"
                resp = "⚠️ Che, hubo un temita al guardar las horas en la base. Probá de nuevo en un ratito."
                await safe_reply(update, resp)

        elif intencion == "BORRAR_ULTIMO_TICKET":
            ultimo = db.get_last_ticket_by_consultant(consultor_nombre)
            if not ultimo:
                reg_estado = "no_encontrado"
                await safe_reply(update, "⚠️ No encontré ningún ticket tuyo reciente para borrar.")
                return

            id_t = ultimo.get("id_ticket")
            reg_id_ticket = id_t
            reg_cliente = ultimo.get("clientes")
            reg_modulo = ultimo.get("modulo")
            ok = db.delete_ticket(id_t, consultor=consultor_nombre or user.first_name)
            if ok:
                reg_estado = "ticket_borrado"
                await safe_reply(
                    update,
                    f"🗑️ *Listo, ya borré el ticket #{id_t} de {ultimo.get('clientes')}.*\n"
                    f"⏱️ Eran `{ultimo.get('tiempo_res')} min` en _{ultimo.get('consultas')}_."
                )
            else:
                reg_estado = "error"
                await safe_reply(update, f"⚠️ Che, no pude borrar el ticket #{id_t}.")

        elif intencion == "CREAR_EVENTO":
            titulo = datos.get("titulo", "Reunión")
            fecha_hora_str = datos.get("fecha_hora")
            duracion = int(datos.get("duracion_minutos", 60))
            desc = datos.get("descripcion", "")
            reg_detalle = titulo

            try:
                start_dt = datetime.fromisoformat(fecha_hora_str)
                # 1. Comprobar si hay conflictos en Google Calendar
                conflictos = calendar_service.check_conflicts(start_dt, duration_minutes=duracion)
                if conflictos:
                    conf = conflictos[0]
                    conf_titulo = conf.get("summary", "Evento agendado")
                    dt_s = conf.get("dt_start")
                    dt_e = conf.get("dt_end")
                    h_inicio = dt_s.strftime("%H:%M") if dt_s else "horario ocupado"
                    h_fin = dt_e.strftime("%H:%M") if dt_e else ""
                    rango_hora = f"{h_inicio} a {h_fin} hs" if h_fin else h_inicio

                    context.user_data["evento_pendiente"] = {
                        "titulo": titulo,
                        "start_datetime_iso": start_dt.isoformat(),
                        "duracion": duracion,
                        "desc": desc,
                        "conflicto_titulo": conf_titulo
                    }

                    keyboard = [
                        [
                            InlineKeyboardButton("⚡ Agendar de todas formas", callback_data="agendar_forzar"),
                            InlineKeyboardButton("✏️ Mover +1h", callback_data="mover_evento_1h")
                        ],
                        [
                            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_evento")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    reg_estado = "conflicto_agenda"
                    aviso = (
                        f"⚠️ *Conflicto de agenda detectado*\n\n"
                        f"No podés agendar *\"{titulo}\"* el {start_dt.strftime('%d/%m')} a las {start_dt.strftime('%H:%M')} hs porque ya tenés:\n"
                        f"📌 *\"{conf_titulo}\"* de {rango_hora}.\n\n"
                        f"¿Qué preferís hacer?"
                    )
                    await safe_reply(update, aviso, reply_markup=reply_markup)
                    return

                # Si no hay conflicto, crear normalmente
                evento = calendar_service.create_event(
                    summary=titulo,
                    start_datetime=start_dt,
                    duration_minutes=duracion,
                    description=desc
                )
                if evento:
                    reg_estado = "evento_agendado"
                    link = evento.get("htmlLink", "")
                    link_text = f"\n🔗 [Ver en Google Calendar]({link})" if link else ""
                    resp = (
                        f"📅 *¡Reunión agendada! Nos vemos ahí:*\n\n"
                        f"📌 *{titulo}*\n"
                        f"🗓️ *Cuándo:* {start_dt.strftime('%d/%m/%Y')} a las `{start_dt.strftime('%H:%M')} hs`\n"
                        f"⏳ *Duración:* {duracion} min{link_text}"
                    )
                else:
                    reg_estado = "error"
                    resp = _format_calendar_create_error()
            except Exception as e:
                logger.error(f"Error parseando fecha de evento: {e}")
                reg_estado = "error"
                resp = "⚠️ No llegué a entender bien el día y la hora. Decime por ejemplo: _'Agendá mañana a las 11hs con Palaversich'_."

            await safe_reply(update, resp)

        elif intencion == "REGISTRAR_COMPROMISOS":
            fecha_obj_str = datos.get("fecha_objetivo")
            tareas = datos.get("tareas", [])
            destinatario = (datos.get("destinatario") or consultor_nombre).strip().upper()
            cliente_comp = datos.get("cliente") or "GENERAL"
            modulo_comp = datos.get("modulo") or "OTROS"
            minutos_comp = int(datos.get("minutos") or 60)
            reg_destinatario = destinatario
            reg_cliente = cliente_comp
            reg_modulo = modulo_comp
            try:
                fecha_obj = datetime.fromisoformat(fecha_obj_str).date()
            except Exception:
                fecha_obj = datetime.now(pytz.timezone(settings.TIMEZONE)).date()

            guardadas = []
            for t_item in tareas:
                c = db.crear_compromiso(
                    consultor=destinatario,
                    tarea=t_item,
                    fecha_objetivo=fecha_obj,
                    origen=f"telegram:{consultor_nombre}",
                    cliente=cliente_comp,
                    modulo=modulo_comp,
                    tiempo_estimado_min=minutos_comp,
                )
                if c:
                    guardadas.append(c)
                    db.registrar_pedido_bot(
                        mensaje_original=texto_usuario,
                        tipo_entrada=tipo_entrada,
                        consultor=consultor_nombre,
                        destinatario=destinatario,
                        intencion="REGISTRAR_COMPROMISOS",
                        cliente=cliente_comp,
                        modulo=modulo_comp,
                        estado="pendiente",
                        id_compromiso=c.get("id"),
                        detalle_resultado=c.get("tarea"),
                        telegram_user_id=user.id,
                        telegram_chat_id=chat_id,
                    )

            if guardadas:
                pedido_logged = True
                dia_txt = "mañana" if fecha_obj > datetime.now(pytz.timezone(settings.TIMEZONE)).date() else "hoy"
                fecha_fmt = fecha_obj.strftime('%d/%m/%Y')

                dest_nombre = _nombre_corto(destinatario)
                cons_nombre = _nombre_corto(consultor_nombre)

                if destinatario != consultor_nombre.upper():
                    resp = f"🎯 *Tarea asignada a {dest_nombre} (por {cons_nombre}) — para {dia_txt} ({fecha_fmt}):*\n\n"
                else:
                    resp = f"🎯 *Compromiso guardado para vos ({dest_nombre}) — para {dia_txt} ({fecha_fmt}):*\n\n"

                keyboard = []
                for item in guardadas:
                    resp += f"• *#{item['id']}* {item['tarea']}\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ #{item['id']} {item['tarea'][:25]}", callback_data=f"completar_tarea_{item['id']}")
                    ])
                resp += f"\n_Al completarla se crea y cierra su ticket automático. Tocá ✅ o decí 'tarea #{guardadas[0]['id']} lista'._"
                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                await safe_reply(update, resp, reply_markup=reply_markup)
            else:
                reg_estado = "error"
                await safe_reply(update, "⚠️ No pude registrar las tareas. Intentá de nuevo.")

        elif intencion == "CONSULTAR_COMPROMISOS":
            fecha_obj_str = datos.get("fecha_objetivo")
            filtro_cons = datos.get("consultor_filtro")
            try:
                fecha_obj = datetime.fromisoformat(fecha_obj_str).date()
            except Exception:
                fecha_obj = datetime.now(pytz.timezone(settings.TIMEZONE)).date()

            if filtro_cons == "MIO":
                target_cons = consultor_nombre
            elif filtro_cons in ["JUANLUIS", "MELANI"]:
                target_cons = filtro_cons
            else:
                target_cons = None

            pendientes = db.obtener_compromisos(
                consultor=target_cons,
                fecha_objetivo=fecha_obj,
                estado="pendiente"
            )
            completadas = db.obtener_compromisos(
                consultor=target_cons,
                fecha_objetivo=fecha_obj,
                estado="completada"
            )

            dia_txt = "HOY" if fecha_obj == datetime.now(pytz.timezone(settings.TIMEZONE)).date() else f"EL {fecha_obj.strftime('%d/%m/%Y')}"
            fecha_fmt = fecha_obj.strftime('%d/%m/%Y')

            if not pendientes and not completadas:
                if target_cons:
                    resp = f"✨ *{target_cons} no tiene tareas anotadas para {dia_txt.lower()}.*"
                else:
                    resp = f"✨ *No hay tareas registradas para {dia_txt.lower()} ({fecha_fmt}).*\n\nPodés dejar una tarea diciendo ej:\n• _\"Dejale una tarea a Juan Luis: llamar a Cargill\"_\n• _\"Tarea para Melani: revisar facturas\"_\n• _\"Tareas de hoy: 1. Llamar cliente 2. Enviar reporte\"_"
                await safe_reply(update, resp)
                return

            resp = f"🎯 *HORIZONTE DE TAREAS ({dia_txt} - {fecha_fmt}):*\n"
            resp += "───────────────────────────\n\n"
            keyboard = []

            pendientes_melani = [p for p in pendientes if "MELANI" in str(p.get("consultor", "")).upper()]
            pendientes_jl = [p for p in pendientes if "JUAN" in str(p.get("consultor", "")).upper()]
            otros_pendientes = [p for p in pendientes if p not in pendientes_melani and p not in pendientes_jl]

            if pendientes_melani:
                resp += "👩‍💼 *Tareas de MELANI:*\n"
                for p in pendientes_melani:
                    resp += f"• [ ] *#{p['id']}* {p['tarea']}\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ #{p['id']} (Melani) {p['tarea'][:20]}", callback_data=f"completar_tarea_{p['id']}")
                    ])
                resp += "\n"

            if pendientes_jl:
                resp += "👨‍💼 *Tareas de JUAN LUIS:*\n"
                for p in pendientes_jl:
                    resp += f"• [ ] *#{p['id']}* {p['tarea']}\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ #{p['id']} (Juan) {p['tarea'][:20]}", callback_data=f"completar_tarea_{p['id']}")
                    ])
                resp += "\n"

            if otros_pendientes:
                resp += "📌 *Otras tareas:*\n"
                for p in otros_pendientes:
                    resp += f"• [ ] *#{p['id']}* {p['tarea']} _({p.get('consultor', '')})_\n"
                    keyboard.append([
                        InlineKeyboardButton(f"✅ #{p['id']} {p['tarea'][:20]}", callback_data=f"completar_tarea_{p['id']}")
                    ])
                resp += "\n"

            if completadas:
                resp += "✅ *Completadas:*\n"
                for c in completadas:
                    con_tag = f" _({c.get('consultor', '')})_" if c.get('consultor') else ""
                    t_tag = f" _(Ticket #{c['id_ticket']})_" if c.get('id_ticket') else ""
                    resp += f"• [x] ~#{c['id']} {c['tarea']}~{con_tag}{t_tag}\n"
                resp += "\n"

            resp += "_Tocá el botón ✅ para marcarla como lista o decí 'tarea [número] lista'._"
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await safe_reply(update, resp, reply_markup=reply_markup)

        elif intencion == "COMPLETAR_COMPROMISO":
            id_comp = int(datos.get("id_compromiso", 0))
            reg_id_compromiso = id_comp
            res = await _ejecutar_completar_compromiso(
                context=context,
                chat_id_origen=chat_id,
                id_comp=id_comp,
                completado_por=consultor_nombre,
                minutos_override=datos.get("minutos"),
                cliente_override=datos.get("cliente"),
                modulo_override=datos.get("modulo"),
            )
            if res.get("ok"):
                reg_estado = "completado"
                reg_id_ticket = res.get("id_ticket")
                comp_ok = res.get("compromiso") or {}
                ticket_ok = res.get("ticket") or {}
                reg_cliente = ticket_ok.get("clientes") or comp_ok.get("cliente")
                reg_modulo = ticket_ok.get("modulo") or comp_ok.get("modulo")
                reg_detalle = comp_ok.get("tarea")
                resp = res["mensaje"]
            elif res.get("reason") == "already_completed":
                reg_estado = "ya_completada"
                comp_prev = res.get("compromiso") or {}
                id_t_prev = comp_prev.get("id_ticket")
                reg_id_ticket = id_t_prev
                extra_t = f" _(ya tiene el Ticket #{id_t_prev} asociado)_" if id_t_prev else ""
                resp = f"ℹ️ La tarea #{id_comp} ya estaba marcada como completada{extra_t}."
            else:
                reg_estado = "no_encontrado"
                resp = f"⚠️ No encontré la tarea #{id_comp} o no se pudo actualizar."
            await safe_reply(update, resp)

        elif intencion == "CONSULTAR_AGENDA":
            await responder_agenda(update, context, datos)

        elif intencion == "CONSULTAR_HORAS":
            f_modo = datos.get("fecha", "HOY")
            c_filtro = datos.get("consultor", "TODOS")
            modo_suj = datos.get("modo_sujeto", "AMBOS")
            await responder_consulta_horas(
                update,
                fecha_modo=f_modo,
                consultor_filtro=c_filtro,
                consultor_usuario=consultor_nombre,
                modo_sujeto=modo_suj
            )

        elif intencion == "RANKING_CLIENTES":
            await responder_ranking_clientes(update, datos)

        elif intencion == "BUSCAR_HISTORIAL":
            cliente = datos.get("cliente")
            consultor = datos.get("consultor")
            modulo = datos.get("modulo")
            texto = datos.get("texto_busqueda")
            es_horas = datos.get("es_consulta_horas", False)
            fecha_relativa = datos.get("fecha_relativa")
            modo_sujeto = datos.get("modo_sujeto", "AMBOS")

            tz = pytz.timezone(settings.TIMEZONE)
            ahora = datetime.now(tz)
            target_fecha = None
            if fecha_relativa == "AYER":
                target_fecha = (ahora - timedelta(days=1)).date()
            elif fecha_relativa == "HOY":
                target_fecha = ahora.date()
            elif fecha_relativa == "ANTEAYER":
                target_fecha = (ahora - timedelta(days=2)).date()

            mes = datos.get("mes")
            anio = datos.get("anio") or ahora.year

            # Mapear filtro consultor según el sujeto detectado
            filtro_consultor = None
            if consultor == "MIO" or modo_sujeto == "MIO":
                filtro_consultor = consultor_nombre
            elif consultor == "JEFE" or modo_sujeto == "JEFE":
                filtro_consultor = "JUANLUIS"
            elif consultor == "MELANI" or modo_sujeto == "COLABORADOR":
                filtro_consultor = "MELANI"
            elif consultor and consultor != "TODOS":
                filtro_consultor = consultor

            tickets = db.search_tickets(
                texto=texto,
                cliente=cliente,
                consultor=filtro_consultor,
                modulo=modulo,
                fecha=target_fecha,
                mes=mes if not target_fecha else None,
                anio=anio if not target_fecha else None,
                limit=None if es_horas else 30
            )

            respuesta_formateada = formatear_resultado_historial(
                tickets=tickets,
                cliente_buscado=cliente,
                texto_buscado=texto,
                fecha_exacta=target_fecha,
                mes=mes,
                anio=anio,
                es_consulta_horas=es_horas,
                consultor_buscado=filtro_consultor,
                modo_sujeto=modo_sujeto,
                consultor_usuario=consultor_nombre
            )
            await safe_reply(update, respuesta_formateada)

        else:
            resp = ai_service.responder_conversacion_ia(texto_usuario, user_name=consultor_nombre)
            await safe_reply(update, resp)
    finally:
        if not pedido_logged:
            db.registrar_pedido_bot(
                mensaje_original=texto_usuario,
                tipo_entrada=tipo_entrada,
                consultor=consultor_nombre,
                destinatario=reg_destinatario,
                intencion=intencion,
                cliente=reg_cliente,
                modulo=reg_modulo,
                estado=reg_estado,
                id_compromiso=reg_id_compromiso,
                id_ticket=reg_id_ticket,
                detalle_resultado=reg_detalle,
                telegram_user_id=user.id if user else None,
                telegram_chat_id=chat_id,
            )

async def borrar_ultimo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /borrar_ultimo: elimina el último ticket registrado."""
    user = update.effective_user
    consultor_db = db.get_consultant_by_telegram_id(user.id)
    c_nom = consultor_db.get("consultor") if consultor_db else None

    ultimo = db.get_last_ticket_by_consultant(c_nom)
    if not ultimo:
        await safe_reply(update, "⚠️ No encontré ningún ticket tuyo reciente para eliminar.")
        return

    id_t = ultimo.get("id_ticket")
    ok = db.delete_ticket(id_t, consultor=c_nom or user.first_name)
    if ok:
        await safe_reply(
            update,
            f"🗑️ *Ticket #{id_t} eliminado correctamente del Dashboard*\n"
            f"🏢 *Cliente:* {ultimo.get('clientes')}\n"
            f"⏱️ *Tiempo:* `{ultimo.get('tiempo_res')} min`\n"
            f"📝 *Detalle:* {ultimo.get('consultas')}"
        )
    else:
        await safe_reply(update, f"❌ No se pudo eliminar el ticket #{id_t}.")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las acciones de botones interactivos (navegación de agenda y borrado de tickets)."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "agenda_hoy":
        await responder_agenda(update, context, {"fecha": "HOY"})
    elif data == "agenda_manana":
        await responder_agenda(update, context, {"fecha": "MANANA"})
    elif data == "agenda_ayer":
        await responder_agenda(update, context, {"fecha": "AYER"})
    elif data.startswith("borrar_ticket_"):
        id_str = data.replace("borrar_ticket_", "")
        try:
            id_t = int(id_str)
            user = update.effective_user
            consultor_db = db.get_consultant_by_telegram_id(user.id)
            c_nom = consultor_db.get("consultor", user.first_name) if consultor_db else user.first_name
            ok = db.delete_ticket(id_t, consultor=c_nom)
            if ok:
                await query.edit_message_text(f"🗑️ *Ticket #{id_t} eliminado correctamente de la base de datos.*", parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text(f"⚠️ No se pudo eliminar el ticket #{id_t}.", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error borrando ticket vía callback: {e}")

    elif data.startswith("completar_tarea_"):
        id_str = data.replace("completar_tarea_", "")
        try:
            id_c = int(id_str)
            user = update.effective_user
            consultor_db = db.get_consultant_by_telegram_id(user.id) if user else None
            c_nom = consultor_db["consultor"] if consultor_db else (user.first_name.upper() if user else "EQUIPO")
            chat_id = update.effective_chat.id if update.effective_chat else None

            res = await _ejecutar_completar_compromiso(
                context=context,
                chat_id_origen=chat_id,
                id_comp=id_c,
                completado_por=c_nom,
            )
            if res.get("ok"):
                id_t = res.get("id_ticket")
                comp_ok = res.get("compromiso") or {}
                ticket_ok = res.get("ticket") or {}
                db.registrar_pedido_bot(
                    mensaje_original=f"[Botón completar tarea #{id_c}]",
                    tipo_entrada="boton",
                    consultor=c_nom,
                    destinatario=comp_ok.get("consultor"),
                    intencion="COMPLETAR_COMPROMISO",
                    cliente=ticket_ok.get("clientes") or comp_ok.get("cliente"),
                    modulo=ticket_ok.get("modulo") or comp_ok.get("modulo"),
                    estado="completado",
                    id_compromiso=id_c,
                    id_ticket=id_t,
                    detalle_resultado=comp_ok.get("tarea"),
                    telegram_user_id=user.id if user else None,
                    telegram_chat_id=chat_id,
                )
                curr_text = query.message.text or ""
                marca_ticket = f" (Listo ✅ Ticket #{id_t})" if id_t else " (Listo ✅)"
                new_text = curr_text.replace(f"#{id_c}", f"~#{id_c}~{marca_ticket}")
                try:
                    await query.edit_message_text(new_text)
                except Exception:
                    pass
                await safe_reply(update, res["mensaje"])
            elif res.get("reason") == "already_completed":
                id_t_prev = (res.get("compromiso") or {}).get("id_ticket")
                extra_t = f" _(Ticket #{id_t_prev})_" if id_t_prev else ""
                await safe_reply(update, f"ℹ️ La tarea #{id_c} ya estaba completada{extra_t}.")
            else:
                await safe_reply(update, f"⚠️ No se pudo completar la tarea #{id_c}.")
        except Exception as e:
            logger.error(f"Error completando tarea vía callback: {e}")

    elif data == "agendar_forzar":
        pend = context.user_data.get("evento_pendiente")
        if not pend:
            await query.edit_message_text("⚠️ No hay evento pendiente para agendar.")
            return
        try:
            start_dt = datetime.fromisoformat(pend["start_datetime_iso"])
            ev = calendar_service.create_event(
                summary=pend["titulo"],
                start_datetime=start_dt,
                duration_minutes=pend["duracion"],
                description=pend["desc"]
            )
            context.user_data.pop("evento_pendiente", None)
            if ev:
                link = ev.get("htmlLink", "")
                link_text = f"\n🔗 [Ver en Google Calendar]({link})" if link else ""
                await query.edit_message_text(
                    f"✅ *Evento agendado superpuesto con éxito*\n\n"
                    f"📌 *Título:* {pend['titulo']}\n"
                    f"⏰ *Horario:* {start_dt.strftime('%d/%m/%Y %H:%M')} hs{link_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(_format_calendar_create_error(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data == "mover_evento_1h":
        pend = context.user_data.get("evento_pendiente")
        if not pend:
            await query.edit_message_text("⚠️ No hay evento pendiente para mover.")
            return
        try:
            start_dt = datetime.fromisoformat(pend["start_datetime_iso"]) + timedelta(hours=1)
            ev = calendar_service.create_event(
                summary=pend["titulo"],
                start_datetime=start_dt,
                duration_minutes=pend["duracion"],
                description=pend["desc"]
            )
            context.user_data.pop("evento_pendiente", None)
            if ev:
                link = ev.get("htmlLink", "")
                link_text = f"\n🔗 [Ver en Google Calendar]({link})" if link else ""
                await query.edit_message_text(
                    f"✅ *Evento reprogramado 1 hora más tarde*\n\n"
                    f"📌 *Título:* {pend['titulo']}\n"
                    f"⏰ *Nuevo Horario:* {start_dt.strftime('%d/%m/%Y %H:%M')} hs{link_text}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(_format_calendar_create_error(), parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif data == "cancelar_evento":
        context.user_data.pop("evento_pendiente", None)
        await query.edit_message_text("❌ *Operación cancelada.* No se agendó ningún evento.", parse_mode=ParseMode.MARKDOWN)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa notas de voz y audios enviándolos a Gemini para transcribir y luego ejecutar la acción."""
    msg = update.effective_message
    if not msg or (not msg.voice and not msg.audio):
        return

    temp_msg = await msg.reply_text("🎙️ _Escuchando y transcribiendo audio..._", parse_mode=ParseMode.MARKDOWN)

    try:
        voice_or_audio = msg.voice or msg.audio
        file = await context.bot.get_file(voice_or_audio.file_id)
        audio_bytes = await file.download_as_bytearray()
        mime_type = getattr(voice_or_audio, "mime_type", None) or "audio/ogg"
        if "opus" in mime_type.lower():
            mime_type = "audio/ogg"

        texto_transcripto = ai_service.transcribe_audio(bytes(audio_bytes), mime_type=mime_type)

        if not texto_transcripto:
            user = update.effective_user
            consultor_db = db.get_consultant_by_telegram_id(user.id) if user else None
            c_nom = consultor_db["consultor"] if consultor_db else (user.first_name.upper() if user else None)
            db.registrar_pedido_bot(
                mensaje_original="[Audio no transcripto]",
                tipo_entrada="audio",
                consultor=c_nom,
                intencion="AUDIO_NO_ENTENDIDO",
                estado="error",
                detalle_resultado="No se pudo transcribir el audio",
                telegram_user_id=user.id if user else None,
                telegram_chat_id=update.effective_chat.id if update.effective_chat else None,
            )
            await temp_msg.edit_text("⚠️ No pude entender el audio o hubo un problema al transcribirlo. Podés volver a grabarlo o escribirlo en texto.")
            return

        try:
            await temp_msg.edit_text(f"🗣️ *\"_{texto_transcripto}_\"*", parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await temp_msg.edit_text(f"🗣️ \"{texto_transcripto}\"")

        # Invocamos handle_message con el texto transcripto explícitamente
        await handle_message(update, context, texto_override=texto_transcripto, tipo_entrada="audio")

    except Exception as e:
        logger.error(f"Error procesando mensaje de voz: {e}", exc_info=True)
        try:
            await temp_msg.edit_text(f"❌ Ocurrió un error al procesar el audio: {e}")
        except Exception:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Excepción en bot:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await safe_reply(update.effective_message, "⚠️ Disculpá, ocurrió un error procesando ese comando.")

# --- TAREAS PROGRAMADAS (CRON) ---

_eventos_notificados_15m = set()

async def job_alarmas_proximos_eventos(context: ContextTypes.DEFAULT_TYPE):
    """Revisa cada minuto si hay eventos que comienzan en los próximos 15 minutos y dispara una alarma."""
    chat_id = settings.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    hoy = now.date()

    eventos = calendar_service.get_events_for_date(hoy)
    for ev in eventos:
        start_str = ev.get("start", "")
        if "T" not in str(start_str):
            continue
        try:
            ev_start = datetime.fromisoformat(str(start_str))
            if ev_start.tzinfo is None:
                ev_start = tz.localize(ev_start)
            
            mins_restantes = (ev_start - now).total_seconds() / 60.0
            ev_key = f"{ev.get('id')}_{start_str}"

            # Alerta con 15 minutos de anticipación (entre 0 y 15 minutos)
            if 0 <= mins_restantes <= 15 and ev_key not in _eventos_notificados_15m:
                _eventos_notificados_15m.add(ev_key)
                min_texto = f"en {int(round(mins_restantes))} minutos" if mins_restantes >= 1.5 else "¡en breve!"
                hora_corta = ev_start.strftime("%H:%M")

                texto = (
                    f"⏰ *¡ALARMA DE REUNIÓN / COMPROMISO!* 🔔\n\n"
                    f"📌 *{ev['summary']}*\n"
                    f"⏱️ *Hora:* `{hora_corta} hs` ({min_texto})\n"
                )
                if ev.get("location"):
                    texto += f"📍 *Lugar:* {ev['location']}\n"
                if ev.get("description"):
                    desc = ev['description'].strip()
                    if len(desc) > 200:
                        desc = desc[:200] + "..."
                    texto += f"ℹ️ {desc}\n"

                await send_group_safe(context.bot, chat_id, texto)
                logger.info(f"Alarma de 15m enviada para: {ev['summary']} ({hora_corta} hs)")
        except Exception as e:
            logger.error(f"Error procesando alarma para evento {ev}: {e}")

async def job_recordatorio_manana(context: ContextTypes.DEFAULT_TYPE):
    """Envía a la mañana (09:00 hs) la agenda de hoy y el recordatorio previo si mañana hay eventos."""
    chat_id = settings.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return
    tz = pytz.timezone(settings.TIMEZONE)
    hoy = datetime.now(tz).date()
    manana = hoy + timedelta(days=1)

    eventos_hoy = calendar_service.get_events_for_date(hoy)
    eventos_manana = calendar_service.get_events_for_date(manana)
    compromisos_hoy = db.obtener_compromisos(fecha_objetivo=hoy, estado="pendiente")

    if not eventos_hoy and not eventos_manana and not compromisos_hoy:
        return

    texto = "☀️ *¡Buen día equipo! Arrancamos la jornada:* 🚀\n\n"
    if eventos_hoy:
        texto += f"🗓️ *Reuniones en agenda para HOY ({hoy.strftime('%d/%m/%Y')}):*\n"
        for ev in eventos_hoy:
            start_str = ev['start']
            hora = start_str.split("T")[1][:5] if "T" in start_str else "Todo el día"
            texto += f"• ⏰ `{hora}` - *{ev['summary']}*\n"
        texto += "\n"

    if compromisos_hoy:
        texto += f"🎯 *Tareas clave para hoy (sacar sí o sí):*\n"
        for c in compromisos_hoy:
            cons_tag = f" _({c.get('consultor', '')})_" if c.get('consultor') else ""
            texto += f"• [ ] *#{c['id']}* {c['tarea']}{cons_tag}\n"
        texto += "\n"

    if eventos_manana:
        texto += f"🔔 *Y ojo que mañana ({manana.strftime('%d/%m/%Y')}) se viene:*\n"
        for ev in eventos_manana:
            start_str = ev['start']
            hora = start_str.split("T")[1][:5] if "T" in start_str else "Todo el día"
            texto += f"• ⏰ `{hora}` - *{ev['summary']}*\n"
        texto += "\n"

    texto += "¡Que tengan un día de diez! 💪🏻"
    await send_group_safe(context.bot, chat_id, texto)

async def job_recordatorio_noche(context: ContextTypes.DEFAULT_TYPE):
    """Envía a la noche (20:30 hs) el recordatorio si mañana hay eventos agendados o tareas pendientes."""
    chat_id = settings.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return
    tz = pytz.timezone(settings.TIMEZONE)
    hoy = datetime.now(tz).date()
    manana = hoy + timedelta(days=1)

    eventos_manana = calendar_service.get_events_for_date(manana)
    compromisos_manana = db.obtener_compromisos(fecha_objetivo=manana, estado="pendiente")

    if not eventos_manana and not compromisos_manana:
        return

    texto = f"🌙 *¡Buen cierre de jornada gente! Mañana ({manana.strftime('%d/%m/%Y')}) se viene:*\n\n"
    if eventos_manana:
        texto += "🗓️ *Reuniones agendadas:*\n"
        for ev in eventos_manana:
            start_str = ev['start']
            hora = start_str.split("T")[1][:5] if "T" in start_str else "Todo el día"
            texto += f"• ⏰ `{hora}` - *{ev['summary']}*\n"
        texto += "\n"

    if compromisos_manana:
        texto += "🎯 *Tareas comprometidas para sacar mañana:*\n"
        for c in compromisos_manana:
            cons_tag = f" _({c.get('consultor', '')})_" if c.get('consultor') else ""
            texto += f"• [ ] *#{c['id']}* {c['tarea']}{cons_tag}\n"
        texto += "\n"

    texto += "¡A descansar y recargar pilas! ✨"

    await send_group_safe(context.bot, chat_id, texto)

async def job_resumen_tarde(context: ContextTypes.DEFAULT_TYPE):
    """Envía el resumen de tickets cargados hoy a las 18:30."""
    chat_id = settings.TELEGRAM_GROUP_CHAT_ID
    if not chat_id:
        return
    tz = pytz.timezone(settings.TIMEZONE)
    hoy = datetime.now(tz).date()
    tickets = db.get_tickets_by_date(hoy)

    texto = f"📊 *Cierre de jornada ({hoy.strftime('%d/%m/%Y')}):*\n\n"
    if tickets:
        total_mins = sum(int(t.get("tiempo_res") or 0) for t in tickets)
        texto += f"Total del equipo hoy: `{total_mins/60.0:.2f} hs` ({total_mins} min)\n\n"
        for t in tickets:
            mins = int(t.get("tiempo_res") or 0)
            con = t.get("consultor", "CONSULTOR")
            cli = t.get("clientes", "CLIENTE")
            desc = t.get("consultas", "")
            texto += f"• *{con}*: `{mins/60.0:.2f}h` en _{cli}_ ({desc})\n"
    else:
        texto += "⚠️ _No se registraron tickets hoy en el sistema._"

    await send_group_safe(context.bot, chat_id, texto)

async def tareas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /tareas: muestra las tareas del día de Melani y Juan Luis."""
    user = update.effective_user
    consultor_db = db.get_consultant_by_telegram_id(user.id)
    consultor_nombre = consultor_db.get("consultor", user.first_name) if consultor_db else user.first_name
    await handle_message(update, context, texto_override="/tareas")

async def tarea_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /tarea: agrega una tarea para Juan Luis, Melani o uno mismo."""
    user = update.effective_user
    consultor_db = db.get_consultant_by_telegram_id(user.id)
    consultor_nombre = consultor_db.get("consultor", user.first_name) if consultor_db else user.first_name
    if not context.args:
        texto = (
            "📌 *Cómo usar el comando /tarea:*\n\n"
            "• Para dejarle una tarea a Juan Luis:\n"
            "  `/tarea Juan Luis llamar a Cargill`\n\n"
            "• Para dejarle una tarea a Melani:\n"
            "  `/tarea Melani revisar facturación`\n\n"
            "• Para una tarea propia:\n"
            "  `/tarea Comprar insumos`\n\n"
            "💡 _¡También podés mandar una nota de voz 🎙️ o escribir normalmente!_\n"
            "Ej: _\"Dejale una tarea a Juan Luis: llamar a Petrobono\"_"
        )
        await safe_reply(update, texto)
        return
    
    texto_raw = "/tarea " + " ".join(context.args)
    await handle_message(update, context, texto_override=texto_raw)

async def recordatorio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /recordatorio: Muestra los compromisos agendados para mañana (día previo)."""
    tz = pytz.timezone(settings.TIMEZONE)
    hoy = datetime.now(tz).date()
    manana = hoy + timedelta(days=1)
    eventos_manana = calendar_service.get_events_for_date(manana)

    if eventos_manana:
        texto = f"🔔 *Recordatorio para mañana ({manana.strftime('%d/%m/%Y')}):*\n\n"
        texto += "Eventos agendados en Google Calendar:\n"
        for ev in eventos_manana:
            start_str = ev['start']
            hora = start_str.split("T")[1][:5] if "T" in start_str else "Todo el día"
            texto += f"• ⏰ `{hora}` - *{ev['summary']}*\n"
    elif calendar_service.last_errors:
        texto = "⚠️ *Error al consultar Google Calendar:* No se pudo verificar la agenda de mañana por un problema de autenticación o permisos con Google."
    else:
        texto = f"ℹ️ _Para mañana ({manana.strftime('%d/%m/%Y')}) no hay eventos agendados en el calendario._"

    await safe_reply(update, texto)

# --- MAIN ---

def _start_healthcheck_server():
    """Abre un servidor HTTP mínimo cuando PORT está definido (necesario en Render Web Service)."""
    port_str = os.getenv("PORT", "").strip()
    if not port_str:
        return
    try:
        port = int(port_str)
    except ValueError:
        return

    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK - Asistente Grandi activo")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            return

    def _serve():
        server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        logger.info(f"Servidor healthcheck escuchando en puerto {port}.")
        server.serve_forever()

    threading.Thread(target=_serve, daemon=True).start()

def main():
    _start_healthcheck_server()
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("¡ERROR CRÍTICO! TELEGRAM_BOT_TOKEN no está definido en el archivo .env")
        return

    tz = pytz.timezone(settings.TIMEZONE)
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("vincular", vincular_command))
    app.add_handler(CommandHandler("consultores", consultores_command))
    app.add_handler(CommandHandler("hoy", hoy_command))
    app.add_handler(CommandHandler("horas", horas_command))
    app.add_handler(CommandHandler("ranking", ranking_command))
    app.add_handler(CommandHandler("demanda", ranking_command))
    app.add_handler(CommandHandler("tareas", tareas_command))
    app.add_handler(CommandHandler("tarea", tarea_command))
    app.add_handler(CommandHandler("recordatorio", recordatorio_command))
    app.add_handler(CommandHandler("borrar_ultimo", borrar_ultimo_command))

    # Botones interactivos (navegación de agenda y borrado de tickets)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Mensajes de voz y audio
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))

    # Mensajes de texto normales
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_error_handler(error_handler)

    if app.job_queue and settings.TELEGRAM_GROUP_CHAT_ID:
        hora_manana = time(hour=8, minute=0, tzinfo=tz)
        hora_tarde = time(hour=18, minute=30, tzinfo=tz)
        hora_noche = time(hour=20, minute=30, tzinfo=tz)
        app.job_queue.run_daily(job_recordatorio_manana, time=hora_manana)
        app.job_queue.run_daily(job_resumen_tarde, time=hora_tarde)
        app.job_queue.run_daily(job_recordatorio_noche, time=hora_noche)
        
        # Alarma recurrente: chequea cada 60 segundos si algún evento empieza en los próximos 15 minutos
        app.job_queue.run_repeating(job_alarmas_proximos_eventos, interval=60, first=5)

        # Si el bot inicia en la mañana (entre las 07:00 y las 12:00), enviar el resumen del día de inmediato
        now = datetime.now(tz)
        if 7 <= now.hour < 12:
            app.job_queue.run_once(job_recordatorio_manana, when=2)

        logger.info("Recordatorios y Alarmas programados: Mañana (08:00 hs), Cierre (18:30 hs), Noche (20:30 hs) y Alarmas 15m antes de cada evento.")

    logger.info("Iniciando Asistente de Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()
