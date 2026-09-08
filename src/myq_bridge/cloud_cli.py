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


EXPERIMENTAL_CLOUD_FLAG = "MYQ_ENABLE_EXPERIMENTAL_CLOUD"


def _require_experimental_cloud() -> None:
    if os.environ.get(EXPERIMENTAL_CLOUD_FLAG) != "1":
        raise RuntimeError(
            "myq-cloud is experimental/current-2026 oracle tooling; set "
            f"{EXPERIMENTAL_CLOUD_FLAG}=1 for an intentional run"
        )


def _store() -> SessionStore:
    return SessionStore(os.environ.get("MYQ_CLOUD_SESSION", "config/cloud_session.json"))


def _client() -> MyQCloudClient:
    _require_experimental_cloud()
    store = _store()
    return MyQCloudClient(load_cloud_session(store), on_session_updated=store.save)


def _dump(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _require_action_confirmation(action: str, confirmation: str | None) -> None:
    if confirmation != action:
        raise HTTPException(
            status_code=428,
            detail=f"Set X-MyQ-Confirm: {action} to authorize this command",
        )


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

    @app.get("/accounts/{account_id}/status", dependencies=[protected])
    def account_status(account_id: str) -> dict[str, Any]:
        return {
            "backend": "direct-cloud",
            "account_id": account_id,
            "doors": translate(lambda: client.door_status(account_id)),
        }

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
        desired = "open" if action == "open" else "closed"
        if state not in {"open", "closed"}:
            raise HTTPException(
                status_code=503,
                detail="Configured garage door state is not stable",
            )
        if door.get("online") is not True:
            raise HTTPException(
                status_code=503,
                detail="Configured garage door is not confirmed online",
            )
        account_id = str(door.get("account_id") or "")
        opener_id = str(door.get("door_opener_id") or "")
        if not account_id or not opener_id:
            raise HTTPException(status_code=503, detail="Garage door identifiers are unavailable")
        result = translate(
            lambda: client.door_command(account_id, opener_id, action)
        )
        return {**result, "backend": "direct-cloud", "desired_state": desired}

    @app.post("/garage/open", dependencies=[protected])
    def open_garage(
        x_myq_confirm: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_action_confirmation("open", x_myq_confirm)
        return garage_action("open")

    @app.post("/garage/close", dependencies=[protected])
    def close_garage(
        x_myq_confirm: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_action_confirmation("close", x_myq_confirm)
        return garage_action("close")

    @app.get("/accounts", dependencies=[protected])
    def accounts() -> list[dict[str, Any]]:
        return translate(client.accounts)

    @app.get("/accounts/{account_id}/devices", dependencies=[protected])
    def devices(account_id: str) -> list[dict[str, Any]]:
        return translate(lambda: client.devices(account_id))

    @app.get(
        "/accounts/{account_id}/doors/{door_opener_id}/preflight/{action}",
        dependencies=[protected],
    )
    def preflight(account_id: str, door_opener_id: str, action: str) -> dict[str, Any]:
        if action not in {"open", "close"}:
            raise HTTPException(status_code=400, detail="action must be open or close")
        return translate(lambda: client.door_preflight(account_id, door_opener_id, action))

    @app.post(
        "/accounts/{account_id}/doors/{door_opener_id}/open",
        dependencies=[protected],
    )
    def open_door(
        account_id: str,
        door_opener_id: str,
        x_myq_confirm: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_action_confirmation("open", x_myq_confirm)
        return translate(lambda: client.door_command(account_id, door_opener_id, "open"))

    @app.post(
        "/accounts/{account_id}/doors/{door_opener_id}/close",
        dependencies=[protected],
    )
    def close_door(
        account_id: str,
        door_opener_id: str,
        x_myq_confirm: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_action_confirmation("close", x_myq_confirm)
        return translate(lambda: client.door_command(account_id, door_opener_id, "close"))

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

    preflight = sub.add_parser(
        "preflight", help="Read a door and report whether an explicit action is safe"
    )
    preflight.add_argument("account_id")
    preflight.add_argument("door_opener_id")
    preflight.add_argument("action", choices=("open", "close"))

    for action in ("open", "close"):
        command = sub.add_parser(action, help=f"{action.title()} a door explicitly")
        command.add_argument("account_id")
        command.add_argument("door_opener_id")
        command.add_argument(
            "--confirm",
            action="store_true",
            required=True,
            help=f"Confirm that this command is intentionally requesting {action}",
        )

    serve = sub.add_parser("serve", help="Expose the direct client as a local REST API")
    serve.add_argument("--host", default=os.environ.get("MYQ_BIND", "0.0.0.0"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("MYQ_PORT", "8766")))

    args = parser.parse_args()

    try:
        _require_experimental_cloud()
    except RuntimeError as exc:
        parser.error(str(exc))

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
        elif args.command == "preflight":
            _dump(client.door_preflight(args.account_id, args.door_opener_id, args.action))
        elif args.command in {"open", "close"}:
            if not args.confirm:
                parser.error(f"{args.command} requires --confirm")
            _dump(client.door_command(args.account_id, args.door_opener_id, args.command))
        else:
            parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
