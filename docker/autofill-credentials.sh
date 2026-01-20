#!/bin/bash

VNC_HOST="${VNC_HOST:-localhost}"
VNC_PORT="${VNC_PORT:-8998}"

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

echo "Typing credentials..."
vncdo -s "${VNC_HOST}::${VNC_PORT}" key ctrl-a
vncdo -s "${VNC_HOST}::${VNC_PORT}" type "${GP_PORTAL}"
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 5

vncdo -s "${VNC_HOST}::${VNC_PORT}" key ctrl-a
vncdo -s "${VNC_HOST}::${VNC_PORT}" type "${GP_USERNAME}"
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 5

vncdo -s "${VNC_HOST}::${VNC_PORT}" key ctrl-a
vncdo -s "${VNC_HOST}::${VNC_PORT}" type "${GP_PASSWORD}"
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 5

vncdo -s "${VNC_HOST}::${VNC_PORT}" key tab
vncdo -s "${VNC_HOST}::${VNC_PORT}" key tab
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 3

vncdo -s "${VNC_HOST}::${VNC_PORT}" key tab
vncdo -s "${VNC_HOST}::${VNC_PORT}" key tab
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 3

TOTP_CODE=$(oathtool --totp -b "${GP_TOTP_SECRET}")
vncdo -s "${VNC_HOST}::${VNC_PORT}" key ctrl-a
vncdo -s "${VNC_HOST}::${VNC_PORT}" type "${TOTP_CODE}"
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 5

vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter
vncdo -s "${VNC_HOST}::${VNC_PORT}" key tab
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

sleep 3

vncdo -s "${VNC_HOST}::${VNC_PORT}" key esc
vncdo -s "${VNC_HOST}::${VNC_PORT}" key tab
vncdo -s "${VNC_HOST}::${VNC_PORT}" key enter

echo "Credentials submitted"
