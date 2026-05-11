#!/bin/sh
# OptimizePV Add-on Entry-Point

# HA Supervisor stellt SUPERVISOR_TOKEN bereit
export HA_URL="http://supervisor/core/api"
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export DATA_DB_PATH="/data/optimizepv.db"

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

# Web-UI starten (Hintergrund)
python -m src.web &
echo "  Web-UI:     Port 8099 (Ingress)"

# Collector starten (Vordergrund)
exec python -m src.main --log-level "${LOG_LEVEL}" collect --interval "${COLLECTOR_INTERVAL}"
