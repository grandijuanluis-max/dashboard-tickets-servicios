"""Script de autorización única vía OAuth 2.0 (App de escritorio) para Google Calendar.

Uso:
    1. Guardá el JSON de 'ID de cliente de OAuth (App de escritorio)' como
       `oauth_credentials.json` (o `credentials.json`) en esta carpeta.
    2. Ejecutá: `./venv/bin/python auth_calendar.py`
    3. Iniciá sesión con la cuenta de Google que tiene acceso al calendario y aceptá los permisos.
    4. Se generará `token.json` automáticamente para que el bot pueda agendar reuniones.
"""

import json
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def find_oauth_client_file() -> Path:
    for name in ("oauth_credentials.json", "credentials.json"):
        candidate = BASE_DIR / name
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if "installed" in data or "web" in data:
                    return candidate
            except Exception:
                continue
    raise FileNotFoundError(
        "No encontré un JSON de cliente OAuth ('installed' o 'web') en "
        "`oauth_credentials.json` ni en `credentials.json`."
    )


def main():
    try:
        client_file = find_oauth_client_file()
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    print(f"🔐 Usando credenciales OAuth de: {client_file.name}")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    token_path = BASE_DIR / "token.json"
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"✅ ¡Listo! Se guardó {token_path.name}. Ya podés iniciar el bot y agendar eventos.")


if __name__ == "__main__":
    main()
