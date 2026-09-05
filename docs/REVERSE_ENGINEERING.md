# Track B1 — app/cloud protocol recovery

## Goal

Use the official Android app as an oracle, then replace UI automation with our own clean client wherever the current protocol permits it.

## Strong current evidence — August 2026

A new public Home Assistant integration, `vector-sec/chamberlain-myq-hacs`, was created August 10, 2026 and implements direct MyQ control with:

- an initial authorized JWT/access token plus refresh token;
- standard OAuth `grant_type=refresh_token` rotation;
- client id `IOS_CGI_MYQ`;
- app version `5.315.0.66076` and matching iOS-style User-Agent;
- `partner-identity.myq-cloud.com/connect/token` for refresh;
- v6 account APIs and v6.2 device enumeration;
- v6 door-opener `PUT .../{open|close}` commands;
- no Play Integrity/App Check argument on the refresh or door-command request surface shown by that implementation.

This is stronger than the old 2023 API evidence. We therefore clean-room implemented the current protocol facts in `src/myq_bridge/cloud.py` and `src/myq_bridge/cloud_cli.py`. Do not copy/vendor the external implementation; its repository currently has no license file.

The remaining B1 gate is **initial authorized-session bootstrap**. Once an authorized access/refresh-token pair is available locally, our client can rotate it and persist the new pair atomically in ignored `config/cloud_session.json`.

As of 2026-09-04, this checkout has no local session file and no token environment variables, so live refresh/account validation is intentionally blocked pending an authorized bootstrap pair. No token material was requested or recorded by the agent.

```powershell
Copy-Item config\cloud_session.example.json config\cloud_session.json
# Fill this local ignored file with an authorized session; never commit it.
myq-cloud refresh
myq-cloud accounts
myq-cloud devices <account-id>

$env:MYQ_API_KEY = '<local-secret>'
myq-cloud serve   # default port 8766
```

The direct REST facade exposes explicit open/close operations only; it does not use a toggle. Read-only status is available globally at `GET /status` and for a single account at `GET /accounts/{account_id}/status`.

## Current APK static cross-check — 5.243.1.73243

The verified APK installed on the SuperBOX is version `5.243.1.73243`. A local decompilation of that exact APK independently confirms the current cloud route families and production hosts:

- authentication uses `https://partner-identity.myq-cloud.com/connect/token`;
- account APIs use `accounts.myq-cloud.com`;
- device APIs use `devices.myq-cloud.com`;
- door-opener APIs use `account-devices-gdo.myq-cloud.com`;
- the v6 Retrofit service includes read access to `.../api/{apiVersion}/accounts/{accountId}/door_openers/{serialNumber}` and explicit `PUT` routes ending in `/open` and `/close`;
- the app's version enum includes `v6.0`, while the newer device-enumeration path used by the clean-room client remains a separate live-evidence question;
- common request metadata includes `MyQApplicationId`, `Culture`, `BrandId`, `ApiVersion: 4.1`, `App-Version`, `Accept: application/json`, and an Android model/release user agent.

The same APK's OAuth parameter enum uses client id `ANDROID_CGI_MYQ`, scope `MyQ_Residential offline_access`, redirect URI `com.myqops://android`, and PKCE `S256`; refresh-token grants are implemented alongside authorization-code grants. This is a concrete reason to keep the clean-room client's client id and app identity configurable: the existing direct-refresh evidence came from a different iOS-style client identity and is not proof that the two refresh-token contexts are interchangeable.

The APK also contains TCP-8883 diagnostic text and App Check/Integrity feature flags. Their static presence is not evidence that every current request is enforced by attestation; that distinction still requires authenticated runtime observation. Raw APK/decompiler output remains local and ignored.

The OAuth manager persists the access and refresh values in the app's encrypted `LiftmasterMyQPrefs.xml` preferences. The repository now includes `scripts/extract_myq_session.ps1`, which uses the already-authorized root path on the SuperBOX, decrypts those two values in memory using the APK's app-local storage configuration, and atomically writes only the direct-client session shape to ignored `config/cloud_session.json`. It never prints token contents. A live run before authentication correctly reports that both tokens are absent.

## Other references

Historical clients proved the MyQ cloud API was sufficient for account login, device enumeration, state and door commands before Chamberlain's anti-automation changes:

- https://github.com/hjdhjd/myq
- official Android package: `com.chamberlain.android.liftmaster.myq`
- current Play listing: https://play.google.com/store/apps/details?id=com.chamberlain.android.liftmaster.myq

The historical v6 client also mentions an apparent MQTT interface and Firebase notifications. Treat that only as a lead until current APK/live traffic confirms which MQTT/WebSocket surfaces are app-facing versus opener-facing.

## Static workflow

After installing a working MyQ build on the Superbox:

```powershell
$dir = .\scripts\pull_myq_apks.ps1
.\scripts\decompile_myq.ps1 -ApkDirectory $dir
```

`tools/summarize_jadx.py` searches the JADX output for:

- `*.myq-cloud.com` domains;
- MQTT / `8883` / broker strings;
- Firebase App Check;
- Play Integrity classes;
- OAuth/PKCE/auth strings;
- OkHttp / Retrofit / certificate pinning;
- WebSocket endpoints.

Raw decompilation stays ignored. Commit only clean-room notes describing behavior/interfaces we need for interoperability.

### Highest-value classes/strings

```text
IntegrityManager
StandardIntegrityManager
FirebaseAppCheck
PlayIntegrityAppCheckProviderFactory
CertificatePinner
OkHttpClient
Retrofit
Authorization
Bearer
code_verifier
code_challenge
mqtt
8883
wss://
myq-cloud.com
```

Also inspect Android resources for base URLs, remote-config keys and feature flags. Split APKs can carry resources not present in `base.apk`, so retain all pulled splits even if JADX initially opens only the base.

## Dynamic workflow

Prefer observation before bypassing anything.

1. Start the authenticated official app.
2. Capture `logcat` while refreshing the door dashboard.
3. Record DNS destinations from the Android host/network.
4. If static analysis shows ordinary OkHttp/Retrofit and traffic details are still missing, attach Frida to log **non-secret request metadata**.
5. Keep credentials/tokens out of committed output.
6. Compare the Android app's client id/app-version/header shape with the working August 2026 iOS identity.
7. Reproduce read-only `accounts` and `devices` calls first.
8. Only after state reads work reliably, reproduce an explicit open/close request.

The Superbox repository already contains Frida-server installation work. Reuse it rather than creating a second incompatible deployment path.

## Revised session-bootstrap hypothesis

The direct refresh evidence changes the likely architecture:

```text
                    one-time / recovery bootstrap
official MyQ app  -----------------------------> authorized session
                                                     |
                                                     v
Home automation -> our local REST service -> MyQ v6 cloud -> opener
```

The leading hypotheses now are:

1. **Integrity is login/bootstrap-only.** Best case: authenticate with a compatible official app, then use the rotating OAuth session indefinitely in our daemon.
2. **Client identity matters at refresh.** Capture the actual Android client id/version metadata and make it configurable; do not assume an Android-issued refresh token is interchangeable with `IOS_CGI_MYQ`.
3. **Old authenticated session can seed a newer client.** Test session persistence/upgrades on the Superbox after basic control is proven.

## Integrity decision tree

- **Login-only attestation:** direct cloud becomes primary; official app is bootstrap/recovery.
- **Refresh-time attestation:** current August 2026 direct-refresh evidence would need reconciliation with our account/token origin; keep app bridge available.
- **Per-command attestation:** contradicted by the current direct integration unless its account/client context differs materially; verify live before assuming.
- **Official partner/device flow becomes available:** prefer it over brittle app emulation.

## Sensitive material

Never commit:

- usernames/passwords;
- OAuth codes/verifiers;
- bearer/access/refresh tokens;
- Firebase installation/auth tokens;
- Play Integrity verdict tokens;
- garage/device serials if not required for public interoperability documentation.

Use ignored `config/cloud_session.json` and `captures/` for local evidence. Commit only sanitized endpoint/method/schema findings.
