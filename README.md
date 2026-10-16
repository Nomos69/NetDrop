# NetDrop

Browser-based LAN sharing with temporary files, text, links, and planned external notifications.

## Current status

Project scaffold only. Backend modules are placeholders; the server, sharing, room access, cleanup, and notifications are not implemented yet. No dependencies are required for this scaffold.

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for scope, assumptions, phases, and completion checks.

## Layout

- `app/`: Python backend modules.
- `static/`: browser HTML, CSS, and JavaScript.
- `tests/`: future automated checks.
- `data/uploads/`: temporary runtime uploads, excluded from version control.
- `.env.example`: proposed host settings; loading is not implemented yet.
- `requirements.txt`: dependencies will be added as needed.

Next phase: implement the runnable FastAPI foundation and document setup commands.
