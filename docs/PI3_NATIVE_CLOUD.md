# Pi3 Linux-native MyQ client

This is the **current production MyQ provider** for Broadlink. It is a small clean-room Linux/Python client that speaks the current official MyQ cloud protocol without Android or an emulator. It still depends on Chamberlain cloud; true-local/no-cloud remains the next research target.

## Production runtime path

```text
Broadlink GarageController
        |
        v
http://127.0.0.1:8766
        |
        v
Pi3 myq-cloud (Python)
        |
        v
Chamberlain MyQ cloud
        |
        v
G0401
```

Broadlink owns user-facing automation, cached state, freshness display, and provider selection. This repository owns the MyQ protocol/session implementation. Broadlink does not contain Chamberlain credentials or reimplement MyQ protocol details.

The Python client implements only PKCE/OAuth session refresh, account/device discovery, normalized garage state, explicit open/close, and post-state verification. Public protocol metadata is pinned to immutable profiles in `protocol_profile.py`; rotating credentials remain in `/var/lib/myq/cloud_session.json` and never belong in Git.

The production profile is `android-5.243.1.73243`. Request-shape regression tests mirror the current APK evidence: Android API calls use bearer auth plus the observed app metadata headers, OAuth refresh does not reuse bearer auth, and GDO open/close is a bodyless v6.0 PUT. See `ANDROID_REQUEST_PARITY.md`.

## State / rate discipline

The MyQ service does **not** poll on its own. Broadlink normally serves its persisted garage state without calling this service. A cloud read occurs only when:

- the user explicitly chooses Recheck state / force refresh;
- a command needs a fresh safety preflight; or
- the backend is verifying the result of the single command it already sent.

Broadlink records a separate `last_status` observation time so the UI can show exactly how old its cached knowledge is. An old cache never triggers an automatic cloud refresh.

The Python service also avoids unnecessary account-list calls after the configured garage identity is known. No mutation is automatically retried after an auth, timeout, or transport ambiguity.

## Pi3 installation / deployment

Code is deployed by **Git/SSH**, not copied piecemeal. The intended checkout is `/home/pi/Projects/myq`.

```bash
cd /home/pi/Projects/myq
git pull --ff-only origin master
sudo ./scripts/install_pi3_native_cloud.sh
```

The installer creates an isolated `.venv`, host-local configuration, and a localhost-only systemd service. The base Python install intentionally excludes Android automation dependencies; Android/Superbox tooling is optional and is not required for production.

Credentials/session state are provisioned separately. `/var/lib/myq/cloud_session.json` must remain mode `0600`; `/etc/myq/myq-cloud.env` contains the local API key and pinned profile. Do not expose port 8766 outside localhost.

Useful read-only checks:

```bash
systemctl status myq-cloud --no-pager
curl -s http://127.0.0.1:8766/health
# Protected /garage/status requires the local X-API-Key.
```

## Broadlink production selection

Production Broadlink uses the Pi3-native provider and disables Superbox selection:

```text
MYQ_ENABLE_PI3_NATIVE_CLOUD=1
MYQ_ENABLE_SUPERBOX=0
```

True-local (`MYQ_LOCAL_URL`) remains higher priority once it is actually implemented and validated. Until then, `pi3-native-cloud` is the active provider.

The Superbox/official-app implementation remains in the repository because it is valuable as:

- a protocol/reverse-engineering oracle when the official app changes;
- an emergency recovery implementation if the Python path breaks;
- preserved evidence for internal SDK dispatch and UI/accessibility fallbacks.

It is **not a production fallback while Python is healthy**, and production must not silently fail over to it.

## Production evidence

The deployed Pi3 service has passed:

- pinned-profile load and `/health`;
- live account/device/status discovery for exactly the intended garage;
- live status through the Broadlink production path;
- systemd service restart followed by successful status recovery without Android;
- request-parity regression tests against the current Android APK;
- Broadlink cache-only behavior, where ordinary UI/status reads do not contact MyQ;
- explicit forced Recheck behavior.

A historical guarded direct-cloud action also produced sensor-verified state change. A later physical-motion test that remained closed is not treated as protocol failure because the opener has an external power prerequisite. Repeated physical mutation testing is not required for normal production status operation and should not be used as a cloud/API probe.

## Failure / change policy

If MyQ changes the app or protocol:

1. leave the last-known-good profile intact;
2. recover public protocol metadata from the exact new official APK;
3. add a new immutable candidate profile;
4. validate auth and read-only state first;
5. compare request construction offline before any mutation;
6. only promote after deliberate testing;
7. never revive `pymyq` or silently switch production to Superbox.

See `FUTURE_CHANGE_RECOVERY.md` and `GOALS_AND_PROVIDER_HIERARCHY.md`.
