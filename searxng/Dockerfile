FROM docker.io/searxng/searxng:latest

COPY run.sh /run.sh
COPY defaults/ /defaults/
RUN chmod +x /run.sh

ENTRYPOINT ["/run.sh"]