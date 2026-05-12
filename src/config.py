import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# .env laden (falls vorhanden)
load_dotenv()

logger = logging.getLogger(__name__)

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

# HA Sensor-Mapping: Aus sensors.yaml laden (oder Defaults verwenden)
# sensors.yaml liegt in /data/ (HA Add-on) oder im Projekt-Root (Entwicklung)
SENSORS_YAML_PATH = Path(os.getenv("SENSORS_YAML_PATH", ""))

def _load_sensors() -> dict:
    """Lädt das Sensor-Mapping aus sensors.yaml.
    
    Suchpfade (in dieser Reihenfolge):
    1. SENSORS_YAML_PATH (Umgebungsvariable)
    2. /data/sensors.yaml (HA Add-on)
    3. PROJECT_ROOT/sensors.yaml (Entwicklung)
    4. Fallback: sensors.yaml.default
    """
    import yaml

    search_paths = [
        SENSORS_YAML_PATH if SENSORS_YAML_PATH != Path("") else None,
        Path("/data/sensors.yaml"),
        PROJECT_ROOT / "sensors.yaml",
    ]

    for p in search_paths:
        if p and p.is_file():
            logger.info("Sensor-Mapping geladen: %s", p)
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f)

    # Fallback: Default-Datei
    default_path = PROJECT_ROOT / "sensors.yaml.default"
    if default_path.exists():
        logger.info("Sensor-Mapping geladen (Default): %s", default_path)
        with open(default_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    logger.warning("Kein sensors.yaml gefunden – verwende leeres Mapping")
    return {"power": {}, "energy": {}}


def _flatten_sensors(sensor_config: dict) -> dict:
    """Wandelt das gruppierte YAML-Format in ein flaches Dict um.
    
    sensors.yaml:              → HA_SENSORS:
      power:                       "pv_power": "sensor.inverter..."
        pv_ac: "sensor..."         "pv_dc_power": "sensor..."
        pv_dc: "sensor..."         ...
      energy:
        pv_total: "sensor..."
    """
    mapping = {}
    
    power = sensor_config.get("power", {})
    # Power-Mapping: yaml-key → interner Name
    power_map = {
        "pv_ac": "pv_power",
        "pv_dc": "pv_dc_power",
        "battery_soc": "battery_soc",
        "battery_power": "battery_power",
        "grid_power": "grid_power",
        "wp_power_a": "wp_power_a",
        "wp_power_b": "wp_power_b",
        "wp_power_c": "wp_power_c",
        "ev_power": "ev_power",
    }
    for yaml_key, internal_key in power_map.items():
        val = power.get(yaml_key, "")
        if val:
            mapping[internal_key] = val
    
    energy = sensor_config.get("energy", {})
    # Energy-Mapping: yaml-key → interner Name
    energy_map = {
        "pv_total": "pv_energy_total",
        "pv_daily": "pv_energy_daily",
        "grid_import": "grid_import_total",
        "grid_export": "grid_export_total",
        "battery_charge": "battery_charge_total",
        "battery_discharge": "battery_discharge_total",
        "wp_energy_a": "wp_energy_a",
        "wp_energy_b": "wp_energy_b",
        "wp_energy_c": "wp_energy_c",
        "ev_total": "ev_energy_total",
    }
    for yaml_key, internal_key in energy_map.items():
        val = energy.get(yaml_key, "")
        if val:
            mapping[internal_key] = val
    
    return mapping


_sensor_config = _load_sensors()
HA_SENSORS = _flatten_sensors(_sensor_config)

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
