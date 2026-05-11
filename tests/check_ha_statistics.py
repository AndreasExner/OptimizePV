"""Prüfe HA Langzeit-Statistiken (stündliche Aggregate)."""
import sys
sys.path.insert(0, ".")
import requests, json
from datetime import datetime, timedelta, timezone
from src.config import HA_URL, HA_TOKEN

headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

# HA hat einen separaten Endpunkt für Langzeit-Statistiken
# /api/history/period liefert bei langen Zeiträumen die statistics

# Teste mit 240h (10 Tage) – hat vorhin 1734 Einträge geliefert
start = (datetime.now(timezone.utc) - timedelta(hours=240)).strftime("%Y-%m-%dT%H:%M:%S+00:00")

sensors = [
    "sensor.inverter_wirkleistung",
    "sensor.evcc_pv_power",
    "sensor.evcc_battery_soc",
    "sensor.power_meter_wirkleistung",
    "sensor.evcc_home_power",
]

for entity in sensors:
    resp = requests.get(
        f"{HA_URL}/api/history/period/{start}",
        headers=headers,
        params={"filter_entity_id": entity},
        timeout=30,
    )
    data = resp.json()
    if data and data[0]:
        entries = data[0]
        first = entries[0]
        last = entries[-1]
        ts1 = first.get("last_updated", first.get("lu", "?"))
        ts2 = last.get("last_updated", last.get("lu", "?"))
        print(f"{entity}")
        print(f"  Einträge: {len(entries)}, von {ts1[:19]} bis {ts2[:19] if ts2 != '?' else '?'}")
        # Prüfe ob es stündliche Intervalle sind
        if len(entries) > 2:
            from datetime import datetime as dt
            try:
                t1 = dt.fromisoformat(entries[1].get("last_updated", entries[1].get("lu", "")))
                t2 = dt.fromisoformat(entries[2].get("last_updated", entries[2].get("lu", "")))
                diff = (t2 - t1).total_seconds()
                print(f"  Intervall Beispiel: {diff:.0f}s = {diff/60:.0f}min")
            except:
                pass
        # Zeige ein paar Werte
        vals = []
        for e in entries[:5]:
            s = e.get("state", e.get("s", "?"))
            vals.append(s)
        print(f"  Erste Werte: {vals}")
        print()
    else:
        print(f"{entity}: keine Daten\n")

# Teste auch den statistics-Endpunkt direkt
print("=== HA Statistics API ===")
try:
    # Dieser Endpunkt existiert ab HA 2023.x
    resp = requests.get(
        f"{HA_URL}/api/history/period/{start}",
        headers=headers,
        params={
            "filter_entity_id": "sensor.evcc_pv_power",
            "significant_changes_only": "0",
        },
        timeout=30,
    )
    data = resp.json()
    if data and data[0]:
        print(f"evcc_pv_power mit significant_changes_only=0: {len(data[0])} Einträge")
except Exception as e:
    print(f"Fehler: {e}")
