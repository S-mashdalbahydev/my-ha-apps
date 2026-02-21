#!/bin/sh
set -eu

PUBLIC_CFG_DIR="/config"

SEARXNG_CFG_DIR="/etc/searxng"
SEARXNG_CFG_FILE="${SEARXNG_CFG_DIR}/settings.yml"
SEARXNG_CACHE_DIR="/var/cache/searxng"

PRIVATE_DATA_DIR="/data"
PRIVATE_CACHE_DIR="${PRIVATE_DATA_DIR}/cache"

mkdir -p "${PUBLIC_CFG_DIR}" "${SEARXNG_CFG_DIR}" "${PRIVATE_CACHE_DIR}"

# 1) Ensure a settings.yml exists in /config (public add-on config)
if [ ! -f "${PUBLIC_CFG_DIR}/settings.yml" ]; then
  echo "[searxng-addon] First run: writing default settings.yml to /config"
  cp "/defaults/settings.yml" "${PUBLIC_CFG_DIR}/settings.yml"
fi

# 2) Copy public settings into the real SearXNG config path
cp "${PUBLIC_CFG_DIR}/settings.yml" "${SEARXNG_CFG_FILE}"

# 3) Cache persistence: link /var/cache/searxng -> /data/cache
rm -rf "${SEARXNG_CACHE_DIR}"
ln -s "${PRIVATE_CACHE_DIR}" "${SEARXNG_CACHE_DIR}"

OPTIONS_JSON="/data/options.json"

# Pick a Python executable (SearXNG image should have python, but be defensive)
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "[searxng-addon] Error: python/python3 not found in image"
  exit 1
fi

get_opt() {
  key="$1"
  "$PY" - <<PY
import json
p="${OPTIONS_JSON}"
k="${key}"
try:
    with open(p, "r", encoding="utf-8") as f:
        o = json.load(f)
    v = o.get(k, "")
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

# 5) Export SearXNG env vars
export SEARXNG_SETTINGS_PATH="${SEARXNG_CFG_FILE}"

if [ -n "${BASE_URL}" ]; then
  export SEARXNG_BASE_URL="${BASE_URL}"
fi

if [ -n "${INSTANCE_NAME}" ]; then
  export SEARXNG_INSTANCE_NAME="${INSTANCE_NAME}"
fi

# These map to server settings (public_instance, limiter, etc.)
export SEARXNG_PUBLIC_INSTANCE="${PUBLIC_INSTANCE}"
export SEARXNG_LIMITER="${LIMITER}"

if [ -n "${VALKEY_URL}" ]; then
  export SEARXNG_VALKEY_URL="${VALKEY_URL}"
fi

# Secret: persist a generated one unless user provided it
if [ -n "${SECRET_OPT}" ]; then
  export SEARXNG_SECRET="${SECRET_OPT}"
else
  if [ ! -f "${PUBLIC_CFG_DIR}/secret.txt" ]; then
    # 64 hex chars
    tr -dc 'a-f0-9' </dev/urandom | head -c 64 > "${PUBLIC_CFG_DIR}/secret.txt"
  fi
  export SEARXNG_SECRET="$(cat "${PUBLIC_CFG_DIR}/secret.txt")"
fi

# 6) Bind host/port for the app server
export GRANIAN_HOST="0.0.0.0"
export GRANIAN_PORT="8080"

# 7) Hand off to the official entrypoint
exec /usr/local/searxng/dockerfiles/docker-entrypoint.sh