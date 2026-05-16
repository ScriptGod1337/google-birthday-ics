# Google Contacts Birthdays → ICS Feed

Expose birthdays from **Google Contacts** as a **live, subscribable ICS calendar feed**.

This project:
- reads birthdays via the **Google People API**
- generates an **iCalendar (ICS)** feed
- serves it over **HTTP**
- works with **personal Google accounts (Gmail)** and **Workspace**
- is **free** (no billing, no paid APIs)

Typical use cases:
- subscribe to contact birthdays in **Apple Calendar**, **Outlook**, **Nextcloud**
- replace the unreliable internal Google “Birthdays” calendar
- keep full control over your data

---

## Features

- ✅ Live ICS feed (calendar subscription, not one-time export)
- ✅ No Google Workspace required
- ✅ Free Google APIs
- ✅ OAuth handled safely
- ✅ Designed for servers (including headless systems)
- ✅ Minimal dependencies
- ❌ No FastAPI / uvicorn based

---

## Requirements

- Python **3.9+**
- A Google account
- Internet access

Install dependencies:

```bash
pip install -r requirements.txt
```

or as an alternative use a python virtual environment
```bash
sudo apt install python3-venv
./create.venv.sh 
source .venv/bin/activate
```

---

## Activation overview (important)

There are **two different files** involved:

| File | Purpose | Created by |
| ---- | ------- | ---------- |
| `credentials.json` | OAuth **client** (app identity) | **You**, via Google Cloud Console |
| `token.json` | OAuth **user token** (login result) | `create_token.py`, after first authorization |

The project **cannot create `credentials.json`**. Create that in Google Cloud
Console, then run `create_token.py` once to create `token.json`.

---

## Step 1 — Create Google Cloud project

1. Open **Google Cloud Console**
2. Create a **new project** (any name)

No billing account needed.

---

## Step 2 — Enable People API

1. Go to **APIs & Services → Library**
2. Search for **People API**
3. Click **Enable**

---

## Step 3 — Configure OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**
2. User type:
   - **External**
3. App name: anything (e.g. *Contacts Birthdays*)
4. Scopes:
   - leave empty (People API is added implicitly)
5. Save

### Add yourself as test user

While still on the consent screen:
- Scroll to **Test users**
- Add **your Google account email**
- Save

> This is required. Otherwise Google will block login with  
> “app is being tested”.

### Publishing status and refresh-token lifetime

For long-running use, set the OAuth consent screen publishing status to
**In production** after your test login works.

If the OAuth app remains **External / Testing**, Google can issue refresh tokens
that expire after **7 days** for non-basic scopes such as:

```text
https://www.googleapis.com/auth/contacts.readonly
```

When that happens, the server logs an `invalid_grant` refresh error and you must
run `create_token.py` again. Moving the consent screen to **In production**
avoids the Testing-mode 7-day refresh-token lifetime. For personal use, you may
still see an unverified-app warning during login, but you can continue for your
own account.

---

## Step 4 — Create OAuth credentials (`credentials.json`)

1. Go to **APIs & Services → Credentials**
2. Click **Create credentials → OAuth client ID**
3. Application type:
   - **Desktop app**
4. Name: anything
5. Create
6. Download the JSON
7. Rename it to:

```text
credentials.json
```

8. Place it next to the script.

---

## Step 5 — First run (token creation)

Create `token.json` on a machine with a browser:

```bash
python3 create_token.py
```

The token creation script will:
- open your browser
- Log in with your Google account
- Approve access
- create `token.json`

You should see log output like:

```text
Starting OAuth browser flow
Saved token.json
```

After that, start the server:

```bash
python3 birthdays_server.py
```

The server reuses `token.json` and refreshes it automatically. It does not start
OAuth login itself.

---

## Running on a headless system (no UI)

### Recommended approach

1. Create `token.json` on a machine with a browser:

```bash
python3 create_token.py
```

2. Copy both files to the server:

```bash
scp credentials.json token.json user@server:/path/to/app/
```

3. Start the server on the headless system:

```bash
python3 birthdays_server.py
```

As long as `token.json` exists, **no UI is needed anymore**.

The server never starts a new OAuth login. If the token is missing or revoked,
it exits with instructions to run `create_token.py` again on a UI machine.

### If token refresh fails with `invalid_grant`

`invalid_grant: Bad Request` means Google no longer accepts the saved refresh token.
Common causes are a revoked token, changed OAuth credentials, account security changes,
or an OAuth consent app that is still in testing.

Delete `token.json` and authorize again:

```bash
rm token.json
python3 create_token.py
```

Then copy the new `token.json` back to the headless server if you created it on
another machine.

---

## _OPTIONAL:_ Run as a systemd service (Linux)

This is a recommended setup for long-running servers.
Systemd service running as a dedicated users and files in the home folder of this user.

### Suggested directory layout

Adjust paths if needed:

```text
/home/google-birthdays/
├── birthdays_server.py
├── create_token.py
├── credentials.json
├── token.json
├── requirements.txt
├── run_birthdays_server.sh
└── .venv/
```

### Create a dedicated user (recommended)

```bash
sudo useradd --system --home /home/google-birthdays --shell /sbin/nologin googlebirthdays
sudo mkdir /home/google-birthdays
sudo chown -R googlebirthdays:googlebirthdays /home/google-birthdays
```

> The service must run as the same user that owns `token.json`, otherwise token refresh may fail.

### systemd unit file

Create:

```bash
sudo nano /etc/systemd/system/google-birthdays.service
```

Paste:

```ini
[Unit]
Description=Google Contacts Birthdays ICS Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=googlebirthdays
Group=googlebirthdays
WorkingDirectory=/home/google-birthdays
ExecStart=bash -c /home/google-birthdays/run_birthdays_server.sh
Restart=on-failure
RestartSec=5

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=/home/google-birthdays

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable google-birthdays
sudo systemctl start google-birthdays
```

Check status:

```bash
sudo systemctl status google-birthdays
```

Follow logs:

```bash
journalctl -u google-birthdays -f
```

### First-time OAuth on servers

`systemd` cannot complete OAuth login. Create `token.json` on a machine with a
browser:

```bash
python3 create_token.py
```

Then copy `credentials.json` and `token.json` to `/home/google-birthdays/` and
start the systemd service normally.

> Headless servers: create `token.json` on a UI machine, then copy `token.json` + `credentials.json` to the server.


## Using the ICS feed

Once the server is running:

```text
http://<host>:8080/birthdays.ics
```

Add this URL to any calendar app as a **subscribed calendar**.

Calendar clients will refresh automatically (typically every 30–120 minutes).

The default feed filename is `birthdays.ics`. Override it with `ICS_FILENAME`:

```bash
ICS_FILENAME=family-birthdays.ics python3 birthdays_server.py
```

Then subscribe to:

```text
http://<host>:8080/family-birthdays.ics
```

`ICS_FILENAME` accepts either `family-birthdays` or `family-birthdays.ics`.
If the `.ics` suffix is missing, the server adds it automatically.

## Configuration

| Variable | Default | Used by | Purpose |
| -------- | ------- | ------- | ------- |
| `GOOGLE_OAUTH_CREDENTIALS` | `credentials.json` | `create_token.py`, `birthdays_server.py` | Path to the OAuth client JSON from Google Cloud Console |
| `GOOGLE_OAUTH_TOKEN` | `token.json` | `create_token.py`, `birthdays_server.py` | Path to the saved user token |
| `ICS_FILENAME` | `birthdays.ics` | `birthdays_server.py` | Feed filename/path served by the HTTP server |

## _OPTIONAL:_ Reverse proxy with Caddy (Docker)

You can expose the ICS feed safely via **Caddy** acting as a reverse proxy in front of the Python server.

This is recommended if you want:
- a stable URL
- optional HTTPS
- no direct exposure of the Python process

### Assumptions
- The birthdays server listens on `localhost:8080`
- Docker is installed
- Caddy runs on the same host

---

### HTTPS with automatic TLS (recommended)

If you have a domain pointing to this server (for example `birthdays.example.com`):

```bash
docker run -d \
  --name caddy-birthdays \
  --restart unless-stopped \
  -p 443:443 \
  --add-host=host.docker.internal:host-gateway \
  -v /home/google-birthdays/caddy/data:/data \
  caddy:latest \
  caddy reverse-proxy \
    --from birthdays.example.com \
    --to host.docker.internal:8080
```

Caddy will:
- automatically obtain Let’s Encrypt certificates
- renew certificates automatically
- redirect HTTP to HTTPS

Most calendar clients **strongly prefer HTTPS**.

---

### Verify Caddy

```bash
docker logs -f caddy-birthdays
```

Test the endpoint:

```bash
curl -I http://localhost:8080/birthdays.ics
```

---

## Security notes

- `credentials.json` and `token.json` grant access to **your contacts**
- Do **not** commit them to Git
- Add to `.gitignore`:

```gitignore
credentials.json
token.json
```

- The server exposes **read-only calendar data**
- Recommended: run behind a firewall or reverse proxy if exposed publicly

---

## Costs

- Google People API: **free**
- OAuth: **free**
- No billing account
- No credit card
- No quotas issues for personal use

---

## Limitations

- Google does **not** provide an official birthdays export
- This workaround is currently the **only reliable solution**
- Google OAuth device-code flow does **not** support the required People API
  contacts scope, so token creation uses a Desktop app OAuth client and a
  browser-capable machine
- OAuth consent screen **Testing** mode can make refresh tokens expire after
  **7 days** for the required contacts scope; use **In production** for
  long-running personal use

---

## License

Apache 2.0

---

## FAQ

### Is this officially supported by Google?

The APIs are supported. The use case is not officially “packaged” by Google, but fully allowed.

### Does this require Google Workspace?

No. Standard Gmail accounts work perfectly.

### Will Google ever add a simpler way?

Unlikely. This limitation has existed for over a decade.

---
