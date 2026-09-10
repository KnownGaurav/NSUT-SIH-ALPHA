# Historical Data Processing & Feature Engineering Pipeline

## Problem Statement ID: 26028 &bull; Ministry of Railways

---

## 1. Pipeline Objectives & The Sectional Paradigm

Standard railway systems fail to predict accurate ETAs because delays do not propagate uniformly. Train operations are governed by physical **block sections**, **junction bottlenecks**, **single/double track priority crossings**, and **engineered timetable slack**.

### Core Engineering Principles
1. **Section-Level Granularity**: Delays and travel times are computed per section (e.g. `NDLS->CNB`, `CNB->PRYJ`, `DDU->GAYA`), recognizing that different segments exhibit vastly different congestion profiles.
2. **Zero Feature Skew**: The feature engineering pipeline (`RailwayFeaturePipeline`) generates the exact same column schema and mathematical transformations during offline model training and online real-time inference.
3. **Pydantic Input Validation**: Raw historical records are validated for chronological consistency, non-empty identifiers, and realistic positive distance constraints.

---

## 2. Derived Metrics & Mathematical Formulations

Given sequential station stops $S_1, S_2, \dots, S_N$ for a specific dated run:

### 1. Station Arrival & Departure Delays
For station $S_i$:
$$\text{Arrival Delay} = \text{Actual Arrival}_i - \text{Scheduled Arrival}_i \quad (\text{minutes})$$
$$\text{Departure Delay} = \text{Actual Departure}_i - \text{Scheduled Departure}_i \quad (\text{minutes})$$

### 2. Station Dwell Time & Dwell Deviation
$$\text{Actual Dwell}_i = \text{Actual Departure}_i - \text{Actual Arrival}_i$$
$$\text{Scheduled Dwell}_i = \text{Scheduled Departure}_i - \text{Scheduled Arrival}_i$$
$$\text{Dwell Deviation}_i = \text{Actual Dwell}_i - \text{Scheduled Dwell}_i$$

### 3. Sectional Running Time
For section $S_{i-1} \rightarrow S_i$:
$$\text{Actual Section Running Time} = \text{Actual Arrival}_i - \text{Actual Departure}_{i-1}$$
$$\text{Scheduled Section Running Time} = \text{Scheduled Arrival}_i - \text{Scheduled Departure}_{i-1}$$

### 4. Delay Recovery Index
Measures whether a locomotive made up time or accumulated extra delay on a given block section:
$$\text{Delay Recovery}_{i-1 \rightarrow i} = \text{Departure Delay}_{i-1} - \text{Arrival Delay}_i$$
- **Positive ($\Delta > 0$)**: Train made up lost time using timetable slack or priority running.
- **Negative ($\Delta < 0$)**: Train experienced deceleration, signal checks, or section congestion.

---

## 3. Historical Section Knowledge Base

Aggregated across multi-day historical observations, the pipeline computes and persists the section profiles:

1. **`hist_section_avg_delay`**:
   $$\mu_{\text{delay}} = \frac{1}{N} \sum_{k=1}^N \text{Arrival Delay}_{k}$$
2. **`hist_section_delay_var`**:
   $$\sigma^2_{\text{delay}} = \frac{1}{N-1} \sum_{k=1}^N (\text{Arrival Delay}_k - \mu_{\text{delay}})^2$$
   High variance indicates an unstable section susceptible to junction queuing.
3. **`hist_section_avg_travel_time`**:
   Mean duration taken by all trains to traverse the block section.
4. **`train_section_performance`**:
   Specific train average travel time relative to the section average:
   $$\text{Performance Ratio} = \frac{\overline{T}_{\text{train, section}}}{\overline{T}_{\text{section}}}$$
   Values $< 1.0$ denote high-priority trains (e.g. Vande Bharat or Rajdhani) that clear the section faster than ordinary coaching trains.

---

## 4. Reusable Feature Matrix Schema

Both `build_training_matrix()` and `build_inference_vector()` output the identical feature schema (`FEATURE_COLUMNS`):

| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `section_dist_km` | `float` | Track distance of the segment in kilometers |
| `scheduled_run_min` | `float` | Timetable planned duration for the section |
| `current_delay_min` | `float` | Instantaneous delay when entering the section |
| `current_speed_ratio` | `float` | Ratio of actual speed to permissible line speed (120 km/h) |
| `hist_section_avg_delay` | `float` | Historical mean delay on this section |
| `hist_section_delay_var` | `float` | Historical variance of delay on this section |
| `hist_section_avg_travel_time` | `float` | Historical mean sectional travel time |
| `train_section_performance` | `float` | Train-specific priority factor on this section |
| `hour_of_day` | `float` | Time of entry (0.0 to 23.0) |
| `day_of_week` | `float` | Day of week (0.0 = Monday, 6.0 = Sunday) |
| `is_weekend` | `float` | Binary flag (1.0 if Saturday/Sunday, else 0.0) |
| `is_rush_hour` | `float` | Binary flag (1.0 if 07:00-10:00 or 17:00-21:00) |
| `speed_restriction_flag` | `float` | Binary flag (1.0 if speed $< 45$ km/h, indicating caution) |

---

## 5. Artifact Locations

- Raw Generated Historical Dataset: `data/historical_train_runs.csv` (560 records across 35 days)
- Processed Sectional Metrics: `data/processed_sections.csv`
- Serialized Section Historical Knowledge Base: `models/section_profiles.json`
- Feature Code: [`src/ml/features.py`](file:///c:/Users/User/Downloads/SIH%202026/src/ml/features.py)
