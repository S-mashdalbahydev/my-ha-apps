ARG BUILD_FROM
FROM $BUILD_FROM

# Install curl if not present, then install Ollama
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

COPY run.sh /
RUN chmod +x /run.sh

CMD [ "/run.sh" ]