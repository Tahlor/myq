# Track B1 — app/cloud protocol recovery

## Goal

Use the official Android app as an oracle, then replace UI automation with our own clean client wherever the current protocol permits it.

Historical clients proved the myQ cloud API was sufficient for account login, device enumeration, state and door commands. Chamberlain later blocked generic third-party clients. The question in 2026 is not whether an API exists—the official app necessarily has one—but what **current attestation/session material** the server requires.

Useful historical reference:

- https://github.com/hjdhjd/myq
- package: `com.chamberlain.android.liftmaster.myq`
- current Play listing (August 2026): https://play.google.com/store/apps/details?id=com.chamberlain.android.liftmaster.myq

The historical v6 client also notes an apparent MQTT interface and Firebase notifications. Treat that only as a lead until current APK/live traffic confirms it.

## Static workflow

After installing a working myQ build on the Superbox:

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

Search for these first:

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
4. If static analysis shows ordinary OkHttp/Retrofit and traffic details are still missing, attach Frida to log request metadata.
5. Redact credentials/tokens from committed output.
6. Reproduce **read-only** requests first (`account`, `devices`, `state`).
7. Only after state reads work reliably, reproduce an explicit open/close request.

The Superbox repository already contains Frida-server installation work. Reuse it rather than creating a second incompatible Frida deployment path.

## Session-bootstrap hypothesis

The June/August 2026 ReDroid reports suggest this useful possibility:

1. authenticate once using pre-Integrity myQ `5.243.1.73243`;
2. retain the resulting long-lived app session;
3. inspect which session token(s) are sufficient for normal API operations;
4. determine whether those tokens can be refreshed without a fresh hardware attestation;
5. if yes, make our own daemon consume/refresh the session directly.

If this works, the production bridge becomes:

```text
Home automation -> our local REST/MQTT service -> myQ cloud
                                        ^
                         official app only for bootstrap/recovery
```

That is much less fragile than accessibility automation while still requiring no garage-side hardware.

## Integrity decision tree

Do not assume "Play Integrity" means the entire effort is blocked.

- **Only login attested:** bootstrap with the older app and reuse session.
- **Refresh attested:** keep the official app as refresh oracle and export only short-lived credentials to the local daemon.
- **Every command attested:** UI/app bridge remains the reliable path unless current attestation can legitimately be obtained on an Android device we control.
- **Server accepts an official partner/device flow:** investigate that cleanly before patching the app.

## Capturing sensitive material

Never commit:

- usernames/passwords;
- OAuth codes/verifiers;
- bearer/refresh tokens;
- Firebase installation/auth tokens;
- Play Integrity verdict tokens;
- garage/device serials if not required for public interoperability documentation.

Store raw captures under ignored `captures/` and record only sanitized endpoint/method/schema findings in Git.
