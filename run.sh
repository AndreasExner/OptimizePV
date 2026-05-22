#!/bin/sh
# OptimizePV Add-on Entry-Point

# HA Supervisor stellt SUPERVISOR_TOKEN bereit
export HA_URL="http://supervisor/core/api"
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export DATA_DB_PATH="/data/optimizepv.db"
export MODELS_DIR="/data/models"
mkdir -p "${MODELS_DIR}"

# Konfiguration aus HA Add-on Options lesen (/data/options.json)
if [ -f /data/options.json ]; then
    export EVCC_URL=$(python -c "import json; print(json.load(open('/data/options.json')).get('evcc_url',''))")
    export COLLECTOR_INTERVAL=$(python -c "import json; print(json.load(open('/data/options.json')).get('collector_interval', 300))")
    export LOG_LEVEL=$(python -c "import json; print(json.load(open('/data/options.json')).get('log_level', 'INFO'))")
fi

echo "OptimizePV startet..."
echo "  HA URL:     ${HA_URL}"
echo "  evcc URL:   ${EVCC_URL}"
echo "  Intervall:  ${COLLECTOR_INTERVAL}s"
echo "  Log-Level:  ${LOG_LEVEL}"
echo "  DB:         ${DATA_DB_PATH}"

# sensors.yaml: addon_config (HA File Editor zugänglich)
# Migration: alte /data/sensors.yaml → /addon_configs/optimizepv/
ADDON_CONFIG_DIR="/addon_configs/optimizepv"
mkdir -p "${ADDON_CONFIG_DIR}"
export SENSORS_YAML_PATH="${ADDON_CONFIG_DIR}/sensors.yaml"

if [ ! -f "${SENSORS_YAML_PATH}" ]; then
    if [ -f /data/sensors.yaml ]; then
        # Migration von alter Position
        mv /data/sensors.yaml "${SENSORS_YAML_PATH}"
        echo "  sensors.yaml migriert: /data/ → ${ADDON_CONFIG_DIR}/"
    else
        cp /app/sensors.yaml.default "${SENSORS_YAML_PATH}"
        echo "  sensors.yaml generiert: ${SENSORS_YAML_PATH}"
    fi
else
    echo "  sensors.yaml: ${SENSORS_YAML_PATH}"
fi

# DB sofort initialisieren (vor Healthcheck)
python -c "from src.data.collector import init_db; init_db()" 2>/dev/null

# Web-UI starten (Hintergrund)
python -m src.web &
echo "  Web-UI:     Port 8099 (Ingress)"

# Forecast-Scheduler starten (Hintergrund, stündlich zur vollen Stunde)
python -c "from src.forecast import run_forecast_scheduler; run_forecast_scheduler()" &
echo "  Forecast:   Stündlich (Hintergrund)"

# Retraining-Scheduler starten (Hintergrund, wöchentlich Montag 00:30 UTC)
python -c "from src.main import run_retrain_scheduler; run_retrain_scheduler()" &
echo "  Retraining: Montag 00:30 UTC (Hintergrund)"

# Collector starten (Vordergrund)
exec python -m src.main --log-level "${LOG_LEVEL}" collect --interval "${COLLECTOR_INTERVAL}"
