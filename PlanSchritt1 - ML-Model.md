# Plan: PV-Optimierung – Schritt 1: ML-Modell ✅

## TL;DR
Erstellung eines lokalen ML-Modells (LightGBM) zur PV-Ertragsprognose und Lade-Optimierung. 
Initiales Training auf evcc-Daten + Wetterprognosen (Open-Meteo).
Schritt 1 ist abgeschlossen – das Modell wird in Schritt 2/3 mit besseren Collector-Daten neu trainiert.

## Kontext
- Daten: Ursprünglich nur evcc REST API, später Umstieg auf HA-Sensoren (Schritt 2)
- Entwicklung: Windows PC, VS Code, Python
- Ziel: Raspberry Pi 4 kompatibel als HA Add-on

## Status: ABGESCHLOSSEN

Das initiale Modell diente als Proof-of-Concept. Es wird durch ein neues Modell
mit korrektem Target (`pv_module_kwh`) und besseren Daten (Collector) ersetzt.

---

## Phase 1: Datenerfassung & Exploration (Foundation)

### 1.1 Projektstruktur anlegen
- Python-Projekt mit `pyproject.toml` oder `requirements.txt`
- Abhängigkeiten: `pandas`, `numpy`, `lightgbm`, `scikit-learn`, `requests`, `matplotlib`, `jupyter`
- Ordnerstruktur: `data/`, `models/`, `notebooks/`, `src/`

### 1.2 Daten-Connector: evcc (einzige Hardware-Schnittstelle)
- **REST API – Echtzeit-Daten**:
  - `GET /api/state` → pvPower, batterySoc, batteryPower, gridPower, homePower, loadpoints
  - `GET /api/tariff/grid` → Day-Ahead Strompreise mit negativen Preisen
  - `GET /api/tariff/feedin` → Einspeisevergütung
  - `GET /api/sessions` → Ladesitzungen mit Kosten
  - `GET /api/history/energy` → Energiehistorie (bis ~14 Tage)
- **REST API – Steuerung**:
  - `POST /api/batterymode/{normal|hold|charge}` → Batterie-Modus
  - `POST /api/batterydischargecontrol/{true|false}` → Entladekontrolle
  - `POST /api/batterygridchargelimit/{value}` → Netzladung Batterie
  - `POST /api/buffersoc/{value}` / `POST /api/prioritysoc/{value}` → Batterie-SoC-Grenzen
  - `POST /api/smartcostlimit/{value}` → Preisschwelle für günstiges Laden
  - `POST /api/loadpoints/{id}/mode/{off|now|minpv|pv}` → EV-Lademodus
  - `POST /api/loadpoints/{id}/plan/energy/{kwh}/{time}` → Ladeplan
- **SQLite-DB (evcc.db) – OPTIONAL, nur bei lokalem Zugriff**:
  - Tabelle `sessions`: Ladesitzungen mit charged_kwh, solar, price
  - Zugriff über `sqlite3` für Training mit > 14 Tage Historie
  - Pfad konfigurierbar via `EVCC_DB_PATH` in `.env`
  - **Nicht nutzbar bei Remote-Installationen** (z.B. HA OS) – SQLite ist dateibasiert, kein Netzwerkzugriff möglich
  - Die REST API (`/api/sessions`, `/api/history/energy`) liefert ebenfalls die volle Historie und ist die bevorzugte Datenquelle
- **Hinweis**: Battery-Mode hat 60s Watchdog → Optimizer muss Modus regelmäßig erneuern

### 1.4 Daten-Connector: Wetter (Open-Meteo)
- API: `https://api.open-meteo.com/v1/forecast` (kostenlos, kein API-Key)
- Parameter: `shortwave_radiation`, `direct_radiation`, `diffuse_radiation`, `cloud_cover`, `temperature_2m`
- Standort-Koordinaten konfigurierbar
- Historische Wetterdaten: `https://archive-api.open-meteo.com/v1/archive` für Training

### 1.5 Daten-Connector: Strompreise
- aWATTar API: `GET https://api.awattar.de/v1/marketdata` (kostenlos, kein Key)
- Oder Tibber GraphQL API (falls Tibber-Kunde)
- Day-Ahead-Preise inkl. negativer Preise in EUR/MWh

### 1.6 Explorative Datenanalyse (Jupyter Notebook)
- Daten laden, bereinigen, visualisieren
- Korrelation PV-Ertrag ↔ Sonneneinstrahlung analysieren
- Tages-/Wochen-/Saisonmuster identifizieren
- Negative Strompreis-Perioden identifizieren und Häufigkeit bestimmen
- Datenqualität prüfen (Lücken, Ausreißer)

---

## Phase 2: Feature Engineering & Modelltraining

### 2.1 Feature Engineering
- Zeitfeatures: `hour_of_day`, `day_of_year`, `month`, `weekday`
- Wetter: `shortwave_radiation`, `direct_radiation`, `cloud_cover`, `temperature`
- Lag-Features: `pv_power_t-1`, `pv_power_t-24` (gleiche Stunde Vortag)
- Rolling-Features: gleitender Durchschnitt PV-Leistung (3h, 6h)
- Strompreis: aktueller Preis, Preis nächste Stunden, Flag negativ

### 2.2 ML-Modell: PV-Ertragsprognose
- **Modell**: LightGBM Regressor (leichtgewichtig, schnell auf Pi4)
- **Target**: PV-Leistung nächste 1-24 Stunden
- **Train/Test Split**: Zeitbasiert (z.B. letzte 7 Tage als Test)
- **Metriken**: MAE, RMSE, R²
- **Baseline**: Persistence-Modell (Ertrag = gleiche Stunde gestern)
- Modellgröße validieren (Ziel: < 20 MB)

### 2.3 Optimierungslogik
- Regelbasierte Optimierung auf Basis der Prognose:
  - **Eigenverbrauch maximieren**: Batterie laden wenn PV > Verbrauch
  - **Negative Preise**: Bei prognostizierten negativen Preisen → Batterie aus Netz laden, EV laden
  - **Einspeisung verschieben**: Batterie-Entladung in Hochpreis-Zeiten verschieben
- Optimierungshorizont: 24 Stunden voraus (Day-Ahead)
- Entscheidungsmatrix: Wann laden/entladen basierend auf Prognose + Preis

### 2.4 Modell-Persistenz & Retraining
- Modell speichern mit `joblib` (~5-20 MB)
- Retraining-Pipeline: täglich oder stündlich mit neuen Daten
- Validierung nach jedem Retraining (Performance-Monitoring)

---

## Phase 3: Evaluation & Dokumentation

### 3.1 Backtesting
- Optimierung auf historischen Daten simulieren
- Vergleich: Ohne Optimierung vs. mit Optimierung
- Metriken: Eigenverbrauchsquote, vermiedene negative Einspeisung, Kosteneinsparung

### 3.2 Dokumentation
- README.md: Setup, Konfiguration, Datenquellen
- Architektur-Diagramm
- Ergebnisse des Backtestings

---

## Relevante Dateien (zu erstellen)

- `requirements.txt` — Python-Abhängigkeiten
- `src/data/evcc_connector.py` — evcc Daten-Connector (REST API + SQLite)
- `src/data/weather_connector.py` — Open-Meteo Wetter-Connector
- `src/data/price_connector.py` — Strompreis-Connector (aWATTar/Tibber)
- `src/features/feature_engineering.py` — Feature-Erstellung
- `src/models/pv_forecast.py` — LightGBM Modell Training & Inference
- `src/optimization/optimizer.py` — Optimierungslogik
- `src/config.py` — Konfiguration (URLs, Koordinaten, Sensor-IDs)
- `notebooks/01_data_exploration.ipynb` — Explorative Analyse
- `notebooks/02_model_training.ipynb` — Modell-Entwicklung
- `tests/` — Unit-Tests für Connectoren und Modell

## Verification ✅

1. **Daten-Connectoren**: Verifiziert gegen reale evcc-Instanz (192.168.66.20:7070) ✅
2. **Open-Meteo API**: 1944 Stunden historische Wetterdaten für Standort 53.31°N, 7.58°E ✅
3. **Modell-Performance**: MAE = 0.84 kWh, R² = 0.80 (Ziel: > 0.7) ✅
4. **Modellgröße**: 0.12 MB (Ziel: < 20 MB) ✅
5. **Inference-Zeit**: < 1ms (LightGBM, gemessen auf Windows) ✅
6. **Backtesting**: Eigenverbrauchsquote +4 PP, Autarkiequote +13.9 PP, ~124 EUR/Jahr Einsparung ✅

## Entscheidungen

- **ML Framework**: LightGBM (nicht TensorFlow/PyTorch — zu groß für Pi4)
- **Wetter-API**: Open-Meteo (kostenlos, kein Key, beste Solardaten für Deutschland via DWD ICON)
- **Preis-API**: aWATTar (kostenlos, einfach) — Tibber als Alternative falls bereits Kunde
- **Datenquelle**: Ausschließlich evcc (REST API + SQLite-DB für Historie)
- **Hardware-Abstraktion**: evcc abstrahiert Wechselrichter, Batterie, Wallbox → herstellerunabhängig
- **Kein Cloud-Dienst**: Alles lokal, wie in Projektbeschreibung gefordert

## Offene Punkte (gelöst)

1. **Historische Daten-Menge**: evcc REST API liefert `home` ab 18.02. (7072 Einträge), `grid` erst ab 19.04. (1347 Einträge). SQLite-DB enthält keine zusätzlichen Daten. PV-Erzeugung wird nicht gespeichert → eigener Daten-Collector nötig (Schritt 2)
2. **Battery-Mode Watchdog**: 60s-Erneuerung im Optimizer vorgesehen
3. **Sponsor-Token**: Für aktuelle Funktionalität nicht erforderlich
4. **evcc API-Format**: Daten werden direkt geliefert (kein `result`-Wrapper), Battery/Grid sind genested → Connector angepasst
5. **Stromtarif**: Festpreis 25,86 ct/kWh, Einspeisevergütung 7,9 ct/kWh → Fokus auf Eigenverbrauch statt dynamische Preise
