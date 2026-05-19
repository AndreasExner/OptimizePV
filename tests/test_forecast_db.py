"""Test: Forecast speichern und aus DB laden."""
import sys
sys.path.insert(0, ".")
from src.data.collector import init_db
from src.forecast import run_forecast_once, load_forecast_from_db

init_db()
ok = run_forecast_once()
print(f"Forecast: {'OK' if ok else 'FEHLER'}")

records = load_forecast_from_db(hours=24)
print(f"DB: {len(records)} Eintraege")
if records:
    print(f"Erster: {records[0]['timestamp']}")
    print(f"Letzter: {records[-1]['timestamp']}")
    print(f"PV DC: {records[0]['pv_dc_forecast']}")
    print(f"Home: {records[0]['home_forecast']}")
    print(f"Batterie: {records[0]['battery_action']}")
