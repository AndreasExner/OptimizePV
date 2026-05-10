"""Schnelltest: Wetter- und Preis-Connectoren gegen Live-APIs."""
import sys
sys.path.insert(0, "d:/GitHub/OptimizePV")

from src.data.weather_connector import get_forecast, get_historical
from src.data.price_connector import get_awattar_prices

# === 1.4 Wetter-Connector ===
print("=== 1.4a Wetter-Forecast (3 Tage) ===")
try:
    df = get_forecast(days=3)
    print(f"  Eintraege: {len(df)}")
    print(f"  Spalten: {list(df.columns)}")
    print(f"  Zeitraum: {df['timestamp'].min()} bis {df['timestamp'].max()}")
    print(df.head(3).to_string(index=False))
except Exception as e:
    print(f"  FEHLER: {e}")

print()
print("=== 1.4b Wetter-Historie (7 Tage) ===")
try:
    from datetime import date, timedelta
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=7)
    df = get_historical(start_date=start, end_date=end)
    print(f"  Eintraege: {len(df)}")
    print(f"  Spalten: {list(df.columns)}")
    print(f"  Zeitraum: {df['timestamp'].min()} bis {df['timestamp'].max()}")
    # Strahlung prüfen
    rad_col = "shortwave_radiation"
    if rad_col in df.columns:
        print(f"  {rad_col} - min: {df[rad_col].min()}, max: {df[rad_col].max()}, mean: {df[rad_col].mean():.1f}")
except Exception as e:
    print(f"  FEHLER: {e}")

# === 1.5 Strompreis-Connector ===
print()
print("=== 1.5 aWATTar Strompreise ===")
try:
    df = get_awattar_prices()
    print(f"  Eintraege: {len(df)}")
    print(f"  Spalten: {list(df.columns)}")
    if not df.empty:
        print(f"  Zeitraum: {df['timestamp'].min()} bis {df['timestamp'].max()}")
        print(f"  Preis (EUR/MWh) - min: {df['price_eur_mwh'].min():.2f}, max: {df['price_eur_mwh'].max():.2f}")
        neg = df[df["is_negative"]]
        print(f"  Negative Preise: {len(neg)} von {len(df)}")
        print(df.head(5).to_string(index=False))
except Exception as e:
    print(f"  FEHLER: {e}")
