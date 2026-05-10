"""Schnelltest: evcc Connector gegen reale Instanz."""
import sys
sys.path.insert(0, "d:/GitHub/OptimizePV")

from src.data.evcc_connector import get_state, get_site_power, get_tariff, get_sessions, get_energy_history

print("=== 1. System State ===")
try:
    state = get_state()
    for k in ["pvPower", "batterySoc", "batteryPower", "gridPower", "homePower"]:
        print(f"  {k}: {state.get(k, 'N/A')}")
    lps = state.get("loadpoints", [])
    print(f"  Loadpoints: {len(lps)}")
except Exception as e:
    print(f"  FEHLER: {e}")

print()
print("=== 2. Site Power ===")
try:
    sp = get_site_power()
    for k, v in sp.items():
        print(f"  {k}: {v}")
except Exception as e:
    print(f"  FEHLER: {e}")

print()
print("=== 3. Grid Tariff ===")
try:
    df = get_tariff("grid")
    print(f"  Eintraege: {len(df)}")
    if not df.empty:
        print(df.head(3).to_string(index=False))
except Exception as e:
    print(f"  FEHLER: {e}")

print()
print("=== 4. Feedin Tariff ===")
try:
    df = get_tariff("feedin")
    print(f"  Eintraege: {len(df)}")
    if not df.empty:
        print(df.head(3).to_string(index=False))
except Exception as e:
    print(f"  FEHLER: {e}")

print()
print("=== 5. Sessions ===")
try:
    df = get_sessions()
    print(f"  Eintraege: {len(df)}")
    if not df.empty:
        cols = [c for c in ["created", "loadpoint", "chargedEnergy", "solarPercentage", "price"] if c in df.columns]
        print(df[cols].head(3).to_string(index=False))
except Exception as e:
    print(f"  FEHLER: {e}")

print()
print("=== 6. Energy History ===")
try:
    df = get_energy_history()
    print(f"  Eintraege: {len(df)}")
    if not df.empty:
        print(f"  Spalten: {list(df.columns)}")
        print(df.head(3).to_string(index=False))
except Exception as e:
    print(f"  FEHLER: {e}")
