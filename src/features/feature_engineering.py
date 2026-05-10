"""Feature Engineering für PV-Optimierung.

Erstellt Features aus evcc-Energiedaten und Wetterdaten für das
LightGBM-Modell zur PV-Ertragsprognose und Verbrauchsvorhersage.
"""

import pandas as pd
import numpy as np


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


# Feature-Spalten für das Modell (ohne Target und Timestamp)
FEATURE_COLS = [
    # Wetter
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "cloud_cover", "temperature_2m", "wind_speed_10m",
    # Zeit
    "hour", "day_of_year", "month", "weekday", "is_weekend",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    # Lag PV
    "pv_kwh_lag1", "pv_kwh_lag2", "pv_kwh_lag3", "pv_kwh_lag24",
    # Lag Verbrauch
    "consumption_kwh_lag1", "consumption_kwh_lag24",
    # Rolling PV
    "pv_kwh_rmean3", "pv_kwh_rstd3",
    "pv_kwh_rmean6", "pv_kwh_rstd6",
    "pv_kwh_rmean24", "pv_kwh_rstd24",
]
