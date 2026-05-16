#!/usr/bin/env python3
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import datetime as dt
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from icalendar import Calendar, Event

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("birthdays")

# ---------------- Config ----------------
SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
CREDENTIALS_JSON = Path(os.getenv("GOOGLE_OAUTH_CREDENTIALS", "credentials.json"))
TOKEN_JSON = Path(os.getenv("GOOGLE_OAUTH_TOKEN", "token.json"))
ICS_FILENAME = os.getenv("ICS_FILENAME", "birthdays.ics").strip().lstrip("/")
if not ICS_FILENAME:
    ICS_FILENAME = "birthdays.ics"
if not ICS_FILENAME.endswith(".ics"):
    ICS_FILENAME = f"{ICS_FILENAME}.ics"
ICS_PATH = f"/{ICS_FILENAME}"

FALLBACK_YEAR = 1970
LEAP_YEAR = 1972

_service = None  # initialized at startup


def print_credentials_help_and_exit() -> None:
    msg = f"""
[ERROR] Missing OAuth client file: {CREDENTIALS_JSON}

This script CANNOT generate credentials.json automatically.
You must create an OAuth Client in Google Cloud Console and download it.

Do this once:
1) Open Google Cloud Console -> APIs & Services -> Library
   - Enable: "People API"
2) APIs & Services -> OAuth consent screen
   - Configure (External or Internal)
3) APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
   - Application type: "Desktop app"
4) Download the JSON and save it as: {CREDENTIALS_JSON}

Then run create_token.py on a machine with a browser to create {TOKEN_JSON}.
"""
    sys.stderr.write(msg.strip() + "\n")
    sys.exit(2)


def print_token_help_and_exit(reason: str) -> None:
    msg = f"""
[ERROR] {reason}

This server does not run OAuth login. Create a fresh token on a machine with a
browser, then copy it to this server:

    python3 create_token.py

Expected files:
  OAuth client: {CREDENTIALS_JSON}
  User token:   {TOKEN_JSON}
"""
    sys.stderr.write(msg.strip() + "\n")
    sys.exit(2)


# ---------------- Google API ----------------
def ensure_service_at_startup():
    """Ensures token.json exists and a People API service is ready BEFORE server starts."""
    global _service
    log.info("Initializing Google People API service (startup)")

    if not CREDENTIALS_JSON.exists():
        print_credentials_help_and_exit()

    creds: Optional[Credentials] = None
    if TOKEN_JSON.exists():
        log.info("Found existing token.json")
        creds = Credentials.from_authorized_user_file(str(TOKEN_JSON), SCOPES)
    else:
        print_token_help_and_exit(f"Missing OAuth token file: {TOKEN_JSON}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Refreshing expired OAuth token (startup)")
            try:
                creds.refresh(Request())
            except RefreshError:
                print_token_help_and_exit(
                    "Google rejected the saved OAuth refresh token. "
                    "Run create_token.py again to re-authorize."
                )
        else:
            print_token_help_and_exit(
                f"OAuth token is invalid and cannot be refreshed: {TOKEN_JSON}"
            )

        TOKEN_JSON.write_text(creds.to_json(), encoding="utf-8")
        log.info("Saved token.json (startup)")

    _service = build("people", "v1", credentials=creds, cache_discovery=False)
    log.info("Google People API service ready (startup)")


def get_service():
    if _service is None:
        raise RuntimeError("Service not initialized. Startup init failed?")
    return _service


# ---------------- ICS generation ----------------
def generate_ics() -> bytes:
    log.info("Generating ICS feed")

    svc = get_service()
    cal = Calendar()
    cal.add("prodid", "-//Contacts Birthdays//")
    cal.add("version", "2.0")

    page_token = None
    event_count = 0

    while True:
        res = svc.people().connections().list(
            resourceName="people/me",
            personFields="names,birthdays",
            pageToken=page_token,
            pageSize=1000,
        ).execute()

        for p in res.get("connections", []):
            name = (p.get("names") or [{}])[0].get("displayName", "Unknown")
            for b in p.get("birthdays", []):
                d = b.get("date")
                if not d or not d.get("month") or not d.get("day"):
                    continue

                year = d.get("year") or FALLBACK_YEAR
                try:
                    start = dt.date(year, d["month"], d["day"])
                except ValueError:
                    if d["month"] == 2 and d["day"] == 29:
                        start = dt.date(LEAP_YEAR, 2, 29)
                    else:
                        continue

                ev = Event()
                ev.add("uid", f"{p.get('resourceName','person/unknown')}-{d['month']:02d}{d['day']:02d}")
                ev.add("dtstart", start)
                ev.add("dtend", start + dt.timedelta(days=1))
                ev.add("rrule", {"freq": "YEARLY"})
                ev.add("summary", f"🎂 {name}")
                cal.add_component(ev)
                event_count += 1

        page_token = res.get("nextPageToken")
        if not page_token:
            break

    log.info("ICS generation finished (%d events)", event_count)
    return cal.to_ical()


# ---------------- HTTP server ----------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        log.info("HTTP request: %s %s", self.command, self.path)

        if self.path != ICS_PATH:
            self.send_error(404)
            return

        try:
            ics = generate_ics()
        except Exception:
            log.exception("Failed to generate ICS")
            self.send_error(500, "ICS generation failed")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Content-Length", str(len(ics)))
        self.end_headers()
        self.wfile.write(ics)
        log.info("ICS served successfully")


# ---------------- Main ----------------
if __name__ == "__main__":
    ensure_service_at_startup()  # OAuth/token happens here, before serving

    host, port = "0.0.0.0", 8080
    log.info("Starting HTTP server on %s:%s", host, port)
    log.info("Endpoint: http://%s:%s%s", host, port, ICS_PATH)

    HTTPServer((host, port), Handler).serve_forever()
