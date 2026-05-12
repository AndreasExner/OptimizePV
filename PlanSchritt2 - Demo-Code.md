# Plan: PV-Optimierung – Schritt 2: Lauffähiger Demo-Code ✅

## TL;DR
Daten-Collector sammelt Echtzeit-Daten von Home Assistant, verpackt als HA Add-on 
mit Web-UI (Flask Ingress). evcc bleibt für die Steuerung zuständig.

## Kontext
- Schritt 1 abgeschlossen: LightGBM-Modell (Proof-of-Concept), Connectoren, Backtesting
- Architektur-Entscheidung: **HA für Daten, evcc für Steuerung** (Hybrid)
- evcc speichert keine PV-Erzeugungshistorie → eigener Daten-Collector nötig
- HA History nur ~24h Detaildaten → Collector löst Langzeit-Aufzeichnung

## Status: ABGESCHLOSSEN

---

## Phase 1: Daten-Collector ✅

### 1.1 Eigene Datenbank (SQLite) ✅
- Tabelle `measurements`: Alle Leistungswerte (W) + Zählerstände (kWh) + pv_dc_power
- Tabelle `collector_log`: Erfolgs-/Fehlerprotokoll mit Response-Zeiten
- Schema-Migrationen (v1→v5) für inkrementelle Updates
- Pfad konfigurierbar via `DATA_DB_PATH`

### 1.2 Collector-Service ✅
- **Primär**: HA REST API (direkte Geräte-Sensoren, kein evcc für Messdaten)
- **Fallback**: evcc REST API bei HA-Ausfall
- Intervall konfigurierbar (Default: 5 Min)
- Fehlertoleranz: Retry mit Backoff, konsekutive Fehler-Warnung
- Vorzeichen normalisiert: Grid pos=Bezug, Batterie pos=Laden
- Home-Verbrauch berechnet: `inverter_wirkleistung + grid - wp - ev`

### 1.3 Sensor-Mapping ✅
- Konfigurierbar über `sensors.yaml` (nicht hardcoded)
- Default-Datei `sensors.yaml.default` wird beim ersten Start generiert
- Benutzer kann Sensoren per SSH/Samba in `/data/sensors.yaml` anpassen
- 19 Sensoren: Leistung (9) + Zählerstände (10)

### Gesammelte Datenpunkte
| Gruppe | Felder |
|---|---|
| PV | pv_power (AC), pv_dc_power (DC Module), pv_energy_total, pv_energy_daily |
| Batterie | battery_soc, battery_power, battery_charge_total, battery_discharge_total |
| Grid | grid_power, grid_import_total, grid_export_total |
| Home | home_power (berechnet) |
| WP | wp_power (3 Phasen summiert), wp_energy_a/b/c |
| EV | ev_power, ev_energy_total |

---

## Phase 2: HA Add-on ✅

### 2.1 Docker ✅
- Dockerfile: Universal (Alpine via BUILD_FROM / Debian als Fallback)
- Multi-Arch: amd64 + aarch64
- Healthcheck mit start-period
- CRLF→LF Fix im Dockerfile (sed)

### 2.2 HA Add-on Struktur ✅
- `config.yaml`: Add-on Konfiguration, Ingress, homeassistant_api
- `run.sh`: Entry-Point, liest /data/options.json, generiert sensors.yaml
- `repository.json`: HA Add-on Repository
- `build_from` direkt in config.yaml (build.yaml deprecated)

### 2.3 Web-UI ✅
- Flask + Waitress (Production Server)
- HA Ingress auf Port 8099
- Status-Cards: PV, Batterie, Grid, Home, WP, EV, Collector-Status
- Daten-Grid: Measurements + Collector Log, konfigurierbare Zeilenanzahl
- Auto-Refresh Status alle 30s

### 2.4 CLI ✅
- `python -m src.main collect` → Daten-Collector starten
- `python -m src.main status` → Collector-Statistiken anzeigen
- `--log-level`, `--interval` Parameter

---

## Phase 3: ML-Anpassungen ✅

### 3.1 Target: pv_module_kwh ✅
- Modulleistung = inverter_wirkleistung + max(0, battery_charge_power)
- Tatsächliche DC-Leistung der Module (bis 13,4 kWp), nicht WR-begrenzt
- Alternativ: pv_dc_power direkt vom WR (sensor.inverter_eingangsleistung)

### 3.2 Feature Engineering ✅
- `build_training_from_collector()`: Nutzt eigene DB statt evcc
- `build_hourly_from_collector()`: 5-Min → stündlich mit Zählerstand-Differenzen
- Lag/Rolling-Features auf pv_module_kwh
- Mindestens 6 Samples pro Stunde für vollständige Aggregation

### 3.3 Optimizer ✅
- Modulleistung auf AC (max 10kW) und Batterie (max 5kW) aufgeteilt
- `available_for_loads_kwh`: Verfügbar für WP/EV parallel zur Batterieladung
- Hardware-Limits aus PV_SPECS in config.py

---

## Verification ✅

1. **Collector**: Läuft auf HA OS, 0% Fehlerrate, alle Sensoren korrekt ✅
2. **AC-Bus-Bilanz**: WR_out = Home + WP + EV + Grid_Export (geht exakt auf) ✅
3. **DC-Bilanz**: PV_DC ≈ PV_AC + Bat_Charge (< 50W Verluste) ✅
4. **Docker**: Container baut und startet auf HA OS (amd64) ✅
5. **Web-UI**: Erreichbar über HA Ingress ✅
6. **Sensor-Mapping**: 19 Sensoren aus sensors.yaml geladen ✅

## Entscheidungen

- **HA statt evcc für Daten**: Direkte Geräte-Sensoren sind genauer als evcc-Aggregation
- **evcc für Steuerung**: Bewährte Ladelogik beibehalten
- **sensors.yaml**: Konfigurierbar, keine Defaults im Code
- **Waitress**: Production WSGI Server statt Flask dev server
- **pv_module_kwh als Target**: Modulleistung vor WR-Begrenzung für Optimierung
- **Home berechnet**: Keine eigene Messung, aus AC-Bus-Bilanz abgeleitet

## Nächste Schritte

1. **Training**: ~7 Tage Collector-Daten → neues Modell mit pv_module_kwh Target
2. **Scheduler**: Stündliche Prognose + Optimierungsplan (noch nicht implementiert)
3. **Retraining-Pipeline**: Tägliches automatisches Retraining
4. **Battery-Mode Watchdog**: 60s-Erneuerung im Live-Betrieb
