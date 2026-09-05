from __future__ import annotations

import secrets
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse

from .config import Settings, load_settings
from .driver import MyQDriver


settings: Settings = load_settings()
driver = MyQDriver(settings)
app = FastAPI(title="myQ software bridge", version="0.1.0")


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


Auth = Depends(require_api_key)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status", dependencies=[Auth])
def status() -> dict:
    try:
        return driver.status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/app/launch", dependencies=[Auth])
def launch() -> dict[str, bool]:
    try:
        driver.launch()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/debug/tree", response_class=PlainTextResponse, dependencies=[Auth])
def debug_tree() -> str:
    try:
        driver.launch()
        return driver.hierarchy()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/debug/nodes", dependencies=[Auth])
def debug_nodes() -> dict:
    try:
        driver.launch()
        xml = driver.hierarchy()
        return {"nodes": driver.visible_nodes(xml)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/doors/{door_name}/open", dependencies=[Auth])
def open_door(door_name: str) -> dict:
    return _command(door_name, "open")


@app.post("/doors/{door_name}/close", dependencies=[Auth])
def close_door(door_name: str) -> dict:
    return _command(door_name, "closed")


@app.post("/doors/{door_name}/toggle", dependencies=[Auth])
def toggle_door(door_name: str) -> dict:
    return _command(door_name, "toggle")


def _command(door_name: str, target: str) -> dict:
    try:
        return driver.command(door_name, target)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def main() -> None:
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
