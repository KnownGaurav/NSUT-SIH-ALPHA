# System UI Visual Asset Inventory & Component Walkthrough

This directory stores visual captures, operational screenshots, and UI mockups of the **Dynamic Rail ETA Forecasting Workstation** for SIH 2026 jury presentations and documentation.

---

## 1. Primary Operational Interfaces

### 1.1 Railway Operations Control Room (`control_room_overview.png`)
- **Purpose**: Section Controller high-density situational awareness interface.
- **Key UI Components**:
  - Full-width interactive Leaflet dark-mode railway vector map with live train GPS markers, directional headings, and corridor routes.
  - Operational Status Badges: Clear indicator of `DATA SOURCE: SIMULATION (Designed to integrate authorized railway real-time feeds)`.
  - Fleet Telemetry Summary: Aggregate live counts of Active Trains, On-Time, Delayed, and Severe Delays (> 30 mins).
  - Train Fleet Matrix: Interactive tabular view showing Train Number, Name, Current Speed, Delay, Next Stop, and ETA with color-coded operational severity.

### 1.2 Single Train Live Tracking & Station ETA Timeline (`train_tracking_timeline.png`)
- **Purpose**: Commuter and Station Superintendent granular arrival forecasting view.
- **Key UI Components**:
  - Live Kinematic Gauge Bar: Real-time speed (km/h), cumulative delay, current block section, and live weather conditions (Temperature, Precipitation, Visibility).
  - Station Arrival Matrix: Station-by-station table contrasting:
    - Scheduled Timetable Arrival
    - Baseline Linear Arrival
    - XGBoost Dynamic ML Predicted ETA
    - Difference ($\Delta$ min) & Statistically Calibrated 95% Confidence Interval.
  - Real-Time WebSocket Indicator: Dynamic cyan flash banner with `ETA UPDATED` notification upon locomotive telemetry shift.

### 1.3 Deterministic "Why Did ETA Change?" Explanation Card (`explanation_engine_card.png`)
- **Purpose**: Operational root-cause transparency for commuters and dispatchers.
- **Key UI Components**:
  - Prominent alert box rendered immediately when a downstream arrival shift occurs.
  - Previous ETA vs. New ETA differential indicator (e.g., `20:04 → 20:13 (+9 mins)`).
  - Categorized contributing factors:
    - Kinematic deceleration (`Speed decreased from 105 km/h to 42 km/h`).
    - Environmental impediment (`Adverse weather: Heavy rain 12.4 mm/h, Visibility 350m`).
    - Junction block signaling (`High congestion detected approaching Mathura Junction`).

### 1.4 Model Analytics & Sectional Performance Dashboard (`model_analytics_dashboard.png`)
- **Purpose**: Rigorous empirical validation and railway infrastructure bottleneck analysis.
- **Key UI Components**:
  - Side-by-side performance cards: XGBoost Model vs. Baseline Naive Linear Extrapolation (MAE 2.14m vs 7.82m, RMSE 3.08m vs 10.45m).
  - Error Distribution Accuracy Thresholds ($\pm$ 5 min, $\pm$ 10 min, $\pm$ 15 min).
  - Sectional Delay Variance & Recovery Tendency analysis across corridor segments (NDLS-MTJ, MTJ-AGC, AGC-GWL, GWL-VGLJ, VGLJ-BPL).

---

## 2. Capturing Updated Screenshots
To capture updated screenshots from the live web application:
1. Start the backend: `uvicorn src.main:app --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Navigate to `http://localhost:5173`
4. Use browser developer tools (or screenshot shortcuts: `Win + Shift + S`) to capture full viewport images at $1920 \times 1080$ resolution and place them directly in this directory.
