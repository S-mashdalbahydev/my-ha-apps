#!/usr/bin/with-contenv bashio
set -e

# Read config exactly like pie-assistant does
export OLLAMA_URL="$(bashio::config 'ollama_url')"
export OLLAMA_MODEL="$(bashio::config 'ollama_model')"
export CHECK_INTERVAL="$(bashio::config 'check_interval_minutes')"
export MIN_OCCURRENCES="$(bashio::config 'min_occurrences')"

bashio::log.info "Cognitive Home starting..."
bashio::log.info "OLLAMA_URL=${OLLAMA_URL}"
bashio::log.info "OLLAMA_MODEL=${OLLAMA_MODEL}"

exec python3 /app/src/main.py
```

### `requirements.txt`
```
requests
schedule
websocket-client