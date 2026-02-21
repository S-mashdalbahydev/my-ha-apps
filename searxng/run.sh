#!/usr/bin/env bash
set -euo pipefail

# Add-on public config (users can edit it)
PUBLIC_CFG_DIR="/config"

# SearXNG official container paths
SEARXNG_CFG_DIR="/etc/searxng"
SEARXNG_CFG_FILE="${SEARXNG_CFG_DIR}/settings.yml"
SEARXNG_CACHE_DIR="/var/cache/searxng"

# Add-on private persistent dir (always there)
PRIVATE_DATA_DIR="/data"
PRIVATE_CACHE_DIR="${PRIVATE_DATA_DIR}/cache"

mkdir -p "${PUBLIC_CFG_DIR}" "${SEARXNG_CFG_DIR}" "${PRIVATE_CACHE_DIR}"

# 1) Ensure a settings.yml exists in /config (public addon config)
if [ ! -f "${PUBLIC_CFG_DIR}/settings.yml" ]; then
  echo "[searxng-addon] First run: writing default settings.yml to /config"
  cp "/defaults/settings.yml" "${PUBLIC_CFG_DIR}/settings.yml"
fi

# 2) Copy public settings into the real SearXNG config path
cp "${PUBLIC_CFG_DIR}/settings.yml" "${SEARXNG_CFG_FILE}"

# 3) Cache persistence: link /var/cache/searxng -> /data/cache
rm -rf "${SEARXNG_CACHE_DIR}"
ln -s "${PRIVATE_CACHE_DIR}" "${SEARXNG_CACHE_DIR}"

# 4) Read HA add-on options (Supervisor injects them; bashio is not guaranteed here)
# Instead we parse /data/options.json with python (python exists in the official image).
OPTIONS_JSON="/data/options.json"

get_opt() {
  python - <<PY
import json, sys
p="${OPTIONS_JSON}"
k="${1}"
try:
    with open(p,"r",encoding="utf-8") as f:
        o=json.load(f)
    v=o.get(k,"")
    print("" if v is None else v)
except Exception:
    print("")
PY
}

BASE_URL="$(get_opt base_url)"
INSTANCE_NAME="$(get_opt instance_name)"
PUBLIC_INSTANCE="$(get_opt public_instance)"
LIMITER="$(get_opt limiter)"
VALKEY_URL="$(get_opt valkey_url)"
SECRET_OPT="$(get_opt secret)"

# 5) Export SearXNG env vars (official docs)
# server.base_url -> SEARXNG_BASE_URL
# server.secret_key -> SEARXNG_SECRET
# limiter -> SEARXNG_LIMITER
export SEARXNG_SETTINGS_PATH="${SEARXNG_CFG_FILE}"

[ -n "${BASE_URL}" ] && export SEARXNG_BASE_URL="${BASE_URL}"
[ -n "${INSTANCE_NAME}" ] && export SEARXNG_INSTANCE_NAME="${INSTANCE_NAME}"
export SEARXNG_PUBLIC_INSTANCE="${PUBLIC_INSTANCE}"
export SEARXNG_LIMITER="${LIMITER}"

# Use Valkey only if user sets it (optional)
# (SearXNG docs list valkey/redis settings; valkey is the modern naming in SearXNG docs)
[ -n "${VALKEY_URL}" ] && export SEARXNG_VALKEY_URL="${VALKEY_URL}"

# Secret key: SearXNG expects a non-default secret for crypto-related features. :contentReference[oaicite:6]{index=6}
if [ -n "${SECRET_OPT}" ]; then
  export SEARXNG_SECRET="${SECRET_OPT}"
else
  # Generate a stable secret once and store it in /config so it survives rebuilds
  if [ ! -f "${PUBLIC_CFG_DIR}/secret.txt" ]; then
    tr -dc 'a-f0-9' </dev/urandom | head -c 64 > "${PUBLIC_CFG_DIR}/secret.txt"
  fi
  export SEARXNG_SECRET="$(cat "${PUBLIC_CFG_DIR}/secret.txt")"
fi

# 6) Bind host/port.
# Official container uses Granian and supports $GRANIAN_* env vars. :contentReference[oaicite:7]{index=7}
export GRANIAN_HOST="0.0.0.0"
export GRANIAN_PORT="8080"

# 7) Hand off to the official entrypoint (keeps upstream behavior)
# The official image entrypoint path is: /usr/local/searxng/dockerfiles/docker-entrypoint.sh :contentReference[oaicite:8]{index=8}
exec /usr/local/searxng/dockerfiles/docker-entrypoint.sh