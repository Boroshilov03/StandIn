import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_SECRET_PATH = "client_secret.json"
ROOT = Path(__file__).resolve().parents[1]

load_dotenv(ROOT / ".env")

with open(CLIENT_SECRET_PATH, "r", encoding="utf-8") as f:
    client_config = json.load(f)

if "web" in client_config:
    print(
        "client_secret.json is using a Web OAuth client. "
        "For local scripts, create a Desktop OAuth client in Google Cloud "
        "and download that JSON (it should have an 'installed' key)."
    )
    print(
        "If you must keep Web client credentials, add "
        "http://localhost:<port>/ as an authorized redirect URI and set "
        "OAUTH_REDIRECT_PORT to that exact port."
    )
    sys.exit(1)

flow = InstalledAppFlow.from_client_config(
    client_config,
    scopes=SCOPES,
)
port = int(os.getenv("OAUTH_REDIRECT_PORT", "8080"))
login_hint = os.getenv("GOOGLE_LOGIN_HINT")
kwargs = {"prompt": "select_account consent", "access_type": "offline"}
if login_hint:
    kwargs["login_hint"] = login_hint

creds = flow.run_local_server(port=port, **kwargs)
try:
    creds = flow.run_local_server(port=port, **kwargs)
except OSError as exc:
    if getattr(exc, "errno", None) == 48:
        print(f"Port {port} is already in use.")
        print(f"Retry with: OAUTH_REDIRECT_PORT={port + 1} python scripts/oauth_setup.py")
        sys.exit(1)
    raise

print("GOOGLE_REFRESH_TOKEN =", creds.refresh_token)
