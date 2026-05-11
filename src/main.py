"""Entry-Point für OptimizePV.

Verwendung:
    python -m src.main collect              # Nur Daten sammeln
    python -m src.main collect --interval 60 # Kürzeres Intervall
    python -m src.main status               # Collector-Statistiken
"""

import argparse
import logging
import signal
import sys

from src.config import COLLECTOR_INTERVAL, DATA_DB_PATH, EVCC_URL


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

    args = parser.parse_args()
    setup_logging(args.log_level)

    # Graceful Shutdown
    def handle_signal(sig, frame):
        logging.info("Shutdown Signal empfangen, beende...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    args.func(args)


if __name__ == "__main__":
    main()
