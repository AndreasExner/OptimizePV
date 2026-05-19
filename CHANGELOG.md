# Changelog

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
