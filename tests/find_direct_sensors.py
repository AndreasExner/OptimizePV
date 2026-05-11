"""Finde alle direkten Geräte-Sensoren (ohne evcc) für Leistung und Arbeit."""
import sys
sys.path.insert(0, ".")
from src.data.ha_connector import find_sensors, get_state

# Batterie: Energie-Sensoren
print("=== Batterie (Energie/Arbeit) ===")
for kw in ["battery_1"]:
    results = [r for r in find_sensors(kw) if r["entity_id"].startswith("sensor.")]
    for s in sorted(results, key=lambda x: x["entity_id"]):
        print(f"  {s['entity_id']:60s} {s['state']:>12s} {s['unit']:>5s}  {s['friendly_name']}")

# go-e Charger
print("\n=== go-e Charger ===")
for entity_id in ["sensor.goe_111927_eto", "sensor.goe_111927_nrg_11"]:
    state = get_state(entity_id)
    val = state.get("state")
    unit = state.get("attributes", {}).get("unit_of_measurement", "")
    name = state.get("attributes", {}).get("friendly_name", "")
    print(f"  {entity_id:60s} {val:>12s} {unit:>5s}  {name}")

# Inverter Energie-Sensoren
print("\n=== PV Wechselrichter (Energie) ===")
for kw in ["inverter_gesamt", "inverter_tages", "inverter_hourly"]:
    results = [r for r in find_sensors(kw) if r["entity_id"].startswith("sensor.")]
    for s in sorted(results, key=lambda x: x["entity_id"]):
        print(f"  {s['entity_id']:60s} {s['state']:>12s} {s['unit']:>5s}  {s['friendly_name']}")

# Grid Smartmeter Energie
print("\n=== Grid Smartmeter (Energie) ===")
for kw in ["power_meter_verbrauch", "power_meter_exportierte"]:
    results = [r for r in find_sensors(kw) if r["entity_id"].startswith("sensor.")]
    for s in sorted(results, key=lambda x: x["entity_id"]):
        print(f"  {s['entity_id']:60s} {s['state']:>12s} {s['unit']:>5s}  {s['friendly_name']}")

# Shelly WP alle Phasen
print("\n=== Shelly WP (alle Phasen) ===")
for kw in ["shelly_warmepumpe_channel"]:
    results = [r for r in find_sensors(kw) 
               if r["entity_id"].startswith("sensor.") 
               and ("energy" in r["entity_id"] or "power" in r["entity_id"])
               and "factor" not in r["entity_id"]
               and "returned" not in r["entity_id"]]
    for s in sorted(results, key=lambda x: x["entity_id"]):
        print(f"  {s['entity_id']:60s} {s['state']:>12s} {s['unit']:>5s}  {s['friendly_name']}")
