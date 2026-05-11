"""Prüfe wie weit die HA History für die wichtigsten Sensoren zurückreicht."""
import sys
sys.path.insert(0, ".")

from src.data.ha_connector import get_history

sensors = [
    ("sensor.inverter_wirkleistung", "PV Leistung"),
    ("sensor.inverter_tagesertrag", "PV Tagesertrag"),
    ("sensor.evcc_battery_soc", "Batterie SoC"),
    ("sensor.evcc_battery_power", "Batterie Leistung"),
    ("sensor.power_meter_wirkleistung", "Grid Leistung"),
    ("sensor.evcc_home_power", "Home Verbrauch"),
    ("sensor.shelly_warmepumpe_channel_a_power", "WP Phase A"),
    ("sensor.evcc_pv_power", "PV (evcc)"),
]

print(f"{'Sensor':<45s} {'Einträge':>10s} {'Von':>25s} {'Bis':>25s} {'Tage':>6s}")
print("-" * 115)

for entity_id, label in sensors:
    try:
        df = get_history(entity_id, hours=240)  # max 10 Tage
        if df.empty:
            print(f"{label:<45s} {'0':>10s} {'–':>25s} {'–':>25s} {'–':>6s}")
        else:
            first = df["timestamp"].min()
            last = df["timestamp"].max()
            days = (last - first).total_seconds() / 86400
            print(f"{label:<45s} {len(df):>10d} {str(first)[:25]:>25s} {str(last)[:25]:>25s} {days:>5.1f}d")
    except Exception as e:
        print(f"{label:<45s} {'ERROR':>10s}  {str(e)[:70]}")
