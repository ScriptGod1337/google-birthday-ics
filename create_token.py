#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("birthdays-token")

SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
CREDENTIALS_JSON = Path(os.getenv("GOOGLE_OAUTH_CREDENTIALS", "credentials.json"))
TOKEN_JSON = Path(os.getenv("GOOGLE_OAUTH_TOKEN", "token.json"))


def print_credentials_help_and_exit() -> None:
    msg = f"""
[ERROR] Missing OAuth client file: {CREDENTIALS_JSON}

Create an OAuth client in Google Cloud Console:
1) Enable the People API
2) Configure the OAuth consent screen
3) Create credentials -> OAuth client ID
   - Application type: Desktop app
4) Download the JSON and save it as: {CREDENTIALS_JSON}
"""
    sys.stderr.write(msg.strip() + "\n")
    sys.exit(2)


def main() -> None:
    if not CREDENTIALS_JSON.exists():
        print_credentials_help_and_exit()

    log.info("Starting OAuth browser flow")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_JSON), SCOPES)
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        success_message="Auth complete. You may close this tab.",
        timeout_seconds=300,
    )

    if not creds.refresh_token:
        sys.stderr.write(
            "OAuth completed, but Google did not return a refresh token. "
            "Revoke this app in your Google Account permissions and try again.\n"
        )
        sys.exit(2)

    TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")
    log.info("Saved %s", TOKEN_JSON)


if __name__ == "__main__":
    main()
