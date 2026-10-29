# NetDrop verification — 2026-10-16

## Current outcome

The LAN prototype is working. The user confirmed that the phone can open NetDrop, join a room, see shared files appear, and download them. The final automated run passed 19 API tests and the two-browser workflow. Step 11 testing and documentation are complete for the currently implemented LAN features; final notification evaluation depends on implementing step 10.

## Results and evidence boundaries

| Check | Automated result | Real-phone result |
| --- | --- | --- |
| Homepage access and room joining | Passed | User confirmed |
| Room ID/PIN validation and copied-input normalization | Passed in mobile-width Chromium | User confirmed joining works after fix |
| Shared file appears automatically and downloads | Passed | User confirmed: “yes it shows actually and i can dl it” |
| Upload/download in both directions with byte checks | Passed in two browser contexts | Both directions not separately confirmed |
| Notes and links appear automatically | Passed | Not separately confirmed |
| Offline reconnect recovers missed content | Passed | Not separately confirmed |
| Expiry removes content and blocks old downloads | Passed with eight-second browser lifetime and exact API deadline checks | Full 30-minute observation not confirmed |
| Cleanup waits for active downloads and releases disconnected transfers | Passed | Not separately tested |
| Cross-room access denial and PIN attempt limit | Passed | Not separately tested |
| Host restart resets rooms and UI recovers | Passed | Not separately tested |

The automated browsers run on one host. They do not independently prove cross-device Wi-Fi behavior. The real-phone results above are user-reported rather than independently observed by the agent.

## Reproducible automated checks

From the project folder, after installing `requirements-dev.txt`:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m playwright install chromium --no-shell
python tests/browser_live.py
```

Saved output from the final run:

- [API test output](api-test-results.txt): 19 tests passed.
- [Browser test output](browser-test-results.txt): workflow passed.

Tests use temporary upload storage. The browser test uses its own server on port 18765, an eight-second lifetime, and a one-second cleanup interval. The normal server on port 8000 and its rooms are not restarted or modified by these checks.

Coverage includes access isolation, unsafe filenames, oversized/interrupted uploads, text/link validation, WebSocket origin/membership checks, live access revocation, exact expiry boundaries, background cleanup, orphan filtering, deletion retries, active download coordination, mobile-width layout, pasted-input handling, and reconnect/restart recovery.

The API runner emits a Starlette deprecation warning for its HTTPX test client; it does not fail the tests. Python compilation, JavaScript syntax, dependency consistency, and whitespace checks also passed.

## Host network findings and resolved issues

- Observed Wi-Fi interface: `wlp2s0`, address `192.168.1.12/24`.
- Server listens on `0.0.0.0:8000`; the host's Wi-Fi URL returned HTTP 200.
- Initially the phone could not reach the page. `/etc/ufw/ufw.conf` had `ENABLED=yes`; active rules could not be read without the user's administrator password.
- A rule allowing TCP 8000 from `192.168.1.0/24` was suggested. The user subsequently confirmed phone access. The exact applied firewall rule was not independently inspected.
- Room entry initially showed a generic browser format error. The form now normalizes copied whitespace/case before validation, explains the 12-character room ID, and gives a specific 6–12 digit PIN message. The user confirmed joining afterward.

The address may change when the host reconnects to Wi-Fi. Use the current Wi-Fi address rather than assuming this snapshot always applies.

## Remaining evaluation

Physical-phone reconnect, transfers explicitly confirmed in both directions, notes/links, and a full wall-clock 30-minute expiry observation remain optional follow-up evidence for the LAN prototype. Do not describe those as completed physical-device tests.

External notification delivery, provider failure handling, retries, and user-notice-time evaluation remain untested because step 10 is not implemented. The current results do not establish production readiness, internet-exposed security, performance under load, or support on other operating systems.

## Local / Online mode verification — 2026-10-29

- API suite: 26 tests passed, including mode discovery, secure online session
  cookies, PIN-authorized online upload/download, WSS updates, rejection of
  plaintext online requests, and server URL validation.
- `tests/browser_modes.py`: passed against two independent loopback servers,
  using HTTP for Local and a temporary self-signed TLS certificate for Online.
  Verified invitation prefill without automatic authorization, PIN-free links,
  clipboard fallback, uploaded/downloaded file bytes in both modes, live updates,
  navigation between configured servers, missing-server explanation, disabled
  submission in an unavailable mode, and mobile layout without horizontal overflow.
- Existing `tests/browser_live.py`: passed, including bidirectional file transfers,
  membership, live updates, reconnect/resync, expiry, and restart recovery.
- Desktop lobby and mobile room screenshots were visually inspected. JavaScript
  syntax and Git whitespace checks passed.

Browser tests use temporary storage and ports 18765–18767. They do not deploy or
contact a public NetDrop service. No new physical-device or public cross-network
result is claimed. The online instance still needs public HTTPS hosting and a
separate Wi-Fi/mobile-data verification. Rooms and indexes remain in memory.

## Connection screen repair — 2026-10-29

Replaced the settings-dependent dropdown with always-available Local Network /
Online buttons and a compact monochrome connection card based on the supplied
reference. Join/Create actions preserve existing room creation, membership, and
6–12 digit PIN behavior. Online accepts an HTTPS host address or invitation link;
Local accepts a LAN host address. Neither forwards a PIN in a URL.

The previous implementation disabled the selector until `/api/sharing` completed
and had no request timeout. Settings now time out after ten seconds and failure
leaves mode navigation usable, with a retry button. Versioned assets and a no-store
homepage reduce stale HTML/script combinations. The exact cause of the user's
original loading screenshot was not independently reproduced on their browser.

A live read of `https://netdrop-r51l.onrender.com/api/sharing` returned HTTP 200
with Local mode and empty local/online addresses before these changes. The ignored
local `.env` now pre-fills that known online address. No public deployment was
performed. Public HTTPS deployments of this updated code detect Online mode and
infer their public origin when optional URL configuration is absent.

Verification: 27 API tests passed; existing live-sharing browser checks passed;
mode browser checks passed for Local/HTTPS Online file transfer, invitations,
manual host routing, invalid HTTP rejection for Online, settings 404, fetch failure,
and timeout recovery. Desktop and mobile screenshots were visually inspected.
These automated checks use isolated local servers, not separate physical networks.
