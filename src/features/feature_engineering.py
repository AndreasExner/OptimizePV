"""Feature Engineering für PV-Optimierung.

Erstellt Features aus Collector-Daten (eigene SQLite-DB) und Wetterdaten
für das LightGBM-Modell zur PV-Modulleistungsprognose.

Target: pv_module_power (W) = inverter_wirkleistung + max(0, battery_charge_power)
Dies ist die tatsächliche DC-Leistung der PV-Module (bis 13,4 kWp),
NICHT die WR-begrenzte AC-Ausgangsleistung (max 10 kW).
"""

import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np

from src.config import DATA_DB_PATH, PV_SPECS


def build_time_features(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """Erzeugt Zeitfeatures aus einer Timestamp-Spalte.

    Args:
        df: DataFrame mit Timestamp-Spalte.
        timestamp_col: Name der Timestamp-Spalte.

    Returns:
        DataFrame mit zusätzlichen Zeitfeatures.
    """
    df = df.copy()
    ts = df[timestamp_col]
    df["hour"] = ts.dt.hour
    df["day_of_year"] = ts.dt.dayofyear
    df["month"] = ts.dt.month
    df["weekday"] = ts.dt.dayofweek  # 0=Mo, 6=So
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    # Zyklische Kodierung für Stunde und Tag
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["doy_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["doy_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)
    return df


def build_lag_features(df: pd.DataFrame, target_col: str, lags: list[int] | None = None) -> pd.DataFrame:
    """Erzeugt Lag-Features für eine Zielvariable.

    Args:
        df: DataFrame, nach Zeitstempel sortiert.
        target_col: Spaltenname der Zielvariable.
        lags: Liste von Lag-Schritten (in Zeilen). Default: [1, 4, 24, 48, 96]
              (bei Stundendaten: 1h, 4h, 24h, 48h; bei 15min: entsprechend)

    Returns:
        DataFrame mit zusätzlichen Lag-Spalten.
    """
    if lags is None:
        lags = [1, 4, 24, 48, 96]

    df = df.copy()
    for lag in lags:
        df[f"{target_col}_lag{lag}"] = df[target_col].shift(lag)
    return df


def build_rolling_features(
    df: pd.DataFrame,
    target_col: str,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """Erzeugt Rolling-Statistiken für eine Zielvariable.

    Args:
        df: DataFrame, nach Zeitstempel sortiert.
        target_col: Spaltenname der Zielvariable.
        windows: Fenstergrößen in Zeilen. Default: [4, 12, 24]

    Returns:
        DataFrame mit Rolling-Mean und Rolling-Std.
    """
    if windows is None:
        windows = [4, 12, 24]

    df = df.copy()
    for w in windows:
        df[f"{target_col}_rmean{w}"] = df[target_col].rolling(w, min_periods=1).mean()
        df[f"{target_col}_rstd{w}"] = df[target_col].rolling(w, min_periods=1).std().fillna(0)
    return df


def reconstruct_pv_hourly(
    home: pd.DataFrame,
    grid: pd.DataFrame,
) -> pd.DataFrame:
    """Rekonstruiert stündliche PV-Erzeugung aus Home- und Grid-Daten.

    PV ≈ home_import + grid_export - grid_import

    Beide DataFrames müssen 'start', 'import', 'export' enthalten.
    Nur der Überlappungszeitraum wird zurückgegeben.

    Returns:
        DataFrame mit Spalten ['timestamp', 'pv_kwh', 'consumption_kwh',
        'grid_import_kwh', 'grid_export_kwh'] in stündlicher Auflösung.
    """
    # Auf Stunde aggregieren
    home = home.copy()
    home["hour_start"] = home["start"].dt.floor("h")
    home_h = home.groupby("hour_start").agg(
        consumption_kwh=pd.NamedAgg(column="import", aggfunc="sum"),
    ).reset_index()

    grid = grid.copy()
    grid["hour_start"] = grid["start"].dt.floor("h")
    grid_h = grid.groupby("hour_start").agg(
        grid_import_kwh=pd.NamedAgg(column="import", aggfunc="sum"),
        grid_export_kwh=pd.NamedAgg(column="export", aggfunc="sum"),
    ).reset_index()

    # Zusammenführen (nur Überlappung)
    merged = pd.merge(home_h, grid_h, on="hour_start", how="inner")
    merged["pv_kwh"] = (
        merged["consumption_kwh"]
        + merged["grid_export_kwh"]
        - merged["grid_import_kwh"]
    ).clip(lower=0)  # PV kann nicht negativ sein

    merged = merged.rename(columns={"hour_start": "timestamp"})
    return merged[["timestamp", "pv_kwh", "consumption_kwh", "grid_import_kwh", "grid_export_kwh"]]


def merge_weather(energy_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """Merged stündliche Energiedaten mit Wetterdaten.

    Args:
        energy_df: DataFrame mit 'timestamp' (UTC, tz-aware).
        weather_df: DataFrame mit 'timestamp' (tz-naive, Europe/Berlin).

    Returns:
        Gemergter DataFrame auf Stundenbasis.
    """
    weather = weather_df.copy()
    # Wetter-Timestamps nach UTC konvertieren für den Merge
    if weather["timestamp"].dt.tz is None:
        weather["timestamp"] = pd.to_datetime(weather["timestamp"]).dt.tz_localize("Europe/Berlin").dt.tz_convert("UTC")
    else:
        weather["timestamp"] = weather["timestamp"].dt.tz_convert("UTC")

    # Auf Stunde runden für sauberen Merge
    energy = energy_df.copy()
    energy["timestamp"] = energy["timestamp"].dt.floor("h")
    weather["timestamp"] = weather["timestamp"].dt.floor("h")

    merged = pd.merge(energy, weather, on="timestamp", how="inner")
    return merged


def build_training_dataset(
    home: pd.DataFrame,
    grid: pd.DataFrame,
    weather: pd.DataFrame,
    target: str = "pv_kwh",
) -> pd.DataFrame:
    """Baut den vollständigen Trainingsdatensatz.

    Kombiniert PV-Rekonstruktion, Wetter-Merge und alle Features.

    Returns:
        Feature-DataFrame bereit für Training (ohne NaN-Zeilen durch Lags).
    """
    # 1. PV rekonstruieren (stündlich)
    energy = reconstruct_pv_hourly(home, grid)

    # 2. Wetter mergen
    df = merge_weather(energy, weather)

    # 3. Zeitfeatures
    df = build_time_features(df, "timestamp")

    # 4. Lag-Features
    lag_steps = [1, 2, 3, 24]  # 1h, 2h, 3h, gleiche Stunde gestern
    df = build_lag_features(df, target, lags=lag_steps)
    df = build_lag_features(df, "consumption_kwh", lags=[1, 24])

    # 5. Rolling-Features
    df = build_rolling_features(df, target, windows=[3, 6, 24])

    # 6. NaN-Zeilen durch Lags entfernen
    df = df.dropna().reset_index(drop=True)

    return df


# Feature-Spalten für das Modell (Target: pv_dc_kwh)
FEATURE_COLS = [
    # Wetter
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "cloud_cover", "temperature_2m", "wind_speed_10m",
    # Zeit
    "hour", "day_of_year", "month", "weekday", "is_weekend",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    # Lag PV DC
    "pv_dc_kwh_lag1", "pv_dc_kwh_lag2", "pv_dc_kwh_lag3",
    "pv_dc_kwh_lag24",
    # Lag Verbrauch
    "home_kwh_lag1", "home_kwh_lag24",
    # Rolling PV DC
    "pv_dc_kwh_rmean3", "pv_dc_kwh_rstd3",
    "pv_dc_kwh_rmean6", "pv_dc_kwh_rstd6",
    "pv_dc_kwh_rmean24", "pv_dc_kwh_rstd24",
]

TARGET_COL = "pv_dc_kwh"


# ---------------------------------------------------------------------------
# Collector-DB → Stündliche Aggregation
# ---------------------------------------------------------------------------


def load_collector_data(hours: int | None = None, db_path: Path | None = None) -> pd.DataFrame:
    """Liest Rohdaten aus der Collector-DB.

    Args:
        hours: Letzte N Stunden. None = alle Daten.
        db_path: Pfad zur DB.

    Returns:
        DataFrame mit allen Messwerten und Timestamps.
    """
    db_path = db_path or DATA_DB_PATH
    if not db_path.exists():
        return pd.DataFrame()

    with sqlite3.connect(str(db_path)) as conn:
        if hours:
            query = f"SELECT * FROM measurements WHERE timestamp >= datetime('now', '-{hours} hours') ORDER BY timestamp"
        else:
            query = "SELECT * FROM measurements ORDER BY timestamp"
        df = pd.read_sql_query(query, conn)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def build_hourly_from_collector(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregiert 5-Min-Collector-Daten zu stündlichen Werten.

    Leistungswerte werden gemittelt, Zählerstände als Differenz berechnet.

    Berechnet pv_module_power = pv_power + max(0, battery_power)
    (Batterie-Ladung kommt von den Modulen, muss addiert werden)

    Returns:
        DataFrame mit stündlichen Werten, inkl. pv_module_kwh als Target.
    """
    df = df.copy()

    # pv_module_power berechnen: Modulleistung = WR-Ausgang + Batterie-Ladung
    # battery_power: positiv = Laden (kommt von Modulen)
    battery_charge = df["battery_power"].clip(lower=0)  # Nur Lade-Anteil
    df["pv_module_power"] = df["pv_power"].fillna(0) + battery_charge.fillna(0)
    # Begrenzen auf Modul-Peak (physikalisch nicht möglich)
    df["pv_module_power"] = df["pv_module_power"].clip(upper=PV_SPECS["module_peak_kw"] * 1000)

    df["hour_start"] = df["timestamp"].dt.floor("h")

    # --- Leistung: Durchschnitt pro Stunde → kW → kWh (da 1h Intervall) ---
    power_cols = ["pv_power", "pv_dc_power", "pv_module_power", "battery_power", "grid_power",
                  "home_power", "wp_power", "ev_power"]
    agg_dict = {col: "mean" for col in power_cols if col in df.columns}
    agg_dict["battery_soc"] = "mean"

    hourly = df.groupby("hour_start").agg(agg_dict).reset_index()

    # W → kWh (Durchschnittsleistung * 1h / 1000)
    for col in power_cols:
        if col in hourly.columns:
            kwh_col = col.replace("_power", "_kwh")
            hourly[kwh_col] = hourly[col] / 1000.0

    # --- Zählerstände: Differenz (Ende - Anfang) pro Stunde ---
    meter_cols = ["pv_energy_total", "grid_import_total", "grid_export_total",
                  "battery_charge_total", "battery_discharge_total",
                  "wp_energy_total", "ev_energy_total"]

    for col in meter_cols:
        if col in df.columns and df[col].notna().any():
            meter_hourly = df.groupby("hour_start")[col].agg(["first", "last"])
            meter_hourly[f"{col}_delta"] = meter_hourly["last"] - meter_hourly["first"]
            hourly = hourly.merge(
                meter_hourly[[f"{col}_delta"]],
                left_on="hour_start", right_index=True, how="left",
            )

    # Wenn Zählerstand-Differenz für PV verfügbar, als exakten Wert nutzen
    if "pv_energy_total_delta" in hourly.columns:
        # pv_module_kwh aus Zähler: PV-Ertrag + Batterie-Ladung
        # Der PV-Zähler zählt nur AC-Ausgang, nicht DC-Batterie
        # Also: module_kwh = pv_energy_delta + battery_charge_delta
        if "battery_charge_total_delta" in hourly.columns:
            hourly["pv_module_kwh_meter"] = (
                hourly["pv_energy_total_delta"].fillna(0) +
                hourly["battery_charge_total_delta"].fillna(0)
            )

    hourly = hourly.rename(columns={"hour_start": "timestamp"})

    # Nur vollständige Stunden (min. 6 Samples bei 5-Min-Intervall)
    sample_count = df.groupby(df["timestamp"].dt.floor("h")).size()
    sample_count.index.name = "timestamp"
    hourly = hourly.merge(sample_count.rename("n_samples"), on="timestamp", how="left")
    hourly = hourly[hourly["n_samples"] >= 6].drop(columns=["n_samples"])

    return hourly.reset_index(drop=True)


def build_training_from_collector(
    weather: pd.DataFrame,
    db_path: Path | None = None,
    target: str = TARGET_COL,
) -> pd.DataFrame:
    """Baut Trainingsdatensatz aus Collector-DB + Wetterdaten.

    Args:
        weather: Open-Meteo Wetterdaten (stündlich).
        db_path: Pfad zur Collector-DB.
        target: Target-Spalte (default: pv_module_kwh).

    Returns:
        Feature-DataFrame bereit für Training.
    """
    # 1. Collector-Daten laden und stündlich aggregieren
    raw = load_collector_data(db_path=db_path)
    if raw.empty:
        raise ValueError("Keine Collector-Daten vorhanden. Collector muss erst Daten sammeln.")

    hourly = build_hourly_from_collector(raw)
    if hourly.empty:
        raise ValueError("Nicht genug Daten für stündliche Aggregation.")

    # 2. Wetter mergen
    df = merge_weather(hourly, weather)

    # 3. Zeitfeatures
    df = build_time_features(df, "timestamp")

    # 4. Lag-Features
    df = build_lag_features(df, target, lags=[1, 2, 3, 24])
    if "home_kwh" in df.columns:
        df = build_lag_features(df, "home_kwh", lags=[1, 24])

    # 5. Rolling-Features
    df = build_rolling_features(df, target, windows=[3, 6, 24])

    # 6. NaN-Zeilen durch Lags entfernen
    df = df.dropna(subset=[c for c in df.columns if "lag" in c]).reset_index(drop=True)

    return df
