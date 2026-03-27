#!/usr/bin/with-contenv bashio
set -e

export OLLAMA_URL="$(bashio::config 'ollama_url')"
export OLLAMA_MODEL="$(bashio::config 'ollama_model')"
export CHECK_INTERVAL="$(bashio::config 'check_interval_minutes')"
export MIN_OCCURRENCES="$(bashio::config 'min_occurrences')"
export CONFIDENCE_THRESHOLD="$(bashio::config 'confidence_threshold')"
export LOOKAHEAD_MINUTES="$(bashio::config 'lookahead_minutes')"
export FORCE_SUGGESTION_MODE="$(bashio::config 'force_suggestion_mode')"
export DISABLE_WEEKDAY_CHECK="$(bashio::config 'disable_weekday_check')"

bashio::log.info "Cognitive Home starting..."
bashio::log.info "CHECK_INTERVAL=${CHECK_INTERVAL}"
bashio::log.info "MIN_OCCURRENCES=${MIN_OCCURRENCES}"
bashio::log.info "CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD}"
bashio::log.info "LOOKAHEAD_MINUTES=${LOOKAHEAD_MINUTES}"
bashio::log.info "FORCE_SUGGESTION_MODE=${FORCE_SUGGESTION_MODE}"
bashio::log.info "DISABLE_WEEKDAY_CHECK=${DISABLE_WEEKDAY_CHECK}"

exec python3 -u /app/src/main.py