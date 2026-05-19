"""Schneller Check der Collector-Daten und stündlichen Aggregation."""
import sys
sys.path.insert(0, ".")
from pathlib import Path
from src.features.feature_engineering import load_collector_data, build_hourly_from_collector

DB = Path("data/optimizepv.db")
raw = load_collector_data(db_path=DB)
print(f"Rohdaten: {len(raw)} Eintraege")
print(f"Zeitraum: {raw['timestamp'].min()} bis {raw['timestamp'].max()}")
print(f"pv_dc_power: {raw['pv_dc_power'].notna().sum()} vorhanden, {raw['pv_dc_power'].isna().sum()} NULL")
print(f"pv_dc_power range: {raw['pv_dc_power'].min():.0f} - {raw['pv_dc_power'].max():.0f} W")

print("\n--- Stündliche Aggregation ---")
hourly = build_hourly_from_collector(raw)
print(f"Stündlich: {len(hourly)} Stunden")
print(f"Zeitraum: {hourly['timestamp'].min()} bis {hourly['timestamp'].max()}")
print(f"Spalten: {list(hourly.columns)}")

# Target prüfen
if "pv_module_kwh" in hourly.columns:
    print(f"\npv_module_kwh: min={hourly['pv_module_kwh'].min():.3f}, max={hourly['pv_module_kwh'].max():.3f}, mean={hourly['pv_module_kwh'].mean():.3f}")
if "pv_dc_power" in hourly.columns:
    print(f"pv_dc_power (mean W): min={hourly['pv_dc_power'].min():.0f}, max={hourly['pv_dc_power'].max():.0f}")

# pv_dc als Alternative: Direkt kWh aus DC-Leistung
hourly["pv_dc_kwh"] = hourly["pv_dc_power"] / 1000.0 if "pv_dc_power" in hourly.columns else None
if "pv_dc_kwh" in hourly.columns:
    print(f"pv_dc_kwh: min={hourly['pv_dc_kwh'].min():.3f}, max={hourly['pv_dc_kwh'].max():.3f}, mean={hourly['pv_dc_kwh'].mean():.3f}")
