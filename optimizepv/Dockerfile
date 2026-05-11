# HA Add-on Dockerfile für OptimizePV
# Wird vom HA Supervisor gebaut – Build-Context ist das optimizepv/ Verzeichnis.
# src/ und requirements.txt werden beim Build hineinkopiert (siehe DOCS.md).

ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}

WORKDIR /app

# System-Dependencies für LightGBM
RUN apk add --no-cache \
    libgomp \
    libstdc++

# Python-Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Applikation
COPY src/ src/
COPY run.sh /

RUN chmod a+x /run.sh

CMD ["/run.sh"]
