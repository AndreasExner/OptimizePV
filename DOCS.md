# OptimizePV – HA Add-on

PV-Optimierung mit ML-basierter Ertragsprognose für Home Assistant.

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. Repository-URL hinzufügen: `https://github.com/AndreasExner/OptimizePV`
3. Add-on **OptimizePV** installieren und starten
4. **„In Seitenleiste anzeigen“** aktivieren für Web-UI Zugriff

## Konfiguration

### Add-on Optionen (HA UI)

| Option | Default | Beschreibung |
|---|---|---|
| `evcc_url` | `http://192.168.66.20:7070` | URL der evcc-Instanz (für Steuerung) |
| `collector_interval` | `300` | Datensammlung alle N Sekunden (60–3600) |
| `log_level` | `INFO` | Log-Level (DEBUG, INFO, WARNING, ERROR) |

Der HA-Zugang (Token) wird automatisch vom Supervisor bereitgestellt.

### Sensor-Mapping (sensors.yaml)

Beim ersten Start wird `/data/sensors.yaml` aus den Defaults generiert.
Die Datei ordnet HA-Sensoren den Datenpunkten zu und kann per SSH/Samba angepasst werden:

```yaml
power:
  pv_ac: "sensor.inverter_wirkleistung"        # WR AC-Ausgang
  pv_dc: "sensor.inverter_eingangsleistung"     # DC Module
  battery_soc: "sensor.battery_1_batterieladung"
  battery_power: "sensor.battery_1_lade_entladeleistung"
  grid_power: "sensor.power_meter_wirkleistung"
  wp_power_a: "sensor.shelly_warmepumpe_channel_a_power"
  wp_power_b: "sensor.shelly_warmepumpe_channel_b_power"
  wp_power_c: "sensor.shelly_warmepumpe_channel_c_power"
  ev_power: "sensor.goe_111927_nrg_11"

energy:
  pv_total: "sensor.inverter_gesamtenergieertrag"
  pv_daily: "sensor.inverter_tagesertrag"
  grid_import: "sensor.power_meter_verbrauch"
  grid_export: "sensor.power_meter_exportierte_energie"
  battery_charge: "sensor.battery_gesamtladung"
  battery_discharge: "sensor.battery_gesamtentladung"
  wp_energy_a: "sensor.shelly_warmepumpe_channel_a_energy"
  wp_energy_b: "sensor.shelly_warmepumpe_channel_b_energy"
  wp_energy_c: "sensor.shelly_warmepumpe_channel_c_energy"
  ev_total: "sensor.goe_111927_eto"
```

Nicht benötigte Sensoren können mit `""` deaktiviert werden.

## Web-UI

Das Web-UI ist über die HA-Seitenleiste oder über **Add-on → Open Web UI** erreichbar:

- **Status-Cards**: PV, Batterie, Grid, Home, Wärmepumpe, EV, Collector-Status
- **Messwerte-Tab**: Alle Tabellenspalten der measurements-Tabelle
- **Collector Log-Tab**: Erfolgs-/Fehlerprotokoll
- **Zeilenauswahl**: 50, 200, 1000 oder alle Zeilen
- Auto-Refresh alle 30 Sekunden

## Daten

Alle gesammelten Daten werden in `/data/optimizepv.db` (SQLite) gespeichert.
Die Datenbank bleibt bei Add-on-Updates erhalten.

### Gesammelte Datenpunkte

| Gruppe | Leistung (W) | Zählerstände (kWh) |
|---|---|---|
| PV | AC-Ausgang + DC-Module | Gesamtertrag + Tagesertrag |
| Batterie | SoC + Lade-/Entladeleistung | Gesamt-Ladung + -Entladung |
| Grid | Netzleistung | Import + Export |
| Home | Berechnet (AC-Bus-Bilanz) | – |
| Wärmepumpe | 3 Phasen summiert | 3 Phasen einzeln |
| EV | Ladeleistung | Lademenge gesamt |

### Berechnete Werte

- **Home**: `inverter_wirkleistung + grid_power - wp_power - ev_power`
- **Grid**: Vorzeichen invertiert (Huawei: pos=Export → Projekt: pos=Bezug)

## CLI (im Container)

```bash
# Status prüfen
docker exec addon_ba10a5b3_optimizepv python -m src.main status

# DB abfragen
docker exec addon_ba10a5b3_optimizepv python -c "
import sqlite3
conn = sqlite3.connect('/data/optimizepv.db')
for r in conn.execute('SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 5'):
    print(r)
"
