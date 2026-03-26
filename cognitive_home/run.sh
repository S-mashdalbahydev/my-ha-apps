#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "RUN.SH STEP 1"
bashio::log.info "RUN.SH STEP 2"

ls -la /app || true
ls -la /app/src || true

bashio::log.info "RUN.SH STEP 3"

python3 --version || true

bashio::log.info "RUN.SH STEP 4"

if [ -f /app/src/main.py ]; then
    bashio::log.info "main.py exists"
else
    bashio::log.info "main.py missing"
fi

bashio::log.info "RUN.SH STEP 5"

python3 -u /app/src/main.py