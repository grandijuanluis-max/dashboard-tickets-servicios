import logging
import os
import sqlite3
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any, List
import pytz
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
        self.last_error: Optional[str] = None
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logger.info("Conexión con Supabase (bd_dashboard_servicios) inicializada.")
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Error conectando a Supabase: {e}")
        else:
            self.last_error = "Faltan credenciales SUPABASE_URL / SUPABASE_KEY"
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
        """Inserta un nuevo ticket directamente en bd_dashboard_servicios con reintento ante colisión de ID."""
        self.last_error = None
        if not self.is_connected():
            self.last_error = "Sin conexión con Supabase (revisá SUPABASE_URL y SUPABASE_KEY)"
            return None

        tz = pytz.timezone(settings.TIMEZONE)
        f = fecha or datetime.now(tz).date()

        # Validar y normalizar cliente
        cli_clean = cliente.strip().upper()
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

        proximo_id = self.get_proximo_id_ticket()
        for intento in range(3):
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
                self.last_error = "Supabase no devolvió datos al insertar en bd_dashboard_servicios"
            except Exception as e:
                err_str = str(e)
                self.last_error = err_str
                if ("duplicate" in err_str.lower() or "unique" in err_str.lower() or "23505" in err_str) and intento < 2:
                    logger.warning(f"Colisión de id_ticket={proximo_id}, reintentando ({intento + 1}/3)...")
                    proximo_id = self.get_proximo_id_ticket() + intento + 1
                    continue
                logger.error(f"Error creando ticket en bd_dashboard_servicios: {e}")
                break
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

    def get_consultant_telegram_id(self, nombre_consultor: str) -> Optional[int]:
        """Obtiene el telegram_id de un consultor desde config_consultores."""
        if not self.is_connected() or not nombre_consultor:
            return None
        try:
            res = (
                self.client.table("config_consultores")
                .select("telegram_id")
                .ilike("consultor", f"%{nombre_consultor.strip().upper()}%")
                .limit(1)
                .execute()
            )
            if res.data and res.data[0].get("telegram_id"):
                return int(res.data[0]["telegram_id"])
        except Exception as e:
            logger.debug(f"Error obteniendo telegram_id de {nombre_consultor}: {e}")
        return None

    def _init_local_db(self) -> Optional[str]:
        """Inicializa base de datos local SQLite para fallback de compromisos y registro de pedidos."""
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
                        asignado_por TEXT,
                        respuesta_asignado TEXT,
                        visto_at TEXT,
                        en_proceso_at TEXT,
                        cliente TEXT DEFAULT 'GENERAL',
                        modulo TEXT DEFAULT 'OTROS',
                        tiempo_estimado_min INTEGER DEFAULT 60,
                        id_ticket INTEGER,
                        completado_por TEXT,
                        completado_at TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                existing_cols = {
                    row[1] for row in conn.execute("PRAGMA table_info(compromisos_diarios)").fetchall()
                }
                for col_name, col_def in [
                    ("asignado_por", "TEXT"),
                    ("respuesta_asignado", "TEXT"),
                    ("visto_at", "TEXT"),
                    ("en_proceso_at", "TEXT"),
                    ("cliente", "TEXT DEFAULT 'GENERAL'"),
                    ("modulo", "TEXT DEFAULT 'OTROS'"),
                    ("tiempo_estimado_min", "INTEGER DEFAULT 60"),
                    ("id_ticket", "INTEGER"),
                    ("completado_por", "TEXT"),
                    ("completado_at", "TEXT"),
                ]:
                    if col_name not in existing_cols:
                        conn.execute(f"ALTER TABLE compromisos_diarios ADD COLUMN {col_name} {col_def}")

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS registro_pedidos_bot (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        telegram_user_id INTEGER,
                        telegram_chat_id INTEGER,
                        consultor TEXT,
                        destinatario TEXT,
                        tipo_entrada TEXT NOT NULL DEFAULT 'texto',
                        mensaje_original TEXT NOT NULL,
                        intencion TEXT,
                        cliente TEXT,
                        modulo TEXT,
                        estado TEXT NOT NULL DEFAULT 'registrado',
                        id_compromiso INTEGER,
                        id_ticket INTEGER,
                        detalle_resultado TEXT,
                        completado_at TEXT
                    )
                """)
                conn.commit()
            return db_path
        except Exception as e:
            logger.error(f"Error inicializando SQLite local: {e}")
            return None

    def crear_compromiso(
        self,
        consultor: str,
        tarea: str,
        fecha_objetivo: date,
        origen: str = "telegram",
        cliente: str = "GENERAL",
        modulo: str = "OTROS",
        tiempo_estimado_min: int = 60,
        asignado_por: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Registra un compromiso/tarea diaria en Supabase o en fallback SQLite."""
        consultor_limpio = consultor.strip().upper()
        tarea_limpia = tarea.strip()
        fecha_str = fecha_objetivo.isoformat()
        cli_clean = (cliente or "GENERAL").strip().upper()
        mod_clean = (modulo or "OTROS").strip().upper()
        mins_clean = int(tiempo_estimado_min or 60)
        asignador_clean = asignado_por.strip().upper() if asignado_por else None
        if not asignador_clean and str(origen).startswith("telegram:"):
            asignador_clean = str(origen).split(":", 1)[1].strip().upper()

        # 1. Intentar Supabase
        if self.is_connected():
            payload_full = {
                "consultor": consultor_limpio,
                "tarea": tarea_limpia,
                "fecha_objetivo": fecha_str,
                "estado": "pendiente",
                "origen": origen,
                "asignado_por": asignador_clean,
                "cliente": cli_clean,
                "modulo": mod_clean,
                "tiempo_estimado_min": mins_clean,
            }
            try:
                res = self.client.table("compromisos_diarios").insert(payload_full).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e_full:
                # Reintentar sin columnas nuevas si aún no se corrió el ALTER TABLE en Supabase
                if "column" in str(e_full).lower() or "schema cache" in str(e_full).lower():
                    try:
                        res = self.client.table("compromisos_diarios").insert({
                            "consultor": consultor_limpio,
                            "tarea": tarea_limpia,
                            "fecha_objetivo": fecha_str,
                            "estado": "pendiente",
                            "origen": origen,
                        }).execute()
                        if res.data and len(res.data) > 0:
                            return res.data[0]
                    except Exception as e_min:
                        logger.warning(f"No se pudo guardar compromiso en Supabase ({e_min}). Usando base local.")
                else:
                    logger.warning(f"No se pudo guardar compromiso en Supabase ({e_full}). Usando base local.")

        # 2. Fallback SQLite
        db_path = self._init_local_db()
        if db_path:
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """INSERT INTO compromisos_diarios
                           (consultor, tarea, fecha_objetivo, estado, origen, asignado_por, cliente, modulo, tiempo_estimado_min)
                           VALUES (?, ?, ?, 'pendiente', ?, ?, ?, ?, ?)""",
                        (consultor_limpio, tarea_limpia, fecha_str, origen, asignador_clean, cli_clean, mod_clean, mins_clean)
                    )
                    new_id = cur.lastrowid
                    conn.commit()
                    return {
                        "id": new_id,
                        "consultor": consultor_limpio,
                        "tarea": tarea_limpia,
                        "fecha_objetivo": fecha_str,
                        "estado": "pendiente",
                        "origen": origen,
                        "asignado_por": asignador_clean,
                        "cliente": cli_clean,
                        "modulo": mod_clean,
                        "tiempo_estimado_min": mins_clean,
                    }
            except Exception as e:
                logger.error(f"Error guardando compromiso en SQLite: {e}")
        return None

    def obtener_compromiso_por_id(self, id_compromiso: int) -> Optional[Dict[str, Any]]:
        """Obtiene una tarea puntual por su ID desde Supabase o SQLite."""
        if self.is_connected():
            try:
                res = self.client.table("compromisos_diarios").select("*").eq("id", int(id_compromiso)).limit(1).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                logger.debug(f"obtener_compromiso_por_id Supabase fallback ({e})")

        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT * FROM compromisos_diarios WHERE id = ?", (int(id_compromiso),)
                    ).fetchone()
                    if row:
                        return dict(row)
            except Exception as e:
                logger.error(f"Error buscando compromiso #{id_compromiso} en SQLite: {e}")
        return None

    def obtener_compromisos(self, consultor: Optional[str] = None, fecha_objetivo: Optional[date] = None, estado: Optional[str] = "pendiente") -> List[Dict[str, Any]]:
        """Obtiene compromisos de Supabase o fallback local. Si estado=='pendiente', incluye activas ('pendiente', 'vista', 'en_proceso')."""
        fecha_str = fecha_objetivo.isoformat() if fecha_objetivo else None
        consultor_limpio = consultor.strip().upper() if consultor else None
        estados_activos = ["pendiente", "vista", "en_proceso"]

        # 1. Intentar Supabase
        if self.is_connected():
            try:
                query = self.client.table("compromisos_diarios").select("*")
                if consultor_limpio:
                    query = query.ilike("consultor", f"%{consultor_limpio}%")
                if fecha_str:
                    query = query.eq("fecha_objetivo", fecha_str)
                if estado == "pendiente":
                    query = query.in_("estado", estados_activos)
                elif estado:
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
                    if estado == "pendiente":
                        sql += " AND estado IN ('pendiente', 'vista', 'en_proceso')"
                    elif estado:
                        sql += " AND estado = ?"
                        params.append(estado)
                    sql += " ORDER BY id ASC"
                    rows = conn.execute(sql, params).fetchall()
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.error(f"Error consultando SQLite local: {e}")
        return []

    def obtener_ultima_tarea_asignada(self, consultor: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Devuelve la tarea activa más reciente para un consultor (útil cuando responde sin indicar el #ID)."""
        tareas = self.obtener_compromisos(consultor=consultor, fecha_objetivo=None, estado="pendiente")
        if not tareas:
            return None
        return tareas[-1]

    def actualizar_estado_compromiso(
        self,
        id_compromiso: int,
        nuevo_estado: str,
        actor: Optional[str] = None,
        nota: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Actualiza el estado de respuesta ('vista', 'en_proceso' o nota) de una tarea sin cerrarla."""
        comp = self.obtener_compromiso_por_id(id_compromiso)
        if not comp:
            return {"ok": False, "reason": "not_found"}

        estado_actual = str(comp.get("estado") or "pendiente").lower()
        if estado_actual == "completada":
            return {"ok": False, "reason": "already_completed", "compromiso": comp}

        now_iso = datetime.now(timezone.utc).isoformat()
        target_estado = nuevo_estado if nuevo_estado in ("pendiente", "vista", "en_proceso") else estado_actual
        if target_estado == "pendiente" and nota:
            # Si responde con un texto libre sin haberla marcado vista, marcarla vista automáticamente
            target_estado = "vista"

        nota_clean = (nota or "").strip()
        if not nota_clean:
            if target_estado == "vista":
                nota_clean = "Visto / Recibido"
            elif target_estado == "en_proceso":
                nota_clean = "En proceso / Lo estoy haciendo"

        upd_full: Dict[str, Any] = {"estado": target_estado}
        if nota_clean:
            upd_full["respuesta_asignado"] = nota_clean
        if target_estado == "vista" or (target_estado == "en_proceso" and not comp.get("visto_at")):
            upd_full["visto_at"] = comp.get("visto_at") or now_iso
        if target_estado == "en_proceso":
            upd_full["en_proceso_at"] = now_iso

        actualizado = False
        if self.is_connected():
            try:
                res = self.client.table("compromisos_diarios").update(upd_full).eq("id", int(id_compromiso)).execute()
                if res.data and len(res.data) > 0:
                    comp = res.data[0]
                    actualizado = True
            except Exception as e_full:
                if "column" in str(e_full).lower() or "schema cache" in str(e_full).lower():
                    try:
                        res = (
                            self.client.table("compromisos_diarios")
                            .update({"estado": target_estado})
                            .eq("id", int(id_compromiso))
                            .execute()
                        )
                        if res.data and len(res.data) > 0:
                            comp = res.data[0]
                            actualizado = True
                    except Exception:
                        pass
                else:
                    logger.warning(f"Error actualizando estado compromiso #{id_compromiso} en Supabase: {e_full}")

        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """UPDATE compromisos_diarios
                           SET estado = ?,
                               respuesta_asignado = COALESCE(?, respuesta_asignado),
                               visto_at = COALESCE(?, visto_at),
                               en_proceso_at = COALESCE(?, en_proceso_at)
                           WHERE id = ?""",
                        (
                            target_estado,
                            nota_clean or None,
                            upd_full.get("visto_at"),
                            upd_full.get("en_proceso_at"),
                            int(id_compromiso),
                        ),
                    )
                    conn.commit()
                    if cur.rowcount > 0:
                        actualizado = True
            except Exception as e:
                logger.error(f"Error actualizando estado compromiso #{id_compromiso} en SQLite: {e}")

        if not actualizado:
            return {"ok": False, "reason": "update_failed", "compromiso": comp}

        comp_merged = dict(comp)
        comp_merged["estado"] = target_estado
        if nota_clean:
            comp_merged["respuesta_asignado"] = nota_clean

        return {
            "ok": True,
            "compromiso": comp_merged,
            "estado": target_estado,
            "nota": nota_clean,
            "actor": (actor or comp.get("consultor") or "").strip().upper(),
        }

    def registrar_pedido_bot(
        self,
        mensaje_original: str,
        tipo_entrada: str = "texto",
        consultor: Optional[str] = None,
        destinatario: Optional[str] = None,
        intencion: Optional[str] = None,
        cliente: Optional[str] = None,
        modulo: Optional[str] = None,
        estado: str = "registrado",
        id_compromiso: Optional[int] = None,
        id_ticket: Optional[int] = None,
        detalle_resultado: Optional[str] = None,
        telegram_user_id: Optional[int] = None,
        telegram_chat_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Guarda en registro_pedidos_bot todo lo solicitado al asistente (audio o texto)."""
        payload = {
            "telegram_user_id": int(telegram_user_id) if telegram_user_id else None,
            "telegram_chat_id": int(telegram_chat_id) if telegram_chat_id else None,
            "consultor": consultor.strip().upper() if consultor else None,
            "destinatario": destinatario.strip().upper() if destinatario else None,
            "tipo_entrada": "audio" if str(tipo_entrada).lower() == "audio" else "texto",
            "mensaje_original": mensaje_original,
            "intencion": intencion,
            "cliente": cliente.strip().upper() if cliente else None,
            "modulo": modulo.strip().upper() if modulo else None,
            "estado": estado,
            "id_compromiso": int(id_compromiso) if id_compromiso else None,
            "id_ticket": int(id_ticket) if id_ticket else None,
            "detalle_resultado": detalle_resultado,
        }

        if self.is_connected():
            try:
                res = self.client.table("registro_pedidos_bot").insert(payload).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"No se pudo guardar en registro_pedidos_bot en Supabase ({e}). Usando fallback local.")

        db_path = self._init_local_db()
        if db_path:
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """INSERT INTO registro_pedidos_bot
                           (telegram_user_id, telegram_chat_id, consultor, destinatario, tipo_entrada,
                            mensaje_original, intencion, cliente, modulo, estado, id_compromiso, id_ticket, detalle_resultado)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            payload["telegram_user_id"], payload["telegram_chat_id"],
                            payload["consultor"], payload["destinatario"], payload["tipo_entrada"],
                            payload["mensaje_original"], payload["intencion"], payload["cliente"],
                            payload["modulo"], payload["estado"], payload["id_compromiso"],
                            payload["id_ticket"], payload["detalle_resultado"],
                        ),
                    )
                    new_id = cur.lastrowid
                    conn.commit()
                    return {"id": new_id, **payload}
            except Exception as e:
                logger.error(f"Error guardando pedido en SQLite local: {e}")
        return None

    def _marcar_pedido_completado_por_compromiso(
        self,
        id_compromiso: int,
        id_ticket: Optional[int],
        completado_at_iso: str,
        detalle: Optional[str] = None,
    ):
        """Actualiza en registro_pedidos_bot el pedido vinculado al compromiso completado."""
        upd = {"estado": "completada", "completado_at": completado_at_iso}
        if id_ticket:
            upd["id_ticket"] = int(id_ticket)
        if detalle:
            upd["detalle_resultado"] = detalle

        if self.is_connected():
            try:
                self.client.table("registro_pedidos_bot").update(upd).eq("id_compromiso", int(id_compromiso)).execute()
            except Exception as e:
                logger.debug(f"Actualización de registro_pedidos_bot en Supabase omitida: {e}")

        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        "UPDATE registro_pedidos_bot SET estado = 'completada', id_ticket = COALESCE(?, id_ticket), completado_at = ?, detalle_resultado = COALESCE(?, detalle_resultado) WHERE id_compromiso = ?",
                        (int(id_ticket) if id_ticket else None, completado_at_iso, detalle, int(id_compromiso)),
                    )
                    conn.commit()
            except Exception as e:
                logger.debug(f"Actualización SQLite registro_pedidos_bot falló: {e}")

    def completar_compromiso(
        self,
        id_compromiso: int,
        completado_por: Optional[str] = None,
        minutos_override: Optional[int] = None,
        cliente_override: Optional[str] = None,
        modulo_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Marca un compromiso como completado y crea/cierra automáticamente su ticket en bd_dashboard_servicios."""
        comp = self.obtener_compromiso_por_id(id_compromiso)
        if not comp:
            return {"ok": False, "reason": "not_found"}

        if str(comp.get("estado", "")).lower() == "completada" and comp.get("id_ticket"):
            return {
                "ok": False,
                "reason": "already_completed",
                "compromiso": comp,
                "id_ticket": comp.get("id_ticket"),
            }

        now_iso = datetime.now(timezone.utc).isoformat()
        quien_completa = (completado_por or comp.get("consultor") or "MELANI").strip().upper()
        consultor_ticket = (comp.get("consultor") or quien_completa).strip().upper()
        cliente_ticket = (cliente_override or comp.get("cliente") or "GENERAL").strip().upper()
        modulo_ticket = (modulo_override or comp.get("modulo") or "OTROS").strip().upper()
        minutos_ticket = int(minutos_override or comp.get("tiempo_estimado_min") or 60)
        tarea_txt = comp.get("tarea") or f"Tarea #{id_compromiso}"
        nota_asignado = str(comp.get("respuesta_asignado") or "").strip()
        resp_ticket = f"Tarea #{id_compromiso} completada por {quien_completa} vía Telegram"
        if nota_asignado:
            resp_ticket += f" | Nota: {nota_asignado}"

        # Crear o cerrar ticket oficial en bd_dashboard_servicios
        ticket_creado = None
        ticket_error = None
        id_ticket_existente = comp.get("id_ticket")
        if id_ticket_existente and self.is_connected():
            try:
                res_upd = (
                    self.client.table("bd_dashboard_servicios")
                    .update({
                        "estado": "CERRADO",
                        "tiempo_res": minutos_ticket,
                        "respuestas": resp_ticket,
                    })
                    .eq("id_ticket", int(id_ticket_existente))
                    .execute()
                )
                if res_upd.data:
                    ticket_creado = res_upd.data[0]
                    self.registrar_auditoria(
                        int(id_ticket_existente),
                        f"CIERRE (Tarea #{id_compromiso}) - Vía Telegram",
                        quien_completa,
                    )
            except Exception as e:
                ticket_error = str(e)
                logger.error(f"Error cerrando ticket #{id_ticket_existente}: {e}")

        if not ticket_creado:
            ticket_creado = self.create_ticket(
                consultor=consultor_ticket,
                cliente=cliente_ticket,
                tiempo_res_minutos=minutos_ticket,
                consultas=tarea_txt,
                respuestas=resp_ticket,
                usuario_cliente="GENERAL",
                modulo=modulo_ticket,
                estado="CERRADO",
                atencion="WHATSAPP",
            )
            if not ticket_creado:
                ticket_error = self.last_error or "Error desconocido al insertar ticket en Supabase"

        id_ticket_final = ticket_creado.get("id_ticket") if ticket_creado else id_ticket_existente

        # Actualizar compromiso como completado (y subirlo a Supabase si venía solo de SQLite)
        marcado = False
        if self.is_connected():
            upd_full = {
                "estado": "completada",
                "id_ticket": int(id_ticket_final) if id_ticket_final else None,
                "completado_por": quien_completa,
                "completado_at": now_iso,
            }
            try:
                res = self.client.table("compromisos_diarios").update(upd_full).eq("id", int(id_compromiso)).execute()
                if res.data and len(res.data) > 0:
                    marcado = True
            except Exception:
                try:
                    res = (
                        self.client.table("compromisos_diarios")
                        .update({"estado": "completada"})
                        .eq("id", int(id_compromiso))
                        .execute()
                    )
                    if res.data and len(res.data) > 0:
                        marcado = True
                except Exception:
                    pass

            if not marcado:
                # La tarea existía solo en SQLite local (antes de crear la tabla en Supabase): insertarla ahora
                try:
                    ins_payload = {
                        "consultor": consultor_ticket,
                        "tarea": tarea_txt,
                        "fecha_objetivo": str(comp.get("fecha_objetivo") or datetime.now(pytz.timezone(settings.TIMEZONE)).date().isoformat()),
                        "estado": "completada",
                        "origen": comp.get("origen") or "telegram",
                        "cliente": cliente_ticket,
                        "modulo": modulo_ticket,
                        "tiempo_estimado_min": minutos_ticket,
                        "id_ticket": int(id_ticket_final) if id_ticket_final else None,
                        "completado_por": quien_completa,
                        "completado_at": now_iso,
                    }
                    res_ins = self.client.table("compromisos_diarios").insert(ins_payload).execute()
                    if res_ins.data and len(res_ins.data) > 0:
                        marcado = True
                except Exception as e_ins:
                    logger.warning(f"No se pudo espejar tarea SQLite #{id_compromiso} en Supabase: {e_ins}")

        db_path = self._init_local_db()
        if db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """UPDATE compromisos_diarios
                           SET estado = 'completada',
                               id_ticket = COALESCE(?, id_ticket),
                               completado_por = ?,
                               completado_at = ?
                           WHERE id = ?""",
                        (int(id_ticket_final) if id_ticket_final else None, quien_completa, now_iso, int(id_compromiso)),
                    )
                    conn.commit()
                    if cur.rowcount > 0:
                        marcado = True
            except Exception as e:
                logger.error(f"Error completando en SQLite: {e}")

        if not marcado:
            return {"ok": False, "reason": "update_failed", "compromiso": comp, "ticket_error": ticket_error}

        detalle_res = (
            f"Completada por {quien_completa} -> Ticket #{id_ticket_final} ({cliente_ticket})"
            if id_ticket_final
            else f"Completada por {quien_completa} (sin ticket: {ticket_error or 'pendiente de sync'})"
        )
        self._marcar_pedido_completado_por_compromiso(
            id_compromiso=int(id_compromiso),
            id_ticket=id_ticket_final,
            completado_at_iso=now_iso,
            detalle=detalle_res,
        )

        return {
            "ok": True,
            "compromiso": comp,
            "ticket": ticket_creado,
            "id_ticket": id_ticket_final,
            "completado_por": quien_completa,
            "ticket_error": ticket_error,
        }

    def sync_local_to_supabase(self) -> int:
        """Sincroniza compromisos pendientes guardados en SQLite local hacia Supabase si aún no existen allá."""
        if not self.is_connected():
            return 0
        db_path = self._init_local_db()
        if not db_path or not os.path.exists(db_path):
            return 0

        synced = 0
        try:
            res_rem = self.client.table("compromisos_diarios").select("consultor,tarea,fecha_objetivo").execute()
            existentes = {
                (
                    str(r.get("consultor") or "").strip().upper(),
                    str(r.get("tarea") or "").strip(),
                    str(r.get("fecha_objetivo") or "")[:10],
                )
                for r in (res_rem.data or [])
            }
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM compromisos_diarios WHERE estado IN ('pendiente', 'vista', 'en_proceso') ORDER BY id ASC"
                ).fetchall()
                for row in rows:
                    r = dict(row)
                    key = (
                        str(r.get("consultor") or "").strip().upper(),
                        str(r.get("tarea") or "").strip(),
                        str(r.get("fecha_objetivo") or "")[:10],
                    )
                    if key in existentes or not key[1]:
                        continue
                    payload = {
                        "consultor": key[0] or "MELANI",
                        "tarea": key[1],
                        "fecha_objetivo": key[2] or datetime.now(pytz.timezone(settings.TIMEZONE)).date().isoformat(),
                        "estado": str(r.get("estado") or "pendiente"),
                        "origen": r.get("origen") or "telegram",
                        "cliente": r.get("cliente") or "GENERAL",
                        "modulo": r.get("modulo") or "OTROS",
                        "tiempo_estimado_min": int(r.get("tiempo_estimado_min") or 60),
                    }
                    try:
                        ins = self.client.table("compromisos_diarios").insert(payload).execute()
                        if ins.data:
                            synced += 1
                            existentes.add(key)
                    except Exception as e_ins:
                        logger.debug(f"sync_local_to_supabase fila #{r.get('id')}: {e_ins}")
        except Exception as e:
            logger.debug(f"sync_local_to_supabase omitido: {e}")
        return synced

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
