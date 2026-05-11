"""Prüfe HA Langzeit-Statistiken über WebSocket/statistics-during-period."""
import sys
sys.path.insert(0, ".")
import requests, json
from datetime import datetime, timedelta, timezone
from src.config import HA_URL, HA_TOKEN

headers = {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}

# Die REST API für statistics ist: /api/history/statistics
# oder via WS: statistics/statistics_during_period

# Versuche den REST-Endpunkt
start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

# Endpunkt 1: /api/history/statistics/<statistic_id>
for stat_id in ["sensor.evcc_pv_power", "sensor.evcc_pv_energy",
                "sensor.inverter_gesamtenergieertrag", "sensor.inverter_tagesertrag",
                "sensor.power_meter_verbrauch", "sensor.power_meter_exportierte_energie"]:
    try:
        resp = requests.get(
            f"{HA_URL}/api/history/period/{start}",
            headers=headers,
            params={"filter_entity_id": stat_id},
            timeout=15,
        )
        data = resp.json()
        count = len(data[0]) if data and data[0] else 0
        if count > 0:
            first_ts = data[0][0].get("last_updated", data[0][0].get("lu", "?"))
            last_ts = data[0][-1].get("last_updated", data[0][-1].get("lu", "?"))
            first_val = data[0][0].get("state", data[0][0].get("s", "?"))
            last_val = data[0][-1].get("state", data[0][-1].get("s", "?"))
            print(f"{stat_id}")
            print(f"  {count} Einträge: {first_ts[:19]} ({first_val}) bis {last_ts[:19]} ({last_val})")
        else:
            print(f"{stat_id}: keine Daten")
    except Exception as e:
        print(f"{stat_id}: ERROR {e}")
