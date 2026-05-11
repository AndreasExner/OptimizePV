"""Test: Neuer Collector mit allen direkten Sensoren."""
import sys
sys.path.insert(0, ".")
from src.data.collector import init_db, collect_once

init_db()
data = collect_once()
if data:
    print(f"Source: {data['source']}")
    print("\n--- Leistung (W) ---")
    for k in ["pv_power", "battery_soc", "battery_power", "grid_power", 
              "home_power", "wp_power", "ev_power"]:
        v = data.get(k)
        print(f"  {k:25s} {v:>10.1f}" if v is not None else f"  {k:25s}       None")
    
    print("\n--- Zaehlerstaende (kWh) ---")
    for k in ["pv_energy_total", "pv_energy_daily", "grid_import_total", 
              "grid_export_total", "battery_charge_total", "battery_discharge_total",
              "wp_energy_total", "ev_energy_total"]:
        v = data.get(k)
        print(f"  {k:25s} {v:>12.2f}" if v is not None else f"  {k:25s}         None")
    
    # Energiebilanz-Check
    print("\n--- Energiebilanz (Leistung) ---")
    pv = data.get("pv_power") or 0
    bat = data.get("battery_power") or 0
    grid = data.get("grid_power") or 0
    home = data.get("home_power") or 0
    wp = data.get("wp_power") or 0
    ev = data.get("ev_power") or 0
    print(f"  PV={pv:.0f}W  Bat={bat:.0f}W  Grid={grid:.0f}W")
    print(f"  Home(berechnet)={home:.0f}W  WP={wp:.0f}W  EV={ev:.0f}W")
    print(f"  Check: PV - Bat + Grid = {pv - bat + grid:.0f}W (soll={home:.0f}W)")
else:
    print("FEHLER: Keine Daten")
