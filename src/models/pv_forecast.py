"""LightGBM PV-Modulleistungsprognose.

Trainiert und evaluiert ein LightGBM-Modell zur Vorhersage der
stündlichen PV-Modulleistung (kWh) basierend auf Wetter- und Zeitfeatures.

Target: pv_module_kwh = inverter_wirkleistung + battery_charge_power
Dies ist die tatsächliche Modulleistung (bis 13,4 kWp), nicht die
WR-begrenzte AC-Ausgangsleistung (max 10 kW).
"""

import os
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.config import MODELS_DIR, MODEL_PARAMS, PV_SPECS
from src.features.feature_engineering import FEATURE_COLS, TARGET_COL


class PVForecastModel:
    """LightGBM-basierte PV-Ertragsprognose."""

    def __init__(self, params: dict | None = None):
        self.model: lgb.LGBMRegressor | None = None
        self.params = params or {
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_samples": 10,
            "random_state": 42,
            "verbose": -1,
        }
        self.feature_cols = FEATURE_COLS
        self.metrics: dict = {}

    def train(
        self,
        df: pd.DataFrame,
        target: str = "pv_kwh",
        test_days: int = 7,
    ) -> dict:
        """Trainiert das Modell mit zeitbasiertem Train/Test-Split.

        Args:
            df: Feature-DataFrame (aus build_training_dataset).
            target: Zielvariable.
            test_days: Anzahl Tage für den Testsatz (am Ende).

        Returns:
            Dict mit Metriken (MAE, RMSE, R²) für Train und Test.
        """
        # Verfügbare Features filtern
        available = [c for c in self.feature_cols if c in df.columns]

        # Zeitbasierter Split
        split_date = df["timestamp"].max() - pd.Timedelta(days=test_days)
        train_mask = df["timestamp"] <= split_date
        test_mask = df["timestamp"] > split_date

        X_train = df.loc[train_mask, available]
        y_train = df.loc[train_mask, target]
        X_test = df.loc[test_mask, available]
        y_test = df.loc[test_mask, target]

        # Training
        self.model = lgb.LGBMRegressor(**self.params)
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.log_evaluation(0)],
        )

        # Metriken
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

        # Baseline: Persistence (gleiche Stunde gestern)
        lag_col = f"{target}_lag24"
        if lag_col in df.columns:
            baseline_pred = df.loc[test_mask, lag_col]
            self.metrics["baseline_mae"] = mean_absolute_error(y_test, baseline_pred)

        return self.metrics

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Vorhersage der PV-Modulleistung.

        Args:
            df: DataFrame mit Feature-Spalten.

        Returns:
            Array mit vorhergesagter PV-Modulleistung (kWh/h).
        """
        if self.model is None:
            raise RuntimeError("Modell ist nicht trainiert. Erst train() aufrufen.")
        available = [c for c in self.feature_cols if c in df.columns]
        predictions = self.model.predict(df[available])
        # Clipping: 0 ≤ prediction ≤ Modul-Peak (kWh/h)
        max_kwh = PV_SPECS["module_peak_kw"]
        return np.clip(predictions, 0, max_kwh)

    def feature_importance(self) -> pd.DataFrame:
        """Gibt Feature-Importances zurück.

        Returns:
            DataFrame mit Feature-Name und Importance, absteigend sortiert.
        """
        if self.model is None:
            raise RuntimeError("Modell ist nicht trainiert.")
        importance = pd.DataFrame({
            "feature": self.metrics.get("features_used", self.feature_cols),
            "importance": self.model.feature_importances_,
        }).sort_values("importance", ascending=False).reset_index(drop=True)
        return importance

    def save(self, path: str | Path | None = None) -> Path:
        """Speichert das trainierte Modell.

        Args:
            path: Speicherpfad. Default: models/pv_forecast.joblib

        Returns:
            Pfad zur gespeicherten Datei.
        """
        if self.model is None:
            raise RuntimeError("Modell ist nicht trainiert.")

        if path is None:
            path = MODELS_DIR / "pv_forecast.joblib"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump({"model": self.model, "params": self.params,
                      "feature_cols": self.feature_cols, "metrics": self.metrics}, path)

        size_mb = path.stat().st_size / (1024 * 1024)
        max_size = MODEL_PARAMS.get("max_model_size_mb", 20)
        if size_mb > max_size:
            print(f"WARNUNG: Modell ist {size_mb:.1f} MB (Limit: {max_size} MB)")
        return path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "PVForecastModel":
        """Lädt ein gespeichertes Modell.

        Args:
            path: Pfad zur .joblib-Datei. Default: models/pv_forecast.joblib

        Returns:
            PVForecastModel-Instanz mit geladenem Modell.
        """
        if path is None:
            path = MODELS_DIR / "pv_forecast.joblib"
        path = Path(path)

        data = joblib.load(path)
        instance = cls(params=data["params"])
        instance.model = data["model"]
        instance.feature_cols = data["feature_cols"]
        instance.metrics = data["metrics"]
        return instance
