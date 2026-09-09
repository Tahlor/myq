# Goals and provider hierarchy

## North-star goal

Control the owner's existing G0401 reliably without adding garage-side hardware. The preferred solution removes Chamberlain cloud dependence entirely. Every fallback should preserve explicit desired-state semantics, fail closed on uncertain state, issue at most one mutation, and verify post-state without retrying an ambiguous command.

## Provider hierarchy

1. **True local / no Chamberlain cloud ? target architecture.** Pi3 talks directly to the G0401, or impersonates the service the G0401 normally contacts. This is the only path that removes both Android and Chamberlain cloud from normal operation.
2. **Linux-native clean-room MyQ client on Pi3 ? preferred cloud fallback.** Reimplement only the current official-client protocol needed for auth refresh, account/device reads, explicit open/close, and verification. No Android runtime or emulator.
3. **Official Android app internal SDK on Superbox ? default proven fallback today.** Frida 17.9.0 invokes the authenticated official app's own SDK. This path is dynamically proven with network-suppressed OPEN and CLOSE dispatch.
4. **Accessibility / Single Tap / UIAutomator ? compatibility fallback.** Retained for recovery and cross-checking, not the normal command path.
5. **Legacy/unmaintained clients ? prohibited unless independently re-proven.** `pymyq` remains deprecated. Similarity of purpose is not evidence of protocol compatibility.

Broadlink must choose a provider before a mutation. It may fail over after a read-only provider failure, but once any mutating request may have been sent it must never try another provider for that command.

## Current status

- True-local: not solved. G0401 firmware 1.10 exposes setup/metadata HTTP but no proven local operation route. Its outbound 8883 session uses TLS 1.2 PSK; the device-unique secret/application protocol remain unknown. Both HTTP and CHUB BLE setup paths provision Wi-Fi data only, and the app-side SmartHub firmware flow merely polls update status, so the highest-value remaining pure-software lane is passive OTA/current-firmware and PSK-provisioning evidence.
- Pi3-native cloud: clean-room Python implementation already covers PKCE/OAuth refresh, account/device reads, guarded open/close, and post-state verification. It is not yet promoted to the production provider because update/recovery packaging and current-session deployment still need to be completed.
- Official-app internal SDK: proven and preserved on `master`; this is the current default known-good command implementation.
- UI automation: retained and tested as fallback.

## Promotion rules

A provider becomes preferred only after repeatable read/status behavior plus explicit-action safety are demonstrated. For a cloud or local mutation provider: require stable pre-state, same-state no-op, one mutation maximum, no mutation replay after 401/timeout/transport ambiguity, and fresh post-state verification from the same provider. A one-off successful command is evidence, not enough by itself for promotion.
