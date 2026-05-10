"""Prüfe Zeitraum der verfügbaren Daten."""
import sys
sys.path.insert(0, "d:/GitHub/OptimizePV")
import requests

url = "http://192.168.66.20:7070/api/history/energy"
r = requests.get(url, timeout=10)
groups = r.json()
for g in groups:
    name = g.get("name", "")
    data = g.get("data", [])
    if data:
        first = data[0]["start"]
        last = data[-1]["end"]
        print(f"{name}: {len(data)} entries, {first} bis {last}")
    else:
        print(f"{name}: leer")

# Sessions
r2 = requests.get("http://192.168.66.20:7070/api/sessions", timeout=10)
sessions = r2.json()
print(f"\nSessions: {len(sessions)}")
if sessions:
    oldest = sessions[-1]
    newest = sessions[0]
    print(f"Aelteste: {oldest['created']}")
    print(f"Neueste:  {newest['created']}")
