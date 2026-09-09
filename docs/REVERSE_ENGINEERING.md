# Official-app and cloud protocol research

This document records current software evidence for issue #9. It is not a
production-cloud design. The official Android app/Superbox bridge is the
production baseline; direct-cloud code is a bounded current-2026 oracle or
fallback only.

## Exact app evidence

The installed APK is myQ 5.243.1.73243,
package com.chamberlain.android.liftmaster.myq. Its static service definitions
include:

- authentication at partner-identity.myq-cloud.com/connect/token;
- account APIs at accounts.myq-cloud.com;
- device APIs at devices.myq-cloud.com;
- GDO APIs at account-devices-gdo.myq-cloud.com;
- explicit v6 GDO PUT operations ending in /open and /close;
- Android client id ANDROID_CGI_MYQ, scope MyQ_Residential offline_access,
  redirect URI com.myqops://android, and PKCE S256;
- common Android metadata MyQApplicationId, Culture, BrandId, ApiVersion 4.1,
  App-Version, and an Android user-agent;
- TCP/8883 diagnostic strings and App Check/Integrity feature flags.

Static strings are not proof of runtime enforcement or opener protocol. Exact
APK decompilation remains local and ignored.

The shared device service exposes a v6.0 device-list route with an envelope
containing items. The clean-room client prefers that route for Android-shaped
sessions and falls back to the separately observed v6.2 route only on 404/405.
This is read-only route selection.

## 2026-09-08 static notification result

The ignored local smali extraction of the installed APK was checked without
invoking any component. MyQMessagingService builds a notification
`PendingIntent` and a notification action targeting
`SnoozeBroadcastReceiver`; the reviewed action string is `snooze`, not a garage
open/close operation. This is a notification/UI clue, not a safe internal
command surface. The native bridge therefore consumes only normalized
notification state and does not attempt to fire the official app's
`PendingIntent`.

The exact APK's binary manifest was also inventoried locally. It contains 59
activities, 16 receivers, 23 services, and 7 exported components. The relevant
exported application surfaces are `LoginActivity`, `SplashActivity`, and
`HomeTabsActivity`; `SnoozeBroadcastReceiver` and `MyQMessagingService` are
not exported. The bounded SDK audit found the internal v6 transport class
`myq/sdk/common/misc/communication/method/k`, including one
`vgdoservice/body` method and 21 v6-service dispatch references, but no direct
dashboard operation invocation. This remains an internal implementation lead,
not an externally callable or production-safe action primitive.

## UI-free invocation investigation

This lane is now **PROVEN in network-suppressed runtime testing** against the
exact installed myQ 5.243.1.73243 APK. Static tracing plus Frida 17.9.0 reached
the real dashboard actuation chain and the official v6 service wrappers.

The live chain is:

```text
DeviceView single tap
  -> dashboard f1.n0/F/B/G0
  -> DevicePollerApiImpl
  -> garage model myq.sdk.data.model.devices.a0 (extends devices.p)
  -> communication.method.k.j(...) for OPEN
  -> communication.method.k.c(...) for CLOSE
  -> Chamberlain v6 default wrappers `f` (open) / `a` (close)
```

On 2026-09-09 the packaged dry-run refreshed devices through the official
`DeviceApiImpl.M(activeAccountId, null)` read path, found exactly one garage in
`CLOSED` state, invoked both internal action methods, and intercepted both
final wrappers before they reached the network. It emitted `suppressed=open`
and `suppressed=close`; no garage movement or outbound command occurred.

The preserved harness is:

```powershell
.\scripts\invoke_myq_internal_action.ps1 -Action probe
```

Safety contract:

- Frida 17.9.0 is the only validated attach pair for this Superbox;
- default mode hooks/suppresses the final open/close wrappers;
- exactly one garage must exist and state must be `OPEN` or `CLOSED`;
- same-state actions are no-ops;
- live mode requires `-Execute` plus matching `-ConfirmAction`;
- a mutation is sent at most once; only read-only refreshes are used afterward;
- an ambiguous/unverified mutation explicitly says **do not retry**.

This is the default proven official-app command mechanism. Accessibility and
UIAutomator remain useful fallbacks but are no longer the preferred command
path. One owner-observed unsuppressed physical transition is still pending
before calling the live mutation path physically verified.

## Notification state

The native bridge contains a package-filtered listener that records normalized
state and timestamp metadata, not notification bodies. It is advisory and
stale-aware; it cannot authorize a command and does not replace a fresh
app/sensor read. Notification access is enabled on the Superbox and the listener is live. It
remains advisory; a natural door event still needs correlation if we want to
use it as an independent state side-channel.

## Current clean-room client

src/myq_bridge/cloud.py implements the currently observed session shape:

- rotating OAuth access/refresh tokens are stored atomically in an ignored
  local file;
- read-only requests may refresh and retry once after 401;
- mutating requests are never automatically replayed after 401;
- account/device reads normalize garage-door state;
- explicit open/close commands serialize, preflight stable online state, send
  at most one PUT, and verify the desired post-state;
- same-state actions are verified no-ops.

src/myq_bridge/cloud_cli.py exposes read-only status/preflight and explicit
action-confirmed commands for research. The CLI is blocked unless
MYQ_ENABLE_EXPERIMENTAL_CLOUD=1 is set. No checked-in service deploys it.

A 2026 authorized session read the owner's door and one explicitly authorized
open completed with sensor-verified closed-to-open state. This proves a useful
fallback/oracle path, not a durable production architecture.

## 2026-09-08 external software check

The current public software evidence reinforces the cloud fallback boundary:

- [`hjdhjd/myq`](https://github.com/hjdhjd/myq) remains an active modern v6
  OAuth implementation used by its maintained Homebridge integration and
  documents status plus open/close operations. It is a useful comparison/oracle
  for current cloud behavior, not a local G0401 protocol implementation;
- [`bvdcode/myq-home-assistant`](https://github.com/bvdcode/myq-home-assistant)
  is a newer community Home Assistant integration that documents MFA/session
  renewal and cloud polling, but likewise uses the residential cloud rather
  than the opener's normal-LAN service; and
- [`arraylabs/pymyq`](https://github.com/arraylabs/pymyq) is archived as of
  2026-06-05, so it remains deprecated and was not revived.

A narrow search found no current primary-source Ezlo SoftHub/Tricon myQ
adapter that would improve the owner's software-only path. No external
integration was installed or made part of the production bridge.

## Static and dynamic workflow

Pull/decompile only the exact installed APK:

    $dir = .\scripts\pull_myq_apks.ps1
    .\scripts\decompile_myq.ps1 -ApkDirectory $dir
    python tools\summarize_jadx.py <jadx-output>
The summary/inventory may report hosts, routes, component names, and method
locations. Never print or commit usernames, passwords, OAuth codes, verifiers,
bearer tokens, Firebase tokens, device serials, or raw notification content.

For runtime observation, start the official app through the user-facing
HomeTabsActivity path. Capture sanitized logcat/DNS metadata while refreshing
state. Frida, if needed, should log non-secret method names and request
metadata only. Read accounts/devices/status before considering one explicit
action. No background service should navigate the app.

## Provisioning and local protocol hypotheses

The current CHUB BLE code is commissioning/metadata oriented. It does not prove
an operational command path. The G0401 normal-LAN service and historical
myq_aes/NVM work are documented in LAN_RECON.md. The current PSK lineage is
still unknown: determine from static app/firmware evidence whether it is
factory/random, server-provisioned, or derived. Stop when evidence indicates a
device-unique secret with no software-accessible source; do not brute-force it.

Historical MyQ clients and MQTT/WebSocket strings are leads only. Confirm
current behavior from live evidence or exact APK/firmware evidence before
assigning protocol semantics.
