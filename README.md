# 🤖 Asistente de Operaciones: Telegram + Supabase + Google Calendar

Asistente inteligente para equipo de trabajo (vos y tu jefe). Permite:
- **Cargar tickets y horas de trabajo** con lenguaje natural o comandos.
- **Crear y consultar eventos** en Google Calendar.
- **Resúmenes automáticos diarios** (agenda matutina a las 08:30 y horas cargadas a las 18:30).
- **Consultas inteligentes** con Google Gemini.

---

## 📁 Estructura del Proyecto

```
asistente-telegram/
├── requirements.txt           # Dependencias de Python
├── schema.sql                 # Script SQL para tablas en Supabase
├── .env.example               # Plantilla de variables de entorno
├── credentials.json           # (A agregar) Llave de Google Service Account
├── src/
│   ├── config.py              # Carga de variables de entorno
│   ├── database.py            # Conexión y operaciones con Supabase
│   ├── calendar_service.py    # Integración con Google Calendar API
│   ├── ai_service.py          # Procesamiento de lenguaje natural con Gemini
│   └── bot.py                 # Bot de Telegram y tareas programadas
```

---

## 🚀 Guía de Configuración Paso a Paso

### 1. Base de Datos (Supabase)
1. Ingresá a tu proyecto en [Supabase](https://supabase.com/).
2. Andá a **SQL Editor** -> **New Query**.
3. Copiá y pegá el contenido de [`schema.sql`](schema.sql) y ejecutalo (`Run`).
4. Andá a **Table Editor** -> `usuarios` e insertá al menos dos registros iniciales con sus nombres y emails (para vos y tu jefe):
   ```sql
   INSERT INTO public.usuarios (nombre, email, rol) VALUES 
   ('Melani', 'tu_email@empresa.com', 'colaborador'),
   ('Nombre Jefe', 'email_jefe@empresa.com', 'jefe');
   ```

### 2. Bot de Telegram
1. En Telegram, hablá con [@BotFather](https://t.me/BotFather).
2. Enviá `/newbot` y seguí los pasos para asignarle un nombre y usuario.
3. Copiá el `API TOKEN` que te da BotFather.
4. (Opcional para el grupo): Creá un grupo con vos, tu jefe y agregá al bot como administrador. Podés obtener el ID del grupo agregando a `@userinfobot` o reenviando un mensaje.

### 3. Google Calendar API (Service Account)
1. Andá a [Google Cloud Console](https://console.cloud.google.com/).
2. Creá un proyecto nuevo o seleccioná uno existente.
3. Habilitá la **Google Calendar API**.
4. En **IAM y administración** > **Cuentas de servicio**:
   - Creá una nueva cuenta de servicio (ej: `asistente-bot`).
   - Creá una clave en formato **JSON** y descargala.
   - Renombrá el archivo a `credentials.json` y guardalo dentro de la carpeta `asistente-telegram/`.
5. Copiá el email de la Service Account (ej: `asistente-bot@tu-proyecto.iam.gserviceaccount.com`).
6. Abrí [Google Calendar](https://calendar.google.com/), andá a la configuración del calendario que quieren usar y en **"Compartir con personas o grupos específicos"** agregá el email de la Service Account con permiso **"Realizar cambios en eventos"**.

### 4. Google Gemini API
1. Obtené una clave gratuita en [Google AI Studio](https://aistudio.google.com/).

### 5. Configurar el archivo `.env`
Copiá la plantilla y completá tus credenciales:
```bash
cp .env.example .env
```

---

## 💻 Instalación y Ejecución

1. Crear y activar entorno virtual:
```bash
cd asistente-telegram
python3 -m venv venv
source venv/bin/activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Iniciar el bot:
```bash
python -m src.bot
```

---

## 💬 Cómo Usarlo en Telegram

1. **Vincularse por primera vez:**
   - En el chat privado con el bot, enviá:
     `/vincular tu_email@empresa.com`
2. **Cargar horas de trabajo:**
   - _"Cargá 2 horas en Cliente XYZ por relevamiento y armado de presupuesto"_
   - _"Registrá 1.5 horas de desarrollo para Acme"_
3. **Agendar en Google Calendar:**
   - _"Agendá reunión mañana a las 15hs con el equipo de soporte"_
4. **Comandos directos:**
   - `/hoy` : Resumen conjunto de eventos de Google Calendar + horas cargadas hoy.
   - `/horas` : Detalle de horas trabajadas hoy por cada integrante.
   - `/clientes` : Lista de clientes registrados.
