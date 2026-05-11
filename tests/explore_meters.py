"""Analysiere die meters-Tabelle der evcc.db im Detail."""
import sqlite3
import pandas as pd
from datetime import datetime

conn = sqlite3.connect("evcc.db")

# Meter-IDs und deren Zuordnung
print("=== Meter-IDs ===")
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT meter FROM meters ORDER BY meter")
meters = [r[0] for r in cursor.fetchall()]
print(f"Meter-IDs: {meters}")

# Entities (Zuordnung)
cursor.execute("SELECT * FROM entities")
entities = cursor.fetchall()
print(f"\nEntities: {entities}")

# Configs (Geräte-Konfiguration)
cursor.execute("SELECT id, class, title, product FROM configs")
configs = cursor.fetchall()
print(f"\nConfigs:")
for c in configs:
    print(f"  ID={c[0]}, class={c[1]}, title={c[2]}, product={c[3]}")

# Pro Meter: Zeitraum, Anzahl, Import/Export Stats
print("\n=== Meter-Details ===")
for m in meters:
    df = pd.read_sql_query(
        f"SELECT * FROM meters WHERE meter = {m} ORDER BY ts",
        conn
    )
    ts_min = datetime.fromtimestamp(df["ts"].min())
    ts_max = datetime.fromtimestamp(df["ts"].max())
    interval = (df["ts"].diff().dropna().median())

    print(f"\nMeter {m}: {len(df)} Einträge")
    print(f"  Zeitraum: {ts_min} bis {ts_max}")
    print(f"  Intervall: {interval:.0f}s = {interval/60:.0f} min")

    if df["import"].notna().any():
        imp = df["import"].dropna()
        print(f"  Import: min={imp.min():.4f}, max={imp.max():.4f}, mean={imp.mean():.4f}")
    else:
        print(f"  Import: keine Daten")

    if df["export"].notna().any():
        exp = df["export"].dropna()
        print(f"  Export: min={exp.min():.4f}, max={exp.max():.4f}, mean={exp.mean():.4f}")
    else:
        print(f"  Export: keine Daten (nur NULL)")

conn.close()
