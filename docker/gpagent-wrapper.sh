#!/bin/bash

CONFIG_DIR="/root/.config/com.yuezk.qt"
CONFIG_FILE="${CONFIG_DIR}/GPClient.conf"

mkdir -p "${CONFIG_DIR}"

if [[ -n "${GP_PORTAL}" ]] || [[ -n "${GP_USERNAME}" ]] || [[ -n "${GP_PASSWORD}" ]]; then
    {
        echo "[General]"
        [[ -n "${GP_PORTAL}" ]] && echo "portal=${GP_PORTAL}"
        [[ -n "${GP_USERNAME}" ]] && echo "username=${GP_USERNAME}"
        [[ -n "${GP_PASSWORD}" ]] && echo "password=${GP_PASSWORD}"
    } > "${CONFIG_FILE}"
fi

exec /usr/bin/gpagent "$@"
