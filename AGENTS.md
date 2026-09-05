# Agent guidance

## Objective

Build a reliable **software-only** integration for the owner's existing myQ garage-door system. Do not require ratgdo, relays, ESP32s, wiring changes, replacement logic boards, or other garage-side hardware unless the owner explicitly changes the goal.

## Work both tracks

1. **Official-app bridge:** keep a usable integration working through the real Android myQ app. The existing SuperBOX S7MAX is the preferred Android host.
2. **Protocol recovery:** progressively remove dependencies on UI automation and ultimately on the myQ cloud if live evidence shows a practical route.

Neither track blocks the other. A working app bridge is useful even while protocol recovery continues.

## Evidence order

Treat evidence in this order:

1. live behavior from the owner's current opener/app/network;
2. current APK static/dynamic analysis;
3. current official myQ behavior/documentation;
4. maintained third-party work;
5. historical myQ API implementations.

Do not assume a 2023 API failure still behaves identically in 2026. Do not assume a historical endpoint still exists merely because it appears in old source.

## Superbox

Reuse `Tahlor/superbox` as the canonical reference for device access. The S7MAX is Android 12, 32-bit ARM, rooted, and reachable through network ADB. Never commit its sensitive identifiers or account material here.

Do not permanently alter Superbox root/security properties just to satisfy myQ until a reversible test proves that is necessary. The box supports other projects.

## Repository hygiene

- Work on `master` unless explicitly told otherwise.
- Keep credentials, session tokens, APKs, pcaps, screenshots and live UI dumps out of Git.
- Prefer scripts that produce sanitized summaries plus ignored raw artifacts.
- Add tests for parsers/state logic whenever captured evidence makes that possible.
- Record decisive runtime findings in `docs/` so later agents do not repeat experiments.

## Physical-access safety

A garage door moves heavy hardware and controls entry to a home.

- Never issue an open/close command solely as a connectivity probe if a read-only observation can answer the question.
- Serialize commands and avoid blind toggles.
- During live command tests, make the requested state explicit and verify observed state before sending a toggle.
