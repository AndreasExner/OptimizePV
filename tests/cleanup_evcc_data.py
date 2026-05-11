"""Bereinige alte evcc-Einträge aus der DB."""
import sqlite3

conn = sqlite3.connect("data/optimizepv.db")
cur = conn.cursor()

# Zähle Einträge nach Quelle
cur.execute("SELECT source, COUNT(*) FROM measurements GROUP BY source")
print("Vor Bereinigung:")
for row in cur.fetchall():
    label = row[0] if row[0] else "NULL (alt/evcc)"
    print(f"  {label}: {row[1]} Eintraege")

cur.execute("SELECT source, COUNT(*) FROM collector_log GROUP BY source")
print("\nCollector Log:")
for row in cur.fetchall():
    label = row[0] if row[0] else "NULL (alt/evcc)"
    print(f"  {label}: {row[1]} Eintraege")

# Lösche evcc- und NULL-Einträge
cur.execute("DELETE FROM measurements WHERE source IS NULL OR source = 'evcc'")
m_deleted = cur.rowcount
cur.execute("DELETE FROM collector_log WHERE source IS NULL OR source = 'evcc'")
l_deleted = cur.rowcount
conn.commit()

print(f"\nGeloescht: {m_deleted} measurements, {l_deleted} log-Eintraege")

# Nachher
cur.execute("SELECT source, COUNT(*) FROM measurements GROUP BY source")
print("\nNach Bereinigung:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} Eintraege")

conn.close()
