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

## UI-free invocation investigation

The exact installed APK and runtime package metadata still need a complete,
read-only inventory of:

- exported activities, services, receivers, and providers;
- deep links and intent filters;
- app shortcuts, widgets, notification actions, and Auto/car components;
- WorkManager/job names and action repository/ViewModel call sites.

Use the decompiled manifest and JADX source for this inventory:

    python tools/android_surface_inventory.py <jadx-output>\resources\AndroidManifest.xml --jadx <jadx-output>\sources

The helper reports only component metadata and signal locations. Search for
PendingIntent, ShortcutInfo, AppWidgetProvider, Intent, startService,
sendBroadcast, and open/close action methods. A manifest entry alone is not
evidence that invocation is safe. Do not call unknown components by trial.

Any discovered primitive must be classified as read-only, user-visible, or
mutating before runtime use. For a mutating primitive, retain the bridge's
stable-state, explicit-confirmation, one-action, and fresh-post-state guards.
Never fail over to another driver after a mutating request may have reached
MyQ.

## Notification state

The native bridge contains a package-filtered listener that records normalized
state and timestamp metadata, not notification bodies. It is advisory and
stale-aware; it cannot authorize a command and does not replace a fresh
app/sensor read. Notification access still needs a future user-visible enable
and runtime validation.

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
