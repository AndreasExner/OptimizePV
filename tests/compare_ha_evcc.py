"""Finaler Vergleich HA vs evcc nach Vorzeichen-Normalisierung."""
import sys
sys.path.insert(0, ".")
from src.data.collector import init_db, collect_once, _collect_from_evcc

init_db()
ha = collect_once()
evcc = _collect_from_evcc()

print("Konvention: grid pos=Bezug, bat pos=Laden")
print(f"{'':18s} {'HA':>8s}  {'evcc':>8s}")
for k in ["pv_power", "battery_soc", "battery_power", "grid_power",
           "home_power", "wp_power", "ev_power"]:
    h = ha.get(k) if ha else None
    e = evcc.get(k) if evcc else None
    hv = f"{h:.0f}" if h is not None else "N/A"
    ev = f"{e:.0f}" if e is not None else "N/A"
    print(f"  {k:18s} {hv:>8s}  {ev:>8s}")
