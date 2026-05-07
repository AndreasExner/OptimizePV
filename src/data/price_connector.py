"""Strompreis-Connector (aWATTar / Tibber).

Liest Day-Ahead-Strompreise inkl. negativer Preise.
"""

from datetime import datetime, timedelta
import pandas as pd
import requests

from src.config import AWATTAR_URL, TIBBER_TOKEN, TIBBER_URL


def get_awattar_prices(
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Liest Day-Ahead-Strompreise von aWATTar (kostenlos, kein API-Key).

    Args:
        start: Startzeit (default: jetzt)
        end: Endzeit (default: +48h)

    Returns:
        DataFrame mit Spalten ['timestamp', 'price_eur_mwh', 'is_negative']
    """
    params = {}
    if start is not None:
        params["start"] = int(start.timestamp() * 1000)
    if end is not None:
        params["end"] = int(end.timestamp() * 1000)

    resp = requests.get(AWATTAR_URL, params=params, timeout=10)
    resp.raise_for_status()

    entries = resp.json().get("data", [])
    if not entries:
        return pd.DataFrame(columns=["timestamp", "price_eur_mwh", "is_negative"])

    records = []
    for entry in entries:
        ts = pd.to_datetime(entry["start_timestamp"], unit="ms", utc=True)
        price = entry["marketprice"]  # EUR/MWh
        records.append({
            "timestamp": ts.tz_convert("Europe/Berlin"),
            "price_eur_mwh": price,
            "price_eur_kwh": price / 1000.0,
            "is_negative": price < 0,
        })

    return pd.DataFrame(records)


def get_tibber_prices() -> pd.DataFrame:
    """Liest Strompreise von Tibber (erfordert API-Token).

    Returns:
        DataFrame mit Spalten ['timestamp', 'price_eur_kwh', 'level', 'is_negative']
    """
    if not TIBBER_TOKEN:
        raise ValueError(
            "TIBBER_TOKEN nicht gesetzt. Bitte in .env konfigurieren "
            "oder aWATTar verwenden."
        )

    query = """
    {
        viewer {
            homes {
                currentSubscription {
                    priceInfo {
                        today { startsAt total energy level }
                        tomorrow { startsAt total energy level }
                    }
                }
            }
        }
    }
    """

    headers = {
        "Authorization": f"Bearer {TIBBER_TOKEN}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        TIBBER_URL,
        json={"query": query},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()

    homes = resp.json()["data"]["viewer"]["homes"]
    if not homes:
        return pd.DataFrame()

    price_info = homes[0]["currentSubscription"]["priceInfo"]
    all_prices = (price_info.get("today") or []) + (price_info.get("tomorrow") or [])

    records = []
    for p in all_prices:
        records.append({
            "timestamp": pd.to_datetime(p["startsAt"]),
            "price_eur_kwh": p["energy"],
            "price_total_eur_kwh": p["total"],
            "level": p["level"],
            "is_negative": p["energy"] < 0,
        })

    return pd.DataFrame(records)
