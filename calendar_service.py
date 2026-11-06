import os
import logging
from datetime import datetime, time, timedelta
import pytz
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from src.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

class CalendarService:
    def __init__(self):
        self.service = None
        self.tz = pytz.timezone(settings.TIMEZONE)
        self._init_service()

    def _init_service(self):
        cred_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        if not os.path.isabs(cred_path):
            from src.config import BASE_DIR
            cred_path = str(BASE_DIR / cred_path)
        if os.path.exists(cred_path):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    cred_path, scopes=SCOPES
                )
                self.service = build("calendar", "v3", credentials=creds)
                logger.info("Google Calendar API inicializada con Service Account.")
            except Exception as e:
                logger.error(f"Error inicializando Google Calendar: {e}")
        else:
            logger.warning(f"No se encontró archivo de credenciales de Google Calendar en: {cred_path}")

    def is_connected(self) -> bool:
        return self.service is not None

    def get_events_for_date(self, target_date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """Obtiene los eventos de todos los calendarios configurados para un día específico (por defecto hoy)."""
        if not self.is_connected():
            return []
        try:
            d = target_date or datetime.now(self.tz).date()
            start_dt = self.tz.localize(datetime.combine(d, time.min))
            end_dt = self.tz.localize(datetime.combine(d, time.max))

            cal_ids = [cid.strip() for cid in settings.GOOGLE_CALENDAR_ID.split(",") if cid.strip()]
            if not cal_ids:
                cal_ids = ["primary"]

            parsed = []
            seen_events = set()

            for cal_id in cal_ids:
                try:
                    events_result = self.service.events().list(
                        calendarId=cal_id,
                        timeMin=start_dt.isoformat(),
                        timeMax=end_dt.isoformat(),
                        singleEvents=True,
                        orderBy="startTime"
                    ).execute()

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

            parsed.sort(key=lambda x: str(x.get("start", "")))
            return parsed
        except Exception as e:
            logger.error(f"Error al obtener eventos de Google Calendar: {e}")
            return []

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
        if not self.is_connected():
            return None
        try:
            cal_ids = [cid.strip() for cid in settings.GOOGLE_CALENDAR_ID.split(",") if cid.strip()]
            target_cal = calendar_id or (cal_ids[0] if cal_ids else "primary")

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
