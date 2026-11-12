import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables del .env
_curr = Path(__file__).resolve().parent
if (_curr / ".env").exists() or (_curr / "requirements.txt").exists():
    BASE_DIR = _curr
else:
    BASE_DIR = _curr.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

def get_credentials_path() -> str:
    cred = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
    if not os.path.isabs(cred):
        return str(BASE_DIR / cred)
    return cred

def _clean_env(name: str, default: str = "") -> str:
    """Lee una variable de entorno limpiando espacios y comillas accidentales al pegarla en la nube."""
    val = os.getenv(name, default)
    return val.strip().strip('"').strip("'") if isinstance(val, str) else default

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = _clean_env("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_GROUP_CHAT_ID: str = _clean_env("TELEGRAM_GROUP_CHAT_ID", "")
    
    SUPABASE_URL: str = _clean_env("SUPABASE_URL", "")
    SUPABASE_KEY: str = _clean_env("SUPABASE_KEY", "")
    
    GOOGLE_SERVICE_ACCOUNT_FILE: str = get_credentials_path()
    GOOGLE_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    GOOGLE_TOKEN_JSON: str = os.getenv("GOOGLE_TOKEN_JSON", "").strip()
    GOOGLE_CALENDAR_ID: str = _clean_env("GOOGLE_CALENDAR_ID", "primary")
    GOOGLE_CALENDAR_ICS_URL: str = _clean_env("GOOGLE_CALENDAR_ICS_URL", "")
    
    GEMINI_API_KEY: str = _clean_env("GEMINI_API_KEY", "")
    TIMEZONE: str = _clean_env("TIMEZONE", "America/Argentina/Buenos_Aires")
    DEBUG: bool = _clean_env("DEBUG", "True").lower() in ("true", "1", "yes")

settings = Settings()
