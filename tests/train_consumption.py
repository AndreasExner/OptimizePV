"""Trainiere das Verbrauchsmodell mit Collector-Daten."""
import sys
sys.path.insert(0, ".")
from pathlib import Path
from src.data.weather_connector import get_historical
from src.features.feature_engineering import build_training_from_collector
from src.models.consumption_forecast import ConsumptionForecastModel, CONSUMPTION_TARGET
from datetime import date, timedelta

DB_PATH = Path("data/optimizepv.db")

# Trainingsdatensatz (gleicher wie für PV)
weather = get_historical(
    start_date=date(2026, 5, 12),
    end_date=date.today() - timedelta(days=1),
)
df = build_training_from_collector(weather, db_path=DB_PATH)
print(f"Trainingsdaten: {len(df)} Zeilen")
print(f"home_kwh: min={df['home_kwh'].min():.3f}, max={df['home_kwh'].max():.3f}, mean={df['home_kwh'].mean():.3f}")

# Features prüfen
from src.models.consumption_forecast import CONSUMPTION_FEATURES
available = [c for c in CONSUMPTION_FEATURES if c in df.columns]
missing = [c for c in CONSUMPTION_FEATURES if c not in df.columns]
print(f"Features: {len(available)} verfügbar, {len(missing)} fehlen")
if missing:
    print(f"  Fehlend: {missing}")

# Training
model = ConsumptionForecastModel()
metrics = model.train(df, target=CONSUMPTION_TARGET, test_days=2)

print(f"\n=== Verbrauchsmodell ({CONSUMPTION_TARGET}) ===")
print(f"Training ({metrics['train_samples']} Samples):")
print(f"  MAE:  {metrics['train_mae']:.3f} kWh")
print(f"  R²:   {metrics['train_r2']:.4f}")
print(f"Test ({metrics['test_samples']} Samples):")
print(f"  MAE:  {metrics['test_mae']:.3f} kWh")
print(f"  R²:   {metrics['test_r2']:.4f}")
if "baseline_mae" in metrics:
    improvement = (1 - metrics["test_mae"] / metrics["baseline_mae"]) * 100
    print(f"Baseline MAE: {metrics['baseline_mae']:.3f} kWh")
    print(f"Verbesserung: {improvement:+.1f}%")

# Feature Importance
imp = model.feature_importance()
print(f"\nTop 10 Features:")
print(imp.head(10).to_string(index=False))

# Speichern
path = model.save()
size_mb = path.stat().st_size / (1024 * 1024)
print(f"\nModell gespeichert: {path} ({size_mb:.2f} MB)")
