#!/bin/bash
# Generate GPClient.conf from environment variables if it doesn't exist or is empty

CONFIG_DIR="/root/.config/com.yuezk.qt"
CONFIG_FILE="$CONFIG_DIR/GPClient.conf"

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Check if config file exists and has content
if [ -s "$CONFIG_FILE" ]; then
    echo "GPClient.conf already exists, skipping generation"
    exit 0
fi

# Check if GP_PORTAL is set
if [ -z "$GP_PORTAL" ]; then
    echo "WARNING: GP_PORTAL not set and no GPClient.conf found"
    echo "Set GP_PORTAL environment variable or mount a config file"
    exit 0
fi

echo "Generating GPClient.conf from environment variables..."

# Generate minimal config with portal
cat > "$CONFIG_FILE" << EOF
[General]
portal=$GP_PORTAL
EOF

# Optionally add selected gateway if specified
if [ -n "$GP_GATEWAY" ]; then
    echo "${GP_PORTAL}_selectedGateway=$GP_GATEWAY" >> "$CONFIG_FILE"
fi

echo "Generated $CONFIG_FILE:"
cat "$CONFIG_FILE"
