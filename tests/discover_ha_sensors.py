"""Ermittle verfügbare HA-Sensoren für PV, Batterie, Grid, Verbrauch."""
import sys
sys.path.insert(0, ".")

from src.data.ha_connector import find_sensors

# Relevante Suchbegriffe
searches = [
    ("sun2000", "Huawei Wechselrichter"),
    ("shelly", "Shelly 3EM (Grid)"),
    ("vaillant", "Vaillant Wärmepumpe"),
    ("power", "Leistungssensoren"),
    ("energy", "Energiezähler"),
    ("battery", "Batterie"),
    ("wallbox", "Wallbox"),
    ("go_e", "go-e Charger"),
    ("goe", "go-e Charger"),
]

for keyword, desc in searches:
    results = find_sensors(keyword)
    # Nur Sensoren mit numerischen Werten
    sensors = [r for r in results if r["entity_id"].startswith("sensor.")]
    if sensors:
        print(f"\n=== {desc} ({keyword}) – {len(sensors)} Sensoren ===")
        for s in sorted(sensors, key=lambda x: x["entity_id"]):
            print(f"  {s['entity_id']:55s} = {s['state']:>10s} {s['unit']:>5s}  ({s['friendly_name']})")
