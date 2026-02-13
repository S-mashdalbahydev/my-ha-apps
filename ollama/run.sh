#!/usr/bin/with-contenv bashio
set -e

MODEL="$(bashio::config 'model')"

# Start Ollama server in background
ollama serve &
SERVER_PID=$!

# Give it a moment to come up
sleep 2

# Optional: auto-pull a model on startup if provided in options
if [ -n "${MODEL}" ] && [ "${MODEL}" != "null" ]; then
  bashio::log.info "Pulling model: ${MODEL}"
  ollama pull "${MODEL}" || true
fi

wait $SERVER_PID
