# NetDrop premium redesign — verification and handoff

Implemented in the existing vanilla frontend. FastAPI endpoints, authorization,
secure cookies, HTTPS enforcement, WebSockets, temporary storage, Brevo REST
integration, and Render configuration were not changed. No commit, push, or
production deployment was performed.

## Changes

- Dark default and persistent light theme, reusable color/spacing/interaction
  tokens, local system typography, and an original consistent SVG icon set.
- Two-column landing page with the requested hero, interactive device network,
  immediate create/join actions, native accessible PIN input and masked cells.
- Workspace navigation, upload and clipboard editors before secondary settings,
  room-ID copying, live status, member initials/presence and transitions.
- Native modal dialogs for QR/link/email invitations and optional email alerts.
  Alerts explicitly disclose that attachments leave the room.
- Drag/drop file selection, actual XHR progress, readable sizes, local raster
  image previews, transfer success/error states and retry support.
- Safe clipboard rendering and copying, URL detection, character count, and
  Ctrl/Command+Enter submission. Search, type filters and six-item pagination.
- Circular MM:SS file timers use the server expiry, turn amber near expiry,
  and retain their SVG when updated. Fixed the old updater that replaced timer
  contents and pagination buttons incorrectly re-enabled after requests.
- Reduced-motion behavior, labeled inputs, visible focus states, adequate touch
  controls, stronger primary-button contrast, and keyboard-dismissable dialogs.

## Files

- `static/index.html`: landing, workspace and dialog structure.
- `static/premium.css`: new active design system and responsive layouts.
- `static/ui.js`: local SVG icons, theme, dialogs and device illustration.
- `static/app.js`: frontend integration, filtering, upload selection and timers.
- `tests/browser_redesign.py`: reproducible local browser workflow.
- `docs/redesign-plan.md`: analysis and implementation plan.
- `docs/redesign-screenshots/`: before/after evidence.

The former `static/styles.css` remains available as a recoverable legacy asset;
the application now loads `premium.css`. Baseline commit: `4b80ab7`. Original
frontend copies also remain at `/tmp/netdrop-redesign-baseline` for this session.

## Validation

The final Chromium Playwright run passed against a local HTTPS service:

- Layouts at 360, 390, 768, 1024 and 1440 pixels, with no document overflow.
- Dark/light switching and persistence; desktop/mobile screenshots inspected.
- Real creation/joining, invalid PIN validation, invitation links and two-client
  member/content synchronization.
- Actual file upload and byte-verified download, drag/drop selection, intercepted
  upload failure followed by a successful real retry, and local image previews.
- Text/link sharing, copying, URL detection, shortcut submission and safe display
  of HTML-looking text.
- Search, filters, pagination, refresh on the last page, and owner deletion.
- Timer SVG preservation, countdown, warning and expired visual states.
- QR image loading, invitation copying, email and subscription interface results.
  Email/subscription requests were intercepted; no real email was sent.
- Escape dismissal and focus restoration, input labeling, reduced motion, room
  leave/close flows, and no JavaScript page errors.

JavaScript syntax checks and `git diff --check` also passed. No runtime packages
were added. Playwright was already installed; Chromium was downloaded for QA.
The optional headless-shell download ran out of disk space and was stopped; all
tests successfully used the full Chromium executable.

## Screenshots

| View | Before | After |
| --- | --- | --- |
| Desktop landing | [Before](redesign-screenshots/before-1440.png) | [Dark](redesign-screenshots/landing-dark-1440.png), [Light](redesign-screenshots/landing-light-1440.png) |
| Mobile landing | [Before](redesign-screenshots/before-390.png) | [After](redesign-screenshots/landing-dark-390.png) |
| Workspace | — | [Desktop](redesign-screenshots/workspace-dark-1440.png), [Mobile](redesign-screenshots/workspace-dark-390.png), [Light](redesign-screenshots/workspace-light-1440.png) |
| Dialogs | — | [Invitations](redesign-screenshots/invitation-dialog.png), [Email alerts](redesign-screenshots/alerts-dialog.png) |

## Preview and deployment

Use the existing local TLS certificate or create a temporary certificate, then:

```bash
NETDROP_ONLINE_URL=https://localhost:8443 \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8443 \
  --ssl-keyfile /tmp/netdrop-key.pem --ssl-certfile /tmp/netdrop-cert.pem
```

Open `https://localhost:8443`. The temporary certificate produces a browser
warning. The QA script uses port 18443 by default; override `NETDROP_TEST_URL`
to test another local HTTPS port. Run it only against disposable local rooms.

No database migrations or new production dependencies are needed. Include the
new `premium.css` and `ui.js` assets in the eventual deploy. Existing Render
single-worker and public HTTPS-origin requirements still apply.

## Limits

- Chromium desktop emulation was verified; real phones, Safari/Firefox,
  cross-network deployment, delivery through Brevo, and a formal WCAG audit were
  not tested. No production-ready certification is implied by local checks.
- Image previews intentionally cover locally selected raster files. Automatically
  fetching shared files for thumbnails would trigger backend download alerts.
- Local measurements are not a production performance benchmark; no Lighthouse
  score was collected. There are no new frontend framework or CDN dependencies.
- Native browser confirmations remain for destructive operations and leaving a
  room. The device visualization is illustrative, not hardware discovery.
