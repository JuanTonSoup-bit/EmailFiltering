"""OAuth handling for the Gmail API.

On first run this opens a browser for consent and caches the resulting token so
subsequent runs are non-interactive. Requires an OAuth *Desktop app* client
secret downloaded from the Google Cloud Console (see backend/README.md).
"""

from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..config import settings


def get_credentials() -> Credentials:
    creds: Credentials | None = None
    scopes = list(settings.gmail_scopes)

    if os.path.exists(settings.gmail_token_file):
        creds = Credentials.from_authorized_user_file(
            settings.gmail_token_file, scopes
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(settings.gmail_credentials_file):
                raise FileNotFoundError(
                    f"Missing OAuth client secret at "
                    f"'{settings.gmail_credentials_file}'. Download it from the "
                    f"Google Cloud Console and set GMAIL_CREDENTIALS_FILE."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.gmail_credentials_file, scopes
            )
            creds = flow.run_local_server(port=0)

        with open(settings.gmail_token_file, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    return creds
