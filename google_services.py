"""Client Google condivisi da Drive e Google Slides.

La webapp conserva soltanto il refresh token nei Secrets di Streamlit e
richiede un access token fresco a ogni generazione. In questo modo non dipende
dal token di accesso (breve) salvato settimane prima.
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def build_google_services(secrets):
    """Restituisce credenziali fresche e client Drive/Slides autenticati."""
    if "oauth_token" not in secrets:
        raise RuntimeError("Secrets mancanti: sezione [oauth_token].")

    token = dict(secrets["oauth_token"])
    required = [
        "refresh_token",
        "token_uri",
        "client_id",
        "client_secret",
        "scopes",
    ]
    missing = [key for key in required if not token.get(key)]
    if missing:
        raise RuntimeError(
            f"Secrets OAuth incompleti. Mancano: {', '.join(missing)}"
        )

    credentials = Credentials(
        token=None,
        refresh_token=token["refresh_token"],
        token_uri=token["token_uri"],
        client_id=token["client_id"],
        client_secret=token["client_secret"],
        scopes=list(token["scopes"]),
    )
    credentials.refresh(Request())

    drive = build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
    slides = build(
        "slides",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
    return credentials, drive, slides


def build_drive_service(secrets):
    """Restituisce solo il client Drive usando comunque un token fresco."""
    _, drive, _ = build_google_services(secrets)
    return drive
