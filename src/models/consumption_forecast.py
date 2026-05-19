"""LightGBM Hausverbrauchs-Prognose.

Trainiert ein Modell zur Vorhersage des stündlichen Hausverbrauchs (kWh)
basierend auf Zeit-, Wetter- und Lag-Features.

Target: home_kwh – Gesamter Hausverbrauch (berechnet aus AC-Bus-Bilanz).
"""

from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config import MODELS_DIR

# Features für das Verbrauchsmodell
CONSUMPTION_FEATURES = [
    # Zeit (Haupttreiber für Verbrauchsmuster)
    "hour", "day_of_year", "month", "weekday", "is_weekend",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    # Wetter (Temperatur beeinflusst WP-Verbrauch)
    "temperature_2m", "cloud_cover",
    # Lag Verbrauch
    "home_kwh_lag1", "home_kwh_lag2", "home_kwh_lag3",
    "home_kwh_lag24",
    # Rolling Verbrauch
    "home_kwh_rmean3", "home_kwh_rstd3",
    "home_kwh_rmean6", "home_kwh_rstd6",
    "home_kwh_rmean24", "home_kwh_rstd24",
]

CONSUMPTION_TARGET = "home_kwh"


class ConsumptionForecastModel:
    """LightGBM-basierte Verbrauchsprognose."""

    def __init__(self, params: dict | None = None):
        self.model: lgb.LGBMRegressor | None = None
        self.params = params or {
            "n_estimators": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "num_leaves": 12,
            "subsample": 0.8,
            "colsample_bytree": 0.7,
            "min_child_samples": 8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "verbose": -1,
        }
        self.feature_cols = CONSUMPTION_FEATURES
        self.metrics: dict = {}

    def train(
        self,
        df: pd.DataFrame,
        target: str = CONSUMPTION_TARGET,
        test_days: int = 2,
    ) -> dict:
        """Trainiert das Verbrauchsmodell."""
        available = [c for c in self.feature_cols if c in df.columns]

        split_date = df["timestamp"].max() - pd.Timedelta(days=test_days)
        train_mask = df["timestamp"] <= split_date
        test_mask = df["timestamp"] > split_date

        X_train = df.loc[train_mask, available]
        y_train = df.loc[train_mask, target]
        X_test = df.loc[test_mask, available]
        y_test = df.loc[test_mask, target]

        self.model = lgb.LGBMRegressor(**self.params)
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.log_evaluation(0)],
        )

        y_pred_train = self.model.predict(X_train)
        y_pred_test = self.model.predict(X_test)

        self.metrics = {
            "train_mae": mean_absolute_error(y_train, y_pred_train),
            "train_rmse": np.sqrt(mean_squared_error(y_train, y_pred_train)),
            "train_r2": r2_score(y_train, y_pred_train),
            "test_mae": mean_absolute_error(y_test, y_pred_test),
            "test_rmse": np.sqrt(mean_squared_error(y_test, y_pred_test)),
            "test_r2": r2_score(y_test, y_pred_test),
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "features_used": available,
        }

        # Baseline: Persistence (gestern gleiche Stunde)
        lag_col = f"{target}_lag24"
        if lag_col in df.columns:
            baseline_pred = df.loc[test_mask, lag_col]
            self.metrics["baseline_mae"] = mean_absolute_error(y_test, baseline_pred)

        return self.metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Vorhersage des stündlichen Hausverbrauchs."""
        if self.model is None:
            raise RuntimeError("Modell nicht trainiert.")
        available = [c for c in self.feature_cols if c in df.columns]
        predictions = self.model.predict(df[available])
        return np.clip(predictions, 0, None)

    def feature_importance(self) -> pd.DataFrame:
        """Feature-Importances."""
        if self.model is None:
            raise RuntimeError("Modell nicht trainiert.")
        return pd.DataFrame({
            "feature": self.metrics.get("features_used", self.feature_cols),
            "importance": self.model.feature_importances_,
        }).sort_values("importance", ascending=False).reset_index(drop=True)

    def save(self, path: str | Path | None = None) -> Path:
        """Speichert das Modell."""
        if self.model is None:
            raise RuntimeError("Modell nicht trainiert.")
        if path is None:
            path = MODELS_DIR / "consumption_forecast.joblib"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "params": self.params,
                      "feature_cols": self.feature_cols, "metrics": self.metrics}, path)
        return path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ConsumptionForecastModel":
        """Lädt ein gespeichertes Modell."""
        if path is None:
            path = MODELS_DIR / "consumption_forecast.joblib"
        path = Path(path)
        data = joblib.load(path)
        instance = cls(params=data["params"])
        instance.model = data["model"]
        instance.feature_cols = data["feature_cols"]
        instance.metrics = data["metrics"]
        return instance
