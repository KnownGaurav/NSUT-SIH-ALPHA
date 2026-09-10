# PRODUCTION REST & WEBSOCKET API SPECIFICATION
**Indian Railways Dynamic Train ETA Prediction Platform**  
*SIH 2026 Problem Statement ID: 26028 &bull; Ministry of Railways*

---

## 1. Architectural Standards & Design Principles

The API layer is built with **FastAPI** following production-grade microservice and railway operational guidelines:
- **Consistent Response Schemas**: All responses are strongly typed using Pydantic v2 data transfer objects (`src/models/api_schemas.py`).
- **Standard HTTP Status Codes**:
  - `200 OK`: Successful resource query / calculation.
  - `400 Bad Request`: Validation failure on input parameters.
  - `404 Not Found`: Train, station, or route not recognized.
  - `500 Internal Server Error`: Unhandled operational exception (intercepted by middleware).
  - `502 Bad Gateway`: External upstream meteorological outage.
- **Operational Header Diagnostics**:
  - `X-Process-Time-Ms`: High-precision microsecond execution duration.
- **Zero Secret Exposure**: Zero API keys or tokens embedded in responses; environment-configured via 12-factor settings (`src/core/config.py`).
- **Interoperability**: Designed to be consumed by:
  - React Desktop / Operations Workstation UI
  - Native Mobile Applications (Flutter / Kotlin / Swift)
  - Control Room Supervision Software (COA / TMS integration)
  - External public inquiry microservices (NTES / IRCTC)

---

## 2. API Endpoints Catalog

### 2.1 System Health & Diagnostics
#### `GET /api/health`
Returns operational liveness and active data provider mode (`simulation` vs `cris_ntes`).
- **Response**:
```json
{
  "status": "ok",
  "service": "railway-eta-api",
  "provider": "simulation",
  "is_simulation": true,
  "version": "1.0.0"
}
```

---

### 2.2 Trains & Route Network
#### `GET /api/trains`
Retrieve all registered coaching trains with origin, destination, and train type.
- **Response**: `List[TrainSummaryResponse]`

#### `GET /api/trains/{train_number}`
Retrieve detailed train metadata with latest live position telemetry and route identity.
- **Response**: `TrainDetailResponse`
- **Errors**: `404 Not Found` if train number is invalid.

#### `GET /api/trains/{train_number}/route`
Retrieve complete scheduled timetable, ordered station sequence, distance from origin, and scheduled dwell times.
- **Response**: `TrainRouteResponse`

#### `GET /api/trains/{train_number}/position`
Retrieve latest real-time GPS coordinates, speed, delay, block section, and active operational event.
- **Response**: `TrainPositionResponse`

---

### 2.3 Dynamic ETA & Explanations
#### `GET /api/trains/{train_number}/eta` *(Aliases: `/eta/dynamic`, `/eta/ml`)*
Compute dynamic ML Expected Time of Arrival predictions for all upcoming stations using XGBoost regression, environmental weather context, and sectional headway congestion.
- **Response**: `DynamicETAResponse`
- **Fields**: `predicted_eta`, `predicted_delay_minutes`, `delta_vs_baseline_minutes`, `confidence` (statistical tolerance 0.0–1.0), `lower_bound`, `upper_bound`.
- **Downstream Corridor Slack (Phase 21)**:
  - `total_slack_minutes_remaining`: Total buffer available (dwell times + timetable sectional slack).
  - `projected_recovery_minutes`: Machine-learning projected recovery before terminal destination.

#### `GET /api/trains/{train_number}/eta/baseline`
Compute deterministic baseline arrival forecast according to scheduled timetable running times plus current accumulated delay.
- **Response**: `BaselineETAResponse`

#### `GET /api/trains/{train_number}/eta/explanation`
Retrieve deterministic operational explanation for why a train's ETA changed.
- **Response**: `ETAExplanationResponse`
- **Attribution Categories**: `SPEED`, `DELAY`, `CONGESTION`, `STATION_HALT`, `RECOVERY`, `WEATHER`.

---

### 2.4 Control Room & Historical Analytics
#### `GET /api/trains/control-room/summary`
Central supervisory status across all active coaching trains on the network.
- **Response**: `ControlRoomSummary`
- **Fields**: `total_active_trains`, `on_time_count`, `delayed_count`, `severe_delay_count`, `deteriorating_count`, `trains` roster.

#### `GET /api/trains/analytics/model-performance`
Empirical performance metrics comparing Baseline vs XGBoost ML ETA on chronologically held-out test runs, section-level profiles, and multi-day zonal performance aggregations.
- **Response**: `ModelAnalyticsResponse`
- **Zonal Performance (Phase 21)**: `zonal_breakdown` grouping railway zones (`NR`, `NCR`, `ECR`, `ER`, `WR`, `WCR`, etc.) with `average_delay_minutes`, `recovery_tendency_percent`, and zone-scaled `model_mae`.

---

### 2.5 Stations, Platform Operations & Environmental Weather
#### `GET /api/stations`
Retrieve all registered stations across Indian Railways corridors with geographical coordinates, zone, and state.
- **Response**: `List[StationResponse]`

#### `GET /api/stations/{station_code}`
Retrieve specific station geographic details by code (e.g. `NDLS`, `CNB`, `HWH`).
- **Response**: `StationResponse`
- **Errors**: `404 Not Found`

#### `GET /api/stations/{station_code}/arrivals` *(Phase 19 & 20)*
Retrieve upcoming train movements, platform assignments, clearance conflicts, and cleaning turnaround readiness.
- **Query Params**: `window_hours` (default: 4)
- **Response**: `StationArrivalsResponse`
- **Fields**: `assigned_platform`, `platform_conflict_flag`, `conflict_with_train`, `turnaround_impact` (`cleaning_depot_status`, `crew_handover_ready`), `current_status`.

#### `GET /api/weather?latitude={lat}&longitude={lon}`
Retrieve meteorological observations (temperature, rain, wind speed, visibility, severe flag) via Open-Meteo API with TTL cache.
- **Response**: `WeatherInfoResponse`

---

### 2.6 Simulation & Disruption Controls
#### `GET /api/simulator/status` *(Alias: `/api/simulation/status`)*
Retrieve normalized operational kinematics across all simulated trains.
- **Response**: `List[NormalizedTrainState]`

#### `POST /api/simulator/event` *(Alias: `/api/simulation/event`)*
Trigger an operational event (`NORMAL_OPERATION`, `SPEED_RESTRICTION`, `CONGESTION`, `UNSCHEDULED_HALT`, `RECOVERY`). Immediately triggers recalculation and WebSocket broadcast.
- **Request**:
```json
{
  "train_number": "12302",
  "event": "CONGESTION"
}
```

#### `POST /api/simulator/tick` *(Alias: `/api/simulation/tick`)*
Manually step physical simulation kinematics.

#### `POST /api/simulator/reset` *(Alias: `/api/simulation/reset`)*
Reset train position to origin with 0 delay.

---

### 2.7 WebSocket Real-Time Stream
#### `WS /ws/trains/{train_number}`
Bidirectional WebSocket stream providing instant telemetry updates and dynamic ETA shifts without polling.
- **On Connection**: Sends initial cached train state.
- **On Telemetry Update**: Broadcasts full enriched payload including `eta_updated` flags, shift deltas, and deterministic explanations.
- **Heartbeat / Keep-Alive**: Send `"ping"` $\rightarrow$ Server responds `{"type":"pong"}`.
