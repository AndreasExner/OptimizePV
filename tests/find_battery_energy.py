"""Suche Batterie-Energiezähler (kWh)."""
import sys
sys.path.insert(0, ".")
from src.data.ha_connector import find_sensors

results = [r for r in find_sensors("battery") 
           if r["entity_id"].startswith("sensor.") and r["unit"] == "kWh"]
print("Batterie-Sensoren mit kWh:")
for s in sorted(results, key=lambda x: x["entity_id"]):
    print(f"  {s['entity_id']:60s} {s['state']:>12s} {s['unit']:>5s}  {s['friendly_name']}")
if not results:
    print("  Keine gefunden")

# Auch nach Huawei-spezifischen Bezeichnungen suchen
for kw in ["charge_discharge_energy", "accumulated", "battery_day", "battery_total",
           "battery_charge", "battery_discharge", "stored_energy"]:
    results = [r for r in find_sensors(kw) if r["entity_id"].startswith("sensor.")]
    if results:
        print(f"\n--- {kw} ---")
        for s in results:
            print(f"  {s['entity_id']:60s} {s['state']:>12s} {s['unit']:>5s}  {s['friendly_name']}")
