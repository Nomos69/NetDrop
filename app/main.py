"""NetDrop server. Run from the project folder with python -m app.main."""

import asyncio
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config, files, realtime, rooms


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    files.cleanup_once()
    cleanup = asyncio.create_task(files.cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(title="NetDrop", lifespan=lifespan)


class OnlineHTTPS:
    """Check transport without wrapping or buffering streaming uploads."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and config.SHARING_MODE == "online"
                and scope["scheme"] != "https" and scope["path"] != "/up"):
            response = JSONResponse({"detail": "Online sharing requires HTTPS."}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


app.add_middleware(OnlineHTTPS)


@app.get("/api/sharing")
async def sharing(request: Request):
    mode = config.sharing_mode(request)
    return {"mode": mode, "local_url": config.LOCAL_URL,
            "online_url": config.ONLINE_URL or (str(request.base_url).rstrip("/") if mode == "online" else "")}


app.include_router(rooms.router)
app.include_router(files.router)
app.include_router(realtime.router)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.api_route("/up", methods=["GET", "HEAD"], include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(config.STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
