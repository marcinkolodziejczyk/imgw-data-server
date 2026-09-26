import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, downloader
from .store import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

state: dict = {"last_sync": None}


async def run_sync() -> None:
    new_files = await asyncio.to_thread(downloader.sync)
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    if new_files:
        await asyncio.to_thread(store.load)


async def sync_loop() -> None:
    if not config.SYNC_ON_STARTUP:
        await asyncio.sleep(config.SYNC_INTERVAL_HOURS * 3600)
    while True:
        try:
            await run_sync()
        except Exception:
            log.exception("Synchronizacja nie powiodła się")
        await asyncio.sleep(config.SYNC_INTERVAL_HOURS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    downloader.convert_legacy_files()
    store.load()
    task = asyncio.create_task(sync_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="IMGW – dobowe dane klimatyczne", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/stations")
def get_stations() -> list[dict]:
    return store.stations()


@app.get("/api/data")
def get_data(
    station: str = Query(..., description="Kod stacji, np. 254220090"),
    month: int | None = Query(None, ge=1, le=12),
    day: int | None = Query(None, ge=1, le=31),
    year: int | None = Query(None, ge=1900, description="Opcjonalnie, gdy na dysku jest więcej niż jeden rok"),
) -> list[dict]:
    if day is not None and month is None:
        raise HTTPException(400, "Parametr 'day' wymaga podania 'month'")
    if not store.has_station(station):
        raise HTTPException(404, f"Nieznana stacja: {station}")
    return store.query(station, year=year, month=month, day=day)


@app.get("/api/status")
def get_status() -> dict:
    return {"last_sync": state["last_sync"], "files": store.files()}
