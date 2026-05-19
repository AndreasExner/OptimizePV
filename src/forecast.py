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


def create_forecast(hours: int = 24, db_path: Path | None = None) -> pd.DataFrame | None:
    """Erstellt eine Rolling Vorhersage (24h oder 36h).

    Args:
        hours: Vorhersage-Horizont in Stunden (24 oder 36).
        db_path: Pfad zur Collector-DB.

    Returns:
        DataFrame mit stündlichen Vorhersagen, oder None bei Fehler.
        Spalten: timestamp, ghi, pv_dc_forecast, price_eur_mwh,
                 pv_ac_available, battery_action, ev_recommendation, reason
    """
    hours = min(max(hours, 24), 48)  # Clamp auf 24-48
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
    weather = weather[weather["timestamp_local"] >= now].head(hours)

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
            combined = build_lag_features(combined, "home_kwh", lags=[1, 2, 3, 24])
            combined = build_rolling_features(combined, "home_kwh", windows=[3, 6, 24])
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
        logger.warning("Kein trainiertes PV-Modell gefunden")
        forecast_df["pv_dc_forecast"] = 0

    # --- 5b. Verbrauchs-Vorhersage ---
    from src.models.consumption_forecast import ConsumptionForecastModel, CONSUMPTION_FEATURES

    consumption_path = MODELS_DIR / "consumption_forecast.joblib"
    if consumption_path.exists():
        try:
            # Fehlende Verbrauchs-Features auffüllen
            for col in CONSUMPTION_FEATURES:
                if col not in forecast_df.columns:
                    forecast_df[col] = 0
            cons_model = ConsumptionForecastModel.load(consumption_path)
            forecast_df["home_forecast"] = cons_model.predict(forecast_df)
        except Exception as e:
            logger.error("Verbrauchsvorhersage fehlgeschlagen: %s", e)
            forecast_df["home_forecast"] = 0.5  # Fallback
    else:
        logger.warning("Kein Verbrauchsmodell gefunden – verwende 0.5 kWh/h")
        forecast_df["home_forecast"] = 0.5

    # --- 6. Ergebnis zusammenbauen ---
    result = forecast_df[["timestamp", "shortwave_radiation", "pv_dc_forecast", "home_forecast"]].copy()
    result = result.rename(columns={"shortwave_radiation": "ghi"})
    # home_forecast sichern – wird von _add_recommendations gelesen aber nicht dupliziert
    result["home_forecast"] = result["home_forecast"].round(3)

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
    """Fügt Optimierungsempfehlungen hinzu – berücksichtigt Verbrauch."""
    inverter_max = PV_SPECS["inverter_max_kw"]
    bat_max_charge = PV_SPECS["battery_max_charge_kw"]

    recommendations = []
    for _, row in df.iterrows():
        pv_dc = row["pv_dc_forecast"]
        home = row.get("home_forecast", 0.5)
        price = row.get("price_eur_mwh")
        is_negative = row.get("is_negative", False)
        ghi = row.get("ghi", 0)

        # PV auf AC und Batterie aufteilen
        pv_ac = min(pv_dc, inverter_max)
        dc_surplus = max(0, pv_dc - inverter_max)
        bat_charge_dc = min(dc_surplus, bat_max_charge)

        # AC-Überschuss nach Verbrauch
        ac_surplus = max(0, pv_ac - home)
        ac_deficit = max(0, home - pv_ac)

        # Empfehlungen
        if ghi <= 10:  # Nacht
            recommendations.append({
                "pv_ac_available": 0,
                "surplus": 0,
                "battery_action": "Entladen" if ac_deficit > 0.3 else "Halten",
                "ev_recommendation": "Netz" if not is_negative else "Laden (neg. Preis!)",
                "reason": f"Nacht – Verbrauch {home:.1f}kWh",
            })
        elif is_negative:
            recommendations.append({
                "pv_ac_available": round(pv_ac, 1),
                "surplus": round(ac_surplus, 1),
                "battery_action": "Aus Netz laden!",
                "ev_recommendation": "Laden (neg. Preis!)",
                "reason": f"Neg. Preis ({price:.0f} EUR/MWh) – alles laden!",
            })
        elif ac_surplus > 3:
            recommendations.append({
                "pv_ac_available": round(pv_ac, 1),
                "surplus": round(ac_surplus + bat_charge_dc, 1),
                "battery_action": f"Laden ({ac_surplus + bat_charge_dc:.1f}kW verf.)",
                "ev_recommendation": "PV-Laden",
                "reason": f"PV {pv_dc:.1f}kW − Haus {home:.1f}kW = {ac_surplus:.1f}kW Überschuss",
            })
        elif ac_surplus > 0.5:
            recommendations.append({
                "pv_ac_available": round(pv_ac, 1),
                "surplus": round(ac_surplus + bat_charge_dc, 1),
                "battery_action": f"Laden ({ac_surplus + bat_charge_dc:.1f}kW verf.)",
                "ev_recommendation": "Min-PV" if ac_surplus > 1.5 else "Warten",
                "reason": f"PV {pv_dc:.1f}kW − Haus {home:.1f}kW = {ac_surplus:.1f}kW Überschuss",
            })
        elif ac_deficit > 0.5:
            recommendations.append({
                "pv_ac_available": round(pv_ac, 1),
                "surplus": 0,
                "battery_action": f"Entladen ({ac_deficit:.1f}kW Defizit)",
                "ev_recommendation": "Warten",
                "reason": f"Haus {home:.1f}kW > PV {pv_ac:.1f}kW → Batterie",
            })
        else:
            recommendations.append({
                "pv_ac_available": round(pv_ac, 1),
                "surplus": round(ac_surplus, 1),
                "battery_action": "Halten",
                "ev_recommendation": "Warten",
                "reason": f"PV ≈ Verbrauch ({pv_ac:.1f} ≈ {home:.1f}kW)",
            })

    rec_df = pd.DataFrame(recommendations)
    return pd.concat([df.reset_index(drop=True), rec_df], axis=1)
