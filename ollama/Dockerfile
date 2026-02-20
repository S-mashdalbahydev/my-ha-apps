ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM $BUILD_FROM

# Install dependencies
RUN apk add --no-cache curl bash zstd

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

COPY run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]