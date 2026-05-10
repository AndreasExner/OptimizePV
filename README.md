# OptimizePV

Lokale ML-basierte Optimierung einer privaten PV-Anlage. Maximiert den Eigenverbrauch und reduziert Einspeisung – komplett lokal, ohne Cloud, lauffähig auf Raspberry Pi 4.

## Überblick

| Metrik | Baseline | Optimiert | Δ |
|---|---|---|---|
| Eigenverbrauchsquote | 24,7% | 28,7% | **+4,0 PP** |
| Autarkiequote | 84,6% | 98,5% | **+13,9 PP** |
| Netzbezug | 31,6 kWh | 3,0 kWh | -90% |
| Einsparung (hochgerechnet) | – | – | **~124 EUR/Jahr** |

*Backtesting über 14 Tage (19.04.–03.05.2026), 10 kWh Batterie.*

## Architektur

```
evcc (REST API)          Open-Meteo API         aWATTar API
     │                        │                      │
     ▼                        ▼                      ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ evcc_connector │  │ weather_connector │   │ price_connector  │
└──────┬──────┘    └────────┬─────────┘    └────────┬────────┘
       │                    │                       │
       ▼                    ▼                       ▼
    ┌──────────────────────────────────────────────────┐
    │           feature_engineering.py                  │
    │  (PV-Rekonstruktion, Zeit/Lag/Rolling-Features)   │
    └──────────────────────┬───────────────────────────┘
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

## Setup

### Voraussetzungen
- Python 3.12+
- Zugriff auf eine evcc-Instanz (REST API)

### Installation

```bash
git clone https://github.com/your-repo/OptimizePV.git
cd OptimizePV
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### Konfiguration

`.env` erstellen (siehe `.env.example`):

```env
EVCC_URL=http://192.168.x.x:7070
LATITUDE=53.306
LONGITUDE=7.581
```

## Datenquellen

| Quelle | Connector | Daten |
|---|---|---|
| evcc REST API | `evcc_connector.py` | PV-Leistung, Batterie, Grid, Loadpoints, Sessions |
| evcc Tarife | `evcc_connector.py` | Grid-Tarif, Einspeisevergütung |
| Open-Meteo | `weather_connector.py` | Strahlung, Temperatur, Bewölkung (Forecast + Archiv) |
| aWATTar | `price_connector.py` | Day-Ahead-Marktpreise (optional) |

## Notebooks

| Notebook | Beschreibung |
|---|---|
| `01_data_exploration.ipynb` | Explorative Analyse aller Datenquellen |
| `02_model_training.ipynb` | LightGBM Training & Evaluation |
| `03_backtesting.ipynb` | Optimierungssimulation auf historischen Daten |

## ML-Modell

- **Algorithmus**: LightGBM Regressor
- **Target**: Stündliche PV-Erzeugung (kWh)
- **Features**: Sonneneinstrahlung, Temperatur, Bewölkung, Tageszeit, Lag/Rolling-Statistiken
- **Performance**: R² = 0.80, MAE = 0.84 kWh (Test), 6,3% besser als Persistence-Baseline
- **Modellgröße**: 0,12 MB (Pi4-kompatibel)
- **PV-Rekonstruktion**: `PV ≈ home_import + grid_export - grid_import` (kein direkter PV-Sensor in History)

## Projektstruktur

```
OptimizePV/
├── src/
│   ├── config.py                    # Zentrale Konfiguration
│   ├── data/
│   │   ├── evcc_connector.py        # evcc REST API (Lesen + Steuern)
│   │   ├── weather_connector.py     # Open-Meteo Wetter-API
│   │   └── price_connector.py       # aWATTar / Tibber Preise
│   ├── features/
│   │   └── feature_engineering.py   # Feature-Pipeline
│   ├── models/
│   │   └── pv_forecast.py           # LightGBM Modell
│   └── optimization/
│       └── optimizer.py             # Ladestrategie
├── notebooks/                       # Jupyter Notebooks
├── models/                          # Gespeicherte Modelle
├── data/                            # Daten-Verzeichnis
├── tests/                           # Tests
├── requirements.txt
└── docker-compose.yml               # Optional: evcc Demo
```

## Nächste Schritte (Schritt 2: Demo-Code)

1. Periodischer Scheduler (stündlich: Daten holen → Predict → Optimieren)
2. Retraining-Pipeline (täglich mit neuen Daten)
3. Battery-Mode Watchdog (60s-Erneuerung)
4. Integration in evcc als eigenständiger Service
