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
| `token.json` | OAuth **user token** (login result) | **Script**, after first authorization |

The script **cannot create `credentials.json`**, but **will create `token.json` automatically**.

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

Start the server:

```bash
python3 birthdays_server.py
```

On **first run only**:
- Open stated URL in a browser window on the same machine
- Log in with your Google account
- Approve access

The script will:
- create `token.json`
- store it locally
- reuse it on future starts
- refresh it automatically

You should see log output like:

```text
OAuth authorization completed (startup)
Saved token.json (startup)
Google People API service ready
```

---

## Running on a headless system (no UI)

### Recommended approach

1. Run the script **once on a machine with a browser**
2. Let it create `token.json`
3. Copy both files to the server:

```bash
scp credentials.json token.json user@server:/path/to/app/
```

4. Start the server on the headless system:

```bash
python3 birthdays_server.py
```

As long as `token.json` exists, **no UI is needed anymore**.

---

## _OPTIONAL:_ Run as a systemd service (Linux)

This is a recommended setup for long-running servers.
Systemd service running as a dedicated users and files in the home folder of this user.

### Suggested directory layout

Adjust paths if needed:

```text
/home/google-birthdays/
├── birthdays_server.py
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

`systemd` cannot complete the first OAuth login. Do this once (on a machine with a browser),
or run it once manually as the service user if a browser is available:

```bash
cd /home/google-birthdays
sudo -u googlebirthdays .venv/bin/python birthdays_server.py
```

This creates `token.json`. After that, start the systemd service normally.

> Headless servers: create `token.json` on a UI machine, then copy `token.json` + `credentials.json` to the server.


## Using the ICS feed

Once the server is running:

```text
http://<host>:8080/birthdays.ics
```

Add this URL to any calendar app as a **subscribed calendar**.

Calendar clients will refresh automatically (typically every 30–120 minutes).

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
curl -I http://localhost/birthdays.ics
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
- OAuth consent screen will remain in *Testing* (fine for personal use)

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