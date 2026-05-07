"""Home Assistant Daten-Connector.

Liest historische Sensordaten über die HA REST API.
"""

from datetime import datetime, timedelta
import pandas as pd
import requests

from src.config import HA_URL, HA_TOKEN, HA_SENSORS


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def get_sensor_history(
    entity_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Liest die Historie eines Sensors aus Home Assistant.

    Args:
        entity_id: z.B. "sensor.inverter_input_power"
        start: Startzeit (default: vor 7 Tagen)
        end: Endzeit (default: jetzt)

    Returns:
        DataFrame mit Spalten ['timestamp', 'state']
    """
    if start is None:
        start = datetime.now() - timedelta(days=7)
    if end is None:
        end = datetime.now()

    url = f"{HA_URL}/api/history/period/{start.isoformat()}"
    params = {
        "filter_entity_id": entity_id,
        "end_time": end.isoformat(),
        "minimal_response": "",
        "significant_changes_only": "",
    }

    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    if not data or not data[0]:
        return pd.DataFrame(columns=["timestamp", "state"])

    records = [
        {"timestamp": entry["last_changed"], "state": entry["state"]}
        for entry in data[0]
        if entry["state"] not in ("unavailable", "unknown")
    ]

    df = pd.DataFrame(records)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["state"] = pd.to_numeric(df["state"], errors="coerce")
        df = df.dropna(subset=["state"])
    return df


def get_all_sensors(
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Liest alle konfigurierten Sensoren und kombiniert sie in einen DataFrame.

    Returns:
        DataFrame mit Spalten ['timestamp', 'pv_power', 'battery_soc', ...]
    """
    dfs = {}
    for name, entity_id in HA_SENSORS.items():
        df = get_sensor_history(entity_id, start, end)
        if not df.empty:
            df = df.set_index("timestamp").rename(columns={"state": name})
            dfs[name] = df

    if not dfs:
        return pd.DataFrame()

    # Alle Sensoren auf gemeinsamen Zeitindex zusammenführen (stündlich)
    combined = pd.concat(dfs.values(), axis=1)
    combined = combined.resample("1h").mean()
    return combined.reset_index()
