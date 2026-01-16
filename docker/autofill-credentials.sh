#!/bin/bash

VNC_HOST="${VNC_HOST:-localhost}"
VNC_PORT="${VNC_PORT:-8998}"
CDP_PORT="${QTWEBENGINE_REMOTE_DEBUGGING:-9222}"

if [[ -z "${GP_PORTAL}" ]] || [[ -z "${GP_USERNAME}" ]] || [[ -z "${GP_PASSWORD}" ]] || [[ -z "${GP_TOTP_SECRET}" ]]; then
    echo "GP_PORTAL, GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set"
    exit 1
fi

MAX_RETRIES=30
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    if nc -z "$VNC_HOST" "$VNC_PORT" 2>/dev/null; then
        echo "VNC server is ready"
        break
    fi
    echo "Waiting for VNC server... ($i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

sleep 5

echo "Step 1: Filling portal URL via VNC..."
vncdo -s "${VNC_HOST}::${VNC_PORT}" key ctrl-a
vncdo -s "${VNC_HOST}::${VNC_PORT}" type "${GP_PORTAL}"
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

echo "Waiting for SAML login window and CDP server..."
for i in $(seq 1 $MAX_RETRIES); do
    if curl -s "http://127.0.0.1:${CDP_PORT}/json/version" > /dev/null 2>&1; then
        echo "CDP server is ready"
        break
    fi
    echo "Waiting for CDP server... ($i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

sleep 3

echo "Step 2: Running Playwright for OneLogin authentication..."
cd /app && node autofill-credentials.js

echo "Autofill complete"
