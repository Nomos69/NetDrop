# NetDrop redesign plan

Baseline: commit `4b80ab7`; original frontend copies and before screenshots in
`/tmp/netdrop-redesign-baseline`. No backend changes or deployment are planned.

1. Inspect FastAPI routes, secure WebSockets, cookie authorization, Brevo REST
   notifications, and vanilla frontend. Preserve all contracts.
2. Capture the existing landing page on desktop/mobile using a local TLS server.
3. Replace the visual system with dark/light tokens, consistent SVG icons,
   a device-network hero, and a compact accessible room-entry panel.
4. Prioritize uploads and clipboard in the workspace; use sidebar navigation
   and native dialogs for invitations and notifications. Add search, filters,
   drag/drop, readable file sizes, clipboard shortcuts, and retain expiry rings.
5. Exercise real room creation/joining, multi-client updates, uploads/downloads,
   clipboard, pagination, owner actions, dialogs, themes, and responsive layouts
   at 360, 390, 768, 1024, and 1440 pixels. Never send real emails during tests.
6. Inspect screenshots and fix observed issues. Record evidence and limitations.

Architecture: FastAPI/Uvicorn; HTML/CSS/JavaScript; in-memory rooms and sessions;
temporary filesystem uploads; secure WebSockets; server-generated SVG QR codes;
Brevo HTTPS REST API. There is no persistent database or SMTP client.

Initial issues: settings dominate the workspace; repeated card treatments dilute
hierarchy; symbols vary by platform; pagination buttons are re-enabled after
requests; the generic expiry updater replaces the circular timer's child nodes;
the timer's live region can announce every second. Correct these during redesign.
