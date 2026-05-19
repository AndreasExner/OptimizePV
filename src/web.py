"""OptimizePV Web-UI.

Dashboard (Hauptseite) + Collector-Datenansicht (Unterseite).
Läuft als Flask/Waitress im HA Add-on via Ingress.
"""

import os
import sqlite3

from flask import Flask, jsonify, render_template_string, request

from src.config import DATA_DB_PATH

app = Flask(__name__)

INGRESS_PATH = os.getenv("INGRESS_PATH", "")


def _get_db():
    """Gibt eine DB-Verbindung zurück."""
    conn = sqlite3.connect(str(DATA_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Shared Styles
# ---------------------------------------------------------------------------

SHARED_STYLES = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #1c1c1c; color: #e0e0e0; padding: 16px; }
h1 { font-size: 1.4em; margin-bottom: 4px; color: #ffa726; }
h2 { font-size: 1.1em; margin: 16px 0 8px; color: #90caf9; }
a { color: #90caf9; text-decoration: none; }
a:hover { text-decoration: underline; }

.nav { font-size: 0.85em; margin-bottom: 16px; color: #888; }
.nav a { margin-right: 16px; }
.nav a.active { color: #ffa726; font-weight: 600; }

.status-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px; margin-bottom: 16px;
}
.card {
    background: #2a2a2a; border-radius: 8px; padding: 16px;
    border-left: 4px solid #555;
}
.card.ok { border-left-color: #66bb6a; }
.card.warn { border-left-color: #ffa726; }
.card.err { border-left-color: #ef5350; }
.card.pv { border-left-color: #ffa726; }
.card.battery { border-left-color: #66bb6a; }
.card.grid { border-left-color: #ef5350; }
.card.home { border-left-color: #42a5f5; }
.card.wp { border-left-color: #ab47bc; }
.card.ev { border-left-color: #26c6da; }
.card.info { border-left-color: #78909c; }
.card .label { font-size: 0.75em; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }
.card .value { font-size: 1.8em; font-weight: 600; margin: 4px 0; }
.card .sub { font-size: 0.8em; color: #888; }
.card .unit { font-size: 0.65em; color: #888; }

.btn { background: #333; border: 1px solid #555; color: #ccc;
       padding: 5px 14px; border-radius: 4px; cursor: pointer;
       font-size: 0.85em; text-decoration: none; display: inline-block; }
.btn:hover { background: #444; text-decoration: none; }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
select { background: #333; color: #ccc; border: 1px solid #555;
         padding: 4px 8px; border-radius: 4px; font-size: 0.85em; }
.ts { color: #888; font-size: 0.75em; }

.tabs { display: flex; gap: 4px; margin-bottom: 8px; }
.tab { padding: 6px 14px; background: #333; border: none; color: #aaa;
       border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.85em; }
.tab.active { background: #2a2a2a; color: #fff; }

.table-wrap { overflow-x: auto; max-height: 70vh; overflow-y: auto; }
table { border-collapse: collapse; width: 100%; font-size: 0.8em; }
th { background: #333; position: sticky; top: 0; padding: 6px 10px;
     text-align: left; white-space: nowrap; }
td { padding: 5px 10px; border-bottom: 1px solid #333; white-space: nowrap; }
tr:hover td { background: #333; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
"""


# ---------------------------------------------------------------------------
# Dashboard Template (Hauptseite)
# ---------------------------------------------------------------------------

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OptimizePV</title>
    <style>""" + SHARED_STYLES + """
    .chart-container { background: #2a2a2a; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .chart-container canvas { max-height: 350px; }
    .rec-table { width: 100%; font-size: 0.82em; margin-top: 12px; }
    .rec-table th { background: #333; padding: 6px 10px; text-align: left; white-space: nowrap; }
    .rec-table td { padding: 5px 10px; border-bottom: 1px solid #333; white-space: nowrap; }
    .rec-table tr:hover td { background: #333; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; }
    .badge-green { background: #1b5e20; color: #a5d6a7; }
    .badge-orange { background: #e65100; color: #ffcc80; }
    .badge-red { background: #b71c1c; color: #ef9a9a; }
    .badge-blue { background: #0d47a1; color: #90caf9; }
    .badge-gray { background: #424242; color: #bdbdbd; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
    <h1>⚡ OptimizePV</h1>
    <div class="nav">
        <a href="#" class="active">Dashboard</a>
        <a id="nav-collector" href="#">Collector &amp; Daten</a>
    </div>

    <div class="status-grid" id="dashboard-cards">
        <div class="card info"><div class="label">Laden...</div></div>
    </div>

    <!-- Forecast Chart -->
    <div class="chart-container">
        <div class="toolbar" style="margin-bottom:8px">
            <h2 style="margin:0">Vorhersage</h2>
            <select id="forecast-hours" onchange="loadForecast()">
                <option value="24" selected>24 Stunden</option>
                <option value="36">36 Stunden</option>
            </select>
        </div>
        <canvas id="forecast-chart"></canvas>
    </div>

    <!-- Empfehlungstabelle -->
    <div class="table-wrap" id="rec-wrap" style="display:none">
        <h2>Stündliche Empfehlungen</h2>
        <table class="rec-table" id="rec-table"></table>
    </div>

    <script>
    const BASE = window.location.pathname.replace(/\\/$/, '');
    document.getElementById('nav-collector').href = BASE + '/collector';
    let forecastChart = null;

    function fmtTs(ts) {
        if (!ts) return '–';
        const d = new Date(ts);
        return d.toLocaleDateString('de-DE', {day:'2-digit', month:'2-digit', year:'2-digit'})
             + ' ' + d.toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
    }

    async function loadDashboard() {
        const resp = await fetch(BASE + '/api/dashboard');
        const d = await resp.json();

        const cards = document.getElementById('dashboard-cards');
        const statusClass = d.addon_status === 'running' ? 'ok' : 'warn';
        const collectorClass = d.collector.error_rate < 5 ? 'ok' : (d.collector.error_rate < 20 ? 'warn' : 'err');

        let trainingHtml;
        if (d.training.r2 != null) {
            trainingHtml = `
                <div class="value">${(d.training.r2 * 100).toFixed(0)}%</div>
                <div class="sub">R² = ${d.training.r2.toFixed(3)}</div>
                <div class="sub">MAE = ${d.training.mae.toFixed(3)} kWh</div>
            `;
        } else {
            trainingHtml = '<div class="value">–</div><div class="sub">Kein Modell</div>';
        }

        cards.innerHTML = `
            <div class="card ${statusClass}">
                <div class="label">Add-on Status</div>
                <div class="value">${d.addon_status === 'running' ? '● Online' : '○ Offline'}</div>
                <div class="sub">DB: ${d.db_size_mb.toFixed(1)} MB, ${d.measurements_total} Messwerte</div>
            </div>
            <div class="card ${collectorClass}">
                <div class="label">Collector (24h)</div>
                <div class="value">${d.collector.ok} <span class="unit">OK</span></div>
                <div class="sub">${d.collector.errors} Fehler (${d.collector.error_rate.toFixed(1)}%), gesamt: ${d.collector.total_all_time}</div>
                <div class="sub">Letzte Abfrage: ${fmtTs(d.collector.last_timestamp)}</div>
            </div>
            <div class="card info">
                <div class="label">Letztes Training</div>
                ${trainingHtml}
                <div class="sub">${fmtTs(d.training.trained_at)}</div>
            </div>
        `;
    }

    async function loadForecast() {
        const chartEl = document.getElementById('forecast-chart');
        try {
            const hours = document.getElementById('forecast-hours').value;
            chartEl.style.opacity = '0.4';
            const resp = await fetch(BASE + '/api/forecast?hours=' + hours);
            const data = await resp.json();
            if (!data.forecast || !data.forecast.length) {
                console.warn('Kein Forecast:', data.error);
                return;
            }

            const fc = data.forecast;
            const showDate = parseInt(hours) > 24;
            const labels = fc.map(r => {
                const d = new Date(r.timestamp);
                const time = d.toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'});
                return showDate ? d.toLocaleDateString('de-DE', {day:'2-digit', month:'2-digit'}) + ' ' + time : time;
            });

            const ctx = document.getElementById('forecast-chart').getContext('2d');
            if (forecastChart) forecastChart.destroy();

            forecastChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'PV DC (kWh)',
                            data: fc.map(r => r.pv_dc_forecast),
                            backgroundColor: 'rgba(255, 167, 38, 0.7)',
                            borderColor: '#ffa726',
                            borderWidth: 1,
                            yAxisID: 'y',
                            order: 3,
                        },
                        {
                            label: 'Verbrauch (kWh)',
                            data: fc.map(r => r.home_forecast),
                            type: 'line',
                            borderColor: '#42a5f5',
                            backgroundColor: 'rgba(66, 165, 245, 0.1)',
                            borderWidth: 2,
                            pointRadius: 2,
                            fill: true,
                            yAxisID: 'y',
                            order: 2,
                        },
                        {
                            label: 'GHI (W/m²)',
                            data: fc.map(r => r.ghi),
                            type: 'line',
                            borderColor: '#ffcc80',
                            backgroundColor: 'transparent',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            yAxisID: 'y2',
                            order: 1,
                        },
                        {
                            label: 'Strompreis (EUR/MWh)',
                            data: fc.map(r => r.price_eur_mwh),
                            type: 'line',
                            borderColor: '#ef5350',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            pointRadius: 2,
                            yAxisID: 'y3',
                            order: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { labels: { color: '#ccc', font: { size: 11 } } },
                    },
                    scales: {
                        x: { ticks: { color: '#999', font: { size: 10 } }, grid: { color: '#333' } },
                        y: {
                            position: 'left', title: { display: true, text: 'kWh/h', color: '#ffa726' },
                            ticks: { color: '#ffa726' }, grid: { color: '#333' }, min: 0,
                        },
                        y2: {
                            position: 'right', title: { display: true, text: 'GHI (W/m²)', color: '#ffcc80' },
                            ticks: { color: '#ffcc80' }, grid: { display: false }, min: 0,
                        },
                        y3: {
                            position: 'right', title: { display: true, text: 'EUR/MWh', color: '#ef5350' },
                            ticks: { color: '#ef5350' }, grid: { display: false },
                            afterFit: (axis) => { axis.paddingRight = 10; },
                        },
                    },
                },
            });

            // Empfehlungstabelle
            const wrap = document.getElementById('rec-wrap');
            const table = document.getElementById('rec-table');
            wrap.style.display = 'block';

            const badgeClass = (action) => {
                if (action.includes('Laden') && action.includes('neg')) return 'badge-red';
                if (action.includes('Laden') || action.includes('DC')) return 'badge-green';
                if (action.includes('Entladen')) return 'badge-orange';
                if (action.includes('Netz')) return 'badge-blue';
                return 'badge-gray';
            };

            let html = '<thead><tr><th>Zeit</th><th>PV DC</th><th>Verbr.</th><th>Übersch.</th><th>Preis</th><th>Batterie</th><th>EV</th><th>Begründung</th></tr></thead><tbody>';
            fc.forEach(r => {
                const t = new Date(r.timestamp).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
                const price = r.price_eur_mwh != null ? r.price_eur_mwh.toFixed(1) : '–';
                const priceClass = r.is_negative ? 'badge-red' : 'badge-gray';
                html += `<tr>
                    <td>${t}</td>
                    <td class="num">${r.pv_dc_forecast.toFixed(1)} kWh</td>
                    <td class="num">${r.home_forecast.toFixed(1)} kWh</td>
                    <td class="num">${r.surplus.toFixed(1)} kW</td>
                    <td><span class="badge ${priceClass}">${price}</span></td>
                    <td><span class="badge ${badgeClass(r.battery_action)}">${r.battery_action}</span></td>
                    <td><span class="badge ${badgeClass(r.ev_recommendation)}">${r.ev_recommendation}</span></td>
                    <td class="ts">${r.reason}</td>
                </tr>`;
            });
            html += '</tbody>';
            table.innerHTML = html;

        } catch (e) {
            console.error('Forecast laden fehlgeschlagen:', e);
        } finally {
            document.getElementById('forecast-chart').style.opacity = '1';
        }
    }

    loadDashboard();
    loadForecast();
    setInterval(loadDashboard, 30000);
    setInterval(loadForecast, 300000); // alle 5 Min
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Collector Template (Unterseite)
# ---------------------------------------------------------------------------

COLLECTOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OptimizePV – Collector</title>
    <style>""" + SHARED_STYLES + """</style>
</head>
<body>
    <h1>⚡ OptimizePV</h1>
    <div class="nav">
        <a id="nav-dashboard" href="#">Dashboard</a>
        <a href="#" class="active">Collector &amp; Daten</a>
    </div>

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
        <button class="btn" onclick="loadAll()">↻ Aktualisieren</button>
        <a class="btn" id="download-link">⬇ DB Download</a>
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
    const BASE = window.location.pathname.replace(/\\/collector\\/?$/, '');
    document.getElementById('nav-dashboard').href = BASE + '/';
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
                <div class="sub">DC: ${fmtW(l.pv_dc_power)} | Tagesertrag: ${fmt(l.pv_energy_daily,1)} kWh</div>
            </div>
            <div class="card battery">
                <div class="label">Batterie</div>
                <div class="value">${fmt(l.battery_soc,0)}%</div>
                <div class="sub">${fmtW(l.battery_power)} ${l.battery_power > 0 ? '↑ Laden' : l.battery_power < 0 ? '↓ Entladen' : ''}</div>
            </div>
            <div class="card grid">
                <div class="label">Grid</div>
                <div class="value">${fmtW(l.grid_power)}</div>
                <div class="sub">${l.grid_power > 0 ? '↓ Bezug' : l.grid_power < 0 ? '↑ Einspeisung' : 'Ausgeglichen'}</div>
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
            <div class="card ${s.error_rate < 5 ? 'ok' : 'warn'}">
                <div class="label">Collector (24h)</div>
                <div class="value">${s.ok} <span class="unit">OK</span></div>
                <div class="sub">${s.errors} Fehler (${s.error_rate.toFixed(1)}%) | gesamt: ${s.total_all_time}</div>
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

        const numCols = new Set(['pv_power','pv_dc_power','battery_soc','battery_power','grid_power',
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
    return render_template_string(DASHBOARD_TEMPLATE)


@app.route("/collector")
@app.route("/collector/")
def collector_view():
    return render_template_string(COLLECTOR_TEMPLATE)


@app.route("/api/dashboard")
def api_dashboard():
    """Liefert Dashboard-KPIs: Status, Collector, Training."""
    import joblib
    from src.config import MODELS_DIR

    db = _get_db()
    try:
        # Collector-Stats (24h)
        stats_24h = db.execute(
            """SELECT status, COUNT(*) as cnt FROM collector_log
               WHERE timestamp >= datetime('now', '-24 hours')
               GROUP BY status"""
        ).fetchall()
        counts_24h = {r["status"]: r["cnt"] for r in stats_24h}
        total_24h = sum(counts_24h.values())
        ok_24h = counts_24h.get("ok", 0)
        errors_24h = counts_24h.get("error", 0) + counts_24h.get("timeout", 0)

        # Gesamt-Zähler
        total_all = db.execute("SELECT COUNT(*) FROM collector_log").fetchone()[0]
        measurements_total = db.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]

        # Letzte Abfrage
        last_row = db.execute(
            "SELECT timestamp FROM measurements ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        last_ts = last_row["timestamp"] if last_row else None

        # DB-Größe
        db_size_mb = DATA_DB_PATH.stat().st_size / (1024 * 1024) if DATA_DB_PATH.exists() else 0

        # Training-Infos
        model_path = MODELS_DIR / "pv_forecast.joblib"
        training = {"r2": None, "mae": None, "trained_at": None}
        if model_path.exists():
            try:
                import os
                model_data = joblib.load(model_path)
                metrics = model_data.get("metrics", {})
                training["r2"] = metrics.get("test_r2")
                training["mae"] = metrics.get("test_mae")
                # Zeitpunkt aus Datei-Änderungsdatum
                mtime = os.path.getmtime(model_path)
                from datetime import datetime, timezone
                training["trained_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            except Exception:
                pass

        return jsonify({
            "addon_status": "running",
            "db_size_mb": db_size_mb,
            "measurements_total": measurements_total,
            "collector": {
                "total_24h": total_24h, "ok": ok_24h, "errors": errors_24h,
                "error_rate": errors_24h / total_24h * 100 if total_24h > 0 else 0,
                "total_all_time": total_all,
                "last_timestamp": last_ts,
            },
            "training": training,
        })
    finally:
        db.close()


@app.route("/api/forecast")
def api_forecast():
    """Liefert den Forecast aus der DB (gespeichert vom Scheduler)."""
    from src.forecast import load_forecast_from_db

    hours = request.args.get("hours", "24", type=str)
    try:
        hours = int(hours)
    except ValueError:
        hours = 24

    records = load_forecast_from_db(hours=hours)
    if not records:
        return jsonify({"forecast": [], "error": "Kein Forecast in DB. Warte auf stündlichen Forecast-Lauf."})

    return jsonify({"forecast": records})


@app.route("/api/status")
def api_status():
    """Liefert aktuelle Werte und Collector-Statistiken für Collector-View."""
    db = _get_db()
    try:
        row = db.execute(
            "SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        latest = dict(row) if row else None

        # 24h Stats
        stats = db.execute(
            """SELECT status, COUNT(*) as cnt FROM collector_log
               WHERE timestamp >= datetime('now', '-24 hours')
               GROUP BY status"""
        ).fetchall()
        counts = {r["status"]: r["cnt"] for r in stats}
        total = sum(counts.values())
        ok = counts.get("ok", 0)
        errors = counts.get("error", 0) + counts.get("timeout", 0)

        # Gesamt
        total_all = db.execute("SELECT COUNT(*) FROM collector_log WHERE status = 'ok'").fetchone()[0]

        return jsonify({
            "latest": latest,
            "collector": {
                "total": total, "ok": ok, "errors": errors,
                "error_rate": errors / total * 100 if total > 0 else 0,
                "total_all_time": total_all,
            },
        })
    finally:
        db.close()


@app.route("/api/table/<table_name>")
def api_table(table_name):
    """Liefert Tabellendaten als JSON."""
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
    if not DATA_DB_PATH.exists():
        return jsonify({"error": "Datenbank nicht gefunden"}), 404
    return send_file(
        str(DATA_DB_PATH),
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
