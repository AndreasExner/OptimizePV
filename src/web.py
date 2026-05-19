"""OptimizePV Web-UI.

Einfaches Status-Panel und Daten-Grid für das HA Add-on (Ingress).
"""

import os
import sqlite3

from flask import Flask, jsonify, render_template_string, request

from src.config import DATA_DB_PATH

app = Flask(__name__)

# Ingress-Pfad: HA leitet /api/hassio_ingress/<token>/ hierher
INGRESS_PATH = os.getenv("INGRESS_PATH", "")


def _get_db():
    """Gibt eine DB-Verbindung zurück."""
    conn = sqlite3.connect(str(DATA_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OptimizePV</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #1c1c1c; color: #e0e0e0; padding: 16px; }
        h1 { font-size: 1.4em; margin-bottom: 12px; color: #ffa726; }
        h2 { font-size: 1.1em; margin: 16px 0 8px; color: #90caf9; }

        .status-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 10px; margin-bottom: 16px;
        }
        .card {
            background: #2a2a2a; border-radius: 8px; padding: 14px;
            border-left: 4px solid #555;
        }
        .card.pv { border-left-color: #ffa726; }
        .card.battery { border-left-color: #66bb6a; }
        .card.grid { border-left-color: #ef5350; }
        .card.home { border-left-color: #42a5f5; }
        .card.wp { border-left-color: #ab47bc; }
        .card.ev { border-left-color: #26c6da; }
        .card.info { border-left-color: #78909c; }
        .card .label { font-size: 0.75em; color: #999; text-transform: uppercase; }
        .card .value { font-size: 1.6em; font-weight: 600; margin: 4px 0; }
        .card .unit { font-size: 0.7em; color: #888; }

        .tabs { display: flex; gap: 4px; margin-bottom: 8px; }
        .tab { padding: 6px 14px; background: #333; border: none; color: #aaa;
               border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.85em; }
        .tab.active { background: #2a2a2a; color: #fff; }

        .table-wrap { overflow-x: auto; max-height: 70vh; overflow-y: auto; }
        table { border-collapse: collapse; width: 100%; font-size: 0.8em; }
        th { background: #333; position: sticky; top: 0; padding: 6px 10px;
             text-align: left; white-space: nowrap; cursor: pointer; }
        th:hover { background: #444; }
        td { padding: 5px 10px; border-bottom: 1px solid #333; white-space: nowrap; }
        tr:hover td { background: #333; }
        .num { text-align: right; font-variant-numeric: tabular-nums; }

        .collector-ok { color: #66bb6a; }
        .collector-err { color: #ef5350; }
        .refresh-btn { background: #333; border: 1px solid #555; color: #ccc;
                       padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em; }
        .refresh-btn:hover { background: #444; }
        .toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
        select { background: #333; color: #ccc; border: 1px solid #555;
                 padding: 4px 8px; border-radius: 4px; font-size: 0.85em; }
        .ts { color: #888; font-size: 0.75em; }
    </style>
</head>
<body>
    <h1>⚡ OptimizePV</h1>

    <!-- Status Cards -->
    <div class="status-grid" id="status-cards">
        <div class="card info"><div class="label">Laden...</div></div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
        <button class="tab active" onclick="switchTab('measurements')">Messwerte</button>
        <button class="tab" onclick="switchTab('collector_log')">Collector Log</button>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
        <select id="row-limit" onchange="loadTable()">
            <option value="50">50 Zeilen</option>
            <option value="200">200 Zeilen</option>
            <option value="1000">1000 Zeilen</option>
            <option value="0">Alle</option>
        </select>
        <button class="refresh-btn" onclick="loadAll()">↻ Aktualisieren</button>
        <a class="refresh-btn" id="download-link" style="text-decoration:none">⬇ DB Download</a>
        <span class="ts" id="last-update"></span>
    </div>

    <!-- Data Grid -->
    <div class="table-wrap">
        <table id="data-table">
            <thead><tr><th>Laden...</th></tr></thead>
            <tbody></tbody>
        </table>
    </div>

    <script>
    const BASE = window.location.pathname.replace(/\\/$/, '');
    let currentTab = 'measurements';

    function switchTab(tab) {
        currentTab = tab;
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        event.target.classList.add('active');
        loadTable();
    }

    async function loadStatus() {
        const resp = await fetch(BASE + '/api/status');
        const data = await resp.json();
        const cards = document.getElementById('status-cards');

        if (!data.latest) {
            cards.innerHTML = '<div class="card info"><div class="label">Keine Daten</div></div>';
            return;
        }

        const l = data.latest;
        const s = data.collector;
        const fmt = (v, dec=0) => v != null ? Number(v).toFixed(dec) : '–';
        const fmtW = (v) => {
            if (v == null) return '–';
            return Math.abs(v) >= 1000 ? (v/1000).toFixed(1) + ' <span class="unit">kW</span>'
                                       : Math.round(v) + ' <span class="unit">W</span>';
        };

        cards.innerHTML = `
            <div class="card pv">
                <div class="label">PV Leistung</div>
                <div class="value">${fmtW(l.pv_power)}</div>
                <div class="ts">Tagesertrag: ${fmt(l.pv_energy_daily,1)} kWh</div>
            </div>
            <div class="card battery">
                <div class="label">Batterie</div>
                <div class="value">${fmt(l.battery_soc,0)}%</div>
                <div class="ts">${fmtW(l.battery_power)} ${l.battery_power > 0 ? '↑ Laden' : l.battery_power < 0 ? '↓ Entladen' : ''}</div>
            </div>
            <div class="card grid">
                <div class="label">Grid</div>
                <div class="value">${fmtW(l.grid_power)}</div>
                <div class="ts">${l.grid_power > 0 ? '↓ Bezug' : l.grid_power < 0 ? '↑ Einspeisung' : 'Ausgeglichen'}</div>
            </div>
            <div class="card home">
                <div class="label">Hausverbrauch</div>
                <div class="value">${fmtW(l.home_power)}</div>
            </div>
            <div class="card wp">
                <div class="label">Wärmepumpe</div>
                <div class="value">${fmtW(l.wp_power)}</div>
            </div>
            <div class="card ev">
                <div class="label">EV Laden</div>
                <div class="value">${fmtW(l.ev_power)}</div>
            </div>
            <div class="card info">
                <div class="label">Collector</div>
                <div class="value ${s.error_rate < 5 ? 'collector-ok' : 'collector-err'}">${s.ok} <span class="unit">OK</span></div>
                <div class="ts">${s.errors} Fehler (${s.error_rate.toFixed(1)}%)</div>
            </div>
        `;
    }

    async function loadTable() {
        const limit = document.getElementById('row-limit').value;
        const resp = await fetch(BASE + '/api/table/' + currentTab + '?limit=' + limit);
        const data = await resp.json();
        const table = document.getElementById('data-table');

        if (!data.columns || !data.rows.length) {
            table.innerHTML = '<thead><tr><th>Keine Daten</th></tr></thead><tbody></tbody>';
            return;
        }

        const numCols = new Set(['pv_power','battery_soc','battery_power','grid_power',
            'home_power','wp_power','ev_power','pv_energy_total','pv_energy_daily',
            'grid_import_total','grid_export_total','battery_charge_total',
            'battery_discharge_total','wp_energy_total','ev_energy_total',
            'response_ms','loadpoint_power']);

        let html = '<thead><tr>';
        data.columns.forEach(c => html += `<th>${c}</th>`);
        html += '</tr></thead><tbody>';

        data.rows.forEach(row => {
            html += '<tr>';
            data.columns.forEach((c, i) => {
                const cls = numCols.has(c) ? ' class="num"' : '';
                let val = row[i];
                if (val == null) val = '';
                else if (numCols.has(c) && typeof val === 'number') val = Number(val).toFixed(2);
                html += `<td${cls}>${val}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody>';
        table.innerHTML = html;

        document.getElementById('last-update').textContent =
            'Aktualisiert: ' + new Date().toLocaleTimeString('de-DE');
    }

    function loadAll() {
        loadStatus(); loadTable();
        document.getElementById('download-link').href = BASE + '/api/download';
    }
    loadAll();
    setInterval(loadStatus, 30000);
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/api/status")
def api_status():
    """Liefert aktuelle Werte und Collector-Statistiken."""
    db = _get_db()
    try:
        # Letzter Messwert
        row = db.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        latest = dict(row) if row else None

        # Collector-Stats (letzte 24h)
        stats = db.execute(
            """SELECT status, COUNT(*) as cnt FROM collector_log
               WHERE timestamp >= datetime('now', '-24 hours')
               GROUP BY status"""
        ).fetchall()
        counts = {r["status"]: r["cnt"] for r in stats}
        total = sum(counts.values())
        ok = counts.get("ok", 0)
        errors = counts.get("error", 0) + counts.get("timeout", 0)

        return jsonify({
            "latest": latest,
            "collector": {
                "total": total, "ok": ok, "errors": errors,
                "error_rate": errors / total * 100 if total > 0 else 0,
            },
        })
    finally:
        db.close()


@app.route("/api/table/<table_name>")
def api_table(table_name):
    """Liefert Tabellendaten als JSON (Spalten + Zeilen)."""
    # Whitelist: nur erlaubte Tabellen
    allowed = {"measurements", "collector_log"}
    if table_name not in allowed:
        return jsonify({"error": "Tabelle nicht erlaubt"}), 400

    limit = request.args.get("limit", "50", type=str)
    limit_clause = f"LIMIT {int(limit)}" if limit != "0" else ""

    db = _get_db()
    try:
        rows = db.execute(
            f"SELECT * FROM [{table_name}] ORDER BY timestamp DESC {limit_clause}"
        ).fetchall()

        if not rows:
            return jsonify({"columns": [], "rows": []})

        columns = list(rows[0].keys())
        data = [list(row) for row in rows]

        return jsonify({"columns": columns, "rows": data})
    finally:
        db.close()


@app.route("/api/download")
def api_download():
    """Liefert die SQLite-DB als Download."""
    from flask import send_file
    db_path = str(DATA_DB_PATH)
    if not DATA_DB_PATH.exists():
        return jsonify({"error": "Datenbank nicht gefunden"}), 404
    return send_file(
        db_path,
        mimetype="application/x-sqlite3",
        as_attachment=True,
        download_name="optimizepv.db",
    )


def run_web(host: str = "0.0.0.0", port: int = 8099):
    """Startet den Web-Server (Waitress Production Server)."""
    from waitress import serve
    serve(app, host=host, port=port, threads=2)


if __name__ == "__main__":
    run_web()
