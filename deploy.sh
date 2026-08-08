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

# Привести владельца БД к пользователю сервиса (иначе sqlite не сможет писать)
if [ -f router_monitor.db ]; then
    PING_USER=$($SUDO systemctl show router-ping.service -p User --value 2>/dev/null || true)
    if [ -z "$PING_USER" ] || [ "$PING_USER" = "root" ]; then
        PING_USER=$($SUDO systemctl show router-web.service -p User --value 2>/dev/null || true)
    fi
    if [ -n "$PING_USER" ] && [ "$PING_USER" != "root" ]; then
        $SUDO chown "$PING_USER" router_monitor.db 2>/dev/null || true
        $SUDO chmod 664 router_monitor.db 2>/dev/null || true
    fi
fi

$SUDO systemctl restart router-web.service
if systemctl list-unit-files | grep -q '^router-ping.service'; then
    $SUDO systemctl restart router-ping.service
fi

$SUDO systemctl is-active router-web.service && echo "OK: router-web активен"
$SUDO systemctl is-active router-ping.service && echo "OK: router-ping активен"
