import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.ml.features import (
    feature_pipeline,
    REMAINING_TIME_FEATURE_COLUMNS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("railway_eta.ml.train")

MODEL_DIR = "./models"
MODEL_FILE_PATH = os.path.join(MODEL_DIR, "xgboost_eta.json")
METADATA_FILE_PATH = os.path.join(MODEL_DIR, "model_metadata.json")
DATA_CSV_PATH = "./data/historical_train_runs.csv"


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute standard regression metrics and railway-specific precision tolerance windows."""
    abs_errors = np.abs(y_true - y_pred)
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    
    non_zero_mask = y_true > 1.0
    if np.any(non_zero_mask):
        mape = float(np.mean(abs_errors[non_zero_mask] / y_true[non_zero_mask])) * 100.0
    else:
        mape = 0.0

    acc_5m = float(np.mean(abs_errors <= 5.0)) * 100.0
    acc_10m = float(np.mean(abs_errors <= 10.0)) * 100.0
    acc_15m = float(np.mean(abs_errors <= 15.0)) * 100.0

    return {
        "mae_minutes": round(mae, 2),
        "rmse_minutes": round(rmse, 2),
        "mape_percent": round(mape, 2),
        "r2_score": round(r2, 4),
        "accuracy_within_5_min_percent": round(acc_5m, 1),
        "accuracy_within_10_min_percent": round(acc_10m, 1),
        "accuracy_within_15_min_percent": round(acc_15m, 1)
    }


def train_eta_model(
    data_path: str = DATA_CSV_PATH,
    split_ratio: float = 0.8
) -> Tuple[xgb.XGBRegressor, Dict[str, Any]]:
    logger.info("Initializing Railway XGBoost ETA Model Training Pipeline...")
    os.makedirs(MODEL_DIR, exist_ok=True)

    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Historical training data file not found at: {data_path}")

    df_raw = pd.read_csv(data_path)
    logger.info(f"Loaded {len(df_raw)} raw historical observation records.")

    profiles_path = os.path.join(MODEL_DIR, "section_profiles.json")
    if os.path.exists(profiles_path):
        feature_pipeline.load_profiles(profiles_path)
    else:
        logger.info("Fitting section profiles from historical runs...")
        df_proc = feature_pipeline.process_historical_runs(df_raw)
        feature_pipeline.fit_historical_profiles(df_proc)
        feature_pipeline.save_profiles(profiles_path)

    df_samples = feature_pipeline.build_remaining_time_dataset(df_raw)
    logger.info(f"Constructed {len(df_samples)} station-pair remaining travel time samples.")

    unique_dates = sorted(df_samples["run_date"].unique())
    split_idx = int(len(unique_dates) * split_ratio)
    train_dates = set(unique_dates[:split_idx])
    val_dates = set(unique_dates[split_idx:])

    train_df = df_samples[df_samples["run_date"].isin(train_dates)].reset_index(drop=True)
    val_df = df_samples[df_samples["run_date"].isin(val_dates)].reset_index(drop=True)

    logger.info(
        f"Temporal Split: Training period ({len(train_dates)} days, {len(train_df)} samples: {min(train_dates)} to {max(train_dates)}), "
        f"Validation period ({len(val_dates)} days, {len(val_df)} samples: {min(val_dates)} to {max(val_dates)})"
    )

    X_train = train_df[REMAINING_TIME_FEATURE_COLUMNS]
    y_train = train_df["target_remaining_travel_time_min"]

    X_val = val_df[REMAINING_TIME_FEATURE_COLUMNS]
    y_val = val_df["target_remaining_travel_time_min"]
    y_val_baseline = val_df["baseline_rem_time_min"]

    model_params = {
        "n_estimators": 160,
        "max_depth": 5,
        "learning_rate": 0.075,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "min_child_weight": 2.0,
        "random_state": 42,
        "objective": "reg:squarederror"
    }

    model = xgb.XGBRegressor(**model_params)
    logger.info("Training XGBoost Regressor...")
    model.fit(X_train, y_train)

    y_pred_val = model.predict(X_val)

    ml_metrics = compute_metrics(y_val.to_numpy(), y_pred_val)
    baseline_metrics = compute_metrics(y_val.to_numpy(), y_val_baseline.to_numpy())

    logger.info(f"Validation Baseline MAE: {baseline_metrics['mae_minutes']} min, RMSE: {baseline_metrics['rmse_minutes']} min")
    logger.info(f"Validation XGBoost MAE:  {ml_metrics['mae_minutes']} min, RMSE: {ml_metrics['rmse_minutes']} min")
    logger.info(f"Accuracy within +/- 5 min: Baseline = {baseline_metrics['accuracy_within_5_min_percent']}%, ML = {ml_metrics['accuracy_within_5_min_percent']}%")
    logger.info(f"Accuracy within +/- 10 min: Baseline = {baseline_metrics['accuracy_within_10_min_percent']}%, ML = {ml_metrics['accuracy_within_10_min_percent']}%")

    importances = model.feature_importances_
    feat_importance_dict = {
        feat: round(float(imp), 4)
        for feat, imp in sorted(zip(REMAINING_TIME_FEATURE_COLUMNS, importances), key=lambda x: x[1], reverse=True)
    }

    metadata: Dict[str, Any] = {
        "model_name": "XGBoost Dynamic Railway ETA Predictor",
        "model_version": "1.0.0",
        "target_variable": "remaining_travel_time_minutes",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "XGBRegressor",
        "hyperparameters": model_params,
        "feature_columns": REMAINING_TIME_FEATURE_COLUMNS,
        "feature_importances": feat_importance_dict,
        "dataset_summary": {
            "total_samples": len(df_samples),
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "train_period": {"start": min(train_dates), "end": max(train_dates)},
            "val_period": {"start": min(val_dates), "end": max(val_dates)},
            "trains_covered": list(df_samples["train_number"].unique())
        },
        "evaluation": {
            "validation_split_method": "chronological_by_run_date",
            "deterministic_baseline": baseline_metrics,
            "xgboost_model": ml_metrics,
            "improvements": {
                "mae_reduction_minutes": round(baseline_metrics["mae_minutes"] - ml_metrics["mae_minutes"], 2),
                "mae_reduction_percent": round(((baseline_metrics["mae_minutes"] - ml_metrics["mae_minutes"]) / baseline_metrics["mae_minutes"]) * 100.0, 1),
                "acc_within_5m_gain_percent": round(ml_metrics["accuracy_within_5_min_percent"] - baseline_metrics["accuracy_within_5_min_percent"], 1)
            }
        }
    }

    model.save_model(MODEL_FILE_PATH)
    logger.info(f"Serialized XGBoost model to {MODEL_FILE_PATH}")

    with open(METADATA_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved model metadata to {METADATA_FILE_PATH}")

    return model, metadata


if __name__ == "__main__":
    train_eta_model()
