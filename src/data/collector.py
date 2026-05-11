"""Daten-Collector: Sammelt Echtzeit-Daten in eigene SQLite-DB.

Primäre Datenquelle: Home Assistant (HA) REST API
Fallback: evcc REST API

HA liefert direkte Sensordaten vom Wechselrichter, Stromzähler und
Wärmepumpe – genauer als die evcc-Aggregation.
"""

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.config import (
    DATA_DB_PATH, EVCC_URL, COLLECTOR_INTERVAL, COLLECTOR_RETRY_DELAY,
    HA_SENSORS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS measurements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'ha',
    -- Momentanleistung (W)
    pv_power    REAL,
    battery_soc REAL,
    battery_power REAL,
    grid_power  REAL,
    home_power  REAL,   -- berechnet: PV + Bat_Entladung + Grid_Import - Bat_Ladung - Grid_Export
    wp_power    REAL,   -- Summe 3 Phasen
    ev_power    REAL,
    -- Zählerstände (kWh, kumulativ)
    pv_energy_total          REAL,
    pv_energy_daily          REAL,
    grid_import_total        REAL,
    grid_export_total        REAL,
    battery_charge_total     REAL,
    battery_discharge_total  REAL,
    wp_energy_total          REAL,   -- Summe 3 Phasen
    ev_energy_total          REAL,
    -- Sonstiges
    battery_mode TEXT,
    vehicle_connected INTEGER,
    loadpoint_power REAL
);

CREATE INDEX IF NOT EXISTS idx_measurements_ts ON measurements(timestamp);

CREATE TABLE IF NOT EXISTS collector_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    status      TEXT    NOT NULL,  -- 'ok', 'error', 'timeout'
    source      TEXT    NOT NULL DEFAULT 'ha',
    message     TEXT,
    response_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_collector_log_ts ON collector_log(timestamp);

CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Datenbank-Zugriff
# ---------------------------------------------------------------------------


def init_db(db_path: Path | None = None) -> Path:
    """Initialisiert die Datenbank und erstellt/migriert Tabellen.

    Returns:
        Pfad zur Datenbank.
    """
    db_path = db_path or DATA_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)

        # Schema-Version prüfen/setzen
        cur = conn.execute("SELECT COUNT(*) FROM schema_info")
        if cur.fetchone()[0] == 0:
            conn.execute("INSERT INTO schema_info (version) VALUES (?)", (SCHEMA_VERSION,))
        else:
            cur = conn.execute("SELECT version FROM schema_info")
            old_version = cur.fetchone()[0]
            if old_version < SCHEMA_VERSION:
                _migrate_db(conn, old_version)
                conn.execute("UPDATE schema_info SET version = ?", (SCHEMA_VERSION,))

    logger.info("Datenbank initialisiert: %s", db_path)
    return db_path


def _migrate_db(conn: sqlite3.Connection, from_version: int) -> None:
    """Migriert die DB von einer älteren Version."""
    if from_version < 2:
        # v2: source-Spalte, wp_power, ev_power hinzufügen
        for col, typ in [("source", "TEXT DEFAULT 'evcc'"),
                         ("wp_power", "REAL"), ("ev_power", "REAL")]:
            try:
                conn.execute(f"ALTER TABLE measurements ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass  # Spalte existiert bereits
        try:
            conn.execute("ALTER TABLE collector_log ADD COLUMN source TEXT DEFAULT 'evcc'")
        except sqlite3.OperationalError:
            pass
        logger.info("DB migriert: v%d → v2", from_version)
    if from_version < 3:
        # v3: Zählerstände hinzufügen
        for col in ["pv_energy_total", "pv_energy_daily",
                     "grid_import_total", "grid_export_total", "wp_energy_total"]:
            try:
                conn.execute(f"ALTER TABLE measurements ADD COLUMN {col} REAL")
            except sqlite3.OperationalError:
                pass
        logger.info("DB migriert: v%d → v3", from_version)
    if from_version < 4:
        # v4: battery_charge/discharge_total, ev_energy_total hinzufügen
        for col in ["battery_charge_total", "battery_discharge_total", "ev_energy_total"]:
            try:
                conn.execute(f"ALTER TABLE measurements ADD COLUMN {col} REAL")
            except sqlite3.OperationalError:
                pass
        logger.info("DB migriert: v%d → v4", from_version)


def store_measurement(data: dict, db_path: Path | None = None) -> None:
    """Speichert einen Messwert in der Datenbank."""
    db_path = db_path or DATA_DB_PATH

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """INSERT INTO measurements
               (timestamp, source, pv_power, battery_soc, battery_power,
                grid_power, home_power, wp_power, ev_power,
                pv_energy_total, pv_energy_daily,
                grid_import_total, grid_export_total,
                battery_charge_total, battery_discharge_total,
                wp_energy_total, ev_energy_total,
                battery_mode, vehicle_connected, loadpoint_power)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["timestamp"],
                data.get("source", "ha"),
                data.get("pv_power"),
                data.get("battery_soc"),
                data.get("battery_power"),
                data.get("grid_power"),
                data.get("home_power"),
                data.get("wp_power"),
                data.get("ev_power"),
                data.get("pv_energy_total"),
                data.get("pv_energy_daily"),
                data.get("grid_import_total"),
                data.get("grid_export_total"),
                data.get("battery_charge_total"),
                data.get("battery_discharge_total"),
                data.get("wp_energy_total"),
                data.get("ev_energy_total"),
                data.get("battery_mode"),
                data.get("vehicle_connected"),
                data.get("loadpoint_power"),
            ),
        )


def store_log(status: str, message: str = "", response_ms: int = 0,
              source: str = "ha", db_path: Path | None = None) -> None:
    """Speichert einen Collector-Log-Eintrag."""
    db_path = db_path or DATA_DB_PATH
    ts = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO collector_log (timestamp, status, source, message, response_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, status, source, message, response_ms),
        )


def get_measurements(hours: int = 24, db_path: Path | None = None):
    """Liest Messwerte der letzten N Stunden als DataFrame.

    Returns:
        pandas DataFrame mit Messwerten.
    """
    import pandas as pd

    db_path = db_path or DATA_DB_PATH
    if not db_path.exists():
        return pd.DataFrame()

    query = """
        SELECT * FROM measurements
        WHERE timestamp >= datetime('now', ?)
        ORDER BY timestamp
    """

    with sqlite3.connect(str(db_path)) as conn:
        df = pd.read_sql_query(query, conn, params=(f"-{hours} hours",))

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def get_collector_stats(hours: int = 24, db_path: Path | None = None) -> dict:
    """Liefert Collector-Statistiken der letzten N Stunden."""
    db_path = db_path or DATA_DB_PATH
    if not db_path.exists():
        return {"total": 0, "ok": 0, "errors": 0, "error_rate": 0}

    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute(
            """SELECT status, COUNT(*) FROM collector_log
               WHERE timestamp >= datetime('now', ?)
               GROUP BY status""",
            (f"-{hours} hours",),
        )
        counts = dict(cur.fetchall())

    total = sum(counts.values())
    ok = counts.get("ok", 0)
    errors = counts.get("error", 0) + counts.get("timeout", 0)
    return {
        "total": total,
        "ok": ok,
        "errors": errors,
        "error_rate": errors / total * 100 if total > 0 else 0,
    }


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


def collect_once(db_path: Path | None = None) -> dict | None:
    """Fragt HA ab (Fallback: evcc) und speichert das Ergebnis.

    Returns:
        Dict mit Messwerten oder None bei Fehler.
    """
    # Primär: Home Assistant
    data = _collect_from_ha(db_path)
    if data is not None:
        return data

    # Fallback: evcc
    logger.info("HA nicht verfügbar – Fallback auf evcc")
    return _collect_from_evcc(db_path)


def _collect_from_ha(db_path: Path | None = None) -> dict | None:
    """Sammelt Daten von Home Assistant – direkt von den Geräten, ohne evcc."""
    from src.data.ha_connector import get_site_snapshot

    ts = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()

    try:
        values = get_site_snapshot(HA_SENSORS)
        response_ms = int((time.monotonic() - start) * 1000)
    except requests.exceptions.Timeout:
        response_ms = int((time.monotonic() - start) * 1000)
        logger.warning("HA Timeout nach %d ms", response_ms)
        store_log("timeout", "HA timeout", response_ms, "ha", db_path)
        return None
    except requests.exceptions.ConnectionError as e:
        response_ms = int((time.monotonic() - start) * 1000)
        logger.warning("HA nicht erreichbar: %s", e)
        store_log("error", f"HA connection error: {e}", response_ms, "ha", db_path)
        return None
    except Exception as e:
        response_ms = int((time.monotonic() - start) * 1000)
        logger.error("HA Fehler: %s", e)
        store_log("error", str(e), response_ms, "ha", db_path)
        return None

    # --- Vorzeichen normalisieren ---
    # Grid: Huawei liefert positiv = Einspeisung, negativ = Bezug.
    # Konvention: positiv = Bezug, negativ = Einspeisung → invertieren.
    grid_raw = values.get("grid_power")
    grid_power = -grid_raw if grid_raw is not None else None

    # Batterie: Huawei liefert positiv = Laden, negativ = Entladen → passt.
    battery_power = values.get("battery_power")

    # --- Summierungen ---
    # WP-Leistung: Summe 3 Phasen (Shelly 3EM)
    wp_vals = [values.get(f"wp_power_{p}") for p in "abc"]
    wp_power = sum(v for v in wp_vals if v is not None) if any(v is not None for v in wp_vals) else None

    # WP-Energie: Summe 3 Phasen
    wp_e_vals = [values.get(f"wp_energy_{p}") for p in "abc"]
    wp_energy = sum(v for v in wp_e_vals if v is not None) if any(v is not None for v in wp_e_vals) else None

    # EV-Leistung (go-e liefert direkt in W)
    ev_power = values.get("ev_power")

    # --- Home-Verbrauch berechnen ---
    # Home = PV + Bat_Entladung + Grid_Bezug
    # Mit Vorzeichen: Home = PV - Battery_Power + Grid_Power
    # (battery_power pos=Laden verbraucht PV, grid_power pos=Bezug liefert Strom)
    pv = values.get("pv_power") or 0
    bat = battery_power or 0
    grd = grid_power or 0
    home_power = pv - bat + grd  # PV minus Batterieladung plus Netzbezug
    if home_power < 0:
        home_power = 0  # Kann durch Messungenauigkeiten leicht negativ werden

    data = {
        "timestamp": ts,
        "source": "ha",
        "pv_power": values.get("pv_power"),
        "battery_soc": values.get("battery_soc"),
        "battery_power": battery_power,
        "grid_power": grid_power,
        "home_power": home_power,
        "wp_power": wp_power,
        "ev_power": ev_power,
        # Zählerstände
        "pv_energy_total": values.get("pv_energy_total"),
        "pv_energy_daily": values.get("pv_energy_daily"),
        "grid_import_total": values.get("grid_import_total"),
        "grid_export_total": values.get("grid_export_total"),
        "battery_charge_total": values.get("battery_charge_total"),
        "battery_discharge_total": values.get("battery_discharge_total"),
        "wp_energy_total": wp_energy,
        "ev_energy_total": values.get("ev_energy_total"),
        "battery_mode": None,
        "vehicle_connected": None,
        "loadpoint_power": ev_power,
    }

    store_measurement(data, db_path)
    store_log("ok", f"PV={data['pv_power']}", response_ms, "ha", db_path)

    logger.debug(
        "[HA] PV=%.0fW, Bat=%s%% (%.0fW), Grid=%.0fW, Home=%.0fW, WP=%.0fW, EV=%.0fW [%dms]",
        data["pv_power"] or 0,
        data["battery_soc"] or "?",
        data["battery_power"] or 0,
        data["grid_power"] or 0,
        data["home_power"] or 0,
        data["wp_power"] or 0,
        data["ev_power"] or 0,
        response_ms,
    )
    return data


def _collect_from_evcc(db_path: Path | None = None) -> dict | None:
    """Sammelt Daten von evcc (Fallback)."""
    ts = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()

    try:
        resp = requests.get(f"{EVCC_URL}/api/state", timeout=10)
        response_ms = int((time.monotonic() - start) * 1000)
        resp.raise_for_status()
        state = resp.json()
    except Exception as e:
        response_ms = int((time.monotonic() - start) * 1000)
        logger.error("evcc Fallback fehlgeschlagen: %s", e)
        store_log("error", f"evcc fallback: {e}", response_ms, "evcc", db_path)
        return None

    battery = state.get("battery", {})
    grid = state.get("grid", {})
    loadpoints = state.get("loadpoints", [])
    lp_power = sum(lp.get("chargePower", 0) for lp in loadpoints)

    # evcc battery_power: positiv = Entladung (Energie aus Batterie).
    # Konvention im Projekt: positiv = Laden (wie Huawei) → invertieren.
    bat_raw = battery.get("power")
    bat_normalized = -bat_raw if bat_raw is not None else None
    # evcc grid_power: positiv = Bezug → gleiche Konvention, keine Änderung.

    data = {
        "timestamp": ts,
        "source": "evcc",
        "pv_power": state.get("pvPower"),
        "battery_soc": battery.get("soc"),
        "battery_power": bat_normalized,
        "grid_power": grid.get("power"),
        "home_power": state.get("homePower"),
        "wp_power": None,
        "ev_power": lp_power,
        "battery_mode": state.get("batteryMode"),
        "vehicle_connected": 1 if any(lp.get("connected", False) for lp in loadpoints) else 0,
        "loadpoint_power": lp_power,
    }

    store_measurement(data, db_path)
    store_log("ok", f"PV={data['pv_power']} (evcc fallback)", response_ms, "evcc", db_path)

    logger.debug(
        "[evcc] PV=%.0fW, Bat=%d%% (%.0fW), Grid=%.0fW, Home=%.0fW [%dms]",
        data["pv_power"] or 0, data["battery_soc"] or 0,
        data["battery_power"] or 0, data["grid_power"] or 0,
        data["home_power"] or 0, response_ms,
    )
    return data


def run_collector(
    db_path: Path | None = None,
    interval: int | None = None,
) -> None:
    """Startet den Collector als Endlosschleife.

    Primär: Home Assistant, Fallback: evcc.

    Args:
        db_path: Datenbank-Pfad. Default aus Config.
        interval: Abfrage-Intervall in Sekunden. Default aus Config.
    """
    interval = interval or COLLECTOR_INTERVAL
    db_path = db_path or DATA_DB_PATH

    init_db(db_path)
    logger.info("Collector gestartet: HA→evcc Fallback, interval=%ds, db=%s",
                interval, db_path)

    consecutive_errors = 0

    while True:
        result = collect_once(db_path)

        if result is None:
            consecutive_errors += 1
            if consecutive_errors >= 5:
                logger.warning(
                    "%d aufeinanderfolgende Fehler – HA und evcc nicht erreichbar?",
                    consecutive_errors,
                )
            wait = min(interval, COLLECTOR_RETRY_DELAY * consecutive_errors)
        else:
            if consecutive_errors > 0:
                logger.info("Datenquelle wieder erreichbar nach %d Fehlern", consecutive_errors)
            consecutive_errors = 0
            wait = interval

        time.sleep(wait)
