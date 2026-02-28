#!/usr/bin/with-contenv bashio
set -e

export SEARX_URL="$(bashio::config 'searx_url')"
export OLLAMA_URL="$(bashio::config 'ollama_url')"
export MODEL="$(bashio::config 'model')"

export MAX_RESULTS="$(bashio::config 'max_results')"
export CTX_CHAR_LIMIT="$(bashio::config 'ctx_char_limit')"

export TEMPERATURE="$(bashio::config 'temperature')"
export NUM_PREDICT="$(bashio::config 'num_predict')"
export NUM_CTX="$(bashio::config 'num_ctx')"

bashio::log.info "Agent starting..."
bashio::log.info "SEARX_URL=${SEARX_URL}"
bashio::log.info "OLLAMA_URL=${OLLAMA_URL}"
bashio::log.info "MODEL=${MODEL}"

exec gunicorn \
  --workers 2 \
  --bind 0.0.0.0:5055 \
  --access-logfile - \
  --error-logfile - \
  server:app