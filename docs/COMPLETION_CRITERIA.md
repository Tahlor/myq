# Meta-objective completion gate

The project is complete only when it has a trustworthy, software-only path for the owner's existing myQ opener. “The code can send an HTTP request” is not sufficient.

## Required gates

1. **Read gate:** an authenticated path reads the real door state, identifies the configured opener unambiguously, and has been repeated against the live account without exposing credentials.
2. **Command gate:** an explicitly requested `open` or `close` operation crosses an action-specific confirmation boundary, reads a stable `open`/`closed` pre-state, refuses offline/unknown/transitional states, sends at most one action, and returns success only after a fresh read observes the requested post-state. A same-state request is a verified no-op; ambiguous outcomes fail closed.
3. **Official-app fallback:** the native SuperBOX bridge remains installable, authenticated, package-scoped, and documented as the UI fallback. It must not launch myQ from a background LAN request.
4. **Protocol decision:** the direct-cloud and LAN tracks have a current evidence record stating what is proven, what remains experimental, and the next safe observation. Local control is a bonus track, not a reason to add garage-side hardware.
5. **Handoff gate:** tests cover the parser/state logic and command safety rules; raw credentials, APKs, captures, screenshots, and UI dumps remain ignored; recovery and rollback steps are documented.

## Current status — 2026-09-06

- Direct-cloud read: two consecutive owner-authorized status reads each returned one door as `closed` and `online`; no mutating endpoint was called.
- Direct-cloud command: the client and REST/CLI callers now expose a read-only preflight, require action-specific confirmation at mutating boundaries, and enforce serialized before-state and after-state verification in tests. A temporary loopback REST service also passed authenticated `/health`, `/status`, and `/preflight/open` checks with `closed → open` readiness; no live mutating request has been made.
- Official-app bridge: the dashboard shortcut is stable across an app-process restart, the bridge reads `Garage Door: closed` twice after restart, and background navigation is guarded. The package launcher still reproduces a `LoginActivity` focus-loss ANR, and the dashboard's live action surface needs an explicitly authorized test; full Superbox reboot persistence remains pending.
- LAN track: current evidence confirms an outbound TCP/8883 session for the probable device, but no local status or command protocol is proven.

The goal remains active until the read and command gates pass on the real account and the remaining handoff gates are satisfied.
