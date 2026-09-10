# Future-change recovery process

This document is the playbook for MyQ app/API/firmware changes. The goal is to make a future breakage a bounded compatibility update instead of rediscovering the project from scratch.

## Preserve four independent evidence layers

1. **Device-local layer:** G0401 model/firmware, normal-LAN HTTP surface, outbound transport, TLS/PSK observations, and any locally proven operation protocol.
2. **Linux-native cloud layer:** versioned public protocol profile, OAuth/PKCE behavior, read endpoints, mutation endpoints, and safety semantics. Credentials/tokens are never part of the profile.
3. **Official Android internal layer:** exact APK version, validated Frida pair, live model class, SDK refresh path, and final OPEN/CLOSE wrapper call sites.
4. **UI compatibility layer:** accessibility selectors, Single Tap behavior, notifications, and UIAutomator observations.

A change in one layer must not automatically invalidate the others.

## When MyQ updates or something breaks

1. Record exact date, installed APK version/versionCode, failure symptom, and which provider failed. Do not begin by changing production settings.
2. Re-run read-only health/status for every provider. Determine whether the failure is authentication, account/device discovery, state parsing, mutation dispatch, Android class drift, or G0401 connectivity.
3. Pull/decompile the exact new APK into ignored local captures. Never commit APKs, tokens, serials, screenshots, or raw traffic containing credentials.
4. Run the protocol-profile/static surface audit. Compare public client ID, OAuth scope/redirect, application ID, app/API versions, hostnames/routes, Android SDK classes, and OPEN/CLOSE wrappers against the last-known-good profile.
   Example: `python tools/audit_protocol_profile.py <decompiled-root> [<additional-root> ...]`. Exit code 2 means required static public markers are missing and a candidate needs review; runtime-attested fields such as an application ID may be reported as unattested without causing drift. Neither result by itself proves a protocol change.
5. Update a **candidate profile** only. Do not overwrite the last-known-good profile in place.
6. Validate candidate authentication/session refresh and account/device reads first. Safe GET/HEAD operations may retry after a token refresh; mutations may not.
7. Validate desired-state parsing and exactly-one-door selection. Unknown/transitional/offline state must fail closed.
8. Validate mutation routing with a suppressed/intercepted dry run where possible. For Android internal SDK changes, hook the final network wrapper and prove OPEN and CLOSE are both reached while suppressed.
9. Only then perform one owner-authorized physical command, starting from a known state and verifying convergence. Never use a garage command as a connectivity probe.
10. Promote the candidate only after tests, docs, and evidence are committed. Keep the previous profile so rollback remains possible.

## Versioned protocol profile

Public protocol metadata belongs in one versioned structure: client identity, OAuth authorization/token endpoints, scope, redirect URI, application/brand/culture/API headers, account/device read routes, and explicit operation routes. Session credentials are stored separately and rotate independently. Every persisted cloud session pins an exact `profile_name`; client ID alone is not a durable version key because MyQ may reuse it across app generations.

An app update is not itself a reason to change the Pi3-native client. Continue using the last-known-good profile until read-only evidence shows it no longer works or the exact new APK demonstrates a required change. If a new read route is needed, bounded read-only fallback is acceptable. Never add automatic fallback between mutating endpoints.

## Regression checklist

- repository policy still forbids `pymyq` as a runtime dependency;
- last-known-good protocol profile remains available;
- persisted sessions pin an exact profile name, with legacy migration only when client ID/app version resolve uniquely;
- exact APK audit reports known/missing/drifted public surfaces without printing secrets;
- read-only account and device tests pass;
- state normalization handles only stable OPEN/CLOSED as actionable;
- same-state command is a no-op;
- mutation requires explicit action confirmation;
- mutation sends once at most;
- 401/timeout after mutation is ambiguous and is not replayed;
- post-state polling never sends another command;
- Android internal dry run suppresses both OPEN and CLOSE at the final wrapper;
- Broadlink provider order remains true-local -> Pi3-native cloud -> official-app internal -> UI fallback once Pi3-native is promoted.

## What not to do

Do not revive an old client because its repository starts working again without reproducing current behavior against the owner's setup. Do not copy opaque credentials from the APK into source. Do not auto-adopt a new app version/profile merely because it is newer. Do not treat TCP/8883 as proof of MQTT. Do not brute-force the G0401 PSK. Do not retry or fail over after an ambiguous physical mutation.
