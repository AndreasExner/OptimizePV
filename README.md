# Pre-Version

*Dies ist eine Vorabversion und ausschließlich zu Entwicklungszwecken verfügbar*

*Installiere diese Version NICHT, wenn Du nicht genau weißt, was Du tust!*

# OptimizePV

Lokale ML-basierte Optimierung einer privaten PV-Anlage. Maximiert den Eigenverbrauch durch intelligente Batterie- und Ladesteuerung – komplett lokal, ohne Cloud, lauffähig auf Raspberry Pi 4 als Home Assistant Add-on.

## Features

- **Daten-Collector**: Sammelt PV-, Batterie-, Grid- und Verbrauchsdaten über Home Assistant (5-Min-Intervall)
- **ML-Prognose PV**: LightGBM-Modell sagt PV-DC-Modulleistung voraus (stündlich, 24/36h)
- **ML-Prognose Verbrauch**: Zweites Modell für Hausverbrauch (Haushalt + WP)
- **Optimierung**: Empfehlungen für Batterie und EV basierend auf PV-Überschuss und Strompreis
- **Dashboard**: Chart mit PV-Prognose, Verbrauch, Globalstrahlung und Börsenstrompreis
- **HA Add-on**: Installierbar als Home Assistant Add-on (Docker, Multi-Arch)

## Architektur

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
│  (SQLite DB)  │         │  (Stündliche Aggregation)  │
└──────────────┘         └────────────┬─────────────┘
                                      │
                                      ▼
                            ┌─────────────────┐
                            │  pv_forecast.py  │
                            │   (LightGBM)     │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  optimizer.py    │
                            │ (Ladestrategie)  │
                            └────────┬────────┘
                                     │
                                     ▼
                                evcc REST API
                            (Batterie, Loadpoints)
```

## Installation

### Als Home Assistant Add-on

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. Repository-URL hinzufügen: `https://github.com/AndreasExner/OptimizePV`
3. Add-on **OptimizePV** installieren und starten

Der HA-Zugang (Token) wird automatisch vom Supervisor bereitgestellt.

### Lokale Entwicklung (Windows/Linux)

```bash
git clone https://github.com/AndreasExner/OptimizePV.git
cd OptimizePV
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Konfiguration

`.env` erstellen (siehe `.env.example`):

```env
# Home Assistant
HA_URL=http://<ha-ip>:8123
HA_TOKEN=<long-lived-access-token>

# evcc (Steuerung)
EVCC_URL=http://<evcc-ip>:7070

# Standort (für Wetter-API)
LATITUDE=<your-latitude>
LONGITUDE=<your-longitude>
```

### Collector starten

```bash
python -m src.main collect              # Standard (5 Min Intervall)
python -m src.main collect --interval 60 # Kürzeres Intervall
python -m src.main status               # Statistiken anzeigen
```

## Datenquellen

| Quelle | Connector | Daten |
|---|---|---|
| Home Assistant | `ha_connector.py` | PV, Batterie, Grid, Verbrauch (direkte Sensoren) |
| Eigene SQLite-DB | `collector.py` | Langzeit-Aufzeichnung aller Messwerte + Zählerstände |
| Open-Meteo | `weather_connector.py` | Strahlung, Temperatur, Bewölkung (Forecast + Archiv) |
| evcc | `evcc_connector.py` | Steuerung: Batterie-Modus, EV-Laden, Smart-Cost |
| aWATTar | `price_connector.py` | Day-Ahead-Marktpreise (optional) |

## Sensor-Mapping

Die HA-Sensoren werden über `sensors.yaml` konfiguriert (nicht im Code). Beim ersten Start wird `/data/sensors.yaml` aus den Defaults generiert. Anpassungen per SSH oder Samba:

```yaml
# /data/sensors.yaml (Auszug)
power:
  pv_ac: "sensor.inverter_wirkleistung"
  pv_dc: "sensor.inverter_eingangsleistung"
  battery_soc: "sensor.battery_1_batterieladung"
  battery_power: "sensor.battery_1_lade_entladeleistung"
  grid_power: "sensor.power_meter_wirkleistung"
  wp_power_a: "sensor.shelly_warmepumpe_channel_a_power"
  # ...
energy:
  pv_total: "sensor.inverter_gesamtenergieertrag"
  grid_import: "sensor.power_meter_verbrauch"
  # ...
```

Unterstützte Geräte:

- **PV-Wechselrichter**: AC-Leistung + DC-Eingangsleistung + Gesamtertrag
- **Batterie**: SoC + Lade-/Entladeleistung + Lade-/Entladezähler
- **Smartmeter/Grid**: Leistung + Import/Export-Zähler
- **Wärmepumpe**: Leistung pro Phase + Energie (3-phasig)
- **EV-Charger**: Leistung + Energiezähler

### Berechnete Werte

- **Home-Verbrauch**: `inverter_wirkleistung + grid_power - wp - ev` (AC-Bus-Bilanz)
- **PV-Modulleistung**: `pv_dc_power` direkt vom Wechselrichter (DC, vor WR-Begrenzung)

### Vorzeichen-Konvention

| Sensor | pos = | neg = |
|---|---|---|
| `grid_power` | Netzbezug | Einspeisung |
| `battery_power` | Laden | Entladen |

## ML-Modelle

### PV-Ertragsprognose
- **Algorithmus**: LightGBM Regressor
- **Target**: `pv_dc_kwh` – DC-Eingangsleistung der Module (stündlich)
- **Features**: Sonneneinstrahlung (GHI, DNI, DHI), Temperatur, Bewölkung, Tageszeit, Lag/Rolling
- **Modellgröße**: < 1 MB (Pi4-kompatibel)

### Verbrauchsprognose
- **Target**: `home_kwh` – Hausverbrauch inkl. WP (ohne EV)
- **Features**: Tageszeit, Wochentag, Temperatur, Lag/Rolling
- Beide Modelle werden für die 24/36h Vorhersage kombiniert

## Projektstruktur

```
OptimizePV/
├── config.yaml                      # HA Add-on Konfiguration
├── Dockerfile                       # Docker Build (Multi-Arch)
├── run.sh                           # Add-on Entry-Point
├── repository.json                  # HA Add-on Repository
├── sensors.yaml.default             # Default Sensor-Mapping
├── src/
│   ├── config.py                    # Konfiguration (lädt sensors.yaml)
│   ├── main.py                      # CLI Entry-Point
│   ├── web.py                       # Web-UI (Flask + Waitress)
│   ├── data/
│   │   ├── ha_connector.py          # Home Assistant REST API
│   │   ├── collector.py             # Daten-Collector + SQLite-DB
│   │   ├── evcc_connector.py        # evcc REST API (Steuerung)
│   │   ├── weather_connector.py     # Open-Meteo Wetter-API
│   │   └── price_connector.py       # aWATTar / Tibber Preise
│   ├── features/
│   │   └── feature_engineering.py   # Feature-Pipeline
│   ├── models/
│   │   └── pv_forecast.py           # LightGBM Modell
│   └── optimization/
│       └── optimizer.py             # Ladestrategie
├── notebooks/                       # Jupyter Notebooks (Entwicklung)
├── data/                            # Lokale Daten (nicht im Repo)
├── models/                          # Gespeicherte Modelle
├── tests/                           # Tests
├── requirements.txt
└── docker-compose.yml               # Lokale Entwicklung
```

## Lizenz

MIT
