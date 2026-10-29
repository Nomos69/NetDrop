# NetDrop project plan

Status: steps 1–8 of the implementation procedure are implemented, including live updates, reconnect resync, expiry, and cleanup. Step 9 core LAN access/sharing is confirmed by the user on a phone. Step 11 verification and documentation cover the current LAN prototype; remaining real-device observations are listed in docs/verification.md. Step 10 external alerts remain unimplemented.

## Basis and scope

Source: `NetDrop_API_Updated.pptx` (11 slides). The presentation describes proposed requirements and technology choices; it is reference material, not permission to implement every proposed feature now. The initial workspace contained no application source code; the basic server foundation is now implemented.

Goal: let people on the same LAN share temporary files, text, and links through a browser room, with live updates. Add an opt-in external alert after a successful file upload. LAN sharing must remain usable when the internet or notification provider is unavailable.

Working assumptions to confirm before the affected phase:

- One host runs NetDrop; browsers connect to that host. This is a host-based LAN application.
- Files expire 30 minutes after a successful upload. Expired files cannot be downloaded, even between cleanup runs.
- Rooms use PIN-protected access; browser sessions retain room authorization without putting PINs in URLs.
- Start with one host process, local file storage, and in-memory room state. Restart behavior must be documented.
- Prototype defaults: 100 MiB uploads of any file type as download attachments; 100 rooms; 500 active items per room. Notes and links share the configured 30-minute lifetime.
- No delivery channel, endpoint, price, quota, or delivery guarantee is assumed for Greppoo Notification Hub.

## Scope boundaries

Core prototype: rooms and access control; file upload/download; shared text and links; WebSocket updates; expiry and cleanup; simple host configuration.

Notification integration: verified provider contract; explicit recipient opt-in or authorized room configuration; backend-only credentials; one new-file event; bounded retries and attempt logs.

Later options: expiry reminders, friendly local DNS, Cloudflare Tunnel, saved settings/subscriptions/logs using SQLite, and OS-specific PyInstaller packages. Remote access requires a separate security review before exposure.

## Proposed structure

```text
NetDrop/
  app/
    main.py                 # FastAPI setup and application lifecycle
    config.py               # host configuration and limits
    rooms.py                # room state and authorization
    files.py                # upload, download, expiry, cleanup
    realtime.py             # room-scoped WebSocket updates
    notifications.py        # provider requests, retries, attempt results
  static/
    index.html
    styles.css
    app.js
  tests/
  data/uploads/             # runtime files; excluded from version control
  .env.example              # variable names and safe examples only
  .gitignore
  requirements.txt
  README.md
  PROJECT_PLAN.md
```

Use plain HTML/CSS/JavaScript with FastAPI and Uvicorn. Add HTTPX when integrating alerts. Add dnslib, SQLite, and packaging dependencies only when their phases are selected. Keep modules small; avoid extra architectural layers for the prototype.

## Phased execution

### Phase 0 — Resolve requirements and verify the provider

1. Agree on room creation/joining, host controls, upload limits, expiry behavior, and restart behavior.
2. Obtain the official Notification Hub documentation and confirm authentication, supported channels, recipient setup, request/response schema, quotas, timeouts, and retry/idempotency support.
3. Choose one supported channel and a test recipient with consent. Establish whether provider acceptance and actual delivery can be measured separately.

Completion: a short confirmed requirements list and provider contract. Missing API access blocks external alerts, but does not block the LAN phases.

### Phase 1 — Runnable foundation

Create the minimal project, configuration, static interface shell, and run instructions. Bind to an appropriate LAN interface and document the host address and port.

Completion: the page loads locally and from a second device on the same LAN. Report local and real-device results separately.

### Phase 2 — Rooms and temporary sharing

Implement room creation/joining, authorized sessions, bounded PIN attempts, file upload/download, text/link sharing, and room-scoped content lists. Store files under server-generated names outside static assets; enforce configured size limits, prevent path traversal, and render user text safely. A file becomes visible only after storage succeeds.

Completion: authorized users can share and retrieve content; wrong PINs, cross-room access, oversized uploads, unsafe filenames, and interrupted uploads are handled predictably.

### Phase 3 — Live feed and expiry

Add authorized WebSocket subscriptions, room-scoped updates, reconnect with a fresh content list, expiry checks on download, and periodic cleanup. Coordinate cleanup with active transfers so downloads do not race with deletion. On startup, remove expired/orphaned files according to the documented restart policy.

Completion: two browsers see changes without manual refresh; reconnect restores current state; expired content disappears and expired downloads are refused. Verify expiry using a shortened test lifetime as well as the configured 30-minute value.

### Phase 4 — New-file notifications

After a successful upload, create an event with a stable identifier, select opted-in/configured recipients, and queue delivery separately from the upload response. Keep secrets on the backend. Send minimal content without file contents or PINs. Use bounded HTTP timeouts, limited retries with backoff, provider rate-limit handling, and duplicate suppression. Log pending, accepted, failed, and delivered only when the provider supplies evidence for that state.

Define queue durability explicitly: an in-memory queue loses pending work on restart; use SQLite here if restart-safe retries are required. Do not promise exactly-once delivery when a timeout leaves the provider result uncertain.

Completion: one successful upload triggers the intended alert; internet failure does not break upload/download; temporary failures retry within limits; permanent failures stop; duplicate processing is suppressed; logs contain no secrets. Actual delivery requires a real provider test, separate from mocked tests.

### Phase 5 — Evaluation and handoff

Run focused automated checks for authorization, upload failure, expiry, event generation, and retry behavior. Perform browser and real-device LAN checks, plus real-provider delivery checks when credentials are available. Record observed results and remaining limitations.

Measure provider acceptance separately from confirmed delivery, notification delay, and whether consenting users notice new files sooner than with the live feed alone. Prepare setup instructions, dependency versions, host/firewall guidance, and an evidence checklist.

Completion: documented results support the claimed features; untested LAN/provider/OS behavior is clearly identified.

### Phase 6 — Optional improvements, one at a time

Choose only after the core workflow passes: expiry reminders with cancellation when content is deleted; durable settings and logs; local DNS with client/router configuration; remote access with stronger authentication and exposure controls; packaging and validation on each target OS.

## Execution order

Phase 0 requirements → Phase 1 foundation → Phase 2 sharing → Phase 3 live updates/expiry → Phase 4 alerts → Phase 5 evaluation. Provider verification can proceed alongside LAN development. Phase 6 remains optional.

Implement and verify one phase at a time. The next implementation task is provider verification and external alerts. Final notification evaluation remains dependent on that implementation; current LAN verification boundaries are recorded in docs/verification.md.

## Local / Online sharing addition

Implemented the mode selector, server routing, active mode labels, invitation
links without PINs, HTTPS enforcement for online HTTP/WebSocket connections,
and configuration/setup instructions. Each server retains independent room state;
selecting Online requires a configured, separately deployed HTTPS service.
This implementation does not deploy a hosting service. Real cross-network
verification remains separate from the local two-server browser checks.


## Sharing improvements — 2026-10-29

Implemented automatic idle-room cleanup, creator-owned close/remove/delete
controls, sequential multiple-file uploads with progress/cancel/retry, live expiry
countdowns, and private QR invitations generated on the server. Room ownership
belongs to the creating browser session; member removal permits rejoining with the
PIN. Existing downloads retain their deletion leases. Idle time defaults to 30
minutes and is configurable with `NETDROP_ROOM_IDLE_SECONDS`.

Greppoo notifications remain deferred. Physical-device and public cross-network
verification still require the device checklist in `docs/verification.md`.
