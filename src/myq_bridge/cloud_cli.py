from __future__ import annotations

import argparse
import json
import os
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException

from .cloud import (
    MyQAuthError,
    MyQCloudClient,
    MyQCloudError,
    SessionStore,
    load_cloud_session,
)


def _store() -> SessionStore:
    return SessionStore(os.environ.get("MYQ_CLOUD_SESSION", "config/cloud_session.json"))


def _client() -> MyQCloudClient:
    store = _store()
    return MyQCloudClient(load_cloud_session(store), on_session_updated=store.save)


def _dump(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def select_door(
    doors: list[dict[str, Any]],
    *,
    door_id: str | None = None,
    door_name: str | None = None,
) -> dict[str, Any]:
    """Select the configured garage door without leaking MyQ IDs upstream.

    Selection order is explicit id, explicit case-insensitive name, then the only
    discovered door. Multiple unconfigured doors are deliberately ambiguous.
    """
    if door_id:
        matches = [door for door in doors if str(door.get("door_opener_id") or "") == door_id]
        if len(matches) == 1:
            return matches[0]
        raise ValueError("Configured MYQ_DOOR_ID did not match exactly one garage door")

    if door_name:
        wanted = door_name.strip().casefold()
        matches = [
            door
            for door in doors
            if str(door.get("name") or "").strip().casefold() == wanted
        ]
        if len(matches) == 1:
            return matches[0]
        raise ValueError("Configured MYQ_DOOR_NAME did not match exactly one garage door")

    if len(doors) == 1:
        return doors[0]
    if not doors:
        raise ValueError("No garage doors were discovered for this MyQ account")
    raise ValueError(
        "Multiple garage doors discovered; set MYQ_DOOR_ID or MYQ_DOOR_NAME"
    )


def create_app(api_key: str) -> FastAPI:
    if len(api_key) < 16:
        raise RuntimeError("MYQ_API_KEY must be at least 16 characters")

    app = FastAPI(title="myQ direct cloud bridge", version="0.2.0")
    client = _client()

    def auth(x_api_key: str | None = Header(default=None)) -> None:
        import secrets

        if not x_api_key or not secrets.compare_digest(api_key, x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

    protected = Depends(auth)

    @app.on_event("shutdown")
    def close_client() -> None:
        client.close()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "backend": "direct-cloud"}

    def translate(call):
        try:
            return call()
        except MyQAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except MyQCloudError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def configured_door() -> dict[str, Any]:
        doors = translate(client.door_status)
        try:
            return select_door(
                doors,
                door_id=os.environ.get("MYQ_DOOR_ID"),
                door_name=os.environ.get("MYQ_DOOR_NAME"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/status", dependencies=[protected])
    def status() -> dict[str, Any]:
        return {"backend": "direct-cloud", "doors": translate(client.door_status)}

    @app.get("/garage/status", dependencies=[protected])
    def garage_status() -> dict[str, Any]:
        door = configured_door()
        return {
            "backend": "direct-cloud",
            "name": door.get("name") or "Garage Door",
            "state": door.get("door_state"),
            "online": door.get("online"),
            "last_update": door.get("last_update"),
        }

    def garage_action(action: str) -> dict[str, Any]:
        door = configured_door()
        state = str(door.get("door_state") or "").strip().lower()
        if state == action:
            return {
                "ok": True,
                "changed": False,
                "action": action,
                "state": state,
                "backend": "direct-cloud",
            }
        if door.get("online") is False:
            raise HTTPException(status_code=503, detail="Configured garage door is offline")
        account_id = str(door.get("account_id") or "")
        opener_id = str(door.get("door_opener_id") or "")
        if not account_id or not opener_id:
            raise HTTPException(status_code=503, detail="Garage door identifiers are unavailable")
        translate(lambda: client.door_action(account_id, opener_id, action))
        return {
            "ok": True,
            "changed": True,
            "action": action,
            "previous_state": state or None,
            "backend": "direct-cloud",
        }

    @app.post("/garage/open", dependencies=[protected])
    def open_garage() -> dict[str, Any]:
        return garage_action("open")

    @app.post("/garage/close", dependencies=[protected])
    def close_garage() -> dict[str, Any]:
        return garage_action("close")

    @app.get("/accounts", dependencies=[protected])
    def accounts() -> list[dict[str, Any]]:
        return translate(client.accounts)

    @app.get("/accounts/{account_id}/devices", dependencies=[protected])
    def devices(account_id: str) -> list[dict[str, Any]]:
        return translate(lambda: client.devices(account_id))

    @app.post(
        "/accounts/{account_id}/doors/{door_opener_id}/open",
        dependencies=[protected],
    )
    def open_door(account_id: str, door_opener_id: str) -> dict[str, bool]:
        translate(lambda: client.door_action(account_id, door_opener_id, "open"))
        return {"ok": True}

    @app.post(
        "/accounts/{account_id}/doors/{door_opener_id}/close",
        dependencies=[protected],
    )
    def close_door(account_id: str, door_opener_id: str) -> dict[str, bool]:
        translate(lambda: client.door_action(account_id, door_opener_id, "close"))
        return {"ok": True}

    @app.post(
        "/accounts/{account_id}/doors/{door_opener_id}/remotes/{state}",
        dependencies=[protected],
    )
    def remotes(account_id: str, door_opener_id: str, state: str) -> dict[str, bool]:
        if state not in {"enabled", "disabled"}:
            raise HTTPException(status_code=400, detail="state must be enabled or disabled")
        # myQ calls the vacation/remote-disable state 'lock mode'.
        translate(
            lambda: client.set_lock_mode(
                account_id, door_opener_id, enabled=(state == "disabled")
            )
        )
        return {"ok": True}

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Direct MyQ cloud client")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("refresh", help="Refresh and persist OAuth tokens")
    sub.add_parser("accounts", help="List accounts")
    sub.add_parser("status", help="List normalized garage-door status")

    devices = sub.add_parser("devices", help="List devices for an account")
    devices.add_argument("account_id")

    for action in ("open", "close"):
        command = sub.add_parser(action, help=f"{action.title()} a door explicitly")
        command.add_argument("account_id")
        command.add_argument("door_opener_id")

    serve = sub.add_parser("serve", help="Expose the direct client as a local REST API")
    serve.add_argument("--host", default=os.environ.get("MYQ_BIND", "0.0.0.0"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("MYQ_PORT", "8766")))

    args = parser.parse_args()

    if args.command == "serve":
        api_key = os.environ.get("MYQ_API_KEY", "")
        uvicorn.run(create_app(api_key), host=args.host, port=args.port)
        return

    with _client() as client:
        if args.command == "refresh":
            client.refresh()
            _dump({"ok": True, "session_file": str(_store().path)})
        elif args.command == "accounts":
            _dump(client.accounts())
        elif args.command == "status":
            _dump(client.door_status())
        elif args.command == "devices":
            _dump(client.devices(args.account_id))
        elif args.command in {"open", "close"}:
            client.door_action(args.account_id, args.door_opener_id, args.command)
            _dump({"ok": True, "action": args.command})
        else:
            parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
