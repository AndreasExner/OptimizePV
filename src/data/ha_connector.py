"""Home Assistant Daten-Connector.

Liest Sensordaten aus Home Assistant über die REST API.
Wird als primäre Datenquelle für PV, Batterie, Grid und Verbrauch genutzt.
evcc bleibt für die Steuerung zuständig.

HA liefert bessere Daten als evcc:
- Direkte PV-Erzeugung vom Wechselrichter (nicht rekonstruiert)
- Vollständiger Hausverbrauch (inkl. aller Verbraucher)
- Individuelle Sensoren für jeden Messpunkt
- History über den HA Recorder (default 10 Tage)
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import requests

from src.config import HA_URL, HA_TOKEN

logger = logging.getLogger(__name__)


def _headers() -> dict:
    """Erstellt Auth-Header für HA API."""
    return {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    """Baut die API-Base-URL.

    HA Supervisor: HA_URL = 'http://supervisor/core/api' (enthält /api)
    Direkt:        HA_URL = 'http://192.168.x.x:8123'   (/api wird angehängt)
    """
    if HA_URL.rstrip("/").endswith("/api"):
        return HA_URL.rstrip("/")
    return f"{HA_URL.rstrip('/')}/api"


def _get(endpoint: str, timeout: int = 10) -> requests.Response:
    """GET-Request an HA API mit Auth."""
    resp = requests.get(f"{_base_url()}/{endpoint}", headers=_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Sensor-Zugriff
# ---------------------------------------------------------------------------


def get_state(entity_id: str) -> dict:
    """Liest den aktuellen State eines HA-Sensors.

    Args:
        entity_id: z.B. 'sensor.sun2000_active_power'

    Returns:
        Dict mit 'state', 'attributes', 'last_updated' etc.
    """
    resp = _get(f"states/{entity_id}")
    return resp.json()


def get_state_value(entity_id: str) -> float | None:
    """Liest den numerischen Wert eines Sensors.

    Returns:
        Float-Wert oder None wenn unavailable/unknown.
    """
    state = get_state(entity_id)
    val = state.get("state")
    if val in (None, "unavailable", "unknown"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def get_all_states() -> list[dict]:
    """Liest alle Sensor-States von HA.

    Returns:
        Liste aller Entity-States.
    """
    resp = _get("states")
    return resp.json()


def find_sensors(keyword: str) -> list[dict]:
    """Sucht Sensoren anhand eines Keywords im Entity-Namen.

    Args:
        keyword: Suchbegriff (case-insensitive).

    Returns:
        Liste passender Entities mit id, state, unit, friendly_name.
    """
    all_states = get_all_states()
    keyword_lower = keyword.lower()
    results = []
    for entity in all_states:
        eid = entity.get("entity_id", "")
        friendly = entity.get("attributes", {}).get("friendly_name", "")
        if keyword_lower in eid.lower() or keyword_lower in friendly.lower():
            results.append({
                "entity_id": eid,
                "state": entity.get("state"),
                "unit": entity.get("attributes", {}).get("unit_of_measurement", ""),
                "friendly_name": friendly,
            })
    return results


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def get_history(
    entity_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    hours: int = 24,
) -> pd.DataFrame:
    """Liest die History eines Sensors.

    Args:
        entity_id: z.B. 'sensor.sun2000_active_power'
        start: Startzeit (default: jetzt - hours)
        end: Endzeit (default: jetzt)
        hours: Stunden zurück (wenn kein start angegeben)

    Returns:
        DataFrame mit ['timestamp', 'value'].
    """
    if start is None:
        start = datetime.utcnow() - timedelta(hours=hours)
    if end is None:
        end = datetime.utcnow()

    ts = start.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    params = {
        "filter_entity_id": entity_id,
        "end_time": end.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "minimal_response": "",
        "no_attributes": "",
    }

    resp = requests.get(
        f"{_base_url()}/history/period/{ts}",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()

    data = resp.json()
    if not data or not data[0]:
        return pd.DataFrame(columns=["timestamp", "value"])

    records = []
    for entry in data[0]:
        state = entry.get("s", entry.get("state"))
        if state in (None, "unavailable", "unknown"):
            continue
        try:
            val = float(state)
        except (ValueError, TypeError):
            continue
        records.append({
            "timestamp": entry.get("lu", entry.get("last_updated")),
            "value": val,
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Bulk-Abfrage für Collector
# ---------------------------------------------------------------------------


def get_site_snapshot(sensor_map: dict[str, str]) -> dict:
    """Liest mehrere Sensoren in einem Rutsch.

    Args:
        sensor_map: Dict {lokaler_name: entity_id}, z.B.
                    {'pv_power': 'sensor.sun2000_active_power', ...}

    Returns:
        Dict mit lokalen Namen als Keys und Float-Werten.
    """
    result = {}
    for local_name, entity_id in sensor_map.items():
        result[local_name] = get_state_value(entity_id)
    return result
