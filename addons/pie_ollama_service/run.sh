#!/usr/bin/env bash
set -e

MODELS_PATH="/data/models"

# Read user options like home-learning describes (/data/options.json)
if [ -f /data/options.json ] && command -v jq >/dev/null 2>&1; then
  val="$(jq -r '.models_path // empty' /data/options.json)"
  if [ -n "${val}" ] && [ "${val}" != "null" ]; then
    MODELS_PATH="${val}"
  fi
fi

export OLLAMA_HOST="0.0.0.0:11434"
export OLLAMA_MODELS="${MODELS_PATH}"

mkdir -p "${OLLAMA_MODELS}"

echo "[ollama_service] Starting Ollama..."
echo "[ollama_service] OLLAMA_MODELS=${OLLAMA_MODELS}"
echo "[ollama_service] OLLAMA_HOST=${OLLAMA_HOST}"

exec ollama serve
