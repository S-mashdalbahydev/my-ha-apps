ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache \
    python3 \
    py3-pip \
    portaudio-dev \
    gcc \
    python3-dev \
    musl-dev \
    alsa-utils

RUN pip3 install pyaudio --break-system-packages

COPY sound_monitor.py /
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]