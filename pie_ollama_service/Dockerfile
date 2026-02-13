FROM ollama/ollama:latest

# Tools for reading /data/options.json
RUN apt-get update && apt-get install -y jq && rm -rf /var/lib/apt/lists/*

COPY run.sh /run.sh
RUN chmod +x /run.sh

# Ollama API default port
EXPOSE 11434

CMD ["/run.sh"]
