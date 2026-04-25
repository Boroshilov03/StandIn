import os
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def run() -> None:
    load_dotenv()
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth/callback")
    if not client_id or not client_secret:
        raise RuntimeError("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "project_id": "standin-local",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    print("Open this URL in a browser and complete consent:\n")
    print(auth_url)
    print("\nPaste the full callback URL after consent:")
    callback_url = input("> ").strip()

    code = parse_qs(urlparse(callback_url).query).get("code", [None])[0]
    if not code:
        raise RuntimeError("No OAuth code found in callback URL.")

    flow.fetch_token(code=code)
    refresh_token = flow.credentials.refresh_token
    if not refresh_token:
        raise RuntimeError(
            "No refresh token returned. Re-run with prompt=consent and make sure this is first grant."
        )
    print("\nRefresh token:\n")
    print(refresh_token)
    print("\nSave to .env as USER_<USER_ID>_REFRESH_TOKEN=...")


if __name__ == "__main__":
    run()
