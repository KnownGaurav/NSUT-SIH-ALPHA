# Deterministic Baseline ETA Engine

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Overview & Purpose of the Baseline Model

Before introducing non-linear machine learning models (e.g. Gradient Boosted Trees), disciplined data science and engineering practices require a **deterministic benchmark baseline**.

### Purpose
1. **Performance Benchmark**: Establishes ground truth error metrics (MAE, RMSE, MAPE) against which any future ML model must be evaluated.
2. **Deterministic Fallback**: If inference service dependencies, weather APIs, or feature extractors experience transient degradation, the system can gracefully degrade to this deterministic baseline.
3. **Punctuality Reference**: Standardizes how railway enquiry systems calculate expected arrival times.

> [!WARNING]
> This is a deterministic baseline engine based on linear projections and basic timetable slack adjustments. It is **NOT** the final machine learning prediction engine.

---

## 2. Mathematical Formulation

Given a train at current timestamp $T_{\text{now}}$ with current delay $D_{\text{curr}}$, evaluating an upcoming station stop $S_k$:

### 1. Scheduled Remaining Travel Time
$$\text{Scheduled Remaining Travel Time}_k = T_{\text{sched}}(S_k) - T_{\text{sched\_curr}}$$
where $T_{\text{sched\_curr}}$ is the planned time at the train's current track location.

### 2. Timetable Slack Recovery Adjustment
Indian Railways timetables incorporate slack margins (typically ~3% to 5% of sectional running times on long electrified corridors). If the train is currently delayed ($D_{\text{curr}} > 0$), locomotives can recover a modest portion of lost time:
$$\text{Potential Recovery}_k = \min\left(0.25 \times D_{\text{curr}}, \sum_{j=\text{next}}^k \frac{d_j}{100.0} \times 1.5\right)$$
$$\text{Baseline Delay}_k = \max\left(0.0, D_{\text{curr}} - \text{Potential Recovery}_k\right)$$

### 3. Baseline Remaining Travel Time
$$\text{Baseline Remaining Travel Time}_k = \text{Scheduled Remaining Travel Time}_k + \text{Baseline Delay}_k$$

### 4. Expected Time of Arrival (ETA)
$$\text{Baseline ETA}_k = T_{\text{now}} + \text{Baseline Remaining Travel Time}_k$$

---

## 3. Worked Example

| Parameter | Value |
| :--- | :--- |
| **Current Time ($T_{\text{now}}$)** | `18:00` |
| **Next Station ($S_k$)** | `Agra Cantt (AGC)` |
| **Scheduled Remaining Travel Time** | `42 minutes` |
| **Current Delay ($D_{\text{curr}}$)** | `+15 minutes` |
| **Calculated Baseline Remaining Travel Time** | `42 + 15 = 57 minutes` |
| **Calculated Baseline ETA** | `18:00 + 57m = 18:57` |

---

## 4. Why Machine Learning is Needed Beyond Baseline

While the baseline provides a reasonable linear projection, real-world railway networks deviate substantially due to:
1. **Compound Junction Delay**: Bottleneck junctions (e.g. Mughalsarai, Kanpur, Mathura) queue trains non-linearly. A 15-minute delay outside a junction can become 45 minutes if a platform block occurs.
2. **Weather Speed Restrictions**: Dense winter fog in Northern India imposes mandatory speed limits (e.g. 60 km/h for cab-signaled locos, 30 km/h in severe fog), rendering timetable run-times invalid.
3. **Train-Specific Precedence**: High-priority coaching trains (Rajdhani, Vande Bharat) are given clear green paths ahead of freight and ordinary express trains, achieving far higher recovery rates than the baseline assumes.
4. **Time of Day & Day of Week**: Commuter peak hours around major suburban terminals severely reduce track availability.

These non-linear relationships will be modeled by the upcoming Gradient Boosted Decision Tree (XGBoost / LightGBM) engine.

---

## 5. REST API Specification

### Baseline Prediction Endpoint
`GET /api/trains/{train_number}/eta/baseline`

**Example Response**:
```json
{
  "train_number": "12301",
  "generated_at": "2026-09-10T18:00:00Z",
  "current_delay_minutes": 15.0,
  "current_station": "NDLS",
  "next_station": "AGC",
  "model_name": "Deterministic Baseline Engine (v1.0)",
  "is_simulation": true,
  "stations": [
    {
      "station_code": "NDLS",
      "station_name": "New Delhi",
      "sequence": 1,
      "distance_from_origin_km": 0.0,
      "scheduled_arrival": null,
      "baseline_eta": null,
      "baseline_delay_minutes": 0.0,
      "remaining_travel_time_minutes": 0.0,
      "remaining_distance_km": 0.0,
      "recovery_adjustment_minutes": 0.0,
      "is_passed": true
    },
    {
      "station_code": "AGC",
      "station_name": "Agra Cantt",
      "sequence": 2,
      "distance_from_origin_km": 195.0,
      "scheduled_arrival": "18:42:00",
      "baseline_eta": "2026-09-10T18:57:00Z",
      "baseline_delay_minutes": 15.0,
      "remaining_travel_time_minutes": 57.0,
      "remaining_distance_km": 117.0,
      "recovery_adjustment_minutes": 0.0,
      "is_passed": false
    }
  ]
}
```
