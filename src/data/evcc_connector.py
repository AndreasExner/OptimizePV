"""evcc Daten-Connector.

Liest Systemstatus und historische Energiedaten über die evcc REST API.
"""

import pandas as pd
import requests

from src.config import EVCC_URL


def get_state() -> dict:
    """Liest den aktuellen Systemstatus von evcc.

    Returns:
        Dict mit aktuellem PV-Ertrag, Batterie-SoC, Grid-Power, Loadpoints etc.
    """
    resp = requests.get(f"{EVCC_URL}/api/state", timeout=10)
    resp.raise_for_status()
    return resp.json()["result"]


def get_energy_history() -> pd.DataFrame:
    """Liest die Energiehistorie von evcc (bis zu 14 Tage).

    Returns:
        DataFrame mit Energiedaten pro Zeitintervall.
    """
    resp = requests.get(f"{EVCC_URL}/api/sessions", timeout=10)
    resp.raise_for_status()

    sessions = resp.json().get("result", [])
    if not sessions:
        return pd.DataFrame()

    df = pd.DataFrame(sessions)
    if "created" in df.columns:
        df["created"] = pd.to_datetime(df["created"])
    if "finished" in df.columns:
        df["finished"] = pd.to_datetime(df["finished"])
    return df


def get_tariff() -> pd.DataFrame:
    """Liest aktuelle Tarifpreise aus evcc.

    Returns:
        DataFrame mit Spalten ['start', 'end', 'price']
    """
    resp = requests.get(f"{EVCC_URL}/api/tariff/grid", timeout=10)
    resp.raise_for_status()

    rates = resp.json().get("result", {}).get("rates", [])
    if not rates:
        return pd.DataFrame(columns=["start", "end", "price"])

    df = pd.DataFrame(rates)
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    return df
