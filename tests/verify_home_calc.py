"""Verifiziere die neue Home-Berechnung und pv_dc_power."""
import sys
sys.path.insert(0, ".")
from src.data.collector import init_db, collect_once

init_db()
d = collect_once()
if d:
    pv_ac = d.get("pv_power") or 0
    pv_dc = d.get("pv_dc_power") or 0
    bat = d.get("battery_power") or 0
    grid = d.get("grid_power") or 0
    home = d.get("home_power") or 0
    wp = d.get("wp_power") or 0
    ev = d.get("ev_power") or 0

    print("=== Leistungswerte ===")
    print(f"  PV DC (Module):  {pv_dc:.0f} W")
    print(f"  PV AC (WR-Out):  {pv_ac:.0f} W")
    print(f"  Batterie:        {bat:.0f} W (pos=Laden)")
    print(f"  Grid:            {grid:.0f} W (pos=Bezug, neg=Einspeisung)")
    print(f"  Home:            {home:.0f} W (berechnet)")
    print(f"  WP:              {wp:.0f} W")
    print(f"  EV:              {ev:.0f} W")

    print(f"\n=== Bilanz-Checks ===")
    # Check 1: DC ≈ AC + Batterie-Ladung (bei Laden)
    bat_charge = max(0, bat)
    print(f"  PV_DC ({pv_dc:.0f}) vs PV_AC+Bat_Charge ({pv_ac + bat_charge:.0f})")

    # Check 2: AC-Bus: WR_out = Home + WP + EV + Grid_Export
    ac_sum = home + wp + ev + max(0, -grid)  # grid neg = export
    ac_in = pv_ac + max(0, grid)  # grid pos = import
    print(f"  AC-Bus: WR_out ({pv_ac:.0f}) + Grid_Import ({max(0,grid):.0f}) = {pv_ac + max(0,grid):.0f}")
    print(f"  AC-Bus: Home ({home:.0f}) + WP ({wp:.0f}) + EV ({ev:.0f}) + Grid_Export ({max(0,-grid):.0f}) = {ac_sum:.0f}")
