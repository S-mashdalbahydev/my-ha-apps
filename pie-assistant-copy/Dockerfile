ARG BUILD_FROM
FROM $BUILD_FROM

# Python + venv (Debian)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt

# Create venv and install requirements inside it
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
 && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Make the venv python/pip the default
ENV PATH="/opt/venv/bin:$PATH"

COPY app/server.py /app/server.py
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD [ "/run.sh" ]