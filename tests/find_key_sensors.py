"""Finde die wichtigsten Sensoren für das Sensor-Mapping."""
import sys
sys.path.insert(0, ".")
from src.data.ha_connector import find_sensors

keywords = ["inverter", "wechselrichter", "evcc_pv", "evcc_battery",
            "evcc_grid", "evcc_home", "power_meter", "battery_soc",
            "battery_state", "active_power", "input_power"]

for kw in keywords:
    results = [r for r in find_sensors(kw) if r["entity_id"].startswith("sensor.")]
    if results:
        print(f"--- {kw} ---")
        for s in results:
            eid = s["entity_id"]
            val = s["state"]
            unit = s["unit"]
            name = s["friendly_name"]
            print(f"  {eid:55s} {val:>12s} {unit:>5s}  {name}")
        print()
