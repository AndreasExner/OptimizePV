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


def cmd_retrain(args: argparse.Namespace) -> None:
    """Trainiert PV- und Verbrauchsmodell mit Collector-Daten."""
    from datetime import date, timedelta
    from src.data.weather_connector import get_historical
    from src.features.feature_engineering import (
        load_collector_data, build_hourly_from_collector,
        build_training_from_collector, TARGET_COL,
    )
    from src.models.pv_forecast import PVForecastModel
    from src.models.consumption_forecast import ConsumptionForecastModel, CONSUMPTION_TARGET

    # Daten prüfen
    raw = load_collector_data()
    if raw.empty:
        print("FEHLER: Keine Collector-Daten vorhanden.")
        sys.exit(1)

    hourly = build_hourly_from_collector(raw)
    days = (hourly["timestamp"].max() - hourly["timestamp"].min()).total_seconds() / 86400
    print(f"Collector-Daten: {len(raw)} Rohdaten, {len(hourly)} Stunden, {days:.1f} Tage")

    if len(hourly) < 48:
        print(f"FEHLER: Mindestens 48 Stunden nötig, nur {len(hourly)} vorhanden.")
        sys.exit(1)

    # Wetter laden
    print("Lade Wetterdaten...")
    weather = get_historical(
        start_date=hourly["timestamp"].min().date(),
        end_date=date.today() - timedelta(days=1),
    )
    print(f"Wetter: {len(weather)} Stunden")

    # Trainingsdatensatz
    df = build_training_from_collector(weather)
    print(f"Trainingsdatensatz: {len(df)} Zeilen")

    test_days = max(1, min(int(days * 0.25), 3))
    print(f"Test-Split: {test_days} Tage")

    # --- PV-Modell ---
    print(f"\n=== PV-Modell ({TARGET_COL}) ===")
    pv_model = PVForecastModel(params={
        "n_estimators": 300, "max_depth": 5, "learning_rate": 0.05,
        "num_leaves": 16, "subsample": 0.8, "colsample_bytree": 0.7,
        "min_child_samples": 10, "reg_alpha": 0.1, "reg_lambda": 1.0,
        "random_state": 42, "verbose": -1,
    })
    pv_metrics = pv_model.train(df, target=TARGET_COL, test_days=test_days)
    pv_path = pv_model.save()
    print(f"  MAE:  {pv_metrics['test_mae']:.3f} kWh")
    print(f"  R²:   {pv_metrics['test_r2']:.4f}")
    if "baseline_mae" in pv_metrics:
        imp = (1 - pv_metrics["test_mae"] / pv_metrics["baseline_mae"]) * 100
        print(f"  vs. Baseline: {imp:+.1f}%")
    print(f"  Gespeichert: {pv_path}")

    # --- Verbrauchsmodell ---
    print(f"\n=== Verbrauchsmodell ({CONSUMPTION_TARGET}) ===")
    cons_model = ConsumptionForecastModel()
    cons_metrics = cons_model.train(df, target=CONSUMPTION_TARGET, test_days=test_days)
    cons_path = cons_model.save()
    print(f"  MAE:  {cons_metrics['test_mae']:.3f} kWh")
    print(f"  R²:   {cons_metrics['test_r2']:.4f}")
    if "baseline_mae" in cons_metrics:
        imp = (1 - cons_metrics["test_mae"] / cons_metrics["baseline_mae"]) * 100
        print(f"  vs. Baseline: {imp:+.1f}%")
    print(f"  Gespeichert: {cons_path}")

    print("\n✅ Training abgeschlossen.")


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


if __name__ == "__main__":
    main()
