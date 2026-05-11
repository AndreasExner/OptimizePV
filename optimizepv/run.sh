#!/usr/bin/with-contenv bashio
# OptimizePV Add-on Entry-Point
# Liest Konfiguration aus HA Add-on Options und startet den Collector.

# --- Konfiguration aus Add-on Options lesen ---
EVCC_URL=$(bashio::config 'evcc_url')
COLLECTOR_INTERVAL=$(bashio::config 'collector_interval')
LOG_LEVEL=$(bashio::config 'log_level')

# HA Supervisor stellt Token und URL automatisch bereit
export HA_URL="http://supervisor/core/api"
export HA_TOKEN="${SUPERVISOR_TOKEN}"
export EVCC_URL
export COLLECTOR_INTERVAL
export LOG_LEVEL
export DATA_DB_PATH="/data/optimizepv.db"

bashio::log.info "OptimizePV startet..."
bashio::log.info "  HA URL:     ${HA_URL}"
bashio::log.info "  evcc URL:   ${EVCC_URL}"
bashio::log.info "  Intervall:  ${COLLECTOR_INTERVAL}s"
bashio::log.info "  Log-Level:  ${LOG_LEVEL}"
bashio::log.info "  DB:         ${DATA_DB_PATH}"

# --- Collector starten ---
exec python -m src.main --log-level "${LOG_LEVEL}" collect --interval "${COLLECTOR_INTERVAL}"
