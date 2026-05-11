"""Prüfe HA History – teste verschiedene Zeiträume."""
import sys
sys.path.insert(0, ".")
import requests, json
from datetime import datetime, timedelta, timezone
from src.config import HA_URL, HA_TOKEN

headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

entity = "sensor.evcc_pv_power"

for hours in [1, 6, 24, 48, 120, 240]:
    start = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    resp = requests.get(
        f"{HA_URL}/api/history/period/{start}",
        headers=headers,
        params={"filter_entity_id": entity, "minimal_response": "", "no_attributes": ""},
        timeout=30,
    )
    data = resp.json()
    count = len(data[0]) if data and data[0] else 0
    if count > 0:
        first = data[0][0]
        last = data[0][-1]
        # minimal_response hat 'lu' statt 'last_updated' und 's' statt 'state'
        ts_first = first.get("lu", first.get("last_updated", "?"))
        ts_last = last.get("lu", last.get("last_updated", "?"))
        print(f"{hours:>4d}h: {count:>6d} Einträge, {ts_first} bis {ts_last}")
    else:
        print(f"{hours:>4d}h: keine Daten")
