#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

git pull --ff-only

if [ ! -x venv/bin/pip ]; then
    rm -rf venv
    python3 -m venv venv
fi
venv/bin/pip install -q -r requirements.txt

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
fi

$SUDO systemctl restart router-web.service
if systemctl list-unit-files | grep -q '^router-ping.service'; then
    $SUDO systemctl restart router-ping.service
fi

$SUDO systemctl is-active router-web.service && echo "OK: router-web активен"
$SUDO systemctl is-active router-ping.service && echo "OK: router-ping активен"
