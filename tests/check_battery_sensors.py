"""Prüfe die neuen Batterie-Sensoren aus HA."""
import sys
sys.path.insert(0, ".")
from src.data.ha_connector import get_state

for entity_id in [
    "sensor.battery_1_batterieladung",
    "sensor.battery_1_lade_entladeleistung",
    # Vergleich mit bestehenden
    "sensor.evcc_battery_soc",
    "sensor.evcc_battery_power",
]:
    state = get_state(entity_id)
    val = state.get("state")
    unit = state.get("attributes", {}).get("unit_of_measurement", "")
    name = state.get("attributes", {}).get("friendly_name", "")
    device_class = state.get("attributes", {}).get("device_class", "")
    print(f"{entity_id}")
    print(f"  Wert: {val} {unit}")
    print(f"  Name: {name}")
    print(f"  Device Class: {device_class}")
    print()
