"""NetDrop server. Run from the project folder with python -m app.main."""

import asyncio
from contextlib import asynccontextmanager, suppress

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
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
app.include_router(rooms.router)
app.include_router(files.router)
app.include_router(realtime.router)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


@app.api_route("/up", methods=["GET", "HEAD"], include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host=config.HOST, port=config.PORT)
