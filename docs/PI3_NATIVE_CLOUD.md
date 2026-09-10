# Pi3 Linux-native MyQ client

This is provider tier 2 in `GOALS_AND_PROVIDER_HIERARCHY.md`: a small clean-room Linux client that speaks the current official MyQ cloud protocol without Android or an emulator. It is preferable to the Superbox fallback when proven, but it still depends on Chamberlain cloud.

## Design

Runtime path:

```text
Broadlink -> localhost Pi3 myq-cloud -> Chamberlain cloud -> G0401
```

The client implements only PKCE/OAuth session refresh, account/device discovery, normalized garage state, explicit open/close, and post-state verification. Public protocol metadata is pinned to an immutable profile in `protocol_profile.py`; rotating credentials remain in `/var/lib/myq/cloud_session.json` and never belong in Git.

The current candidate profile is `android-5.243.1.73243`. A persisted session records its exact `profile_name`. Legacy sessions are migrated only when client ID/app version resolve unambiguously. Future ambiguity fails closed rather than selecting the newest profile.

## Pi3 installation

Code is deployed by Git only. On Pi3 the intended checkout is `/home/pi/Projects/myq`. The installer creates an isolated `.venv`, host-local configuration, and a localhost-only systemd service:

```bash
cd /home/pi/Projects/myq
sudo ./scripts/install_pi3_native_cloud.sh
```

The installer does not invent or copy MyQ credentials. If `/var/lib/myq/cloud_session.json` is absent it installs the service but leaves it stopped. Provision that file separately with mode `0600`, then enable/start the service. `/etc/myq/myq-cloud.env` is root-owned and contains a generated local API key plus the pinned protocol profile.

Useful read-only checks:

```bash
systemctl status myq-cloud --no-pager
curl -s http://127.0.0.1:8766/health
# Protected /garage/status also requires X-API-Key from /etc/myq/myq-cloud.env.
```

Do not expose port 8766 outside localhost. Broadlink runs on the same Pi and should use `http://127.0.0.1:8766` after promotion.

## Promotion gate

Installing or starting this service does **not** make it the production provider. Promotion requires:

1. profile/session loads successfully and reports the expected pinned profile;
2. repeated read-only account/device/status calls identify exactly the intended garage with stable OPEN/CLOSED state;
3. token refresh succeeds without changing protocol profile;
4. a mutation dry run or request-shape test confirms the single explicit endpoint with no alternate mutation fallback;
5. one owner-authorized physical action is sent from known state and post-state converges;
6. service restart and Pi reboot recover status without interactive Android involvement;
7. only then update Broadlink ordering to true-local -> Pi3-native cloud -> Superbox internal SDK -> UI fallback.

A failed/ambiguous mutation is never retried through this service or another provider.
