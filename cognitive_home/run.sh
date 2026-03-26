#!/usr/bin/with-contenv bashio
set -ex

export OLLAMA_URL="$(bashio::config 'ollama_url')"
export OLLAMA_MODEL="$(bashio::config 'ollama_model')"
export CHECK_INTERVAL="$(bashio::config 'check_interval_minutes')"
export MIN_OCCURRENCES="$(bashio::config 'min_occurrences')"

bashio::log.info "Cognitive Home starting..."
bashio::log.info "OLLAMA_URL=${OLLAMA_URL}"
bashio::log.info "OLLAMA_MODEL=${OLLAMA_MODEL}"

bashio::log.info "Checking filesystem..."
ls -la /app
ls -la /app/src || true

bashio::log.info "Checking Python..."
which python3 || true
python3 --version || true

bashio::log.info "Checking main.py..."
python3 -c "import os; print('/app/src/main.py exists =', os.path.exists('/app/src/main.py'))"
python3 -c "print(open('/app/src/main.py', 'r', encoding='utf-8').read()[:300])" || true

bashio::log.info "Launching app..."
exec python3 -u /app/src/main.py