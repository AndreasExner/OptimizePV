# Plan: PV-Optimierung – Schritt 1: ML-Modell

## TL;DR
Erstellung eines lokalen ML-Modells (LightGBM) zur PV-Ertragsprognose und Lade-Optimierung. 
Das Modell nutzt historische Daten aus Home Assistant/evcc + Wetterprognosen (Open-Meteo) + Strompreise (Tibber/aWATTar), 
um Eigenverbrauch zu maximieren und Einspeisung bei negativen Preisen zu vermeiden. 
Entwicklung in Python auf Windows (VS Code), später lauffähig auf Raspberry Pi 4.

## Kontext
- Hardware: Huawei Wechselrichter, Hausbatterie, EV mit evcc
- Daten: evcc + Home Assistant vorhanden
- Entwicklung: Windows PC, VS Code, Python
- Ziel: Raspberry Pi 4 kompatibel

---

## Phase 1: Datenerfassung & Exploration (Foundation)

### 1.1 Projektstruktur anlegen
- Python-Projekt mit `pyproject.toml` oder `requirements.txt`
- Abhängigkeiten: `pandas`, `numpy`, `lightgbm`, `scikit-learn`, `requests`, `matplotlib`, `jupyter`
- Ordnerstruktur: `data/`, `models/`, `notebooks/`, `src/`

### 1.2 Daten-Connector: Home Assistant
- REST API Client für HA: `GET /api/history/period/<timestamp>?filter_entity_id=<ids>`
- Relevante Sensoren identifizieren (Huawei Solar Integration):
  - PV-Leistung (`sensor.huawei_inverter_active_power`)
  - Batterie-SoC (`sensor.battery_soc`)
  - Netzeinspeisung (`sensor.grid_feed_in_power`)
  - Hausverbrauch (`sensor.home_consumption`)
- Alternativ: Direktzugriff auf HA SQLite-DB (`home-assistant_v2.db`, Tabelle `statistics`)
- Daten als CSV exportieren für Offline-Analyse

### 1.3 Daten-Connector: evcc
- REST API: `GET http://<evcc>:8080/api/state` (aktueller Zustand)
- `GET /api/history/energy` (historische Energiedaten, 14 Tage)
- `GET /api/sessions` (Ladesitzungen mit Kosten)
- evcc SQLite-DB für längere Historie

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
- `src/data/ha_connector.py` — Home Assistant Daten-Connector
- `src/data/evcc_connector.py` — evcc Daten-Connector  
- `src/data/weather_connector.py` — Open-Meteo Wetter-Connector
- `src/data/price_connector.py` — Strompreis-Connector (aWATTar/Tibber)
- `src/features/feature_engineering.py` — Feature-Erstellung
- `src/models/pv_forecast.py` — LightGBM Modell Training & Inference
- `src/optimization/optimizer.py` — Optimierungslogik
- `src/config.py` — Konfiguration (URLs, Koordinaten, Sensor-IDs)
- `notebooks/01_data_exploration.ipynb` — Explorative Analyse
- `notebooks/02_model_training.ipynb` — Modell-Entwicklung
- `tests/` — Unit-Tests für Connectoren und Modell

## Verification

1. **Daten-Connectoren**: Unit-Tests mit Mock-Daten + manueller Test gegen lokale HA/evcc-Instanz
2. **Open-Meteo API**: Abruf und Validierung der Sonneneinstrahlung für eigenen Standort
3. **Modell-Performance**: MAE < 20% der mittleren PV-Leistung, R² > 0.7 auf Testdaten
4. **Modellgröße**: < 20 MB serialisiert (Pi4-kompatibel)
5. **Inference-Zeit**: < 100ms pro Vorhersage (gemessen auf Windows, extrapoliert für Pi4)
6. **Backtesting**: Eigenverbrauchsquote um mindestens 5% verbessert vs. Baseline

## Entscheidungen

- **ML Framework**: LightGBM (nicht TensorFlow/PyTorch — zu groß für Pi4)
- **Wetter-API**: Open-Meteo (kostenlos, kein Key, beste Solardaten für Deutschland via DWD ICON)
- **Preis-API**: aWATTar (kostenlos, einfach) — Tibber als Alternative falls bereits Kunde
- **Datenquelle**: Primär Home Assistant (längere Historie), evcc als Ergänzung
- **Kein Cloud-Dienst**: Alles lokal, wie in Projektbeschreibung gefordert

## Offene Punkte

1. **HA Sensor-Entity-IDs**: Die tatsächlichen Sensor-Namen hängen von der Huawei-Integration-Konfiguration ab — müssen beim Setup ermittelt werden
2. **Historische Daten-Menge**: HA Standard-Retention ist 7 Tage. Falls Recorder länger konfiguriert ist, ideal. Sonst: ab jetzt sammeln + historische Wetterdaten von Open-Meteo als Ersatz
3. **Batterie-Steuerung**: Kann evcc die Hausbatterie direkt steuern, oder nur EV-Ladung? Falls nur EV → Batterie-Steuerung muss über HA/Modbus erfolgen
