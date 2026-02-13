name: "Ollama Service (Local)"
description: "Runs Ollama locally on Home Assistant OS and stores models in /data."
version: "0.1.0"
slug: "ollama_service"
init: false
startup: services
arch:
  - aarch64
  - amd64

# Keep it INTERNAL by default (recommended).
# If you want to reach Ollama from your LAN, uncomment:
# ports:
#   11434/tcp: 11434

options:
  models_path: "/data/models"
schema:
  models_path: str
