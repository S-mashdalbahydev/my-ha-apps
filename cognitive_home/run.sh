#!/usr/bin/with-contenv bashio
set -e

export OLLAMA_URL="$(bashio::config 'ollama_url')"
export OLLAMA_MODEL="$(bashio::config 'ollama_model')"
export CHECK_INTERVAL="$(bashio::config 'check_interval_minutes')"
export MIN_OCCURRENCES="$(bashio::config 'min_occurrences')"

bashio::log.info "RUN.SH STEP 1"
bashio::log.info "OLLAMA_URL=${OLLAMA_URL}"
bashio::log.info "OLLAMA_MODEL=${OLLAMA_MODEL}"
bashio::log.info "CHECK_INTERVAL=${CHECK_INTERVAL}"
bashio::log.info "MIN_OCCURRENCES=${MIN_OCCURRENCES}"

ls -la /app || true
ls -la /app/src || true

bashio::log.info "RUN.SH STEP 2"
python3 --version || true

bashio::log.info "RUN.SH STEP 3"

if [ -f /app/src/main.py ]; then
    bashio::log.info "main.py exists"
else
    bashio::log.info "main.py missing"
fi

bashio::log.info "RUN.SH STEP 4"

exec python3 -u /app/src/main.py