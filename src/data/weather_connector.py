"""Open-Meteo Wetter-Connector.

Liest Wettervorhersagen und historische Wetterdaten für PV-Prognose.
Kostenlos, kein API-Key erforderlich.
"""

from datetime import date, datetime, timedelta
import pandas as pd
import requests

from src.config import (
    LATITUDE,
    LONGITUDE,
    OPENMETEO_ARCHIVE_URL,
    OPENMETEO_FORECAST_URL,
    OPENMETEO_HOURLY_PARAMS,
)


def get_forecast(days: int = 7) -> pd.DataFrame:
    """Liest Wettervorhersage von Open-Meteo.

    Args:
        days: Vorhersage-Horizont in Tagen (max 16)

    Returns:
        DataFrame mit stündlichen Wetterdaten (Strahlung, Temperatur, Wolken)
    """
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(OPENMETEO_HOURLY_PARAMS),
        "timezone": "Europe/Berlin",
        "forecast_days": min(days, 16),
    }

    resp = requests.get(OPENMETEO_FORECAST_URL, params=params, timeout=15)
    resp.raise_for_status()

    data = resp.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"time": "timestamp"})
    return df


def get_historical(
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Liest historische Wetterdaten von Open-Meteo Archive API.

    Args:
        start_date: Start (default: vor 30 Tagen)
        end_date: Ende (default: gestern)

    Returns:
        DataFrame mit stündlichen historischen Wetterdaten
    """
    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ",".join(OPENMETEO_HOURLY_PARAMS),
        "timezone": "Europe/Berlin",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }

    resp = requests.get(OPENMETEO_ARCHIVE_URL, params=params, timeout=30)
    resp.raise_for_status()

    data = resp.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"time": "timestamp"})
    return df
