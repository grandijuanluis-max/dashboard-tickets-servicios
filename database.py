import logging
import os
import sqlite3
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
try:
    from src.config import settings, BASE_DIR
except ImportError:
    from config import settings, BASE_DIR

logger = logging.getLogger(__name__)

CLIENTES_HABITUALES = [
    "PALAVERSICH", "IPR", "KARTONSEC", "PASINA", "ANHSA", 
    "SG_MONTAGES", "PETROBONO", "PXP", "DOPERT", "FREMEC",
    "SUAREZ", "MONTARFE", "LGS", "CONDIMENTOS", "GRUPO VAZQUEZ", "GR_CONSULTING"
]

MODULOS_HABITUALES = [
    "ACCESOS", "ADMINISTRACION", "ANYDESK", "GR CONSULTING", "CONTABILIDAD", 
    "COMPRAS", "VENTAS", "LOGISTICA", "ECCOMERCE", "MAILS", "PRODUCCION", 
    "IMPUESTOS", "ERROR TABLAS", "STOCK", "QUERYS CREAR", "QUERYS MODIF", 
    "SINCRONIZACION", "CAMBIO VERSION", "CAMBIO EJECUTABLE", "INVESTIGACION", 
    "ANALISIS", "CRM/WORKFLOW", "FACT.ELECT", "CONFIGURACIONES", "REPORTES", 
    "FACTURACION", "WEB", "OTROS"
]

class Database:
    def __init__(self):
        self.client: Optional[Client] = None
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logger.info("Conexión con Supabase (bd_dashboard_servicios) inicializada.")
            except Exception as e:
                logger.error(f"Error conectando a Supabase: {e}")
        else:
            logger.warning("Faltan credenciales de Supabase en el archivo .env")

    def is_connected(self) -> bool:
        return self.client is not None

    def get_consultant_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Busca el consultor en config_consultores por su telegram_id."""
        if not self.is_connected():
            return None
        try:
            res = self.client.table("config_consultores").select("*").eq("telegram_id", telegram_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            # Si aún no existe la columna telegram_id en config_consultores, no explotar
            logger.debug(f"Búsqueda por telegram_id: {e}")
        return None

    def link_telegram_consultant(self, nombre_consultor: str, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Vincula el telegram_id al consultor en config_consultores."""
        if not self.is_connected():
            return None
        try:
            nombre_limpio = nombre_consultor.strip().upper()
            query = self.client.table("config_consultores").select("*").ilike("consultor", f"%{nombre_limpio}%").execute()
            if query.data:
                consultor_real = query.data[0]["consultor"]
                updated = self.client.table("config_consultores").update({"telegram_id": telegram_id}).eq("consultor", consultor_real).execute()
                return updated.data[0] if updated.data else query.data[0]
        except Exception as e:
            logger.error(f"Error vinculando consultor: {e}")
        return None

    def get_proximo_id_ticket(self) -> int:
        """Obtiene el próximo ID de ticket de bd_dashboard_servicios."""
        if not self.is_connected():
            return 1
        try:
            res = (
                self.client.table("bd_dashboard_servicios")
                .select("id_ticket")
                .order("id_ticket", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and res.data[0].get("id_ticket") is not None:
                return int(res.data[0]["id_ticket"]) + 1
        except Exception as e:
            logger.error(f"Error obteniendo próximo id_ticket: {e}")
        return 1

    def registrar_auditoria(self, id_ticket: int, accion: str, consultor: str):
        """Registra la acción en log_auditoria igual que appservicios.py."""
        if not self.is_connected():
            return
        try:
            data = {
                "id_ticket": int(id_ticket),
                "consultor": consultor,
                "fecha_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "accion": accion
            }
            self.client.table("log_auditoria").insert(data).execute()
        except Exception as e:
            logger.debug(f"Auditoría log: {e}")

    def create_ticket(
        self,
        consultor: str,
        cliente: str,
        tiempo_res_minutos: int,
        consultas: str,
        respuestas: str = "Resuelto vía soporte / desarrollo",
        usuario_cliente: str = "GENERAL",
        modulo: str = "OTROS",
        tipo_cons: str = "FUNCIONAL",
        prioridad: str = "MEDIA",
        estado: str = "CERRADO",
        atencion: str = "WHATSAPP",
        online: str = "SI",
        fecha: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """Inserta un nuevo ticket directamente en bd_dashboard_servicios."""
        if not self.is_connected():
            return None
        
        f = fecha or date.today()
        proximo_id = self.get_proximo_id_ticket()
        
        # Validar y normalizar cliente
        cli_clean = cliente.strip().upper()
        # Si coincide parcialmente con la lista conocida, usar el nombre oficial
        for c in CLIENTES_HABITUALES:
            if cli_clean in c or c in cli_clean:
                cli_clean = c
                break

        # Validar módulo
        mod_clean = modulo.strip().upper()
        for m in MODULOS_HABITUALES:
            if mod_clean in m or m in mod_clean:
                mod_clean = m
                break

        payload = {
            "id_ticket": proximo_id,
            "consultor": consultor.strip().upper(),
            "tipo_cons": tipo_cons,
            "prioridad": prioridad,
            "estado": estado,
            "atencion": atencion,
            "clientes": cli_clean,
            "usuario": usuario_cliente.strip().upper(),
            "fe_consult": f.strftime("%d/%m/%Y"),
            "modulo": mod_clean,
            "consultas": consultas,
            "respuestas": respuestas,
            "tiempo_res": int(tiempo_res_minutos),
            "online": online,
            "anio": f.year,
            "mes": f.month
        }

        try:
            res = self.client.table("bd_dashboard_servicios").insert(payload).execute()
            if res.data:
                saved = res.data[0]
                self.registrar_auditoria(proximo_id, f"ALTA ({estado}) - Vía Telegram", consultor)
                return saved
        except Exception as e:
            logger.error(f"Error creando ticket en bd_dashboard_servicios: {e}")
        return None

    def get_tickets_by_date(self, target_date: Optional[date] = None, consultor: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene tickets de una fecha (fe_consult en formato DD/MM/YYYY)."""
        if not self.is_connected():
            return []
        try:
            d = target_date or date.today()
            f_str = d.strftime("%d/%m/%Y")
            query = self.client.table("bd_dashboard_servicios").select("*").eq("fe_consult", f_str)
            if consultor:
                query = query.ilike("consultor", f"%{consultor.strip().upper()}%")
            res = query.execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error obteniendo tickets por fecha: {e}")
            return []

    def search_tickets(
        self,
        texto: Optional[str] = None,
        cliente: Optional[str] = None,
        consultor: Optional[str] = None,
        modulo: Optional[str] = None,
        fecha: Optional[date] = None,
        mes: Optional[int] = None,
        anio: Optional[int] = None,
        limit: Optional[int] = 30
    ) -> List[Dict[str, Any]]:
        """Busca tickets en bd_dashboard_servicios por cliente, consultor, modulo, fecha o palabra clave."""
        if not self.is_connected():
            return []
        try:
            query = self.client.table("bd_dashboard_servicios").select("*")
            
            if fecha:
                f_str = fecha.strftime("%d/%m/%Y")
                query = query.eq("fe_consult", f_str)
            else:
                if anio:
                    query = query.eq("anio", int(anio))
                if mes:
                    query = query.eq("mes", int(mes))

            if cliente:
                query = query.ilike("clientes", f"%{cliente.strip().upper()}%")
            if consultor:
                query = query.ilike("consultor", f"%{consultor.strip().upper()}%")
            if modulo:
                query = query.ilike("modulo", f"%{modulo.strip().upper()}%")
            if texto:
                clean_txt = texto.strip().replace("'", "")
                query = query.or_(f"consultas.ilike.%{clean_txt}%,respuestas.ilike.%{clean_txt}%")

            query = query.order("id_ticket", desc=True)
            if limit:
                query = query.limit(limit)
            res = query.execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error en search_tickets: {e}")
            return []

    def delete_ticket(self, id_ticket: int, consultor: str = "USUARIO") -> bool:
        """Elimina un ticket de bd_dashboard_servicios y registra en log_auditoria."""
        if not self.is_connected():
            return False
        try:
            self.client.table("bd_dashboard_servicios").delete().eq("id_ticket", int(id_ticket)).execute()
            self.registrar_auditoria(id_ticket, "BAJA - Vía Telegram", consultor)
            return True
        except Exception as e:
            logger.error(f"Error borrando ticket #{id_ticket}: {e}")
            return False

    def get_last_ticket_by_consultant(self, consultor: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Obtiene el último ticket registrado (opcionalmente filtrado por consultor)."""
        if not self.is_connected():
            return None
        try:
            query = self.client.table("bd_dashboard_servicios").select("*")
            if consultor:
                query = query.ilike("consultor", f"%{consultor.strip().upper()}%")
            res = query.order("id_ticket", desc=True).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception as e:
            logger.error(f"Error obteniendo último ticket: {e}")
        return None

    def get_consultants(self) -> List[str]:
        """Devuelve los nombres de consultores habilitados."""
        if not self.is_connected():
            return []
        try:
            res = self.client.table("config_consultores").select("consultor").execute()
            if res.data:
                return [r["consultor"] for r in res.data if r.get("consultor")]
        except Exception as e:
            logger.error(f"Error obteniendo consultores: {e}")
        return []

    def get_boss_name(self) -> str:
        """Devuelve el nombre del consultor jefe (ADMIN)."""
        if not self.is_connected():
            return "JUANLUIS"
        try:
            res = self.client.table("config_consultores").select("consultor").ilike("rol", "%ADMIN%").execute()
            if res.data and res.data[0].get("consultor"):
                return res.data[0]["consultor"]
        except Exception:
            pass
        return "JUANLUIS"

    def _init_local_db(self) -> Optional[str]:
        """Inicializa base de datos local SQLite para fallback de compromisos."""
        try:
            db_dir = str(BASE_DIR / "data")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "compromisos.db")
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS compromisos_diarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        consultor TEXT NOT NULL,
                        tarea TEXT NOT NULL,
                        fecha_objetivo TEXT NOT NULL,
                        estado TEXT NOT NULL DEFAULT 'pendiente',
                        origen TEXT DEFAULT 'telegram',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            return db_path
        except Exception as e:
            logger.error(f"Error inicializando SQLite local: {e}")
            return None

    def crear_compromiso(self, consultor: str, tarea: str, fecha_objetivo: date, origen: str = "telegram") -> Optional[Dict[str, Any]]:
        """Registra un compromiso/tarea diaria en Supabase o en fallback SQLite."""
        consultor_limpio = consultor.strip().upper()
        tarea_limpia = tarea.strip()
        fecha_str = fecha_objetivo.isoformat()

        # 1. Intentar Supabase
        if self.is_connected():
            try:
                res = self.client.table("compromisos_diarios").insert({
                    "consultor": consultor_limpio,
                    "tarea": tarea_limpia,
                    "fecha_objetivo": fecha_str,
                    "estado": "pendiente",
                    "origen": origen
                }).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"No se pudo guardar compromiso en Supabase ({e}). Usando base local.")

        # 2. Fallback SQLite
        db_path = self._init_local_db()
        if db_path:
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO compromisos_diarios (consultor, tarea, fecha_objetivo, estado, origen) VALUES (?, ?, ?, 'pendiente', ?)",
                        (consultor_limpio, tarea_limpia, fecha_str, origen)
                    )
                    new_id = cur.lastrowid
                    conn.commit()
                    return {
                        "id": new_id,
                        "consultor": consultor_limpio,
                        "tarea": tarea_limpia,
                        "fecha_objetivo": fecha_str,
                        "estado": "pendiente",
                        "origen": origen
                    }
            except Exception as e:
                logger.error(f"Error guardando compromiso en SQLite: {e}")
        return None

    def obtener_compromisos(self, consultor: Optional[str] = None, fecha_objetivo: Optional[date] = None, estado: Optional[str] = "pendiente") -> List[Dict[str, Any]]:
        """Obtiene compromisos de Supabase o fallback local."""
        fecha_str = fecha_objetivo.isoformat() if fecha_objetivo else None
        consultor_limpio = consultor.strip().upper() if consultor else None

        # 1. Intentar Supabase
        if self.is_connected():
            try:
                query = self.client.table("compromisos_diarios").select("*")
                if consultor_limpio:
                    query = query.ilike("consultor", f"%{consultor_limpio}%")
                if fecha_str:
                    query = query.eq("fecha_objetivo", fecha_str)
                if estado:
                    query = query.eq("estado", estado)
                res = query.order("id", desc=False).execute()
                if res.data is not None:
                    return res.data
            except Exception as e:
                logger.debug(f"Lectura de compromisos en Supabase falló ({e}), intentando SQLite local.")

        # 2. Fallback SQLite
        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    sql = "SELECT * FROM compromisos_diarios WHERE 1=1"
                    params = []
                    if consultor_limpio:
                        sql += " AND UPPER(consultor) LIKE ?"
                        params.append(f"%{consultor_limpio}%")
                    if fecha_str:
                        sql += " AND fecha_objetivo = ?"
                        params.append(fecha_str)
                    if estado:
                        sql += " AND estado = ?"
                        params.append(estado)
                    sql += " ORDER BY id ASC"
                    rows = conn.execute(sql, params).fetchall()
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error consultando SQLite local: {e}")
        return []

    def completar_compromiso(self, id_compromiso: int) -> bool:
        """Marca un compromiso como completado."""
        # 1. Supabase
        if self.is_connected():
            try:
                res = self.client.table("compromisos_diarios").update({"estado": "completada"}).eq("id", id_compromiso).execute()
                if res.data and len(res.data) > 0:
                    return True
            except Exception:
                pass
        # 2. SQLite
        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE compromisos_diarios SET estado = 'completada' WHERE id = ?", (id_compromiso,))
                    conn.commit()
                    return cur.rowcount > 0
            except Exception as e:
                logger.error(f"Error completando en SQLite: {e}")
        return False

    def eliminar_compromiso(self, id_compromiso: int) -> bool:
        """Elimina un compromiso."""
        # 1. Supabase
        if self.is_connected():
            try:
                res = self.client.table("compromisos_diarios").delete().eq("id", id_compromiso).execute()
                if res.data and len(res.data) > 0:
                    return True
            except Exception:
                pass
        # 2. SQLite
        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM compromisos_diarios WHERE id = ?", (id_compromiso,))
                    conn.commit()
                    return cur.rowcount > 0
            except Exception as e:
                logger.error(f"Error eliminando en SQLite: {e}")
        return False

db = Database()
