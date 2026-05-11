"""Analysiere evcc.db Struktur und Inhalt."""
import sqlite3

conn = sqlite3.connect("evcc.db")
cursor = conn.cursor()

# Alle Tabellen
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
print("=== Tabellen ===")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cursor.fetchone()[0]
    print(f"  {t}: {count} Zeilen")

print()
for t in tables:
    cursor.execute(f"PRAGMA table_info([{t}])")
    cols = cursor.fetchall()
    col_names = [c[1] for c in cols]
    print(f"=== {t} ({', '.join(col_names)}) ===")

    # Zeitraum
    for time_col in ["created", "start", "timestamp"]:
        if time_col in col_names:
            cursor.execute(f"SELECT MIN([{time_col}]), MAX([{time_col}]) FROM [{t}]")
            mi, ma = cursor.fetchone()
            print(f"  Zeitraum ({time_col}): {mi} bis {ma}")
            break

    # Erste Zeile
    cursor.execute(f"SELECT * FROM [{t}] LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"  Beispiel:")
        for name, val in zip(col_names, row):
            v = str(val)[:80] if val is not None else "NULL"
            print(f"    {name} = {v}")
    print()

conn.close()
