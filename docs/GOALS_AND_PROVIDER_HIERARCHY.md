# Goals and provider hierarchy

## North-star goal

Control the owner's existing G0401 reliably without adding garage-side hardware. The preferred end state removes Chamberlain cloud dependence entirely. Every provider must preserve explicit desired-state semantics, fail closed on uncertain state, issue at most one mutation, and never retry or fail over after a mutating request may have been sent.

## Production architecture today

The production path is now:

```text
Broadlink -> localhost Pi3 myq-cloud (Python) -> Chamberlain MyQ cloud -> G0401
```

Broadlink owns the stateful garage object, cached state, freshness UX, schedules, web/voice entrypoints, and provider selection. `Tahlor/myq` owns the Chamberlain protocol implementation and rotating session. Broadlink does not own MyQ credentials or protocol details.

Normal Broadlink status/UI reads are cache-only. MyQ is contacted only for an explicit Recheck/force refresh or for the safety checks around an explicit command. Cache age alone never causes cloud traffic.

The current Python profile is pinned to the current Android-derived protocol profile. Live deployed status has been validated on Pi3, including service restart recovery. Request construction is regression-tested against the current APK's observed Retrofit/OkHttp contract.

## Provider hierarchy

1. **True local / no Chamberlain cloud - target architecture.** Pi3 talks directly to the G0401, or locally emulates the Chamberlain service the G0401 normally contacts. This is the only path that removes Chamberlain cloud from normal operation.
2. **Linux-native clean-room MyQ client on Pi3 - current production provider.** Small Python service implementing only the current official-client protocol needed for session refresh, account/device reads, explicit open/close, and verification. No Android runtime or emulator.
3. **Official Android app / Superbox paths - retained backup research only.** Preserve the proven internal-SDK, accessibility, UIAutomator, notification, and reverse-engineering work because it is useful for recovery, comparison against future app changes, and protocol archaeology. It is **not in production** while the Python provider is healthy. Broadlink production sets `MYQ_ENABLE_SUPERBOX=0`.
4. **Legacy/unmaintained clients - prohibited unless independently re-proven.** `pymyq` remains permanently deprecated. Similarity of purpose is not evidence of compatibility.

Broadlink chooses one provider before mutation. Read-only selection may try another provider, but once a mutation may have been sent it must never retry that action through any provider.

## Current status

- **Pi3-native Python cloud path: production.** Deployed under systemd on Pi3, localhost-only, live status validated, restart recovery validated, current Android-shaped request parity tested, and selected as the only active cloud provider in Broadlink production.
- **Broadlink stateful integration: production.** `GarageController` persists the latest observation, exposes the age of the cached observation, never refreshes merely because data is old, and supports explicit one-shot force refresh.
- **Superbox / official Android app: preserved but disabled from production selection.** Keep all code, documentation, Frida/internal-SDK evidence, UI fallbacks, and recovery notes. Treat them as a research oracle and emergency recovery path, not as a background fallback that production may silently use.
- **True-local: not solved.** G0401 firmware 1.10 exposes setup/metadata HTTP but no proven operational LAN endpoint. Its normal outbound 8883 session uses TLS 1.2 PSK; the device credential and application protocol remain unknown. Provisioning evidence shows Wi-Fi credentials but no obvious cloud PSK being sent by the app.

## Next software-only research priority

Before opening hardware, finish the highest-value direct-software lane:

1. passively identify the G0401's natural DNS/HTTPS/8883 destinations and any OTA/version-check traffic;
2. recover a current firmware or OTA manifest if it is normally retrievable without changing device state;
3. analyze current firmware/offline artifacts for TLS-PSK provisioning/storage, OTA endpoints, HTTP route tables, NVM records, and opener/cloud protocol strings;
4. finish classification of PSK origin: fixed, metadata-derived, locally generated, server-provisioned, factory-random, or unknown;
5. probe only evidence-backed read-only LAN routes; do not fuzz or reset/re-pair the production unit.

If these software lanes are exhausted without a credential/protocol recovery path, then the hardware gate can be reconsidered with a narrow objective: recover firmware/device credential material needed to decrypt and reproduce the G0401 cloud session locally.

## Promotion / regression rules

For any production provider: require repeatable read/status behavior, explicit desired-state semantics, stable pre-state, same-state no-op, one mutation maximum, no mutation replay after 401/timeout/transport ambiguity, and same-provider post-state verification. Future MyQ/app changes must create a new protocol profile and be validated read-only before promotion; never silently overwrite the last-known-good profile.
