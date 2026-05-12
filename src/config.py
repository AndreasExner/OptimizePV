import os
from pathlib import Path
from dotenv import load_dotenv

# .env laden (falls vorhanden)
load_dotenv()

# Projektpfade
PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_EXPORTS = PROJECT_ROOT / "data" / "exports"
MODELS_DIR = PROJECT_ROOT / "models"

# Eigene Datenbank (Collector)
DATA_DB_PATH = Path(os.getenv("DATA_DB_PATH", str(PROJECT_ROOT / "data" / "optimizepv.db")))

# Collector-Intervalle (Sekunden)
COLLECTOR_INTERVAL = int(os.getenv("COLLECTOR_INTERVAL", "300"))  # 5 Min
COLLECTOR_RETRY_DELAY = int(os.getenv("COLLECTOR_RETRY_DELAY", "30"))  # Retry bei Fehler

# evcc (Steuerung)
EVCC_URL = os.getenv("EVCC_URL", "http://evcc.local:7070")
EVCC_DB_PATH = os.getenv("EVCC_DB_PATH", "/etc/evcc/evcc.db")

# Home Assistant (Datenquelle)
HA_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")

# HA Sensor-Mapping: lokaler Name → HA entity_id
# Alle Sensoren direkt von den Geräten (kein evcc für Messdaten).
# Kann per .env überschrieben werden.
HA_SENSORS = {
    # --- Momentanleistung (W) ---
    "pv_power":         os.getenv("HA_SENSOR_PV_POWER", "sensor.inverter_wirkleistung"),
    "pv_dc_power":      os.getenv("HA_SENSOR_PV_DC_POWER", "sensor.inverter_eingangsleistung"),
    "battery_soc":      os.getenv("HA_SENSOR_BATTERY_SOC", "sensor.battery_1_batterieladung"),
    "battery_power":    os.getenv("HA_SENSOR_BATTERY_POWER", "sensor.battery_1_lade_entladeleistung"),
    "grid_power":       os.getenv("HA_SENSOR_GRID_POWER", "sensor.power_meter_wirkleistung"),
    "wp_power_a":       os.getenv("HA_SENSOR_WP_POWER_A", "sensor.shelly_warmepumpe_channel_a_power"),
    "wp_power_b":       os.getenv("HA_SENSOR_WP_POWER_B", "sensor.shelly_warmepumpe_channel_b_power"),
    "wp_power_c":       os.getenv("HA_SENSOR_WP_POWER_C", "sensor.shelly_warmepumpe_channel_c_power"),
    "ev_power":         os.getenv("HA_SENSOR_EV_POWER", "sensor.goe_111927_nrg_11"),
    # --- Zählerstände (kWh, kumulativ) ---
    "pv_energy_total":        os.getenv("HA_SENSOR_PV_ENERGY", "sensor.inverter_gesamtenergieertrag"),
    "pv_energy_daily":        os.getenv("HA_SENSOR_PV_DAILY", "sensor.inverter_tagesertrag"),
    "grid_import_total":      os.getenv("HA_SENSOR_GRID_IMPORT", "sensor.power_meter_verbrauch"),
    "grid_export_total":      os.getenv("HA_SENSOR_GRID_EXPORT", "sensor.power_meter_exportierte_energie"),
    "battery_charge_total":   os.getenv("HA_SENSOR_BAT_CHARGE", "sensor.battery_gesamtladung"),
    "battery_discharge_total": os.getenv("HA_SENSOR_BAT_DISCHARGE", "sensor.battery_gesamtentladung"),
    "wp_energy_a":            os.getenv("HA_SENSOR_WP_ENERGY_A", "sensor.shelly_warmepumpe_channel_a_energy"),
    "wp_energy_b":            os.getenv("HA_SENSOR_WP_ENERGY_B", "sensor.shelly_warmepumpe_channel_b_energy"),
    "wp_energy_c":            os.getenv("HA_SENSOR_WP_ENERGY_C", "sensor.shelly_warmepumpe_channel_c_energy"),
    "ev_energy_total":        os.getenv("HA_SENSOR_EV_ENERGY", "sensor.goe_111927_eto"),
}

# Standort (für Open-Meteo Wetter-API)
LATITUDE = float(os.getenv("LATITUDE", "51.1657"))
LONGITUDE = float(os.getenv("LONGITUDE", "10.4515"))

# Open-Meteo API
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_HOURLY_PARAMS = [
    "temperature_2m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "cloud_cover",
    "wind_speed_10m",
]

# aWATTar Strompreis-API
AWATTAR_URL = "https://api.awattar.de/v1/marketdata"

# Tibber (optional)
TIBBER_TOKEN = os.getenv("TIBBER_TOKEN", "")
TIBBER_URL = "https://api.tibber.com/v1-beta/gql"

# PV-Anlagen-Spezifikationen (Hardware-Limits)
PV_SPECS = {
    "module_peak_kw": float(os.getenv("PV_MODULE_PEAK_KW", "13.4")),    # kWp Module
    "inverter_max_kw": float(os.getenv("PV_INVERTER_MAX_KW", "10.0")),   # kW Wechselrichter-Limit
    "battery_capacity_kwh": float(os.getenv("BATTERY_CAPACITY_KWH", "10.0")),
    "battery_max_charge_kw": float(os.getenv("BATTERY_MAX_CHARGE_KW", "5.0")),
    "battery_max_discharge_kw": float(os.getenv("BATTERY_MAX_DISCHARGE_KW", "5.0")),
    "battery_min_soc_pct": float(os.getenv("BATTERY_MIN_SOC_PCT", "10")),
}

# ML-Modell Parameter
MODEL_PARAMS = {
    "forecast_hours": 24,        # Vorhersage-Horizont in Stunden
    "training_days": 30,         # Trainings-Daten: letzte N Tage
    "retrain_interval_hours": 24,# Retraining alle N Stunden
    "max_model_size_mb": 20,     # Maximale Modellgröße in MB
}
