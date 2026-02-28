ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache curl bash ca-certificates zstd

RUN curl -fsSL https://ollama.com/install.sh | sh

ENV OLLAMA_MODELS=/data/models

EXPOSE 11434

CMD ["ollama", "serve"]
