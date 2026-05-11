"""Teste verschiedene HA API Endpunkte für Langzeitdaten."""
import sys
sys.path.insert(0, ".")
import requests, json
from src.config import HA_URL, HA_TOKEN

headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

# 1. Prüfe welche API-Endpunkte verfügbar sind
endpoints = [
    "/api/",
    "/api/config",
    "/api/states/sensor.evcc_pv_power",
]

for ep in endpoints:
    try:
        resp = requests.get(f"{HA_URL}{ep}", headers=headers, timeout=10)
        if ep == "/api/config":
            cfg = resp.json()
            print(f"HA Version: {cfg.get('version')}")
            print(f"Location: {cfg.get('location_name')}")
        elif ep == "/api/":
            print(f"API root: {resp.json()}")
    except Exception as e:
        print(f"{ep}: {e}")

# 2. Recorder-Konfiguration ist nicht über API abrufbar,
#    aber wir können testen wie weit die History tatsächlich reicht
print("\n=== History-Tiefe testen ===")
from datetime import datetime, timedelta, timezone

# Teste Tag für Tag
for days_ago in [0, 1, 2, 3, 5, 7, 10, 14, 30]:
    start = (datetime.now(timezone.utc) - timedelta(days=days_ago+1))
    end = (datetime.now(timezone.utc) - timedelta(days=days_ago))
    resp = requests.get(
        f"{HA_URL}/api/history/period/{start.isoformat()}",
        headers=headers,
        params={
            "filter_entity_id": "sensor.evcc_pv_power",
            "end_time": end.isoformat(),
        },
        timeout=15,
    )
    data = resp.json()
    count = len(data[0]) if data and data[0] else 0
    print(f"  {days_ago+1}-{days_ago}d ago: {count:>6d} Einträge")
