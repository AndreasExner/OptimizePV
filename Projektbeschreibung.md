# PV Optimierung

## Zusammenfassung
Dieses Projekt soll die Einspeisung privater PV Anlagen optimieren. Inbesondere soll die Einspeisung zu Zeiten negativer Strompreise reduziert werden, in dem das Laden von Hausbatterien und EV in diese Zeit verschoben werden. Priorität hat nach wie vor der optimierte Eigenverbrauch. Für die Optmierung werden die aufgezeichneten Daten der eigenen PV Anlage sowie Wetterprognose herangezogen.

## Projektschritte

1. Erstellung eines ML Modell zur Optimierung der PV Anlage
2. Lauffähiger demo code
3. Integration in evcc

## Vorgaben und Regeln

- Primäres Ziel: Optimierung Eigenverbrauch
- Sekundäres Ziel: Reduzierung der Einspeisung während Phasen mit negativem Strompreis
- ML Modell ohne Cloud lauffähig
- Hardware: alte x86, Rasperry Pi 4 oder höher, oder vergleichbare Hardware
- Zielplattform: evcc (als einzige Schnittstelle zur PV-Hardware)
- Plattform für Schritt 1 und 2: beliebig, möglichst lokal in VSCODE
- Unabhängig von PV-Hardware-Herstellern: evcc abstrahiert Wechselrichter, Batterie und Wallbox

## Funktionen

- Traing ML mit historischen Daten aus evcc (SQLite-DB) und Wetter Daten (optional, wenn Anlage neu oder Daten nicht verfügbar)
- Laufendes ML Training anhand aktueller Daten aus evcc (REST API) und Wetterdaten. z.B. stündlich
- Laufende Optimierung der Einspeisung anhand aktueller Daten aus evcc und Wetterdaten. z.B. stündlich
- Steuerung von Batterie-Modi, EV-Ladeplänen und Smart-Cost-Limits über evcc REST API