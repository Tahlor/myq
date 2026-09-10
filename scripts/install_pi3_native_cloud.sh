#!/usr/bin/env bash
set -euo pipefail

ROOT="${MYQ_ROOT:-/home/pi/Projects/myq}"
RUN_USER="${MYQ_RUN_USER:-pi}"
BOOTSTRAP_PYTHON="${MYQ_BOOTSTRAP_PYTHON:-/home/pi/Projects/py311/bin/python}"
ENV_FILE="/etc/myq/myq-cloud.env"
SESSION_FILE="/var/lib/myq/cloud_session.json"
SERVICE_FILE="/etc/systemd/system/myq-cloud.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo; root is used only for systemd and /etc,/var/lib setup." >&2
  exit 2
fi
if [[ ! -d "$ROOT/.git" ]]; then
  echo "Expected Git checkout at $ROOT" >&2
  exit 2
fi
if [[ ! -x "$BOOTSTRAP_PYTHON" ]]; then
  BOOTSTRAP_PYTHON="$(command -v python3)"
fi

install -d -m 0750 -o root -g "$RUN_USER" /etc/myq
install -d -m 0700 -o "$RUN_USER" -g "$RUN_USER" /var/lib/myq

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  runuser -u "$RUN_USER" -- "$BOOTSTRAP_PYTHON" -m venv "$ROOT/.venv"
fi
runuser -u "$RUN_USER" -- "$ROOT/.venv/bin/python" -m pip install -q -e "$ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  api_key="$(openssl rand -hex 24)"
  cat >"$ENV_FILE" <<EOF
MYQ_ENABLE_EXPERIMENTAL_CLOUD=1
MYQ_PROTOCOL_PROFILE=android-5.243.1.73243
MYQ_CLOUD_SESSION=$SESSION_FILE
MYQ_BIND=127.0.0.1
MYQ_PORT=8766
MYQ_API_KEY=$api_key
EOF
  chown root:"$RUN_USER" "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
fi

install -m 0644 "$ROOT/deploy/myq-cloud.service" "$SERVICE_FILE"
systemctl daemon-reload

if [[ -s "$SESSION_FILE" ]]; then
  chown "$RUN_USER":"$RUN_USER" "$SESSION_FILE"
  chmod 0600 "$SESSION_FILE"
  systemctl enable --now myq-cloud.service
  echo "myq-cloud installed and started on 127.0.0.1:8766"
else
  echo "myq-cloud installed but not started: provision $SESSION_FILE first"
fi
