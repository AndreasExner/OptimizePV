# PV Optimierung

## Zusammenfassung
Dieses Projekt soll die Einspeisung privater PV Anlagen optimieren. Inbesondere soll die Einspeisung zu Zeiten negativer Strompreise reduziert werden, in dem das Laden von Hausbatterien und EV in diese Zeit verschoben werden. Priorität hat nach wie vor der optimierte Eigenverbrauch. Für die Optmierung werden die aufgezeichneten Daten der eigenen PV Anlage sowie Wetterprognose herangezogen.

## Projektschritte

1. Erstellung eines ML Modell zur Optimierung der PV Anlage ✅
2. Lauffähiger Demo-Code (Daten-Collector + Scheduler)
3. Integration als HA Add-on (Docker-Container auf HA OS)

## evcc Zugang

- Entwicklung und Test erfolgen gegen eine reale evcc-Instanz
- **Optional**: Für Entwicklung ohne Zugriff auf eine reale Instanz kann eine evcc-Demo via Docker gestartet werden (`docker-compose up -d`). Die Demo liefert simulierte Daten.

## Erkenntnisse aus Schritt 1

- evcc speichert **keine PV-Erzeugungshistorie** – PV muss aus home + grid rekonstruiert werden
- Grid-Daten (Shelly 3EM) erst ab 19.04. verfügbar, Home-Daten ab 18.02.
- Stromtarif ist Festpreis (25,86 ct/kWh), kein dynamischer Tarif
- Einspeisevergütung: 7,9 ct/kWh (konstant)
- evcc SQLite-DB enthält keine zusätzlichen Daten gegenüber REST API
- **Eigener Daten-Collector nötig** für bessere Trainingsdaten (pvPower, batteryPower, gridPower aus /api/state)

## Integrationsweg: HA Add-on

- OptimizePV läuft als Docker-Container (HA Add-on) auf HA OS
- Zugriff auf evcc über internes Netzwerk (REST API)
- Eigene SQLite-DB für gesammelte Daten (persistenter Volume-Mount)
- Konfiguration per Umgebungsvariablen
- Kein HA-spezifischer Code nötig – nur evcc REST API
- Pi4-kompatibel (ARM Docker-Image)

## Vorgaben und Regeln

- Primäres Ziel: Optimierung Eigenverbrauch
- Sekundäres Ziel: Reduzierung der Einspeisung während Phasen mit negativem Strompreis
- ML Modell ohne Cloud lauffähig
- Hardware: alte x86, Rasperry Pi 4 oder höher, oder vergleichbare Hardware
- Zielplattform: evcc (als einzige Schnittstelle zur PV-Hardware)
- Plattform für Schritt 1 und 2: beliebig, möglichst lokal in VSCODE
- Unabhängig von PV-Hardware-Herstellern: evcc abstrahiert Wechselrichter, Batterie und Wallbox

## Funktionen

- **Daten-Collector**: Periodisches Abfragen von /api/state und Speichern in eigener SQLite-DB
- Training ML mit gesammelten Daten + Wetterdaten
- Laufendes ML Training anhand aktueller Daten (z.B. täglich)
- Laufende Optimierung der Einspeisung anhand aktueller Daten aus evcc und Wetterdaten (z.B. stündlich)
- Steuerung von Batterie-Modi, EV-Ladeplänen und Smart-Cost-Limits über evcc REST API
- Laufende Optimierung der Einspeisung anhand aktueller Daten aus evcc und Wetterdaten. z.B. stündlich
- Steuerung von Batterie-Modi, EV-Ladeplänen und Smart-Cost-Limits über evcc REST API