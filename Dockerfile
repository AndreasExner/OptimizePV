# Multi-Arch Dockerfile für OptimizePV
# Läuft auf amd64 (Windows/NUC) und arm64 (Raspberry Pi 4 / HA OS)

FROM python:3.12-slim AS builder

WORKDIR /app

# System-Dependencies für LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime Stage ---
FROM python:3.12-slim

WORKDIR /app

# LightGBM braucht libgomp
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python-Pakete aus Builder kopieren
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Applikation kopieren
COPY src/ src/

# Daten- und Modell-Verzeichnisse (werden als Volumes gemountet)
RUN mkdir -p /data /config

# Environment-Defaults
ENV PYTHONUNBUFFERED=1
ENV DATA_DB_PATH=/data/optimizepv.db
ENV EVCC_URL=http://localhost:7070
ENV HA_URL=http://supervisor/core
ENV COLLECTOR_INTERVAL=300

# Healthcheck: Prüft ob die DB existiert und kürzlich beschrieben wurde
HEALTHCHECK --interval=600 --timeout=10 --retries=3 \
    CMD python -c "from pathlib import Path; import time; p=Path('/data/optimizepv.db'); exit(0 if p.exists() and time.time()-p.stat().st_mtime < 900 else 1)"

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["collect"]
