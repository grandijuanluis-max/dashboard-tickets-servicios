import os
import json
import logging
from datetime import datetime, time, timedelta, date
import pytz
from typing import List, Dict, Any, Optional
import requests
from icalendar import Calendar
import recurring_ical_events
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
try:
    from src.config import settings, BASE_DIR
except ImportError:
    from config import settings, BASE_DIR

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

class CalendarService:
    def __init__(self):
        self.service = None
        self._creds = None
        self._token_path: Optional[str] = None
        self.tz = pytz.timezone(settings.TIMEZONE)
        self.last_errors: Dict[str, str] = {}
        self._ical_cache: Dict[str, tuple] = {}
        self._init_service()

    def _init_service(self):
        # 1. Variable de entorno GOOGLE_TOKEN_JSON o archivo local token.json (OAuth)
        if settings.GOOGLE_TOKEN_JSON:
            try:
                token_info = json.loads(settings.GOOGLE_TOKEN_JSON)
                creds = OAuthCredentials.from_authorized_user_info(token_info, SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                if creds and creds.valid:
                    self._creds = creds
                    self.service = build("calendar", "v3", credentials=creds)
                    logger.info("Google Calendar API inicializada con OAuth (GOOGLE_TOKEN_JSON).")
                    return
            except Exception as e:
                logger.error(f"Error cargando GOOGLE_TOKEN_JSON: {e}")
                self.last_errors["init"] = str(e)

        for candidate in [str(BASE_DIR / "token.json"), str(BASE_DIR / "data" / "token.json")]:
            if os.path.exists(candidate):
                try:
                    creds = OAuthCredentials.from_authorized_user_file(candidate, SCOPES)
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        with open(candidate, "w") as f:
                            f.write(creds.to_json())
                    if creds and creds.valid:
                        self._creds = creds
                        self._token_path = candidate
                        self.service = build("calendar", "v3", credentials=creds)
                        logger.info(f"Google Calendar API inicializada con OAuth ({os.path.basename(candidate)}).")
                        return
                except Exception as e:
                    logger.error(f"Error cargando OAuth token {candidate}: {e}")
                    self.last_errors["init"] = str(e)

        # 2. Variable de entorno GOOGLE_CREDENTIALS_JSON (ideal para Railway/Render sin subir credentials.json a GitHub)
        if settings.GOOGLE_CREDENTIALS_JSON:
            try:
                cred_info = json.loads(settings.GOOGLE_CREDENTIALS_JSON)
                creds = service_account.Credentials.from_service_account_info(
                    cred_info, scopes=SCOPES
                )
                self._creds = creds
                self.service = build("calendar", "v3", credentials=creds)
                logger.info("Google Calendar API inicializada con Service Account (GOOGLE_CREDENTIALS_JSON).")
                return
            except Exception as e:
                logger.error(f"Error cargando GOOGLE_CREDENTIALS_JSON: {e}")
                self.last_errors["init"] = str(e)

        # 3. Fallback a archivo Service Account (credentials.json)
        cred_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        if not os.path.isabs(cred_path):
            cred_path = str(BASE_DIR / cred_path)
        if os.path.exists(cred_path):
            try:
                with open(cred_path, "r") as f:
                    cred_data = json.load(f)
                if "installed" in cred_data or "web" in cred_data:
                    msg = "credentials.json es de tipo OAuth. Ejecutá auth_calendar.py para generar token.json."
                    logger.warning(msg)
                    self.last_errors["init"] = msg
                    return
                creds = service_account.Credentials.from_service_account_file(
                    cred_path, scopes=SCOPES
                )
                self._creds = creds
                self.service = build("calendar", "v3", credentials=creds)
                logger.info("Google Calendar API inicializada con Service Account.")
            except Exception as e:
                logger.error(f"Error inicializando Google Calendar: {e}")
                self.last_errors["init"] = str(e)
        else:
            logger.warning(f"No se encontró archivo de credenciales de Google Calendar en: {cred_path}")
            self.last_errors["init"] = f"No se encontró archivo de credenciales en {cred_path}"

    def _ensure_fresh_credentials(self):
        """Refresca el token OAuth si venció y actualiza token.json."""
        if self._creds and self._token_path and getattr(self._creds, "expired", False) and getattr(self._creds, "refresh_token", None):
            try:
                self._creds.refresh(Request())
                with open(self._token_path, "w") as f:
                    f.write(self._creds.to_json())
            except Exception as e:
                logger.error(f"Error refrescando token OAuth: {e}")
                self.last_errors["create"] = str(e)

    def is_connected(self) -> bool:
        return self.service is not None

    def _get_events_from_ical(self, source: str, target_date: date) -> List[Dict[str, Any]]:
        """Descarga o lee un feed iCal (.ics) y extrae los eventos para la fecha dada usando recurring_ical_events."""
        try:
            content = None
            if source.startswith("http://") or source.startswith("https://"):
                now_ts = datetime.now().timestamp()
                cached = self._ical_cache.get(source)
                if cached and (now_ts - cached[0] < 120):
                    content = cached[1]
                else:
                    resp = requests.get(source, timeout=12)
                    if resp.status_code == 404:
                        self.last_errors[source] = "Google Calendar devolvió 404. Si es la URL pública, en Google Calendar asegurate de marcar 'Compartir públicamente', o usá la 'Dirección secreta en formato iCal'."
                        return []
                    resp.raise_for_status()
                    content = resp.content
                    self._ical_cache[source] = (now_ts, content)
            elif os.path.exists(source):
                with open(source, "rb") as f:
                    content = f.read()
            else:
                return []

            if not content:
                return []

            cal = Calendar.from_ical(content)
            raw_events = recurring_ical_events.of(cal).at(target_date)
            parsed = []

            for item in raw_events:
                summary = str(item.get("summary") or "Sin título")
                dtstart = item.get("dtstart").dt
                dtend = item.get("dtend").dt if item.get("dtend") else dtstart

                if isinstance(dtstart, datetime):
                    if dtstart.tzinfo is None:
                        dtstart = self.tz.localize(dtstart)
                    else:
                        dtstart = dtstart.astimezone(self.tz)
                    start_str = dtstart.isoformat()
                else:
                    start_str = dtstart.isoformat()

                if isinstance(dtend, datetime):
                    if dtend.tzinfo is None:
                        dtend = self.tz.localize(dtend)
                    else:
                        dtend = dtend.astimezone(self.tz)
                    end_str = dtend.isoformat()
                else:
                    end_str = dtend.isoformat()

                parsed.append({
                    "id": str(item.get("uid", "")),
                    "summary": summary,
                    "start": start_str,
                    "end": end_str,
                    "location": str(item.get("location", "")),
                    "description": str(item.get("description", "")),
                    "htmlLink": "",
                    "calendar_id": source
                })

            return parsed
        except Exception as e:
            logger.error(f"Error procesando iCal {source}: {e}")
            self.last_errors[source] = str(e)
            return []

    def get_events_for_date(self, target_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Obtiene los eventos de todos los calendarios configurados para un día específico (por defecto hoy)."""
        self.last_errors = {}
        d = target_date or datetime.now(self.tz).date()

        parsed = []
        seen_events = set()
        api_ok = False

        # 1. Priorizar API en vivo de Google Calendar si está conectada (refleja eventos creados al instante)
        api_cal_ids = self._api_calendar_ids()
        if self.is_connected() and api_cal_ids:
            self._ensure_fresh_credentials()
            start_dt = self.tz.localize(datetime.combine(d, time.min))
            end_dt = self.tz.localize(datetime.combine(d, time.max))

            for cal_id in api_cal_ids:
                try:
                    events_result = self.service.events().list(
                        calendarId=cal_id,
                        timeMin=start_dt.isoformat(),
                        timeMax=end_dt.isoformat(),
                        singleEvents=True,
                        orderBy="startTime"
                    ).execute()
                    api_ok = True

                    items = events_result.get("items", [])
                    for item in items:
                        ev_id = item.get("id")
                        summary = item.get("summary", "Sin título")
                        start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
                        end = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))

                        unique_key = (summary.strip().lower(), str(start))
                        if unique_key in seen_events:
                            continue
                        seen_events.add(unique_key)

                        parsed.append({
                            "id": ev_id,
                            "summary": summary,
                            "start": start,
                            "end": end,
                            "location": item.get("location", ""),
                            "description": item.get("description", ""),
                            "htmlLink": item.get("htmlLink", ""),
                            "calendar_id": cal_id
                        })
                except Exception as cal_err:
                    logger.error(f"Error consultando calendario {cal_id}: {cal_err}")
                    self.last_errors[cal_id] = str(cal_err)

        # 2. Fallback a fuentes iCal (URL o backup local) si la API no está conectada o falló
        if not api_ok:
            ical_sources = []
            ics_url_setting = getattr(settings, "GOOGLE_CALENDAR_ICS_URL", "")
            if ics_url_setting:
                for u in ics_url_setting.split(","):
                    if u.strip():
                        ical_sources.append(u.strip())

            cal_ids = [cid.strip() for cid in settings.GOOGLE_CALENDAR_ID.split(",") if cid.strip()]
            for cid in cal_ids:
                if cid.startswith("http://") or cid.startswith("https://") or cid.endswith(".ics"):
                    if cid not in ical_sources:
                        ical_sources.append(cid)

            local_backup_ics = str(BASE_DIR / "data" / "calendar_backup.ics")
            if not ical_sources and os.path.exists(local_backup_ics):
                ical_sources.append(local_backup_ics)

            for source in ical_sources:
                events_ical = self._get_events_from_ical(source, d)
                for ev in events_ical:
                    unique_key = (ev["summary"].strip().lower(), str(ev["start"]))
                    if unique_key in seen_events:
                        continue
                    seen_events.add(unique_key)
                    parsed.append(ev)

            if not parsed and os.path.exists(local_backup_ics) and local_backup_ics not in ical_sources:
                backup_events = self._get_events_from_ical(local_backup_ics, d)
                for ev in backup_events:
                    unique_key = (ev["summary"].strip().lower(), str(ev["start"]))
                    if unique_key in seen_events:
                        continue
                    seen_events.add(unique_key)
                    parsed.append(ev)

            if not self.is_connected() and not ical_sources:
                self.last_errors["connection"] = "Servicio de Google Calendar no inicializado y no hay feed iCal configurado"
            elif ical_sources and not self.last_errors.get(ical_sources[0]):
                # Si el fallback iCal funcionó, limpiar errores previos de API
                self.last_errors = {}

        parsed.sort(key=lambda x: str(x.get("start", "")))
        return parsed

    def _api_calendar_ids(self) -> List[str]:
        """Devuelve los IDs de calendario válidos para Google Calendar API (excluyendo URLs o archivos .ics)."""
        cal_ids = [cid.strip() for cid in settings.GOOGLE_CALENDAR_ID.split(",") if cid.strip()]
        return [c for c in cal_ids if not (c.startswith("http://") or c.startswith("https://") or c.endswith(".ics"))]

    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        duration_minutes: int = 60,
        description: str = "",
        attendees: Optional[List[str]] = None,
        calendar_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Crea un evento en el Google Calendar."""
        self.last_errors.pop("create", None)
        if not self.is_connected():
            self.last_errors["create"] = self.last_errors.get("init") or "Servicio de Google Calendar no inicializado (falta credentials.json válido)."
            return None
        try:
            self._ensure_fresh_credentials()
            api_cal_ids = self._api_calendar_ids()
            target_cal = calendar_id or (api_cal_ids[0] if api_cal_ids else "primary")

            end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            body = {
                "summary": summary,
                "description": description,
                "start": {
                    "dateTime": start_datetime.isoformat(),
                    "timeZone": settings.TIMEZONE,
                },
                "end": {
                    "dateTime": end_datetime.isoformat(),
                    "timeZone": settings.TIMEZONE,
                },
            }
            if attendees:
                body["attendees"] = [{"email": email} for email in attendees]

            event = self.service.events().insert(
                calendarId=target_cal,
                body=body
            ).execute()
            return event
        except Exception as e:
            logger.error(f"Error creando evento en Google Calendar: {e}")
            self.last_errors["create"] = str(e)
            return None

    def check_conflicts(
        self,
        start_datetime: datetime,
        duration_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Busca eventos existentes que se superpongan con el horario propuesto."""
        if not self.is_connected():
            return []
        try:
            target_date = start_datetime.date()
            events = self.get_events_for_date(target_date)
            new_start = start_datetime
            if new_start.tzinfo is None:
                new_start = self.tz.localize(new_start)
            new_end = new_start + timedelta(minutes=duration_minutes)

            conflicts = []
            for ev in events:
                start_raw = ev.get("start")
                end_raw = ev.get("end")
                if not start_raw or not end_raw:
                    continue
                # Si es evento de todo el día (ej: 'YYYY-MM-DD') no lo consideramos conflicto de hora específica
                if len(str(start_raw)) == 10:
                    continue
                try:
                    ev_start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                    ev_end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
                    if ev_start.tzinfo is None:
                        ev_start = self.tz.localize(ev_start)
                    if ev_end.tzinfo is None:
                        ev_end = self.tz.localize(ev_end)

                    # Condición de superposición
                    if ev_start < new_end and ev_end > new_start:
                        conflicts.append({
                            **ev,
                            "dt_start": ev_start,
                            "dt_end": ev_end
                        })
                except Exception as parse_err:
                    logger.debug(f"Error parseando fechas para conflicto: {parse_err}")
            return conflicts
        except Exception as e:
            logger.error(f"Error comprobando conflictos de agenda: {e}")
            return []

    def update_event_time(
        self,
        calendar_id: str,
        event_id: str,
        new_start_datetime: datetime,
        duration_minutes: int = 60
    ) -> Optional[Dict[str, Any]]:
        """Modifica la fecha y hora de un evento existente en Google Calendar."""
        if not self.is_connected():
            return None
        try:
            new_end_datetime = new_start_datetime + timedelta(minutes=duration_minutes)
            patch_body = {
                "start": {
                    "dateTime": new_start_datetime.isoformat(),
                    "timeZone": settings.TIMEZONE,
                },
                "end": {
                    "dateTime": new_end_datetime.isoformat(),
                    "timeZone": settings.TIMEZONE,
                }
            }
            updated = self.service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=patch_body
            ).execute()
            return updated
        except Exception as e:
            logger.error(f"Error modificando evento {event_id}: {e}")
            return None

calendar_service = CalendarService()
