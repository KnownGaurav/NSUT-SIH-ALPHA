# System Architecture: Dynamic Railway ETA Prediction Platform

## Problem Statement
- **ID**: 26028
- **Title**: Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains
- **Ministry**: Ministry of Railways (Government of India)
- **Theme**: Smart Automation

---

## 1. Architectural Philosophy & Reality Grounding
Indian Railways operates one of the most intricate rail networks globally, handling thousands of coaching trains daily across varied topography, single/double-line sections, and dense junction bottlenecks.

### The Problem with Simple Delay Addition
Standard railway enquiry systems typically calculate ETA as:
$$\text{ETA}_{\text{scheduled}} + \text{Delay}_{\text{current}}$$
This naive linear projection fails because:
1. **Sectional Congestion**: A train entering high-density corridors (e.g., Mughalsarai–Kanpur–New Delhi) experiences compounded delays due to precedence conflicts and block section queuing.
2. **Slack & Make-up Time**: Timetables have engineered margins allowing locomotives to recover lost time if signals remain clear and speed restrictions permit.
3. **Station Dwell Non-Linearity**: Dwell times depend on passenger boarding volumes, platform availability, and turnarounds.
4. **Weather & Environmental Disruptions**: Fog in Northern India, heavy monsoons, and extreme temperatures impose speed restrictions (e.g., fog speed caps).

### Provider-Agnostic Interface Strategy
To respect data access boundaries without claiming internal live RTIS (Real-Time Train Information System) or COA (Control Office Application) feeds are freely open:
- The backend features a **Normalized Train Data Interface**.
- **Supported Modes**:
  1. `simulation` (Default): A realistic physics- and timetable-based simulation reproducing authentic Indian Railways routes (e.g., 12301/12302 Howrah Rajdhani, 22435/22436 Vande Bharat).
  2. `third_party`: Standardized REST/WebSocket ingest for third-party aggregate APIs.
  3. `cris_ntes`: Plug-and-play adapter ready for official CRIS/NTES enterprise gateway tokens upon institutional authorization.
- Every prediction and UI payload explicitly tags its provenance (`LIVE_DATA` vs `SIMULATION_DATA`).

---

## 2. High-Level System Architecture

```
+-------------------------------------------------------------------------+
|                          Data Ingestion Layer                           |
|  +--------------------+   +---------------------+   +----------------+  |
|  | CRIS/NTES Gateway  |   | Third-Party Feed    |   | Simulation     |  |
|  | (Enterprise token) |   | (REST/Push)         |   | Engine (Local) |  |
|  +---------+----------+   +----------+----------+   +-------+--------+  |
+------------|-------------------------|----------------------|-----------+
             |                         |                      |
             +-------------------------+----------------------+
                                       |
                                       v
                       +-------------------------------+
                       |  Data Adapter & Normalizer    |
                       |  (Validates to TrainState)    |
                       +---------------+---------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
       +-----------------------+               +-----------------------+
       |   State Store / Redis |               | PostgreSQL / PostGIS  |
       |  (Live Train States)  |               | (Timetables & Track)  |
       +-----------+-----------+               +-----------+-----------+
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                       +-------------------------------+
                       |  Feature Engineering Pipeline |
                       |  - Sectional Congestion Index |
                       |  - Dwell Deviation            |
                       |  - Time of Day / Day of Week  |
                       |  - Weather Restriction Factors|
                       |  - Historical Speed / Margins |
                       +---------------+---------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
       +-----------------------+               +-----------------------+
       |   Baseline Predictor  |               | ML Engine (XGBoost)   |
       |   Sched Time + Delay  |               | Remaining Travel Time |
       +-----------+-----------+               +-----------+-----------+
                   |                                       |
                   +-------------------+-------------------+
                                       |
                                       v
                       +-------------------------------+
                       | Dynamic ETA & Explainability  |
                       | - Final Station ETAs          |
                       | - Uncertainty Bounds (P10/P90)|
                       | - Delay Factor Attribution    |
                       +---------------+---------------+
                                       |
                                       v
                       +-------------------------------+
                       | FastAPI REST & WebSocket APIs |
                       +---------------+---------------+
                                       |
         +-----------------------------+-----------------------------+
         |                                                           |
         v                                                           v
+-----------------------------+             +-----------------------------+
|    Passenger Mobile/Web UI   |             |   Control Room Dashboard    |
| (Clean Timelines, ETAs, Map)|             | (GIS, Section Density, Logs)|
+-----------------------------+             +-----------------------------+
```

---

## 3. Technology Stack & Component Justification

| Component | Choice | Justification |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI (Python 3.12) | High throughput async I/O, native Pydantic schema validation, automatic OpenAPI generation. |
| **Prediction Modeling** | XGBoost / LightGBM | Superior tabular data performance on sectional features, fast inference (<10ms per route), explainability via SHAP/feature weights. |
| **Real-time Pipeline** | WebSockets + In-Memory/Redis | Sub-second latency for position ticks and dynamic ETA updates without polling. |
| **Database** | PostgreSQL / PostGIS | Geospatial coordinates for track alignment, station geometries, and historical run logs. |
| **Frontend Framework** | React + Vite | Clean component lifecycle, fast hot-reloading, low bundle overhead. |
| **Styling** | Tailwind CSS | Industrial styling tokens without bloated design-system overhead. |
| **Mapping Engine** | MapLibre GL / Leaflet | Lightweight, customizable vector and raster tile maps free of restrictive proprietary API costs. |

---

## 4. Engineering Principles & Guidelines

1. **Explicit Data Integrity**: No fabricated live data. All simulated feeds are strictly tagged as `simulation`.
2. **Explainable Predictions**: Every dynamic ETA is paired with human-readable rationale (e.g., *"Section congestion at Mughalsarai junction (+14m); recoverability index: low"*).
3. **No Fluff Design**: High data density, restrained neutral palette, operational clarity over ornamental animations.
4. **Local Runnability**: Capable of booting entirely locally with embedded simulation fixtures for rapid development and testing.

---

## 5. Multi-Tier Operational Subsystems (Phases 19–21)

To fully address the comprehensive scope of **SIH Problem Statement 26028**, the platform provides specialized interfaces catering to all major railway stakeholder groups:

### 1. Station Operations & Platform Occupancy Supervision (`StationOperationsView.jsx`)
- **Dynamic Platform Allocation**: Deterministically projects arriving and departing trains to terminal platforms across major terminals (`NDLS`, `CNB`, `PRYJ`, `BSB`, `HWH`, `DBG`, `TPTY`).
- **Clearance Conflict Engine**: Flags potential platform overlaps when two trains share the same platform within a 25-minute clearance window under dynamic ETA revisions.
- **Turnaround Depot Scheduling**: Categorizes rake handover statuses (`ON_SCHEDULE`, `TIGHT_WINDOW`, `DELAYED_HANDOVER`) to assist pit-line cleaning and crew management.

### 2. Passenger Information System (PIS) LED Board (`PassengerDisplayView.jsx`)
- **Station Display Architecture**: High-contrast amber/yellow LED typography on dark-navy aesthetic matching physical Indian Railways station masthead displays.
- **Blinking Arrival Indicators**: Visual pulse notifications for trains arriving within 10 minutes or experiencing platform alterations.
- **Commuter Mobile Simulation**: High-fidelity phone-frame layout demonstrating how dynamic ETAs propagate to passenger smartphone apps (UTS/IRCTC Rail Connect).

### 3. Zonal Aggregation & Downstream Corridor Slack (`AnalyticsView.jsx` & `StationTimeline.jsx`)
- **Zonal Performance Grouping**: Aggregates sectional delays across all 16 Indian Railways zones (`NR`, `NCR`, `ECR`, `ER`, `WR`, `WCR`, `SCR`, etc.) with empirical recovery rates and zone-scaled MAE.
- **Corridor Timetable Slack**: Dynamically calculates downstream dwell buffer minutes and scheduled sectional slack, estimating the exact minutes of delay a train is forecasted to recover before reaching its destination terminal.

---

## 6. View Navigation Architecture

The frontend application provides seamless, state-preserved switching across five primary operational perspectives:
- `control_room`: Pan-India fleet supervision and network GIS corridor map.
- `tracking`: Single-train deep telemetry, station journey timeline, corridor slack breakdown, and disruption simulation triggers.
- `station_ops`: Platform occupancy supervision, conflict detection, and turnaround depot monitoring.
- `passenger_led`: Authentic station LED departure/arrival display with responsive mobile phone preview.
- `analytics`: Model performance validation, XGBoost feature attribution, and zonal breakdown.

