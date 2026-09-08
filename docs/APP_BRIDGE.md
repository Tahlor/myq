# Official Android app bridge

The SuperBOX S7MAX is the production baseline for the software-only
integration:

    Broadlink -> Superbox:8765 -> official myQ Android app -> Chamberlain -> opener

The native companion in android_bridge/ is preferred. The Python/UIAutomator
implementation in src/myq_bridge/ is the controlled second driver and
diagnostic fallback.

## Known host and app

The Superbox is Android 12/API 31, 32-bit ARM (armeabi-v7a), rooted, and
reachable through network ADB. The installed official package is
com.chamberlain.android.liftmaster.myq, version 5.243.1.73243
(versionCode 73243). The APK was obtained and verified locally on 2026-09-04;
the APK and all account material stay outside Git.

The native bridge package is com.tahlor.myqbridge. Its HTTP host is a
foreground service on TCP 8765. Its accessibility component is scoped to the
official myQ package and exposes health, status, compact node inspection, and
explicit open/close/toggle endpoints. Every protected request requires an API
key; every mutation also requires a matching X-MyQ-Confirm header.

## Live evidence

The following read-only and lifecycle checks were completed without committing
credentials or raw UI artifacts:

- the bridge installed and returned health OK;
- authenticated node inspection worked;
- the bridge kept TCP 8765 alive while myQ handed off to Chrome for OAuth;
- the package-visibility query for the official APK was added and fixed the
  launch-intent lookup;
- background activity launching was removed after Android 12 rejected it and a
  LoginActivity focus-loss ANR was observed;
- the official package launcher still reproduces that LoginActivity cold-start
  ANR, including when the bridge accessibility component is disabled;
- the exported dashboard activity
  com.chamberlain.myq.main.HomeTabsActivity launches and remains foreground;
- after closing the first-run tour, the bridge observed the dashboard and two
  consecutive read-only status calls returned the configured Garage Door as
  closed;
- force-stopping only the official APK and cold-launching the dashboard
  repeated the successful read path and returned closed;
- the owner-authorized OAuth flow supplied a rotating session. A separate
  clean-room client read the account and door successfully, and one explicitly
  authorized direct-cloud open was verified closed-to-open by the sensor;
- no bridge action selector is currently configured. A calibration tap of the
  dashboard progress indicator produced an Opening state followed by a
  not-responding alert, so it is treated as a live control surface rather than
  a navigation element. The alert was dismissed without a second device tap.

A full Superbox reboot, native accessibility rebind after reboot, and
notification-access validation remain pending. No command should be used to
test those lifecycle paths.

## Install and operate

    $serial = .\scripts\connect_superbox.ps1
    .\scripts\install_myq_superbox.ps1 -PackagePath C:\path\to\myq -AdbSerial $serial
    $key = .\scripts\build_install_android_bridge.ps1 -AdbSerial $serial | Select-Object -Last 1
    $headers = @{ 'X-API-Key' = $key }

Bring the official dashboard to the foreground through the companion
Open myQ action or the verified HomeTabsActivity component. Then inspect:

    Invoke-RestMethod http://<superbox-ip>:8765/health
    Invoke-RestMethod http://<superbox-ip>:8765/debug/nodes -Headers $headers
    Invoke-RestMethod http://<superbox-ip>:8765/status -Headers $headers

Copy config/doors.example.json to ignored config/doors.json and configure
stable state selectors. Prefer resource IDs. Do not configure an action
selector until its role is separately established. For a command, first read
state, require open/closed rather than unknown or transitional state, use an
explicit endpoint and matching confirmation, and verify the requested
post-state. A same-state explicit request is a no-op.

If an app update leaves the bridge accessibility service enabled but detached,
run scripts/rebind_bridge_accessibility.ps1. It removes and re-adds only the
bridge component, preserves other enabled services, starts the visible bridge
activity, and verifies both enabled and bound state. It does not change root,
debug, su, or system-image security properties.

## Optional notification side-channel

The native bridge now includes a package-filtered notification listener. It
stores only normalized state plus an epoch timestamp and never stores or
returns notification bodies. It is advisory, stale-aware, and never used as
sole command authorization; accessibility/UIAutomator remains authoritative.
Notification access has not been enabled or runtime-validated in this
unattended run. The minimal owner-visible validation is: on the S7MAX open
Android Settings -> Notifications -> Notification access, enable “myQ LAN
Bridge notifications”, return to the bridge, and read `/status` without
sending a garage command. A natural myQ notification can then be correlated
with the normalized `notification_state`; if no notification arrives, the
side-channel remains unavailable and the app read path stays authoritative.

## Recovery/watchdog

The host is intentionally started from the visible bridge activity and from
the boot receiver. A watchdog may poll health then authenticated status and
perform only scoped recovery: start our MainActivity/host and rebind our
accessibility component while preserving other services. Bringing
HomeTabsActivity to the foreground remains a user-facing action; the watchdog
must not background-navigate myQ, send a garage command, or automatically fail
over after an ambiguous mutation.

Any future watchdog must follow the same scoped checks; no watchdog may
background-navigate myQ or send a garage command. A full-device reboot
validation is still a user-visible Superbox operation and should be scheduled
only when it will not interrupt another project.

## Current unknowns

- whether MyQ Button Preferences exposes Single Tap on the owner's account;
- whether an official internal intent/service/widget/notification action can
  replace accessibility clicking;
- whether native notification access is enabled and produces door-specific
  events;
- whether the bridge/accessibility binding survives a complete Superbox reboot;
- whether a newer APK can reuse the authenticated session without a new
  login;
- which explicit dashboard action selector can be safely calibrated.

Direct-cloud refresh/read/command evidence is preserved for comparison only.
It is not the production bridge and does not change the software-exhaustion
or hardware-activation gate.
