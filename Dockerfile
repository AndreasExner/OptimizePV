# Dockerfile für OptimizePV
#
# HA Add-on Build:  BUILD_FROM wird von HA Supervisor gesetzt (Alpine-basiert)
# Standalone Build: docker build --build-arg BUILD_FROM=python:3.12-slim .
#
# Multi-Arch: amd64 (Windows/NUC) und aarch64 (Raspberry Pi 4 / HA OS)

ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM}

WORKDIR /app

# System-Dependencies für LightGBM
# Erkennung: Alpine (apk) vs Debian (apt-get)
RUN if command -v apk > /dev/null 2>&1; then \
        apk add --no-cache libgomp libstdc++; \
    else \
        apt-get update && apt-get install -y --no-install-recommends libgomp1 \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Applikation
COPY src/ src/
COPY run.sh /
RUN chmod a+x /run.sh

# Daten-Verzeichnis
RUN mkdir -p /data

# Environment-Defaults
ENV PYTHONUNBUFFERED=1
ENV DATA_DB_PATH=/data/optimizepv.db
ENV EVCC_URL=http://localhost:7070
ENV HA_URL=http://supervisor/core/api
ENV COLLECTOR_INTERVAL=300

# Healthcheck
HEALTHCHECK --interval=600 --timeout=10 --retries=3 \
    CMD python -c "from pathlib import Path; import time; p=Path('/data/optimizepv.db'); exit(0 if p.exists() and time.time()-p.stat().st_mtime < 900 else 1)"

CMD ["/run.sh"]
