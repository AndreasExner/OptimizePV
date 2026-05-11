"""Prüfe HA History Format und Tiefe – Rohformat."""
import sys
sys.path.insert(0, ".")
import requests
from datetime import datetime, timedelta
from src.config import HA_URL, HA_TOKEN

headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

# 10 Tage zurück
start = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
entity = "sensor.inverter_wirkleistung"

# Ohne minimal_response, um das volle Format zu sehen
resp = requests.get(
    f"{HA_URL}/api/history/period/{start}",
    headers=headers,
    params={"filter_entity_id": entity},
    timeout=30,
)
data = resp.json()

if data and data[0]:
    entries = data[0]
    print(f"Sensor: {entity}")
    print(f"Einträge: {len(entries)}")
    print(f"\nErstes Element (Rohformat):")
    import json
    print(json.dumps(entries[0], indent=2, default=str)[:500])
    print(f"\nLetztes Element:")
    print(json.dumps(entries[-1], indent=2, default=str)[:500])
    
    # Zeitraum
    first_ts = entries[0].get("last_updated") or entries[0].get("last_changed")
    last_ts = entries[-1].get("last_updated") or entries[-1].get("last_changed")
    print(f"\nZeitraum: {first_ts} bis {last_ts}")
else:
    print("Keine Daten!")
