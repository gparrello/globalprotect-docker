#!/bin/bash

# This script now uses CDP-based autofill via a Python script.
# It no longer requires xdotool or a visible window.

if [[ -z "${GP_USERNAME}" ]] || [[ -z "${GP_PASSWORD}" ]] || [[ -z "${GP_TOTP_SECRET}" ]]; then
    echo "GP_USERNAME, GP_PASSWORD, and GP_TOTP_SECRET must be set"
    exit 1
fi

export PYTHONUNBUFFERED=1
python3 /autofill-cdp.py
