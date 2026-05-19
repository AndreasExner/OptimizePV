"""Forecast-Service: Rolling 24h PV-Prognose + Optimierung.

Kombiniert Wettervorhersage, ML-Modell und Strompreise
zu einem stündlichen Optimierungsplan.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DATA_DB_PATH, PV_SPECS, MODELS_DIR
from src.data.weather_connector import get_forecast
from src.data.price_connector import get_awattar_prices
from src.features.feature_engineering import (
    build_time_features, build_lag_features, build_rolling_features,
    load_collector_data, build_hourly_from_collector, merge_weather,
    FEATURE_COLS, TARGET_COL,
)
from src.models.pv_forecast import PVForecastModel

logger = logging.getLogger(__name__)


def create_forecast(db_path: Path | None = None) -> pd.DataFrame | None:
    """Erstellt eine Rolling 24h Vorhersage.

    Returns:
        DataFrame mit stündlichen Vorhersagen, oder None bei Fehler.
        Spalten: timestamp, ghi, pv_dc_forecast, price_eur_mwh,
                 pv_ac_available, battery_action, ev_recommendation, reason
    """
    db_path = db_path or DATA_DB_PATH

    # --- 1. Wettervorhersage (24h) ---
    try:
        weather = get_forecast(days=2)  # 2 Tage, wir nehmen die nächsten 24h
    except Exception as e:
        logger.error("Wettervorhersage fehlgeschlagen: %s", e)
        return None

    # Nur zukünftige Stunden
    now = pd.Timestamp.now(tz="Europe/Berlin").floor("h")
    weather["timestamp_local"] = pd.to_datetime(weather["timestamp"])
    if weather["timestamp_local"].dt.tz is None:
        weather["timestamp_local"] = weather["timestamp_local"].dt.tz_localize("Europe/Berlin")
    weather = weather[weather["timestamp_local"] >= now].head(24)

    if weather.empty:
        logger.warning("Keine Wetterdaten für die nächsten 24h")
        return None

    # --- 2. Strompreise (aWATTar) ---
    try:
        prices = get_awattar_prices()
    except Exception as e:
        logger.warning("Strompreise nicht verfügbar: %s", e)
        prices = pd.DataFrame(columns=["timestamp", "price_eur_mwh", "is_negative"])

    # --- 3. Aktuelle Collector-Daten für Lag-Features ---
    try:
        raw = load_collector_data(hours=48, db_path=db_path)
        if not raw.empty:
            hourly_hist = build_hourly_from_collector(raw)
        else:
            hourly_hist = pd.DataFrame()
    except Exception as e:
        logger.warning("Collector-Daten nicht verfügbar: %s", e)
        hourly_hist = pd.DataFrame()

    # --- 4. Features für Vorhersage bauen ---
    forecast_df = weather[["timestamp", "shortwave_radiation", "direct_radiation",
                           "diffuse_radiation", "cloud_cover", "temperature_2m",
                           "wind_speed_10m"]].copy()
    forecast_df = forecast_df.rename(columns={"timestamp": "timestamp"})

    # Timestamp nach UTC für Merge
    if forecast_df["timestamp"].dt.tz is None:
        forecast_df["timestamp"] = forecast_df["timestamp"].dt.tz_localize("Europe/Berlin").dt.tz_convert("UTC")
    else:
        forecast_df["timestamp"] = forecast_df["timestamp"].dt.tz_convert("UTC")

    # Zeitfeatures
    forecast_df = build_time_features(forecast_df, "timestamp")

    # Lag-Features aus historischen Daten
    if not hourly_hist.empty and TARGET_COL in hourly_hist.columns:
        # Letzte bekannte Werte für Lags
        hist = hourly_hist[["timestamp", TARGET_COL]].copy()
        if "home_kwh" in hourly_hist.columns:
            hist["home_kwh"] = hourly_hist["home_kwh"]

        combined = pd.concat([hist, forecast_df], ignore_index=True)
        combined = combined.sort_values("timestamp").reset_index(drop=True)
        combined = build_lag_features(combined, TARGET_COL, lags=[1, 2, 3, 24])
        if "home_kwh" in combined.columns:
            combined = build_lag_features(combined, "home_kwh", lags=[1, 24])
        combined = build_rolling_features(combined, TARGET_COL, windows=[3, 6, 24])

        # Nur die Forecast-Zeilen behalten
        forecast_df = combined[combined["timestamp"].isin(forecast_df["timestamp"])].copy()
    else:
        # Keine historischen Daten – Lag-Features auf 0
        for col in FEATURE_COLS:
            if col not in forecast_df.columns:
                forecast_df[col] = 0

    # Fehlende Features mit 0 auffüllen
    for col in FEATURE_COLS:
        if col not in forecast_df.columns:
            forecast_df[col] = 0

    # --- 5. ML-Vorhersage ---
    model_path = MODELS_DIR / "pv_forecast.joblib"
    if model_path.exists():
        try:
            model = PVForecastModel.load(model_path)
            forecast_df["pv_dc_forecast"] = model.predict(forecast_df)
        except Exception as e:
            logger.error("Modell-Vorhersage fehlgeschlagen: %s", e)
            forecast_df["pv_dc_forecast"] = 0
    else:
        logger.warning("Kein trainiertes Modell gefunden")
        forecast_df["pv_dc_forecast"] = 0

    # --- 6. Ergebnis zusammenbauen ---
    result = forecast_df[["timestamp", "shortwave_radiation", "pv_dc_forecast"]].copy()
    result = result.rename(columns={"shortwave_radiation": "ghi"})

    # Preise mergen (nach Stunde)
    if not prices.empty:
        prices_h = prices[["timestamp", "price_eur_mwh", "is_negative"]].copy()
        prices_h["timestamp"] = prices_h["timestamp"].dt.tz_convert("UTC").dt.floor("h")
        result = result.merge(prices_h, on="timestamp", how="left")
    if "price_eur_mwh" not in result.columns:
        result["price_eur_mwh"] = None
        result["is_negative"] = False

    # --- 7. Optimierungsempfehlungen ---
    result = _add_recommendations(result)

    # Timestamp nach Europe/Berlin für Anzeige
    result["timestamp"] = result["timestamp"].dt.tz_convert("Europe/Berlin")

    logger.info("Forecast erstellt: %d Stunden, PV DC Ø %.1f kWh/h",
                len(result), result["pv_dc_forecast"].mean())

    return result.reset_index(drop=True)


def _add_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    """Fügt Optimierungsempfehlungen hinzu."""
    inverter_max = PV_SPECS["inverter_max_kw"]
    bat_max_charge = PV_SPECS["battery_max_charge_kw"]

    recommendations = []
    for _, row in df.iterrows():
        pv_dc = row["pv_dc_forecast"]
        price = row.get("price_eur_mwh")
        is_negative = row.get("is_negative", False)
        ghi = row.get("ghi", 0)

        # PV auf AC und Batterie aufteilen
        pv_ac = min(pv_dc, inverter_max)
        dc_surplus = max(0, pv_dc - inverter_max)
        bat_charge_potential = min(dc_surplus, bat_max_charge)

        # Empfehlungen
        if ghi <= 10:  # Nacht
            recommendations.append({
                "pv_ac_available": 0,
                "battery_action": "Entladen (Nacht)",
                "ev_recommendation": "Netz" if not is_negative else "Laden (neg. Preis!)",
                "reason": "Kein PV-Ertrag",
            })
        elif is_negative:
            recommendations.append({
                "pv_ac_available": pv_ac,
                "battery_action": "Aus Netz laden!",
                "ev_recommendation": "Laden (neg. Preis!)",
                "reason": f"Negativer Strompreis ({price:.0f} EUR/MWh)",
            })
        elif pv_dc > inverter_max:
            recommendations.append({
                "pv_ac_available": pv_ac,
                "battery_action": f"DC-Laden ({bat_charge_potential:.1f}kW)",
                "ev_recommendation": "PV-Laden" if pv_ac > 3 else "Warten",
                "reason": f"PV-Überschuss: {pv_dc:.1f}kW > WR {inverter_max}kW",
            })
        elif pv_ac > 2:
            recommendations.append({
                "pv_ac_available": pv_ac,
                "battery_action": "Laden (PV-Überschuss)",
                "ev_recommendation": "PV-Laden" if pv_ac > 4 else "Min-PV",
                "reason": f"PV verfügbar: {pv_ac:.1f}kW",
            })
        else:
            recommendations.append({
                "pv_ac_available": pv_ac,
                "battery_action": "Halten",
                "ev_recommendation": "Warten",
                "reason": f"Wenig PV ({pv_ac:.1f}kW)",
            })

    rec_df = pd.DataFrame(recommendations)
    return pd.concat([df.reset_index(drop=True), rec_df], axis=1)
