# PV Optimierung

## Zusammenfassung
Dieses Projekt optimiert den Eigenverbrauch privater PV-Anlagen. Insbesondere soll die Einspeisung zu Zeiten niedriger oder negativer Strompreise reduziert werden, indem das Laden von Hausbatterien und EV in diese Zeiten verschoben wird. Priorität hat der optimierte Eigenverbrauch.

Das Reduzieren der Einspeisung zu Zeiten niedriger oder negativer Strompreise soll aus zwei Gründen erfolgen:
- Ertragsmaximierung bei dynamischen Tarifen
- Reduzierung der Netzlast / Einspeisevergütung als Beitrag zur Versorgungssicherheit

## Projektschritte

1. Erstellung eines ML-Modells zur Optimierung der PV-Anlage ✅
2. Lauffähiger Demo-Code (Daten-Collector + HA Add-on) ✅
3. Training mit Collector-Daten + Weiterentwicklung ⬜

## Architektur: Hybrid HA + evcc

```
Home Assistant (Datenquelle)         Open-Meteo API
     │                                    │
     ▼                                    ▼
┌──────────────┐              ┌──────────────────┐
│ ha_connector  │              │ weather_connector │
└──────┬───────┘              └────────┬─────────┘
       │                               │
       ▼                               ▼
┌──────────────┐         ┌──────────────────────────┐
│  collector    │────────→│  feature_engineering.py   │
│  (SQLite DB)  │         └────────────┬─────────────┘
└──────────────┘                       │
                                       ▼
                             ┌─────────────────┐
                             │  pv_forecast.py  │
                             │   (LightGBM)     │
                             └────────┬────────┘
                                      │
                                      ▼
                             ┌─────────────────┐
                             │  optimizer.py    │
                             └────────┬────────┘
                                      │
                                      ▼
                                 evcc REST API
                             (Batterie, Loadpoints)
```

- **Daten lesen**: Home Assistant REST API → direkte Geräte-Sensoren (Huawei WR, Shelly, go-e)
- **Steuern**: evcc REST API → Batterie-Modus, EV-Laden, Smart-Cost
- **HA Add-on**: Docker-Container auf HA OS mit Web-UI (Ingress)

## Vorgaben und Regeln

- Primäres Ziel: Optimierung Eigenverbrauch
- Sekundäres Ziel: Reduzierung der Einspeisung während Phasen mit negativem Strompreis
- ML-Modell ohne Cloud lauffähig
- Hardware: x86 oder Raspberry Pi 4+
- Datenquelle: Home Assistant (direkte Sensoren), evcc als Fallback
- Steuerung: evcc REST API
- Entwicklung: Windows, VS Code, Python
- Unabhängig von PV-Hardware-Herstellern durch konfigurierbare Sensoren

## Funktionen

- **Daten-Collector**: Periodisches Abfragen von HA-Sensoren (alle 5 Min) und Speichern in eigener SQLite-DB
- **Sensor-Mapping**: Konfigurierbar über sensors.yaml (PV, Batterie, Grid, WP, EV + Zählerstände)
- **ML-Training**: LightGBM-Modell für PV-Modulleistungsprognose (Target: pv_module_kwh)
- **Optimierung**: Regelbasierte Batterie- und Ladesteuerung unter Berücksichtigung der Hardware-Limits
- **Web-UI**: Status-Panel und Daten-Grid über HA Ingress
- **Steuerung**: Batterie-Modi, EV-Ladepläne und Smart-Cost-Limits über evcc REST API

## PV-Anlagen-Spezifikationen

| Komponente | Spezifikation |
|---|---|
| Module | 13,4 kWp |
| Wechselrichter | Huawei SUN2000-10KTL, max 10 kW AC |
| Batterie | 10 kWh, max 5 kW Laden/Entladen |
| Smartmeter | Huawei DTSU666-H |
| Wallbox | go-e Charger HOMEfix |
| Wärmepumpe | Vaillant flexoTHERM (gemessen per Shelly 3EM)

## Erkenntnisse

- evcc speichert keine PV-Erzeugungshistorie → eigener Daten-Collector nötig
- HA History nur ~24h Detaildaten verfügbar → Collector löst Langzeit-Aufzeichnung
- Stromtarif ist Festpreis (kein dynamischer Tarif) → Fokus auf Eigenverbrauch
- Home-Verbrauch wird berechnet: `inverter_wirkleistung + grid_power - wp - ev`
- PV-Modulleistung = DC-Eingangsleistung (direkt vom WR, nicht WR-begrenzt)
- Grid-Vorzeichen: Huawei pos=Export → invertiert zu pos=Bezug
- Batterie-Vorzeichen: Huawei pos=Laden → beibehalten