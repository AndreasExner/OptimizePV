# Pre-Version

*Dies ist eine Vorabversion und ausschließlich zu Entwicklungszwecken verfügbar*
*Installiere diese Version NICHT, wenn Du nicht genau weißt, was Du tust!*

# OptimizePV

Lokale ML-basierte Optimierung einer privaten PV-Anlage. Maximiert den Eigenverbrauch durch intelligente Batterie- und Ladesteuerung – komplett lokal, ohne Cloud, lauffähig auf Raspberry Pi 4 als Home Assistant Add-on.

## Features

- **Daten-Collector**: Sammelt PV-, Batterie-, Grid- und Verbrauchsdaten über Home Assistant
- **ML-Prognose**: LightGBM-Modell sagt PV-Modulleistung voraus (stündlich, 24h voraus)
- **Optimierung**: Regelbasierte Batterie- und Ladesteuerung via evcc
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

Die HA-Sensoren werden in `src/config.py` zugeordnet und können per `.env` überschrieben werden. Unterstützte Geräte:

- **PV-Wechselrichter**: Leistung (W) + Gesamtertrag (kWh)
- **Batterie**: SoC (%) + Lade-/Entladeleistung (W) + Zählerstände
- **Smartmeter/Grid**: Leistung (W) + Import/Export-Zähler (kWh)
- **Wärmepumpe**: Leistung pro Phase (W) + Energie (kWh)
- **EV-Charger**: Leistung (W) + Energiezähler (kWh)

## ML-Modell

- **Algorithmus**: LightGBM Regressor
- **Target**: `pv_module_kwh` – Stündliche PV-Modulleistung (DC, vor WR-Begrenzung)
- **Berechnung**: `Modulleistung = WR-Ausgangsleistung + Batterie-Ladeleistung`
- **Features**: Sonneneinstrahlung, Temperatur, Bewölkung, Tageszeit, Lag/Rolling-Statistiken
- **Modellgröße**: < 1 MB (Pi4-kompatibel)

## Projektstruktur

```
OptimizePV/
├── config.yaml                      # HA Add-on Konfiguration
├── Dockerfile                       # Docker Build (Multi-Arch)
├── run.sh                           # Add-on Entry-Point
├── repository.json                  # HA Add-on Repository
├── src/
│   ├── config.py                    # Zentrale Konfiguration + Sensor-Mapping
│   ├── main.py                      # CLI Entry-Point
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
