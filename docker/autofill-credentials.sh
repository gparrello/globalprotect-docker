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

# Find the GlobalProtect Login window
echo "Finding GlobalProtect Login window..."
WIN_ID=$(xdotool search --name "GlobalProtect Login" | head -1)
if [[ -z "$WIN_ID" ]]; then
    echo "ERROR: Could not find GlobalProtect Login window"
    exit 1
fi
echo "Found window: $WIN_ID"

# Helper function to send keys to the window
send_key() {
    xdotool key --window "$WIN_ID" "$@"
}

send_type() {
    xdotool type --window "$WIN_ID" "$@"
}

echo "Step 1: Typing username..."
send_key ctrl+a
send_type "${GP_USERNAME}"
send_key Return

sleep $STEP_DELAY

echo "Step 2: Typing password..."
send_key ctrl+a
send_type "${GP_PASSWORD}"
send_key Return

sleep $STEP_DELAY

echo "Step 3: Selecting MFA method..."
send_key Tab
send_key Tab
send_key Return

sleep $STEP_DELAY

echo "Step 4: Confirming MFA selection..."
send_key Tab
send_key Tab
send_key Return

sleep $STEP_DELAY

echo "Step 5: Typing TOTP code..."
TOTP_CODE=$(oathtool --totp -b "${GP_TOTP_SECRET}")
echo "Generated TOTP: $TOTP_CODE"
send_key ctrl+a
send_type "${TOTP_CODE}"
send_key Return

sleep $STEP_DELAY

echo "Credentials submitted"
