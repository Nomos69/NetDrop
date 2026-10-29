# NetDrop

Browser-based LAN sharing with temporary files, text, links, and planned external notifications.

## Current status

Steps 1–8 are implemented: server configuration, interface, PIN-protected rooms, file/text/link sharing, live updates with reconnection, and automatic expiry/cleanup. Step 9: the user confirmed phone access, room joining, automatic file appearance, and downloading over the LAN. Step 11: verification and documentation cover the current LAN prototype. Step 10 external notifications remain planned; their tests must be added when implemented.

## Setup and run (Linux)

From the NetDrop project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main
```

Open http://127.0.0.1:8000 on the host. Stop the server with Ctrl+C.
On another device on the same LAN, use `http://<host-LAN-IP>:8000`. Find the host address using `hostname -I`. The host firewall must permit the configured TCP port. Phone access and file sharing were confirmed by the user; see [verification results](docs/verification.md) for the exact scope.

## Online uptime monitoring

The public `/up` endpoint accepts GET and HEAD requests and returns HTTP 200 while
the server is responding. GET returns `{"status":"ok"}`; HEAD returns headers
without a response body. It does not create a room or browser session.

After deploying the endpoint to Render:

1. Open UptimeRobot and choose **Add New Monitor**.
2. Select **HTTP(s)** and name it **NetDrop**.
3. Enter `https://YOUR-SERVICE.onrender.com/up` as the URL.
4. Set the monitoring interval to **5 minutes** and select your alert contact.
5. Create the monitor and wait for its status to show **Up**.

No UptimeRobot API key or Python package is needed in NetDrop. The monitor
runs externally, so the host computer can be off. Regular requests can help
avoid Render Free's idle sleep, but cannot guarantee uptime or prevent restarts.
Rooms still reset on server restart, and free-host local uploads are temporary.
This endpoint checks HTTP responsiveness; it does not test file sharing or WebSockets.

## Configuration

Defaults work without a `.env` file. To customize them, copy `.env.example` to `.env` and edit it. Restart the server after changes. Existing environment variables take precedence over `.env` values.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NETDROP_HOST` | `0.0.0.0` | Listen on all host network interfaces |
| `NETDROP_PORT` | `8000` | HTTP port, from 1 to 65535 |
| `NETDROP_FILE_TTL_SECONDS` | `1800` | Lifetime of files, text, and links in seconds |
| `NETDROP_MAX_UPLOAD_MB` | `100` | Upload limit in MiB |
| `NETDROP_CLEANUP_INTERVAL_SECONDS` | `5` | Seconds between cleanup scans |

The upload size limit is enforced while receiving each file. A file's lifetime begins after it is fully saved. Notes and links use the same lifetime from creation. New downloads are rejected at the expiry deadline, even between cleanup scans. Active downloads may finish; deletion waits until their response completes or disconnects. Expired content disappears from lists and live feeds on the next scan (normally within five seconds). The server creates `data/uploads/` on startup. Paths resolve relative to the project, and uploads are outside the public static directory.

## Layout

- `app/config.py`: configuration loading and validation.
- `app/main.py`: server, homepage, and static assets.
- `app/rooms.py`: room creation, PIN checks, and cookie-based membership.
- `app/files.py`: authorized file uploads/downloads and text/link sharing.
- `app/realtime.py`: authorized room WebSockets and live update signals.
- `app/notifications.py`: placeholder for external alerts.
- `static/`: browser HTML, CSS, and JavaScript.
- `tests/`: API, expiry, and browser checks.
- `data/uploads/`: temporary runtime uploads, excluded from version control.

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full plan. Next: verify the notification provider before step 10. The LAN test record is in [docs/verification.md](docs/verification.md).

## Using rooms

Enter an optional display name when creating or joining a room. Blank names get
a generated guest name. The **Room members** list shows joined browser sessions,
marks your own entry with **You**, and updates automatically on joins and leaves.
Green **Online** means at least one tab for that browser has a live connection;
multiple tabs count as one member. Disconnections can take a moment to detect.
Closing all tabs marks the member offline; **Leave room** removes the entry.
Expired sessions disappear as the roster refreshes. Names are self-selected,
not verified identities, and only room members can view the list.

1. Create a room with a name and a 6–12 digit PIN.
2. Share the displayed 12-character room ID and PIN with intended participants. Use the code shown inside the room, not its name. The join form tolerates spaces and uppercase letters in copied IDs.
3. On another browser/device, enter that ID and PIN to join.
4. Upload a file, write text, or share an HTTP/HTTPS link.
5. Other participants see additions automatically and click a filename to download. Refresh remains available as a fallback. Live updates reconnect automatically and fetch the latest content after a connection interruption.
6. Leave room removes that browser session's membership in the room.

Room names and content are displayed as plain text. Files download as attachments, with server-generated storage names. Each room is limited to 500 items; the host supports up to 100 rooms and 1,000 active browser sessions. Join attempts are limited to five per minute per client IP, including successful attempts. Multiple users behind the same proxy share that limit. PINs are salted and hashed in memory.

Browser sessions last 12 hours. Use a single server process: rooms, membership, and content indexes are in memory and reset on restart. After restart, old uploads are no longer listed or downloadable because room indexes reset. Startup and periodic cleanup remove generated upload filenames once their last-modified age exceeds the configured lifetime. Fresh orphaned uploads wait until that deadline; unrelated files and `.gitkeep` are preserved. Failed deletions are logged and retried. Local HTTP does not encrypt traffic; use this prototype on a trusted LAN.

## Automated checks

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Tests use temporary storage and cover sharing/access isolation, WebSocket authorization and revocation, expiry boundaries, background cleanup, orphan cleanup, deletion retries, and downloads crossing the expiry deadline.

For the two-browser check (uses temporary storage and port 18765):

```bash
python -m playwright install chromium --no-shell
python tests/browser_live.py
```

It checks room/PIN validation, pasted-input normalization, uploads/downloads in both directions, automatic updates, offline reconnection with missed content, expiry with an eight-second lifetime, mobile layout, and restart recovery. The normal server keeps its 30-minute default. Real-device LAN testing remains separate.

## Step 9: real-device LAN checklist

1. Run the server on the host and keep its terminal open.
2. Connect the second device to the same Wi-Fi/LAN, then open `http://<host-Wi-Fi-IP>:8000` (not `127.0.0.1`).
3. Create a room on the host and join it from the second device using its ID and PIN.
4. Upload a small file on each device. Verify the other device sees it automatically and can download the correct contents.
5. Share a note and link; verify both appear automatically.
6. Temporarily disconnect the second device's Wi-Fi, share another note on the host, then reconnect. Verify the missed note appears.
7. Check that an expired file disappears and its previous download URL no longer works. The automated browser test covers this using eight seconds; normal rooms use 30 minutes.

If the second device cannot connect, check host firewall rules for the configured TCP port and router client isolation. No firewall rules are changed automatically. See `docs/verification.md` for the exact verification boundary.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Page fails on the host | Run `python -m app.main` from the activated environment and leave the terminal open. Use the configured port. |
| Page works on the host but fails on the phone | Use the computer's Wi-Fi IP, connect both devices to the same LAN, and check firewall/router client isolation. `127.0.0.1` on the phone points to the phone itself. |
| Room ID format error | Enter the 12-character code shown inside the host's room, using digits and a–f. Refresh the phone page to load the latest form. |
| PIN format error | Use 6–12 digits; keep leading zeros. |
| Room ID or PIN is incorrect | Check the code and PIN. A host restart clears rooms, so create a new room afterward. |
| Too many join attempts | Wait one minute before retrying; the limit applies per client IP. |
| Live updates reconnecting | Check Wi-Fi, keep the host running, and use Refresh as a fallback. Returning to the page reconnects and fetches current content. |
| File no longer downloads | It may have expired after 30 minutes or become unavailable after a host restart. Share it again if needed. |

For this host's observed `192.168.1.0/24` LAN, the following narrow Ubuntu firewall rule permits access to the default port:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8000 proto tcp
```

Run it on the host, entering the administrator password locally. Adjust the subnet and port if your network or configuration differs. Do not disable the whole firewall. The Wi-Fi address can change after reconnecting; check `hostname -I` when needed.

## Remaining work

External notifications (step 10) require verified provider documentation, a supported delivery channel, credentials, and consenting test recipients. Notification delivery/failure/retry testing is not included in the current LAN test results. Real-phone reconnection and a full wall-clock 30-minute expiry observation are not yet confirmed; these behaviors have automated coverage using a shortened lifetime and exact deadline checks.

## Local and Online sharing

Use the **Local Network / Online** tabs before creating or joining a room:

- **Local** uses the host on the same Wi-Fi/LAN and works without internet.
- **Online** opens the configured public HTTPS server for people on different networks.

Each server owns its rooms, sessions, and uploads. Switching servers does not copy
files or rooms. Both modes keep the room PIN, upload limits, authorization, live
updates, and expiry. The room screen shows its mode and a copyable invitation link.
Opening an invitation fills the room ID; the recipient must still enter the PIN.
Clipboard access may be unavailable over LAN HTTP; select and copy the displayed
link manually in that case.

### Configure the local host

Add to the local `.env`, replacing the addresses with your own:

```dotenv
NETDROP_SHARING_MODE=local
NETDROP_LOCAL_URL=http://192.168.1.12:8000
NETDROP_ONLINE_URL=https://YOUR-SERVICE.onrender.com
```

Run with `python -m app.main`. Keep the LAN address current if it changes.
`NETDROP_ONLINE_URL` pre-fills the Online connection field. If it is empty,
participants can paste a complete HTTPS server address or invitation link.
Click **Connect to online server**, then enter the room PIN on that server. If the local URL is empty,
links use the current browser address; a localhost address only works on the host.
The mode tabs route to servers; it does not restrict the host's network
exposure. Keep the local server accessible only within the trusted LAN.

### Configure an online server

Deploy this repository as a Python web service with one worker:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers`
- Health check path: `/up`
- Environment: `NETDROP_SHARING_MODE=online` and
  `NETDROP_ONLINE_URL=https://YOUR-SERVICE.onrender.com`.
- Configure Uvicorn's `FORWARDED_ALLOW_IPS` to trust the hosting reverse proxy so
  HTTPS and secure WebSocket requests retain their external scheme. On a service
  whose backend is reachable exclusively through its trusted proxy, `*` can be
  used; do not use that setting for a directly exposed backend.
- Optionally set `NETDROP_LOCAL_URL` so participants can open your LAN host when
  they are on that LAN. Otherwise participants can enter a local host address manually.

The online server rejects non-HTTPS application requests and non-secure WebSockets;
`/up` remains available for internal health checks. The hosting service supplies
HTTPS. Setting the public URL alone does not deploy a server or establish public
connectivity. Do not expose a local development server by forwarding a router port.

Use a single process: rooms and content indexes still reset on restart. Uploads
require writable disk and remain temporary; this change adds no durable database,
object storage, or automatic replication. An online deployment must be tested on
separate networks before claiming real-world online sharing is verified.

To check both modes locally using temporary storage and a test TLS certificate:

```bash
python tests/browser_modes.py
```

### Connection screen troubleshooting

The compact connection card uses Local Network / Online tabs and Join / Create
room actions. PINs remain 6–12 digits and room IDs remain 12 characters. The UI
uses versioned assets, and the homepage is served without caching to avoid mixing
old scripts with a new screen. Settings requests time out after ten seconds; a
failed or missing `/api/sharing` endpoint leaves the tabs and invite-link field
usable, with a visible retry action. Restart an older server after updating code.

Public HTTPS hosts automatically identify as Online and use their current origin
when no online URL was configured. Local/private hosts retain Local mode unless
explicitly configured otherwise. Behind a reverse proxy, preserve the HTTPS scheme
using the trusted proxy configuration described above.

The current checkout's ignored `.env` points Online to
`https://netdrop-r51l.onrender.com`. This is local configuration; changing the
source here does not update the deployed Render service. Deploy the updated
repository to show this screen on that public service.

## Room ownership and invitations

The browser session that creates a room owns it. Only that owner can close the
room, remove another member, or delete any shared file, note, or link. These
checks run on the server. Leaving does not close a room; rejoining from the same
unexpired browser session restores the owner's controls. Ownership cannot be
recovered from the PIN alone after the creator's session expires.

Removing a member immediately revokes that browser session's access and live
connection. It is not a permanent ban: someone with the PIN can rejoin. Closing a
room revokes everyone's access and deletes its content. Already-running downloads
may finish; their files are removed afterward. A cancelled upload might already
have reached the server, so inspect the feed before retrying or delete the item as
the owner.

Open **Show invitation QR code** inside a room to display a locally generated QR
code. It contains the same invitation URL as the copy button, never the PIN.
Scanning opens the join form; the recipient still enters the PIN. Local QR codes
require the same LAN and a reachable host address. Configure `NETDROP_LOCAL_URL`
if the host uses localhost; a localhost QR code will not connect a phone.

## Upload queue and expiry countdowns

Choose multiple files, then click **Upload files**. Files upload one at a time,
with a progress bar and a separate result for each file. **Cancel** stops a queued
or active upload; **Retry** resubmits a cancelled or failed upload. A failed file
does not stop later files. Oversized files are rejected individually. Progress
reaching 100% means the browser sent the bytes; **Shared** confirms the server
saved the file. Network failures can leave the outcome uncertain: check the feed
before retrying to avoid duplicates.

Leaving or losing room access cancels the browser's upload queue. The queue is
kept only in the current page and is not resumed after a reload. Each shared item
shows a countdown; it uses the device clock, while server time remains the source
of truth for expiry. Expired entries disappear on the next cleanup update.

## Idle-room cleanup

`NETDROP_ROOM_IDLE_SECONDS` defaults to `1800` (30 minutes). A room is eligible
for cleanup after that period without an authorized request, live browser
connection, or file transfer. The idle timer restarts when the last live tab
disconnects or a download ends. Closing a tab does not immediately close its room.
Cleanup revokes old memberships and removes the room's content, freeing room
capacity. Active uploads and downloads prevent automatic room retirement.

Additional isolated checks:

```bash
python tests/browser_controls.py
```

This uses temporary storage and port 18768 to check owner controls, upload batches,
progress, cancellation, retry, expiry countdowns, QR display, and mobile layout.
