#!/bin/bash
# Wait for Xvfb to be ready
MAX_RETRIES=30
for i in $(seq 1 $MAX_RETRIES); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb is ready"
        break
    fi
    echo "Waiting for Xvfb... ($i/$MAX_RETRIES)"
    sleep 1
done

# Set US keyboard layout for consistent VNC input
setxkbmap -display :99 us

exec x11vnc -display :99 -forever -shared -rfbport 8998 -nopw \
    -noxdamage -noxrecord -noxfixes \
    -norc \
    -wait 50 -defer 50
