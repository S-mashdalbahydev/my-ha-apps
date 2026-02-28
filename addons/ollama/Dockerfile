ARG BUILD_FROM
FROM $BUILD_FROM

# Debian packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates zstd \
  && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]