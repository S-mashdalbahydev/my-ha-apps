ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM $BUILD_FROM

# Alpine uses apk, not apt-get
RUN apk add --no-cache curl bash

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]