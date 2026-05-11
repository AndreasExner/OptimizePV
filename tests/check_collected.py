"""Berechne Verbrauch aus gesammelten Collector-Daten."""
import sqlite3
import pandas as pd

conn = sqlite3.connect("data/optimizepv.db")
df = pd.read_sql_query(
    "SELECT timestamp, pv_power, home_power, grid_power, battery_power, battery_soc "
    "FROM measurements ORDER BY timestamp",
    conn,
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
conn.close()

print(f"Gesammelte Daten: {len(df)} Einträge")
print(f"Zeitraum: {df['timestamp'].min()} bis {df['timestamp'].max()}")
duration_min = (df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 60
hours = duration_min / 60
print(f"Dauer: {duration_min:.0f} Minuten")

avg_home = df["home_power"].mean()
avg_pv = df["pv_power"].mean()
avg_grid = df["grid_power"].mean()
avg_bat = df["battery_power"].mean()

print(f"\n=== Durchschnittswerte ===")
print(f"Hausverbrauch:  {avg_home:.0f} W  ({avg_home * hours / 1000:.2f} kWh gesamt)")
print(f"PV-Erzeugung:   {avg_pv:.0f} W  ({avg_pv * hours / 1000:.2f} kWh gesamt)")
print(f"Grid:           {avg_grid:.0f} W  ({avg_grid * hours / 1000:.2f} kWh, neg=Einspeisung)")
print(f"Batterie:       {avg_bat:.0f} W  (neg=Entladung)")
print(f"Batterie SoC:   {df['battery_soc'].min():.0f}% - {df['battery_soc'].max():.0f}%")

# Energiebilanz-Check: PV = Home + Grid_Export + Bat_Charge (vereinfacht)
print(f"\n=== Energiebilanz ===")
print(f"PV ({avg_pv:.0f}W) ≈ Home ({avg_home:.0f}W) + Grid ({-avg_grid:.0f}W) + Bat ({avg_bat:.0f}W)")
bilanz = avg_pv - avg_home + avg_grid - avg_bat
print(f"Differenz: {bilanz:.0f} W {'(OK)' if abs(bilanz) < 100 else '(Abweichung!)'}")
