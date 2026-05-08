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

# evcc
EVCC_URL = os.getenv("EVCC_URL", "http://evcc.local:7070")
EVCC_DB_PATH = os.getenv("EVCC_DB_PATH", "/etc/evcc/evcc.db")

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

# ML-Modell Parameter
MODEL_PARAMS = {
    "forecast_hours": 24,        # Vorhersage-Horizont in Stunden
    "training_days": 30,         # Trainings-Daten: letzte N Tage
    "retrain_interval_hours": 24,# Retraining alle N Stunden
    "max_model_size_mb": 20,     # Maximale Modellgröße in MB
}
