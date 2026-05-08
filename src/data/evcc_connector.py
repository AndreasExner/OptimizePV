"""evcc Daten-Connector.

Liest Systemstatus, historische Energiedaten und Steuerungsbefehle über die evcc
REST API. Für längere Historie wird die evcc SQLite-Datenbank direkt gelesen.

evcc ist die einzige Schnittstelle zur PV-Hardware – damit bleibt das Projekt
herstellerunabhängig.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from src.config import EVCC_DB_PATH, EVCC_URL

# ---------------------------------------------------------------------------
# REST API – Lesen
# ---------------------------------------------------------------------------


def get_state() -> dict:
    """Liest den aktuellen Systemstatus von evcc.

    Returns:
        Dict mit pvPower, batterySoc, batteryPower, gridPower, homePower,
        loadpoints etc.
    """
    resp = requests.get(f"{EVCC_URL}/api/state", timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]


def get_site_power() -> dict:
    """Extrahiert die wichtigsten Leistungswerte aus dem aktuellen State.

    Returns:
        Dict mit Keys: pv_power, battery_soc, battery_power, grid_power,
        home_power (alle float).
    """
    state = get_state()
    return {
        "pv_power": float(state.get("pvPower", 0)),
        "battery_soc": float(state.get("batterySoc", 0)),
        "battery_power": float(state.get("batteryPower", 0)),
        "grid_power": float(state.get("gridPower", 0)),
        "home_power": float(state.get("homePower", 0)),
    }


def get_sessions() -> pd.DataFrame:
    """Liest die Ladesitzungen von evcc.

    Returns:
        DataFrame mit Ladesitzungsdaten.
    """
    resp = requests.get(f"{EVCC_URL}/api/sessions", timeout=10)
    resp.raise_for_status()

    sessions = resp.json().get("result", [])
    if not sessions:
        return pd.DataFrame()

    df = pd.DataFrame(sessions)
    for col in ("created", "finished"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


def get_energy_history() -> pd.DataFrame:
    """Liest die Energiehistorie von evcc (REST API, bis ~14 Tage).

    Returns:
        DataFrame mit Energiedaten pro Zeitintervall.
    """
    resp = requests.get(f"{EVCC_URL}/api/history/energy", timeout=10)
    resp.raise_for_status()
    data = resp.json().get("result", [])
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


def get_tariff(tariff_type: str = "grid") -> pd.DataFrame:
    """Liest aktuelle Tarifpreise aus evcc.

    Args:
        tariff_type: 'grid', 'feedin' oder 'co2'

    Returns:
        DataFrame mit Spalten ['start', 'end', 'price']
    """
    resp = requests.get(f"{EVCC_URL}/api/tariff/{tariff_type}", timeout=10)
    resp.raise_for_status()

    rates = resp.json().get("result", {}).get("rates", [])
    if not rates:
        return pd.DataFrame(columns=["start", "end", "price"])

    df = pd.DataFrame(rates)
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    return df


# ---------------------------------------------------------------------------
# REST API – Steuern
# ---------------------------------------------------------------------------


def set_battery_mode(mode: str) -> None:
    """Setzt den Batterie-Modus.

    Args:
        mode: 'normal', 'hold' oder 'charge'
    """
    resp = requests.post(f"{EVCC_URL}/api/batterymode/{mode}", timeout=10)
    resp.raise_for_status()


def set_battery_discharge_control(enabled: bool) -> None:
    """Aktiviert/deaktiviert die Batterie-Entladekontrolle."""
    val = "true" if enabled else "false"
    resp = requests.post(
        f"{EVCC_URL}/api/batterydischargecontrol/{val}", timeout=10
    )
    resp.raise_for_status()


def set_battery_grid_charge_limit(limit: float | None) -> None:
    """Setzt das Grid-Charge-Limit für die Batterie (in W).

    Args:
        limit: Leistungsgrenze in W, oder None zum Entfernen.
    """
    if limit is None:
        resp = requests.delete(
            f"{EVCC_URL}/api/batterygridchargelimit", timeout=10
        )
    else:
        resp = requests.post(
            f"{EVCC_URL}/api/batterygridchargelimit/{limit}", timeout=10
        )
    resp.raise_for_status()


def set_buffer_soc(soc: float) -> None:
    """Setzt den Buffer-SoC (minimaler Batterie-Ladestand in %)."""
    resp = requests.post(f"{EVCC_URL}/api/buffersoc/{soc}", timeout=10)
    resp.raise_for_status()


def set_priority_soc(soc: float) -> None:
    """Setzt den Priority-SoC (Batterie-Priorität in %)."""
    resp = requests.post(f"{EVCC_URL}/api/prioritysoc/{soc}", timeout=10)
    resp.raise_for_status()


def set_smart_cost_limit(limit: float | None) -> None:
    """Setzt das Smart-Cost-Limit (Preisschwelle für günstiges Laden).

    Args:
        limit: Preisschwelle in ct/kWh, oder None zum Entfernen.
    """
    if limit is None:
        resp = requests.delete(f"{EVCC_URL}/api/smartcostlimit", timeout=10)
    else:
        resp = requests.post(
            f"{EVCC_URL}/api/smartcostlimit/{limit}", timeout=10
        )
    resp.raise_for_status()


def set_loadpoint_mode(loadpoint_id: int, mode: str) -> None:
    """Setzt den Lademodus eines Loadpoints.

    Args:
        loadpoint_id: 1-basierte Loadpoint-ID.
        mode: 'off', 'now', 'minpv' oder 'pv'.
    """
    resp = requests.post(
        f"{EVCC_URL}/api/loadpoints/{loadpoint_id}/mode/{mode}", timeout=10
    )
    resp.raise_for_status()


def set_loadpoint_plan(
    loadpoint_id: int, energy_kwh: float, deadline: str
) -> None:
    """Erstellt einen Ladeplan für einen Loadpoint.

    Args:
        loadpoint_id: 1-basierte Loadpoint-ID.
        energy_kwh: Gewünschte Energiemenge in kWh.
        deadline: Zielzeit im ISO 8601 Format.
    """
    resp = requests.post(
        f"{EVCC_URL}/api/loadpoints/{loadpoint_id}/plan/energy/{energy_kwh}/{deadline}",
        timeout=10,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# SQLite – Langzeit-Historie
# ---------------------------------------------------------------------------


def get_db_path() -> Path:
    """Gibt den Pfad zur evcc SQLite-Datenbank zurück."""
    return Path(EVCC_DB_PATH)


def get_long_history(days: int = 90) -> pd.DataFrame:
    """Liest die Energiehistorie aus der evcc SQLite-Datenbank.

    Damit steht deutlich längere Historie als über die REST API (14 Tage)
    zur Verfügung.

    Args:
        days: Anzahl Tage in die Vergangenheit.

    Returns:
        DataFrame mit Ladesitzungen.
    """
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    since = (datetime.now() - timedelta(days=days)).isoformat()

    query = """
        SELECT created, finished, loadpoint, identifier,
               charge_duration, solar, price,
               charged_kwh AS energy_kwh
        FROM sessions
        WHERE created >= ?
        ORDER BY created
    """

    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(query, conn, params=(since,))

    for col in ("created", "finished"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df
