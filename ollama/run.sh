#!/usr/bin/with-contenv bashio
set -e

MODEL="$(bashio::config 'model')"

# Store models in /data so they persist
export OLLAMA_MODELS="/data/ollama"

# Start Ollama server in background
ollama serve &
SERVER_PID=$!

sleep 2

# Optional: auto-pull a model on startup if provided
if [ -n "${MODEL}" ] && [ "${MODEL}" != "null" ]; then
  bashio::log.info "Pulling model: ${MODEL}"
  ollama pull "${MODEL}" || true
fi

wait $SERVER_PID