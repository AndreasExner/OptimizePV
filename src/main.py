"""Entry-Point für OptimizePV.

Verwendung:
    python -m src.main collect              # Daten sammeln
    python -m src.main collect --interval 60 # Kürzeres Intervall
    python -m src.main status               # Collector-Statistiken
    python -m src.main retrain              # Modelle neu trainieren
"""

import argparse
import logging
import signal
import sys

from src.config import COLLECTOR_INTERVAL


def setup_logging(level: str = "INFO") -> None:
    """Konfiguriert Logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_collect(args: argparse.Namespace) -> None:
    """Startet den Daten-Collector."""
    from src.data.collector import init_db, run_collector

    init_db()
    run_collector(interval=args.interval)


def cmd_status(args: argparse.Namespace) -> None:
    """Zeigt Collector-Statistiken."""
    from src.data.collector import get_collector_stats, get_measurements

    stats = get_collector_stats(hours=args.hours)
    print(f"=== Collector Status (letzte {args.hours}h) ===")
    print(f"  Abfragen gesamt: {stats['total']}")
    print(f"  Erfolgreich:     {stats['ok']}")
    print(f"  Fehler:          {stats['errors']}")
    print(f"  Fehlerrate:      {stats['error_rate']:.1f}%")

    df = get_measurements(hours=args.hours)
    if not df.empty:
        print(f"\n=== Messwerte ({len(df)} Einträge) ===")
        print(f"  Zeitraum: {df['timestamp'].min()} bis {df['timestamp'].max()}")
        for col in ["pv_power", "battery_soc", "grid_power", "home_power"]:
            if col in df.columns and df[col].notna().any():
                print(f"  {col}: min={df[col].min():.0f}, max={df[col].max():.0f}, mean={df[col].mean():.0f}")
    else:
        print("\n  Keine Messwerte vorhanden.")


def _run_training() -> bool:
    """Führt das Training beider Modelle durch und protokolliert in DB."""
    import json
    import time as _time
    from datetime import date, datetime, timedelta, timezone
    import sqlite3
    from src.config import DATA_DB_PATH
    from src.data.weather_connector import get_historical
    from src.features.feature_engineering import (
        load_collector_data, build_hourly_from_collector,
        build_training_from_collector, TARGET_COL,
    )
    from src.models.pv_forecast import PVForecastModel
    from src.models.consumption_forecast import ConsumptionForecastModel, CONSUMPTION_TARGET

    logger = logging.getLogger("retrain")
    overall_start = _time.monotonic()
    trained_at = datetime.now(timezone.utc).isoformat()

    # Daten prüfen
    raw = load_collector_data()
    if raw.empty:
        logger.error("Keine Collector-Daten vorhanden.")
        return False

    hourly = build_hourly_from_collector(raw)
    days = (hourly["timestamp"].max() - hourly["timestamp"].min()).total_seconds() / 86400
    data_start = hourly["timestamp"].min().isoformat()
    data_end = hourly["timestamp"].max().isoformat()
    logger.info("Collector-Daten: %d Rohdaten, %d Stunden, %.1f Tage", len(raw), len(hourly), days)

    if len(hourly) < 48:
        logger.error("Mindestens 48 Stunden nötig, nur %d vorhanden.", len(hourly))
        return False

    # Wetter laden
    weather = get_historical(
        start_date=hourly["timestamp"].min().date(),
        end_date=date.today() - timedelta(days=1),
    )
    logger.info("Wetter: %d Stunden", len(weather))

    # Trainingsdatensatz
    df = build_training_from_collector(weather)
    logger.info("Trainingsdatensatz: %d Zeilen", len(df))
    test_days = max(1, min(int(days * 0.25), 3))

    def _save_training_record(model_type, metrics, importance_df, model_path, duration):
        """Speichert Training-Ergebnis in DB."""
        vs_baseline = None
        if "baseline_mae" in metrics and metrics["baseline_mae"] > 0:
            vs_baseline = (1 - metrics["test_mae"] / metrics["baseline_mae"]) * 100

        feat_json = json.dumps(
            importance_df.head(15).to_dict(orient="records")
        ) if importance_df is not None else "[]"

        with sqlite3.connect(str(DATA_DB_PATH)) as conn:
            conn.execute(
                """INSERT INTO training_history
                   (trained_at, duration_s, model_type, samples, features_used,
                    data_days, data_start, data_end,
                    train_mae, train_rmse, train_r2,
                    test_mae, test_rmse, test_r2,
                    baseline_mae, vs_baseline_pct,
                    feature_importance, model_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trained_at, duration, model_type,
                 metrics.get("train_samples", 0), len(metrics.get("features_used", [])),
                 days, data_start, data_end,
                 metrics.get("train_mae"), metrics.get("train_rmse"), metrics.get("train_r2"),
                 metrics.get("test_mae"), metrics.get("test_rmse"), metrics.get("test_r2"),
                 metrics.get("baseline_mae"), vs_baseline,
                 feat_json, str(model_path)),
            )

    # --- PV-Modell ---
    t0 = _time.monotonic()
    pv_model = PVForecastModel(params={
        "n_estimators": 300, "max_depth": 5, "learning_rate": 0.05,
        "num_leaves": 16, "subsample": 0.8, "colsample_bytree": 0.7,
        "min_child_samples": 10, "reg_alpha": 0.1, "reg_lambda": 1.0,
        "random_state": 42, "verbose": -1,
    })
    pv_metrics = pv_model.train(df, target=TARGET_COL, test_days=test_days)
    pv_path = pv_model.save()
    pv_importance = pv_model.feature_importance()
    pv_duration = _time.monotonic() - t0

    pv_vs = ""
    if "baseline_mae" in pv_metrics:
        imp = (1 - pv_metrics["test_mae"] / pv_metrics["baseline_mae"]) * 100
        pv_vs = f", vs.Baseline: {imp:+.1f}%"
    logger.info("PV-Modell: MAE=%.3f, R²=%.4f%s → %s (%.1fs)",
                pv_metrics["test_mae"], pv_metrics["test_r2"], pv_vs, pv_path, pv_duration)

    _save_training_record("pv", pv_metrics, pv_importance, pv_path, pv_duration)

    # --- Verbrauchsmodell ---
    t0 = _time.monotonic()
    cons_model = ConsumptionForecastModel()
    cons_metrics = cons_model.train(df, target=CONSUMPTION_TARGET, test_days=test_days)
    cons_path = cons_model.save()
    cons_importance = cons_model.feature_importance()
    cons_duration = _time.monotonic() - t0

    cons_vs = ""
    if "baseline_mae" in cons_metrics:
        imp = (1 - cons_metrics["test_mae"] / cons_metrics["baseline_mae"]) * 100
        cons_vs = f", vs.Baseline: {imp:+.1f}%"
    logger.info("Verbrauchsmodell: MAE=%.3f, R²=%.4f%s → %s (%.1fs)",
                cons_metrics["test_mae"], cons_metrics["test_r2"], cons_vs, cons_path, cons_duration)

    _save_training_record("consumption", cons_metrics, cons_importance, cons_path, cons_duration)

    total_duration = _time.monotonic() - overall_start
    logger.info("Training abgeschlossen in %.1fs (%d Samples, %.1f Tage Daten)",
                total_duration, len(df), days)
    return True


def cmd_retrain(args: argparse.Namespace) -> None:
    """Trainiert PV- und Verbrauchsmodell mit Collector-Daten."""
    ok = _run_training()
    if not ok:
        sys.exit(1)
    print("✅ Training abgeschlossen.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="optimizepv",
        description="PV-Optimierung: Daten-Collector und Optimizer",
    )
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    sub = parser.add_subparsers(dest="command", required=True)

    # --- collect ---
    p_collect = sub.add_parser("collect", help="Daten-Collector starten (HA → evcc Fallback)")
    p_collect.add_argument("--interval", type=int, default=COLLECTOR_INTERVAL,
                           help=f"Abfrage-Intervall in Sekunden (default: {COLLECTOR_INTERVAL})")
    p_collect.set_defaults(func=cmd_collect)

    # --- status ---
    p_status = sub.add_parser("status", help="Collector-Statistiken anzeigen")
    p_status.add_argument("--hours", type=int, default=24,
                          help="Zeitraum in Stunden (default: 24)")
    p_status.set_defaults(func=cmd_status)

    # --- retrain ---
    p_retrain = sub.add_parser("retrain", help="PV- und Verbrauchsmodell trainieren")
    p_retrain.set_defaults(func=cmd_retrain)

    args = parser.parse_args()
    setup_logging(args.log_level)

    # Graceful Shutdown
    def handle_signal(_sig, _frame):
        logging.info("Shutdown Signal empfangen, beende...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    args.func(args)


def run_retrain_scheduler() -> None:
    """Wöchentlicher Retraining-Scheduler. Läuft jeden Montag um 00:30 Uhr."""
    import time
    from datetime import datetime, timezone, timedelta

    logger = logging.getLogger("retrain.scheduler")
    setup_logging("INFO")
    logger.info("Retraining-Scheduler gestartet (jeden Montag 00:30 UTC)")

    while True:
        now = datetime.now(timezone.utc)

        # Nächsten Montag 00:30 UTC berechnen
        days_until_monday = (7 - now.weekday()) % 7
        if days_until_monday == 0 and (now.hour > 0 or (now.hour == 0 and now.minute >= 30)):
            days_until_monday = 7  # Schon vorbei heute

        next_train = now.replace(hour=0, minute=30, second=0, microsecond=0) + timedelta(days=days_until_monday)
        wait = (next_train - now).total_seconds()
        logger.info("Nächstes Training: %s (in %.0fh)", next_train.strftime("%Y-%m-%d %H:%M UTC"), wait / 3600)

        time.sleep(wait)

        logger.info("=== Wöchentliches Retraining gestartet ===")
        try:
            ok = _run_training()
            if ok:
                logger.info("=== Wöchentliches Retraining erfolgreich ===")
            else:
                logger.error("=== Wöchentliches Retraining fehlgeschlagen ===")
        except Exception as e:
            logger.error("Retraining Fehler: %s", e, exc_info=True)


if __name__ == "__main__":
    main()
