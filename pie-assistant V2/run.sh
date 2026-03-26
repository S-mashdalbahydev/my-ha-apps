#!/usr/bin/with-contenv bashio
set -e

export SEARX_URL="$(bashio::config 'searx_url')"
export OLLAMA_URL="$(bashio::config 'ollama_url')"
export OLLAMA_EMBED_URL="$(bashio::config 'ollama_embed_url')"
export MODEL="$(bashio::config 'model')"
export EMBED_MODEL="$(bashio::config 'embed_model')"

export SCRAPE_PAGES="$(bashio::config 'scrape_pages')"
export SNIPPET_PAGES="$(bashio::config 'snippet_pages')"
export CHUNK_SIZE="$(bashio::config 'chunk_size')"
export CHUNK_OVERLAP="$(bashio::config 'chunk_overlap')"
export TOP_K_CHUNKS="$(bashio::config 'top_k_chunks')"

export NUM_PREDICT="$(bashio::config 'num_predict')"
export TEMPERATURE="$(bashio::config 'temperature')"
export NUM_CTX="$(bashio::config 'num_ctx')"
export REQUEST_TIMEOUT="$(bashio::config 'request_timeout')"
export EMBED_TIMEOUT="$(bashio::config 'embed_timeout')"
export CHAT_TIMEOUT="$(bashio::config 'chat_timeout')"

bashio::log.info "Pie Assistant starting..."
bashio::log.info "MODEL=${MODEL}  EMBED_MODEL=${EMBED_MODEL}"
bashio::log.info "SEARX_URL=${SEARX_URL}"
bashio::log.info "OLLAMA_URL=${OLLAMA_URL}"

exec gunicorn \
  --workers 2 \
  --bind 0.0.0.0:5055 \
  --timeout 180 \
  --access-logfile - \
  --error-logfile - \
  server:app