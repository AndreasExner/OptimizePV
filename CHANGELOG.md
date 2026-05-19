# Changelog

## 0.8.0

- Forecast-Scheduler: Stündlich zur vollen Stunde, Ergebnisse in DB gespeichert
- Retraining-Scheduler: Wöchentlich Montag 00:30 UTC, Ergebnisse in DB protokolliert
- Training-Historie: Neue DB-Tabelle mit R², MAE, RMSE, Baseline, Feature Importance
- Web-UI: Neue Seite "Modell-Historie" mit KPIs, Trend-Charts, Feature Importance
- Web-UI: Neue Seite "Forecast-DB" mit Tabelle und manuellem Forecast-Button
- Web-UI: Manuelles Training und Forecast per Button auslösbar
- Web-UI: Navigation auf allen Seiten vollständig (4 Menüpunkte)
- Web-UI: Timestamps in deutschem Kurzformat
- Verbrauchsmodell: LightGBM für home_kwh, in Forecast integriert
- Empfehlungen berücksichtigen Verbrauch (PV − Haus = Überschuss)
- Dashboard: Verbrauchslinie im Chart, Überschuss-Spalte
- Umschaltbar 24h/36h Forecast
- DB Schema v7: forecasts + training_history Tabellen

## 0.7.2

- Verbessertes Logging: Modell-Pfade und Vorhersage-Status im Forecast
- Debug: Existenz-Check für Modell-Dateien im Log

## 0.7.1

- CLI: `retrain` Befehl zum Trainieren der Modelle auf dem Zielsystem
- Modelle werden in /data/models/ gespeichert (persistentes Volume auf HA)
- MODELS_DIR per Umgebungsvariable konfigurierbar

## 0.7.0

- Verbrauchsmodell (home_kwh): LightGBM Prognose des Hausverbrauchs
- Forecast berücksichtigt jetzt Verbrauch bei Empfehlungen
- Dashboard: Verbrauchslinie im Chart, Überschuss-Spalte in Tabelle
- Umschaltbar zwischen 24h und 36h Vorhersage (Dropdown)
- Fix: NaN-Preise bei 36h korrekt als null serialisiert
- KPI: Timestamps in deutschem Kurzformat (TT.MM.JJ HH:MM)
- KPI: Trainings-Zeitpunkt angezeigt
- Empfehlungen mit Begründung: PV − Haus = Überschuss

## 0.6.0

- Rolling 24h Vorhersage mit PV DC, Wetter und Strompreisen
- Forecast-Service: Wetter (Open-Meteo) + ML-Modell + aWATTar Preise
- Dashboard: Chart.js Grafik (PV DC Balken, GHI Linie, Preis Linie)
- Empfehlungstabelle: Batterie, EV, Begründung pro Stunde
- Negative Strompreise werden erkannt und empfohlen
- Auto-Refresh Forecast alle 5 Minuten

## 0.5.1

- Web-UI: Dashboard als Hauptseite (Status, Collector, Training KPIs)
- Web-UI: Collector-View als Unterseite (/collector)
- Fix: Collector KPI zeigt 24h-Stats + Gesamt-Zähler
- Training-KPI liest R²/MAE aus gespeichertem Modell
- Navigation zwischen Dashboard und Collector

## 0.5.0

- Neues ML-Modell: Target pv_dc_kwh (DC-Modulleistung direkt vom WR)
- Training mit Collector-Daten (7 Tage, 2046 Messwerte)
- Performance: MAE=0.55 kWh, R²=0.73, +38% vs. Baseline
- Feature Engineering: pv_dc_power in stündlicher Aggregation
- Anlagen-Analyse: WR-Clipping, Batterie-Auslastung, Optimierungspotenzial
- Notebook 04: Training mit Collector-Daten

## 0.4.2

- Web-UI: DB Download-Button in der Toolbar
- Backup der Datenbank direkt aus dem Browser

## 0.4.1

- Lint-Warnungen bereinigt (unused imports, fehlende encoding)
- Dokumentation aktualisiert (README, DOCS, Projektbeschreibung, Planschritte)

## 0.4.0

- Sensor-Mapping aus sensors.yaml (konfigurierbar, nicht mehr hardcoded)
- sensors.yaml.default wird beim ersten Start generiert
- PyYAML als Dependency

## 0.3.0

- Fix: Home-Berechnung korrigiert (AC-Bus-Bilanz: WR + Grid - WP - EV)
- pv_dc_power: DC-Eingangsleistung der Module hinzugefügt
- DB Schema v5

## 0.2.1

- Fix: Startup – DB sofort initialisieren (Healthcheck)
- Fix: HEALTHCHECK Zeiteinheit (600s)
- Fix: run.sh CRLF → LF, Shebang auf /bin/sh
- Waitress Production Server statt Flask dev server

## 0.2.0

- Web-UI: Status-Panel + Daten-Grid (Flask Ingress)
- HA Add-on Struktur im Repo-Root
- config.yaml mit Ingress und Sidebar-Panel

## 0.1.0

- Initiales Release
- Daten-Collector: HA-Sensoren (PV, Batterie, Grid, WP, EV)
- Zählerstände für exakte Energieberechnung
- evcc-Fallback bei HA-Ausfall
- ML-Modell: LightGBM PV-Modulleistungsprognose (vorbereitet)
