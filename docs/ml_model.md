# Machine Learning Dynamic ETA Model Documentation

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Mathematical Formulation & Prediction Objective

Traditional train tracking engines attempt to predict either whole arrival timestamps directly or extrapolate static scheduled differences. This leads to heavy drift when traversing multi-section routes.

### Objective
The ML model predicts **remaining travel time** ($\tau_{\text{rem}}$ in minutes) from the current train state to each upcoming target station:

$$\hat{\tau}_{\text{rem}} = f_{\text{XGBoost}}(\mathbf{x})$$

The dynamic expected time of arrival (ETA) timestamp is then computed:

$$\text{Dynamic ETA} = T_{\text{current}} + \hat{\tau}_{\text{rem}}$$

### Confidence Intervals
Based on the chronologically validated root-mean-squared error ($\text{RMSE} = 3.51$ minutes):

$$\tau_{\text{confidence}} = \hat{\tau}_{\text{rem}} \pm 1.5 \times \text{RMSE}_{\text{val}}$$

$$\text{Confidence Interval} = \left[\max\left(0, \hat{\tau}_{\text{rem}} - 5.3\right), \; \hat{\tau}_{\text{rem}} + 5.3\right] \quad (\text{minutes})$$

---

## 2. Feature Engineering & Candidate Features

Features are constructed with **zero train/test skew** via [`RailwayFeaturePipeline`](../src/ml/features.py):

| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `scheduled_remaining_time_min` | `float` | Timetable planned duration to target station |
| `distance_to_station_km` | `float` | Track distance from current position to station |
| `distance_to_destination_km` | `float` | Remaining track distance to final terminal station |
| `current_delay_min` | `float` | Instantaneous operational delay at current location |
| `current_speed_ratio` | `float` | Ratio of instantaneous speed to 120 km/h line speed |
| `stations_remaining` | `float` | Number of scheduled intermediate halts remaining |
| `hist_section_avg_delay` | `float` | Historical mean delay on entering block section |
| `hist_section_delay_var` | `float` | Historical delay variance on active block section |
| `hist_section_avg_travel_time` | `float` | Historical sectional average traverse duration |
| `train_type_code` | `float` | Categorical encoding (1: Rajdhani/Tejas, 2: Vande Bharat) |
| `hour_of_day` | `float` | Time of departure (0.0 to 23.0) |
| `day_of_week` | `float` | Day index (0.0 = Monday, 6.0 = Sunday) |
| `is_weekend` | `float` | Binary weekend indicator |
| `is_rush_hour` | `float` | Binary peak-hour congestion indicator |
| `speed_restriction_flag` | `float` | Binary flag indicating cautionary section speeds (< 45 km/h) |

### Feature Importances (Trained Model)
1. `scheduled_remaining_time_min`: **44.80%**
2. `distance_to_station_km`: **36.06%**
3. `stations_remaining`: **10.58%**
4. `hist_section_avg_travel_time`: **6.15%**
5. `distance_to_destination_km`: **1.37%**
6. `hist_section_avg_delay`: **0.81%**
7. `hist_section_delay_var`: **0.21%**
8. `hour_of_day`: **0.01%**

---

## 3. Training Pipeline & Anti-Leakage Protocol

- **Dataset**: 1,400 station-pair remaining travel time observations generated from 35 days of multi-train runs (`12302`, `12952`, `22436`).
- **Strict Chronological Split**:
  - **Training Set**: 1,120 samples spanning 28 days (2026-08-05 to 2026-09-01)
  - **Validation Set**: 280 samples spanning 7 unseen days (2026-09-02 to 2026-09-08)
  - *No random shuffling* was permitted across dates, preventing temporal lookahead leakage.

### Hyperparameters
```json
{
  "n_estimators": 160,
  "max_depth": 5,
  "learning_rate": 0.075,
  "subsample": 0.85,
  "colsample_bytree": 0.85,
  "min_child_weight": 2.0,
  "objective": "reg:squarederror"
}
```

---

## 4. Empirical Evaluation Against Deterministic Baseline

The model was evaluated against the deterministic timetable slack recovery baseline on the held-out 7-day validation partition:

| Metric | Deterministic Baseline | XGBoost ML Model | Improvement |
| :--- | :---: | :---: | :---: |
| **Mean Absolute Error (MAE)** | 6.35 minutes | **2.69 minutes** | **-57.6%** reduction in error |
| **Root Mean Squared Error (RMSE)** | 7.98 minutes | **3.51 minutes** | **-56.0%** reduction |
| **Mean Absolute Percentage Error (MAPE)** | 3.00% | **0.89%** | **-70.3%** relative error |
| **Coefficient of Determination ($R^2$)** | 0.9989 | **0.9998** | Higher variance capture |
| **Accuracy within $\pm 5$ min** | 48.9% | **83.6%** | **+34.7%** absolute gain |
| **Accuracy within $\pm 10$ min** | 74.3% | **99.3%** | **+25.0%** absolute gain |
| **Accuracy within $\pm 15$ min** | 94.3% | **100.0%** | **+5.7%** absolute gain |

> [!NOTE]
> All evaluation metrics above are strictly computed on the chronological validation set and persisted in [`models/model_metadata.json`](../models/model_metadata.json). No metrics are fabricated.

---

## 5. API Endpoints

### 1. `GET /api/trains/{train_number}/eta/dynamic`
*(Alias: `/api/trains/{train_number}/eta/ml`)*

#### Sample Response:
```json
{
  "train_number": "12302",
  "generated_at": "2026-09-10T18:56:00+00:00",
  "current_delay_minutes": 12.0,
  "current_station": "NDLS",
  "next_station": "CNB",
  "model_name": "XGBoost Dynamic Railway ETA Predictor",
  "model_version": "1.0.0",
  "is_simulation": true,
  "stations": [
    {
      "station_code": "NDLS",
      "station_name": "New Delhi",
      "sequence": 1,
      "distance_from_origin_km": 0.0,
      "scheduled_arrival": null,
      "baseline_eta": null,
      "dynamic_eta": null,
      "predicted_remaining_minutes": 0.0,
      "baseline_remaining_minutes": 0.0,
      "delta_vs_baseline_minutes": 0.0,
      "confidence_lower_minutes": 0.0,
      "confidence_upper_minutes": 0.0,
      "is_passed": true
    },
    {
      "station_code": "CNB",
      "station_name": "Kanpur Central",
      "sequence": 2,
      "distance_from_origin_km": 440.0,
      "scheduled_arrival": "21:30:00",
      "baseline_eta": "2026-09-10T21:42:00+00:00",
      "dynamic_eta": "2026-09-10T21:39:18+00:00",
      "predicted_remaining_minutes": 163.3,
      "baseline_remaining_minutes": 166.0,
      "delta_vs_baseline_minutes": -2.7,
      "confidence_lower_minutes": 158.0,
      "confidence_upper_minutes": 168.6,
      "is_passed": false
    }
  ]
}
```

---

## 6. Artifact Inventory

- Training Pipeline: [`src/ml/train_model.py`](../src/ml/train_model.py)
- Inference Engine: [`src/ml/predict.py`](../src/ml/predict.py)
- Reusable Feature Module: [`src/ml/features.py`](../src/ml/features.py)
- Serialized Model: [`models/xgboost_eta.json`](../models/xgboost_eta.json)
- Serialized Metadata: [`models/model_metadata.json`](../models/model_metadata.json)
- Automated Test Suite: [`tests/test_ml_prediction.py`](../tests/test_ml_prediction.py)
