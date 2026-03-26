ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
 && if [ -s /app/requirements.txt ]; then /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt; fi

ENV PATH="/opt/venv/bin:$PATH"

COPY src/ /app/src/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]