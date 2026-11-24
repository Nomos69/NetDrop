<div align="center">
  <img src="static/logo.svg" width="88" alt="NetDrop logo">
  <h1>NetDrop</h1>
  <p><strong>Temporary online file and clipboard sharing.</strong></p>
</div>

## About

NetDrop is an HTTPS-only browser-based sharing app. Create a PIN-protected,
temporary room, invite participants from any network, and share files, text,
and links in real time. Local-network transfer, LAN discovery, and the Windows
local companion have been removed.

## Features

- PIN-protected temporary rooms
- File, text, and link sharing
- Live member and content updates over secure WebSockets
- Copyable invitation links and SVG QR invitations
- Owner controls, automatic expiry, and optional Brevo email invitations

## Deploy and run

NetDrop requires a public HTTPS origin. Configure TLS at your reverse proxy or
hosting platform before starting the app.

```bash
git clone https://github.com/Nomos69/NetDrop.git
cd NetDrop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set the exact public address in `.env`:

```dotenv
NETDROP_ONLINE_URL=https://your-service.example.com
```

Then start the app behind HTTPS:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

The application rejects ordinary HTTP requests (except `/up`) and rejects
non-secure WebSockets. Open the public `https://` URL in the browser.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `NETDROP_HOST` | `0.0.0.0` | Address the server listens on |
| `NETDROP_PORT` | `8000` | Internal server port |
| `NETDROP_ONLINE_URL` | required | Public HTTPS origin used in invitations |
| `NETDROP_FILE_TTL_SECONDS` | `1800` | Uploaded-file lifetime |
| `NETDROP_MAX_UPLOAD_BYTES` | `50000000` | Maximum bytes per uploaded file |
| `NETDROP_CLEANUP_INTERVAL_SECONDS` | `5` | Expiry-cleanup interval |
| `NETDROP_ROOM_TTL_SECONDS` | `259200` | Room lifetime |
| `NETDROP_INVITATION_TTL_SECONDS` | `86400` | Email invitation-token lifetime |
| `BREVO_API_KEY` | empty | Optional Brevo API key |
| `BREVO_SENDER_EMAIL` | empty | Verified Brevo sender |
| `BREVO_SENDER_NAME` | `NetDrop` | Invitation sender name |

## Render

Create a Python Web Service and use:

| Setting | Value |
| --- | --- |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers` |
| Health check | `/up` |

Set `NETDROP_ONLINE_URL` to the exact HTTPS Render URL. Use one worker and one
service instance: rooms and sessions are in memory, and uploads are temporary.

## Security notes

Invitation links contain a room ID, never its PIN. The recipient must still
enter the PIN. PIN hashes, rooms, sessions, and upload metadata are held in
memory and reset after a service restart.
