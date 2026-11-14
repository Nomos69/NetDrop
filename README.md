<div align="center">
  <img src="static/logo.svg" width="88" alt="NetDrop logo">
  <h1>NetDrop</h1>
  <p><strong>Temporary file and clipboard sharing for local networks and the web.</strong></p>
  <p>Create a PIN-protected room, invite participants, and share files, text, and links in real time—directly from a browser.</p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.12-282828?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.12">
    <img src="https://img.shields.io/badge/FastAPI-ASGI-484848?style=flat-square&amp;logo=fastapi&amp;logoColor=white" alt="FastAPI ASGI">
    <img src="https://img.shields.io/badge/WebSockets-Live_updates-686868?style=flat-square" alt="WebSocket live updates">
    <img src="https://img.shields.io/badge/Brevo-Email_API-888888?style=flat-square" alt="Brevo email API">
  </p>
</div>

## About NetDrop

NetDrop is a lightweight, browser-based sharing application for classrooms,
offices, laboratories, and small groups. A host creates a temporary room and
participants join using a 12-character room ID and a four-digit PIN. Everyone in
the room can share files, notes, and links while WebSockets keep the feed and
member list synchronized.

NetDrop supports two environments:

| Mode | Best for | Connection |
| --- | --- | --- |
| **Local Network** | Fast sharing in the same room, office, or Wi-Fi network | Devices connect to the host computer's LAN address |
| **Online** | Sharing between different networks | Participants connect to a separately deployed HTTPS server |

Each server owns its rooms and uploads. Local and online servers do not copy or
synchronize data with one another.

## Features

- PIN-protected temporary rooms with cookie-based browser sessions
- File uploads and attachment downloads with a configurable size limit
- Shared text and validated HTTP/HTTPS links
- Live room feed and member presence through WebSockets
- Automatic reconnect and feed resynchronization
- Multi-file upload queue with progress, cancel, and retry controls
- Configurable file expiry and fixed room expiry
- Owner controls for deleting content, removing members, and closing rooms
- Copyable invitation links and locally generated QR codes
- Optional opt-in upload alerts and expiring room invitations through Brevo's transactional email REST API
- Responsive monochrome interface for desktop and mobile browsers
- Health endpoint for Render and external uptime monitoring

## How it works

```text
Host creates a room
        │
        ├── shares room ID + PIN
        ├── copies invitation link
        ├── displays QR invitation
        └── sends optional Brevo email invitation
                         │
Participants join from a browser
                         │
Files, notes, links, members, and expiry updates stay synchronized
```

The invitation URL contains the room ID but never the PIN. Participants must
enter the PIN after opening the link or scanning the QR code.

## Technology

| Layer | Technology | Role |
| --- | --- | --- |
| Backend | Python, FastAPI, Uvicorn | HTTP API, authorization, cleanup, and static delivery |
| Realtime | WebSockets | Live feed, member presence, and reconnect updates |
| Frontend | HTML, CSS, JavaScript | Responsive browser interface with no framework required |
| Validation | Pydantic | Request and configuration validation |
| QR invitations | qrcode | Server-generated SVG invitation codes |
| Email invitations | Brevo REST API, HTTPX | Transactional room invitations |
| Storage | Memory and temporary local files | Rooms/sessions in memory and uploads under `data/uploads/` |

## Quick start

### Requirements

- Python 3.12 or a compatible Python 3 release
- A modern browser
- Devices on the same LAN for Local Network mode

### Run locally

```bash
git clone https://github.com/Nomos69/NetDrop.git
cd NetDrop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

Open `http://127.0.0.1:8000` on the host computer.

For another device on the same network, find the host address with:

```bash
hostname -I
```

Then open `http://HOST_LAN_IP:8000`, for example
`http://192.168.1.12:8000`. The host firewall must allow the configured port.

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Using NetDrop

1. Select **Local Network** or **Online**.
2. Choose **Create a room**, enter a name, and create a four-digit PIN.
3. Share the room ID and PIN, copy the invitation link, show the QR code, or send
   an email invitation.
4. Participants open NetDrop, enter the room ID and PIN, and optionally choose a
   display name.
5. Share files, notes, or links. Room members receive updates automatically.
6. Use **Leave room** to leave without closing it. The owner can use **Close
   room** to revoke access and remove its shared content.

Display names are participant-provided labels, not verified identities.

## Configuration

Copy `.env.example` to `.env`. Environment variables override values from the
file, and the server must be restarted after changes.

| Variable | Default | Description |
| --- | --- | --- |
| `NETDROP_HOST` | `0.0.0.0` | Address the server listens on |
| `NETDROP_PORT` | `8000` | Local HTTP port |
| `NETDROP_FILE_TTL_SECONDS` | `1800` | Lifetime of uploaded files |
| `NETDROP_MAX_UPLOAD_BYTES` | `50000000` | Exact maximum size of each uploaded file |
| `NETDROP_CLEANUP_INTERVAL_SECONDS` | `5` | Interval between cleanup scans |
| `NETDROP_ROOM_TTL_SECONDS` | `259200` | Maximum room lifetime: three days |
| `NETDROP_INVITATION_TTL_SECONDS` | `86400` | Email invitation-token lifetime |
| `NETDROP_SHARING_MODE` | `local` | This server's mode: `local` or `online` |
| `NETDROP_LOCAL_URL` | empty | Reachable LAN origin used in local invitations |
| `NETDROP_ONLINE_URL` | empty | Public HTTPS origin used in online invitations |
| `BREVO_API_KEY` | empty | Optional Brevo API key; never commit this value |
| `BREVO_SENDER_EMAIL` | empty | Sender verified in Brevo |
| `BREVO_SENDER_NAME` | `NetDrop` | Sender name shown in invitation emails |

Example local configuration:

```dotenv
NETDROP_SHARING_MODE=local
NETDROP_LOCAL_URL=http://192.168.1.12:8000
NETDROP_ONLINE_URL=https://your-service.onrender.com
```

Example online configuration:

```dotenv
NETDROP_SHARING_MODE=online
NETDROP_ONLINE_URL=https://your-service.onrender.com
```

Use only the HTTPS origin for `NETDROP_ONLINE_URL`: no path, query, fragment, or
credentials.

## Deploy on Render

Create a **Web Service** from this repository and use:

| Render setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers` |
| Health check path | `/up` |

Add these environment variables in **Render → Environment**:

```text
NETDROP_SHARING_MODE=online
NETDROP_ONLINE_URL=https://YOUR-EXACT-SERVICE.onrender.com
```

Use one worker and one service instance. NetDrop stores rooms, browser sessions,
members, and content indexes in process memory, so multiple workers would not
share the same state.

Render supplies HTTPS, but free instances and their files are temporary. A
restart or redeployment clears rooms and may remove uploads. The `/up` endpoint
only confirms that the HTTP service responds; it does not test rooms, uploads, or
WebSockets.

## Brevo email invitations

NetDrop uses Brevo's transactional **HTTPS REST API**, not an SMTP connection.

1. In Brevo, open **Settings → SMTP & API → API Keys & MCP**.
2. Generate a restricted API key named `NetDrop`.
3. Give it **Transactional email → All** permission and leave unrelated
   permissions disabled.
4. Verify a sender address. For reliable inbox delivery, use a domain you own and
   authenticate its DKIM and DMARC records.
5. Add the following secrets to `.env` or Render Environment:

```dotenv
BREVO_API_KEY=your-private-api-key
BREVO_SENDER_EMAIL=your-verified-sender@example.com
BREVO_SENDER_NAME=NetDrop
```

Only the room owner can send an invitation. Each email has a random, expiring
server-validated token; it never includes the room PIN. Recipients still need the
PIN separately to enter the room.
Invitations are limited to one attempt every 30 seconds and 10 attempts per hour
per browser session. Duplicate attempts to the same room and recipient are
blocked for five minutes.

Brevo API acceptance does not prove inbox placement. Check Brevo's transactional
logs and the recipient's spam folder when troubleshooting delivery.

## Security and privacy

- PINs are salted and hashed with `scrypt` in server memory.
- PINs are excluded from invitation links, QR codes, access logs, and application
  logs.
- Room membership and owner operations are checked on the server.
- Cross-site writes require NetDrop's custom request header.
- Uploads use server-generated storage names outside the public static directory.
- Files download as attachments and expire at the configured deadline.
- Unsafe or expired download requests are rejected.
- Notification logs exclude recipients, PINs, message bodies, and API keys.
- Online mode requires HTTPS and secure WebSockets.

Local mode uses HTTP and does not encrypt network traffic. Use it only on a
trusted LAN. NetDrop is a temporary-sharing prototype, not permanent cloud
storage or an identity platform.

## Data lifecycle and limits

- Files, notes, and links expire after 30 minutes by default.
- New downloads are refused at the exact expiry deadline.
- Active transfers can finish before their files are removed.
- Rooms retire after the configured idle period when no live members or transfers
  remain.
- A server restart clears all room, membership, ownership, and content indexes.
- The prototype supports up to 100 rooms, 500 items per room, and 1,000 active
  browser sessions in one process.
- Join attempts are limited to five per minute per client IP.

## Project structure

```text
NetDrop/
├── app/
│   ├── config.py          # Environment loading and validation
│   ├── main.py            # FastAPI application and health endpoint
│   ├── rooms.py           # Rooms, sessions, PINs, ownership, and QR codes
│   ├── files.py           # Files, notes, links, expiry, and cleanup
│   ├── realtime.py        # Authorized WebSocket updates
│   └── notifications.py   # Brevo invitation API integration
├── static/
│   ├── index.html         # Browser interface
│   ├── styles.css         # Responsive monochrome design
│   ├── app.js             # Client behavior and live updates
│   ├── logo.svg
│   └── favicon.svg
├── tests/                 # API and browser workflow checks
├── docs/                  # Verification notes and project documents
├── data/uploads/          # Temporary runtime uploads; ignored by Git
├── .env.example
├── PROJECT_PLAN.md
└── requirements.txt
```

## Testing

Install development dependencies and run the API suite:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py' -v
```

Install Chromium for Playwright, then run the browser workflows:

```bash
python -m playwright install chromium --no-shell
python tests/browser_live.py
python tests/browser_modes.py
python tests/browser_controls.py
python tests/browser_notifications.py
```

The automated checks cover authorization, room isolation, live updates,
reconnection, expiration, cleanup, ownership, uploads, mode switching, QR codes,
Brevo request behavior, and responsive layouts. Browser checks use isolated local
servers and mocked provider responses; they do not prove a public deployment or
real email delivery.

See [docs/verification.md](docs/verification.md) for recorded evidence and its
boundaries.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Phone cannot open the local host | Use the computer's LAN IP, connect both devices to the same network, and check the firewall and router client isolation |
| `127.0.0.1` fails on another device | That address points to the device itself; use the host computer's LAN IP |
| Room ID or PIN is rejected | Use the 12-character room ID and the original four-digit PIN; a restart invalidates old rooms |
| Live updates keep reconnecting | Check connectivity, keep the host running, and use **Refresh** as a fallback |
| File disappeared | It expired, the owner deleted it, the room closed, or the server restarted |
| Render deploy times out after startup | Set the Render health check path to `/up` |
| Invitation shows the wrong hostname | Set `NETDROP_LOCAL_URL` or `NETDROP_ONLINE_URL` to the exact reachable origin and create a new room |
| Email lands in spam | Authenticate the sender domain with DKIM and DMARC and inspect Brevo transactional logs |

## Current status and roadmap

Implemented:

- Local and online room modes
- Temporary file, text, and link sharing
- Live updates, reconnection, and member presence
- Owner controls, QR invitations, upload queue, expiry, and cleanup
- Brevo REST API room invitations
- Responsive desktop and mobile interface

Planned or optional:

- Persistent room and retry state using SQLite or another durable store
- Durable object storage for hosted uploads
- Brevo delivery webhooks and delivery-state display
- Automatic opt-in notifications after new uploads
- Packaged desktop launchers for supported operating systems

The detailed implementation phases are documented in
[PROJECT_PLAN.md](PROJECT_PLAN.md).

---

NetDrop is designed for short-lived collaboration. Share only with intended room
participants and treat every room as temporary.
