# NetDrop — creative minimalism refinement

Implemented in the existing vanilla frontend. No backend, API, hosting, security, or email-provider changes; no new dependencies, commit, push, or deployment.

## Before and after

| View | Before | After |
| --- | --- | --- |
| Light landing | [Before](motion-screenshots/before/landing-light-1440.png) | [After](motion-screenshots/after/landing-light-1440.png) |
| Dark workspace | [Before](motion-screenshots/before/workspace-dark-1440.png) | [After](motion-screenshots/after/workspace-dark-1440.png) |
| Mobile landing | [Before](motion-screenshots/before/landing-dark-390.png) | [After](motion-screenshots/after/landing-dark-390.png) |
| Mobile workspace | [Before](motion-screenshots/before/workspace-dark-390.png) | [After](motion-screenshots/after/workspace-dark-390.png) |
| Invitations | [Before](motion-screenshots/before/invitation-dialog.png) | [After](motion-screenshots/after/invitation-dialog.png) |
| Email alerts | [Before](motion-screenshots/before/alerts-mobile.png) | [After](motion-screenshots/after/alerts-mobile.png) |

Additional final captures: [Create room](motion-screenshots/after/create-room.png), [Join room](motion-screenshots/after/join-room.png). All images are actual Chromium screenshots, not mockups. Screenshots freeze motion; run the app to evaluate transitions.

## Three refinement passes

1. Introduced warm neutral/charcoal palettes with blue and lime, editorial headings, flat workspace dividers, tighter radii, dotted SVG device illustration and moving file packets. Inspected desktop landing, mobile landing, workspace, and invitation screenshots. Found excessive mobile illustration height and a browser test acting before animated dialog dismissal completed.
2. Reduced mobile illustration height, tightened list spacing, stabilized static packet positions, added copy checkmarks and distinguished content icons. Inspected create/join, mobile workspace and alerts. Full two-client browser workflow passed after waiting for the modal to finish closing before interacting with the underlying search field.
3. Added an original transfer brand mark, quieter completed-upload bars, readable file metadata, palette-aware focus outlines, and protection against an older toast clearing a newer message. Inspected final desktop light landing, dark workspace and 360px landing. Final functional suite passed, including live packet movement, reduced-motion behavior and copy confirmation. The motion assertion explicitly accommodates the intentional pause at each device.

Intermediate evidence is saved in `motion-screenshots/pass1` and `motion-screenshots/pass2`; final evidence in `motion-screenshots/after`.

## Interaction and implementation

- Reusable palette/motion tokens in `static/motion.css`; local/system font fallbacks, with no remote font requests. Space Grotesk is a preferred installed heading font, not a bundled dependency.
- Staggered entry, sliding active-tab underline, form entrance, hover/press feedback, drag highlighting, genuine upload progress, drawn completion checkmarks, incoming content/member transitions, copy confirmations, toast and native-dialog animations, theme transitions.
- Reduced-motion preferences disable CSS and Web Animations effects. Native PIN fields, labels, focus outlines and modal keyboard behavior remain intact.
- Existing circular countdowns use the server's actual file expiry timestamps (30-minute default), not an invented client lifetime. Existing filtering, pagination, upload retry/cancel, WebSockets, QR, and owner controls remain.
- Brevo remains the existing HTTPS REST integration; email UI tests intercept delivery and do not prove inbox arrival.

## Verification

`tests/browser_redesign.py` passed for two isolated browser sessions over local HTTPS: create/join and PIN validation, live synchronization, notes/links, clipboard, upload/download bytes, retry, drag/drop, previews, circular timers, search/filter/pagination, QR, mocked email preferences/invitations, deletion, leave/close, theme persistence, labels, motion preferences, and no page errors or horizontal overflow at 360/390/768/1024/1440px.

JavaScript syntax checks and `git diff --check` passed.

API suite: **28 passed; 3 failures and 5 errors**, reproduced identically against a clean archive of the unchanged HEAD with the required HTTPS origin configured. These are existing WebSocket test-client errors (5), attachment notification expectation (1), failed-expiry-delete retry expectation (1), and legacy HTTP/LAN QR expectation (1). They were not changed as part of this frontend request. The initial sandbox API run stalled; the completed runs were outside the sandbox.

Not verified: physical devices, Safari/Firefox, production performance, live Brevo delivery, or a formal accessibility audit.

## Preview locally

The existing HTTPS preview on **https://localhost:8443** serves the updated static files. Hard-refresh if it was already open. Its temporary local certificate may produce a browser warning; this is local testing only.

To restart a preview with the existing local certificate:

```bash
cd /home/rhimar-clifford-capunong/NetDrop
NETDROP_ONLINE_URL=https://localhost:8443 .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8443 --ssl-keyfile /tmp/netdrop-key.pem --ssl-certfile /tmp/netdrop-cert.pem
```

Do not start a second server if that port is already in use. Use two tabs to try creating and joining a room. Localhost invitations work only on this computer; this does not reintroduce LAN/Local transfer mode.
