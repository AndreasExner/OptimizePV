import requests
r24 = requests.get("http://localhost:8099/api/forecast?hours=24")
r36 = requests.get("http://localhost:8099/api/forecast?hours=36")
d24 = r24.json()
d36 = r36.json()
print(f"24h: {len(d24.get('forecast', []))} Eintraege")
print(f"36h: {len(d36.get('forecast', []))} Eintraege")
