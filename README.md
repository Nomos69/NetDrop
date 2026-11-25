<div align="center">
  <img src="static/logo.svg" width="88" alt="NetDrop logo">
  <h1>NetDrop</h1>
  <p><strong>Temporary online and local-network file and clipboard sharing.</strong></p>
</div>

## About

NetDrop offers two ways to share. Online rooms use a public HTTPS service and
work across networks. Local rooms run on a Windows host and share over the same
Wi-Fi or LAN without sending room content through the online service.

## Features

- PIN-protected temporary rooms
- File, text, and link sharing
- Live member and content updates over secure WebSockets
- Copyable invitation links and SVG QR invitations
- Owner controls, automatic expiry, and optional Brevo email invitations
- Optional Windows local companion for LAN hosting and host discovery

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

Online mode rejects ordinary HTTP requests (except `/up`) and non-secure
WebSockets. Open the public `https://` URL in the browser.

## Local sharing

On the online NetDrop page, choose **Local Sharing** to download the Windows
companion. Install it, choose **Host a local room**, then use the updated
NetDrop room interface to create a room. Participants must be on the same
Wi-Fi or LAN and can join with the room ID and PIN. If automatic host discovery
is unavailable, open the host's LAN address directly.

The companion sets local mode for its own server process; users do not need to
edit `.env` or run Python. The local server stores temporary uploads under the
user's NetDrop data directory. Local sharing uses HTTP on the LAN, so use a
trusted private network.

To build the Windows installer locally, install Python 3.12+ and Inno Setup 6,
then run this from PowerShell:

```powershell
.\packaging\build-windows.ps1
```

The generated installer is `dist\installer\NetDrop-Local-Setup.exe`. Publishing
a GitHub Release builds the installer and attaches that exact asset; the
website's download link works after the release workflow succeeds. A manually
dispatched workflow also makes the installer available as a downloadable
workflow artifact.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `NETDROP_HOST` | `0.0.0.0` | Address the server listens on |
| `NETDROP_PORT` | `8000` | Internal server port |
| `NETDROP_SHARING_MODE` | `online` | `online` or `local`; the companion sets `local` |
| `NETDROP_ONLINE_URL` | required in online mode | Public HTTPS origin used in invitations |
| `NETDROP_LOCAL_URL` | request origin | Optional HTTP(S) LAN origin used in local invitations |
| `NETDROP_LOCAL_DISCOVERY` | `1` | Enable local mDNS discovery |
| `NETDROP_LAN_HOSTNAME` | system hostname | Optional single-label mDNS name |
| `NETDROP_LOCAL_INSTALLER_URL` | latest Windows release asset | HTTPS download URL shown in Local Sharing |
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
Set `NETDROP_SHARING_MODE=online` for the public service.

## Security notes

Invitation links contain a room ID, never its PIN. The recipient must still
enter the PIN. PIN hashes, rooms, sessions, and upload metadata are held in
memory and reset after a service restart.
