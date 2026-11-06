import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables del .env
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

def get_credentials_path() -> str:
    cred = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
    if not os.path.isabs(cred):
        return str(BASE_DIR / cred)
    return cred

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_GROUP_CHAT_ID: str = os.getenv("TELEGRAM_GROUP_CHAT_ID", "")
    
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    GOOGLE_SERVICE_ACCOUNT_FILE: str = get_credentials_path()
    GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Argentina/Buenos_Aires")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

settings = Settings()
