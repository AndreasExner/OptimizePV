# OptimizePV – HA Add-on

PV-Optimierung mit ML-basierter Ertragsprognose für Home Assistant.

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. Repository-URL hinzufügen: `https://github.com/AndreasExner/OptimizePV`
3. Add-on **OptimizePV** installieren

## Konfiguration

| Option | Default | Beschreibung |
|---|---|---|
| `evcc_url` | `http://192.168.66.20:7070` | URL der evcc-Instanz (für Steuerung) |
| `collector_interval` | `300` | Datensammlung alle N Sekunden |
| `log_level` | `INFO` | Log-Level (DEBUG, INFO, WARNING, ERROR) |

Der HA-Zugang (Token) wird automatisch vom Supervisor bereitgestellt.

## Datenquellen

Das Add-on liest Sensordaten direkt aus Home Assistant:
- **PV**: Wechselrichter (Huawei SUN2000)
- **Batterie**: SoC und Lade-/Entladeleistung
- **Grid**: Smartmeter (Import/Export)
- **Wärmepumpe**: Shelly 3EM (3 Phasen)
- **EV**: go-e Charger

Die Sensor-Zuordnung kann über Umgebungsvariablen angepasst werden.

## Daten

Alle gesammelten Daten werden in `/data/optimizepv.db` (SQLite) gespeichert.
Die Datenbank bleibt bei Add-on-Updates erhalten.
