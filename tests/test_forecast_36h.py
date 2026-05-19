"""Test: Forecast API mit 24h und 36h vergleichen."""
import requests
import json

for hours in [24, 36]:
    r = requests.get(f"http://localhost:8099/api/forecast?hours={hours}")
    print(f"\n=== {hours}h: Status {r.status_code} ===")
    d = r.json()
    if d.get("error"):
        print(f"  ERROR: {d['error']}")
    fc = d.get("forecast", [])
    print(f"  Einträge: {len(fc)}")
    if fc:
        print(f"  Erster: {fc[0]['timestamp']}")
        print(f"  Letzter: {fc[-1]['timestamp']}")
        # Prüfe ob alle Felder vorhanden und serialisierbar sind
        for key in fc[0]:
            val = fc[0][key]
            print(f"  {key}: {type(val).__name__} = {val}")
