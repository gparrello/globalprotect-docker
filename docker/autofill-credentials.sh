#!/bin/bash

export DISPLAY=:99
STEP_DELAY="${STEP_DELAY:-5}"

if [[ -z "${GP_USERNAME}" ]] || [[ -z "${GP_PASSWORD}" ]] || [[ -z "${GP_TOTP_SECRET}" ]]; then
    echo "GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set"
    exit 1
fi

MAX_RETRIES=30
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        echo "Xvfb server is ready"
        break
    fi
    echo "Waiting for Xvfb server... ($i/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

sleep $STEP_DELAY

# Focus the GlobalProtect Login window
echo "Focusing GlobalProtect Login window..."
WIN_ID=$(xdotool search --name "GlobalProtect Login" | head -1)
if [[ -n "$WIN_ID" ]]; then
    xdotool windowactivate --sync "$WIN_ID"
    echo "Window focused: $WIN_ID"
else
    echo "WARNING: Could not find GlobalProtect Login window"
fi

echo "Typing credentials..."
xdotool key ctrl+a
xdotool type "${GP_USERNAME}"
xdotool key Return

sleep $STEP_DELAY

xdotool key ctrl+a
xdotool type "${GP_PASSWORD}"
xdotool key Return

sleep $STEP_DELAY

xdotool key Tab
xdotool key Tab
xdotool key Return

sleep $STEP_DELAY

xdotool key Tab
xdotool key Tab
xdotool key Return

sleep $STEP_DELAY

TOTP_CODE=$(oathtool --totp -b "${GP_TOTP_SECRET}")
xdotool key ctrl+a
xdotool type "${TOTP_CODE}"
xdotool key Return

sleep $STEP_DELAY

echo "Credentials submitted"
