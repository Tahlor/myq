# Meta-objective completion gate

The project is complete only when it has a trustworthy, software-only path for the owner's existing myQ opener. “The code can send an HTTP request” is not sufficient.

## Required gates

1. **Read gate:** an authenticated path reads the real door state, identifies the configured opener unambiguously, and has been repeated against the live account without exposing credentials.
2. **Command gate:** an explicitly requested `open` or `close` operation crosses an action-specific confirmation boundary, reads a stable `open`/`closed` pre-state, refuses offline/unknown/transitional states, sends at most one action, and returns success only after a fresh read observes the requested post-state. A same-state request is a verified no-op; ambiguous outcomes fail closed.
3. **Official-app fallback:** the native SuperBOX bridge remains installable, authenticated, package-scoped, and documented as the UI fallback. It must not launch myQ from a background LAN request.
4. **Protocol decision:** the direct-cloud and LAN tracks have a current evidence record stating what is proven, what remains experimental, and the next safe observation. Local control is a bonus track, not a reason to add garage-side hardware.
5. **Handoff gate:** tests cover the parser/state logic and command safety rules; raw credentials, APKs, captures, screenshots, and UI dumps remain ignored; recovery and rollback steps are documented, including post-update accessibility rebinding.

## Current status — 2026-09-06

- Direct-cloud read: two consecutive owner-authorized status reads returned one door as `closed` and `online` before the command. A fresh authenticated read after the command returned `open` and `online`; no credentials or account/device identifiers were exposed.
- Direct-cloud command: the client and REST/CLI callers expose a read-only preflight, require action-specific confirmation at mutating boundaries, and enforce serialized before-state and after-state verification in tests. With explicit owner authorization, exactly one guarded `open` was sent after the sensor reported stable `closed`/online; the command result was `closed → open` with `changed=True`, and no retry or toggle was issued.
- Official-app bridge: the dashboard shortcut is stable across an app-process restart, background navigation is guarded, and the native bridge independently reported `Garage Door: open` and online after the cloud command. The package launcher still reproduces a `LoginActivity` focus-loss ANR, but the explicit exported dashboard activity is the documented foreground fallback; full Superbox reboot persistence remains pending.
- LAN track: current evidence confirms an outbound TCP/8883 session for the probable device, but no local status or command protocol is proven.
- Handoff: the sanitized test suite passes (`33 passed`), the accessibility rebind helper was live-tested while preserving existing services, and sensitive runtime artifacts remain ignored.

All required gates for this software-only milestone now pass. Full-device-reboot persistence, the package-launcher ANR, and direct LAN protocol recovery remain non-blocking follow-up work.
