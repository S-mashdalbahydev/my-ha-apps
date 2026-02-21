ARG BUILD_FROM
FROM $BUILD_FROM

# Python + deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY app/server.py /app/server.py
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]