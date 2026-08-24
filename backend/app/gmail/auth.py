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


SIGN_IN_HINT = (
    "No usable Gmail token. Run the one-time sign-in from backend/:\n"
    '  .venv\\Scripts\\python.exe -c "from app.gmail.auth import '
    'get_credentials; get_credentials()"'
)


def get_credentials(interactive: bool = True) -> Credentials:
    """Load cached credentials, refreshing or obtaining them as needed.

    `interactive` controls whether this may open a browser for consent.

    It must be False anywhere that runs unattended -- the poller and the
    /api/scan endpoint. Those run inside a background server that is started
    by a logon task, and a consent window appearing unbidden a few seconds
    after every sign-in is both alarming and useless: nobody knows what
    launched it, and clicking through it is exactly the reflex an
    anti-phishing tool should not be training. Unattended callers get a clear
    error telling them to run the sign-in deliberately instead.

    Refreshing an existing token stays allowed in both modes -- that is
    non-interactive by nature and is what keeps a signed-in install working.
    """
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
            # Order matters: a missing client secret is the more specific and
            # more actionable problem, so report it before falling back to
            # "go and sign in" -- which you cannot do without that file.
            if not os.path.exists(settings.gmail_credentials_file):
                raise FileNotFoundError(
                    f"Missing OAuth client secret at "
                    f"'{settings.gmail_credentials_file}'. Download it from the "
                    f"Google Cloud Console and set GMAIL_CREDENTIALS_FILE."
                )
            if not interactive:
                raise RuntimeError(SIGN_IN_HINT)
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.gmail_credentials_file, scopes
            )
            creds = flow.run_local_server(port=0)

        with open(settings.gmail_token_file, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    return creds
