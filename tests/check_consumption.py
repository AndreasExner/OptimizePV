"""Prüfe welche Verbrauchsdaten die evcc API liefert."""
import requests
import json

r = requests.get("http://192.168.66.20:7070/api/state", timeout=10)
d = r.json()

print("=== Aktuelle Leistungswerte ===")
print(f"homePower:      {d.get('homePower')} W")
print(f"pvPower:        {d.get('pvPower')} W")
print(f"pvEnergy:       {d.get('pvEnergy')} kWh (Gesamtzähler)")
print(f"grid.power:     {d.get('grid', {}).get('power')} W")
print(f"grid.energy:    {d.get('grid', {}).get('energy')} kWh (Gesamtzähler)")
print(f"battery.energy: {d.get('battery', {}).get('energy')} kWh (Gesamtzähler)")

print("\n=== Statistics ===")
stats = d.get("statistics", {})
print(json.dumps(stats, indent=2, default=str)[:800])

print("\n=== Forecast Keys ===")
forecast = d.get("forecast", {})
print(f"Keys: {list(forecast.keys()) if forecast else 'keine'}")

# Home energy history - gibt es detailliertere Endpunkte?
print("\n=== Weitere Endpunkte testen ===")
for ep in ["/api/health", "/api/tariff/planner"]:
    try:
        r2 = requests.get(f"http://192.168.66.20:7070{ep}", timeout=5)
        print(f"{ep}: {r2.status_code} - {str(r2.text)[:200]}")
    except Exception as e:
        print(f"{ep}: {e}")
