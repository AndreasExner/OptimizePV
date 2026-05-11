# Plan: PV-Optimierung – Schritt 2: Lauffähiger Demo-Code

## TL;DR
Aus dem ML-Modell (Schritt 1) wird ein lauffähiger Service: 
Daten-Collector sammelt Echtzeit-Daten, Scheduler steuert Prognose + Optimierung, 
alles verpackt als Docker-Container (Vorbereitung für HA Add-on in Schritt 3).

## Kontext
- Schritt 1 abgeschlossen: LightGBM-Modell (R²=0.80), Connectoren, Backtesting
- Hauptproblem: evcc speichert keine PV-Erzeugungshistorie → eigener Daten-Collector nötig
- Ziel: Eigenständiger Service, der ohne Notebooks auskommt
- Architektur: Docker-Container → später HA Add-on

---

## Phase 1: Daten-Collector

### 1.1 Eigene Datenbank (SQLite)
- Tabelle `measurements`: pvPower, batteryPower, batterySoc, gridPower, homePower, timestamp
- Tabelle `weather_cache`: Wetter-Forecast-Cache (stündlich)
- Tabelle `model_runs`: Modell-Performance-Tracking
- Pfad konfigurierbar via `DATA_DB_PATH` in `.env`
- Migrations-Logik für Schema-Updates

### 1.2 Collector-Service
- Periodisch `/api/state` abfragen (Intervall konfigurierbar, default: 5 Min)
- Werte in eigene SQLite-DB schreiben
- Fehlertoleranz: evcc-Ausfälle überbrücken (Retry, Logging)
- Leichtgewichtig: minimaler Speicher-/CPU-Verbrauch

### 1.3 Daten-Export
- Historische Daten aus eigener DB als DataFrame bereitstellen
- Nahtlose Integration mit Feature Engineering aus Schritt 1
- Übergangsphase: Eigene DB + evcc History API kombinieren (bis genug eigene Daten vorhanden)

---

## Phase 2: Scheduler & Service-Loop

### 2.1 Haupt-Scheduler
- **Alle 5 Min**: Daten-Collector (Messwerte sammeln)
- **Alle 60 Min**: PV-Prognose erstellen + Optimierungsplan berechnen
- **Alle 60s**: Battery-Mode erneuern (Watchdog)
- **Täglich (03:00)**: Modell-Retraining mit neuen Daten
- Implementierung mit `schedule` oder `asyncio`-basiert

### 2.2 Prognose-Pipeline
- Aktuelle Wetterdaten holen (Open-Meteo Forecast)
- Features berechnen (aus eigener DB + Wetter)
- Modell-Vorhersage (24h PV + Verbrauch)
- Ergebnis loggen

### 2.3 Optimierungs-Loop
- Auf Basis der Prognose: Batterie-Modus + EV-Ladestrategie bestimmen
- evcc-API-Befehle senden
- Battery-Mode-Watchdog (alle 60s erneuern)
- Dry-Run-Modus: Nur loggen, nicht steuern (für Testing)

### 2.4 Retraining-Pipeline
- Täglich: Neue Daten aus eigener DB laden
- Feature Engineering → LightGBM Training
- Performance-Vergleich: Neues vs. altes Modell
- Nur deployen wenn neues Modell besser (oder gleich gut)
- Modell-Archiv: Alte Modelle behalten

---

## Phase 3: Docker & Deployment-Vorbereitung

### 3.1 Dockerfile
- Base-Image: `python:3.12-slim` (Multi-Arch: amd64 + arm64)
- Multi-Stage Build: nur Runtime-Dependencies
- Volumes: `/data` (DB + Modelle), `/config` (.env)
- Healthcheck: evcc-Erreichbarkeit prüfen
- **Hinweis**: Docker nur für Deployment (HA OS), Entwicklung direkt im venv

### 3.2 docker-compose.yml erweitern
- OptimizePV-Service neben evcc
- Volume-Mounts für Persistenz
- Environment-Variablen für Konfiguration
- Restart-Policy: `unless-stopped`

### 3.3 CLI / Entry-Point
- `python -m src.main` → startet Service (Windows/Linux direkt oder im Container)
- Argumente: `--dry-run`, `--collect-only`, `--retrain`
- Logging: Strukturiert (JSON), Level konfigurierbar
- Graceful Shutdown (SIGTERM)

---

## Relevante Dateien (zu erstellen)

- `src/data/collector.py` — Daten-Collector + eigene SQLite-DB
- `src/scheduler.py` — Haupt-Scheduler (Collect, Predict, Optimize)
- `src/main.py` — Entry-Point / CLI
- `Dockerfile` — Docker-Image
- `docker-compose.yml` — Erweitert um OptimizePV-Service

## Verification

1. **Collector**: Sammelt min. 24h Daten fehlerfrei, DB wächst korrekt
2. **Prognose**: Pipeline liefert 24h-Forecast aus eigener DB
3. **Dry-Run**: Optimierungsplan wird erstellt und geloggt (ohne evcc-Steuerung)
4. **Docker**: Container startet, verbindet sich mit evcc, sammelt Daten
5. **Retraining**: Neues Modell wird trainiert und nur bei Verbesserung deployed
6. **Ressourcen**: < 100 MB RAM, < 5% CPU auf Pi4

## Entscheidungen

- **Daten-Collector statt evcc-DB**: evcc speichert keine PV-History → eigene Sammlung nötig
- **SQLite**: Leichtgewichtig, kein Server, passt zu Pi4
- **Scheduler statt Cron**: In-Process-Scheduling, Docker-freundlich
- **Dry-Run-Modus**: Sicheres Testen ohne Einfluss auf die Anlage
- **Docker-First**: Gleiche Umgebung für Entwicklung und HA Add-on

## Offene Punkte

1. **Mindest-Datenmenge für Retraining**: Ab wann lohnt sich eigene DB vs. evcc-History?
   → Geschätzt: nach ~7 Tagen Collector-Lauf (168 Stunden × 12 Samples = ~2000 Datenpunkte)
2. **Watchdog-Timing**: 60s reicht für Battery-Mode, aber Netzwerk-Latenz beachten
3. **HA Add-on Manifest**: Wird in Schritt 3 definiert (addon.yaml, repository)
